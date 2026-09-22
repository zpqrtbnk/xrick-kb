#!/usr/bin/env python3
"""
Unpack Rick Dangerous 2's .HNK files.   python3 kb2/extract_hnk.py [--rd2]

Source of truth: the eight archives kb2/assets/hnk/RICK_01..08.HNK (byte-identical to disks/chaos43/, checked by
kb2/verify_hnk.py) and the game program's own depackers, transcribed in kb2/hnk.py. The full story of the format, why there
are two files per map and how the game loads them is in kb2/hnk-system.md.

Per map N (1..4), file pair (2N-1, 2N):
    RICK_(2N-1).HNK  one LSD! layer  ->  map<N>_demo.bin          the attract-mode input recording (1024 bytes; map 3: see hnk-system.md)
    RICK_(2N).HNK    LSD! layer      ->  map<N>_level_stage1.bin  (34816 / 37888 / 37376 / 39936 bytes; the game keeps it at $65300)
                     tree layer      ->  map<N>_level.bin         the level image, 73472 bytes, the game keeps it at $53400

Outputs in kb2/assets/maps/:  map<N>_demo.bin, map<N>_level_stage1.bin, map<N>_level.bin, demos.json, manifest.json.

--rd2 additionally unpacks the fifth data set that exists only in the raw original-disk image disks/RICKDA2/RD2 (sectors 19-20 and
314-388; this game program can not load it, see hnk-system.md section 7) into kb2/assets/maps/extra_rd2/.
"""
import hashlib
import json
import os
import struct
import sys

import hnk

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HNKDIR = os.path.join(HERE, "assets", "hnk")
OUT = os.path.join(HERE, "assets", "maps")
MAPS = {1: (1, 2), 2: (3, 4), 3: (5, 6), 4: (7, 8)}        # map -> (small file number, big file number)
BITS = {0: "up", 1: "down", 2: "left", 3: "right", 7: "fire"}   # kb2/algo-player.md section 1
md5 = lambda b: hashlib.md5(b).hexdigest()


def demo_pairs(b):
    """(count, state) pairs of a demo stream as read by read_player_input $141cc: count 0 ends the stream."""
    pairs, i = [], 0
    while i + 1 < len(b) and b[i] != 0:
        pairs.append((b[i], b[i + 1]))
        i += 2
    ended = i + 1 < len(b) and b[i] == 0
    return pairs, ended, i


def demo_json(b):
    pairs, ended, term = demo_pairs(b)
    states = sorted({s for _, s in pairs})
    stray = sorted(s for s in states if s & ~0x8F)
    return {"bytes": len(b), "pairs": len(pairs), "frames": sum(c for c, _ in pairs), "terminator_at": term if ended else None,
            "states": ["%02x" % s for s in states], "states_outside_the_five_input_bits": ["%02x" % s for s in stray],
            "valid": bool(ended and not stray), "stream": [[c, s] for c, s in pairs]}


def main():
    os.makedirs(OUT, exist_ok=True)
    manifest, demos = {}, {}
    for m, (ns, nb) in MAPS.items():
        small = open(os.path.join(HNKDIR, "RICK_%02d.HNK" % ns), "rb").read()
        big = open(os.path.join(HNKDIR, "RICK_%02d.HNK" % nb), "rb").read()
        demo = hnk.depack(small)
        level, stage1 = hnk.unpack_all(big)
        assert stage1 is not None and len(level) == 0x11F00
        for name, data in (("demo", demo), ("level_stage1", stage1), ("level", level)):
            with open(os.path.join(OUT, "map%d_%s.bin" % (m, name)), "wb") as f:
                f.write(data)
        manifest["map%d" % m] = {
            "demo": {"hnk": "RICK_%02d.HNK" % ns, "hnk_bytes": len(small), "hnk_md5": md5(small), "bytes": len(demo), "md5": md5(demo)},
            "level": {"hnk": "RICK_%02d.HNK" % nb, "hnk_bytes": len(big), "hnk_md5": md5(big), "stage1_bytes": len(stage1), "stage1_md5": md5(stage1),
                      "bytes": len(level), "md5": md5(level)}}
        demos["map%d" % m] = demo_json(demo)
        print("map %d: RICK_%02d.HNK %5d B -> demo %4d B%s | RICK_%02d.HNK %5d B -> stage1 %5d B -> level %d B" % (
            m, ns, len(small), len(demo), "" if demos["map%d" % m]["valid"] else " (NOT a valid stream)", nb, len(big), len(stage1), len(level)))
    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    with open(os.path.join(OUT, "demos.json"), "w") as f:
        json.dump({"note": "count = number of frames the state byte is held; state bits " + json.dumps(BITS) + "; see kb2/hnk-system.md", **demos}, f)

    if "--rd2" in sys.argv:
        rd2 = open(os.path.join(ROOT, "disks", "RICKDA2", "RD2"), "rb").read()
        ex = os.path.join(OUT, "extra_rd2")
        os.makedirs(ex, exist_ok=True)
        demo = rd2[19 * 512:21 * 512]
        stage1 = rd2[314 * 512:389 * 512]
        level = hnk.depack_tree(stage1)
        for name, data in (("map5_demo", demo), ("map5_level_stage1", stage1), ("map5_level", level)):
            with open(os.path.join(ex, name + ".bin"), "wb") as f:
                f.write(data)
        print("extra (RD2 raw sectors, map 5): demo %d B %s, stage1 %d B, level %d B" % (
            len(demo), "valid" if demo_json(demo)["valid"] else "INVALID", len(stage1), len(level)))


if __name__ == "__main__":
    main()
