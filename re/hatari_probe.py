#!/usr/bin/env python3
"""
Rick Dangerous (Atari ST) — Hatari dynamic-verification harness.

Run from WSL.  See re/hatari.md for the architecture.  In short: hconsole binds a Unix
socket, Hatari connects back to it, commands go OUT over the socket, and results come
BACK only via the debugger log file.

    python3 re/hatari_probe.py <probe> [args...]

Probes are registered in PROBES at the bottom.  Every probe gets a booted, rebased
machine: the harness drives the cracktro menu, declines the trainer, dumps RAM and
measures the relocation delta before the probe body runs.

Two invariants, both learned the hard way (re/hatari.md §3, §4):

  * The trainer must always be declined -- it patches game code, which would
    invalidate any comparison against algo-*.md.
  * The relocation delta is deterministic per boot STAGE, but the game relocates
    0x178 bytes between the trainer prompt and the title screen.  A breakpoint armed
    before a stage transition is silently stale afterwards.  Measure at the stage the
    probe runs in, re-measure after any transition, and never hardcode.
"""

import sys, os, time, struct

sys.path.insert(0, "/usr/share/hatari/hconsole")
import hconsole

REPO = "/mnt/d/d/reverse/xrick"
TOS  = "/mnt/d/d/reverse/atari/emutos-512k-1.4/etos512us.img"
OUT  = os.path.join(REPO, "re", "hatari")
os.makedirs(OUT, exist_ok=True)

# --- boot chain timings (disks/rd.st is a Fuzion cracktro, not a bare game disk) ---
MENU_WAIT    = 14.0
MENU_KEY     = "0x3c"          # F2 = RICK   (Atari F1..F4 = 0x3B..0x3E)
TRAINER_WAIT = 12.0
TITLE_WAIT   = 20.0

# reset_sound_chip pokes the PSG through absolute hardware addresses, so its byte
# pattern does not relocate -- a position-independent anchor.  build_sndh.py's
# find_delta() is the canonical implementation; this mirrors it.
ANCHOR     = bytes.fromhex("13fc0007ffff88000039003fffff8802")
REF_RESET  = 0x44C10           # reset_sound_chip,  atari_ram.bin numbering
REF_TRACKS = 0x44F08           # music_track_table
N_TRACKS   = 29

# Reference addresses used by probes, all in atari_ram.bin numbering.
REF = {
    "reset_sound_chip": 0x44C10,
    "play_music":       0x44CCE,
    "music_tick":       0x44E0C,
    "setup_timer_a":    0x45006,
    "silence_channels": 0x45528,
    "music_tracks":     0x44F08,
}


def measure_delta(path):
    """Relocation delta of this dump vs atari_ram.bin numbering, with a self-check."""
    D = open(path, "rb").read()
    hits, i = [], 0
    while True:
        i = D.find(ANCHOR, i)
        if i < 0:
            break
        hits.append(i); i += 1
    if not hits:
        return None, "anchor not found -- the game is not resident in this dump"
    delta = hits[0] - REF_RESET
    tt = REF_TRACKS + delta
    types = [struct.unpack_from(">h", D, tt + k * 8)[0] for k in range(N_TRACKS)]
    if not all(t in (0, 1, 2) for t in types):
        return None, f"delta {delta:#x} rejected -- track table invalid ({types[:8]})"
    return delta, "track-table self-check PASS"


