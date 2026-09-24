#!/usr/bin/env python3
"""
port-rd2.md §7: embed the PRISTINE Rick Dangerous 2 program image for the RAM-model port.

Source: kb2/assets/RICK2.PRG (md5-identical to disks/chaos43/RICK2.PRG). Its data section is an LSD! archive;
hnk.depack() of it gives the game program (194,332 bytes, == FILE.DRS of disks/rd2.st, verify_hnk.py step 7).
The program runs so that RAM address = offset + $f8b8. That base was checked on game_main ($10992), the sound region,
the graphics banks, the hall-of-fame table and the boot code ($10000 = 40c0 0800 000d).

This is the program as loaded, NOT the prg2-ram.bin snapshot of the running game (see kb2/sound-ref.md §9 for the
differences). The port copies it into its emulated RAM at RD2_PROG_BASE; non-sound code and data are then read at their
original addresses. (The sound engine keeps its own, separately generated blob for now: port-rd2.md §7.)

Run: py -3 kb2/gen_rd2_program.py
Writes: include/rd2/dat_rd2_program.h + src/rd2/dat_rd2_program.c
"""
import hashlib
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hnk
from gen_rd2_common import c_bytes, gen_header, write_pair

BASE = 0xf8b8


def main():
    prg = open(os.path.join(HERE, "assets", "RICK2.PRG"), "rb").read()
    magic, tsize, dsize = struct.unpack(">HII", prg[:10])
    assert magic == 0x601A
    data = prg[28 + tsize:28 + tsize + dsize]
    assert data[:4] == b"LSD!"
    game = hnk.depack(data)
    assert len(game) == 194332, len(game)
    # anchors re-checked every run (never trusted from a previous run)
    assert game[0x10000 - BASE:0x10000 - BASE + 4] == bytes.fromhex("40c00800"), "boot entry"
    assert game[0x10992 - BASE:0x10992 - BASE + 6] == bytes.fromhex("41f900019044"), "game_main"
    assert game[0x17d0e - BASE + 4:0x17d0e - BASE + 8] == bytes.fromhex("08000000"), "hall-of-fame entry 0 score"
    src = ["Source: kb2/assets/RICK2.PRG data section, hnk.depack()ed (LSD! layer): %d bytes, md5 %s." %
           (len(game), hashlib.md5(game).hexdigest()),
           "Load address: RAM = offset + $%x (so this blob spans $%x..$%x)." % (BASE, BASE, BASE + len(game)),
           "Pristine program, NOT the prg2-ram.bin snapshot (kb2/sound-ref.md §9)."]
    hdr = gen_header("gen_rd2_program.py", "\n".join(src))
    hbody = ("#define RD2_PROG_BASE 0x%xu\n#define RD2_PROG_SIZE %d\n\nextern const U8 rd2_program[RD2_PROG_SIZE];\n"
             % (BASE, len(game)))
    sbody = "const U8 rd2_program[RD2_PROG_SIZE] = {\n  %s\n};\n" % c_bytes(game)
    write_pair("dat_rd2_program", hdr, hbody, sbody)


if __name__ == "__main__":
    main()
