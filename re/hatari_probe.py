#!/usr/bin/env python3
"""
Rick Dangerous (Atari ST) - Hatari dynamic-verification harness.

Run from WSL. See re/hatari.md for the architecture. In short: hconsole binds a Unix
socket, Hatari connects back to it, commands go OUT over the socket, and results come
BACK on Hatari's stdout.

    python3 re/hatari_probe.py <probe> [args...]

Boot path -- use chaos43, NOT rd.st
-----------------------------------
disks/chaos43/RICK.PRG is the build the Ghidra dump was taken from: it reproduces the
documented layout exactly (delta -0x2054, identical to atari_ram_1M.bin). It is
autostarted from a GEMDOS drive, so no floppy, no mouse and no compilation menu:

    trainer menu   F1 lives / F2 ammo / F3 dynamite / F4 select level -- ALL DEFAULT OFF
                   "Press space to play"
    title screen
    gameplay       entered by asserting FIRE

Leave F1..F3 off: they patch game code and would invalidate any comparison against
algo-*.md. (disks/rd.st is a different, Fuzion-cracked build with its own loader and a
different relocation; it is not the analysed binary. Do not use it.)

Driving the game
----------------
hatari-event cannot press fire -- it injects emulated IKBD scancodes, while
--joy1 keys intercepts HOST keys, so neither reaches a joystick read. Instead we poke
the decoded joystick byte the KB documents at 0x4922B. keyboard_isr only rewrites it
when an IKBD packet arrives, and with no joystick attached those are rare, so a poke
sticks. This makes gameplay fully scriptable.

Breakpoint gotcha
-----------------
NEVER use :quiet as a detector. It suppresses the per-hit :trace output, and the b
listing carries no hit counter -- so a firing breakpoint looks identical to one that
never fired. Use ":trace :once": it prints one line, continues, and deletes itself.
Presence in a later b listing means it never fired.
"""

import sys, os, time, struct, shutil, glob

sys.path.insert(0, "/usr/share/hatari/hconsole")
import hconsole

REPO = "/mnt/d/d/reverse/xrick"
TOS  = "/mnt/d/d/reverse/atari/emutos-512k-1.4/etos512us.img"
OUT  = os.path.join(REPO, "re", "hatari")
HD   = os.path.expanduser("~/rickhd")
os.makedirs(OUT, exist_ok=True)

MENU_WAIT  = 20.0        # RICK.PRG unpacking -> trainer menu
TITLE_WAIT = 22.0        # space -> title screen
KEY_SPACE  = "0x39"

# Joystick bits, per re/data-structures.md (joystick1_state @ 0x4922B).
J_UP, J_DOWN, J_LEFT, J_RIGHT, J_FIRE = 0x01, 0x02, 0x04, 0x08, 0x80

ANCHOR     = bytes.fromhex("13fc0007ffff88000039003fffff8802")
REF_RESET  = 0x44C10
REF_TRACKS = 0x44F08
N_TRACKS   = 29

