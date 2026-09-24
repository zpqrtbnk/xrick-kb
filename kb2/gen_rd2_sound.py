#!/usr/bin/env python3
"""
port-rd2.md P1j: embed RD2's sound engine (code + tables + PSG stream data) verbatim.

Source: kb2/prg2-ram.bin[0x19e96:0x31eb0], the exact "sound region" bounds sound-ref.md
S1 states and S5's stream-extent scan confirms (the highest stream, id 47, ends exactly
at $31eb0 -- "the region needs no safety margin"). Embedded RAW and UNMODIFIED --
mirrors xrick/xrick/src/rd1/dat_sndh_engine.c exactly, including its key trick: RD1's
syssnd.c uploads its blob at the SAME address it was captured from (SNDH_ENGINE_BASE
== the live address), so every internal absolute reference in the blob is already
correct and NO relocation fixup pass is needed (unlike a generic SNDH file, which must
self-relocate because a player picks its own load address). RD2's driver (port-rd2.md
P5) must do the same: upload this blob at RD2_SNDH_BASE unchanged.

Per sound-ref.md S6, the *only* required deviation from the verbatim bytes is patching
the two `tst.w ($3efb6).l` operand fields (S6.4) -- $3efb6 is a demo-mode flag OUTSIDE
this blob's range, so it can't be read from the uploaded copy. The blob embedded here
is left pristine (unpatched), matching RD1's dat_sndh_engine.c precedent (blob stays a
verbatim capture); the patch itself is P5's job (rewrite these operands, at upload
time, to point at a zero cell the driver owns) -- this script only records the two
site addresses and the value found there, verified directly against prg2-ram.bin in
this session (not assumed from the doc's prose):
    $1a70c: 4 bytes, currently 0x0003efb6 (tst.w opcode 4a79 is 2 bytes earlier, $1a70a)
    $1a7fc: 4 bytes, currently 0x0003efb6 (tst.w opcode 4a79 is 2 bytes earlier, $1a7fa)

Entry points / state cells (sound-ref.md SS1-4, addresses as captured -- since the
blob uploads at its native address, these ARE the addresses to call/poke at runtime):
    dispatch       $1a6aa  FUN_0001a6aa(D0=id 0-91, D1=param)
    tick           $1a866  FUN_0001a866 -- call once per 50 Hz VBL (TC50 in SNDH terms)
    timerA install $1a978  FUN_0001a978 -- call once at init (installs vector $134,
                                            enables IERA/IMRA bit 5; no callers in the
                                            game itself -- boot code did this, so the
                                            driver must supply it, sound-ref.md S6.5)
    master state   $1a974  byte; must be cleared to 0 before each dispatch call
                            (sound-ref.md S6.3 -- it reads 1 in the captured image)
    dispatch table $1c376  92 entries x 8 bytes (type,param,ptr), ids 0-91

Run: py -3 kb2/gen_rd2_sound.py
Writes: include/rd2/dat_rd2_sndh_engine.h + src/rd2/dat_rd2_sndh_engine.c
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gen_rd2_common import c_bytes, gen_header, write_pair

BASE, END = 0x19e96, 0x31eb0
DEMOFLAG_SITES = (0x1a70c, 0x1a7fc)
DEMOFLAG_TARGET = 0x0003efb6


def main():
    ram = open(os.path.join(HERE, "prg2-ram.bin"), "rb").read()
    blob = ram[BASE:END]
    # verify the two patch-site operands mechanically, not from the doc's prose alone
    for site in DEMOFLAG_SITES:
        opcode = ram[site - 2:site]
        operand = int.from_bytes(ram[site:site + 4], "big")
        assert opcode == b"\x4a\x79", "expected tst.w (xxx).l opcode 4a79 at 0x%x-2, got %s" % (site, opcode.hex())
        assert operand == DEMOFLAG_TARGET, "expected 0x%x at 0x%x, got 0x%x" % (DEMOFLAG_TARGET, site, operand)

    src = ["Source: kb2/prg2-ram.bin[0x%x:0x%x] (%d bytes), sound-ref.md S1/S5." % (BASE, END, len(blob)),
           "Verbatim, unpatched -- see this script's docstring for the one required",
           "runtime patch (P5's job, not baked in here) and the entry-point addresses."]
    hdr = gen_header("gen_rd2_sound.py", "\n".join(src))
    hbody = [
        "#define RD2_SNDH_BASE 0x%xu" % BASE,
        "#define RD2_SNDH_SIZE %d" % len(blob),
        "#define RD2_SNDH_FN_DISPATCH 0x%xu\t/* D0=id 0-91, D1=param */" % 0x1a6aa,
        "#define RD2_SNDH_FN_TICK 0x%xu\t/* call once per 50 Hz VBL */" % 0x1a866,
        "#define RD2_SNDH_FN_TIMERA_INSTALL 0x%xu\t/* call once at init */" % 0x1a978,
        "#define RD2_SNDH_STATE_MASTER 0x%xu\t/* byte; clear to 0 before each dispatch */" % 0x1a974,
        "#define RD2_SNDH_DISPATCH_TABLE 0x%xu\t/* 92 x 8 bytes, ids 0-91 */" % 0x1c376,
        "#define RD2_SNDH_DISPATCH_ENTRIES 92",
        "#define RD2_SNDH_DEMOFLAG_SITE_1 0x%xu\t/* 4-byte operand, currently points at 0x3efb6 (outside blob) */" % DEMOFLAG_SITES[0],
        "#define RD2_SNDH_DEMOFLAG_SITE_2 0x%xu" % DEMOFLAG_SITES[1],
        "#define RD2_SNDH_DEMOFLAG_ORIGINAL_TARGET 0x%xu" % DEMOFLAG_TARGET,
        "",
        "extern const U8 rd2_sndh_engine_blob[RD2_SNDH_SIZE];",
    ]
    sbody = "const U8 rd2_sndh_engine_blob[RD2_SNDH_SIZE] = {\n  %s\n};\n" % c_bytes(blob)
    write_pair("dat_rd2_sndh_engine", hdr, "\n".join(hbody) + "\n", sbody)


if __name__ == "__main__":
    main()
