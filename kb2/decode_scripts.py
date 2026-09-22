#!/usr/bin/env python3
"""
Decode Rick Dangerous 2's enemy byte-code scripts.   python3 kb2/decode_scripts.py  ->  kb2/assets/levels/scripts.json

Formats (from `advance_actor_move_script` $172fa and `advance_actor_anim_script` $171bc, read in Ghidra
2026-09-19; big-endian words; a script pointer points at the next record):

MOVEMENT script (actor +$16, repeat counter +$1a)  -> returns (dx, dy) signed bytes + carry
    word n != 0, -1 :  record (n.w, dx.b, dy.b)   apply (dx, dy) for n consecutive calls, then advance 4 bytes
    word 0          :  record (0.w, off.w)        jump: pointer += signed off (relative to THIS record); carry = 1
    word -1 ($ffff) :  record (-1.w, sound.w)     play sound `sound` if the actor's y is in [$23,$148]; advance 4; continue

ANIMATION script (actor +$1e, wait counter +$22)   -> writes the frame id to actor +$0e; carry = 1 after a jump
    word f >= 0     :  record (f.w)               show frame f, advance 2 (no wait)
    word -1 ($ffff) :  record (-1.w, off.w)       jump relative to this record; continue (carry = 1)
    word -3 ($fffd) :  record (-3.w, sound.w)     sound as above; advance 4; continue
    any other < 0   :  record (m.w, ticks.w, f.w) (canonically $fffe) show frame f for `ticks` calls (counter = ticks-1)

Sources: monster descriptors (image 0x0000 type table; descriptor +4 = movement, +6 = animation, offsets relative to the
descriptor), plus five scripts stored in the program itself: $1466e, $1468a, $14696, $12ed6 (anim, set with
`move.l #imm,(0x1e,A6)`) and $12e5e (the bomb's animation, put into record $16b12 by `update_player_rick` `$139e2`), plus the armed 5-actor group's scripts (anim `$159f6..$15a6e`, move `$158aa..$15b1c`, see algo-flow.md).
"""
import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
LEVELS = os.path.join(HERE, "assets", "levels")
MAPS = {1: "map1", 2: "map2", 3: "map3", 4: "map4"}   # map N -> kb2/assets/maps/map<N>_level.bin (the big HNK of the pair, fully unpacked)
MAPDIR = os.path.join(HERE, "assets", "maps")           # kb2/extract_hnk.py output
NTYPES = {1: 49, 2: 43, 3: 50, 4: 68}      # from kb2/extract_tables.py
s16 = lambda b, o: struct.unpack(">h", b[o:o + 2])[0]
u16 = lambda b, o: struct.unpack(">H", b[o:o + 2])[0]


def decode(buf, off, kind):
    ops, seen = [], set()
    while off not in seen:
        seen.add(off)
        w = s16(buf, off)
        if kind == "move":
            if w == 0:
                ops.append({"at": off, "op": "jump", "offset": s16(buf, off + 2), "target": off + s16(buf, off + 2)})
                return ops
            if w == -1:
                ops.append({"at": off, "op": "sound", "id": u16(buf, off + 2)})
            else:
                ops.append({"at": off, "op": "move", "count": w, "dx": struct.unpack(">b", buf[off + 2:off + 3])[0],
                            "dy": struct.unpack(">b", buf[off + 3:off + 4])[0]})
            off += 4
        else:
            if w >= 0:
                ops.append({"at": off, "op": "frame", "frame": w})
                off += 2
            elif w == -1:
                ops.append({"at": off, "op": "jump", "offset": s16(buf, off + 2), "target": off + s16(buf, off + 2)})
                return ops
            elif w == -3:
                ops.append({"at": off, "op": "sound", "id": u16(buf, off + 2)})
                off += 4
            else:
                ops.append({"at": off, "op": "show", "marker": w, "ticks": s16(buf, off + 2), "frame": s16(buf, off + 4)})
                off += 6
    return ops


def main():
    out = {"format": __doc__.split("\n\n")[1].strip() if False else "see kb2/decode_scripts.py docstring"}
    for m, name in MAPS.items():
        img = open(os.path.join(MAPDIR, "map%d_level.bin" % m), "rb").read()
        n = NTYPES[m]
        offs = [2 * i + u16(img, 2 * i) for i in range(n)]
        starts = {"move": set(), "anim": set()}
        types = []
        for i, o in enumerate(offs):
            mv, an = o + s16(img, o + 4), o + s16(img, o + 6)
            mops, aops = decode(img, mv, "move"), decode(img, an, "anim")
            starts["move"].update(op["at"] for op in mops)
            starts["anim"].update(op["at"] for op in aops)
            types.append({"type": i + 1, "movement_script_at": mv, "animation_script_at": an,
                          "movement": mops, "animation": aops})
        # every jump must land on a record boundary of a script of the same kind
        bad = 0
        for t in types:
            for kind, key in (("move", "movement"), ("anim", "animation")):
                j = t[key][-1]
                if j["target"] not in starts[kind]:
                    bad += 1
        out["map%d" % m] = {"level_image": "map%d_level.bin" % m, "types": types, "jump_targets_off_boundary": bad}
        print("map %d: %d types, %d scripts, jumps off a record boundary: %d" % (m, n, 2 * n, bad))
    ram = open(os.path.join(HERE, "prg2-ram.bin"), "rb").read()
    out["in_program"] = {"$%x" % a: decode(ram, a, "anim") for a in (0x1466e, 0x1468a, 0x14696, 0x12ed6, 0x12e5e)}
    # the armed 5-actor group (`FUN_00015b3c` template table $1586e, defeat table $15a2c; kb2/algo-flow.md section 8)
    out["in_program_group"] = {
        "anim": {"$%x" % a: decode(ram, a, "anim") for a in (0x159f6, 0x159fc, 0x15a02, 0x15a1e, 0x15a24, 0x15a54, 0x15a5a, 0x15a5c, 0x15a5e, 0x15a6e)},
        "move": {"$%x" % a: decode(ram, a, "move") for a in (0x158aa, 0x15a74, 0x15a98, 0x15ac4, 0x15af0, 0x15b1c)}}
    with open(os.path.join(LEVELS, "scripts.json"), "w") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
