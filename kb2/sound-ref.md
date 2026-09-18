# Rick Dangerous 2 (Atari ST) — sound engine reference

Canonical reference for the SNDH extraction. Replaces the former `sound.md`
(24-pass narrative log, deleted: it contained mutually contradictory
"confirmed" facts and several misread addresses — see §8).

> **STATUS: COMPLETE.** `build_sndh.py` → `rick2_sfx.sndh` (98870 bytes,
> 92 subtunes) was confirmed working by listening test on 2026-09-18: all
> three playback types correct, including type-2 digitised samples. The
> architecture that works is in §6; the engine is byte-identical to the
> original except for **4 bytes at one site** (§6.4).

Every fact below was read from the live Ghidra program `prg2-ram.bin`
(`/prg2-ram.bin.0`, 68000:BE:32, image base 0, 1 MiB) on 2026-09-18, with the
exact address recorded so it can be re-checked in one call. Disassembly is
Ghidra's; data-table decoding is from the program image, which was verified to
map 1:1 onto Ghidra addresses (file offset == address) at four independent
points.

## 1. Hardware and location

- Plain **YM2149 PSG** only: `$ffff8800` = register select, `$ffff8802` = data.
  No STe DMA sound anywhere.
- All sound code and data live in `RICK2.PRG` (the main program image). The
  `RICK_0N.HNK` level archives carry no audio.
- Sound region: **`$19e96` – `$31eb0`**. Code and tables occupy `$19e96`–`$1c6aa`;
  `$1c6aa`–`$31eb0` is raw type-2 stream data.
- Two independent interrupt sources drive it:
  - **VBL, 50 Hz** → `FUN_0001a866` (`TICK`), the per-tick driver. Installed on
    CPU vector `$70`; the ISR at `$1902e` just calls it.
  - **MFP Timer A, 4915.2 Hz** → the streamer at `$1a994`. Enabled only while a
    type-2 sound plays.

## 2. Dispatch table — `$1c376`, 8 bytes/entry, **92 entries (ids 0-91)**

| offset | size | field |
|---|---|---|
| +0 | word | `type` (0, 1 or 2) |
| +2 | word | `param` |
| +4 | long | `ptr` — type-2 only: absolute address of the PSG stream. **0 for all type-0 and type-1 entries.** For type-1 its *low word* is read separately as a channel-mode selector (§4). |

Full decode (all 736 bytes read at once):

- **type 0 — 10 entries**, ids 0-9. `param` = 0,1,2,3,5,6,7,8,9,10 (param 4 is
  never used — a genuine table gap, not an error).
- **type 1 — 45 entries**, id 45 and ids 48-91. `param` range 0-27.
- **type 2 — 37 entries**, ids 10-44, 46, 47. `param == 0` for every one, so all
  37 share timer preset 0. Two genuine duplicate pointer pairs: id 34 ≡ id 16
  (`$209f0`) and id 35 ≡ id 19 (`$2280a`).

Entry 92 does not exist: byte offset 736 is the first byte of id 10's stream
data (`$1c656`). Reading it as an entry yields `type=0x4b77`, which is how the
"93 subtunes" claim arose.

## 3. Dispatcher — `FUN_0001a6aa` (`$1a6aa`), D0 = id, D1 = param

```
$1a6aa  movem.l {D2-D7,A0-A6},-(SP)
$1a6ae  tst.w  ($1a5ce).l          ; debug id-remap flag; 0 in the image
$1a6b4  beq.b  $1a6c0
$1a6b6  cmp.w  #9,D0w              ; if flag set and id > 9: id += 0x29
$1a6bc  addi.b #0x29,D0b
$1a6c6  lea    ($1c376).l,A0 ; adda.l D2(=id*8),A0
$1a6ce  cmpi.w #1,(A0) ; beq -> $1a70a     (type 1)
$1a6d6  cmpi.w #2,(A0) ; beq -> $1a7fa     (type 2)
        ...fall through...                 (type 0)
```

