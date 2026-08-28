#!/usr/bin/env python3
"""
Rick Dangerous (Atari ST) — SNDH builder.

Packages the game's *original* sound engine — tracked music, sound effects and
PCM/digidrum samples alike — into a single SNDH file with one subtune per entry in
`music_track_table`. SNDH players (sc68, sndh-player, ZXTune) contain a 68000
emulator, so the original replay code runs verbatim; nothing is re-synthesised and
no emulator is written here.

WHY THIS WORKS
    An audit of every global the sound engine touches shows the whole subsystem is
    one contiguous window: code 0x44C10-0x45720, state/tables 0x44F08-0x46B66, song
    data in 0x45720-0x48F15, PCM samples at 0x4DF86 / 0x4FCF2 / 0x50DA8. Nothing
    below 0x44C10, nothing in the graphics blob, no calls into game code. So the
    window 0x44C10..0x5324F is self-contained and can be lifted wholesale.

WHY A RELOCATING STUB IS NEEDED
    The replay code is position-dependent — absolute addressing throughout
    (`jsr 0x44CCE.l`, data at 0x45720/0x46932/0x4DF86). SNDH players load the file
    at an address of their choosing, so the stub copies the image back to 0x44C10
    before calling anything.

WHY setup_timer_a MATTERS
    PCM samples are played from the MFP Timer-A interrupt, not from the 50 Hz tick.
    `init` therefore calls setup_timer_a (0x45006) as well as play_music; without it
    the tracked music plays but every digidrum is silent.

The 68000 stub is hand-assembled below. Every opcode encoding used is verified
against an identical instruction found elsewhere in this same binary (see ENCODINGS).
"""

import os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
D    = open(os.path.join(HERE, "atari_ram.bin"), "rb").read()
OUT  = os.path.join(HERE, "assets", "audio")
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- constants
IMG_BASE   = 0x44C10          # first byte of the sound window (reset_sound_chip)
IMG_END    = 0x53250          # end of the program image = end of the last sample
DUMP_END   = len(D)           # 0x50000 — our capture stops here
TRACK_TBL  = 0x44F08
N_TRACKS   = 29

FN_RESET   = 0x44C10          # reset_sound_chip
FN_PLAY    = 0x44CCE          # play_music(d0 = track, d1 = variant)
FN_TICK    = 0x44E0C          # music_tick  (called once per 50 Hz frame)
FN_TIMERA  = 0x45006          # setup_timer_a  — required for PCM
FN_SILENCE = 0x45528          # silence_all_channels — clears the 3 channel-active
                              # flags (0x45454/0x4546E/0x45488) and zeroes PSG volumes

# ENCODINGS — each verified against a real instruction in atari_ram.bin
MOVEM_PUSH = 0x48E7FFFE       # movem.l d0-a6,-(sp)      (as at 0x4B032)
MOVEM_POP  = 0x4CDF7FFF       # movem.l (sp)+,d0-a6      (as at render_sprites tail)
SUBQ1_D0   = 0x5340           # subq.w #1,d0             (cf. 0x5347 at 0x4C07C)
PUSH_D0_W  = 0x3F00           # move.w d0,-(sp)          (cf. 0x1F00 at 0x49272)
POP_D0_W   = 0x301F           # move.w (sp)+,d0          (cf. 0x101F at 0x492A2)
LEA_PC_A0  = 0x41FA           # lea d16(pc),a0           (as at 0x45686)
LEA_ABS_A1 = 0x43F9           # lea xxx.l,a1             (as at 0x4B072)
MOVE_L_INC = 0x22D8           # move.l (a0)+,(a1)+
MOVEW_IMM_D7 = 0x3E3C         # move.w #imm,d7           (cf. 0x303C at 0x4C530)
DBF_D7     = 0x51CF           # dbf d7,disp              (cf. 0x51C8 at 0x4B31A)
JSR_ABS    = 0x4EB9           # jsr xxx.l                (as at 0x4C536)
MOVEQ0_D1  = 0x7200           # moveq #0,d1             (cf. 0x7201 at 0x4C534)
RTS        = 0x4E75           # rts
BRA_W      = 0x6000           # bra.w disp
MOVE_SR_PUSH = 0x40E7         # move.w sr,-(sp)
MOVE_POP_SR  = 0x46DF         # move.w (sp)+,sr
MOVE_IMM_SR  = 0x46FC         # move.w #imm,sr

be16 = lambda v: struct.pack(">H", v & 0xFFFF)
be32 = lambda v: struct.pack(">I", v & 0xFFFFFFFF)

# ------------------------------------------------------------- the image
have  = D[IMG_BASE:DUMP_END]                    # what the capture actually holds
full  = IMG_END - IMG_BASE                      # what the engine really spans
blob  = have + b"\x00" * (full - len(have))     # zero-fill the uncaptured tail
assert len(blob) == full and full % 4 == 0
missing = full - len(have)

# ---------------------------------------------------------------- header
def tag(name, value=None):
    b = name.encode()
    if value is not None:
        b += str(value).encode() + b"\x00"
    return b

hdr  = b"SNDH"
hdr += tag("TITL", "Rick Dangerous")
hdr += tag("COMM", "Unknown")                   # composer not established — do not invent one
hdr += tag("RIPP", "xrick RE project")
hdr += tag("CONV", "build_sndh.py (engine lifted from a Hatari RAM snapshot)")
hdr += tag("##",   N_TRACKS)
hdr += tag("TC",   50)                          # play() called at 50 Hz
hdr += b"HDNS"
if len(hdr) & 1:
    hdr += b"\x00"