# Reference addresses, in atari_ram.bin numbering.
REF = {
    "reset_sound_chip":  0x44C10,
    "play_music":        0x44CCE,
    "music_tick":        0x44E0C,
    "setup_timer_a":     0x45006,
    "silence_channels":  0x45528,
    "music_tracks":      0x44F08,
    "player_controller": 0x4C046,
    "joystick1_state":   0x4922B,
    "keyboard_isr":      0x49262,
    "level_index":       0x4B586,
    "start_level":       0x4B588,
    # --- G1 targets ---
    "level_select_choice":     0x498C0,   # word
    "max_level_reached":       0x498C2,   # word; run_selection_menu returns early if 0
    "pooky_flag":              0x498C4,   # word; POOKY9999 sets it to 0x00FF
    "run_selection_menu":      0x498C6,   # level select, gated by pooky_flag
    "show_selection_menu":     0x499A0,
    "probe_player_tile_collision": 0x4CD70,
    "player_collision_flags":  0x4D00A,   # byte: 02 ladder 04 lethal 10 one-way
                                          #       20 floor 40 solid 80 ladder-top
    "scripted_trap_update":    0x4D15C,

    # --- T11: MFP Timer-A digi-sample rate -----------------------------------------
    "smp_rate_table":   0x44FF0,   # 2 bytes/entry: [0]=TACR prescaler sel, [1]=TADR count
    "smp_tacr":         0x45000,   # pending sample's TACR
    "smp_tadr":         0x45001,   # pending sample's TADR
    "snd_state":        0x45002,   # 0 idle / 1 tracked music / 2 start sample / 0xFF playing
    "smp_loop":         0x45004,   # ISR: 0 = stop at terminator, non-0 = rewind
    "smp_track":        0x45005,
    "smp_start_ptr":    0x44FFC,   # long: sample start
    "smp_cur_ptr":      0x457C8,   # long: ISR advances this by 1 byte per interrupt
    "timer_a_isr":      0x45022,
    "song_active":      0x45096,

    # --- T6: the eight bTriggerFlags bits, addressed by their TAKEN branch ---------
    # The btst site itself executes for every trap entity every frame regardless of the
    # bit's value, so breakpointing it proves nothing. These are the addresses control
    # only reaches when the bit is actually SET (and, for the *_fired ones, when the
    # associated hit test also succeeded).
    "trig_fired":       0x4D258,   # a trap actually triggered: move.b #-1,(0x47,A0)
    "b80_set":          0x4D19A,   # 0x80 player-touch: bit set, probing player+(0x0B,0x0A)
    "b80_fired":        0x4D1B4,   #   ... and the player was inside the trigger box
    "b40_set":          0x4D1C0,   # 0x40 stick jab: bit set
    "b40_fired":        0x4D1DA,   #   ... and the jab point hit
    "b20_set":          0x4D1E4,   # 0x20 bullet: bit set
    "b20_hit":          0x4D1FE,   #   ... and the bullet hit (clr.w bullet_active)
    "b02_despawn":      0x4D20C,   # 0x02 SET   -> despawn_offscreen_entity route
    "b02_erase":        0x4D21C,   # 0x02 CLEAR -> bset erase-pending render bits
    "b10_set":          0x4D236,   # 0x10 explosion: bit set
    "b10_fired":        0x4D250,   #   ... and the blast overlapped
    "b04_lethal_idle":  0x4D170,   # 0x04 lethal while IDLE     -> wHazardActive = 0xFF
    "b08_lethal_trig":  0x4D284,   # 0x08 lethal while TRIGGERED-> wHazardActive = 0xFF
    "b01_oneshot":      0x4D368,   # 0x01 one-shot: despawn at path end
    "landing_rebound_pc":      0x4C1DE,   # move.w #0xfe,D4 ; sub.w nVelY,D4
    "nVelY":                   0x4A756,   # word
    "resolve_channel_note_period": 0x4538C,
    "note_period_table":       0x45720,
}


def stage_hd():
    """Build the GEMDOS drive: RICK.PRG plus its hunks, WITHOUT the AUTO folder
    (AUTO/MENU44.PRG would launch the compilation menu and steal the boot)."""
    src = os.path.join(REPO, "disks", "chaos43")
    if not os.path.isdir(HD) or not os.path.exists(os.path.join(HD, "RICK.PRG")):
        os.makedirs(HD, exist_ok=True)
        names = ["RICK.PRG", "RICK2.PRG"]
        names += [os.path.basename(p) for p in glob.glob(os.path.join(src, "RICK_*.HNK"))]
        for f in names:
            shutil.copy2(os.path.join(src, f), HD)
    return HD


def measure_delta(path):
    """Relocation delta vs atari_ram.bin numbering, with a self-check."""
    D = open(path, "rb").read()
    i = D.find(ANCHOR)
    if i < 0:
        return None, "anchor not found -- the game is not resident in this dump"
    delta = i - REF_RESET
    tt = REF_TRACKS + delta
    types = [struct.unpack_from(">h", D, tt + k * 8)[0] for k in range(N_TRACKS)]
    if not all(t in (0, 1, 2) for t in types):
        return None, "delta %#x rejected -- track table invalid (%s)" % (delta, types[:8])
    return delta, "track-table self-check PASS"


