# Rick Dangerous 2 — collision probes and hit tests, transcribed

Written 2026-09-23 to close `port-rd2.md` §5.A. Every line below was read from the 68000 disassembly in Ghidra
(`prg2-ram.bin`, `disassemble_bytes` over `$15f1e`–`$16461` and `$14b7a`–`$14d47`) — no decompiler, nothing from
`xrick2-wk.md`. Addresses are RAM addresses. Word compares are **signed** unless stated. "Carry set" = the routine's
boolean result (`ori #1,CCR` / `andi #$fe,CCR`).

Shared cells (`$15f0e`–`$15f1c`, values in the captured image in brackets):

| cell | role |
|---|---|
| `[$15f0e]` word | probe x (input) |
| `[$15f10]` word | probe y (input) |
| `[$15f12]` word | vertical velocity (input; 8.8). Tile part: only its sign. Actor part: its **high byte** (`move.b ($15f12)`) |
| `[$15f14]` byte | result flags (output) |
| `[$15f16]` word | ≠ 0 → also test actors (input) |
| `[$15f18]` word | y of the platform actor found (output; set to `$7fff` on entry) |
| `[$15f1a]`/`[$15f1c]` word | that platform's (dx, dy) (output) |
| `[$161ca]`/`[$161cc]` word | actor-test box y offset / height, set by the entry point (`$15fba`: 0 / `$15`; `$15f1e`: 5 / `$10`) |
| `[$12e16]` word | crouch head-room flag (`$15f1e` only) |

Tables: `A0 = $65200` = the 256-byte tile-attribute table (`attr[]`); the tile window is `$65300`, 32 bytes per row.

## 1. `compute_tile_map_ptr` (`$1643e`) — in: D7 = x offset; out: A1, D7

```
A1 = $65300 + ((y & $fff8) * 4)            # y = [$15f10]; word, adda.w sign-extends
D7 = D7 + x                                # x = [$15f0e]
A1 = A1 + (D7 asr 3)                       # arithmetic shift
```
Returns D7 = x + offset (callers then test `D7 & 7`).

## 2. `query_tile_and_actor_collision` (`$15fba`) — the standard probe

