# Rick Dangerous 2 — rendering, scrolling, frame pacing (transcribed)

Written 2026-09-23 to close `port-rd2.md` §5.C/§5.D and the render callees found by the full call-site sweep. Read
instruction by instruction in Ghidra (`prg2-ram.bin`) — the plain blitter (`$19e96`–`$1a4f8`, all 521 instructions) and
the masked blitter (`$1952c`–`$19e94`, all 769 instructions) were read in full, not sampled. No decompiler.
Formats and addresses of the assets are in `graphics.md`; this file is the **code**. Screen coordinates below are
pixels of the 320×200 screen; "group" = a 16-px column group (screen group g covers x `16g .. 16g+15`).

## 0. Buffers

| buffer | layout | role |
|---|---|---|
| `[$18eda]` / `[$18ede]` | two 32000-byte ST screens (`$70000`/`$78000`), 160 B/line, 4 word-interleaved planes | **displayed** / **draw target**; `$19234` swaps them |
| `$68000` (gameplay) | 256 lines × 128 B (256 px, 4 planes), **circular**, line index `& $ff` | background bitmap; screen line 8 shows bitmap line `[$1662e]` |
| `$65800` | 256 lines × 40 B (1 bit/px, 320 px wide; the playfield starts at byte 4 = x 32), circular like `$68000` | tile mask for the masked blitter |
| `$68000` (scenes / transitions) | a 160-B/line screen-layout image (32000 B) | off-screen picture; same address, different use |
| `$65300` | 40 rows × 32 tile ids | tile window; window row 0 = world tile row `[$16462] >> 3` |

## 1. Frame pacing and buffer flip

- VBL ISR `$1902e`: `[$19232] += 1; jsr $1a866 (sound TICK); rte`. Nothing else.
- `$19216` "wait + flip": wait while `[$18ed8] - 1 > [$19232]`; then `$19234`. Does **not** clear the counter.
- `$191e6` "wait": `t0 = [$19232]`; wait until `[$19232] >= [$18ed8] - 1` **and** `[$19232] != t0`; then `[$19232] = 0`.
- `$19234` flip: toggle bit 7 of bytes `$18edc` and `$18ee0` (bit 15 of both screen pointers), write `$18edb`/`$18edc` to
  `$ff8201`/`$ff8203`. After the flip `[$18eda]` is displayed and `[$18ede]` is the next draw target.
- With `[$18ed8] = 2`, one game frame = `$19216` (counter ≥ 1) + `$191e6` (counter changed again) = at least 2 VBLs.
  With `[$18ed8] = 1` (transition slide) each step is 1 VBL.

## 2. Palette fades

- `$19134` fade-in, 8 steps, each step starts with `$191e6`: for each of the 16 colours `c` (target `[$18ee2]`, hardware
  `$ff8240`): `if (t & $700) > R: hw += $100`; `if (t & $70) > G: hw += $10`; `if (t & 7) > B: hw += 1`; with thresholds
  `R = $700 - $100k`, `G = $70 - $10k`, `B = 7 - k` for step `k = 0..7` (the blue threshold is the `dbf` counter itself).
  Starting from black, each component reaches its target at the last step.
- `$1919e` fade-out, 8 steps, each step `$191e6` then each colour component `> 0` is decremented by one unit.
- `$19116` (A0 = palette): `[$18ee2] = A0`; copy 16 words to `$ff8240`. `$19106` = `$19116($18ee6)`.

## 3. Sprites

**Walk** (`$170ce` = `$170d4` then `$170f2`, A6 = first record, A1 = destination screen base): records in order until a
negative `+0`; `$170d4` draws those with `+0 != 0` and `+14 == 0`; `$170f2` those with `+0 != 0` and `+14 != 0`
(clearing `+14` first). Callers: `$170b6` (chain `$167a2`, into `[$18ede]`), `$1709e` (chain `$167a2`, into `$68000`
as a screen-layout image — transitions), `$17086` (scene sprites `$16d7c`, into `[$18ede]`).

**Entry `$17116`**: `id = +e`; `$fe` → nothing. Bank: `id >= $c0` → `$5fe00` (id−`$c0`); `>= $80` → `$3a844` (id−`$80`);
`>= $40` → `$5aa00` (id−`$40`); else `$37274`; frame = bank + 336·idx. Screen position **(x + 32, y − $38)**;
`+12 != 0` → masked blitter `$1952c`, else plain `$19e96`.

