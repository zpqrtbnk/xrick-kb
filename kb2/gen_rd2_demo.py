#!/usr/bin/env python3
"""
port-rd2.md P1i: embed the 4 maps' attract-mode demo-input streams.

Format (hnk-system.md, kb2/extract_hnk.py's demo_pairs): raw bytes read directly by
read_player_input ($141cc) as (count, state) pairs; count 0 ends the stream. Embedded
RAW, unparsed -- same reasoning as the other gen_rd2_*.py scripts: the port's input
code (P3b) reads it exactly as the original does, no re-encoding.

Maps 1, 2, 4: kb2/assets/maps/map<N>_demo.bin (the genuine depacked HNK stream, 1024 B).

Map 3: RICK_05.HNK depacks to demonstrated crack corruption (512 B of "Rob Northen
Comp..." padding, no terminator within 512 B) -- hnk-system.md S6, PLAN.md T25/T36.
User decision 2026-09-22 (port-rd2.md S4): ship the T25 candidate instead -- the raw
sectors at disks/RICKDA2/RD2[7680:8704] (1024 B), which decode as a well-formed stream
(52 pairs, terminator at byte 104) unlike the corrupted RICK_05.HNK. This candidate is
UNVERIFIED against an original disk (no reference copy exists to compare) -- flagged
as such here and in the generated file; it is a reconstruction, not a proven-original
byte sequence, and PLAN.md T36 (how the crack corruption happened) is still open.

Run: py -3 kb2/gen_rd2_demo.py
Writes: include/rd2/dat_rd2_demo.h + src/rd2/dat_rd2_demo.c
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from gen_rd2_common import MAPDIR, c_bytes, gen_header, write_pair

RD2_DISK = os.path.join(ROOT, "disks", "RICKDA2", "RD2")
MAP3_CANDIDATE_RANGE = (7680, 8704)  # hnk-system.md S6, PLAN.md T25: RD2[7680:8704]


def main():
    streams = {}
    for m in (1, 2, 4):
        streams[m] = open(os.path.join(MAPDIR, "map%d_demo.bin" % m), "rb").read()
        assert len(streams[m]) == 1024, (m, len(streams[m]))
    with open(RD2_DISK, "rb") as f:
        f.seek(MAP3_CANDIDATE_RANGE[0])
        streams[3] = f.read(MAP3_CANDIDATE_RANGE[1] - MAP3_CANDIDATE_RANGE[0])
    assert len(streams[3]) == 1024, len(streams[3])

    src = ["Sources: kb2/assets/maps/map<N>_demo.bin for maps 1/2/4 (genuine depacked HNK streams).",
           "Map 3: disks/RICKDA2/RD2[%d:%d] -- the T25 candidate, NOT the genuine (corrupted) HNK." %
           MAP3_CANDIDATE_RANGE,
           "*** Map 3's stream is UNVERIFIED against an original disk (no reference copy exists). ***",
           "*** It is a reconstruction the user chose to ship anyway (port-rd2.md S4, 2026-09-22); ***",
           "*** PLAN.md T25/T36 track this. Do not present it as a proven-original byte sequence. ***"]
    hdr = gen_header("gen_rd2_demo.py", "\n".join(src))
    hbody = ["#define RD2_DEMO_BYTES 1024\n#define RD2_DEMO_MAP3_IS_RECONSTRUCTED 1\n"]
    sbody = []
    for m in (1, 2, 3, 4):
        hbody.append("extern const U8 rd2_demo_map%d[RD2_DEMO_BYTES];" % m)
        sbody.append("const U8 rd2_demo_map%d[RD2_DEMO_BYTES] = {\n  %s\n};\n" % (m, c_bytes(streams[m])))
    hbody.append("\nextern const U8 * const rd2_demo[4]; /* index 0..3 = map 1..4; map 3 (index 2) is reconstructed, see above */")
    sbody.append("const U8 * const rd2_demo[4] = {\n  rd2_demo_map1, rd2_demo_map2, rd2_demo_map3, rd2_demo_map4\n};\n")
    write_pair("dat_rd2_demo", hdr, "\n".join(hbody) + "\n", "\n".join(sbody))


if __name__ == "__main__":
    main()
