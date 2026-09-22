# Rick Dangerous 2 — player controller (`update_player_rick` `$13096`), transcribed

Every statement below was read from the 68000 disassembly in Ghidra (`prg2-ram.bin`) on 2026-09-19; the routines are
`$13096` (687 instructions, `$13096`–`$13d0a`), `$13d0a`, `$13d58`, `$13e14`, `$141cc`, `$15f1e` (crouch probe) and `$15fba`
(`algo-actors.md` §6). Nothing is guessed: where a name describes a role, the sentence says which instruction proves it. Registers
inside `update_player_rick`: **D0 = joystick byte for the whole call**, D1 = new y (long), D2 = new x, D6 = dx / vertical impulse, D7 = tile
flags returned by the probe (`[$15f14]`).

## 1. State variables (addresses are RAM)

**Record layout of the sprite/actor array.** All these records are 88 bytes and contiguous (verified by the arithmetic of the
addresses used): `$167a2` object slots ×4, `$16902` **Rick's laser shot**, `$1695a` **Rick**, `$169b2` debris ×4, `$16b12` **bomb**,
`$16b6a` actor slots ×6. Field offsets follow `algo-actors.md` §1: +0 active word, +2 x, +6 y (word; +8 fraction), +`$c` vy, +`$e` frame.

| addr | proven by |
|---|---|
| `[$1695a]` = active; `[$1695c]` x; `[$16960]`/`[$16962]` y integer/fraction; `[$16966]` vy (signed 8.8); `[$16968]` frame id | Rick's record is `$1695a` (base `$167a2 + 5·$58`); `[$16968]` is written with sprite ids and the draw routine reads +`$e` (`graphics.md` §4) |
| `[$1697e]` | written 1 by input bit 2 (LEFT) and 0 by bit 3 (RIGHT) (`$134d2`–`$13524`); read by `$13d58` to choose the shot direction; adds `$0d` to the frame at `$138ba` → **facing (1 = left)** |
| `[$1697c]` | walk-animation counter: `+1/+2/+4` per frame modulo `$28`/`$20` (`$13844`); `-1` when idle |
| `[$12e10]`, `[$12e12]` | previous y and x, saved at `$13096`/`$130a0` |
| `[$12e18]` | set to 1 by DOWN on the ground (`$133e2`); when non-zero the probe `$15f1e` is used and frame 6 is chosen → **crouch** |
| `[$12e16]` | set −1 by `$15f1e` when its top row(s) contain a tile with attribute bit 1; blocks clearing `[$12e18]` (`$13398`, `$13484`) |
| `[$12e1a]` | set by ladder-grab tests, makes the frame `$1a`/`$1b` and the up/down movement at `$138c6` → **on a ladder** |
| `[$12e1c]` | set to 1 when landing on a floor/platform, selects the ground branch of the frame choice (`$136ec`) |
| `[$12e14]` | set −1 by a trigger record with bit 5 (`level-tables.md` §2); selects the branch at `$13b84` and frame `$0c` |
| `[$12e2a]` | dead flag: selects `$13ace`; also disables actor collisions (`$14b7a` returns "no hit") |
| `[$12e2c]` | "hit" flag written −1 by enemy code; consumed at `$13a62` |
| `[$12e24]`, `[$12e26]`, `[$12e28]` | 1 while UP+FIRE / laser latch / 1 while DOWN+FIRE |
| `[$12e1e]` `[$12e20]` `[$12e22]` | animation-mode flags, see §4 |
| `[$12ef2]`, `[$12ef4]` | last input byte for the melee move; its countdown (starts at 10) |
| `[$12e2e]` | dx inherited from a moving platform (`[$15f1a]`, `$131cc`) |
| `[$14360]` | 1 / 2 when x was clamped at the left / right limit (`$135b8`, `$135cc`); the "side" tested by the trigger table (`level-tables.md` §2: `b0 & 3 == [$14360]`, `$14380`) |
| `[$1662c]` | vertical scroll request = y − previous y (`$13a4e`), consumed by `$16658` (`graphics.md` §3a) |
| HUD counters | `[$176f4]` laser shots (decremented at `$13d72`), `[$17702]` bombs (`$13996`), `[$17710]` lives (`$13a84`); `[$176f2]`, `[$17700]`, `[$1770e]` = "redraw" words set −1 |