class Session:
    """A booted, rebased Hatari running the analysed build, in gameplay."""

    def __init__(self, auto=True, extra_args=None):
        stage_hd()
        self.ram = os.path.join(OUT, "ram.bin")
        args = ["--tos", TOS, "--machine", "st", "--memsize", "1",
                "--sound", "off", "--fast-forward", "on",
                "--harddrive", HD, "--auto", "C:\\RICK.PRG",
                "--log-file", os.path.join(OUT, "hatari.log")]
        if extra_args:
            args = extra_args + args
        print("[boot] autostarting C:\\RICK.PRG from the GEMDOS drive")
        self.h = hconsole.Hatari(args)
        self.delta = None
        if auto:
            self.to_game()

    # -- boot stages -------------------------------------------------------------
    def to_title(self):
        time.sleep(MENU_WAIT)
        print("[boot] trainer menu -> SPACE (F1..F3 cheats left OFF for fidelity)")
        self.h.insert_event("keypress " + KEY_SPACE)
        time.sleep(TITLE_WAIT)
        self.delta = self.rebase("title")

    def to_game(self):
        self.to_title()
        print("[boot] asserting FIRE to start the game")
        self.hold(J_FIRE, rounds=8)
        time.sleep(2)
        self.joy(0)
        # Fast-forward is ~48x realtime, so a 0.35s poke gap spans ~17 EMULATED
        # seconds -- far too coarse to steer with, and Rick dies to the opening
        # boulder while an input is still held. Drop to realtime now that boot is done.
        print("[boot] fast-forward OFF (realtime) for gameplay")
        self.h.change_option("--fast-forward off")
        time.sleep(2)
        self.delta = self.rebase("in-game")

    # -- plumbing ----------------------------------------------------------------
    def cmd(self, c):
        self.h.debug_command(c)

    def addr(self, name):
        return REF[name] + self.delta

    def joy(self, bits):
        """Assert a joystick state (one poke)."""
        self.cmd("memwrite $%x $%02x" % (self.addr("joystick1_state"), bits))

    def tap(self, bits, hold=0.15, after=0.45):
        """A single press-and-release, for menus where FIRE means confirm."""
        self.joy(bits); time.sleep(hold)
        self.joy(0);    time.sleep(after)

    def hold(self, bits, rounds=6, gap=0.12):
        """Hold a joystick state across several frames."""
        for _ in range(rounds):
            self.joy(bits)
            time.sleep(gap)

    def watch(self, name, once=True):
        """Arm a detector. Prints one line if it fires; survives in b if it never does."""
        opts = ":trace :once" if once else ":trace"
        self.cmd("b pc = $%x %s" % (self.addr(name), opts))
        time.sleep(0.4)

    def dump_ram(self, path=None):
        path = path or self.ram
        self.cmd("savebin %s 0 0x100000" % path)
        time.sleep(4)
        return path

    def rebase(self, tag=""):
        self.dump_ram()
        delta, note = measure_delta(self.ram)
        if delta is None:
            print("[rebase] %s FAILED -- %s" % (tag, note))
            return self.delta
        print("[rebase] %s delta = %+#x (%+d)   %s" % (tag, delta, delta, note))
        return delta

    def shot(self, tag=""):
        self.h.trigger_shortcut("screenshot")
        time.sleep(1.5)
        print("[shot] %s" % tag)

    def finish(self):
        print("[end] remaining (= never fired) breakpoints:")
        self.cmd("b"); time.sleep(1.2)
        try:
            self.h.kill_hatari()
        except Exception:
            pass
        time.sleep(1)


# ================================ probes ====================================

def probe_boot(s):
    """Smoke test: reach gameplay, screenshot, confirm the game loop runs."""
    s.watch("player_controller")
    time.sleep(4)
    s.shot("(gameplay)")


def probe_drive(s):
    """Prove Rick responds to scripted joystick input: walk right, left, jump."""
    s.shot("(start position)")
    for tag, bits in [("right", J_RIGHT), ("left", J_LEFT), ("jump", J_UP)]:
        print("[drive] %s" % tag)
        s.hold(bits, rounds=10)
        s.joy(0)
        time.sleep(1)
        s.shot("(after %s)" % tag)


