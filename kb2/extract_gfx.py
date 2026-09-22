#!/usr/bin/env python3
"""
Extract Rick Dangerous 2's tile and sprite graphics to PNG.  Run on the host (needs Pillow).

    python3 kb2/extract_gfx.py [--refs <dir with ram_map<N>_f120.bin>]

Sources (all checked 2026-09-19, see kb2/graphics.md):
  tiles          kb2/assets/maps/map<N>_level.bin   image offset 0x4900 (= $57d00)
  sprites A/C    kb2/prg2-ram.bin  $37274 (41 frames) and $3a844 (29 frames)   [shared bank, RAM only]
  font           kb2/prg2-ram.bin  $3ce54, 256 glyphs of 8x8, 32 bytes each        [RAM only]
  anim tiles     kb2/assets/maps/map<N>_level.bin   image offset 0x7100 (= $5a500), 32 tiles
  sprites B/D    kb2/assets/maps/map<N>_level.bin   image offset 0x7600 (= $5aa00), 128 frames
  palette        kb2/prg2-ram.bin  $18ee6, 16 words (same for all maps). No code writes any single colour specially —
                 checked 2026-09-22 by an exhaustive xref search on both the table word and the hardware register
                 $ff8242: only the two generic whole-palette fade routines ($1919e/$19134) ever touch it. The live
                 $ff8240 differing from the table only in colour 1's low bit (0008/0088/0080/0080) is the STE-only
                 4th colour bit, invisible on an ST (`kb2/assets/gfx/pal_map<N>.bin` keep those readings for the record)
  banners        kb2/prg2-ram.bin  $35a74, four 0x600-byte slices ("CONGRATULATIONS!", "HALL OF FAME", "SELECT LEVEL",
                 "LOADING...", one per `FUN_000194ce` argument 0-3); 256x24, 4-colour (only bitplanes 0-1 are written,
                 valid because the screen is always cleared first — checked 2026-09-22, see kb2/graphics.md §4b

Formats (from the game's own blitters, disassembled in Ghidra):
  tile    8x8, 40 bytes: per pixel row 5 bytes = plane0..plane3 (1 byte each, MSB = left pixel) + 1 mask byte
  sprite  32x21, 336 bytes: per pixel row 4 longwords = plane0..plane3 (32 pixels each, MSB = left pixel);
          NO stored mask: a pixel is transparent when all four planes are 0 (colour 0)
  colour  ST 3 bits per channel (word & 0x777); STE extra bits (0x008 etc.) are ignored, as on an ST

Outputs go to kb2/assets/gfx/.
"""
import json
import os
import struct
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
GFX = os.path.join(ASSETS, "gfx")
LEVELS = os.path.join(ASSETS, "levels")
MAPS = {1: "map1", 2: "map2", 3: "map3", 4: "map4"}   # map N -> kb2/assets/maps/map<N>_level.bin (the big HNK of the pair, fully unpacked)
MAPDIR = os.path.join(HERE, "assets", "maps")           # kb2/extract_hnk.py output

TILE_OFF = 0x4900        # image offset of the tile bank ($57d00 - $53400)
TILE_COUNT = 256
TILE_BYTES = 40
ANIM_OFF = 0x7100        # animated background tiles ($5a500 - $53400): 8 tile types x 4 frames, 40 bytes each
SPR_LEVEL_OFF = 0x7600   # image offset of the level sprite bank ($5aa00 - $53400)
SPR_LEVEL_COUNT = 128    # (0x11e00 - 0x7600) / 336
SPR_BYTES = 336
SHARED_A = (0x37274, 41)  # frames 0..40
SHARED_C = (0x3a844, 29)  # frames 128..156: the text glyph set starts at $3ce54 = $3a844 + 29*336
FONT = (0x3ce54, 256)     # 8x8 glyphs, 32 bytes each (4 plane bytes per pixel row, no mask)
BANNERS = (0x35a74, 0x600, {0: "congratulations", 1: "hall_of_fame", 2: "select_level", 3: "loading"})  # $194ce arg -> name


