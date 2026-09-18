#!/usr/bin/env python3
"""
Build rick2_sfx.sndh from the Rick Dangerous 2 (Atari ST) program image.

Design (see sound-ref.md for the derivation of every constant here):

  * The game's own sound engine is copied byte-for-byte and EXECUTED. Nothing in
    it is reimplemented, and its behaviour is never second-guessed.
  * The engine needs TWO clocks and gets both, exactly as the game does:
      - 50 Hz bytecode/envelope driver: the SNDH play() entry (tag TC50), one
        call to FUN_0001a866 per tick. TC50 is what both genuine reference files
        in this directory use.
      - 4915.2 Hz type-2 sample streamer: a REAL MFP Timer-A interrupt. The
        engine already contains the installer (FUN_0001a978: sets vector $134,
        unmasks IERA/IMRA bit 5) and the arm block already programs TACR/TADR
        with TACR=6 (/100) and TADR=5 -> 2457600/500 = 4915.2 Hz. The installer
        has no callers in the game because the original called it from boot code
        outside the sound region; init() supplies that one missing host action.
    Driving the streamer from play() instead does NOT work: it makes the sample
    rate hostage to the player's tick rate, and no player honours ~4915 Hz.
  * Timer A is free for us because we declare TC50, so the player takes Timer C.

Deviations from the original bytes -- the complete list:

  1. The two `tst.w ($3efb6).l` address fields at $1a70c and $1a7fc are
     retargeted to a zero cell appended to the blob. $3efb6 is the demo-mode
     flag, lies outside the copied region, and reads 0 during normal gameplay.
     Control flow is untouched -- only what the tst reads.
  2. $1a974 is cleared before each dispatch (it is 1 in the image; every
     type-1/type-2 gate requires 0). This reproduces the precondition the game
     has whenever a sound genuinely triggers.

That is all. The streamer keeps its three RTE exits because it is once again a
genuine interrupt handler. $1a975 and the per-channel envelope accumulators are
left alone: the engine never resets them either, so carry-over is the original
design.

Host substitution in the stub (not modifications to engine code): init() calls
the engine's own Timer-A installer and stops any still-running stream before
dispatching; exit() stops and masks Timer A so nothing can fire after the
player unloads the file.
"""
import struct
import pathlib

# paths are relative to this script, so it runs from anywhere
_HERE = pathlib.Path(__file__).resolve().parent
SRC = _HERE / 'prg2-ram.bin'
OUT = _HERE / 'rick2_sfx.sndh'

LO       = 0x19e96      # start of sound region
HI       = 0x31eb0      # end: id 47's stream terminator + 1 (terminator scan)
CODE_END = 0x1c6aa      # code+tables end; beyond this is raw stream data
DT       = 0x1c376      # dispatch table
NSUB     = 92           # 92 entries, ids 0..91

# blob-relative offsets of the engine entry points we call
ENTRY   = 0x1a6aa - LO  # dispatcher       FUN_0001a6aa(D0=id, D1=param)
TICK    = 0x1a866 - LO  # 50 Hz driver     FUN_0001a866
SILENCE = 0x1ae96 - LO  # silence-all      FUN_0001ae96
TMRINIT = 0x1a978 - LO  # Timer-A installer FUN_0001a978
A974    = 0x1a974 - LO  # master state byte

GATE_SITES = (0x1a70c, 0x1a7fc)            # $3efb6 operand fields

# MFP68901 registers (fixed hardware addresses, never relocated)
IERA = 0xfffffa07       # interrupt enable A  (bit 5 = Timer A)
IMRA = 0xfffffa13       # interrupt mask A    (bit 5 = Timer A)
TACR = 0xfffffa19       # Timer A control     (0 = stopped)

# stub variable, addressed via A1
V_GUARD, VARLEN = 0, 2

# ---------------------------------------------------------------- 68000 helpers
def w(x):
    assert 0 <= x <= 0xffff, hex(x)
    return struct.pack('>H', x)

def l(x):
    return struct.pack('>I', x & 0xffffffff)

def sw(x):                      # signed 16-bit displacement
    assert -32768 <= x <= 32767, f'displacement out of range: {x}'
    return struct.pack('>h', x)

# ------------------------------------------------------------------- read image
img = SRC.read_bytes()
assert len(img) == 0x100000, len(img)

ents = [struct.unpack_from('>HHI', img, DT + i * 8) for i in range(NSUB)]
n0 = sum(1 for t, _, _ in ents if t == 0)
n1 = sum(1 for t, _, _ in ents if t == 1)
n2 = sum(1 for t, _, _ in ents if t == 2)
assert (n0, n1, n2) == (10, 45, 37), (n0, n1, n2)

# every type-2 stream must terminate before the next one starts, and HI must be
# exactly the highest terminator + 1
ptrs = sorted({ptr for t, _, ptr in ents if t == 2})
terms = {}
for p in ptrs:
    e = img.index(b'\x00', p)
    nxt = min((q for q in ptrs if q > p), default=None)
    assert nxt is None or e < nxt, f'stream 0x{p:x} overruns 0x{nxt:x}'
    terms[p] = e
