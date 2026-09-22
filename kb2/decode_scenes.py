#!/usr/bin/env python3
"""
Decode Rick Dangerous 2's cut-scene scripts.   python3 kb2/decode_scenes.py  ->  kb2/assets/levels/scenes.json

Source: `FUN_00018186` `$18186` (the scene runner; disassembled in Ghidra 2026-09-19).  Data: level image offset 0x2000
(= $55400), which holds per map:
    word 0x2000      offset of the image list (`$18326`: A3 = $55400 + word[$55400]; entry n at A3 + 2*(n-1) -> word offset of an image record)
    words 0x2002..   scene table: entry k = offset (from $55400) of scene k's script
    ...              scripts, image records, animation/movement scripts, text
The runner does `A0 = $55400 + word[$55402 + 2*scene]` and loops `op = word[A0]; if op == 0: stop; jsr handler[op-1]`.
Handlers (`$18232` table) and how far each one advances A0 (all read from the handlers):
    1 create sprite      (slot, x, y)              8 bytes   $1826a: slot A2 = $16d7c + 88*slot; [A2]=1; x, y; scripts/velocity cleared
    2 remove sprite      (slot)                    4         $182b6: [A2] = 0
    3 set velocity       (slot, dx, dy)            8         $182c8: clears move-script ptr, +$a = dx, +$c = dy
    4 set animation      (slot, off)               6         $182ea: +$1e = $55400 + off, wait counter 0
    5 clear / image      (0)  |  (n, 6 words)      4 | 16    $1830c: arg 0 clears the 32000-byte buffer at $68000; else draws image n via $18d00
    6 text               (col, row) + bytes + $ff  6 + len   $1834e: text drawn by $19316, then skip to after the $ff, padded to even
    7 skip                                         4         $1838a
    8 sound              (id)                      4         $18390: play_sound(id)
    9 run frames         (n)                       4         $183ac: n iterations that move + animate every sprite (`$183b4` loop)
   10 set movement       (slot, off)               6         $184aa: +$16 = $55400 + off, counters cleared
   11 skip                                         16        $184d2
   12 skip                                         4         $18502
   13 call               (off)                     -         $184dc: return address := A0 + 4; A0 := $55400 + off
   14 return                                       -         $184fa: A0 := return address
Text bytes are glyph ids of the font (`graphics.md` §4a): digits 0-9, letters at their ASCII codes, $20 = space.
"""
import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
LEVELS = os.path.join(HERE, "assets", "levels")
MAPS = {1: "map1", 2: "map2", 3: "map3", 4: "map4"}   # map N -> kb2/assets/maps/map<N>_level.bin (the big HNK of the pair, fully unpacked)
MAPDIR = os.path.join(HERE, "assets", "maps")           # kb2/extract_hnk.py output
BASE = 0x2000
u16 = lambda b, o: struct.unpack(">H", b[o:o + 2])[0]
OPNAME = {1: "create_sprite", 2: "remove_sprite", 3: "set_velocity", 4: "set_animation", 5: "image", 6: "text", 7: "skip4",
          8: "sound", 9: "run_frames", 10: "set_movement", 11: "skip16", 12: "skip4b", 13: "call", 14: "return"}


def glyph_text(bs):
    return "".join(chr(c) if 0x20 <= c < 0x7f else ("<%d>" % c if c < 10 else "<%02x>" % c) for c in bs)


