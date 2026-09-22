#!/usr/bin/env python3
"""
Extract Rick Dangerous 2's level layouts (submaps) to PNG plus a JSON index.  Needs Pillow.

    python3 kb2/extract_levels.py

Layout model (all from the game's own code, disassembled in Ghidra; verified against live RAM, see
kb2/graphics.md "Level tile map"):

  level image (kb2/assets/maps/map<N>_level.bin, loaded at $53400, so image offset = address - $53400)
    0x1800  ($54c00)  submap header table, 8 bytes per submap = 4 big-endian words   (FUN_00014458 @ $14458)
                        w0  block-map offset: submap block map starts at $56400 + w0
                        w1  maximum scroll / 8: [$16468] = w1 << 3 pixels   (clamp in $16718)
                        w2  trigger table  at $54c00 + w2   -> [$1435c]
                        w3  spawn table    at $54c00 + w3   -> [$144c4]
    0x3000  ($56400)  block maps: rows of 8 block ids = 32 tiles = 256 px wide, one row = 32 px tall
    0x3900  ($56d00)  block table: 16 bytes per block = 4x4 tile ids, row-major   (func_0x00016474 / $165fc)
    0x4900  ($57d00)  tiles, 8x8, 40 bytes (see extract_gfx.py)
  A submap is 256 px wide and (w1*8 + 192) px tall: 192 px is the visible playfield height.
  The game only scrolls vertically.

Outputs: kb2/assets/gfx/levelmap_map<N>_sub<I>.png  (one per distinct (base, height); duplicates are listed
in kb2/assets/gfx/levelmaps.json)
"""
import json
import os
import struct

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
GFX = os.path.join(HERE, "assets", "gfx")
LEVELS = os.path.join(HERE, "assets", "levels")
MAPS = {1: "map1", 2: "map2", 3: "map3", 4: "map4"}   # map N -> kb2/assets/maps/map<N>_level.bin (the big HNK of the pair, fully unpacked)
MAPDIR = os.path.join(HERE, "assets", "maps")           # kb2/extract_hnk.py output
HDR, MAPBASE, BLOCKS, TILES = 0x1800, 0x3000, 0x3900, 0x4900


def palette(m=None):
    """The game palette: 16 words at $18ee6 of kb2/prg2-ram.bin (identical for all maps)."""
    b = open(os.path.join(HERE, "prg2-ram.bin"), "rb").read()[0x18ee6:0x18ee6 + 32]
    out = []
    for i in range(16):
        w = struct.unpack(">H", b[2 * i:2 * i + 2])[0]
        out.append((((w >> 8) & 7) * 255 // 7, ((w >> 4) & 7) * 255 // 7, (w & 7) * 255 // 7))
    return out


def tiles(img, pal):
    out = []
    for n in range(256):
        t = Image.new("RGB", (8, 8))
        px = t.load()
        for r in range(8):
            row = img[TILES + 40 * n + 5 * r: TILES + 40 * n + 5 * r + 4]
            for bit in range(8):
                px[bit, r] = pal[sum(((row[p] >> (7 - bit)) & 1) << p for p in range(4))]
        out.append(t)
    return out


def main():
    index = {}
    for m, name in MAPS.items():
        img = open(os.path.join(MAPDIR, "map%d_level.bin" % m), "rb").read()
        T = tiles(img, palette(m))
        count = struct.unpack(">H", img[HDR + 4:HDR + 6])[0] // 8      # first trigger table starts right after the headers
        entries, seen = [], {}
        for i in range(count):
            w0, w1, w2, w3 = struct.unpack(">4H", img[HDR + 8 * i: HDR + 8 * i + 8])
            rows = w1 // 4 + 6
            e = {"index": i, "block_map_offset": w0, "max_scroll": w1 * 8, "height_px": w1 * 8 + 192,
                 "block_rows": rows, "trigger_table_image_offset": HDR + w2, "spawn_table_image_offset": HDR + w3}
            key = (w0, rows)
            if key in seen:
                e["same_layout_as"] = seen[key]
            else:
                seen[key] = i
                out = Image.new("RGB", (256, rows * 32))
                for ry in range(rows):
                    for bx in range(8):
                        blk = img[BLOCKS + 16 * img[MAPBASE + w0 + 8 * ry + bx]:][:16]
                        for k in range(16):
                            out.paste(T[blk[k]], (bx * 32 + (k % 4) * 8, ry * 32 + (k // 4) * 8))
                out.save(os.path.join(GFX, "levelmap_map%d_sub%d.png" % (m, i)))
            entries.append(e)
        index["map%d" % m] = {"level_image": "map%d_level.bin" % m, "submap_headers": entries}
        print("map %d: %d headers, %d distinct layouts" % (m, count, len(seen)))
    with open(os.path.join(GFX, "levelmaps.json"), "w") as f:
        json.dump(index, f, indent=1)


if __name__ == "__main__":
    main()