assert max(terms.values()) + 1 == HI, hex(max(terms.values()) + 1)

# timer preset 0, used by all 37 type-2 entries -> the play() rate
assert all(p == 0 for t, p, _ in ents if t == 2)
TA_CTRL, TA_DATA = img[0x1a962], img[0x1a963]
assert (TA_CTRL, TA_DATA) == (6, 5), (TA_CTRL, TA_DATA)
PRESCALE = {1: 4, 2: 10, 3: 16, 4: 50, 5: 64, 6: 100, 7: 200}[TA_CTRL]
STREAM_RATE = 2457600 / (PRESCALE * TA_DATA)
assert STREAM_RATE == 4915.2, STREAM_RATE
PLAY_RATE = 50           # the SNDH tick; drives FUN_0001a866 only

# ------------------------------------------------------------------- build blob
blob = bytearray(img[LO:HI])
ZERO = len(blob)                      # zero cell for the $3efb6 redirect
blob += b'\x00\x00'
assert ZERO % 2 == 0

for a in (0x1a9ca, 0x1a9ee, 0x1aa06):  # streamer exits stay RTE: it is a real ISR
    assert blob[a - LO:a - LO + 2] == b'\x4e\x73', f'no RTE at 0x{a:x}'

for a in GATE_SITES:                  # deviation 1
    o = a - LO
    assert blob[o:o + 4] == struct.pack('>I', 0x3efb6), f'no $3efb6 at 0x{a:x}'
    blob[o:o + 4] = struct.pack('>I', LO + ZERO)

# ------------------------------------------------------- relocation fixup table
# Every even offset in the code/table region holding a longword that points back
# into that same region, plus the type-2 ptr fields structurally (their values
# lie above CODE_END so a scan cannot see them), plus our two retargeted
# operands.
fx = set()
for a in range(LO, CODE_END - 3, 2):
    v, = struct.unpack_from('>I', img, a)
    if LO <= v < CODE_END:
        fx.add(a - LO)
scanned = len(fx)
for i, (t, _, _) in enumerate(ents):
    if t == 2:
        fx.add(DT + i * 8 + 4 - LO)
structural = len(fx) - scanned
fx |= {a - LO for a in GATE_SITES}
fixups = sorted(fx)

assert scanned == 78, scanned
assert len(fixups) == 116, len(fixups)          # 78 + 37 - 1 overlap + 2 gates
assert (TMRINIT_IMM := 0x1a97a - LO) in fixups  # the ISR address the installer
#   writes to vector $134 must itself be relocated, or $134 gets the pre-reloc
#   address and the first Timer-A interrupt jumps into unrelated memory.
assert all(o < 0x8000 for o in fixups)          # 0xffff is then unambiguous
for o in fixups:
    v, = struct.unpack_from('>I', blob, o)
    assert LO <= v <= LO + ZERO, f'fixup 0x{o:x} holds 0x{v:x}'

FIXTAB = b''.join(w(o) for o in fixups) + w(0xffff)

# ------------------------------------------------------------------ SNDH header
def tag(name, body=b''):
    return name + body + b'\x00'

TAGS = (b'SNDH'
        + tag(b'TITL', b'Rick Dangerous 2')
        + tag(b'COMM', b'Core Design / Ben Daglish - all 92 in-game sounds')
        + tag(b'RIPP', b'extracted from RICK2.PRG')
        + tag(b'CONV', b'build_sndh.py')
        + tag(b'YEAR', b'1990')
        + tag(b'##%02d' % NSUB)
        + tag(b'#!01')
        + tag(b'TC%d' % PLAY_RATE)
        + tag(b'FLAG', b'~y'))
if (12 + len(TAGS) + 4) % 2:
    TAGS += b'\x00'
TAGS += b'HDNS'
CODE_OFF = 12 + len(TAGS)
assert CODE_OFF % 2 == 0

