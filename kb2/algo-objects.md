# Rick Dangerous 2 — the 4-slot object table (`update_object_slots` `$150a2`, `FUN_000150c0`), transcribed

Read from the 68000 disassembly in Ghidra on 2026-09-19: `$150a2` (10 instr.), `$150c0` (412 instr., `$150c0`–`$156ee`), `$1570e`, `$18538`,
the spawn constructor `FUN_00014862` (`level-tables.md` §3) and the collision probe (`algo-actors.md` §6). `A6` = the object record
(88 bytes, `$167a2` + 88·k, k = 0..3). Only the object table uses this code; actors use `update_actor_ai` (`algo-actors.md`).

## Fields used (byte offsets; all words unless noted)

`+0` kind (1, 2 or 3; 0 = free — set from spawn byte 0 & 3 by `FUN_00014862`) · `+2` x · `+6`/`+8` y integer/fraction (`+6` is also read as a long) ·
`+$a` dx · `+$c` vy (8.8) · `+$e` sprite frame · `+$10`, `+$12`, `+$14` flags (`+$12` = masked blitter, `+$14` = second draw pass; `graphics.md` §4) ·
`+$22` animation phase · `+$3e` frame base (from `$14854`) · `+$40` "on a moving platform" · `+$42` on floor · `+$44` unused here (only cleared/tested) ·
`+$46`, `+$48` slow / conveyor markers · `+$4a` platform dx · `+$4c` hit-by-actor flag (set by `$15740`) · `+$4e` dying · `+$50` "climbing" ·
`+$52` / `+$54` oscillation counter / period · `+$56` stun timer. `+$2a` spawn record pointer (used by the despawn routines).

`FUN_00014862` (`$14862`) initialises: `+0 = b0 & 3` **as a word**; `+$e = +$3e = word[$14854 + (((b0 & $c) − 4) >> 1)]` where `$14854` =
`65, 75, 194, 256` (words; only the first three are reachable: `b0 & $c` is 4, 8 or 12); `+8 = 0`, `+$c = $100`, `+$a = 2`; `+$42 … +$50`, `+$56 = 0`;
`+2 = (b2 & $1f)·8 (+4 if b2 bit 5)`, `+6 = b1·8 − (scroll & ~7) + 3`; `+$10 = +$14 = 0`; `+$12 = −1` if `b3` bit 7; `+$2a = record`; the record's spawned
bit is set. For `b0 & 3 == 1` it also sets `+$54 = ((b3 & $3c) << 1) + 8` and `+$52 = 0`.

## Per-frame update (`FUN_000150c0`)

```
if +4c != 0: goto DESTROY
+40 = 0 ; +4a = 0
if +56 != 0: +56 -= 1
if +4e != 0: goto DYING_MOVE                       # $1568e
if +50 != 0: goto HELD                             # $15590
+42 = +44 = +46 = +48 = 0
vy = min(+c + $80, $800) ; +c = vy ; [15f12] = vy
D1 = (vy << 8) + long[+6] ; y_new = D1 >> 16
if y_new < 0 or y_new > $12b: despawn_forced ($149f0) ; return
[15f10] = y_new ; [15f0e] = +2 ; [15f16] = -1 ; D7 = probe($15fba)
P:  if D7 & $20: goto DESTROY
    if D7 & $40:                                   # platform actor below
        y_new = [15f18] - $15 ; [15f10] = y_new ; +42 = 1 ; +4a = [15f1a] ; [15f16] = 0 ; D7 = probe
        if D7 & $20: goto DESTROY
        if D7 & 6:   goto CEIL
        if [15f1a] | [15f1c]: +40 = 1
        +c = $100 ; goto S2
    if D7 & 4:                                     goto FLOORCASE
    if !(D7 & 2):                                  goto STORE
    if +c >= 0:                                    goto FLOORCASE
CEIL:  y_new = (y_new | 7) + 1 ; fraction = 0 ; +c = $100 ; goto STORE
FLOORCASE:                                          # $15206
    if +0 == 3 and (D7 & $10) and y_new <= [16960] and (+2 & $1f) == 4: +50 = 1 ; +c = $100 ; goto STORE
    +50 = 0 ; +42 = 1
    y_new = (((y_new + $0c) | 7) - $14) ; fraction = 0 ; +c = $100
    if D7 & 1 and map == 3:                        # $15266
        v = +c                                     # = $100, just stored
        if v >= $200: +c = -v + $60 ; play_sound($19) ; goto STORE       # UNREACHABLE: v is always $100 here
        else:         +c = $100                     ; goto STORE
    goto S2
S2: if D7 & 1 and map == 5: play_sound($1a) ; +c = -$87f       # $152a0
STORE:  long[+6] = y_new (with fraction)                        # $152c8
    if +0 == 3 and (D7 & 8) and !(D7 & $10) and y_new > [16960] and (+2 & $1f) == 4: +50 = 1
    if +56 != 0 or +40 != 0 or (+c >= 0 and +42 == 0) or (+0 == 3 and +50 != 0): D6 = 0 ; D2 = +2 ; goto MOVEX
    D6 = +a
    if D7 & 1:
        if map == 2: +48 = 1
        elif map == 4: +46 = 1 ; D6 = 1 ; if +a < 0: D6 = -1 ; +48 = 1      # +48 is only set on the negative branch ($15358 bpl $15366)
    if   +0 == 1: { +52 += 1 ; if +52 == +54: +52 = 0 ; D6 = -D6 }               # oscillator, period +54
    elif +0 == 2: { if rnd_gate(): { D6 = 2 ; if +2 >= [1695c]: D6 = -2 } }         # $15398: moves toward Rick's x (when the gate fires)
    else:         { if rnd_gate(): D6 = -D6 }
MOVEX:                                             # $153b4
    D6 += +4a ; D2 = +2 + D6
    if D6 < 0 and D2 < 0:     D2 = 0    ; D6 = -D6 ; +52 = 0
    if D6 > 0 and D2 >= $e8:  D2 = $e8  ; D6 = -D6 ; +52 = 0
    [15f10] = +6 ; [15f12] = -1 ; [15f0e] = D2 ; [15f16] = -1 ; D7 = probe
    if D7 & $20: goto DESTROY
    if D7 & 2:  D2 = (((D2 + (D6 < 0 ? $0c : 3)) & ~7) - 4) ; D6 = -D6 ; +52 = 0
    +2 = D2 ; if D6 != 0: +a = D6
    if +0 == 3 and !(D7 & 8): +50 = 0
    <frame choice below>
    <contacts below>
```