def probe_pooky(s):
    """G1 item 2: what does the POOKY9999 easter egg actually do?

    algo-system.md: entering "POOKY" + END in the name grid sets word 0x498C4 = 0x00FF.
    algo-level.md: that flag gates run_selection_menu, making level select a cheat-only
    screen. Setting the flag directly tests the claim AND, if it works, gives us level
    access with NO code modification -- unlike the cracktro's F4, which may patch.
    """
    s.cmd("help b"); time.sleep(0.6)          # capture full option list (is :file available?)

    flag = s.addr("pooky_flag")
    print("[pooky] flag @ %#x; baseline (flag clear)" % flag)
    s.cmd("memdump $%x-$%x" % (flag, flag + 1)); time.sleep(0.6)
    s.watch("run_selection_menu")             # must NOT fire while flag is clear
    s.watch("show_selection_menu")
    time.sleep(3)
    print("[pooky] --- setting flag to 0x00FF ---")
    s.cmd("memwrite w $%x $00ff" % flag); time.sleep(0.5)
    s.cmd("memdump $%x-$%x" % (flag, flag + 1)); time.sleep(0.6)
    s.shot("(title, flag set)")

    print("[pooky] asserting FIRE to start")
    s.hold(J_FIRE, rounds=10)
    s.joy(0)
    time.sleep(6)
    s.shot("(after fire with POOKY flag set)")
    time.sleep(3)
    s.shot("(a moment later)")


def probe_levelsel(s):
    """G1 item 2 completed, and level access for items 1/3/4.

    run_selection_menu returns immediately unless BOTH menu_enabled (0x498C4, the POOKY
    flag) and max_level_reached (0x498C2) are non-zero -- and the latter is 0 on a fresh
    boot, which is why the previous run fell straight through into level 1. Setting both
    gives the game's OWN level select with no code patching, unlike the cracktro's F4.
    FIRE is the menu's confirm, so it must be tapped, never held.
    """
    for nm, val in [("pooky_flag", "00ff"), ("max_level_reached", "0003")]:
        s.cmd("memwrite w $%x $%s" % (s.addr(nm), val)); time.sleep(0.4)
        s.cmd("memdump $%x-$%x" % (s.addr(nm), s.addr(nm) + 1)); time.sleep(0.5)
    print("[levelsel] flags set; tapping FIRE to leave the title")
    s.watch("run_selection_menu")
    s.tap(J_FIRE)
    time.sleep(3)
    s.shot("(expect: level-select menu)")

    print("[levelsel] moving DOWN twice, then confirming")
    s.tap(J_DOWN); s.shot("(after DOWN 1)")
    s.tap(J_DOWN); s.shot("(after DOWN 2)")
    s.cmd("memdump $%x-$%x" % (s.addr("level_select_choice"), s.addr("level_select_choice") + 1))
    time.sleep(0.5)
    s.tap(J_FIRE)
    time.sleep(6)
    s.shot("(expect: the chosen level)")
    s.cmd("memdump $%x-$%x" % (s.addr("level_index"), s.addr("level_index") + 1))
    time.sleep(0.6)


def probe_rebound(s):
    """G1 item 5: how big is nVelY at the moment of landing?

    The arithmetic is certain (disassembly at 0x4C1DE: move.w #0xfe,D4 / sub.w nVelY,D4),
    so the only question is the VELOCITY RANGE landings actually occur at -- that decides
    whether 0xFE - nVelY is a token nudge or a real upward rebound. Rather than log every
    landing, arm one conditional breakpoint per threshold and see which ones ever fire.
    """
    pc, v = s.addr("landing_rebound_pc"), s.addr("nVelY")
    print("[rebound] landing site %#x, nVelY %#x" % (pc, v))
    s.cmd("b pc = $%x :trace :once" % pc)                      # does landing happen at all
    time.sleep(0.4)
    for th in (0x200, 0x400, 0x800):
        s.cmd("b pc = $%x && ($%x).w > $%x :trace :once" % (pc, v, th))
        time.sleep(0.4)
    # UP alone does not jump from standing, but the opening room has drops -- walking
    # right produces real falls, which reach higher velocities than a jump anyway.
    print("[rebound] armed; walking right to fall off ledges")
    for i in range(8):
        s.hold(J_RIGHT, rounds=12)
        s.joy(0)
        time.sleep(1.2)
        s.cmd("memdump $%x-$%x" % (v, v + 1))
        time.sleep(0.4)
        s.shot("(step %d)" % i)


