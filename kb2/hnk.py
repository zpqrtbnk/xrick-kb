#!/usr/bin/env python3
"""
Depacker for Rick Dangerous 2's "LSD!" .HNK archives.

Direct transcription of the game's own depacker at $73f0/$7444-$758e in
prg2-ram.bin (Ghidra disassembly), including its three PC-relative parameter
tables. Nothing here is guessed; each constant's source address is noted.

Container (verified against all 8 .HNK files):
    +0  'LSD!'
    +4  u32 big-endian  unpacked size
    +8  u32 big-endian  stream length  (== filesize - 4 in every file)
    +12 packed stream

Algorithm: backward LZ77. The stream is read from the END towards +12, MSB
first, and output is written from the END of the output buffer downwards. The
bit buffer is an 8-bit register with a marker bit: `lsl.b #1` shifts a bit out
into C, and when the register reaches 0 the marker has been consumed, so a new
byte is loaded and `roxl.b #1` both takes its MSB as the bit and re-injects the
marker at bit 0. Each byte therefore yields exactly 8 data bits.

The original also writes the ST border colour ($ffff8240) inside the literal
loop to make loading stripes; that is display-only and omitted.
"""
import struct

MAGIC = b'LSD!'

# $74ac: literal-run length. Escalating code: try the smallest class first and
# move up while the field reads all-ones. bits[i] / base[i], i = 3 down to 0.
LIT_BITS = (0x0a, 0x03, 0x02, 0x02)
LIT_BASE = (0x0e, 0x07, 0x04, 0x01)

# $7506: match length. index 0..4 (4 = shortest).
LEN_BITS = (0x0a, 0x02, 0x01, 0x00, 0x00)
LEN_BASE = (0x0a, 0x06, 0x04, 0x03, 0x02)

# $754a: match offset, 3 classes. Reads bits[i]+1 bits, adds base[i].
OFF_BITS = (0x0b, 0x04, 0x07)
OFF_BASE = (0x0120, 0x0000, 0x0020)


class _Bits:
    """Backward MSB-first bit reader with the marker-bit refill scheme."""

    __slots__ = ('d', 'p', 'r', 'x')

    def __init__(self, data, pos):
        self.d = data
        self.p = pos - 1          # move.b -(A0),D0b
        self.r = data[self.p]
        self.x = 0

    def bit(self):
        c = (self.r >> 7) & 1     # lsl.b #1,D0b
        self.r = (self.r << 1) & 0xFF
        self.x = c
        if self.r:
            return c
        self.p -= 1               # move.b -(A0),D0b
        self.r = self.d[self.p]
        c2 = (self.r >> 7) & 1    # roxl.b #1,D0b  (X re-enters as the marker)
        self.r = ((self.r << 1) & 0xFF) | self.x
        self.x = c2
        return c2

    def bits(self, n):
        v = 0
        for _ in range(n):        # roxl.w #1,D1w per bit -> MSB first
            v = (v << 1) | self.bit()
        return v

    def byte(self):
        self.p -= 1               # move.b -(A0),-(A1)
        return self.d[self.p]


def depack(data):
    """Depack one .HNK image. Returns the unpacked bytes."""
    if data[:4] != MAGIC:
        raise ValueError('not an LSD! archive')
    unpacked, stream_len = struct.unpack_from('>II', data, 4)
    if stream_len != len(data) - 4:
        raise ValueError(f'stream length {stream_len} != filesize-4 {len(data)-4}')

    out = bytearray(unpacked)
    op = unpacked                                   # A1, walks down

    # $744c-$7458: A0 = end of stream, then align:
    #   tst.w -(A0); bpl +2; subq.l #1,A0
    pos = len(data) - 2
    if struct.unpack_from('>h', data, pos)[0] < 0:
        pos -= 1
    b = _Bits(data, pos)

    END = 12                                        # A4+8 == filebase+12
    while True:
        if b.bit():                                 # $7464: 1 -> literal run
            if not b.bit():                         # $7470: short form, 1 byte
                n = 0
            else:
                i = 3
                while True:                         # $7478 escalating classes
                    nb = LIT_BITS[i]
                    n = b.bits(nb)
                    if i == 0 or n != (1 << nb) - 1:
                        break
                    i -= 1
                n += LIT_BASE[i]
            for _ in range(n + 1):                  # dbf -> n+1 bytes
                op -= 1
                out[op] = b.byte()

        # $74c0: match, or end of stream
        if b.p <= END:
            break

        i = 3                                       # $74ce length class
        while True:
            if not b.bit():
                break
            i -= 1
            if i == -1:
                break
        i += 1
        nb = LEN_BITS[i]
        length = (b.bits(nb) if nb else 0) + LEN_BASE[i]

        if length == 2:                             # $7556 short-offset form
            if b.bit():
                nb2, base = 8, 0x40
            else:
                nb2, base = 5, 0x00
            dist = b.bits(nb2 + 1) + base
        else:
            j = 1                                   # $751a offset class
            while True:
                if not b.bit():
                    break
                j -= 1
                if j == -1:
                    break
            j += 1
            dist = b.bits(OFF_BITS[j] + 1) + OFF_BASE[j]

        src = op + dist + length                    # $757a
        for _ in range(length):
            src -= 1
            op -= 1
            out[op] = out[src]

    if op != 0:
        raise ValueError(f'output underrun: {op} bytes never written')
    return bytes(out)


def depack_tree(src):
    """FUN_0001795c: the second-stage bit-tree decoder.

    Applied to the LSD!-depacked image of the large .HNK of each pair. Layout:
        +0     u32 output length
        +4     tree: pairs of int16. A bit selects the slot; a negative value
               is a leaf (symbol = its low byte), a positive value is a
               relative byte offset to the child pair.
        +0x400 bitstream: u16 big-endian words, MSB first.
    """
    n, = struct.unpack_from('>I', src, 0)
    out = bytearray(n)
    bp, cnt, acc = 0x400, 0, 0
    for i in range(n):
        node = 4
        while True:
            cnt -= 1
            if cnt < 0:
                cnt = 15
                acc, = struct.unpack_from('>H', src, bp)
                bp += 2
            bit = (acc >> 15) & 1
            acc = (acc << 1) & 0xFFFF
            if bit:
                node += 2
            v, = struct.unpack_from('>h', src, node)
            if v < 0:
                break
            node += v
        out[i] = v & 0xFF
    return bytes(out)


def unpack_all(data):
    """Full pipeline: LSD! layer, then the tree layer if one is present."""
    stage1 = depack(data)
    if len(stage1) > 0x400:
        n, = struct.unpack_from('>I', stage1, 0)
        if 0 < n < (1 << 22):
            try:
                return depack_tree(stage1), stage1
            except Exception:
                pass
    return stage1, None


if __name__ == '__main__':
    import pathlib, sys
    for a in sys.argv[1:]:
        p = pathlib.Path(a)
        r = depack(p.read_bytes())
        out = p.with_suffix('.bin')
        out.write_bytes(r)
        print(f'{p.name}: {p.stat().st_size} -> {len(r)} bytes  ({out.name})')