**Input byte** (`read_player_input` `$141cc`): bit 0 UP, 1 DOWN, 2 LEFT, 3 RIGHT, 7 FIRE (the tests `btst #0/#1` move y by ∓2 on the ladder
at `$138d8`–`$138ea`, `btst #2/#3` set `[$1697e]`, `btst #7` is the fire tests). In demo mode the byte comes from the demo stream
(`level-tables.md`/`PLAN.md` T25).

## 2. Frame order

```
[12e10] = y ; [12e12] = x ; [14360] = 0 ; [12e2e] = 0
D0 = read_player_input()
if [12ef4] != 0: [12ef4] -= 1
if D0.b != [12ef2].b: [12ef2] = 0 ; [12ef4] = 0
if [12e2a]: goto DEAD      # $13ace
if [12e2c]: goto DIE       # $13a62
if [12e14]: goto TUNNEL    # $13b84
if [12e1a]: goto LADDER    # $138c6
GRAVITY:
   [12e1c] = [12e1e] = [12e20] = [12e22] = [12e24] = [12e28] = 0
   vy = min([16966] + $80, $800) ; [16966] = [15f12] = vy
   y_new = ((vy << 8) + long[16960]) >> 16          # 16.16 add
   [15f10] = y_new ; [15f0e] = x ; [15f16] = -1
   D7 = probe()                                       # crouch ? $15f1e : $15fba
```

`probe()` = the tile+actor query of `algo-actors.md` §6 with inputs `[$15f0e] x`, `[$15f10] y`, `[$15f12]` vertical velocity, `[$15f16]`;
result flags in `[$15f14]`.

## 3. Vertical resolution (label `A`, `$13194`)

```
A:  if D7 & $20: goto DIE
    if D7 & $40:                                       # standing on a platform actor
        y = [15f18] - $15 ; fraction = 0 ; [15f10] = y ; long[16960] = y << 16
        [12e1c] = 1 ; [12e2e] = [15f1a] ; [15f16] = 0
        D7 = probe()
        if D7 & $20: goto DIE
        if D7 & 6:  goto CEIL                          # $13234
        D6 = $100 ; goto L13348
    if D7 & 4:                        goto FLOOR       # $1327a
    if !(D7 & 2):                     goto AIR         # $13476
    if [16966] >= 0:                  goto FLOOR
CEIL:                                                    # $13234  (moving up into a solid tile)
    if [12e1a]: { t = x & $1f ; if t < 10: x = (x & $f0) | 4 }
    y = ((y | 7) + 1) ; fraction = 0 ; [16966] = $100 ; goto AIR_STORE
FLOOR:                                                   # $1327a
    if D7 & $10 and ![12e18]:
        if [12e1a]: goto AIR_STORE
        if !(D0 & $80) and (D0 & 2):                    # DOWN without FIRE at a ladder-top tile
            t = x & $1f ; if t < 10: { x = (x & $f0) | 4 ; [12e1a] = 1 ; goto AIR_STORE }
    [12e1a] = 0 ; [12e1c] = 1                           # $132ce: landed
    y = (((y + $0c) | 7) - $14) ; fraction = 0 ; long[16960] = y << 16
    D6 = $100
    if D7 & 1 and map == 3:                             # $13300
        D6 = [16966]
        if D6 < $200: [16966] = $100 ; D6 = -$600 ; goto L13390
        play_sound($19) ; D6 = -D6 + $60 ; [16966] = D6 ; D6 = -$87f ; goto L13390
L13348:
    [16966] = D6 ; D6 = -$600
    if D7 & 1:
        if map == 1: D6 = -$200
        elif map == 5: play_sound($1a) ; [16966] = -$87f ; goto COMMON      # $134ac
L13390:                                                   # D6 = the jump impulse
    if [12e18]:                                          # crouching
        if [12e16]: goto COMMON
        [12e18] = 0 ; goto L133da
    if D0 & $80: goto FIRE                               # $133ee
    if !(D0 & 1): goto L133da
    [16966] = D6                                          # JUMP
    if !(D7 & $10) and (D7 & 8): [12e1a] = 1              # UP also grabs a ladder tile
    goto COMMON
L133da: if (D0 & 2): [12e18] = 1                          # crouch
        goto COMMON
AIR:                                                      # $13476  (also the target of the "AIR_STORE" jumps above)
    long[16960] = y (with its fraction, as adjusted above)
    if [12e18] and ![12e16]: [12e18] = 0
    if (D0 & 3) and (D7 & 8): [12e1a] = 1                 # UP or DOWN next to a ladder tile grabs it
    goto COMMON
```