TRIG_SITES = [
    ("trig_fired",      "A TRAP TRIGGERED (any cause)"),
    ("b80_set",         "0x80 player-touch   bit set"),
    ("b80_fired",       "0x80 player-touch   TRIGGERED"),
    ("b40_set",         "0x40 stick jab      bit set"),
    ("b40_fired",       "0x40 stick jab      TRIGGERED"),
    ("b20_set",         "0x20 bullet         bit set"),
    ("b20_hit",         "0x20 bullet         HIT (bullet consumed)"),
    ("b02_despawn",     "0x02 SET   -> despawn route"),
    ("b02_erase",       "0x02 CLEAR -> erase-pending route"),
    ("b10_set",         "0x10 explosion      bit set"),
    ("b10_fired",       "0x10 explosion      TRIGGERED"),
    ("b04_lethal_idle", "0x04 lethal while IDLE      armed"),
    ("b08_lethal_trig", "0x08 lethal while TRIGGERED armed"),
    ("b01_oneshot",     "0x01 one-shot       despawn at path end"),
]


def probe_triggers(s):
    """T6: watch the bTriggerFlags bits actually fire in a running game.

    The census in re/entities.md already proves all eight bits appear in shipped data;
    what has never been done is watching one FIRE. Each detector sits on the taken
    branch, so a hit means the bit was set and (for *_fired / *_hit) the associated
    test succeeded. Anything still listed by the final `b` never fired.
    """
    print("[trig] delta %+#x" % s.delta)
    for name, what in TRIG_SITES:
        print("[trig] arm %-16s %#08x  %s" % (name, s.addr(name), what))
        s.watch(name, once=True)

    # Level 1 opens with a boulder trap armed for player-touch, then spikes and darts.
    # Walk right in bursts; jab, shoot and drop dynamite along the way so the 0x40,
    # 0x20 and 0x10 paths get a chance too.
    for i in range(10):
        print("[trig] --- leg %d: walk right ---" % i)
        s.hold(J_RIGHT, rounds=14)
        s.joy(0); time.sleep(1.0)

        s.tap(J_FIRE)                       # stick jab  -> 0x40
        time.sleep(0.6)
        s.tap(J_FIRE | J_UP)                # shoot      -> 0x20
        time.sleep(0.8)
        if i % 3 == 2:
            s.tap(J_FIRE | J_DOWN)          # dynamite   -> 0x10 (after its fuse)
            time.sleep(2.5)
        s.shot("leg %d" % i)


def probe_triggers2(s):
    """T6 second pass: the six bits the first run never reached.

    Run 1 confirmed the 0x80 -> trigger -> 0x08 chain but Rick never left the opening
    room (GAME OVER by leg 9 -- he died to the boulder), so 0x40/0x20/0x10/0x04/0x02/0x01
    were never given a trap that carries them. Use the game's OWN level select (POOKY +
    max_level_reached, no code patching) to reach Egypt, then stand still first: 0x04
    (lethal while IDLE) arms every frame for any idle entity carrying it and needs no
    player action at all.
    """
    for nm, val in [("pooky_flag", "00ff"), ("max_level_reached", "0003")]:
        s.cmd("memwrite w $%x $%s" % (s.addr(nm), val)); time.sleep(0.4)
    print("[trig2] entering the game's level-select menu")
    s.tap(J_FIRE); time.sleep(3)
    s.tap(J_DOWN); time.sleep(0.6)          # level 1 -> level 2 (Egypt)
    s.tap(J_FIRE); time.sleep(6)
    s.shot("(expect: Egypt)")
    s.cmd("memdump $%x-$%x" % (s.addr("level_index"), s.addr("level_index") + 1))
    time.sleep(0.6)

    remaining = ["b40_set", "b40_fired", "b20_set", "b20_hit", "b02_despawn",
                 "b02_erase", "b10_set", "b10_fired", "b04_lethal_idle",
                 "b01_oneshot", "trig_fired", "b08_lethal_trig"]
    for name in remaining:
        print("[trig2] arm %-16s %#08x" % (name, s.addr(name)))
        s.watch(name, once=True)

    print("[trig2] standing still (0x04 needs no input at all)")
    time.sleep(6)
    s.shot("idle")

    for i in range(8):
        print("[trig2] --- leg %d ---" % i)
        s.tap(J_FIRE | J_UP);   time.sleep(1.2)     # shoot   -> 0x20 / 0x02
        s.tap(J_FIRE);          time.sleep(0.8)     # jab     -> 0x40
        if i % 2 == 1:
            s.tap(J_FIRE | J_DOWN); time.sleep(3.0) # dynamite-> 0x10
        s.hold(J_RIGHT, rounds=22, gap=0.07)        # keep moving, do not pause
        s.joy(0); time.sleep(0.5)
        s.shot("leg %d" % i)


