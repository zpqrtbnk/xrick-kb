#!/usr/bin/env python3
"""
Rick Dangerous 2 -- per-frame RAM trace of the ORIGINAL under Hatari, for comparison with
the port's RD2_TRACE output (port-rd2.md P8). Run from WSL:

    python3 kb2/hatari_rd2_trace.py <out_dir> [frames]

Boots like kb2/hatari_rd2.py (chaos43_noauto.st, --auto A:\\RICK2.PRG, SPACE at the crack
screen). A one-shot breakpoint at level start ($10a4e: jsr $142a0) arms the frame head
$10a54; hit k of the frame head saves RAM $12e00-$17800, $54c00-$56400 and $70000-$7ffff
(concatenated) to <out_dir>/f<k>.bin, so frame 1 is the first frame of the first run
(the first attract demo). A breakpoint re-armed at the current PC fires again at once
(observed: 15 copies of frame 1), so each hit arms a one-shot breakpoint at the next
instruction $10a5c, whose script re-arms $10a54 for hit k+1. The port writes the same
windows at the same point (src/rd2/rd2_sys.c rd2_dbg_frame).
"""
import os, sys, time

sys.path.insert(0, "/usr/share/hatari/hconsole")
import hconsole

REPO = "/mnt/d/d/reverse/xrick"
TOS = "/mnt/d/d/reverse/atari/emutos-512k-1.4/etos512us.img"
DISK = os.path.join(REPO, "disks", "chaos43_noauto.st")
BOOT_WAIT = 8.0
KEY_SPACE = "0x39"
FRAME_HEAD = 0x10a54
LEVEL_START = 0x10a4e    # jsr $142a0 in game_main
NEXT_INSN = 0x10a5c      # the instruction after the frame head (move.w #0,$115dc is 8 bytes)
WINDOWS = [(0x12e00, 0x17800), (0x54c00, 0x56400), (0x70000, 0x80000)]   # same order as the port

LOAD_CALL = 0x10a36      # jsr $123b0 (load_map_if_changed) in game_main
MAP_ADDR = 0x1239c

out = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 800
force_map = int(sys.argv[3]) if len(sys.argv) > 3 else 0   # optional: like kb2/hatari_rd2.py, poke
                                                             # [$1239c] at the first $10a36 hit
# optional joystick sequence (one byte per frame): after the dumps, frame k writes byte k-1 into
# [$1a4fb]; frame 1 also clears the demo flag [$3efb6] -> a real game driven by that input
joyseq = open(sys.argv[4], "rb").read() if len(sys.argv) > 4 else b""
os.makedirs(out, exist_ok=True)
for k in range(1, n + 1):
    with open(os.path.join(out, "f_%d.ini" % k), "w") as f:
        for w, (lo, hi) in enumerate(WINDOWS):
            f.write("savebin %s/f%d.w%d $%x $%x\n" % (out, k, w, lo, hi - lo))
        if joyseq and k == 1:
            f.write("w w $3efb6 0\n")
        if k <= len(joyseq):
            f.write("w b $1a4fb $%02x\n" % joyseq[k - 1])
        if k < n:
            f.write("b pc = $%x :once :file %s/a_%d.ini\n" % (NEXT_INSN, out, k + 1))
        f.write("c\n")
    with open(os.path.join(out, "a_%d.ini" % k), "w") as f:
        f.write("b pc = $%x :once :file %s/f_%d.ini\nc\n" % (FRAME_HEAD, out, k))
    for q in ["f%d.bin" % k] + ["f%d.w%d" % (k, w) for w in range(len(WINDOWS))]:
        if os.path.exists(os.path.join(out, q)):
            os.remove(os.path.join(out, q))
with open(os.path.join(out, "start.ini"), "w") as f:
    f.write("b pc = $%x :once :file %s/f_1.ini\nc\n" % (FRAME_HEAD, out))

h = hconsole.Hatari(["--tos", TOS, "--machine", "st", "--memsize", "1",
                     "--sound", "off", "--fast-forward", "on",
                     "--disk-a", DISK, "--auto", "A:\\RICK2.PRG",
                     "--log-file", os.path.join(out, "hatari.log")])
try:
    time.sleep(1)
    if force_map:
        with open(os.path.join(out, "inject.ini"), "w") as f:
            f.write("w w $%x %d\nc\n" % (MAP_ADDR, force_map))
        h.debug_command("b pc = $%x :once :file %s/inject.ini" % (LOAD_CALL, out))
    h.debug_command("b pc = $%x :once :file %s/start.ini" % (LEVEL_START, out))
    time.sleep(BOOT_WAIT)
    print("[boot] crack screen -> SPACE")
    h.insert_event("keypress " + KEY_SPACE)
    lo, hi = WINDOWS[-1]
    last = os.path.join(out, "f%d.w%d" % (n, len(WINDOWS) - 1))
    t0 = time.time()
    while time.time() - t0 < 900 and not (os.path.exists(last) and os.path.getsize(last) == hi - lo):
        time.sleep(2)
    time.sleep(1)
    got = 0
    for k in range(1, n + 1):                      # concatenate the windows like the port
        parts = [os.path.join(out, "f%d.w%d" % (k, w)) for w in range(len(WINDOWS))]
        if not all(os.path.exists(q) for q in parts):
            break
        with open(os.path.join(out, "f%d.bin" % k), "wb") as fo:
            for q in parts:
                with open(q, "rb") as fi:
                    fo.write(fi.read())
                os.remove(q)
        got += 1
    print("[trace] %d frames saved in %.0fs" % (got, time.time() - t0))
finally:
    try:
        h.kill_hatari()
    except Exception:
        pass
