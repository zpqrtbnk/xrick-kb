#!/usr/bin/env python3
"""
port-rd2.md P1a(tiles)/P1e/P1f/P1h: embed each map's level image whole.

Design decision (recorded in port-rd2.md): rather than re-slicing the level image into
separate per-subsystem C tables (tiles, block maps, trigger table, spawn table, monster
types, scripts, scenes...), embed the RAW level image once per map and give the engine
(P3/P4) the same offset constants the disassembly uses. All of these subsystems are, in
the original game, just offsets into ONE blob loaded at $53400 -- graphics.md S3/S3a/S3b,
level-tables.md, decode_scenes.py's docstring all address it that way. Re-slicing at
generation time would mean re-deriving record boundaries (spawn records are variable
length) and would duplicate storage; embedding the whole blob means P3/P4's C code is a
direct, checkable transliteration of the 68000 pointer arithmetic (same precedent as
xrick/xrick/src/rd1/dat_sndh_engine.c, which embeds its blob whole rather than splitting
it into named tables).

Source: kb2/assets/maps/map<N>_level.bin (kb2/extract_hnk.py's depacked output, itself
checked against 3 independent sources -- kb2/hnk-system.md). All of map<N>_level.bin is
included: 73,472 bytes/map, identical across all 4 maps (kb2/assets/maps/manifest.json).

Offsets (all cited from graphics.md / level-tables.md, not re-derived here):
  0x0000  monster type table (level-tables.md S4)
  0x1800  submap header table (graphics.md S3a, level-tables.md S1)
  0x2000  cut-scene data (decode_scenes.py)
  0x3000  block maps (graphics.md S3a)
  0x3900  block table (graphics.md S3a)
  0x4900  tiles, 256 x 40 bytes (graphics.md S3)
  0x7100  animated tiles, 32 x 40 bytes (graphics.md S3b)
  0x7600  level sprite bank, 128 x 336 bytes, ids 64-127/192-255 (graphics.md S4)
  0x11e00 tile attribute table, 256 bytes (level-tables.md/algo-actors.md S6)
Per-map submap counts (17/14/14/13) and monster-type counts (49/43/50/68) are BOTH
documented as *derived* quantities, not stored constants (level-tables.md S1 "count
per map = first trigger offset / 8"; S4 "number of types = highest type id used by its
spawn records"), so they are recorded here as comments only -- the port's own runtime
code must derive them exactly the way the original does, not read them from a constant.

Run: py -3 kb2/gen_rd2_levelimg.py
Writes: include/rd2/dat_rd2_levelimg.h + src/rd2/dat_rd2_levelimg.c
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_rd2_common import MAPDIR, c_bytes, gen_header, write_pair

MAPS = (1, 2, 3, 4)
SUBMAP_COUNTS = {1: 17, 2: 14, 3: 14, 4: 13}          # level-tables.md S1 -- derived, not stored; recorded for reference
MONSTER_TYPE_COUNTS = {1: 49, 2: 43, 3: 50, 4: 68}    # level-tables.md S4 -- derived, not stored; recorded for reference

OFFSETS = [
    ("MONSTERS", 0x0000, "monster type table, level-tables.md S4"),
    ("SUBMAP_HEADERS", 0x1800, "submap header table, 8 bytes/submap, level-tables.md S1"),
    ("SCENES", 0x2000, "cut-scene data, decode_scenes.py"),
    ("BLOCKMAP", 0x3000, "block maps, graphics.md S3a"),
    ("BLOCKTABLE", 0x3900, "block table, 16 bytes/block, graphics.md S3a"),
    ("TILES", 0x4900, "tiles, 256 x 40 bytes, graphics.md S3"),
    ("ANIM_TILES", 0x7100, "animated tiles, 32 x 40 bytes, graphics.md S3b"),
    ("SPRITES", 0x7600, "level sprite bank, 128 x 336 bytes, graphics.md S4"),
    ("TILE_ATTR", 0x11e00, "tile attribute table, 256 bytes, level-tables.md/algo-actors.md S6"),
]


def main():
    src = ["Source: kb2/assets/maps/map<N>_level.bin, embedded whole (73472 bytes/map).",
           "Offset constants below are cited from graphics.md/level-tables.md, not re-derived.",
           "Submap counts (per map, derived not stored): %s" % SUBMAP_COUNTS,
           "Monster-type counts (per map, derived not stored): %s" % MONSTER_TYPE_COUNTS]
    hdr = gen_header("gen_rd2_levelimg.py", "\n".join(src))
    hbody = ["#define RD2_LEVELIMG_SIZE 73472\n"]
    for name, off, note in OFFSETS:
        hbody.append("#define RD2_LVLIMG_OFF_%s 0x%x\t/* %s */" % (name, off, note))
    hbody.append("")
    sbody = []
    for m in MAPS:
        path = os.path.join(MAPDIR, "map%d_level.bin" % m)
        data = open(path, "rb").read()
        assert len(data) == 73472, (m, len(data))
        hbody.append("extern const U8 rd2_levelimg_map%d[RD2_LEVELIMG_SIZE];" % m)
        sbody.append("const U8 rd2_levelimg_map%d[RD2_LEVELIMG_SIZE] = {\n  %s\n};\n" % (m, c_bytes(data)))
    # stage-1 files: what $123b0 leaves at $65300 after loading (graphics.md S3: "right after load_map the bytes at
    # $65300 are still the packed stage-1 file (measured equal to map2_level_stage1.bin)"); the RAM-model port
    # reproduces that footprint
    sizes = []
    for m in MAPS:
        st = open(os.path.join(MAPDIR, "map%d_level_stage1.bin" % m), "rb").read()
        sizes.append(len(st))
        hbody.append("extern const U8 rd2_stage1_map%d[%d];" % (m, len(st)))
        sbody.append("const U8 rd2_stage1_map%d[%d] = {\n  %s\n};\n" % (m, len(st), c_bytes(st)))
    hbody.append("extern const U8 * const rd2_stage1[4];\nextern const U32 rd2_stage1_size[4];")
    sbody.append("const U8 * const rd2_stage1[4] = {\n  rd2_stage1_map1, rd2_stage1_map2, rd2_stage1_map3, rd2_stage1_map4\n};\n")
    sbody.append("const U32 rd2_stage1_size[4] = { %s };\n" % ", ".join("%du" % z for z in sizes))
    hbody.append("\nextern const U8 * const rd2_levelimg[4]; /* index 0..3 = map 1..4 */")
    sbody.append("const U8 * const rd2_levelimg[4] = {\n  rd2_levelimg_map1, rd2_levelimg_map2, rd2_levelimg_map3, rd2_levelimg_map4\n};\n")
    write_pair("dat_rd2_levelimg", hdr, "\n".join(hbody) + "\n", "\n".join(sbody))


if __name__ == "__main__":
    main()
