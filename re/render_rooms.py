#!/usr/bin/env python3
"""
Rick Dangerous (Atari ST) — room map renderer.

Renders all 47 rooms to PNG from the resident level data, exercising the full
tilemap decode chain end-to-end:

    RoomHeader.pTileMap  ->  block-index stream (1 byte per block, 8 per row)
      -> block_defs[block] @0x22FEE  (16 bytes = 4x4 tile indices, row-major)
        -> tile bitmap @ tile_gfx_base + tile*32  (8x8, 4 planes, byte-per-plane)

Each room is 8 blocks (= 32 tiles = 256 px) wide. Height has two parts:

  own_rows  the room's own block-index stream, which runs to the next room's
            pTileMap in address order (the streams are packed contiguously,
            ending at the block table).
  margin    a further 6 block-rows (192 px = one screen). The player can see
            below the room's own stream: world_row_base reaches the room's last
            transition row -- empirically (own_rows-1)*4 -- and the screen then
            shows one more screenful, which physically lives in the FOLLOWING
            stream. Without this the bottom of every room is cut mid-structure.
            Clamped so we never read past the block-definition table (room 46).

With --overlay, entity spawn positions from placement_table are marked, which also
cross-checks the placement format against the geometry.

Usage:  python re/render_rooms.py [--overlay]
"""

import os, sys, struct
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
D    = open(os.path.join(HERE, "atari_ram.bin"), "rb").read()
OUT  = os.path.join(HERE, "assets", "rooms")
os.makedirs(OUT, exist_ok=True)

u16 = lambda o: struct.unpack_from(">H", D, o)[0]
u32 = lambda o: struct.unpack_from(">I", D, o)[0]

ROOM_HEADERS  = 0x47620
N_ROOMS       = 47
BLOCK_DEFS    = 0x22FEE
TILE_BANKS    = (0x1D01E, 0x1F01E)
ATTR_LUTS     = (0x49F1E, 0x4A01E)
LEVEL_START   = 0x4B522
PLACEMENTS    = 0x481E4
PALETTE_ADDR  = 0x4DEE2
BLOCKS_PER_ROW = 8