`rnd_gate()` = `FUN_0001570e` (`$1570e`): carry set iff `(+2 & 15) == 4` **and** after calling the generator `$18538` the byte at `$18569` `& 3 == 0`.
Generator `$18538` (state longs `[$18562]`, `[$18566]`): `d6 = [18562]; d7 = [18566]; swap(d6, d7); d7 = rol32(d7, 3); d7.w −= 7; d7.w ^= d6.w;
[18562] = d6; [18566] = d7`. (It is also used for the animated-tile phase, `graphics.md` §3b.)

**Frame choice** (`$1546e`–`$15510`):

```
if +40 == 0:
    if +50 != 0:  +e = 8 ; if ((+2 ^ +6) & 4): +e = 9 ; goto ADDBASE
    if +42 == 0:  +e = 2 ; +22 = 0 ; goto MIRROR
    if +56 != 0 or +44 != 0: +e = 1 ; +22 = 0 ; goto MIRROR
    step = 1 ; if +46 == 0: step = 4 ; if +48 == 0: step = 2
    +22 = (+22 + step) mod $20 ; +e = byte[$1485a + (+22 >> 2)]      # $1485a = 01 00 02 00 01 00 02 00
else: +e = 1 ; +22 = 0
MIRROR: if +a < 0: +e += 3
ADDBASE: +e += +3e
```

**Contacts** (every frame after the move):

```
if point_3_in_box(+2 + 4, +6, $10, $15):     +56 = $28 ; +10 = 1 ; play_sound($18) ; goto SHOT      # melee point ([12ef6],[12ef8]) while [12ef4] != 0
else if check_box_vs_player(+2 + 4, +6, $10, $15): [12e2c] = -1                                  # hurts Rick
SHOT: if point_1_in_box(...): [16902] = 0 ; goto DESTROY                                        # the laser shot ([12efa],[12efc]) — consumed
      box = (+2 + 4 − $10, +6 − $0e, $20, $1d)
      if point_2_in_box(box): score += $50 ; goto DESTROY                                       # ([12f02],[12f04]) while [16b12] != 0 and [12efe] != 0
      return
```
(point numbering as in `algo-actors.md` §4: 1 = `$14bee`, 2 = `$14c20`, 3 = `$14c5a`.)

## HELD (`+50 != 0`, `$15590`)

```
+3 &= ~1 ; +7 &= ~1                         # bclr #0 on the low bytes of x and y
y = +6 ; D6 = 0
if +56 == 0: t = ([16960] + 1) & ~1 ; if y < t: D6 = 2 elif y > t: D6 = -2
+c = D6 ; y += D6 ; [15f12] = D6 ; [15f10] = y ; [15f0e] = +2 ; D7 = probe ; goto P
```

## DESTROY (`$155e6`) and DYING_MOVE (`$1568e`)

```
DESTROY: if +4c != 0: score += $100 ; +4c = 0
         +4e = -1 ; +12 = 0 ; +22 = 0 ; +8 = 0 ; +c = -$500 ; +a = 2 ; score += $50
         if $23 <= +6 <= $148:
             id = word[$156f0 + 6·(map−1) + (byte(+3f) & $80 ? 4 : (+3e == $41 ? 0 : 2))] ; play_sound(id)
         if +2 >= $74: +a = -2
DYING_MOVE: +2 += +a ; +22 = (+22 + 1) & 3 ; +e = (+22 >> 1) + 6 + +3e ; +14 = -1
         vy = min(+c + $80, $800) ; +c = vy ; long[+6] += vy << 8
         if +6 >= $12b: despawn ($14a12)
```
Sound table `$156f0` (words, 3 per map for maps 1–5): `15 15 15 | 11 14 11 | 11 11 12 | 13 15 11 | 11 11 11`; column 0 is chosen for frame base `$41`,
column 1 for base `$4b` (75), column 2 for a base with bit 7 set (194 = `$c2`).

## What the code proves and what it does not name

- Rows: kind 1 = moves back and forth with period `+$54` (`+$52` counter reset at the walls); kind 2 = when `rnd_gate()` fires moves ±2 toward Rick's x; kind 3 = when
  `rnd_gate()` fires reverses direction, and can enter the "climbing" state `+50` (moves ±2 vertically toward Rick's y, `HELD`). These are the branches as coded; no
  game-level names are given because none is in the code.
- Consumers of `+4c` (set by `$15740` for objects touched by a hurtful actor): +$100 points and destruction.