**Type 0** (`$1a6de`) — no gate of any kind:
`a977=id; a976=D1; D0=entry.param; jsr $1aa88; clr.b (TACR); a974=1`.

**Type 1** (`$1a70a`) — gated:
`if ($3efb6 != 0) return;  if (a974 == 1) return;` then, since `ptr`'s low word
is 0 for every real entry, always the round-robin path at `$1a758`:
`if (a974 != 0) return;` → rotate channel cursor in `a975` (§4) →
`bsr $1adf8` → `bset #7,(0x18,A6); clr.b (aa08); clr.b (TACR); a974=0`.

**Type 2** (`$1a7fa`) — gated:
`if ($3efb6 != 0) return;  if (a974 != 0 && (id > a977 || D1 != 0)) return;`
then `a977=id; a976=0; a972/a973 = ($1a962)[param*2]; a96e=entry.ptr;
clr.b (aa08); a974=2`.

**`$3efb6` is outside the sound region** — a demo-mode flag, 0 during normal
gameplay. It must be made to read 0 in a standalone build (§6).

## 4. State cells and channel structs

| address | meaning |
|---|---|
| `$1a5ce` | word; debug id-remap flag. **0 in the image**; only ever set by a hidden scancode-`$1F` hotkey. No action needed. |
| `$1a962` | byte pairs `[TACR,TADR]` indexed by `param*2`. Preset 0 = **`06 05`**. |
| `$1a96e` | long; pending type-2 stream pointer, set at dispatch. |
| `$1a972`/`$1a973` | bytes; Timer-A control/data for the pending sound. |
| `$1a974` | byte; master state. `0`=idle, `1`=type-0 playing, `2`=type-2 armed-pending, `-1`=type-2 streaming (or fully stopped). **`1` in the image — must be cleared at init or every gate rejects.** |
| `$1a975` | byte; bits 0-1 round-robin channel cursor, bits 4-6 per-channel busy. Carry-over state by design. |
| `$1a976` | byte; type-2 loop flag. Dispatcher always sets 0 → one-shot. |
| `$1a977` | byte; currently-playing id (used for type-2 priority compare). |
| `$1aa08` | word; type-0 "channels still active" master flag. |
| `$1b126` | long; **live type-2 stream cursor**. `0` in the image. |
| `$1adaa` | type-1 channel structs, **stride 26, 3 channels** (`$1adaa`, `$1adc4`, `$1adde`). |
| `$1c054` | type-0 per-`param` channel-script table, stride 6 (3 words, each a relative offset from `$1c054`). |
| `$1c20a` | type-1 instrument records, **stride 13, indexed by `param`** (28 records, `$1c20a`-`$1c376`, ending exactly where the dispatch table begins). |

Channel-struct fields confirmed by reading `$1adaa`:
`[2]` = this channel's PSG mixer mask — **`0x09`/`0x12`/`0x24`** for A/B/C, i.e.
`bit0|bit3`, `bit1|bit4`, `bit2|bit5` = that channel's tone-disable and
noise-disable bits. `[0x10]` = long, self-modifying ramp-state pointer (the
image holds `$1affe`, ramp state 2). `[0x14]` = long, instrument pointer
(`$1c1c4`/`$1c1ce`). Both are absolute and need relocation.

## 5. The three playback types

### Type 0 (ids 0-9) — bytecode VM, 50 Hz
`$1aa88` calls silence-all, then indexes `$1c054` by `param` for three
per-channel bytecode script starts, initialises three 34-byte channel structs,
and sets `aa08 = 0xff`. `TICK` then steps the VM (`$1ab4c` → `$1ab9e` → …)
once per 50 Hz tick until all three channels hit opcode `0xff`, at which point
`aa08` reaches 0 and `TICK` takes the `$1a5d0` full-stop branch.