**Both blitters, common entry** (plain `$19e96`, masked `$1952c`):
```
if +10 < 0: +10 = 0 ; if bit 7 of byte $18edc is set: return      # hidden on alternate frames (flicker)
sy -= [$16462] & 7                                                  # the fine vertical scroll
if sy <= -13 or sy >= $c8 or sx < 0 or sx >= $120: return          # (+10 is NOT cleared on this path)
rows: sy < 8   -> skip (8 - sy) top rows, rows = 13 + sy, sy = 8
      sy > $b3 -> rows = $c8 - sy
      else     -> rows = 21
masked only: mask row = ([$1662e] - 8 + sy) & $ff, advanced by 1 per row with wrap at 256 lines
```
**Horizontal clipping** — the routing by group `g = sx >> 4` and shift `s = sx & 15`, read path by path in both blitters:
pixels are written **only in screen groups 2..17**, i.e. screen x ∈ [32, 288). Groups 0, 1 (x < 32) and 18, 19 (x ≥ 288)
are never written. (g = 0: only the part landing in group 2; g = 1: groups 2–3 only; g = 16: groups 16–17; g = 17: group 17.)

**Pixel rule** per sprite row (planes p0..p3 of the 32-px row, `opaque = p0|p1|p2|p3`):
- plain: `dest = (dest & ~opaque) | sprite` — colour 0 is transparent.
- masked: `m` = the mask bits under the sprite for that screen line; `sprite &= m`, `opaque &= m`, then as plain.
- silhouette (`+10 > 0`; cleared when the draw happens): `dest |= opaque` (**& m** when masked) in all 4 planes → colour 15.
- An all-transparent row is skipped (no write); that test uses the **unmasked** planes.

## 4. Text and banners

- `$19272` (A0 = glyph string ending `$ff`, D0 = column in 8-px units, D1 = row in 8-px units): each glyph (32 bytes at
  `$3ce54 + 32n`, 8 rows × 4 plane bytes) is written **opaque** into **both** screens at the fixed bases `$70000` and
  `$78000` (not via the pointers), at x = 8·col, y = 8·row, then col += 1. No clipping.
- `$19316`: the same into the single off-screen `$68000` (160-B layout); used by scene opcode 6.
- `$1925a` (A0 = records `(word col, word row, long string)`): `$19272` per record until a negative `col`.
- `$194ce` (D0 = 0..3): banner `$35a74 + $600·D0`, 24 lines × 256 px, **planes 0 and 1 only** (planes 2–3 untouched),
  into **both** `[$18eda]` and `[$18ede]` at x = 32, y = `D0 == 3 ? 80 : 0`.
- `$19388`: clear both screens (`[$18ede]`, then `[$18eda]`), 32000 bytes each to 0.

## 5. HUD (`$177a8`) and score (`$17810`)

```
$177a8: if [$176f0] != 0: $19272(col 4, row 0, "$176e8") # six digit bytes + the $ff at $176ee; [$176f0] is NOT cleared here
        for each of the 3 slots at $176f2, $17700, $1770e (14 bytes):
            if word[+0] != 0:
                bytes +6..+11 = $20 (6 spaces) ; repeat word[+2] times: write byte[+5] (icon) from +6 on
                $19272(col byte[+4], row 0, +6) ; word[+0] = 0
```
`[$176f0]`: a byte search for the absolute operand `000176f0` finds exactly 5 sites. `$17746`, `$1788c`, `$17c18` and
`$181c0` all store `-1`; `$177ac` is this read. There is no store of 0, so once set the score is redrawn every frame. (Ghidra's
xref list and its instruction search both miss `$181c0`, because that region is not decoded as code.)
`$17810` (D0 = BCD long): if demo → only `[$176f0] = -1`. Else: `[$17896] = D0`; X cleared; `abcd` adds bytes
`$17899,$17898,$17897` into `$176e6,$176e5,$176e4` with carry (the final carry is lost, max 999999); digit bytes
`$176e8..$176ed` = the six nibbles, high to low; `[$176f0] = -1`.

## 6. Background: window generation and the bitmap

**Window generation `$16474`** (after `$14458`):
```
A0 = [$1646a] ; tr = [$16462] >> 3 (tile row) ; br = tr >> 2 ; sub = tr & 3
A0 += br * 8 ; [$1646e] = A0 ; [$16472] = sub ; A1 = $65300
if sub != 0: partial(A0, A1, first = sub, rows = 4 - sub)    # $165a6
repeat (sub != 0 ? 9 : 10): full(A0, A1)                     # $165fc: 8 blocks x 4 tile rows
if sub != 0: partial(A0, A1, first = 0, rows = sub)          # total: exactly 40 tile rows
```
`$165a6` partial(first, rows): for each of the 8 block ids at A0 (A0 += 8): copy tile-id rows `first..first+rows-1` of the
block (`$56d00 + 16·id + 4·row`, 4 ids per row) into consecutive window rows at column `4·block`; then A1 += 32·rows
(the row count is `((rows-1) & 3) + 1`, so `rows = 0` means 4). `$165fc` full: all 4 rows of each of the 8 blocks, A1 += 128.

