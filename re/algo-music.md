# Rick Dangerous — Sound/Music Engine (0x44BEE–0x45720)

Exact transcription of the PSG sound engine, to re-codable precision. Every constant
is a literal; branch order is preserved; register conventions are stated per function.
Ghidra plate comments hold the raw evidence trail; this file is the reimplementation
reference.

**Scope:** all 16 functions in `0x44BEE`–`0x45720`, plus the sequence data format and
the digi-sample playback path.

---

## 0. Architecture overview

Three layers, driven from two different clocks:

| Layer | Clock | Purpose |
|---|---|---|
| **Tracked music** (`advance_music_channels` → `advance_channel_sequence`) | VBL (`music_tick`, 50 Hz) | Order list → patterns → notes |
| **Voice/envelope coroutines** (`step_all_channel_coroutines`) | VBL, every frame | ADSR + vibrato → PSG registers |
| **Digi samples** (`timer_a_music_isr`) | MFP Timer A | 8-bit PCM via 3-channel volume mixing |

Two *separate* per-channel state arrays, easily confused:

- **Music channel state** — base `0x45098`, stride **0x22 (34)**, 3 entries
  (`0x45098`, `0x450BA`, `0x450DC`). Sequencer bookkeeping.
- **Voice/output state** — base `0x4543C`, stride **0x1A (26)**, 3 entries
  (`0x4543C`, `0x45456`, `0x45470`). Envelope + what actually reaches the chip.
  Shared between music and sound effects; SFX take priority via bit 7 of `+0x18`.

`0x4543A` is the **PSG mixer shadow** (the value written to register 7), sitting two
bytes below the voice array.

### Global variables

| Address | Size | Name / meaning |
|---|---|---|
| `0x44F08` | 29×8 | `music_track_table` — `MusicTrackDescriptor[29]` |
| `0x44FF0` | 2/entry | Sample rate table: `[0]=TACR prescaler, [1]=TADR count` |
| `0x44FFC` | long | Current sample start pointer |
| `0x45000` | byte | TACR value for the pending sample |
| `0x45001` | byte | TADR value for the pending sample |
| `0x45002` | byte | **Engine state**: 0 idle, 1 tracked music, 2 start-sample, 0xFF sample playing |
| `0x45003` | byte | SFX voice alternator (0/1) |
| `0x45004` | byte | Loop flag (0 = one-shot, else loop) |
| `0x45005` | byte | Current track id |
| `0x45096` | byte | Song-active flag (0xFF while playing; **word-tested** by `music_tick`) |
| `0x45098` | 3×0x22 | Music channel state |
| `0x450FD` | 3×8 | Instrument-slot table (byte offsets into the instrument table) |
| `0x4543A` | byte | PSG mixer shadow (register 7) |
| `0x4543C` | 3×0x1A | Voice/output state |
| `0x45720` | 84×2 | `note_period_table` — PSG tone periods |
| `0x457C8` | long | Sample playback working pointer |
| `0x457CC` | 256×4 | Sample byte → PSG reg 8 (volume A) write |
| `0x45BCC` | 256×4 | Sample byte → PSG reg 9 (volume B) write |
| `0x45FCC` | 256×4 | Sample byte → PSG reg 10 (volume C) write |
| `0x463CC` | 10/entry | Instrument table |
| `0x46426` | 13/entry | SFX descriptor table |
| `0x4652A` | — | Pattern data base |
| `0x46932` | 9×6 | Song table (3 words/song), followed by the order lists |
| `0x46B00` | words | Pattern offset table (offsets from `0x4652A`) |
| `0x46B66` | 8/entry | Envelope segment table |

### PSG access idiom

`0xFFFF8800` = register select, `0xFFFF8802` = data. The code uses a longword trick:

```
move.l #0xRRxxVVxx, (0xFFFF8800).l
```
writes `RR` to `0xFFFF8800` (register select) and `VV` to `0xFFFF8802` (data), because
the four bytes land on `8800/8801/8802/8803`. So `#0x05000000` = "register 5 := 0".

### Music channel state layout (stride 0x22, base 0x45098)

