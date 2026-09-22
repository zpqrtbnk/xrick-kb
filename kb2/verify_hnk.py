#!/usr/bin/env python3
"""
Independent checks of the HNK extraction.   python3 kb2/verify_hnk.py     (exit status 1 if a check fails)

1  the eight archives in kb2/assets/hnk are byte-identical to disks/chaos43/ and to the files inside the FAT12 image disks/chaos43_noauto.st
2  the game's own descriptor table ($12dd4 -> per map two (start sector, sector count) pairs) is read from kb2/prg2-ram.bin
3  the LSD! layer output equals the raw sectors of the ORIGINAL-disk image disks/RICKDA2/RD2 at those sectors (an implementation-independent check
   of hnk.depack) -- for 7 of 8 files; RICK_05 is the one where the crack packed the wrong 512 bytes (kb2/hnk-system.md section 6)
4  the loader's file-number check ($11f86: end sector -> ASCII digit) is consistent with the descriptors: which sector ranges the program can load at all
5  live game RAM (kb2/prg2-ram.bin, map 1 running): demo buffer $3efc0, level image $53400 (only 'already spawned' bits 0x80 differ), tile attributes $65200
6  the two loader-time snapshots dump_hnkload_hit1/2.bin: the HNK bytes sit at the depacker's input address
7  RICK2.PRG: its data section is an LSD! archive of the whole game program
"""
import os
import struct
import sys

import hnk

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ok = True


def check(cond, text):
    global ok
    print(("  ok   " if cond else "  FAIL ") + text)
    ok = ok and cond


