#!/usr/bin/env python3
"""
Rick Dangerous 2 (Atari ST) - minimal Hatari harness. Run from WSL.

    python3 kb2/hatari_rd2.py [out_dir] [wait_after_key_seconds] [maps]

    maps   optional comma list, e.g. 2,3,4: after the first dump, force each map in turn
           and dump RAM to <out_dir>/ram_map<N>.bin

Boots disks/chaos43_noauto.st (Chaos #43 disk with AUTO/MENU44.PRG renamed .DIS so TOS
falls through to --auto), autostarts A:\\RICK2.PRG, presses SPACE at the crack screen, waits,
then dumps the full 1 MB of ST RAM to <out_dir>/ram.bin. Same architecture as
kb/hatari_probe.py (hconsole socket: commands out, results on stdout).

Forcing a map (disassembly read in Ghidra 2026-09-19; see PLAN.md T24 "Second pass"):
  * game_main ($10992..$10c27): $10a30 level_start does `jsr $123b0` at $10a36 (once per
    level/demo (re)start, NOT per frame; the per-frame loop is $10a54). $123b0 is
    load_map_if_changed: `move.w $1239c,D0 ; cmp.w $1239e,D0 ; bne load_map($123c4)`.
  * Poking $1239c from outside does NOT work: something puts it back to 1 within a second
    while the attract demo runs (observed: polled current=2, then 1, loaded stayed 1).
  * So we do it atomically with two one-shot debugger breakpoints:
      b pc=$10a36 :file inject   -> "w w $1239c N ; c"     (just before the compare)
      b pc=$10a3c :file dump     -> "savebin ... ; c"      (just after load_map returned)
    load_map loads RICK_(2N-1).HNK -> $3EFC0 and RICK_(2N).HNK -> $65300, then $1795c
    unpacks the latter to $53400, all inside that one call.

RICK2.PRG does raw floppy reads, so it needs real floppy emulation (--disk-a), NOT
--harddrive (kb2/xrick2-ref.md, "Booting RICK2.PRG in Hatari").
"""
import os, sys, time

sys.path.insert(0, "/usr/share/hatari/hconsole")
import hconsole

REPO = "/mnt/d/d/reverse/xrick"
TOS = "/mnt/d/d/reverse/atari/emutos-512k-1.4/etos512us.img"
DISK = os.path.join(REPO, "disks", "chaos43_noauto.st")
BOOT_WAIT = 8.0          # RICK2.PRG loads -> crack screen
KEY_SPACE = "0x39"       # scancode 57
MAP_ADDR = 0x1239c       # g_current_map_number (word)
BP_BEFORE_CMP = 0x10a36  # jsr $123b0 in level_start
BP_AFTER_CMP = 0x10a3c   # instruction after it
FRAME_LOOP = 0x10a54     # per-frame loop head (game_main)
LATER_FRAMES = 120       # frames after the load at which the second dump + palette are taken
MAP_TIMEOUT = 90.0

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "kb2", "hatari")
wait = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
maps = [int(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else []
os.makedirs(out, exist_ok=True)


def dump(h, name):
    path = os.path.join(out, name)
    print("[dump] ->", path)
    h.debug_command("savebin %s 0 0x100000" % path)
    time.sleep(4)


def frame_ram_path(m):
    return os.path.join(out, "pal_map%d.bin" % m)


def force_map(h, m):
    inject = os.path.join(out, "inject%d.ini" % m)
    dumpf = os.path.join(out, "dump%d.ini" % m)
    ram = os.path.join(out, "ram_map%d.bin" % m)
    if os.path.exists(ram):
        os.remove(ram)
    later = os.path.join(out, "later%d.ini" % m)
    frame_ram = os.path.join(out, "ram_map%d_f%d.bin" % (m, LATER_FRAMES))
    pal = frame_ram_path(m)
    for f_ in (frame_ram, pal):
        if os.path.exists(f_):
            os.remove(f_)
    with open(later, "w") as f:
        # LATER_FRAMES frame_loop iterations after the load: full RAM + the 16 palette words
        f.write("savebin %s 0 0x100000\nsavebin %s $ff8240 32\nc\n" % (frame_ram, pal))
    with open(inject, "w") as f:
        f.write("w w $%x %d\nb pc = $%x :%d :once :file %s\nc\n"
                % (MAP_ADDR, m, FRAME_LOOP, LATER_FRAMES, later))
    with open(dumpf, "w") as f:
        f.write("savebin %s 0 0x100000\nc\n" % ram)
    print("[map] arming breakpoints to load map %d" % m)
    h.debug_command("b pc = $%x :once :file %s" % (BP_BEFORE_CMP, inject))
    h.debug_command("b pc = $%x :once :file %s" % (BP_AFTER_CMP, dumpf))
    t0 = time.time()
    while time.time() - t0 < MAP_TIMEOUT:
        time.sleep(2)
        if os.path.exists(ram) and os.path.getsize(ram) == 0x100000:
            time.sleep(3)
            print("[map] map %d captured after %.0fs" % (m, time.time() - t0))
            t1 = time.time()
            while time.time() - t1 < 60 and not os.path.exists(frame_ram_path(m)):
                time.sleep(1)
            time.sleep(6)
            return True
    print("[map] map %d: TIMEOUT (breakpoints never fired?)" % m)
    h.debug_command("b")
    time.sleep(1.5)
    return False


h = hconsole.Hatari(["--tos", TOS, "--machine", "st", "--memsize", "1",
                     "--sound", "off", "--fast-forward", "on",
                     "--disk-a", DISK, "--auto", "A:\\RICK2.PRG",
                     "--log-file", os.path.join(out, "hatari.log")])
try:
    time.sleep(BOOT_WAIT)
    print("[boot] crack screen -> SPACE")
    h.insert_event("keypress " + KEY_SPACE)
    time.sleep(wait)
    dump(h, "ram.bin")
    for m in maps:
        force_map(h, m)
finally:
    try:
        h.kill_hatari()
    except Exception:
        pass