def probe_timera(s):
    """T11: measure the MFP Timer-A interrupt rate and check the prescaler table.

    algo-music.md states rate = 2457600 / (prescaler(TACR) * TADR) with TACR selecting
    1->/4 2->/10 3->/16 4->/50 5->/64 6->/100 7->/200. Those divisors are hardware
    convention, never read out of the game -- the one assumption left in re/.

    No gameplay needed: poke exactly what play_music's type-2 branch writes, then let
    the VBL music_tick start Timer A. The ISR advances smp_cur_ptr by one byte per
    interrupt, so the pointer IS the interrupt counter. smp_loop is held non-zero so the
    sample rewinds instead of stopping, giving an arbitrarily long measuring window.

    All three type-2 tracks carry nParam_index 0 -> table entry [0] = TACR 6, TADR 5,
    which the documented table predicts as 2457600/(100*5) = 4915.2 Hz.
    """
    tacr, tadr = 6, 5
    print("[timera] arming sample: TACR=%d TADR=%d (table entry 0)" % (tacr, tadr))
    for nm, val in [("song_active", 0x00), ("smp_loop", 0xFF), ("smp_track", 0x08),
                    ("smp_tacr", tacr), ("smp_tadr", tadr)]:
        s.cmd("memwrite $%x $%02x" % (s.addr(nm), val)); time.sleep(0.25)
    # sample start = track 8's data pointer, rebased
    s.cmd("memwrite l $%x $%08x" % (s.addr("smp_start_ptr"), 0x0004DF86 + s.delta))
    time.sleep(0.3)
    s.cmd("memwrite $%x $02" % s.addr("snd_state"))       # 2 = "start sample"
    time.sleep(1.0)
    s.cmd("memdump $%x-$%x" % (s.addr("snd_state"), s.addr("snd_state")))
    time.sleep(0.5)

    print("[timera] sampling the ISR pointer; each MARK is followed by its memdump")
    for i in range(24):
        s.cmd("memwrite $%x $ff" % s.addr("smp_loop"))     # keep it looping
        t = time.time()
        print("[timera] MARK %02d t=%.4f" % (i, t))
        sys.stdout.flush()
        s.cmd("memdump $%x-$%x" % (s.addr("smp_cur_ptr"), s.addr("smp_cur_ptr") + 3))
        time.sleep(0.45)
    print("[timera] done; sample pointer base = $%x" % (0x0004DF86 + s.delta))


PROBES = {
    "timera": probe_timera,
    "triggers2": probe_triggers2,
    "triggers": probe_triggers,
    "rebound":  probe_rebound,
    "levelsel": probe_levelsel,
    "boot":  probe_boot,
    "drive": probe_drive,
    "pooky": probe_pooky,
}

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "boot"
    if name not in PROBES:
        sys.exit("unknown probe %r; known: %s" % (name, ", ".join(sorted(PROBES))))
    TITLE_ONLY = {"pooky", "levelsel", "triggers2"}
    sess = Session(auto=(name not in TITLE_ONLY))
    if name in TITLE_ONLY:
        sess.to_title()
        sess.h.change_option("--fast-forward off")
        time.sleep(2)
    try:
        PROBES[name](sess)
    finally:
        sess.finish()