(`L13390`'s branch `if D0 & $80: FIRE` is only reachable when not crouching.)

## 4. Fire (label `FIRE`, `$133ee`) and the three attacks

```
FIRE:
  if D0 & 1: goto UPFIRE                          # $13912
  [12e26] = 0
  if D0 & 2: goto DOWNFIRE                        # $13976
  if D0.b == [12ef2].b: goto L1394e
  if D0 & 4: [1697e]=1 ; [12ef4]=10 ; [12ef2]=D0 ; play_sound($2d) ; goto L1394e   # melee left
  if D0 & 8: [1697e]=0 ; [12ef4]=10 ; [12ef2]=D0 ; play_sound($2d) ; goto L1394e   # melee right
  goto COMMON                                     # FIRE alone: nothing
L1394e: if (D7 & 1) and map == 2: [12e1e] = 1 ; goto COMMON      # else goto AFTER_MOVE ($13662)

UPFIRE: [12e24] = 1
  if [12e26]: goto L1394e
  if [176f4] == 0: play_sound($30) ; [12e26] = 1 ; goto L1394e
  if [16902] == 0: SHOOT() ; goto AFTER_MOVE           # SHOOT = $13d58
  goto L1394e

DOWNFIRE: [12e28] = 1
  if [17702] == 0 or [16b12] != 0: goto L1394e
  [16b12] = 1 ; [17702] -= 1 ; [17700] = -1
  [16b14] = x ; [16b16] = 0 ; [16b18] = y + 5 ; [16b1a] = 0 ; [16b1e] = $100
  [16b34] = 0 ; [16b30] = $12e5e ; [16b36] = 0
  if D0 & 4: [1697e] = 1 ; [16b36] = -$200 ; play_sound($32)
  elif D0 & 8: [1697e] = 0 ; [16b36] = +$200 ; play_sound($32)
  goto AFTER_MOVE

SHOOT ($13d58): play_sound($10)
  [16902] = 1 ; [176f4] -= 1 ; [176f2] = -1 ; [16908] = y + 7
  if [1697e] == 0: [16926] = 8 ; [16904] = x ; [16910] = $1f (tunnel: $92)
  else:            [16926] = -8 ; [16904] = x ; [16910] = $1e (tunnel: $93)
  [12e26] = -1
```

(`$13d58` sets `[$12e26] = -1` in both branches — the latch that `UPFIRE` and `$13d0a` test — and `$133f6` clears it when FIRE is pressed without UP.) The **bomb record** at `$16b12` receives: active 1, x, y+5, vy `$100`, animation-script pointer `$12e5e` (+`$1e`), x velocity in +`$24` (`[$16b36]`).
The script at `$12e5e` (decoded in `scripts.json` → `in_program`) is 49 records to `$12ed2` — frames 32,128,129,128, *sound 48*, 32,128,129,128,
*sound 48*, 130,131,132,131, …, ending `138,139,140,139` — and a jump back to `$12e5e`; the record that follows at `$12ed6` is the
explosion script already documented.
`$13e14` (the shot): `if [16902]`: `x_front = [16904] + (([16926] < 0) ? 4 : $14)`; probe `$161fe` at `(x_front, [16908] + 4)`;
if tile flag bit 1 → ends; else `x_front += [16926]`; if `0 <= x_front <= $ff`: `[12efa] = x_front`, `[12efc] = y`, `[16904] += [16926]`; else `[16902] = 0`.

## 5. Horizontal movement (`COMMON`, `$134ac`)

```
COMMON: if [12e1a] and !(D7 & 8): { [12e1a] = 0 ; if [16966] < 0: [16966] = -$200 }
  if D0 & 4:   [1697e] = 1 ; D6 = -2 ; if D7 & 1: { if map==4: D6 = -1 ; [12e20]=1     elif map==2: [12e22]=1 }
  elif D0 & 8: [1697e] = 0 ; D6 = +2 ; if D7 & 1: { if map==4: D6 = +1 ; [12e20]=1     elif map==2: [12e22]=1 }
  else:        D6 = 0
               if !(D7 & 1) or map != 2: [1697c] = -1
               else: [12e1e] = 1 ; D6 = 2 ; if [1697e]: D6 = -2       # map 2, tile flag bit 0: pushed along the facing
  D6 += [12e2e]
  D2 = x + D6
  if D6 < 0 and D2 < 0:      D2 = 0    ; [14360] = 1
  if D6 > 0 and D2 >= $e8:   D2 = $e8  ; [14360] = 2
  [15f10] = y ; [15f12] = -1 ; [15f0e] = D2 ; [15f16] = -1 ; D7 = probe()
  if D7 & $20: goto DIE
  if D7 & 2:  x = ((D2 + (D6 < 0 ? $0c : 3)) & ~7) - 4 ; else: x = D2 ; if [12e1a] and !(D7 & 8): [12e1a] = 0
AFTER_MOVE ($13662): <frame choice, §6>
```

## 6. Frame choice (`$13662`–`$13a4e`)

```
if [12e14]: [16968] = $0c ; FUN_00013d0a() ; goto FACING
if [12e1a]:                                            # ladder
    if x != [12e12] or y != [12e10]: [12e30] = ([12e30] + 1) & 3 ; if [12e30] == 0: play_sound($31)
    [16968] = $1a ; if (x ^ y) & 4: [16968] = $1b ; goto END
if ![12e1c]: [16968] = [12e18] ? 6 : 8 ; goto FACING                       # airborne
if [12ef4]:                                            # melee
    if [1697e]: [12ef6] = x     ; [12ef8] = y + 8 ; [16968] = $17
    else:       [12ef6] = x+$18 ; [12ef8] = y + 8 ; [16968] = $0a
    goto END
if [12e24]: [16968] = 9 ; goto FACING
if [12e28]: [16968] = ([16b36] != 0) ? $0b : 0 ; goto FACING
if [12e1e]: [16968] = 6 ; if ![12e18]: table = $12e4c ; step = 3 ; wrap = $28 ; goto WALK
if [12ef2].b != 0: [16968] = 0 ; goto FACING
table = [12e18] ? $12e56 : $12e42 ; wrap = [12e18] ? $20 : $28 ; [16968] = [12e18] ? 6 : 0
if [1697c] == -1: [1697c] = 0 ; goto FACING
step = 1 ; if [12e20]: (step 1) ; else: step = 4 ; if [12e22]: (step 4) ; else step = 2
WALK: [1697c] += step ; if [1697c] >= wrap: [1697c] -= wrap
      i = [1697c] >> 2
      sound: crouched → if i & 1: play_sound($32) ; else i ∈ {2,5,7,0} → play_sound($31)   (walking; the crouched walk is `$12e56`)
      [16968] = byte[table + i]
FACING ($138b0): if [1697e]: [16968] += $0d
END ($13a4e): [1662c] = y - [12e10] ; return
```

Tables (RAM `$12e42`, `$12e4c`, `$12e56`): `01 02 03 04 05 01 02 03 04 05` / `05 04 03 02 01 05 04 03 02 01` / `06 07 06 07 06 07 06 07`.
(The exact order of the `step` selection is: `step = 1`; if `[12e20]` use it; else `step = 4`; if `[12e22]` use it; else `step = 2` — `$1382e`–`$13842`.)

## 7. Ladder (`$138c6`)

```
x &= ~1                                                    # bclr #0,[1695d]
D6 = 0 ; if D0 & 1: D6 = -2 elif D0 & 2: D6 = +2
[16966] = D6 ; y_new = y + D6 ; [15f12] = D6 ; [15f10] = y_new ; [15f0e] = x ; D7 = $15fba()
goto A                                                     # same flag handling as §3
```

## 8. Death (`DIE` `$13a62`, `DEAD` `$13ace`)

```
DIE:  play_sound($0a) ; [12e2c] = 0 ; [12e2a] = -1 ; [17710] -= 1 ; [1770e] = -1
      [1696c] = 0 ; [1697c] = 0 ; [16962] = 0 ; [16966] = -$500 ; [1697e] = 2 ; if x >= $74: [1697e] = -2
DEAD: vy = min([16966] + $80, $800) ; [16966] = vy ; long[16960] += vy << 8 ; x += [1697e]
      [1697c] = ([1697c] + 1) & 3 ; i = [1697c] >> 1
      if [16966] < 0: [16968] = i + $1c ; [1696e] = -1 ; return
      D1 = (i << 2) + $95
      for k in 0..3: rec = $169b2 + $58·k ; [rec] = 1 ; [rec+$14] = -1 ; [rec+$e] = D1 + k ;
                     [rec+2] = x + word[$13e04 + 4k] ; [rec+6] = y + word[$13e04 + 4k + 2]
      [1695a] = 0 ; return
```
Debris offsets (`$13e04`): `(-12, 0) (12, 0) (-12, 21) (12, 21)` as `(dx, dy)` word pairs `fff4 0000 000c 0000 fff4 0015 000c 0015`.
The routine has no restart code: `game_main` (`algo-flow.md` §6) respawns Rick once `[$12e2a] ≠ 0` and `[$16960] ≥ $100` (`$149c2`, then `$142fc` → `$14300` → `$12f08`, which clears `[$12e2a]`).

## 9. Transition tunnel (`TUNNEL` `$13b84`)

```
[12e1c]=[12e1e]=[12e20]=[12e22]=[12e24]=[12e28]=[12e1a]=0
vy = min([16966] + $40, $400)
if D0 & 1: vy += -$c0 ; if vy < -$400: vy = -$400
elif D0 & 2: vy += $80 ; if vy > $400: vy = $400
[16966] = [15f12] = vy ; y_new = ((vy << 8) + long[16960]) >> 16 ; [15f10] = y_new ; [15f0e] = x ; [15f16] = -1 ; D7 = $15fba()
if D7 & $20: goto DIE
if D7 & 4 or (D7 & 2 and vy >= 0): y = (((y_new + $0c) | 7) - $14) ; fraction = 0 ; [16966] = 0
elif D7 & 2:                        y = ((y_new | 7) + 1) ; fraction = 0 ; [16966] = 0
long[16960] = y ; D6 = 0 ; if D0 & 4: D6 = -4 ; [1697e] = 1  elif D0 & 8: D6 = 4 ; [1697e] = 0
D2 = x + D6 with the same limits / [14360] as §5 ; [15f10] = y ; [15f12] = -1 ; [15f0e] = D2 ; [15f16] = -1
goto the probe at $13602 and the horizontal resolution of §5
```
`FUN_00013d0a` (`$13d0a`, called from the frame choice while `[12e14]`): if FIRE is not held `[12e26] = 0` and return; else `[12e24] = 1`;
if `[12e26] == 0`: counter `[176f4] == 0` → sound `$30`, `[12e26] = 1`; else if `[16902] == 0` → SHOOT. (So in the tunnel FIRE alone shoots.)

## 10. What is not in this routine

Restart after death, lives = 0, score, and the submap/level changes are in `algo-flow.md`. Tile attribute bits as *consumed here*: bit 5 kills (every probe),
bit 6 platform actor, bit 1 blocks sideways movement and head, bit 2 floor (feet row only, cleared when moving up), bit 3 = a ladder tile is present, bit 4 = "ladder top"
entry via DOWN, bit 0 = per-map surface property (map 1 jump `-$200`, map 2 conveyor, map 3 bounce with sound `$19`, map 4 walk speed 1, map 5 rebound
`-$87f` with sound `$1a` — dead code: there is no map 5, `hnk-system.md` §7). Bit 7 is never seen by the player probes (all masks clear it). The bomb's own update is §11.

## 11. The bomb (`$13e98`, called every frame; record `$16b12`, 88 bytes; script `$12e5e`)

Fields (record offsets): `+0` kind (0 free, 1 falling, 2 exploding), `+2` x (`[$16b14]`, the long at `[$16b14]` = x.16), `+6` y integer / `+8` fraction (`[$16b18]` long), `+$c` vy 8.8 (`[$16b1e]`),
`+$1e` animation pointer (`[$16b30]`), `+$22` anim wait (`[$16b34]`), `+$24` dx 8.8 (`[$16b36]`), `+$4c` hit-by-actor flag (`[$16b5e]`, set by `$15740`). `[$12efe]` = "explosion box active",
`[$12f00]` = explosion frame counter, `[$12f02]/[$12f04]` = explosion centre (point 2 of `algo-actors.md` §4), `[$12f06]` = platform dx (temporary).

```
[12efe] = 0 ; [12f06] = 0 ; if kind < 1: return ; if kind > 1: goto EXPLODE
FALLING (kind 1):
   if +4c != 0: goto BOOM
   $171bc(bomb)                                   # animation step; carry set (script jumped) -> BOOM
   vy = min([16b1e] + $80, $800) ; [16b1e] = vy ; [15f12] = vy
   D1 = (vy << 8) + long[16b18] ; y = D1 >> 16 ; if y > $130 or y < 0: kind = 0 ; return
   [15f10] = y ; [15f0e] = x ; [15f16] = -1 ; probe $16278 -> D7 = [15f14]                 # 8-px variant of the collision probe
   if D7 & $40:                                   # platform actor
        y = [15f18] - $10 ; [15f10] = y ; long[16b18] = y << 16 ; [12f06] = [15f1a] ; [15f16] = 0 ; probe again
        if D7 & $20: BOOM
        if D7 & 6:   goto CEIL else { vy = $100 ; goto HORIZ }
   elif D7 & 4:                     goto LAND
   elif D7 & 2:  if vy >= 0: LAND else CEIL
   else:         long[16b18] = D1 ; goto HORIZ
CEIL:  y = (y | 7) + 1 ; fraction = 0 ; store
LAND:  y = (y - 1) & ~7 ; fraction = 0 ; store                                              # $13fba
   if D7 & $20: BOOM
   if D7 & 1:  map 3: if vy >= $200: vy = -vy + $60 ; goto HORIZ   else vy = $100
               map 5: vy = -$87f                                    # dead code: there is no map 5, hnk-system.md §7
               else:  vy = $100                                     # (no D7&1: vy = $100 as well: $1401a)
HORIZ: D6 = [16b36] ; D5 = 8
   if D7 & 1: map 1 -> D6 = 0 ; map 2 -> jump to the position update at once (`$14076`: no deceleration, no store of D6, no platform dx) ; map 4 -> D5 = $10
   deceleration: D6 moves toward 0 by D5, never crossing 0
   D6 += [12f06] << 8 (platform dx)
   x_new = (long[16b14] + (D6 << 8)) >> 16 ; if x_new > $e8: x_new = $e8, [16b36] = 0 ; if x_new < 0: x_new = 0, [16b36] = 0
   probe $16278 at (x_new, y) ; if D7 & 2: x_new snapped (D6 < 0 ? (x|7)+1 : (x-1) & ~7), fraction 0
   store x ; if D7 & $20: BOOM
BOOM ($1410e): play_sound($13) ; [16b5e] = 0 ; kind = 2 ; [16b34] = 0 ; anim pointer = $12ed6 ; y -= 5 ; [12f00] = 0 ; fall into EXPLODE
EXPLODE (kind 2):
   [12f00] += 1 ; if [12f00] <= 7:  [12efe] = 1 ; [12f02] = x + $c ; [12f04] = y + $a
        box (x + $c - $10, y + $a - $e, $20, $1c) vs Rick ($14b7a): hit -> [12e2c] = -1
   $171bc(bomb) ; if carry (script finished): kind = 0
```
Read from `$13e98`–`$141ca`; the two `D7 & 1` branches on maps 3 and 5 are the same surface-property bit as for Rick and objects. Only the `[$12efe]`
flag and `[$12f02]/[$12f04]` are consumed elsewhere (`algo-objects.md` CONTACTS, `algo-actors.md` §4 point 2: bomb kills objects/actors inside its box); the deceleration
values (D5) come from the code as listed, not from a table.
