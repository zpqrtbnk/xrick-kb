#!/usr/bin/env python3
"""
One overview PNG per map of Rick Dangerous 1 and 2: every submap rendered from the game
data, laid out by its exits, with a coloured border and label per submap and an arrow per
exit (in the source submap's colour) from the exit row to the entry row of the target.

    python3 kb/render_map_overviews.py

No third-party module (PNG written with zlib). Outputs:
    kb/assets/map_overviews/rd1_map<N>.png    N = 1..4
    kb2/assets/map_overviews/rd2_map<N>.png   N = 1..4

Sources
  RD1  kb/atari_ram.bin, decoded as kb/render_rooms.py does (room headers, block stream
       to the next room's start plus one screen of margin, block defs, tile banks,
       palette); exits from the port's map_connect (xrick/xrick/src/rd1/dat_maps.c): one
       list per submap, ended by dir 0xff; dir 0 = right, 1 = left (kb/demo-solver.md §14);
       target 0xff = the next map; rowout / rowin are submap tile rows.
  RD2  kb2/assets/maps/map<N>_level.bin and kb2/prg2-ram.bin (palette $18ee6), decoded as
       kb2/extract_levels.py does, but showing tile rows 8 .. w1+31: the screen shows window
       rows 8..31 ($65400 is the renderer's visible copy, kb2/graphics.md §3; Rick stands
       at y 227 = feet row 30 in map 1 submap 0). Exits = trigger records (level-tables.md
       §2): b0 & 3 side (1 left, 2 right), b1 feet row, b2 target, b3 entry feet row;
       (b0 & $90) == $90 completes the map. Submaps with no exit are header stubs: left out.

Layout: the map's start submap at the origin; a target goes one column right (right exit)
or left (left exit) of its source, shifted vertically so the entry row meets the exit row,
then pushed further out that way while it overlaps one already placed. Lines run from the
exit point (the source's edge, exit row) to the entry point (the target's opposite edge,
entry row); a two-way pair draws as one line with a head at each end. Dashed: the entry
row lies outside the rows drawn for the target, so that end is clamped to its edge.
"""

import os
import re
import struct
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
GAP = 112          # px between columns
LABEL = 34         # px above a submap for its label
BORDER = 4
BG = (40, 40, 48)

COLORS = [(255, 64, 64), (64, 200, 255), (255, 200, 0), (120, 255, 80), (255, 100, 255),
          (255, 150, 40), (80, 120, 255), (0, 230, 180), (230, 230, 230), (255, 120, 160),
          (170, 120, 255), (200, 255, 0), (0, 160, 255), (255, 230, 120), (160, 255, 200),
          (255, 60, 160), (140, 200, 60), (100, 220, 255)]