Opcode grammar (`FUN_0001ab9e`, single unified parser — the "two interpreters"
of early passes was a mislabelling):

| opcode | meaning |
|---|---|
| `$00-$7d` | note index: add transpose (`+0x13`), double, index the period LUT |
| `$7e` | explicit 16-bit period follows |
| `$7f` | set reload/duration from next byte |
| `$80-$bf` (`&0x1f`) | set loop/repeat counter |
| `$c0-$fd` (`&7`) | index instrument/waveform selector table |
| `$fe` | set duration-override byte from next byte |
| `$ff` | **stop this channel** |

### Type 1 (id 45, ids 48-91) — shared 3-voice carrier, 50 Hz
`param` selects a 13-byte instrument record at `$1c20a + param*13`; the channel
is chosen by round-robin on `a975` (cursor cycles 0→1→2→1→2…, channel 0 only on
the first trigger after a reset). `$1adf8` arms the chosen channel; the per-tick
flush `$1aedc` steps each channel through a 4-state ramp machine via the
self-modifying `[0x10]` pointer, terminating at `$1b03c`:
`clr.b (6,A6); or.b (2,A6),(A4)` — i.e. it ORs the channel's mixer mask into the
shared mixer shadow, muting it. `a974` is deliberately left at **0**, which is
what keeps the flush running so termination can happen. Three physical voices
serve all 45 cues, so rapid triggers legitimately steal each other's channels —
original behaviour, not a defect.

### Type 2 (ids 10-44, 46, 47) — 3-channel volume DAC, 4915.2 Hz

**Rate, derived exactly.** Preset 0 at `$1a962` is `TACR=6, TADR=5`. MFP Timer A
in delay mode: 2.4576 MHz input, control code 6 = ÷100, data = countdown 5.
`2457600 / (100*5)` = **4915.2 Hz exactly**.

**Arm block** (`$1a8c2`, runs once on the first `TICK` after a type-2 trigger):
```
a974 = -1                                  ; self-disables the 50 Hz flush
reg7 |= 0x3f                                ; ALL tone AND noise disabled, 3 channels
regs 0,1,2,3,4,5,6 = 0                      ; tone periods + noise period
regs 11,12,13 = 0                           ; envelope
$1b126 = a96e                               ; arm the live cursor
TACR = a972 ; TADR = a973                   ; program the real tempo
```
Registers 8/9/10 are deliberately **not** touched — they are the output.

**Streamer** (`$1a994`, one invocation = one stream byte):
```
A1 = $1b126 ; A0 = (A1)
D0 = (A0)+ ; if D0 == 0 -> stop path
(A1)+ = A0                                  ; commit cursor
A1 += D0*4
(A1)      -> $ffff8800                       ; long write = select reg + write data
(A1+$400) -> $ffff8800
(A1+$800) -> $ffff8800
```
The three 256-entry longword tables live at **`$1b12a`, `$1b52a`, `$1b92a`**.
Each entry is `[reg,00,val,00]`; a single `move.l` to `$ffff8800` puts the
selector on `$8800` and the value on `$8802`. Table 1 always selects register 8,
table 2 register 9, table 3 register 10 — so one stream byte sets all three
channel volumes. With tone and noise disabled by the arm block, the volume
registers act as a crude 3-way DAC: **this is digitised sample playback**, and
`reg7 = 0x3f` is a requirement of the technique, not a bug.

Stop path (byte == 0): if `a976 == 0` (always) → `TACR = 0; a974 = 0`. Else
reload the cursor from `a96e` and loop.

**Stream extents, verified.** Scanning each pointer forward to its first `$00`
byte: all 37 terminators land 0-1 bytes before the next stream's start pointer —
37 independent confirmations of the table, the format and the terminator
convention. The highest, id 47, ends at **`$31eb0`**, so the region needs no
safety margin.

## 6. Requirements for a standalone SNDH build

