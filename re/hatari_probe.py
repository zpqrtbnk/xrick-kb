#!/usr/bin/env python3
"""
Rick Dangerous (Atari ST) — Hatari dynamic-verification driver.

Run from WSL. See re/hatari.md for the architecture; the short version is that
hconsole binds a Unix socket, Hatari connects back to it, commands go OUT over the
socket and results come BACK via the debugger log file.

Boot sequence for disks/rd.st (a Fuzion cracktro compilation, not a bare game disk):

    cracktro menu   F1 CHASE HQ / F2 RICK / F3 SUPER SPRINT / F4 QUARTZ
    trainer prompt  "TRAINER (Y/N) ?"  -> ALWAYS answer N

Answering Y patches the game code (infinite lives etc.), which would invalidate every
comparison against the transcriptions in algo-*.md. N is not optional for this work.

Pass 0 (this file): boot to the title screen, dump RAM, and measure the relocation
delta. The delta is NOT stable across boots -- it must be re-measured every session
and applied to every address before use.

    python3 re/hatari_probe.py [disk] [play_seconds]
"""

import sys, os, time, struct

sys.path.insert(0, "/usr/share/hatari/hconsole")
import hconsole

REPO = "/mnt/d/d/reverse/xrick"
TOS  = "/mnt/d/d/reverse/atari/emutos-512k-1.4/etos512us.img"
OUT  = os.path.join(REPO, "re", "hatari")
os.makedirs(OUT, exist_ok=True)

disk = sys.argv[1] if len(sys.argv) > 1 else "disks/rd.st"
wait = float(sys.argv[2]) if len(sys.argv) > 2 else 25.0

MENU_WAIT = 14.0
MENU_KEY  = "0x3c"            # F2 = RICK  (Atari F1..F4 = 0x3B..0x3E)
TRAINER_WAIT = 12.0

# reset_sound_chip pokes the PSG through absolute hardware addresses, so its byte
# pattern does not relocate -- a position-independent anchor. Kept in sync with
# build_sndh.py's find_delta(), which is the canonical implementation.
ANCHOR     = bytes.fromhex("13fc0007ffff88000039003fffff8802")
REF_RESET  = 0x44C10          # reset_sound_chip,     atari_ram.bin numbering
REF_TRACKS = 0x44F08          # music_track_table
N_TRACKS   = 29


def measure_delta(path):
    """Return the relocation delta of this dump vs atari_ram.bin numbering."""
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


dbglog = os.path.join(OUT, "dbg.log")
ram    = os.path.join(OUT, "ram-boot.bin")
for f in (dbglog, ram):
    if os.path.exists(f):
        os.unlink(f)

args = ["--tos", TOS,
        "--machine", "st", "--memsize", "1",   # matches hatari.sh and the 1 MB dump
        "--sound", "off",
        "--fast-forward", "on",
        "--log-file", os.path.join(OUT, "hatari.log"),
        os.path.join(REPO, disk)]

print(f"booting {disk} ...")
h = hconsole.Hatari(args)
h.debug_command(f"logfile {dbglog}")

time.sleep(MENU_WAIT)
print(f"cracktro menu -> F2 (RICK), scancode {MENU_KEY}")
h.insert_event(f"keypress {MENU_KEY}")

time.sleep(TRAINER_WAIT)
print('trainer prompt -> N (never Y: it patches the code)')
h.send_string("n")

time.sleep(wait)
h.debug_command(f"savebin {ram} 0 0x100000")
time.sleep(4)
h.trigger_shortcut("screenshot")
time.sleep(1)
h.kill_hatari()
time.sleep(1)

if os.path.exists(ram):
    print(f"\nRAM dump: {os.path.getsize(ram):,} bytes -> {ram}")
    delta, note = measure_delta(ram)
    if delta is None:
        print(f"RELOCATION: FAILED -- {note}")
    else:
        print(f"RELOCATION DELTA = {delta:+#x} ({delta:+d})   {note}")
        print(f"  a documented address A is live at A {delta:+#x}")
else:
    print("\nNO RAM DUMP produced.")