```
[$161ca] = 0 ; [$161cc] = $15 ; [$15f18] = $7fff
D2 = 3 ; if (y & 7) < 4: D2 = 2                           # body rows = D2 (3 or 2): each loop enters at its dbf
D7 = 4 ; compute_tile_map_ptr                              # A1 -> tile (y>>3, (x+4)>>3)
if (D7 & 7) == 0: goto ALIGNED                             # (x+4) on a tile boundary
UNALIGNED ($15ffc):
    D0 = D1 = 0
    repeat D2 times:    D0 |= attr[A1[0]] ; D1 |= attr[A1[1]] ; D0 |= attr[A1[2]] ; A1 += 32
    D3 = (D0 & $22) | (D1 & $2a)
    feet row:           D0 = attr[A1[0]] | attr[A1[2]] ; D1 = attr[A1[1]]
    D3 |= (D0 & $27) | (D1 & $7f)
    [$15f14] = D3 ; goto SIGN
ALIGNED ($16052):
    D0 = 0
    repeat D2 times:    D0 |= attr[A1[0]] | attr[A1[1]] ; A1 += 32
    D3 = D0 & $2a
    feet row:           D3 |= (attr[A1[0]] | attr[A1[1]]) & $7f
    [$15f14] = D3
SIGN ($1608e): if [$15f12] < 0 (word): [$15f14] &= ~$04
ACTORS: if [$15f16] == 0: return
    for A0 = $16b6a step $58 until word[A0] < 0:          # sentinel = first negative +0 word
        if word[A0] == 0: next
        F = byte[A0+1]
        if !(F & $80): next
        if F & $40:                                          # solid actor ($160d4)
            if overlap(A0.x, A0.y, A0.+26, A0.+28,  x+4, y+[$161ca], $10, [$161cc]):
                [$15f14] |= $02
                if A0.y > [$15f18]: next
                feet = y + $14
                lim  = sext(high byte of [$15f12]) + 8 + A0.y
                if feet > lim: next
                [$15f18] = A0.y ; [$15f1a] = 0 ; [$15f1c] = 0 ; [$15f14] |= $40
        else:                                                # one-way platform ($1615a)
            if [$15f12] < 0: next
            h = (unsigned high byte of [$15f12]) + 8          # no ext.w here — only reached with vy >= 0
            if overlap(A0.x, A0.y, A0.+26, h,  x+4, y+$14, $10, 1):
                if A0.y > [$15f18]: next
                [$15f14] |= $40 ; [$15f18] = A0.y ; [$15f1a] = A0.+3a ; [$15f1c] = A0.+3c
```
Byte indices into `attr[]` are unsigned (`moveq #0,D4` then `move.b`). **Row count (corrected 2026-09-24):** every row
loop is `bra` → `dbf` (e.g. `$16002 bra.b $1601a`, `$1601a dbf D2,$16004`), so the body runs **D2** times, not D2+1.
The tile rows are: body rows `y>>3 … y>>3 + D2 − 1`, then the feet row `y>>3 + D2` (= the row of `y + $14`, Rick's feet). Unaligned = columns `c, c+1, c+2`; aligned = columns `c, c+1`, with
`c = (x+4) >> 3`. Note the actor part's box `(x+4, y+[$161ca], 16, [$161cc])` also applies with `[$161ca]`/`[$161cc]`
left as set by the entry point — this is how the crouch probe gets a smaller box.

## 3. Crouch probe (`$15f1e`) — `algo-player.md`'s "`$15f1e` when `[$12e18]`"

Entry bytes `48e7ffc0` (same `movem` as `$15fba`; Ghidra has no instruction there, read from memory), then:
```
[$161ca] = 5 ; [$161cc] = $10 ; [$15f18] = $7fff ; [$12e16] = 0
D2 = 2 ; if (y & 7) < 4: D2 = 1
D7 = 4 ; compute_tile_map_ptr
if (D7 & 7) != 0:                                         # unaligned
    D0 = attr[A1[0]] | attr[A1[1]] | attr[A1[2]] ; A1 += 32
    if D0 & $02: [$12e16] = -1
    goto UNALIGNED of §2 ($15ffc)                           # with D2 = 2/1
else:
    D0 = attr[A1[0]] | attr[A1[1]] ; A1 += 32
    if D0 & $02: [$12e16] = -1
    goto ALIGNED of §2 ($16052)
```
So the top tile row only feeds `[$12e16]` (head room); the result byte is built from the D2 (2/1) body rows below it and
the feet row — the same rows as §2 (feet row `y>>3 + D2 + 1` = the row of `y + $14`), with the top one taken out of the result.

## 4. 8-px probe variant (`$16278`) — used by the bomb

```
[$15f18] = $7fff
D2 = 1 ; if (y & 7) != 0: D2 = 2                           # body rows = D2 (bra -> dbf)
D7 = 8 ; compute_tile_map_ptr                             # column c = (x+8) >> 3
if (D7 & 7) != 0:                                          # unaligned: 2 columns
    D0 = 0 ; repeat D2: D0 |= attr[A1[0]] | attr[A1[1]] ; A1 += 32
    D3 = D0 & $23 ; D3 |= (attr[A1[0]] | attr[A1[1]]) & $27
else:                                                      # aligned: 1 column
    D0 = 0 ; repeat D2: D0 |= attr[A1[0]] ; A1 += 32
    D3 = D0 & $2b ; D3 |= attr[A1[0]] & $27
[$15f14] = D3
if [$15f12] < 0: [$15f14] &= ~$04
if [$15f16] == 0: return
actors (same walk and F tests as §2):
    solid:    overlap(A0.x, A0.y, A0.+26, A0.+28,  x+8, y, 8, $10) -> |= $02 ;
              if A0.y > [$15f18]: next ; if y+$f > sext(hi[$15f12]) + 8 + A0.y: next ;
              [$15f18] = A0.y ; [$15f1a] = [$15f1c] = 0 ; |= $40
    one-way:  if [$15f12] < 0: next ; overlap(A0.x, A0.y, A0.+26, hi[$15f12] + 8,  x+8, y+$f, 8, 1) ->
              if A0.y > [$15f18]: next ; |= $40 ; [$15f18] = A0.y ; [$15f1a] = A0.+3a ; [$15f1c] = A0.+3c
```
(`y + $f` is the bomb's feet; its sprite is shorter than Rick's.)

## 5. Point probe (`$161fe`) — laser shot, group shot

```
D7 = 0 ; compute_tile_map_ptr                              # tile (y>>3, x>>3), no x offset
D0 = attr[A1[0]] ; [$15f14] = D0                           # the WHOLE attribute byte, no mask
if D0 & $02: return
for A0 = $16b6a step $58 until word[A0] < 0:
    if word[A0] == 0: next
    if (byte[A0+1] & $c0) != $c0: next                     # solid actors only
    if point_in_box(x, y, A0.x, A0.y, A0.+26, A0.+28): [$15f14] |= $02 ; return
```
Unlike §2–§4, this probe never reads `[$15f16]`/`[$15f12]` and does not clear bit 2.

## 6. `aabb_overlap_test` (`$161ce`) — box A (D0,D1,D2,D3) vs box B (D4,D5,D6,D7), each (x, y, w, h)

```
hit iff  A.x < B.x + B.w  and  B.x < A.x + A.w  and  A.y < B.y + B.h  and  B.y < A.y + A.h
```
(all four strict; the code tests `B.x+B.w <= A.x` → miss, etc.). Registers are preserved.

## 7. `point_in_box` (`$14c8c`) — point (D6, D7) vs box (D0, D1, D2, D3)

```
hit iff  0 <= D6 - D0 <= D2  and  0 <= D7 - D1 <= D3          # inclusive on both edges
```

## 8. `check_box_vs_player` (`$14b7a`) — box (D0, D1, D2, D3) vs Rick (`Rx = [$1695c]`, `Ry = [$16960]`)

```
if [$12e2a] != 0: miss                                     # Rick dead
if D0 >= Rx + $14:        miss
if D0 + D2 <= Rx + 4:     miss
if D1 >= Ry + $15:        miss
if [$12e18] == 0:  if D1 + D3 <= Ry:      miss else hit    # standing: strict
else:              if D1 + D3 <  Ry + 5:  miss else hit    # crouching: INCLUSIVE (blt)
```
**This settles the conflict in `port-rd2.md` §5.A**: the crouching test is `D1 + D3 >= Ry + 5` (inclusive),
the standing one `D1 + D3 > Ry` (strict). `algo-actors.md` §4's half-open `[Ry+5, Ry+$15)` notation was imprecise
on this edge.

## 9. The three trigger points (`$14bee`, `$14c20`, `$14c5a`) — box in (D0..D3)

| routine | point | gate (miss if false) |
|---|---|---|
| `$14bee` point 1 | `([$12efa], [$12efc])` — the laser shot's front | `word[$16902] != 0` (shot active) |
| `$14c20` point 2 | `([$12f02], [$12f04])` — the bomb explosion centre | `word[$16b12] != 0` and `word[$12efe] != 0` |
| `$14c5a` point 3 | `([$12ef6], [$12ef8])` — the melee point | `word[$12ef4] != 0` |

Each is `point_in_box` (§7) after its gate.

## 10. Record-in-box tests used by `dispatch_spawn_record` (box in D0..D3, record in A2)

- `$14cb4` **object** (fixed 16×21 box, like Rick's): `if A2.+4e != 0: miss`;
  hit iff `D0 < A2.x+$14`, `D0+D2 > A2.x+4`, `D1 < A2.y+$15`, `D1+D3 > A2.y` (all strict).
- `$14d04` **actor** (its own size): hit iff `D0 < A2.x+A2.+26`, `D0+D2 > A2.x`, `D1 < A2.y+A2.+28`, `D1+D3 > A2.y`
  (all strict).

## 11. Probe inputs as set by each caller (the probe cells are globals and persist between calls)

`[$15f0e]`/`[$15f10]`/`[$15f12]`/`[$15f16]` are never reset by the probes, so a caller that doesn't write one **inherits the
last value any caller left**. Checked sites:

| caller | probe | `[$15f12]` | `[$15f16]` |
|---|---|---|---|
| Rick gravity (`$13190`/`$1318a`, `algo-player.md` §2) | `$15fba` / `$15f1e` if crouching | new vy | −1 |
| Rick on a platform re-probe (`$131e6`/`$131ec`) | same | (unchanged) | **0** |
| Rick horizontal (`$135fc`/`$13602`, §5) | same | −1 | −1 |
| **Rick ladder (`$1390a`, §7)** | `$15fba` | D6 (−2 / 0 / +2) | **not written: inherited** |
| Rick tunnel (`$13c2a`, §9) | `$15fba` | new vy, then −1 for the horizontal | −1 |
| bomb falling (`$13f24`) | `$16278` | new vy | −1 |
| bomb platform re-probe (`$13f62`) | `$16278` | (unchanged) | **0** |
| bomb horizontal (`$140d0`) | `$16278` | **−1** | −1 |
| objects (`algo-objects.md`) | `$15fba` | as listed there | −1, then 0 for the platform re-probe |

Provenance: the ladder and bomb rows, and the `$13194` result load, were re-read in the disassembly on 2026-09-23. The
other rows restate `algo-player.md` §2/§3/§5/§9 and `algo-objects.md`, which were transcribed from the disassembly on
2026-09-19/20 and not re-read in this pass.

On return, callers read the result with `move.b ($15f14),D7` (e.g. `$13194`), because the probes restore D0–D7.
In the frame order (`algo-flow.md` §2) the object update runs before Rick, so the ladder probe usually inherits the object
code's last `[$15f16]`, or a value left from the previous frame. A port must keep these cells as persistent globals.
