#!/usr/bin/env python3
"""
Rick Dangerous (Atari ST) — asset extractor.

Reads the Hatari RAM snapshot `atari_ram.bin` and writes every located graphic
asset to `re/assets/` as PNG, plus `assets-manifest.md` describing what was found.

Formats (all established in re/data-structures.md and re/algo-*.md):

  Palette   16 words at 0x4DEE2, ST 0x0RGB with 3 bits per channel (0..7).

  Font /    32 bytes per cell = 8x8 pixels, 4 bitplanes, 4 bytes per pixel row
  Tiles     (ONE BYTE PER PLANE per row). Font at 0x1B01E; tile banks at
            0x1D01E and 0x1F01E, 256 tiles each.

  Blocks    16 bytes at 0x22FEE + block*16 = a 4x4 grid of tile indices,
            row-major -> a 32x32 pixel block.

  Sprites   0x150 bytes per frame = 21 rows x 16 bytes. Each row is FOUR
            LONGWORDS, ONE PER BITPLANE, 32 pixels wide (plane-major).
            NOTE this is *not* ST screen format (which interleaves by word);
            render_sprites rotates each plane longword independently to do
            sub-word shifting, so the source is stored plane-major. Verified by
            rendering Rick's idle frame both ways.

  Screens   Full-screen images are standard ST low-res: 320x200, 32000 bytes,
            word-interleaved planes, 160 bytes per scanline.

Transparency: colour index 0. render_sprites derives its mask as
NOT(p0|p1|p2|p3), so index 0 is transparent and there is no stored mask plane.
"""

import os, struct
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
BIN  = os.path.join(HERE, "atari_ram.bin")
OUT  = os.path.join(HERE, "assets")

D = open(BIN, "rb").read()
os.makedirs(OUT, exist_ok=True)

u16 = lambda o: struct.unpack_from(">H", D, o)[0]
u32 = lambda o: struct.unpack_from(">I", D, o)[0]

# ---------------------------------------------------------------- palette
PALETTE_ADDR = 0x4DEE2

