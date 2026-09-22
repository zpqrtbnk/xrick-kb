#!/usr/bin/env python3
"""
Extract Rick Dangerous 2's per-submap trigger and spawn tables and the monster descriptor table.

    python3 kb2/extract_tables.py        # writes kb2/assets/levels/tables.json

Grammar (from the game's code, disassembled in Ghidra 2026-09-19; see kb2/level-tables.md):

  submap header table   image 0x1800, 8 bytes per submap: w0 block-map offset, w1 max scroll/8,
                        w2 trigger table offset, w3 spawn table offset (both relative to image 0x1800)
  trigger table         records of 4 bytes, ended by ONE zero byte   (check_submap_exit_triggers $14362)
  spawn table           header 4 bytes + 4 * (byte3 & 3) detail bytes, repeated, ended by ONE zero byte
                        (scan_enemy_spawn_list $14594)
  For every map the tables chain exactly: trigger_i, spawn_i, trigger_i+1, ... (checked below).

  monster type table    image 0x0000: word i (i = type-1) is a self-relative offset: descriptor address =
                        2*i + word.  Descriptor: b0, b1, b2, b3, then four signed words that are offsets
                        from the descriptor's own address (FUN_000146a0 $146a0).
"""
import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
LEVELS = os.path.join(HERE, "assets", "levels")
MAPS = {1: "map1", 2: "map2", 3: "map3", 4: "map4"}   # map N -> kb2/assets/maps/map<N>_level.bin (the big HNK of the pair, fully unpacked)
MAPDIR = os.path.join(HERE, "assets", "maps")           # kb2/extract_hnk.py output
HDR = 0x1800


def trig(img, off):
    recs = []
    while img[off] != 0:
        b = img[off:off + 4]
        recs.append({"raw": b.hex(), "side": b[0] & 3, "flag5": bool(b[0] & 0x20), "screen_exit": bool(b[0] & 0x40),
                     "flag7": bool(b[0] & 0x80), "y_tile": b[1], "target_submap": b[2], "b3": b[3]})
        off += 4
    return recs, off + 1


def spawn(img, off):
    recs = []
    while img[off] != 0:
        h = img[off:off + 4]
        n = h[3] & 3
        d = [img[off + 4 + 4 * k: off + 8 + 4 * k].hex() for k in range(n)]
        rec = {"raw": h.hex(), "details": d, "type": h[0] & 0x7f, "y_tile": h[1], "monster_path": bool(h[2] & 0x80),
               "x_tile": h[2] & 0x1f, "x_plus4": bool(h[2] & 0x20), "flip": bool(h[3] & 0x80), "mode_bits": h[3] & 0x3c}
        recs.append(rec)
        off += 4 + 4 * n
    return recs, off + 1


def main():
    out = {}
    for m, name in MAPS.items():
        img = open(os.path.join(MAPDIR, "map%d_level.bin" % m), "rb").read()
        cnt = struct.unpack(">H", img[HDR + 4:HDR + 6])[0] // 8
        subs, used = [], set()
        for i in range(cnt):
            w0, w1, w2, w3 = struct.unpack(">4H", img[HDR + 8 * i: HDR + 8 * i + 8])
            t, e1 = trig(img, HDR + w2)
            s, e2 = spawn(img, HDR + w3)
            assert e1 == HDR + w3, (m, i, "trigger table does not end where the spawn table starts")
            if i + 1 < cnt:
                assert e2 == HDR + struct.unpack(">H", img[HDR + 8 * (i + 1) + 4: HDR + 8 * (i + 1) + 6])[0], (m, i)
            for r in s:
                if r["monster_path"] and 1 <= r["type"] <= 0x74:
                    used.add(r["type"])
            subs.append({"index": i, "triggers": t, "spawns": s})
        ntypes = max(used)
        offs = [2 * i + struct.unpack(">H", img[2 * i:2 * i + 2])[0] for i in range(ntypes)]
        mons = []
        for i, o in enumerate(offs):
            d = img[o:o + 12]
            ptr = [o + struct.unpack(">h", img[o + k:o + k + 2])[0] for k in (4, 6, 8, 10)]
            mons.append({"type": i + 1, "descriptor_offset": o, "b0": d[0], "b1": d[1], "b2": d[2], "b3": d[3],
                         "pointer_offsets": ptr})
        out["map%d" % m] = {"level_image": "map%d_level.bin" % m, "submaps": subs, "monster_types": mons,
                            "spawn_records": sum(len(s["spawns"]) for s in subs),
                            "trigger_records": sum(len(s["triggers"]) for s in subs)}
        print("map %d: %d submaps, %d triggers, %d spawns, %d monster types (ids 1..%d)" % (
            m, cnt, out["map%d" % m]["trigger_records"], out["map%d" % m]["spawn_records"], ntypes, ntypes))
    with open(os.path.join(LEVELS, "tables.json"), "w") as f:
        json.dump(out, f, indent=1)
    # tile attribute table: 256 bytes at image offset 0x11e00 ($65200), indexed by tile id (bit meanings: kb2/algo-actors.md section 6)
    attrs = {"map%d" % m: list(open(os.path.join(MAPDIR, "map%d_level.bin" % m), "rb").read()[0x11E00:0x11F00]) for m in MAPS}
    with open(os.path.join(LEVELS, "tile_attributes.json"), "w") as f:
        json.dump({"note": "tile attribute byte per tile id (level image offset 0x11e00 = $65200); tiles differ per map. Bit use: see kb2/algo-actors.md section 6",
                   "maps": attrs}, f)


if __name__ == "__main__":
    main()