| Off | Size | Meaning |
|---|---|---|
| +0x00 | word | Channel's base index into the instrument-slot table (**0, 8, 16** — static data, not set at runtime) |
| +0x02 | long | Order-list (sequence) pointer |
| +0x06 | long | Current pattern start (for repeats) |
| +0x0A | long | Current pattern position |
| +0x0E | long | Instrument pointer |
| +0x12 | byte | Pattern repeat counter |
| +0x13 | byte | Transpose |
| +0x14 | byte | "Need new pattern" flag (0xFF = pattern ended) |
| +0x15 | byte | Note duration counter |
| +0x16 | byte | Channel-active flag (0 = finished) |
| +0x17 | byte | Current note number |
| +0x18 | byte | Mixer enable nibble for this channel |
| +0x1A | long | Envelope segment data pointer |
| +0x1E | byte | Envelope step delay |
| +0x1F | byte | Envelope segment repeat count |
| +0x20 | byte | Envelope control: bit7 = note active, bit6 = restart, bits0-5 = envelope index |

### Voice/output state layout (stride 0x1A, base 0x4543C)

| Off | Size | Meaning |
|---|---|---|
| +0x00 | byte | Tone-enable AND mask |
| +0x01 | byte | Noise-enable AND mask |
| +0x02 | byte | Mixer OR bits (this voice's disable bits) |
| +0x04 | word | Tone period |
| +0x06 | byte | **Current volume, 8-bit** (written to PSG as `>>3`; 0xFF ⇒ 0x1F ⇒ hardware-envelope bit set) |
| +0x08 | word | Note duration counter (`-1` = infinite) |
| +0x0A | byte | Vibrato delay counter (0xFF = disabled) |
| +0x0B | byte | Vibrato half-period counter |
| +0x0C | word | Vibrato pitch offset accumulator (added to period) |
| +0x0E | word | Vibrato per-frame pitch delta |
| +0x0F | byte | (from instrument +7) |
| +0x10 | long | **Coroutine resume pointer** (ADSR state) |
| +0x14 | long | Instrument pointer |
| +0x18 | byte | Instrument flags; **bit7 = voice busy / SFX priority** |

### Instrument record (10 bytes, base 0x463CC)

| Off | Meaning |
|---|---|
| +0 | Attack increment (positive). *In hardware-envelope mode: PSG envelope shape (reg 13)* |
| +1 | Decay increment (negative) |
| +2 | Sustain level |
| +3 | Release increment (negative) |
| +4 | Peak level. *In hardware-envelope mode: envelope period low (reg 11)* |
| +5 | Vibrato delay → voice +0x0A |
| +6 | Vibrato half-period; bit7 set = one-shot sweep |
| +7 | → voice +0x0F |
| +8 | → voice +0x0E (pitch delta) |
| +9 | Flags: bit0 = AND tone mask, bit1 = AND noise mask, **bit2 = use hardware envelope** |

Default instrument at `0x463CC` = `7F FE 20 F8 6C FF 00 00 00 01`
(instant attack, decay −2 to sustain 32, release −8, peak 108, no vibrato, tone on).

**SFX descriptor (13 bytes, base 0x46426)** = a 10-byte instrument record plus
`+0x0A/+0x0B` = tone period (**little-endian**) and `+0x0C` = duration.

---

## 1. `blit_image_5120` — 0x44BEE

`blit_image_5120(A0 = source)` → void. Not sound-related; lives here by address only.

```c
// copies 5120 bytes (1280 longwords) to BOTH screen buffers
for (i = 0; i < 1280; i++) {
    uint32 v = *(uint32*)A0;
    *(uint32*)(0x78000 + i*4) = v;
    *(uint32*)(0x70000 + i*4) = v;
    A0 += 4;
}
```
Note the source is read once per iteration and stored twice (the 68K writes
`(A0)` then `(A0)+`). 5120 bytes = 32 scanlines of a 160-byte ST low-res line.

---

## 2. `reset_sound_chip` — 0x44C10

`reset_sound_chip()` → void. Full silence + engine reset.

```c
psg_select(7); psg_data_or(0x3F);      // ori.b #0x3F -> all tone+noise OFF
for (r in {0,1,2,3,4,5,6,11,12,13,8,9,10}) psg_write(r, 0);  // this exact order
*(word*)0x45096 = 0;                    // song-active flag
*(byte*)0x45002 = 0;                    // engine state = idle
*(byte*)0x45003 = 0;                    // SFX alternator
*(byte*)0x45004 = 0;                    // loop flag
*(byte*)0x45005 = 0;                    // track id
*(byte*)0xFFFFFA19 = 0;                 // MFP TACR: stop Timer A
*(byte*)0xFFFFFA1F = 0;                 // MFP TADR
```
Register 7 is set by read-modify-write (`ori`), not a plain store.

---

## 3. `play_music` — 0x44CCE

`play_music(D0.b = track index, D1.b = loop/variant flag)` → void. Saves D2-D7/A0-A6.

```c
A0 = 0x44F08 + (D0 & 0xFF) * 8;   // MusicTrackDescriptor
switch (A0->nTrack_type) {         // word at +0

case 1:                            // ---- sound effect ----
    if (*(byte*)0x45002 == 1) return;        // busy with tracked music
    if (*(byte*)0x45002 < 0)     return;     // busy with a sample
    if (D1 != 0) {
        slot = 2;                            // dedicated SFX voice
    } else {
        slot = *(byte*)0x45003;              // alternate voices 0/1
        if (++*(byte*)0x45003 == 2) *(byte*)0x45003 = 0;
    }
    A6 = 0x4543C + slot * 0x1A;              // voice state
    A5 = 0x46426 + A0->nParam_index * 13;    // SFX descriptor
    D7 = (A5[0x0B] << 8) | A5[0x0A];         // period, LITTLE-endian
    D6 = A5[0x0C];                           // duration
    trigger_channel_note();                  // A6, A5, D7, D6
    A6[0x18] |= 0x80;                        // mark voice busy (SFX priority)
    *(byte*)0x45096 = 0;
    *(byte*)0xFFFFFA19 = 0;                  // stop Timer A
    *(byte*)0x45002 = 0;
    return;

case 2:                            // ---- digi sample ----
    if (*(byte*)0x45002 == 1) return;
    if (*(byte*)0x45002 < 0)  return;
    *(byte*)0x45005 = D0;
    *(byte*)0x45004 = 0;
    A1 = 0x44FF0 + A0->nParam_index * 2;
    *(byte*)0x45000 = A1[0];                 // TACR prescaler
    *(byte*)0x45001 = A1[1];                 // TADR count
    *(long*)0x44FFC = A0->dwData_ptr;        // sample start
    *(byte*)0x45096 = 0;
    *(byte*)0x45002 = 2;                     // "start sample" -> music_tick acts
    return;

default:                           // ---- tracked music (type 0) ----
    *(byte*)0x45005 = D0;
    *(byte*)0x45004 = D1;                    // loop flag
    init_music_playback(A0->nParam_index);   // D0 = song index
    *(byte*)0xFFFFFA19 = 0;                  // stop Timer A (music runs on VBL)
    *(byte*)0x45002 = 1;
    return;
}
```

**Notes.** The two guard tests are `== 1` then a *signed* `>= 0` test, so state 0xFF
(sample playing) also blocks. Type 1 and 2 both refuse to interrupt music/samples;
type 0 never checks and always takes over.

---

## 4. `music_tick` — 0x44E0C

`music_tick()` → void. Call once per VBL. Saves all registers.

```c
if (*(byte*)0x45002 < 0) return;          // sample playing: touch nothing

step_all_channel_coroutines();            // envelopes/vibrato run every frame

if (*(byte*)0x45002 == 0) return;         // idle

if (*(byte*)0x45002 != 1) {               // == 2: start the queued sample
    *(byte*)0x45002 = 0xFF;
    psg_select(7); psg_data_or(0x3F);     // all tone+noise off
    for (r in {0,1,2,3,4,5,6,11,12,13}) psg_write(r, 0);
    // NOTE: regs 8,9,10 (volumes) deliberately NOT cleared - the sample IS volume
    *(long*)0x457C8 = *(long*)0x44FFC;    // working pointer := sample start
    *(byte*)0xFFFFFA19 = *(byte*)0x45000; // TACR  -> starts Timer A
    *(byte*)0xFFFFFA1F = *(byte*)0x45001; // TADR  -> sample rate
    return;
}

// state == 1: tracked music
if (*(word*)0x45096 == 0) {               // song finished
    if (*(byte*)0x45004 == 0) { reset_sound_chip(); return; }   // one-shot
    play_music(*(byte*)0x45005, 1);       // loop: restart
}
advance_music_channels();
```

---

## 5. `setup_timer_a` — 0x45006

Installs `timer_a_music_isr` at vector `0x134` (MFP Timer A) and enables the
interrupt in MFP IERA/IMRA (bit 5). See `re/functions.md`; unchanged this pass.

---

## 6. `timer_a_music_isr` — 0x45022 — **the digi-sample player**

Interrupt handler. Saves D0/A0/A1.

```c
A1 = 0x457C8;                 // working pointer slot
A0 = *(long*)A1;              // current sample byte pointer
D0 = *A0++;                   // fetch sample byte (zero-extended)

if (D0 == 0) {                // 0x00 terminates the sample
    if (*(byte*)0x45004 == 0) {           // no loop
        *(byte*)0xFFFFFA19 = 0;           // stop Timer A
        *(byte*)0x45002    = 0;           // engine idle
    } else {
        *(long*)0x457C8 = *(long*)0x44FFC;   // rewind to start
    }
    *(byte*)0xFFFFFA0F &= ~0x20;          // clear MFP ISRA bit 5 (Timer A)
    rte;
}

*(long*)A1 = A0;              // store advanced pointer; A1 now = 0x457CC
A0 = 0xFFFF8800;              // PSG register-select port
A1 += D0 * 4;                 // index the three volume tables

*(long*)A0 = *(long*)(A1);          // -> PSG reg 8  (volume A)
*(long*)A0 = *(long*)(A1 + 0x400);  // -> PSG reg 9  (volume B)
*(long*)A0 = *(long*)(A1 + 0x800);  // -> PSG reg 10 (volume C)

*(byte*)0xFFFFFA0F &= ~0x20;
rte;
```

**How samples work.** Each sample byte indexes three 256-entry longword tables which
are *pre-baked PSG register writes*:

- `0x457CC + b*4` → e.g. `0x08000E00` = "register 8 := 0x0E"
- `0x45BCC + b*4` → `0x09000D00` = "register 9 := 0x0D"
- `0x45FCC + b*4` → `0x0A000C00` = "register 10 := 0x0C"

So one 8-bit PCM sample is rendered as three simultaneous 4-bit channel volumes —
the classic ST trick for getting better-than-4-bit amplitude out of the YM2149.
Tone and noise are fully disabled first, so only the DC volume levels are heard.

**Playback rate** = `2457600 / (prescaler(TACR) * TADR)` Hz, where TACR selects the
MFP prescaler (1→/4, 2→/10, 3→/16, 4→/50, 5→/64, 6→/100, 7→/200). Both values come
from `0x44FF0[nParam_index*2]`, so rate is per-sample data, not code.

Samples are **0-terminated**, not length-counted.

---

## 7. `init_music_playback` — 0x45116

`init_music_playback(D0.w = song index)` → void.

```c
silence_all_channels();
D0 &= 0xFF;
A1 = 0x45098; A2 = 0x450BA; A3 = 0x450DC;    // the 3 music channels
A0 = 0x46932;                                 // song table base
A4 = A0 + D0 * 6;                             // 3 words per song

*(long*)(A1+0x02) = A0 + *(word*)A4++;        // ch0 order-list pointer
*(long*)(A2+0x02) = A0 + *(word*)A4++;        // ch1
*(long*)(A3+0x02) = A0 + *(word*)A4++;        // ch2
   // NB: each word is a byte OFFSET from 0x46932, not an absolute address

for (ch in {A1,A2,A3}) {
    ch[0x13] = 0;      // transpose
    ch[0x18] = 0;      // mixer nibble
    ch[0x14] = 1;      // force pattern fetch
    ch[0x12] = 1;      // repeat counter
    ch[0x15] = 1;      // duration counter
    *(long*)(ch+0x0E) = 0x463CC;   // default instrument
    ch[0x16] = 0xFF;   // channel active
}

// reset the instrument-slot table: 3 channels x 8 slots = 0,10,20,...,70
A0 = 0x450FD;
for (c = 0; c < 3; c++)
    for (v = 0; v < 80; v += 10) *A0++ = v;

*(byte*)0x45096 = 0xFF;      // song active
```

---

## 8. `advance_music_channels` — 0x451DA

`advance_music_channels()` → void. Called once per VBL while state == 1.

```c
if (*(byte*)0x45096 == 0) return;

A1 = 0x45098;
D0 = A1[0x16] | A1[0x22+0x16] | A1[0x44+0x16];   // OR the 3 channel-active flags
*(byte*)0x45096 = D0;

if (D0 == 0) {                                    // all channels ended
    if ((*(byte*)0x4543A & 0x3F) == 0x3F) return; // mixer fully muted -> truly done
    *(byte*)0x45096 = 1;                          // else keep alive to let notes ring
    return;
}

advance_channel_sequence(A4 = 0x45098, A6 = 0x4543C);
advance_channel_sequence(A4 = 0x450BA, A6 = 0x45456);
advance_channel_sequence(A4 = 0x450DC, A6 = 0x45470);   // tail-call, falls through
```

---

## 9. `advance_channel_sequence` — 0x4522C — **the sequencer core**

`advance_channel_sequence(A4 = music channel, A6 = voice)` → void.

```c
resolve_channel_note_period();      // envelope/vibrato pitch, writes voice +0x04

if (A4[0x14] != 0) {                // need a new pattern
    if (--A4[0x12] != 0) {          // repeat the current pattern
        *(long*)(A4+0x0A) = *(long*)(A4+0x06);
        A4[0x14] = 0;
        goto have_pattern;
    }
    A4[0x12] = 1;
    A0 = *(long*)(A4+0x02);         // order-list pointer

    for (;;) {                       // ---- ORDER LIST ----
        D0 = *A0++;
        if (D0 < 0x80) break;                       // pattern index -> play it
        if (D0 == 0xFE) { A4[0x13] = *A0++; continue; }   // set transpose
        if (D0 == 0xFF) { A4[0x16] = 0; return; }         // end of channel
        if (D0 < 0xC0) { A4[0x12] = D0 & 0x1F; continue; } // repeat count
        // 0xC0..0xFD: assign instrument to slot (D0 & 7)
        *(byte*)(0x450FD + (D0 & 7) + *(word*)A4) = *A0++;
        continue;
    }

    A4[0x14] = 0;
    *(long*)(A4+0x02) = A0;                          // save order position
    D0 = (int16)(int8)D0 * 2;
    D0 = *(word*)(0x46B00 + D0);                     // pattern offset table
    A0 = 0x4652A + D0;                               // pattern data
    *(long*)(A4+0x06) = A0;                          // remember for repeats
} else {
have_pattern:
    A0 = *(long*)(A4+0x0A);          // resume current pattern position
}

if (--A4[0x15] != 0) {               // note still sounding
    if (*A0 >= 0x80) process_sequence_command();     // A0 may advance
    *(long*)(A4+0x0A) = A0;
    return;
}

for (;;) {                            // ---- PATTERN ----
    if (*A0 >= 0x80) {
        process_sequence_command();
        if (A4[0x14] != 0) goto refetch_pattern;     // pattern ended (0xFF)
        continue;
    }
    D0 = *A0++;

    if (D0 == 0x7F) {                 // REST
        A4[0x15] = *A0++;             // duration
        *(long*)(A4+0x0A) = A0;
        return;
    }
    if (D0 == 0x7E) {                 // raw period, LITTLE-endian
        D6 = *A0++; D7 = *A0++;
        D7 = (D7 << 8) | D6;
    } else {                          // NOTE 0x00..0x7D
        D0 += A4[0x13];               // transpose
        D0 += 12;                     // +1 octave
        A4[0x17] = D0;                // current note
        D7 = *(word*)(0x45720 + D0*2);   // note_period_table[note]
    }

    A4[0x20] = A4[0x18] | 0xC0;       // envelope ctl: active + restart
    A4[0x15] = *A0++;                 // duration
    *(long*)(A4+0x0A) = A0;
    A5 = *(long*)(A4+0x0E);           // instrument

    if (A6[0x18] & 0x80) return;      // SFX owns this voice - drop the note
    trigger_channel_note();           // tail call (A6, A5, D7, D6)
    return;
}
```

`refetch_pattern` re-enters at the `--A4[0x12]` step.

---

## 10. `process_sequence_command` — 0x45342

`process_sequence_command(A0 = pattern ptr, A4 = channel)` → void; advances A0.

```c
D0 = *A0++;
if (D0 <= 0x88) {                     // 0x80..0x88: select instrument from slot
    D0 = (D0 & 7) + *(word*)A4;       // + channel's slot base (0/8/16)
    D0 = *(byte*)(0x450FD + D0);      // slot holds a byte offset
    *(long*)(A4+0x0E) = 0x463CC + D0; // instrument pointer
    return;
}
if (D0 == 0xFF) { A4[0x14] = 0xFF; return; }        // end of pattern
if (D0 <  0xC0) { A4[0x18] = D0 & 0x0F; return; }   // set mixer enable nibble
if (D0 == 0xC2) return;                             // no-op
A0 += 3;                                            // unknown 3-byte command: skip
```

The `<= 0x88` test is the *signed* comparison `cmp.b #-0x78; bgt`, so it selects the
byte range 0x80–0x88 exactly.

---

## 11. `resolve_channel_note_period` — 0x4538C

`resolve_channel_note_period(A4 = channel, A6 = voice)` → void. Runs the software
envelope that walks `0x46B66` and produces the tone period.

```c
if (A6[0x18] & 0x80) return;          // SFX priority
if ((A4[0x20] & 0x80) == 0) return;   // no active note
if ((A4[0x20] & 0x3F) == 0) { A4[0x20] &= ~0x80; return; }   // no envelope -> off

if (A4[0x20] & 0x40) goto restart;    // forced restart
if (--A4[0x1E] != 0) return;          // step delay
if (--A4[0x1F] == 0) goto restart;    // segment exhausted

A0 = *(long*)(A4+0x1A);               // envelope data
D0 = *A0++;
*(long*)(A4+0x1A) = A0;
A4[0x1E] = D0 & 7;                    // next delay
D0 = ((D0 >> 3) & 0x1F) + A4[0x17];   // note offset
goto emit;

restart:
    A0 = 0x46B66 + ((A4[0x20] << 3) & 0xFF);   // 8 bytes per envelope
    if (*A0 >= 0 && (A4[0x20] & 0x40) == 0) { A4[0x1F] = 1; return; }
    A4[0x20] &= ~0x40;
    A4[0x1E] = (*A0 >> 3) & 7;         // delay
    A4[0x1F] = (*A0++ & 7) + 1;        // repeat count
    *(long*)(A4+0x1A) = A0;
    D0 = A4[0x17];                     // base note

emit:
    *(word*)(A6+0x04) = *(word*)(0x45720 + D0*2);   // voice period
```

---

## 12. `trigger_channel_note` — 0x4548A

`trigger_channel_note(A6 = voice, A5 = instrument, D7.w = period, D6.w = duration)`
→ void. Runs with interrupts masked (`ori #0x700,SR` … `move (SP)+,SR`).

```c
*(long*)(A6+0x14) = A5;          // instrument
*(word*)(A6+0x04) = D7;          // period
*(word*)(A6+0x08) = D6;          // duration (-1 = infinite)
A6[0x0A] = A5[5];                // vibrato delay
D0 = A5[6] & 0x7F;
A6[0x0B] = (D0 >> 1) + (D0 & 1); // half-period, rounded up
A6[0x0F] = A5[7];
*(word*)(A6+0x0E) = A5[8];       // pitch delta
*(word*)(A6+0x0C) = 0;           // clear vibrato accumulator

A4 = 0x4543A;                    // mixer shadow
D0 = *A4 | A6[0x02];
A6[0x18] = A5[9];                // instrument flags
if (A6[0x18] & 1) D0 &= A6[0x00];   // enable tone
if (A6[0x18] & 2) D0 &= A6[0x01];   // enable noise
*A4 = D0;

if ((A6[0x18] & 4) == 0) {       // software envelope
    *(long*)(A6+0x10) = 0x4566E; // coroutine -> STATE A (attack)
    return;
}
// hardware envelope
psg_write(13, A5[0]);            // envelope shape
psg_write(11, A5[4]);            // envelope period low
psg_write(12, 0);                // envelope period high
A6[0x06] = 0xFF;                 // volume 0xFF>>3 = 0x1F -> PSG "use envelope" bit
```

---

## 13. `silence_all_channels` — 0x45528

```c
*(byte*)0x4543A |= 0x3F;          // mixer: all tone+noise off
psg_write(7,  *(byte*)0x4543A);
psg_write(8,  0); psg_write(9, 0); psg_write(10, 0);
*(byte*)(0x4543C+0x18) = 0;       // clear all three voice-busy flags
*(byte*)(0x45456+0x18) = 0;
*(byte*)(0x45470+0x18) = 0;
```

---

## 14. `step_all_channel_coroutines` — 0x4556E

`step_all_channel_coroutines()` → void. Runs the three voice coroutines, then flushes
the whole PSG state to the chip.

```c
A4 = 0x4543A;
channel_coroutine_dispatch(A6 = 0x4543C);
channel_coroutine_dispatch(A6 = 0x45456);
channel_coroutine_dispatch(A6 = 0x45470);

psg_write(7, *A4);                       // mixer

D1 = 0;                                   // noise-period source
for (v = 0, regbase = 0; v < 3; v++, regbase += 2) {
    A6 = 0x4543C + v*0x1A;
    D0 = *(word*)(A6+0x04) + *(word*)(A6+0x0C);   // period + vibrato offset
    if (A6[0x18] & 2) D1 = (byte)D0;              // this voice drives noise
    psg_write(regbase + 0, D0 & 0xFF);            // period low
    psg_write(regbase + 1, (D0 >> 8) & 0xFF);     // period high
}
psg_write(6, D1 >> 3);                    // noise period

psg_write(8,  *(byte*)(0x4543C+0x06) >> 3);   // volumes, 8-bit -> 5-bit
psg_write(9,  *(byte*)(0x45456+0x06) >> 3);
psg_write(10, *(byte*)(0x45470+0x06) >> 3);
```

A volume byte of 0xFF becomes 0x1F, which sets PSG bit 4 = "use hardware envelope".

---

## 15. `channel_coroutine_dispatch` — 0x45636 — **the ADSR state machine**

`channel_coroutine_dispatch(A6 = voice, A4 = mixer shadow)` → void.

This is hand-written coroutine code: `+0x10` holds a **resume address**, and each
state rewrites it before returning. A C port must model it as an explicit enum.

```c
D0 = *A4 & A6[0x02];
if (D0 == A6[0x02]) return;        // voice's mixer bits still all set -> silent

A5 = *(long*)(A6+0x14);            // instrument
if (*(word*)(A6+0x08) != 0 && *(word*)(A6+0x08) != -1)
    *(word*)(A6+0x08) -= 1;        // duration countdown (-1 = infinite)

channel_coroutine_state_c();       // vibrato / pitch modulation

if (A6[0x18] & 4) {                // hardware-envelope mode
    if (*(word*)(A6+0x08) != 0) return;
    goto RELEASE_END;
}
goto *(void**)(A6+0x10);           // resume ADSR state
```

### STATE A — attack, entry `0x4566E`
```c
A6[0x06] += A5[0];                       // volume += attack
if ((int8)A6[0x06] < 0) goto clampA;     // overflowed past 0x7F
if (A5[4] > (int8)A6[0x06]) return;      // not at peak yet
clampA:
A6[0x06] = A5[4];                        // clamp to peak
*(long*)(A6+0x10) = 0x45690;             // -> STATE B
```

### STATE B — decay, entry `0x45690`
```c
A6[0x06] += A5[1];                       // negative increment
if ((int8)A6[0x06] < 0) goto clampB;
if (A5[2] < (int8)A6[0x06]) return;      // still above sustain
clampB:
A6[0x06] = A5[2];                        // clamp to sustain
*(long*)(A6+0x10) = 0x456B4;             // -> STATE C
```

### STATE C — sustain, entry `0x456B4`
```c
if (*(word*)(A6+0x08) != 0) return;      // hold until duration expires
*(long*)(A6+0x10) = 0x456C4;             // -> STATE D
```

### STATE D — release, entry `0x456C4`
```c
A6[0x06] += A5[3];                       // negative increment
if ((int8)A6[0x06] >= 0) return;         // still fading
RELEASE_END:
A6[0x06] = 0;                            // silent
*A4 |= A6[0x02];                         // re-disable in mixer
A6[0x18] &= ~0x80;                       // voice no longer busy
```

The `lea (0x8,PC),A0` at the end of each state resolves to *the next state's entry*
(instruction address + 2 + 8), which is how the chain advances.

---

## 16. `channel_coroutine_state_c` — 0x456E8 — vibrato / pitch sweep

`channel_coroutine_state_c(A6 = voice, A5 = instrument)` → void.

```c
D0 = A6[0x0A];
if (D0 != 0) {
    if (D0 == 0xFF) return;              // vibrato disabled/finished
    if (--A6[0x0A] != 0) return;         // still in initial delay
}
*(word*)(A6+0x0C) += *(word*)(A6+0x0E);  // accumulate pitch offset
if (--A6[0x0B] != 0) return;             // half-period not elapsed

D0 = A5[6];                              // vibrato half-period
if (D0 == 0) return;
if ((int8)D0 >= 0) {                     // continuous: reverse direction
    A6[0x0B] = D0;
    *(word*)(A6+0x0E) = -*(word*)(A6+0x0E);
} else {
    A6[0x0A] = 0xFF;                     // bit7 set = one-shot sweep, stop
}
```

---

## 17. Sequence data format — **opcode tables**

Two distinct streams. Both are byte streams where **bit 7 distinguishes data from
command**.

### 17.1 Order list (per channel; pointer at channel +0x02)

| Byte | Operands | Effect |
|---|---|---|
| `0x00`–`0x7F` | — | **Play pattern N.** Ends the order-list scan for this fetch |
| `0x80`–`0xBF` | — | Set pattern **repeat count** = `b & 0x1F` |
| `0xC0`–`0xFD` | 1 byte | Assign instrument to **slot `b & 7`**: `slot_table[chan_base + (b&7)] = next_byte` (a byte offset into the instrument table) |
| `0xFE` | 1 byte | Set **transpose** = next byte |
| `0xFF` | — | **End of channel** (clears channel-active flag) |

### 17.2 Pattern stream (pointer at channel +0x0A)

| Byte | Operands | Effect |
|---|---|---|
| `0x00`–`0x7D` | 1 byte (duration) | **Note.** period = `note_period_table[b + transpose + 12]` |
| `0x7E` | 2 bytes + 1 duration | **Raw period**, little-endian (`lo, hi`) |
| `0x7F` | 1 byte | **Rest** for that many ticks |
| `0x80`–`0x88` | — | **Select instrument** from slot `b & 7` |
| `0x89`–`0xBF` | — | **Set mixer nibble** = `b & 0x0F` (tone/noise enables) |
| `0xC0`,`0xC1`,`0xC3`–`0xFE` | 3 bytes | Unknown command — **skipped** (`A0 += 3`) |
| `0xC2` | — | No-op |
| `0xFF` | — | **End of pattern** |

### 17.3 Validation (hand-decoded, no desync)

**Song 0, channel 0 order list** at `0x46968`:
`00 88 04 FE 05 00 88 04 FE 00 84 04 FE 01 84 04 FE 02 84 04 FE 03 84 04 FE 1C 08 FF`

→ pattern 0 · rpt 8 × pattern 4 · transpose 5, pattern 0 · rpt 8 × pattern 4 ·
transpose 0, rpt 4 × pattern 4 · transpose 1, rpt 4 × pattern 4 · transpose 2,
rpt 4 × pattern 4 · transpose 3, rpt 4 × pattern 4 · transpose 0x1C, pattern 8 ·
**end**. Parses cleanly to the `0xFF`.

**Pattern 0** at `0x4652A`:
`80 17 10 1A 10 1E 10 23 10 26 10 2A 10 2F 10 32 10 FF`

→ select instrument slot 0; then eight notes (23, 26, 30, 35, 38, 42, 47, 50) each
with duration 0x10; then end-of-pattern. **Exactly 18 bytes**, and the pattern offset
table at `0x46B00` gives pattern 1 at offset `0x0012` = 18 — the decode length matches
the table stride exactly, confirming the format.

---

## 18. Notes / uncertainties

- **Pattern opcodes `0xC0`/`0xC1`/`0xC3`–`0xFE` are skipped as 3-byte commands** but
  never interpreted. Either they are unused in shipped data or they carry effects the
  engine ignores. No occurrence was found in the two streams decoded here.
  **Needs dynamic verification** (or a full scan of all pattern data) to confirm they
  never appear.
- The order-list transpose `0x1C` (28) at the end of song 0 channel 0 is unusually
  large. It decodes consistently, but the musical result is unverified.
  **Needs dynamic verification.**
- `(A6+0x0F)` is loaded from instrument `+7` by `trigger_channel_note` but no reader
  was found in this address range. Possibly dead, possibly consumed elsewhere.
- The exact MFP prescaler encoding for TACR is standard 68901 behaviour, not read out
  of this code; the rate formula given assumes it.
- `music_tick` tests `0x45096` as a **word** while every writer touches only the byte
  at `0x45096`. The adjacent byte `0x45097` is therefore read as part of the test. It
  appears to be always zero, but this is an aliasing hazard worth preserving in a port.
- Register 7 is always updated read-modify-write through the `0x4543A` shadow; a port
  must keep that shadow rather than computing the mixer from scratch.