def st_palette(addr, n=16):
    """ST palette word 0x0RGB, 3 bits/channel -> 8-bit RGB triples."""
    pal = []
    for i in range(n):
        w = u16(addr + i * 2)
        r, g, b = (w >> 8) & 7, (w >> 4) & 7, w & 7
        pal.append((r * 255 // 7, g * 255 // 7, b * 255 // 7))
    return pal

PAL = st_palette(PALETTE_ADDR)

def putpal(img, pal, transparent0=False):
    flat = []
    for c in pal:
        flat += list(c)
    flat += [0, 0, 0] * (256 - len(pal))
    img.putpalette(flat)
    if transparent0:
        img.info["transparency"] = 0
    return img

# ------------------------------------------------------- pixel decoders
def cell_8x8(off):
    """32 bytes: 8 rows x 4 bytes, one byte per bitplane. -> 8x8 indices."""
    out = []
    for r in range(8):
        b = [D[off + r * 4 + p] for p in range(4)]
        out.append([sum(((b[p] >> (7 - x)) & 1) << p for p in range(4))
                    for x in range(8)])
    return out

def sprite_frame(off, rows=21):
    """0x150 bytes: rows x 16 bytes; each row = 4 longwords, one per plane."""
    out = []
    for r in range(rows):
        base = off + r * 16
        if base + 16 > len(D):
            break
        pl = [u32(base + p * 4) for p in range(4)]
        out.append([sum(((pl[p] >> (31 - x)) & 1) << p for p in range(4))
                    for x in range(32)])
    return out

def screen_320x200(off):
    """Standard ST low-res: word-interleaved planes, 160 bytes/scanline."""
    out = []
    for y in range(200):
        base = off + y * 160
        row = []
        for grp in range(20):                     # 20 groups x 16 px
            w = [u16(base + grp * 8 + p * 2) for p in range(4)]
            for x in range(16):
                bit = 15 - x
                row.append(sum(((w[p] >> bit) & 1) << p for p in range(4)))
        out.append(row)
    return out

def sheet(cells, cell_w, cell_h, cols, pal, transparent0=False, pad=1):
    """Tile a list of index-grids into one paletted PNG image."""
    rows = (len(cells) + cols - 1) // cols
    W = cols * (cell_w + pad) + pad
    H = rows * (cell_h + pad) + pad
    img = Image.new("P", (W, H), 0)
    putpal(img, pal, transparent0)
    px = img.load()
    for i, cell in enumerate(cells):
        cx = pad + (i % cols) * (cell_w + pad)
        cy = pad + (i // cols) * (cell_h + pad)
        for y, line in enumerate(cell):
            for x, v in enumerate(line):
                if cy + y < H and cx + x < W:
                    px[cx + x, cy + y] = v
    return img

def save(img, name):
    p = os.path.join(OUT, name)
    img.save(p)
    return os.path.basename(p), img.size

report = []

# ---------------------------------------------------------------- font
FONT = 0x1B01E
FONT_GLYPHS = 0x5F          # 0x00..0x5E inclusive; 0x5F+ is unrelated graphics data
glyphs = [cell_8x8(FONT + i * 32) for i in range(FONT_GLYPHS)]
report.append(("font.png", *save(sheet(glyphs, 8, 8, 16, PAL), "font.png"),
               "95 glyphs 0x00-0x5E: digits 0-9 at 0x00, HUD icons at 0x0A-0x0C, "
               "A-Z at ASCII, punctuation to 0x5E (space)"))

# --------------------------------------------------------------- tiles
for bank, base in enumerate((0x1D01E, 0x1F01E)):
    tiles = [cell_8x8(base + t * 32) for t in range(256)]
    n = f"tiles_bank{bank}.png"
    report.append((n, *save(sheet(tiles, 8, 8, 16, PAL), n),
                   f"256 tiles of 8x8 from 0x{base:05X} (32 bytes each)"))

# -------------------------------------------------------------- blocks
BLOCKS = 0x22FEE
for bank, base in enumerate((0x1D01E, 0x1F01E)):
    blocks = []
    for b in range(256):
        grid = [[0] * 32 for _ in range(32)]
        for sub in range(16):
            t = D[BLOCKS + b * 16 + sub]
            cell = cell_8x8(base + t * 32)
            oy, ox = (sub // 4) * 8, (sub % 4) * 8
            for y in range(8):
                for x in range(8):
                    grid[oy + y][ox + x] = cell[y][x]
        blocks.append(grid)
    n = f"blocks_bank{bank}.png"
    report.append((n, *save(sheet(blocks, 32, 32, 16, PAL), n),
                   f"256 blocks of 32x32 (4x4 tiles) from 0x{BLOCKS:05X}, bank {bank}"))

# ------------------------------------------------------------- sprites
# Frames sit on a single regular grid: stride 0x150, all aligned to 110 mod 0x150
# (verified across every table-referenced frame). Sweeping the grid is strictly
# better than walking animation tables, because treasures and enemy variants are
# reached by COMPUTED addresses (type*0x150 + base, frame + bank) that never appear
# as stored pointers -- a table walk or a pointer scan both miss them.
#
# Extent (corrected 2026-08-29): the grid runs to 0x3D62E, i.e. slots 0..211.
# It was previously cut at 0x3BA9E (slot 190), losing 21 real frames. The end is
# now derived, not assumed: sweep to the next known asset (the banners at 0x40FEE)
# and trim TRAILING blanks. Trailing, not first -- slot 127 is a genuine interior
# blank, so stopping at the first all-zero slot truncates the sheet to 127 frames.
# 212 slots corresponds to the port's SPRITES_NBR_SPRITES = 0xD5 = 213 (see
# xrick/re/xref.md Q14).
#
# NO DENSITY FILTER. The old `> 10% nonzero bytes` test silently discarded seven
# sparse-but-genuine frames (the bullet and similar small sprites are only ~17-30
# nonzero bytes out of 0x150) and would have discarded twelve more of the newly
# recovered ones. Every slot is rendered in grid order, blanks included, so
# **sheet cell N is sprite number N** -- which is what makes the sheet usable for
# cross-referencing against gfx_data addresses and against the port.
FRAME_LO, STRIDE, FRAME_ALIGN, FRAME_LIMIT = 0x2BFEE, 0x150, 110, 0x40FEE
grid = [a for a in range(FRAME_LO, FRAME_LIMIT - STRIDE + 1, STRIDE)]
while grid and not any(D[grid[-1]:grid[-1] + STRIDE]):
    grid.pop()                                    # trim trailing blank slots
FRAME_HI = grid[-1] + STRIDE
cells = [sprite_frame(f) for f in grid]
assert all(len(c) == 21 for c in cells)
blanks = [i for i, f in enumerate(grid) if not any(D[f:f + STRIDE])]
n = "sprites.png"
report.append((n, *save(sheet(cells, 32, 21, 20, PAL, transparent0=True), n),
               f"{len(cells)} sprite frames — the complete 32x21 frame grid "
               f"(0x{FRAME_LO:05X}-0x{FRAME_HI:05X}, stride 0x150); "
               f"cell index = sprite number"))

# --------------------------------------------------- unreferenced scenery tiles
# 0x1BBFE-0x1D01D, immediately after the font: 161 cells in the same 8x8 4-plane
# format, depicting sky, clouds, pyramids, sand and buildings. No code or table in
# the program references it (the only longwords pointing here are round numbers
# occurring inside sprite pixel data). Real artwork with no located consumer.
SCENERY_LO, SCENERY_HI = 0x1BBFE, 0x1D01E
scenery = [cell_8x8(SCENERY_LO + i * 32) for i in range((SCENERY_HI - SCENERY_LO) // 32)]
n = "scenery_tiles.png"
report.append((n, *save(sheet(scenery, 8, 8, 32, PAL), n),
               f"{len(scenery)} unreferenced 8x8 scenery tiles at 0x{SCENERY_LO:05X}"))

# ------------------------------------------------------------- screens
# Title: a genuine full-screen 320x200 (32000 bytes).
img = Image.new("P", (320, 200), 0)
putpal(img, PAL)
px = img.load()
for y, row in enumerate(screen_320x200(0x23FEE)):
    for x, v in enumerate(row):
        px[x, y] = v
report.append(("title.png", *save(img, "title.png"),
               "title screen, full 320x200 at 0x23FEE (32000 bytes)"))

# Banners: 0x40FEE is NOT a full screen. It is three 320x32 strips of 5120 bytes
# each -- exactly the size blit_image_5120 copies, which is what that function is for.
BANNERS = 0x40FEE
for i, label in enumerate(("congratulations", "hall_of_fame", "select_level")):
    a = BANNERS + i * 5120
    img = Image.new("P", (320, 32), 0)
    putpal(img, PAL)
    px = img.load()
    for y in range(32):
        base = a + y * 160
        for grp in range(20):
            w = [u16(base + grp * 8 + p * 2) for p in range(4)]
            for x in range(16):
                bit = 15 - x
                px[grp * 16 + x, y] = sum(((w[p] >> bit) & 1) << p for p in range(4))
    n = f"banner_{label}.png"
    report.append((n, *save(img, n),
                   f"320x32 banner at 0x{a:05X} (5120 bytes, drawn by blit_image_5120)"))

# ------------------------------------------------------------- palette
pimg = Image.new("P", (16 * 16, 16), 0)
putpal(pimg, PAL)
p = pimg.load()
for i in range(16):
    for x in range(16):
        for y in range(16):
            p[i * 16 + x, y] = i
report.append(("palette.png", *save(pimg, "palette.png"),
               f"16-colour palette from 0x{PALETTE_ADDR:05X}"))

# -------------------------------------------------------------- report
print(f"palette @0x{PALETTE_ADDR:05X}: " +
      " ".join("#%02X%02X%02X" % c for c in PAL))
print(f"frame grid: {len(grid)} slots 0x{FRAME_LO:05X}-0x{FRAME_HI:05X}, "
      f"all rendered in index order; blank slots: {blanks}")
print()
for name, fname, size, desc in report:
    print(f"  {fname:22s} {str(size):12s} {desc}")
print(f"\nwrote {len(report)} files to {OUT}")