1. **Subtune numbering is 1-based.** Confirmed from a genuine working file:
   `Ben Daglish - Rick Dangerous 2.sndh`'s init begins
   `lea (-0x3a,PC),A0 ; subq.w #1,D0`. So `init(D0)` must use `id = D0 - 1`.
2. **Relocation.** The code uses absolute addressing for its own state and
   tables, so the blob must be self-relocated at load. Fixup set derived
   mechanically: every even offset in `$19e96`-`$1c6aa` holding a longword whose
   value falls in that same range (**78 hits, 34 distinct targets, all
   recognisable state cells / table bases / code entries**), plus the 37 type-2
   `ptr` fields structurally (`$1c376 + id*8 + 4`), minus the single overlap
   (id 10's pointer, whose value is inside the code region) = **114**.
3. **Clear `$1a974`** before each dispatch: it is `1` in the image and all
   type-1/type-2 gates require 0. This reproduces the precondition the game has
   whenever a sound actually triggers.
4. **Make `$3efb6` read 0.** It is outside the region. Redirect the two
   `tst.w ($3efb6).l` address fields (at `$1a70c` and `$1a7fc`) to a
   guaranteed-zero cell inside the blob, so control flow is unchanged.
5. **The two clocks must stay two clocks — and only one of them may come from
   the player.** This is the single most important lesson of the whole task.
   - `play()` is declared **`TC50`** and calls `TICK` (`$1a866`) exactly once
     per tick. Nothing else.
   - The type-2 streamer runs off a **real MFP Timer-A interrupt**, installed by
     the file itself: `init()` calls the engine's own `FUN_0001a978` (`$1a978`),
     which writes vector `$134` and sets bit 5 of IERA (`$fffffa07`) and IMRA
     (`$fffffa13`). The arm block already programs TACR/TADR, so the rate is the
     game's own 4915.2 Hz with no arithmetic on our side. `$1a978` has no callers
     in the game because the original called it from boot code outside the sound
     region — `init()` supplies that one missing host action.

   Two approaches were tried and **both fail**, for instructive reasons:
   - *Bursting the streamer 98× inside a 50 Hz `play()`*: the volume registers
     are a DAC, so they retain only the last value of each burst. The sample is
     decimated to 50 Hz → clicks and hiss.
   - *Declaring the fast rate as the SNDH tick (`TC4915`) and dividing down to
     50 Hz in software*: **real players do not honour a tick that high** (a
     4-digit value may even be read as `TC49`). `TICK` then ran roughly once
     every two seconds, which starves the one shared driver and so breaks all
     three types identically — every subtune reduced to a single click from
     `init()`'s silence-all. Empirical, from a listening test.

   Timer A is available precisely *because* we declare `TC50`: the player takes
   Timer C, and the engine never touches TCDCR/TCDR. Note the converse trap —
   `play()` must **not** be driven by Timer A, because the streamer's stop path
   executes `clr.b ($fffffa19)` and would kill its own clock.
6. **`exit()` must stop and mask Timer A** (`clr.b` TACR, `bclr #5` on IERA and
   IMRA) before anything else. The ISR lives inside the loaded file, so it has
   to be unable to fire once the player unloads it.
7. **Do not reset `a975` or `channel[6]`.** `$1adf8` never resets the envelope
   accumulator, and the ramp machine leaves it where the previous note ended, so
   carry-over is the original design. Resetting them is not more faithful.
8. **The complete deviation list is one site, 4 bytes.** Only the two
   `tst.w ($3efb6).l` operand fields (item 4). Everything else the engine does —
   including the `0x3f` mixer write, the round-robin channel stealing, the
   one-shot stop path and all three `RTE` exits of the streamer — is left
   exactly as shipped in 1990. If a future change needs a fifth patched byte,
   that is a signal to re-read the disassembly, not to patch.

## 7. id → game event (from call sites into `$1a6aa`)

Useful for naming subtunes. Note these are **ids**; subtune number = id + 1.

| id | event | | id | event |
|---|---|---|---|---|
| 0 | level-start fanfare (only site passing D1=1) | | 23 | spawn/appear |
| 1 | timed-effect end/impact | | 24 | object collision |
| 2 | level transition / door | | 25 | hard landing (map 3) |
| 3 | checkpoint / flag | | 26 | hard landing (map 5) |
| 9 | HUD/counter tick | | 34 | countdown-timer expiry |
| 10 | **player death** | | 45 | **jump** |
| 11 | respawn / bounce onscreen | | 48 | wall contact / scroll cue |
| 16 | scroll/transition complete | | 49 | footstep |
| 17 | start timed/rolling effect | | 50 | climb/airborne step, falling object |
| 19 | generic impact / actor destroy | | | |
| 20, 21 | actor AI triggers | | | |

Three call sites take the id from actor script data rather than an immediate, so
a few more ids are reachable in-game than are listed here.

## 8. Corrections to the deleted `sound.md`

Recorded because several of these were used as the basis for "fixes" that
shipped, and one caused a total regression.

| claim | reality |
|---|---|
| type-1 channel structs at `$1adc2` | **`$1adaa`**. `lea (0x5f2,PC),A6` at `$1a7b6` has its extension word at `$1a7b8`, so EA = `$1a7b8 + 0x5f2` = `$1adaa`. The same formula gives `$1c20a` for the instrument table, which matches the known-good value. Passes 23/24's envelope-accumulator clears were therefore aimed at three unrelated bytes, and pass 17's "static mixer masks `0xFD/0xFB/0x40`" were bytes 24,25 of one struct plus byte 0 of the next. The real masks are `0x09/0x12/0x24`. |
| id 91 has `param=20`, so ids 50 and 91 differ (pass 23, "central discovery") | **id 91 has `param=1`**, identical to id 50. `$1c636` is entry **88**, not 91; entry 91 is at `$1c64e`. Pass 23 refuted a correct pass-22 fact with a misread byte and shipped a fix based on it. |
| type-2 mixer must be `0x07` (noise on); type-2 is "authentic noise percussion" (passes 14, 15, 19) | The original's `0x3f` (everything disabled) is correct and required — the volume registers are the DAC. `0x07` unmutes the noise generator, which *is* the hiss; mirroring it into the shared mixer shadow (pass 15) also leaks noise into type-0/1 playback. |
| streamer table storage is PC-relative at `$1a126`, forcing the low bound to `$19e96` (pass 3) | `lea (0x78c,PC),A1` at `$1a998` resolves to **`$1b126`**. The stated reason for widening the extraction was a misread address (the low bound is still needed, but for `$1a4fa`-`$1a5ce` state and `$1a5d0`). |
| type-2 data ends somewhere below a `$32400` safety margin (pass 3) | Ends exactly at **`$31eb0`**, by terminator scan. |
| 93 subtunes (pass 3) / 92 with pass-through `D0` | 92 entries, and subtunes are 1-based, so `id = D0-1`. Every build since pass 1 was off by one, leaving id 0 unreachable and reading past the table for the last subtune. |
| `$1a978` (Timer-A vector install) must be called (pass 5) | **Pass 5 was right, and my own first build was wrong.** I initially recorded this as "unnecessary and undesirable — a standalone build pumps the streamer from `play()`". That build reduced every subtune to a click. Installing the real Timer-A ISR is exactly right and is what makes type-2 work; pass 5's error was not the install but pumping the streamer from `play()` *as well*, at the wrong rate. Corrected in §6.5. |
| type-2 is "authentic noise percussion" / "amplitude-modulated hiss is inherent to the technique" (passes 15, 19) | Wrong, and it misdiagnosed the project's own bug as a property of the hardware. With `reg7 = 0x3f` and a true 4915.2 Hz tick the streams are clean digitised samples — confirmed by listening test. |