PAL = []
for i in range(16):
    w = u16(PALETTE_ADDR + i * 2)
    PAL.append((((w >> 8) & 7) * 255 // 7, ((w >> 4) & 7) * 255 // 7, (w & 7) * 255 // 7))

# ------------------------------------------------------------------ geometry
rooms = [{"idx": i,
          "variant": u16(ROOM_HEADERS + i * 14),
          "tilemap": u32(ROOM_HEADERS + i * 14 + 2),
          "placements": u32(ROOM_HEADERS + i * 14 + 10)} for i in range(N_ROOMS)]

# A room's OWN block-index stream runs to the next stream start in address order.
bounds = sorted({r["tilemap"] for r in rooms} | {BLOCK_DEFS})
for r in rooms:
    nxt = next(b for b in bounds if b > r["tilemap"])
    r["bytes"] = nxt - r["tilemap"]
    r["own_rows"] = r["bytes"] // BLOCKS_PER_ROW

# ...but the player can see BELOW that. world_row_base may reach the room's last
# transition row (empirically (own_rows-1)*4 for most rooms), and the screen then
# shows a further 192 px = 6 block-rows. Those rows physically live in the following
# stream, yet they are part of what the room looks like in play, so render them too.
# Clamp so we never read past the block-definition table.
VISIBLE_BLOCK_ROWS = 192 // 32          # one screen below world_row_base
for r in rooms:
    avail = (BLOCK_DEFS - r["tilemap"]) // BLOCKS_PER_ROW
    r["margin"] = max(0, min(VISIBLE_BLOCK_ROWS, avail - r["own_rows"]))
    r["block_rows"] = r["own_rows"] + r["margin"]

# Level ownership, from level_start_info entry rooms
entries = [(u32(LEVEL_START + i * 20 + 0x0A) - ROOM_HEADERS) // 14 for i in range(4)]
LEVEL_NAMES = ["south_america", "egypt", "castle", "missile_base"]
edges = entries + [N_ROOMS]
for r in rooms:
    r["level"] = max(L for L in range(4) if entries[L] <= r["idx"])

# ------------------------------------------------------------------- decode
def tile_pixels(bank, tile):
    """32 bytes at base+tile*32: 8 rows x 4 bytes, one byte per bitplane."""
    off = TILE_BANKS[bank] + tile * 32
    return [[sum(((D[off + r * 4 + p] >> (7 - x)) & 1) << p for p in range(4))
             for x in range(8)] for r in range(8)]

_tile_cache = {}
def tile_cached(bank, tile):
    k = (bank, tile)
    if k not in _tile_cache:
        _tile_cache[k] = tile_pixels(bank, tile)
    return _tile_cache[k]

def render_room(r):
    bank = r["variant"]
    W, H = BLOCKS_PER_ROW * 32, r["block_rows"] * 32
    img = Image.new("P", (W, H), 0)
    flat = []
    for c in PAL:
        flat += list(c)
    img.putpalette(flat + [0, 0, 0] * (256 - len(PAL)))
    px = img.load()
    for br in range(r["block_rows"]):
        for bc in range(BLOCKS_PER_ROW):
            block = D[r["tilemap"] + br * BLOCKS_PER_ROW + bc]
            bdef  = BLOCK_DEFS + block * 16
            for sub in range(16):                      # 4x4 tiles, row-major
                cell = tile_cached(bank, D[bdef + sub])
                ox = bc * 32 + (sub % 4) * 8
                oy = br * 32 + (sub // 4) * 8
                for y in range(8):
                    for x in range(8):
                        px[ox + x, oy + y] = cell[y][x]
    return img

def overlay_entities(img, r):
    """Mark spawn positions of this room's placement records."""
    rgb = img.convert("RGB")
    dr  = ImageDraw.Draw(rgb)
    o, n = r["placements"], 0
    while True:
        band = u16(o)
        if band == 0x00FF:
            break
        typ  = D[o + 2] & 0x7F
        flags = D[o + 3]
        x    = D[o + 4] & 0xF8
        # Y within the room: band is a world row; block rows are 4 rows of 8 px.
        y    = ((band & 0xFFF8) + (D[o + 4] & 7)) * 8
        if 0 <= y < img.height:
            col = (255, 0, 255) if flags & 0x02 else (0, 255, 255)
            dr.rectangle([x, y, x + 7, y + 7], outline=col)
            dr.text((x + 9, y), str(typ), fill=col)
            n += 1
        o += 6
        if o > r["placements"] + 6 * 400:
            break
    return rgb, n

# -------------------------------------------------------------------- main
overlay = "--overlay" in sys.argv
print(f"{'room':>4} {'lvl':>3} {'bank':>4} {'own':>4} {'+mgn':>5} {'size':>11}  tilemap")
total_ents = 0
for r in rooms:
    img = render_room(r)
    name = f"room{r['idx']:02d}_L{r['level']}_{LEVEL_NAMES[r['level']]}"
    if overlay:
        rgb, n = overlay_entities(img, r)
        total_ents += n
        rgb.save(os.path.join(OUT, name + "_ents.png"))
    img.save(os.path.join(OUT, name + ".png"))
    print(f"{r['idx']:>4} {r['level']:>3} {r['variant']:>4} {r['own_rows']:>4} {r['margin']:>5} "
          f"{img.size[0]:>4}x{img.size[1]:<6} 0x{r['tilemap']:05X}")

print(f"\n{N_ROOMS} rooms written to {OUT}")
if overlay:
    print(f"{total_ents} entity placements overlaid")
tallest = max(rooms, key=lambda r: r["block_rows"])
print(f"tallest: room {tallest['idx']} at {tallest['block_rows']} block-rows "
      f"({tallest['block_rows']*32} px)")
short = [r["idx"] for r in rooms if r["margin"] < VISIBLE_BLOCK_ROWS]
if short:
    print(f"rooms with a reduced margin (data ends at block_defs): {short}")