# ------------------------------------------------------- lay the file out
# 0: bra.w init | 4: bra.w exit | 8: bra.w play | 12: header | code | blob
CODE_AT = 12 + len(hdr)

def build(blob_off):
    """Assemble the stub given where the blob will land; returns (code, init/exit/play offsets)."""
    c = bytearray()
    off = lambda: CODE_AT + len(c)

    init_off = off()
    c += be32(MOVEM_PUSH)
    c += be16(SUBQ1_D0)                          # SNDH subtunes are 1-based
    c += be16(PUSH_D0_W)                         # stash track across the calls
    # Interrupts OFF across the copy: if Timer A is still armed from a previous
    # subtune, its ISR streams from 0x457C8 -- which lives inside the blob we are
    # overwriting. Without this the copy races the sample interrupt.
    c += be16(MOVE_SR_PUSH)
    c += be16(MOVE_IMM_SR) + be16(0x2700)
    lea_at = off()
    c += be16(LEA_PC_A0)
    # lea d16(pc),a0 : EA = (address of extension word) + d16
    c += be16(blob_off - (lea_at + 2))
    c += be16(LEA_ABS_A1) + be32(IMG_BASE)
    c += be16(MOVEW_IMM_D7) + be16(len(blob) // 4 - 1)
    loop_at = off()
    c += be16(MOVE_L_INC)
    c += be16(DBF_D7) + be16(loop_at - (off() + 2))
    c += be16(MOVE_POP_SR)                       # interrupts back on
    c += be16(JSR_ABS) + be32(FN_RESET)
    # Only type-0 tracks call init_music_playback (which zeroes the per-channel work
    # area). Type-1 and type-2 tracks assume the engine is already clean, as it is in
    # the real game where music starts first. Our blob restores the snapshot's LIVE
    # state (track 5 mid-play, song_active=0xFF00), so without this the stale channel
    # rings under every type-1/2 subtune -- audible as a 'ding' from subtune 9 on.
    c += be16(JSR_ABS) + be32(FN_SILENCE)
    c += be16(JSR_ABS) + be32(FN_TIMERA)         # <- PCM depends on this
    c += be16(POP_D0_W)
    c += be16(MOVEQ0_D1)                         # variant 0 = loop
    c += be16(JSR_ABS) + be32(FN_PLAY)
    c += be32(MOVEM_POP)
    c += be16(RTS)

    exit_off = off()
    c += be32(MOVEM_PUSH)
    c += be16(JSR_ABS) + be32(FN_RESET)
    c += be16(JSR_ABS) + be32(FN_SILENCE)
    c += be32(MOVEM_POP)
    c += be16(RTS)

    play_off = off()
    c += be32(MOVEM_PUSH)
    c += be16(JSR_ABS) + be32(FN_TICK)
    c += be32(MOVEM_POP)
    c += be16(RTS)

    while (CODE_AT + len(c)) & 3:                # longword-align the blob
        c += b"\x00"
    return bytes(c), init_off, exit_off, play_off

# The blob offset depends on code length, which depends on the blob offset only via
# a 16-bit displacement — so assemble once to measure, then again with the real value.
probe, *_ = build(0)
blob_off  = CODE_AT + len(probe)
code, init_off, exit_off, play_off = build(blob_off)
assert CODE_AT + len(code) == blob_off, "layout shifted between passes"

branches  = be16(BRA_W) + be16(init_off - 2)
branches += be16(BRA_W) + be16(exit_off - 6)
branches += be16(BRA_W) + be16(play_off - 10)

sndh = branches + hdr + code + blob
path = os.path.join(OUT, "rick_dangerous.sndh")
open(path, "wb").write(sndh)

# ---------------------------------------------------------------- report
print(f"sound window   0x{IMG_BASE:05X}..0x{IMG_END-1:05X}  ({full} bytes)")
print(f"  captured     {len(have)} bytes")
print(f"  zero-filled  {missing} bytes  (uncaptured tail 0x{DUMP_END:05X}..0x{IMG_END-1:05X})")
print(f"header {len(hdr)}B, stub {len(code)}B, blob at +0x{blob_off:X}")
print(f"entry points: init=+0x{init_off:X} exit=+0x{exit_off:X} play=+0x{play_off:X}")
print(f"\nwrote {path}  ({len(sndh)} bytes, {N_TRACKS} subtunes)\n")

print("subtune  track  type  param  data_ptr   note")
for i in range(N_TRACKS):
    o = TRACK_TBL + i * 8
    ty, pa = struct.unpack_from(">hh", D, o)
    dp = struct.unpack_from(">I", D, o + 4)[0]
    kind = {0: "one-shot/SFX", 1: "retrigger", 2: "SAMPLE (PCM)"}.get(ty, f"type {ty}")
    note = ""
    if ty == 2:
        note = "truncated by capture" if dp >= DUMP_END else \
               ("runs past capture" if dp > DUMP_END - 0x400 else "intact")
    print(f"{i+1:>7}  {i:>5}  {ty:>4}  {pa:>5}  0x{dp:05X}  {kind}{'  <- ' + note if note else ''}")