# ---------------------------------------------------------------- 5x7 font
FONT = {
    'A': "01110 10001 10001 11111 10001 10001 10001", 'B': "11110 10001 10001 11110 10001 10001 11110",
    'C': "01111 10000 10000 10000 10000 10000 01111", 'D': "11110 10001 10001 10001 10001 10001 11110",
    'E': "11111 10000 10000 11110 10000 10000 11111", 'G': "01111 10000 10000 10011 10001 10001 01111",
    'I': "11111 00100 00100 00100 00100 00100 11111", 'K': "10001 10010 10100 11000 10100 10010 10001",
    'L': "10000 10000 10000 10000 10000 10000 11111", 'M': "10001 11011 10101 10101 10001 10001 10001",
    'N': "10001 11001 10101 10011 10001 10001 10001", 'O': "01110 10001 10001 10001 10001 10001 01110",
    'P': "11110 10001 10001 11110 10000 10000 10000", 'R': "11110 10001 10001 11110 10100 10010 10001",
    'S': "01111 10000 10000 01110 00001 00001 11110", 'T': "11111 00100 00100 00100 00100 00100 00100",
    'U': "10001 10001 10001 10001 10001 10001 01110", 'X': "10001 10001 01010 00100 01010 10001 10001",
    'Y': "10001 10001 01010 00100 00100 00100 00100",
    '0': "01110 10011 10101 10101 10101 11001 01110", '1': "00100 01100 00100 00100 00100 00100 01110",
    '2': "01110 10001 00001 00010 00100 01000 11111", '3': "11110 00001 00001 01110 00001 00001 11110",
    '4': "00010 00110 01010 10010 11111 00010 00010", '5': "11111 10000 11110 00001 00001 10001 01110",
    '6': "00110 01000 10000 11110 10001 10001 01110", '7': "11111 00001 00010 00100 01000 01000 01000",
    '8': "01110 10001 10001 01110 10001 10001 01110", '9': "01110 10001 10001 01111 00001 00010 01100",
    ' ': "00000 00000 00000 00000 00000 00000 00000", '-': "00000 00000 00000 11111 00000 00000 00000",
    '.': "00000 00000 00000 00000 00000 01100 01100", '$': "00100 01111 10100 01110 00101 11110 00100",
    'F': "11111 10000 10000 11110 10000 10000 10000", 'H': "10001 10001 10001 11111 10001 10001 10001",
    'W': "10001 10001 10001 10101 10101 10101 01010", 'V': "10001 10001 10001 10001 10001 01010 00100",
    'Z': "11111 00001 00010 00100 01000 10000 11111", 'J': "00111 00010 00010 00010 00010 10010 01100",
    'Q': "01110 10001 10001 10001 10101 10010 01101",
}


class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.px = bytearray(bytes(bg) * (w * h))

    def put(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            o = 3 * (y * self.w + x)
            self.px[o:o + 3] = bytes(c)

    def rect(self, x0, y0, x1, y1, c):            # filled, inclusive
        x0, x1 = max(0, x0), min(self.w - 1, x1)
        row = bytes(c) * (x1 - x0 + 1)
        for y in range(max(0, y0), min(self.h - 1, y1) + 1):
            o = 3 * (y * self.w + x0)
            self.px[o:o + len(row)] = row

    def frame(self, x0, y0, x1, y1, c, t):
        self.rect(x0, y0, x1, y0 + t - 1, c)
        self.rect(x0, y1 - t + 1, x1, y1, c)
        self.rect(x0, y0, x0 + t - 1, y1, c)
        self.rect(x1 - t + 1, y0, x1, y1, c)

    def blit(self, x, y, w, rows):                # rows: list of RGB bytes, w px each
        for j, r in enumerate(rows):
            yy = y + j
            if 0 <= yy < self.h:
                o = 3 * (yy * self.w + x)
                self.px[o:o + 3 * w] = r

    def line(self, x0, y0, x1, y1, c, t=3):
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        e = dx + dy
        while True:
            self.rect(x0 - t // 2, y0 - t // 2, x0 + t // 2, y0 + t // 2, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * e
            if e2 >= dy:
                e += dy; x0 += sx
            if e2 <= dx:
                e += dx; y0 += sy

    def dash(self, x0, y0, x1, y1, c, t=3, on=14, off=10):
        import math
        n = max(1, int(math.hypot(x1 - x0, y1 - y0)))
        for k in range(0, n, on + off):
            a, b = k / n, min(n, k + on) / n
            self.line(int(x0 + (x1 - x0) * a), int(y0 + (y1 - y0) * a),
                      int(x0 + (x1 - x0) * b), int(y0 + (y1 - y0) * b), c, t)

    def head(self, x0, y0, x1, y1, c, size=18):   # arrowhead at (x1, y1) for a line from (x0, y0)
        import math
        a = math.atan2(y1 - y0, x1 - x0)
        pts = [(x1, y1),
               (x1 - size * math.cos(a - 0.45), y1 - size * math.sin(a - 0.45)),
               (x1 - size * math.cos(a + 0.45), y1 - size * math.sin(a + 0.45))]
        ys = [p[1] for p in pts]
        for y in range(int(min(ys)), int(max(ys)) + 1):
            xs = []
            for i in range(3):
                (ax, ay), (bx, by) = pts[i], pts[(i + 1) % 3]
                if (ay <= y < by) or (by <= y < ay):
                    xs.append(ax + (y - ay) * (bx - ax) / (by - ay))
            if len(xs) >= 2:
                self.rect(int(min(xs)), y, int(max(xs)), y, c)

    def text(self, x, y, s, c, scale=3):
        for ch in s.upper():
            g = FONT.get(ch, FONT[' ']).split()
            for j, row in enumerate(g):
                for i, b in enumerate(row):
                    if b == '1':
                        self.rect(x + i * scale, y + j * scale, x + i * scale + scale - 1,
                                  y + j * scale + scale - 1, c)
            x += 6 * scale

    def save(self, path):
        raw = bytearray()
        st = 3 * self.w
        for y in range(self.h):
            raw.append(0)
            raw += self.px[y * st:(y + 1) * st]

        def chunk(t, d):
            return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
        png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", self.w, self.h, 8, 2, 0, 0, 0))
        png += chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b"")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "wb").write(png)