class Session:
    """A booted, rebased Hatari running the game."""

    def __init__(self, disk="disks/rd.st", extra_args=None, auto=True):
        self.log = os.path.join(OUT, "dbg.log")
        self.ram = os.path.join(OUT, "ram-boot.bin")
        for f in (self.log, self.ram):
            if os.path.exists(f):
                os.unlink(f)

        args = ["--tos", TOS,
                "--machine", "st", "--memsize", "1",
                "--sound", "off",
                "--fast-forward", "on",
                "--log-file", os.path.join(OUT, "hatari.log"),
                os.path.join(REPO, disk)]
        if extra_args:
            args = extra_args + args

        print(f"[boot] {disk}")
        self.h = hconsole.Hatari(args)
        self.cmd(f"logfile {self.log}")
        self.delta = None
        if auto:
            self.to_title()

    # -- boot stages (separable, so a probe can sample between them) -------------
    def to_menu(self):
        time.sleep(MENU_WAIT)

    def select_game(self):
        print("[boot] cracktro menu -> F2 (RICK)")
        self.h.insert_event(f"keypress {MENU_KEY}")
        time.sleep(TRAINER_WAIT)

    def answer_trainer(self):
        print("[boot] trainer prompt -> N (never Y: it patches the code)")
        self.h.send_string("n")
        time.sleep(TITLE_WAIT)

    def to_title(self):
        self.to_menu(); self.select_game(); self.answer_trainer()
        self.delta = self.rebase()

    # -- plumbing ---------------------------------------------------------------
    def cmd(self, c):
        self.h.debug_command(c)

    def dump_ram(self, path=None):
        path = path or self.ram
        self.cmd(f"savebin {path} 0 0x100000")
        time.sleep(4)
        return path

    def rebase(self, tag=""):
        self.dump_ram()
        delta, note = measure_delta(self.ram)
        if delta is None:
            print(f"[rebase] {tag} FAILED -- {note}")
            return None
        print(f"[rebase] {tag} delta = {delta:+#x} ({delta:+d})   {note}")
        return delta

    def addr(self, name):
        """A documented address, rebased into this session's live layout."""
        return REF[name] + self.delta

    def shot(self, tag=""):
        self.h.trigger_shortcut("screenshot")
        time.sleep(1)
        print(f"[shot] screenshot taken {tag}")

    def finish(self, tail=6000):
        try:
            self.h.kill_hatari()
        except Exception:
            pass
        time.sleep(1)
        if os.path.exists(self.log):
            print(f"\n===== {self.log} (tail) =====")
            print(open(self.log, errors="replace").read()[-tail:])
        else:
            print("(no debugger log produced)")


# ================================ probes ====================================

def probe_syntax(s):
    """Capture this build's exact debugger syntax, and prove breakpoints fire."""
    for c in ["help", "help b", "help breakpoint", "help trace", "help memdump",
              "help memwrite", "help evaluate", "help info", "help history"]:
        s.cmd(c)
        time.sleep(0.3)

    # music_tick runs at 50 Hz, so a working breakpoint must accumulate hits fast.
    tick = s.addr("music_tick")
    print(f"[syntax] arming trace breakpoint on music_tick @ {tick:#x}")
    s.cmd(f"b pc = ${tick:x} :trace")
    time.sleep(3)
    s.cmd("b")                      # list breakpoints + hit counts
    time.sleep(1)


def probe_boot(s):
    """Just boot, rebase and screenshot -- the smoke test."""
    s.shot("(title screen)")


def probe_relocation(s):
    """Is the relocation delta stable? Sample it at every boot stage.

    An earlier reading suggested the delta varied between boots, but those two
    samples were taken at DIFFERENT stages. This separates the two hypotheses:
    stage-dependent relocation vs. genuinely non-deterministic loading.
    """
    s.to_menu()
    s.select_game()
    print(f"[stage] trainer prompt: {s.rebase('trainer-prompt')}")
    s.answer_trainer()
    print(f"[stage] title: {s.rebase('title')}")
    time.sleep(20)
    print(f"[stage] title+20s (attract?): {s.rebase('title+20s')}")
    s.shot("(after attract wait)")


PROBES = {
    "boot":       probe_boot,
    "syntax":     probe_syntax,
    "relocation": probe_relocation,
}

# Probes that drive the boot themselves rather than starting from the title screen.
MANUAL_BOOT = {"relocation"}

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "boot"
    if name not in PROBES:
        sys.exit(f"unknown probe {name!r}; known: {', '.join(sorted(PROBES))}")
    sess = Session(auto=(name not in MANUAL_BOOT))
    try:
        PROBES[name](sess)
    finally:
        sess.finish()