def fat12_files(path):
    d = open(path, "rb").read()
    bps, spc, res, nfat, nroot, tot, _, spf = struct.unpack_from("<HBHBHHBH", d, 11)
    fat = d[res * bps:(res + spf) * bps]
    root = (res + nfat * spf) * bps
    data0 = root + nroot * 32
    cs = bps * spc
    out = {}
    for i in range(nroot):
        e = d[root + 32 * i:root + 32 * i + 32]
        if e[0] == 0:
            break
        if e[0] == 0xE5:
            continue
        name = e[:8].decode("latin1").strip() + "." + e[8:11].decode("latin1").strip()
        cl = struct.unpack_from("<H", e, 26)[0]
        sz = struct.unpack_from("<I", e, 28)[0]
        buf = b""
        while 2 <= cl < 0xFF0:
            buf += d[data0 + (cl - 2) * cs:data0 + (cl - 1) * cs]
            v = struct.unpack_from("<H", fat[cl * 3 // 2:cl * 3 // 2 + 2])[0]
            cl = (v >> 4) if cl & 1 else (v & 0xFFF)
        out[name] = buf[:sz]
    return out


def main():
    ram = open(os.path.join(HERE, "prg2-ram.bin"), "rb").read()
    hn = {n: open(os.path.join(HERE, "assets", "hnk", "RICK_%02d.HNK" % n), "rb").read() for n in range(1, 9)}

    print("1. the archives")
    fat = fat12_files(os.path.join(ROOT, "disks", "chaos43_noauto.st"))
    for n in range(1, 9):
        loose = open(os.path.join(ROOT, "disks", "chaos43", "RICK_%02d.HNK" % n), "rb").read()
        check(hn[n] == loose == fat["RICK_%02d.HNK" % n], "RICK_%02d.HNK (%d B): kb2/assets/hnk == disks/chaos43 == FAT12 image" % (n, len(hn[n])))

    print("2. the game's descriptor table")
    u32 = lambda a: struct.unpack(">I", ram[a:a + 4])[0]
    u16 = lambda a: struct.unpack(">H", ram[a:a + 2])[0]
    desc = []
    for i in range(5):
        pair = u32(0x12DD4 + 4 * i)                      # -> two pointers (demo descriptor, level descriptor)
        d0, d1 = u32(pair), u32(pair + 4)
        desc.append(((u16(d0), u16(d0 + 2)), (u16(d1), u16(d1 + 2))))
    for i, (a, b) in enumerate(desc):
        print("       map %d: demo (start sector %d, count %d)  level (start %d, count %d)" % (i + 1, a[0], a[1], b[0], b[1]))
    check(all(desc[i][0][0] + desc[i][0][1] == (desc[i + 1][0][0] if i < 4 else desc[0][1][0]) for i in range(5)) and
          all(desc[i][1][0] + desc[i][1][1] == desc[i + 1][1][0] for i in range(4)),
          "the descriptors are contiguous sector ranges (5 demos of 2 sectors, then 5 level blobs)")

    print("3. LSD! layer vs raw sectors of the original disk (disks/RICKDA2/RD2)")
    rd2 = open(os.path.join(ROOT, "disks", "RICKDA2", "RD2"), "rb").read()
    for m in range(1, 5):
        for k, n in ((0, 2 * m - 1), (1, 2 * m)):
            s, c = desc[m - 1][k]
            raw = rd2[s * 512:(s + c) * 512]
            got = hnk.depack(hn[n])
            same = raw == got
            if n == 5:
                check(not same and len(got) == 512, "RICK_05: depacks to %d B, the raw sectors %d-%d hold %d B that differ (expected: the crack packed the wrong data)" % (len(got), s, s + c - 1, len(raw)))
            else:
                check(same, "RICK_%02d.HNK depacked (%d B) == RD2 sectors %d..%d" % (n, len(got), s, s + c - 1))

    print("4. what the program's loader accepts ($11f86: end sector -> file digit)")
    ends, digits, a = [], [], 0x11F86
    # the code is: cmp.w #END,D1w / beq -> moveq #digit,D0  (8 pairs); read them from the bytes rather than assuming
    seq = ram[0x11F88:0x11FB8]
    for i in range(8):
        ends.append(struct.unpack(">H", seq[6 * i + 2:6 * i + 4])[0])
    for i in range(8):
        digits.append(ram[0x11FC0 + 4 * i + 1])
    print("       accepted end sectors:", ends, "-> digits", [chr(d) for d in digits])
    want = []
    for m in range(5):
        want += [desc[m][0][0] + desc[m][0][1], desc[m][1][0] + desc[m][1][1]]
    check(ends == want[:8] and [chr(d) for d in digits] == list("12345678"), "the 8 accepted end sectors are exactly maps 1-4 (demo, level); digit i = file RICK_0<i>.HNK")
    check(want[8] not in ends and want[9] not in ends, "map 5 end sectors %d / %d are NOT accepted (they reach the red-border loop at $11fb8)" % (want[8], want[9]))

    print("5. live RAM (map 1)")
    m1d = open(os.path.join(HERE, "assets", "maps", "map1_demo.bin"), "rb").read()
    m1 = open(os.path.join(HERE, "assets", "maps", "map1_level.bin"), "rb").read()
    check(ram[0x3EFC0:0x3EFC0 + 1024] == m1d, "$3efc0 (1024 B) == map1_demo.bin")
    live = ram[0x53400:0x53400 + 0x11F00]
    diff = [i for i in range(0x11F00) if live[i] != m1[i]]
    check(all(live[i] ^ m1[i] == 0x80 for i in diff), "$53400 level image: %d bytes differ from map1_level.bin, every one only in bit 0x80 (the runtime 'already spawned' bit of spawn records)" % len(diff))
    check(ram[0x65200:0x65300] == m1[0x11E00:0x11F00], "$65200 tile attribute table == image offset 0x11e00")

    print("6. loader-time snapshots")
    h1 = open(os.path.join(HERE, "dump_hnkload_hit1.bin"), "rb").read()
    h2 = open(os.path.join(HERE, "dump_hnkload_hit2.bin"), "rb").read()
    check(h1[0x3EFC0:0x3EFC0 + len(hn[1])] == hn[1], "hit1: RICK_01.HNK (%d B) sits at $3efc0 (the depacker's input address)" % len(hn[1]))
    check(h2[0x65300:0x65300 + len(hn[2])] == hn[2], "hit2: RICK_02.HNK (%d B) sits at $65300" % len(hn[2]))

    print("7. RICK2.PRG")
    prg = open(os.path.join(ROOT, "disks", "chaos43", "RICK2.PRG"), "rb").read()
    magic, tsize, dsize = struct.unpack(">HII", prg[:10])
    data = prg[28 + tsize:28 + tsize + dsize]
    game = hnk.depack(data)
    orig = fat12_files(os.path.join(ROOT, "disks", "rd2.st"))["FILE.DRS"]
    check(magic == 0x601A and data[:4] == b"LSD!", "RICK2.PRG = crack loader (text %d B) + an LSD! archive as its data section (%d B)" % (tsize, dsize))
    check(hnk.depack(orig) == game, "that archive depacks (%d B) to exactly the game program FILE.DRS of the other disk image disks/rd2.st" % len(game))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