def decode(img, off, depth=0, seen=None):
    """Decode one script from `off` until op 0 (end) or op 14 (return). Returns list of op dicts."""
    ops, seen = [], set() if seen is None else seen
    while True:
        assert off % 2 == 0, "odd script address %#x" % off
        assert off not in seen, "loop at %#x" % off
        seen.add(off)
        op = u16(img, off)
        if op == 0:
            ops.append({"at": off, "op": "end"})
            return ops
        assert 1 <= op <= 14, "bad opcode %d at %#x" % (op, off)
        e = {"at": off, "op": OPNAME[op]}
        if op == 1:
            e.update(slot=u16(img, off + 2), x=u16(img, off + 4), y=u16(img, off + 6)); n = 8
        elif op == 2:
            e.update(slot=u16(img, off + 2)); n = 4
        elif op == 3:
            e.update(slot=u16(img, off + 2), dx=struct.unpack(">h", img[off + 4:off + 6])[0],
                     dy=struct.unpack(">h", img[off + 6:off + 8])[0]); n = 8
        elif op == 4:
            e.update(slot=u16(img, off + 2), script_offset=u16(img, off + 4)); n = 6
        elif op == 5:
            a = u16(img, off + 2)
            if a == 0:
                e.update(arg=0); n = 4
            else:
                e.update(image=a, words=[u16(img, off + 4 + 2 * k) for k in range(6)]); n = 16
        elif op == 6:
            end = off + 6
            while img[end] != 0xff:
                end += 1
            e.update(col=u16(img, off + 2), row=u16(img, off + 4), glyphs=list(img[off + 6:end]), text=glyph_text(img[off + 6:end]))
            n = end + 1 - off
            if (off + n) % 2:
                n += 1
        elif op in (7, 12):
            n = 4
        elif op == 8:
            e.update(id=u16(img, off + 2)); n = 4
        elif op == 9:
            e.update(frames=u16(img, off + 2)); n = 4
        elif op == 10:
            e.update(slot=u16(img, off + 2), script_offset=u16(img, off + 4)); n = 6
        elif op == 11:
            n = 16
        elif op == 13:
            tgt = u16(img, off + 2)
            e.update(target=BASE + tgt)
            assert depth == 0, "nested call"
            e["subroutine"] = decode(img, BASE + tgt, depth + 1, set())
            n = 4
        elif op == 14:
            ops.append(e)
            return ops
        ops.append(e)
        off += n


def scene_images(img):
    """The image records of the scene zone (read from `$18326` / `$18d00`, checked on all four maps).

    word[0x2000] = offset (from 0x2000) of the image list; the list has (first entry - word[0x2000]) / 2 words, each the offset (from 0x2000) of an
    image record. A record is 4 words (cols, rows, 0, cols) followed by cols*rows bytes = glyph ids of the 256-glyph font at $3ce54 (row-major,
    `$18d00` reads one byte per 8x8 cell and copies the 32-byte glyph). Scene opcode 5 draws a rectangle of an image:
    words (dest col, dest row, src col, src row, width, height) in glyph cells. The records follow one another and the last one ends at the last
    non-zero byte of 0x2000..0x2fff (asserted)."""
    lst = BASE + u16(img, BASE)
    n = (u16(img, lst) - u16(img, BASE)) // 2
    ents = [u16(img, lst + 2 * i) for i in range(n)]
    out, expect = [], BASE + ents[0]
    for i, e in enumerate(ents):
        a = BASE + e
        assert a == expect, "image records are not contiguous"
        cols, rows, z, c2 = struct.unpack(">4H", img[a:a + 8])
        assert z == 0 and c2 == cols == 32, (cols, rows, z, c2)
        glyphs = [list(img[a + 8 + r * cols:a + 8 + (r + 1) * cols]) for r in range(rows)]
        out.append({"index": i + 1, "at": a, "cols": cols, "rows": rows, "glyphs": glyphs})
        expect = a + 8 + cols * rows
    last = max(i for i in range(BASE, BASE + 0x1000) if img[i])
    assert expect == last + 1, "images do not end at the last non-zero byte of the scene zone"
    return out


def main():
    out = {"doc": "see kb2/decode_scenes.py"}
    for m, name in MAPS.items():
        img = open(os.path.join(MAPDIR, "map%d_level.bin" % m), "rb").read()
        nscenes = (u16(img, BASE + 2) - 2) // 2
        scenes = []
        for k in range(nscenes):
            start = BASE + u16(img, BASE + 2 + 2 * k)
            scenes.append({"scene": k, "at": start, "ops": decode(img, start)})
        imgs = scene_images(img)
        out["map%d" % m] = {"image_list_offset": u16(img, BASE), "images": imgs, "scenes": scenes}
        texts = [o["text"] for s in scenes for o in s["ops"] if o["op"] == "text"]
        print("map %d: %d scene(s), %d ops, %d image(s) %s, texts: %s" % (m, nscenes, sum(len(s["ops"]) for s in scenes), len(imgs), [(i["cols"], i["rows"]) for i in imgs], texts[:3]))
    with open(os.path.join(LEVELS, "scenes.json"), "w") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