def palette_rgb(words):
    out = []
    for w in words:
        r, g, b = (w >> 8) & 7, (w >> 4) & 7, w & 7
        out.append((r * 255 // 7, g * 255 // 7, b * 255 // 7))
    return out


def load_palette(m=None):
    """The one game palette: 16 words at $18ee6 in the program (installed by FUN_00019116 $19116); the same for every map."""
    ram = open(os.path.join(HERE, "prg2-ram.bin"), "rb").read()
    return [struct.unpack(">H", ram[0x18ee6 + 2 * i: 0x18ee6 + 2 * i + 2])[0] for i in range(16)]


def tile_images(img, pal):
    """Return (colour sheet, mask sheet) as 128x128 images; cell (r, c) = tile r*16+c."""
    col = Image.new("RGB", (128, 128))
    msk = Image.new("L", (128, 128))
    cp, mp = col.load(), msk.load()
    for n in range(TILE_COUNT):
        base = TILE_OFF + n * TILE_BYTES
        ox, oy = (n % 16) * 8, (n // 16) * 8
        for r in range(8):
            row = img[base + 5 * r: base + 5 * r + 5]
            for bit in range(8):
                v = sum(((row[p] >> (7 - bit)) & 1) << p for p in range(4))
                cp[ox + bit, oy + r] = pal[v]
                mp[ox + bit, oy + r] = 255 if (row[4] >> (7 - bit)) & 1 else 0
    return col, msk


def anim_tiles(img, pal):
    """8 rows (tile ids $f8..$ff) x 4 frames of 8x8 (same 40-byte format as the tiles)."""
    sheet = Image.new("RGB", (32, 64))
    px = sheet.load()
    for n in range(32):
        base = ANIM_OFF + n * TILE_BYTES
        ox, oy = (n % 4) * 8, (n // 4) * 8
        for r in range(8):
            row = img[base + 5 * r: base + 5 * r + 5]
            for bit in range(8):
                px[ox + bit, oy + r] = pal[sum(((row[p] >> (7 - bit)) & 1) << p for p in range(4))]
    return sheet


def sprite_frame(data, off, pal):
    im = Image.new("RGBA", (32, 21))
    px = im.load()
    for r in range(21):
        planes = [struct.unpack(">I", data[off + 16 * r + 4 * p: off + 16 * r + 4 * p + 4])[0] for p in range(4)]
        for bit in range(32):
            v = sum(((planes[p] >> (31 - bit)) & 1) << p for p in range(4))
            px[bit, r] = (0, 0, 0, 0) if v == 0 else pal[v] + (255,)
    return im


def sprite_sheet(data, base, count, pal, cols=16):
    rows = (count + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * 32, rows * 21), (0, 0, 0, 0))
    for n in range(count):
        sheet.paste(sprite_frame(data, base + n * SPR_BYTES, pal), ((n % cols) * 32, (n // cols) * 21))
    return sheet


def banner(ram, arg, pal):
    """One of the 4 UI banners (`FUN_000194ce`, kb2/graphics.md §4b): 256x24, planes 0-1 only, decoded straight —
    the source is already laid out as 16 groups/row of (plane0 word, plane1 word), one group per 16 px."""
    src = ram[BANNERS[0] + arg * BANNERS[1]: BANNERS[0] + (arg + 1) * BANNERS[1]]
    img = Image.new("RGB", (256, 24))
    px = img.load()
    for y in range(24):
        for g in range(16):
            off = y * 64 + g * 4
            p0, p1 = struct.unpack(">HH", src[off:off + 4])
            for bit in range(16):
                idx = ((p0 >> (15 - bit)) & 1) | (((p1 >> (15 - bit)) & 1) << 1)
                px[g * 16 + bit, y] = pal[idx]
    return img


def main():
    os.makedirs(GFX, exist_ok=True)
    ram = open(os.path.join(HERE, "prg2-ram.bin"), "rb").read()
    pal1 = palette_rgb(load_palette(1))
    # shared banks use map 1's palette (palettes differ only in colour 1, see kb2/graphics.md)
    sprite_sheet(ram, SHARED_A[0], SHARED_A[1], pal1).save(os.path.join(GFX, "sprites_shared_A_0-40.png"))
    sprite_sheet(ram, SHARED_C[0], SHARED_C[1], pal1).save(os.path.join(GFX, "sprites_shared_C_128-156.png"))
    font = Image.new("RGB", (128, 128))
    fp = font.load()
    for n in range(FONT[1]):
        for r in range(8):
            pl = ram[FONT[0] + 32 * n + 4 * r: FONT[0] + 32 * n + 4 * r + 4]
            for bit in range(8):
                fp[(n % 16) * 8 + bit, (n // 16) * 8 + r] = pal1[sum(((pl[p] >> (7 - bit)) & 1) << p for p in range(4))]
    font.save(os.path.join(GFX, "font_glyphs.png"))
    for arg, name in BANNERS[2].items():
        banner(ram, arg, pal1).save(os.path.join(GFX, "banner_%s.png" % name))
    print("banners written")
    # cut-scene background images: glyph-id matrices (kb2/decode_scenes.py) drawn with the font, in the game palette
    # (no scene opcode changes the palette; `$18d00` copies 8x8 font glyphs)
    scenes_path = os.path.join(LEVELS, "scenes.json")
    if os.path.exists(scenes_path):
        sc = json.load(open(scenes_path))
        for m in MAPS:
            for im in sc["map%d" % m]["images"]:
                cols, rows = im["cols"], im["rows"]
                pic = Image.new("RGB", (cols * 8, rows * 8))
                pp = pic.load()
                for r in range(rows):
                    for c in range(cols):
                        n = im["glyphs"][r][c]
                        for y in range(8):
                            pl = ram[FONT[0] + 32 * n + 4 * y: FONT[0] + 32 * n + 4 * y + 4]
                            for bit in range(8):
                                pp[c * 8 + bit, r * 8 + y] = pal1[sum(((pl[q] >> (7 - bit)) & 1) << q for q in range(4))]
                pic.save(os.path.join(GFX, "scene_map%d_image%d.png" % (m, im["index"])))
        print("scene images written")
    for m, name in MAPS.items():
        img = open(os.path.join(MAPDIR, "map%d_level.bin" % m), "rb").read()
        pal = palette_rgb(load_palette(m))
        col, msk = tile_images(img, pal)
        col.save(os.path.join(GFX, "tiles_map%d.png" % m))
        msk.save(os.path.join(GFX, "tilemask_map%d.png" % m))
        anim_tiles(img, pal).save(os.path.join(GFX, "tiles_anim_map%d.png" % m))
        # level bank: frames 64..127 first, then 192..255 (the game routes ids by range, see graphics.md)
        sprite_sheet(img, SPR_LEVEL_OFF, SPR_LEVEL_COUNT, pal).save(
            os.path.join(GFX, "sprites_map%d_level_64-127_192-255.png" % m))
        print("map %d: tiles + level sprites written" % m)
    if "--refs" in sys.argv:
        d = sys.argv[sys.argv.index("--refs") + 1]
        for m in MAPS:
            r = open(os.path.join(d, "ram_map%d_f120.bin" % m), "rb").read()
            pal = palette_rgb(load_palette(m))
            im = Image.new("RGB", (320, 200))
            px = im.load()
            for y in range(200):
                for gx in range(20):
                    base = 0x70000 + y * 160 + gx * 8
                    ws = [(r[base + 2 * p] << 8) | r[base + 2 * p + 1] for p in range(4)]
                    for bit in range(16):
                        px[gx * 16 + bit, y] = pal[sum(((ws[p] >> (15 - bit)) & 1) << p for p in range(4))]
            im.save(os.path.join(GFX, "ref_screen_map%d.png" % m))
        print("reference screens written")


if __name__ == "__main__":
    main()
