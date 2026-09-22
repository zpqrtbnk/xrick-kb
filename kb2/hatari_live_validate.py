#!/usr/bin/env python3
"""
Live validation of RD2's remaining kb2 gaps (#3, #4, #5, #7).  Run from WSL.

    python3 kb2/hatari_live_validate.py <map> [out_dir]

Runs ONE map per process invocation (a 250-deep chained breakpoint crashed the emulated 68000 with bus
errors in an earlier attempt at this session — bus errors at PC=$e00d98 (TOS ROM) reading garbage
addresses, i.e. the guest CPU itself derailed, not just the host script; keeping each map's session short
and independent avoids compounding that risk).

  1. force the map via the same breakpoint method as kb2/hatari_rd2.py
  2. take 5 full-RAM snapshots ~4s apart while its (attract-mode) demo plays
  3. chain PROBE_SAMPLES one-shot breakpoints at $161c8 (the collision probe's single RTS,
     kb2/algo-actors.md section 6), each dumping the 16-byte block $15f0e..$15f1e (probe
     inputs/outputs) to its own small file

Analysis (kb2/analyze_live_validate.py) then answers, from the dumps alone, byte-for-byte:
  - gap #3/#4: did the "already spawned" bit (byte0 bit 0x80) flip on any spawn-table record
    live, and if so was it a monster-path (type 1..0x74), pickup (type >=0x75, mode $20/$28/$2c)
    or trigger-path (byte2 bit7 clear) record? Does the resulting actor slot (for a monster-path
    record) show populated width/height fields (+0x26/+0x28, only ever written by the type<0x75
    descriptor path, kb2/level-tables.md)?
  - gap #5: does each active actor's position/frame change between snapshots match what
    kb2/decode_scripts.py computes for its current script pointer + elapsed frames?
  - gap #7: which `[$15f14]` byte values actually occur live, and do they only ever combine the
    bits kb2/algo-actors.md section 6 already names?
"""
import os
import sys
import time

sys.path.insert(0, "/usr/share/hatari/hconsole")
import hconsole

REPO = "/mnt/d/d/reverse/xrick"
TOS = "/mnt/d/d/reverse/atari/emutos-512k-1.4/etos512us.img"
DISK = os.path.join(REPO, "disks", "chaos43_noauto.st")
BOOT_WAIT = 8.0
KEY_SPACE = "0x39"
MAP_ADDR = 0x1239c
BP_BEFORE_CMP = 0x10a36
BP_AFTER_CMP = 0x10a3c
FRAME_LOOP = 0x10a54
PROBE_RTS = 0x161c8       # query_tile_and_actor_collision's single exit (kb2/algo-actors.md section 6)
PROBE_REGION = (0x15f0e, 16)
SNAP_GAP_FRAMES = 100     # ~4s at 2 vblanks/frame, 50Hz -> 40ms/frame
SNAPSHOTS = 5
PROBE_SAMPLES = 40        # kept modest after the 250-chain crash
PROBE_STRIDE = 15         # sample every Nth hit, not every hit (rapid same-address rearm crashed the emulated CPU twice)
MAP_TIMEOUT = 90.0

m = int(sys.argv[1])
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(REPO, "kb2", "hatari_live")
d = os.path.join(out, "map%d" % m)
os.makedirs(d, exist_ok=True)


def arm_probe_chain(h):
    addr, length = PROBE_REGION
    for i in range(PROBE_SAMPLES):
        fn = os.path.join(d, "probe_%04d.ini" % i)
        dump = os.path.join(d, "probe_%04d.bin" % i)
        with open(fn, "w") as f:
            f.write("savebin %s $%x %d\n" % (dump, addr, length))
            if i + 1 < PROBE_SAMPLES:
                f.write("b pc = $%x :%d :once :file %s\n" % (PROBE_RTS, PROBE_STRIDE, os.path.join(d, "probe_%04d.ini" % (i + 1))))
            f.write("c\n")
    h.debug_command("b pc = $%x :%d :once :file %s" % (PROBE_RTS, PROBE_STRIDE, os.path.join(d, "probe_0000.ini")))


def arm_snapshot_chain(h):
    for i in range(SNAPSHOTS):
        fn = os.path.join(d, "snap_%d.ini" % i)
        dump = os.path.join(d, "snap_%d.bin" % i)
        with open(fn, "w") as f:
            f.write("savebin %s 0 0x100000\n" % dump)
            if i + 1 < SNAPSHOTS:
                f.write("b pc = $%x :%d :once :file %s\n" % (FRAME_LOOP, SNAP_GAP_FRAMES, os.path.join(d, "snap_%d.ini" % (i + 1))))
            f.write("c\n")
    h.debug_command("b pc = $%x :%d :once :file %s" % (FRAME_LOOP, SNAP_GAP_FRAMES, os.path.join(d, "snap_0.ini")))


def force_map(h):
    inject = os.path.join(d, "inject.ini")
    dumpf = os.path.join(d, "afterload.ini")
    ram = os.path.join(d, "loaded.bin")
    if os.path.exists(ram):
        os.remove(ram)
    with open(inject, "w") as f:
        f.write("w w $%x %d\nc\n" % (MAP_ADDR, m))
    with open(dumpf, "w") as f:
        f.write("savebin %s 0 0x100000\nc\n" % ram)
    print("[map %d] arming load breakpoints" % m)
    h.debug_command("b pc = $%x :once :file %s" % (BP_BEFORE_CMP, inject))
    h.debug_command("b pc = $%x :once :file %s" % (BP_AFTER_CMP, dumpf))
    t0 = time.time()
    while time.time() - t0 < MAP_TIMEOUT:
        time.sleep(2)
        if os.path.exists(ram) and os.path.getsize(ram) == 0x100000:
            print("[map %d] loaded after %.0fs" % (m, time.time() - t0))
            return True
    print("[map %d] TIMEOUT" % m)
    return False


h = hconsole.Hatari(["--tos", TOS, "--machine", "st", "--memsize", "1",
                     "--sound", "off", "--fast-forward", "on",
                     "--disk-a", DISK, "--auto", "A:\\RICK2.PRG",
                     "--log-file", os.path.join(d, "hatari.log")])
try:
    time.sleep(BOOT_WAIT)
    print("[boot] crack screen -> SPACE")
    h.insert_event("keypress " + KEY_SPACE)
    time.sleep(20.0)
    if force_map(h):
        arm_snapshot_chain(h)
        arm_probe_chain(h)
        wait_s = SNAPSHOTS * SNAP_GAP_FRAMES * 0.04 + 8
        print("[map %d] capturing for %.0fs" % (m, wait_s))
        time.sleep(wait_s)
        try:
            h.debug_command("b")
        except Exception as e:
            print("[map %d] debug_command('b') failed (emulator may have crashed): %r" % (m, e))
finally:
    try:
        h.kill_hatari()
    except Exception as e:
        print("[map %d] kill_hatari failed (already dead?): %r" % (m, e))
print("[map %d] done ->" % m, d)