# ------------------------------------------------------------------ stub layout
def build_stub(off, blob_pos):
    """Emit the stub at file offset `off`, with the blob at `blob_pos`.
    Returns (bytes, symbol dict). All instruction lengths are fixed, so the
    length of the result does not depend on `blob_pos`."""
    s = {}
    body = bytearray(VARLEN)
    s['vars'] = off
    s['fixups'] = off + len(body); body += FIXTAB
    if len(body) % 2: body += b'\x00'

    def here():
        return off + len(body)

    def e(*parts):
        for p in parts:
            body.extend(p)

    def lea_pc(target, reg_opcode):
        """lea (d16,PC),An -- EA = address of extension word + d16"""
        e(w(reg_opcode), sw(target - (here() + 2)))

    def patch_branch(site, target):
        i = site - off + 2
        body[i:i + 2] = sw(target - (site + 2))

    # ---------------------------------------------------------------- init(D0)
    s['init'] = here()
    e(w(0x5340))                                   # subq.w #1,D0  (1-based!)
    lea_pc(blob_pos, 0x41FA)                       # lea blob(PC),A0
    lea_pc(s['vars'], 0x43FA)                      # lea vars(PC),A1
    # ---- one-time self-relocation
    e(w(0x4A29), sw(V_GUARD))                      # tst.b (guard,A1)
    br_done1 = here(); e(w(0x6600), w(0))          # bne.w reloced
    e(w(0x137C), w(0x0001), sw(V_GUARD))           # move.b #1,(guard,A1)
    e(w(0x2208))                                   # move.l A0,D1
    e(w(0x0481), l(LO))                            # subi.l #LO,D1
    lea_pc(s['fixups'], 0x45FA)                    # lea fixups(PC),A2
    rloop = here()
    e(w(0x341A))                                   # move.w (A2)+,D2
    br_done2 = here(); e(w(0x6B00), w(0))          # bmi.w reloced
    e(w(0x48C2))                                   # ext.l D2
    e(w(0xD3B0), w(0x2800))                        # add.l D1,(0,A0,D2.L)
    e(w(0x6000), sw(rloop - (here() + 2)))         # bra.w rloop
    reloced = here()
    patch_branch(br_done1, reloced)
    patch_branch(br_done2, reloced)
    # ---- per-init setup
    # stop any stream still running from a previous subtune (the dispatcher does
    # this itself on the type-0 and type-1 paths; type-2 relies on its arm block)
    e(w(0x4239), l(TACR))                          # clr.b (TACR).l
    # install the engine's own Timer-A ISR + unmask it. Idempotent, and verified
    # to clobber no registers (two absolute move/bset only).
    e(w(0x4EA8), sw(TMRINIT))                      # jsr (TMRINIT,A0)
    e(w(0x4228), sw(A974))                         # clr.b (a974,A0)   deviation 2
    e(w(0x3F00))                                   # move.w D0,-(SP)
    e(w(0x4EA8), sw(SILENCE))                      # jsr (SILENCE,A0)
    lea_pc(blob_pos, 0x41FA)                       # lea blob(PC),A0  (SILENCE may
    e(w(0x301F))                                   # move.w (SP)+,D0   clobber A0)
    e(w(0x7200))                                   # moveq #0,D1
    e(w(0x4EA8), sw(ENTRY))                        # jsr (ENTRY,A0)
    e(w(0x4E75))                                   # rts

    # ------------------------------------------------------------------ exit()
    # Stop and mask Timer A first: our ISR lives in the loaded file, so it must
    # be unable to fire once the player unloads it.
    s['exit'] = here()
    e(w(0x4239), l(TACR))                          # clr.b (TACR).l
    e(w(0x08B9), w(0x0005), l(IERA))               # bclr #5,(IERA).l
    e(w(0x08B9), w(0x0005), l(IMRA))               # bclr #5,(IMRA).l
    lea_pc(blob_pos, 0x41FA)                       # lea blob(PC),A0
    e(w(0x4EA8), sw(SILENCE))                      # jsr (SILENCE,A0)
    e(w(0x4E75))                                   # rts

    # ------------------------------------------------------------------ play()
    # One call to the 50 Hz driver per SNDH tick. The type-2 streamer is driven
    # by the hardware Timer-A interrupt, not from here.
    s['play'] = here()
    lea_pc(blob_pos, 0x41FA)                       # lea blob(PC),A0
    e(w(0x4EA8), sw(TICK))                         # jsr (TICK,A0)
    e(w(0x4E75))                                   # rts

    if len(body) % 2:
        body += b'\x00'
    return bytes(body), s

# length is blob_pos-independent, so one probe fixes the blob position exactly
probe, _ = build_stub(CODE_OFF, 0)
BLOB_POS = CODE_OFF + len(probe)
code, syms = build_stub(CODE_OFF, BLOB_POS)
assert len(code) == len(probe)

# ------------------------------------------------------------------- emit file
out = bytearray()
for i, name in enumerate(('init', 'exit', 'play')):
    site = i * 4
    out += w(0x6000) + sw(syms[name] - (site + 2))
out += TAGS
assert len(out) == CODE_OFF, (len(out), CODE_OFF)
out += code
assert len(out) == BLOB_POS, (len(out), BLOB_POS)
out += blob

OUT.write_bytes(out)
print(f'wrote {OUT.name}: {len(out)} bytes')
print(f'  code at 0x{CODE_OFF:x}   blob at 0x{BLOB_POS:x}   blob len {len(blob)}')
print(f'  init 0x{syms["init"]:x}  exit 0x{syms["exit"]:x}  play 0x{syms["play"]:x}')
print(f'  vars 0x{syms["vars"]:x}  fixups 0x{syms["fixups"]:x}')
print(f'  {NSUB} subtunes, 1-based (id = D0-1); {n0} type0 / {n1} type1 / {n2} type2')
print(f'  play() = TC{PLAY_RATE} -> FUN_0001a866 once per tick')
print(f'  type-2 streamer = hardware MFP Timer A, {STREAM_RATE} Hz '
      f'(TACR={TA_CTRL} /{PRESCALE}, TADR={TA_DATA})')
print(f'  fixups {len(fixups)} = {scanned} scanned + {structural} structural '
      f'+ {len(GATE_SITES)} gate operands')