**Scroll shifts** (called by §7):
- `$164de` (down): window rows 1..39 → 0..38; new row 39 = partial(A0 = `[$1646e]` + `$50`, first = `[$16472]`, rows = 1);
  `[$16472] = ([$16472] + 1) & 3`, and when it wraps to 0, `[$1646e] += 8`.
- `$1653e` (up): rows 38..0 → 39..1; `[$16472] = ([$16472] - 1) & 3`, and when it becomes 3, `[$1646e] -= 8`;
  new row 0 = partial(A0 = `[$1646e]`, first = `[$16472]`, rows = 1).

**Row renderer `$185a6`** (A0 = 32 tile ids, A1 = bitmap line (128-B pitch), A2 = mask line (40-B pitch)): A2 += 4
(skips x 0..31); for each of 16 column pairs: for the even then the odd tile of the pair: if id ≥ `$f8` → register an
animated slot (`$175f2`, with A0 = the id's window address, A3/A4 = its bitmap/mask address); copy the 40-byte tile
(`$57d00 + 40·id`): 8 rows × (4 plane bytes into the even or odd byte of the 4 plane words, + 1 mask byte), bitmap step
128, mask step 40. A1 += 8, A2 += 2 per pair; after the row, A1 += `$380`, A2 += `$11c` (next 8 lines).
(Ghidra's listing of `$18600`–`$18689` is misaligned; the raw bytes are the same unrolled row pattern
`49ec0028 169d 175d0002 175d0004 175d0006 47eb0080 189d`, repeated.)

**Full render `$1856a`**: window row 7 (`$653e0`) → bitmap/mask line 248; window rows 8..33 (26 rows) → lines 0..207.
**`$16630`** (after every level start / transition): `[$1662c] = 0`; `[$1662e] = [$16462] & 7`; reset the animated
slots (`$175c6`: count 0, cursor `$17394`, every slot flag 0 up to the negative sentinel flag); `$1856a`.

**Background to screen `$18782`**: copy 192 lines of the circular bitmap, starting at line `[$1662e]`, to the draw screen
at (32, 8) (128 bytes per 160-byte line). If `(([$1662e] + $c0) & $ff) > [$1662e]` it is one block; otherwise it wraps:
lines `[$1662e]..255` go to the top, lines `0..(([$1662e]+$c0)&$ff)-1` go below them.

## 7. Vertical scrolling

- `$16658` (every frame): if Rick is dead (`[$12e2a]`) return. `ry = [$16960] - ([$16462] & 7)`.
  If `ry < $9b`: scroll **up** (`$166ae`) only if `[$1662c] < 0`. If `ry >= $9b`: scroll **down** (`$16718`) only if
  `[$1662c] > 0`. (A `ry < $86` test at `$16688` is unreachable, since it is only reached with `ry >= $9b`.)
  `[$1662c]` = Rick's y change this frame (`algo-player.md` §6).
- `$16718` (down): `new = [$16462] + [$1662c]`, clamped to `<= [$16468]` (with `[$1662c]` reduced to match);
  `[$16462] = new`; if unchanged return; if `(old & 7) + [$1662c] > 7` (an 8-px row boundary was crossed): `$17694`,
  `$164de`, `$1888e`, `$16786`, `$171a4(-8)`, `$14542`; else `$16786` only.
- `$166ae` (up): the same against `[$16466]` (0); crossing when `(old & 7) + [$1662c] < 0`: `$17644`, `$1653e`,
  `$1884c`, `$16786`, `$171a4(+8)`, `$14542`.
  **Correction to `graphics.md` §3a:** the pairing there was swapped. Scrolling **up** calls `$1884c` and scrolling **down**
  calls `$1888e`.
- `$16786`: `[$1662e] = ([$1662e] + [$1662c]) & $ff`.
- `$1884c` (up): render window row 8 (`$65400`) into bitmap/mask line `((([$1662e] & $f8) - 8) & $ff)`.
  `$1888e` (down): render window row 33 (`$65720`) into line `((([$1662e] & $f8) + $d0) & $ff)`. Both use `$185a6` and are
  called **before** `$16786` updates `[$1662e]`.

## 8. Animated background tiles

- Slots: 14 bytes at `$17394` (`+0` flag: 0 free, >0 used, <0 end sentinel; `+1` frame index; `+2` window-byte address;
  `+6` bitmap address; `+10` mask address), count `[$17392]` (≤ `$28`).
- `$175f2` register (if count < `$28`): first free slot: flag 1; index = `((id - $f8) << 2) + (PRNG $18538, then byte
  [$18568] & 3)`; store the three addresses; count += 1.
- `$18dac` every frame (if count ≠ 0): from cursor `[$18da8]`, 8 iterations: a free slot is skipped; the sentinel resets
  the cursor to `$17394` **and uses up one of the 8 iterations**; a used slot: `index = (index & ~3) | ((index + 1) & 3)`,
  then copy the 40-byte tile `$5a500 + 40·index` into its bitmap (4 plane bytes, step 128) and mask (step 40) addresses.
  The cursor is saved.
- `$17644` (scroll up): for each used slot, window address += 32; if ≥ `$65740` the slot is freed (count −1).
  `$17694` (scroll down): −32; if < `$65400` freed. The bitmap/mask addresses are not changed (the bitmap is circular).
- PRNG `$18538`: `d6 = [$18562]; d7 = [$18566]; exg d6,d7; rol.l #3,d7; d7.w -= 7; d7.w ^= d6.w; store both`.
  Seeded by `$18516` at every submap load (`$14458`): `d7 = $16051966`, `d6 = $09121967 << 8`, `d7.w = d6.w - 7`,
  `d6.w ^= d7.w`, store `[$18562] = d6`, `[$18566] = d7`. So the "random" sequence restarts at every submap.

## 9. Submap transition (`$18abe` left exit, `$18bb2` right exit) and the slide

```
$18782 ; Rick active := 0 ; laser := 0 ; $170b6 (sprites, without Rick) ; Rick active := 1 ; bomb := 0
$14458(D0, D1) ; $16474 ; $188d0 (new picture + mask) ; $157b4 ; $149c2 ; $14542
[$14592] = -1 ; $14594 ; [$14592] = 0 ; $1709e (all sprites, Rick included, into the new picture)
$19216 ; $191e6                                # the old picture, without Rick, is now displayed
[$18ed8] = 1 ; 16 steps { slide(step) ; $19216 ; $191e6 } ; [$18ed8] = 2 ; $16630
```
`slide` (both read in full): for each of the 192 playfield lines, from the **displayed** screen into the draw screen:
- left exit `$18b5c`: dest group 2 = one group of the new picture (`$68588` = new group 17 at step 1, −8 bytes per step);
  dest groups 3..17 = displayed groups 2..16. The picture moves right by 16 px per step.
- right exit `$18c50`: dest groups 2..16 = displayed groups 3..17; dest group 17 = new picture group (`$68510` = new
  group 2 at step 1, +8 per step). The picture moves left by 16 px per step.

After 16 steps the screen shows exactly the new picture.

`$188d0` builds the new picture at `$68510` (160-B layout, i.e. screen (32, 8)) and the mask at `$65804`: `[$1662e] = 0`;
f = `[$16462] & 7`; if f ≠ 0: the first tile row is drawn from tile line f (8−f lines); then full tile rows (23 if
f ≠ 0, 24 if f = 0); then if f ≠ 0 a last partial row of **f+1** lines, so 193 lines are written in total when f ≠ 0. No
animated-tile registration here.

## 10. Scenes (`$18186`) — the runner and its "run frames" opcode

Runner: does nothing in demo mode (`tst.w $3efb6`, read from raw bytes `4a790003efb6 6702 4e75` since Ghidra did not
decode `$18186`). `[$18180] = scene`, `[$18184] = 0` (abort), `[$18182] = fire held ? -1 : 0`; `[$16462] = 0`; the four
HUD dirty flags = −1; `$177a8`; `$1704c` from `$16d7c` (scene sprite records); then run opcodes from
`$55400 + word[$55402 + 2·scene]` until op 0 or `[$18184] != 0`. Operand formats: `decode_scenes.py` docstring (exact).

Opcode 9 "run frames" `n` (`$183ac`), n iterations:
```
for each scene record from $16d7c until a negative +0: if +0 != 0:
    if +16 != 0: (dx, dy) = $1726e ; x += dx ; y += dy     # algo-spawn.md §6
    else:        x += +a ; y += +c
    $171bc                                                  # animation step
if scene == 2: DRAW                                         # (cmpi.w #2,$18180 at $183fe; read from raw bytes)
elif scene == 1:
    if fire not held: [$18182] = 0 ; DRAW
    elif [$18182] != 0: DRAW                                # still the press held from entry
    else: [$18184] = -1 ; end this opcode                   # a new press aborts scene 1
else (scene 0):
    [$184a8] += 1 ; if == 7: [$184a8] = 0 ; DRAW
    elif fire held: skip DRAW                               # holding fire shows only every 7th iteration: fast-forward
    else DRAW
DRAW: $18caa (copy the off-screen picture $68000, 192 lines from its line 0 at x 32, to the draw screen at (32, 8)) ;
      $17086 (scene sprites) ; $19216 ; $191e6 ;
      if scene == 0 and last key byte == $19 (P): repeat $191e6 until fire ; $191e6
```
Opcode 5 image (`$18d00`): draws a `w×h` rectangle of glyph cells of the image record (`8 + src_col + 32·src_row`) into
the off-screen at cell (dest col, dest row), opaque, 160-B layout, `$500` bytes per cell row.
