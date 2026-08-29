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


PROBES = {
    "boot":  probe_boot,
    "drive": probe_drive,
}

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "boot"
    if name not in PROBES:
        sys.exit("unknown probe %r; known: %s" % (name, ", ".join(sorted(PROBES))))
    sess = Session()
    try:
        PROBES[name](sess)
    finally:
        sess.finish()