def rgb_rows(pix, pal, w):
    """pix: list of rows of colour indices -> list of RGB byte rows"""
    lut = [bytes(c) for c in pal]
    return [b"".join(lut[v] for v in r) for r in pix]


# ---------------------------------------------------------------- RD1
def rd1_maps():
    D = open(os.path.join(HERE, "atari_ram.bin"), "rb").read()
    u16 = lambda o: struct.unpack_from(">H", D, o)[0]
    u32 = lambda o: struct.unpack_from(">I", D, o)[0]
    ROOM_HEADERS, N, BLOCK_DEFS = 0x47620, 47, 0x22FEE
    TILE_BANKS, PALETTE_ADDR = (0x1D01E, 0x1F01E), 0x4DEE2
    pal = []
    for i in range(16):
        w = u16(PALETTE_ADDR + i * 2)
        pal.append((((w >> 8) & 7) * 255 // 7, ((w >> 4) & 7) * 255 // 7, (w & 7) * 255 // 7))
    rooms = [{"variant": u16(ROOM_HEADERS + i * 14), "tilemap": u32(ROOM_HEADERS + i * 14 + 2)}
             for i in range(N)]
    bounds = sorted({r["tilemap"] for r in rooms} | {BLOCK_DEFS})
    for r in rooms:                                           # as kb/render_rooms.py
        nxt = next(b for b in bounds if b > r["tilemap"])
        own = (nxt - r["tilemap"]) // 8
        avail = (BLOCK_DEFS - r["tilemap"]) // 8
        r["rows"] = own + max(0, min(6, avail - own))
    tcache = {}

    def tile(bank, t):
        if (bank, t) not in tcache:
            off = TILE_BANKS[bank] + t * 32
            tcache[(bank, t)] = [[sum(((D[off + y * 4 + p] >> (7 - x)) & 1) << p for p in range(4))
                                  for x in range(8)] for y in range(8)]
        return tcache[(bank, t)]

    def render(i):
        r = rooms[i]
        pix = [[0] * 256 for _ in range(r["rows"] * 32)]
        for br in range(r["rows"]):
            for bc in range(8):
                blk = D[r["tilemap"] + br * 8 + bc]
                for k in range(16):
                    cell = tile(r["variant"], D[BLOCK_DEFS + blk * 16 + k])
                    ox, oy = bc * 32 + (k % 4) * 8, br * 32 + (k // 4) * 8
                    for y in range(8):
                        pix[oy + y][ox:ox + 8] = cell[y]
        return rgb_rows(pix, pal, 256)

    # connections from the port's dat_maps.c: lists in submap order, dir 0xff ends one
    src = open(os.path.join(REPO, "xrick", "xrick", "src", "rd1", "dat_maps.c")).read()
    body = src[src.index("connect_t map_connect"):]
    body = body[:body.index("};")]
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    recs = [tuple(int(v, 0) if v not in ("0000", "000000") else 0 for v in m)
            for m in re.findall(r"\{\s*(\w+)\s*,\s*(\w+)\s*,\s*(\w+)\s*,\s*(\w+)\s*\}", body)]
    exits, cur = [[] for _ in range(N)], 0
    for d, ro, sm, ri in recs:
        if d == 0xff:
            cur += 1
            continue
        exits[cur].append({"side": 1 if d == 1 else 2, "row": ro, "target": sm, "entry": ri,
                           "special": "NEXT MAP" if sm == 0xff else None})
    assert cur == N, cur
    # maps: start submaps 0, 9, $14, $26 (map_maps), each map up to the next start
    starts = [0, 9, 0x14, 0x26, N]
    out = []
    for m in range(4):
        subs = list(range(starts[m], starts[m + 1]))
        out.append({"game": 1, "map": m + 1, "start": starts[m], "subs": subs,
                    "img": {s: render(s) for s in subs},
                    "exits": {s: exits[s] for s in subs},
                    "rowpx": lambda row: row * 8})
    return out


# ---------------------------------------------------------------- RD2
def rd2_maps():
    K2 = os.path.join(REPO, "kb2")
    prg = open(os.path.join(K2, "prg2-ram.bin"), "rb").read()
    pal = []
    for i in range(16):
        w = struct.unpack(">H", prg[0x18ee6 + 2 * i:0x18ee6 + 2 * i + 2])[0]
        pal.append((((w >> 8) & 7) * 255 // 7, ((w >> 4) & 7) * 255 // 7, (w & 7) * 255 // 7))
    HDR, MAPBASE, BLOCKS, TILES = 0x1800, 0x3000, 0x3900, 0x4900
    start_sub = {1: 0, 2: 0, 3: 1, 4: 0}                      # algo-flow.md §5 start records
    out = []
    for m in range(1, 5):
        img = open(os.path.join(K2, "assets", "maps", "map%d_level.bin" % m), "rb").read()
        tl = []
        for n in range(256):
            t = []
            for y in range(8):
                row = img[TILES + 40 * n + 5 * y:TILES + 40 * n + 5 * y + 4]
                t.append([sum(((row[p] >> (7 - x)) & 1) << p for p in range(4)) for x in range(8)])
            tl.append(t)
        count = struct.unpack(">H", img[HDR + 4:HDR + 6])[0] // 8
        subs, imgs, exits = [], {}, {}
        for i in range(count):
            w0, w1, w2, w3 = struct.unpack(">4H", img[HDR + 8 * i:HDR + 8 * i + 8])
            ex, a = [], HDR + w2
            while img[a] != 0:
                b0, b1, b2, b3 = img[a:a + 4]
                ex.append({"side": b0 & 3, "row": b1, "target": b2, "entry": b3,
                           "special": "MAP DONE" if (b0 & 0x90) == 0x90 else None})
                a += 4
            if not ex:
                continue                                      # header stub
            subs.append(i)
            exits[i] = ex
            pix = []
            for row in range(8, w1 + 32):                     # the rows the screen can show
                prow = [[0] * 256 for _ in range(8)]
                for bx in range(8):
                    blk = img[BLOCKS + 16 * img[MAPBASE + w0 + 8 * (row >> 2) + bx]:][:16]
                    for k in range(4):
                        t = tl[blk[(row & 3) * 4 + k]]
                        for y in range(8):
                            prow[y][bx * 32 + k * 8:bx * 32 + k * 8 + 8] = t[y]
                pix += prow
            imgs[i] = rgb_rows(pix, pal, 256)
        out.append({"game": 2, "map": m, "start": start_sub[m], "subs": subs, "img": imgs,
                    "exits": exits, "rowpx": lambda row: (row - 8) * 8})
    return out


# ---------------------------------------------------------------- layout and drawing
def overview(M, path):
    subs, ex, img = M["subs"], M["exits"], M["img"]
    W = 256
    H = {s: len(img[s]) for s in subs}
    color = {s: COLORS[k % len(COLORS)] for k, s in enumerate(subs)}
    pos = {M["start"]: (0, 0)}
    order = [M["start"]]

    def overlaps(s, x, y):
        for t, (tx, ty) in pos.items():
            if t != s and x < tx + W + GAP // 2 and tx < x + W + GAP // 2 and \
               y < ty + H[t] + LABEL + 24 and ty < y + H[s] + LABEL + 24:
                return True
        return False

    i = 0
    while i < len(order):                                     # breadth first from the start
        u = order[i]; i += 1
        ux, uy = pos[u]
        for e in ex[u]:
            v = e["target"]
            if e["special"] or v not in H or v in pos:
                continue
            step = W + GAP if e["side"] == 2 else -(W + GAP)
            x = ux + step
            y = uy + M["rowpx"](e["row"]) - M["rowpx"](e["entry"])
            n = 0
            while overlaps(v, x, y) and n < 40:
                x += step; n += 1
            pos[v] = (x, y); order.append(v)
    for s in subs:                                            # anything unreachable: below the rest
        if s not in pos:
            pos[s] = (0, max(py + H[t] for t, (px, py) in pos.items()) + 200)
    minx = min(x for x, y in pos.values()) - 300
    miny = min(y for x, y in pos.values()) - LABEL - 60
    maxx = max(x + W for x, y in pos.values()) + 300
    maxy = max(y + H[s] for s, (x, y) in pos.items()) + 40
    C = Canvas(maxx - minx, maxy - miny, BG)
    title = "RICK DANGEROUS %d - MAP %d" % (M["game"], M["map"])
    C.text(12, 10, title, (255, 255, 255), 4)
    P = {s: (x - minx, y - miny) for s, (x, y) in pos.items()}
    for s in subs:
        x, y = P[s]
        C.blit(x, y, W, img[s])
        C.frame(x - BORDER, y - BORDER, x + W + BORDER - 1, y + H[s] + BORDER - 1, color[s], BORDER)
        lab = ("S%d" % s) + ("  START" if s == M["start"] else "")
        C.text(x, y - LABEL + 2, lab, color[s], 4)
    for s in subs:                                            # exits
        x, y = P[s]
        for e in ex[s]:
            ax = x + W + BORDER if e["side"] == 2 else x - BORDER - 1
            ay = y + M["rowpx"](e["row"]) + 4
            if e["special"]:
                bx = ax + (90 if e["side"] == 2 else -90)
                C.line(ax, ay, bx, ay, color[s], 5)
                C.head(ax, ay, bx, ay, color[s], 22)
                tx = bx + 8 if e["side"] == 2 else bx - 8 - 6 * 3 * len(e["special"])
                C.text(tx, ay - 10, e["special"], color[s], 3)
                continue
            v = e["target"]
            if v not in P:
                continue
            tx, ty = P[v]
            bx = tx - BORDER - 1 if e["side"] == 2 else tx + W + BORDER
            by = ty + M["rowpx"](e["entry"]) + 4
            # an entry row outside the rows drawn for the target (RD2 map 1: submap 2's
            # tunnel exit enters submap 0 at row 74, which shows rows 8..31): clamp it to
            # the target's edge and dash the line
            dashed = not (ty <= by < ty + H[v])
            by = min(max(by, ty), ty + H[v] - 1)
            if dashed:
                C.dash(ax, ay, bx, by, color[s], 3)
            else:
                C.line(ax, ay, bx, by, color[s], 3)
            C.head(ax, ay, bx, by, color[s], 18)
    C.save(path)
    print("%s: %d submaps, %dx%d" % (path, len(subs), C.w, C.h))


def main():
    for M in rd1_maps():
        overview(M, os.path.join(HERE, "assets", "map_overviews", "rd1_map%d.png" % M["map"]))
    for M in rd2_maps():
        overview(M, os.path.join(REPO, "kb2", "assets", "map_overviews", "rd2_map%d.png" % M["map"]))


if __name__ == "__main__":
    main()
