# Rick Dangerous 2 — spawn machinery, script steppers, chain helpers, bonus timer (transcribed)

Written 2026-09-23 to close `port-rd2.md` §5.B. Read instruction by instruction in Ghidra (`prg2-ram.bin`,
`disassemble_bytes` over `$14542`–`$14d6f`, `$1704c`–`$17393`, `$15740`–`$15869`) — no decompiler. Collision/box tests
used below are in `algo-collision.md`. Carry = boolean return. All tables (`$14594` scan, trigger boxes, …) are read from the
**working copy** of the level image at `$53400` (runtime bits are written into it — see §9).

## 1. Seek the spawn table (`$14542`)

```
A0 = [$144c4]                           # the current submap's spawn table (set by $14458)
if A0 == 0: goto STORE
while byte[A0] != 0:
    if byte[A0+1] * 8 >= [$16462]: break   # first record whose y (tile*8) is at or below the scroll
    A0 += 4 + 4 * (byte[A0+3] & 3)
STORE: [$144c8] = A0                    # working pointer of the per-frame scan
```

## 2. Per-frame spawn scan (`scan_enemy_spawn_list`, `$14594`)

```
if [$144c2] != 0:                                    # 5-actor group armed (algo-flow.md §10)
    if word[$16b6a] == 0: init_actor_group()          # $15b3c, only while actor 0 is free
    return
A0 = [$144c8] ; if A0 == 0: return                     # the pointer is NOT advanced by the scan
limit = [$16462] + $128
loop:
    b0 = byte[A0] ; if b0 == 0: return
    y = byte[A0+1] * 8 ; if y >= limit: return
    if b0 & $80: goto NEXT                            # already spawned
    if byte[A0+2] & $80:                              # actor record
        if [$14592] != 0: SPAWN ; goto NEXT            # forced (level start / transition)
        d = y - [$16462]
        if d < $28 or d >= $110: SPAWN                 # only while it is off-screen (outside [$28, $110))
        goto NEXT
    else:                                             # trigger/effect record
        if dispatch_spawn_record(A0, A6 = 0): SPAWN   # §5; carry = a box fired
NEXT: A0 += 4 + 4 * (byte[A0+3] & 3) ; goto loop
SPAWN = $14636 (§3)
```

## 3. Spawn dispatch (`$14636`)

`D0 = byte[A0]` (bit 7 is clear here): `$78` → bonus start `$157be` (§8); `$7c` → bonus stop `$157f4` (§8);
`1 ≤ D0 ≤ $74` → monster constructor `$146a0` (§4); anything else (`> $74`) → object constructor `$14862` (§4b).

## 4. Monster constructor (`$146a0`) — into the 6-slot actor table

```
A6 = free_actor_slot()            # $14962: scan $16b6a..+5*$58: word<0 -> fail, word==0 -> found
if none: return
byte[A6+$2e] = 0 ; long[A6+$2a] = A0
mode = byte[A0+3] & $3c
if mode == $20: STATIC(anim = [$1239c]==4 ? $1468a : $1466e, frame = $40)
if mode == $28: STATIC(anim = 0, frame = $27)
if mode == $2c: STATIC(anim = 0, frame = $28)
A1 = $53400 + 2*((b0 & $7f) - 1) ; A1 += sext(word[A1])          # the descriptor
word[A6+$26] = byte[A1] ; word[A6+$28] = byte[A1+1]
hi = byte[A1+2] & $c0
if mode == $10: byte[A6+$2e] = $60 ; if byte[A0+3] & $40: long[A6+$2a] = 0
F = mode | 1 | hi ; byte[A6+1] = F                # the +0 word becomes $00F (free-slot test found it 0)
byte[A6+$30] = (F & $3f) | (byte[A1+2] << 2)       # byte arithmetic: bits 0-5 of A1[2] land in bits 2-7
long[A6+$16] = A1 + sext(word[A1+4]) ; word[A6+$1a] = 0
long[A6+$1e] = A1 + sext(word[A1+6]) ; word[A6+$22] = 0
advance_anim_script(A6)                           # $171bc, see §6: sets the first frame (+ plays sound records)
long[A6+$1e] = A1 + sext(word[A1+6]) ; word[A6+$22] = 0   # D0 still holds this pointer ($171bc preserves D0):
                                                  # the pointer and wait are RESET to the script start
long[A6+$32] = A1 + sext(word[A1+8]) ; long[A6+$36] = A1 + sext(word[A1+10])
COMMON:
    word[A6+2] = (byte[A0+2] & $1f)*8 + (byte[A0+2] & $20 ? 4 : 0)
    word[A6+6] = byte[A0+1]*8 - ([$16462] & ~7) + (byte[A0+2] & $40 ? 3 : 0)
    word[A6+$10] = word[A6+$14] = 0 ; word[A6+$12] = (byte[A0+3] & $80) ? -1 : 0
    byte[A0] |= $80                                # spawned
STATIC(anim, frame):                               # $14800/$14810/$14820
    long[A6+$1e] = anim ; word[A6+$e] = frame ; word[A6+$22] = 0
    word[A6+0] = mode                              # so F (byte +1) = mode, high byte 0
    word[A6+$4e] = 0 ; goto COMMON                 # +$26/+$28 not written (the static path uses a fixed 24x21 box)
```
**Correction to the earlier reading:** the constructor calls the animation step once, then puts the animation pointer
and wait counter back to the script start. So only the first frame is applied, and any sound record the script
starts with plays at spawn time.

## 4b. Object constructor (`$14862`) — into the 4-slot object table

As transcribed in `algo-objects.md` (re-read 2026-09-23, matches): `A6 = free_object_slot()` (`$14970`: `$167a2`, 4 slots,
same free/sentinel test); `+4c = +4e = 0`; `+0 = b0 & 3` (**word**; may be 0, leaving the slot free);
`+e = +3e = word[$14854 + (((b0 & $c) - 4) >> 1)]` (`lsr.b`; table `0041 004b 00c2`, the 4th word overlaps the byte table
`$1485a`); kind 1: `+54 = ((b3 & $3c) << 1) + 8` (byte arithmetic), `+52 = 0`; `+8 = 0`, `+c = $100`, `+a = 2`,
`+42 = +44 = +46 = +48 = +50 = +4a = +56 = 0`; `+2` as COMMON above; `+6 = b1*8 - (scroll & ~7) + 3` (always `+3`);
`+10 = +14 = 0`, `+12 = b3 bit 7 ? -1 : 0`; `+2a = A0`; `b0 |= $80`.

## 5. `dispatch_spawn_record` (`$14a3c`, A0 = record, A6 = calling actor or 0) — trigger boxes

```
n = byte[A0+3] & 3 ; if n == 0: return miss
A1 = A0 + 4
repeat n times:                                   # one 4-byte box d0 d1 d2 d3
    h = ((d2 >> 4) + 1) * 8 ; w = ((d2 & $f) + 1) * 8 ; x = d0
    y = d1*8 - ([$16462] & ~7)
    if y < 0: h += y ; if h < 0: goto CLEAR ; y = 0    # clipped at the top; skipped only if h goes NEGATIVE
    if d3 & $01 and check_box_vs_player(x, y, w, h): HIT
    if d3 & $02 and point1_in_box(...):  [$115dc] = -1 ; HIT
    if d3 & $04 and point2_in_box(...):  HIT
    if d3 & $08 and point3_in_box(...):  HIT
    if d3 & $10: for each of the 4 object slots: if +0 != 0 and slot != A6 and object_in_box(slot): HIT
    if d3 & $20: for each of the 6 actor slots:  if +0 != 0 and slot != A6 and actor_in_box(slot):  HIT
CLEAR: d3 &= ~$80 ; A1 += 4 ; next box            # a box that does not hit is UN-latched
return miss
HIT:                                              # $14b40
    if d3 & $80: A1 += 4 ; next box               # already latched: ignored (and NOT un-latched), keep scanning
    if d3 & $40: return hit                       # repeatable: no latch, no sound
    d3 |= $80
    if d3 & $08: play_sound($17, 0)               # tied to the MASK bit 3, whichever test actually fired
    return hit
```
(Tests: `algo-collision.md` §7–§10.)

## 6. Script steppers

**Animation `$171bc`** (A6 = record; preserves D0/D1/A0; carry = a jump was taken) — `algo-actors.md` §2 is exact.
Sound records play only while `0x23 <= y <= 0x148` (`blt`/`bgt`), with D1 = 0.

**Movement `$172fa`** (returns D0 = dx, D1 = dy, sign-extended; carry after a jump) — `algo-actors.md` §2 is exact;
on a jump it returns D0 = D1 = 0.

**Group/scene movement `$1726e`** (used by the 5-actor group and the scene runner) — **different from `$172fa`**:
```
D0 = D1 = 0 ; if long[+16] == 0: return carry 0
A0 = long[+16]
loop:
    if word[+1a] == 0:
        if word[A0] < 0:                            # ANY negative word is a sound record here, not only -1
            if 0x23 <= y <= 0x148: play_sound(word[A0+2], 0)
            A0 += 4 ; continue
        word[+1a] = word[A0]
    D0 = sext(byte[A0+2]) ; D1 = sext(byte[A0+3])
    word[+1a] -= 1
    if word[+1a] != 0: long[+16] = A0 ; return carry 0
    A0 += 4
    if word[A0] != 0: long[+16] = A0 ; return carry 0
    A0 += sext(word[A0+2]) ; long[+16] = A0 ; return carry 1   # jump taken EAGERLY, with this step's dx/dy
```

## 7. Chain helpers

- `$1704c` (A6 = first record): for each record until a negative `+0` word: `+0 = 0`, `+16 = 0` (long), `+1a = 0`, `+1c = 0`,
  `+1e = 0` (long), `+22 = 0`, `+10 = 0`. (Clears **every** record, free or not, including `+1c`.)
- `$171a4` (D0): for every record of the chain from `$167a2` whose `+0 != 0`, `+6 += D0`.
- `$14998` "off-screen": carry iff `y < 0` or `y >= $128` or `x < 0` or `x > $e8` (signed).
- `$149f0` despawn (forced): if `+0 != 0`: `+0 = 0`; if `+2a != 0`: clear bit 7 of `byte[+2a]` (the spawn record becomes spawnable again).
- `$14a12` despawn: same, but the spawn record's bit is cleared only if its `byte[+3]` bit 6 is **clear**.
- `$149c2`: `$149f0` on the 4 object slots then on the 6 actor slots.
- `$14d48` update actors: if `[$144c2]` return; for the 6 slots from `$16b6a`: if `+0 != 0`: `update_actor_ai` (`$14d70`,
  `algo-actors.md` §3 — re-read 2026-09-23 against the disassembly, every branch matches).
- `$15740` (box D0..D3 = the calling actor's): for each object slot with `+0 != 0`, `+4e == 0`, `+4c == 0`: if
  `object_in_box`: `+4c = -1`.
- `$15776` (box D0..D3): **tests the falling bomb, not the laser** — if `word[$16b12] == 1` and
  `aabb_overlap(box, (bomb.x+8, bomb.y, 8, $10))`: `word[$16b5e] = -1` (the bomb's `+4c`, which makes it explode).
  Called only when the actor's F bit 7 is set. (`algo-actors.md` §1 called this "extra check against the shot object" —
  corrected there.)

## 8. Bonus timer (`$157b4`/`$157be`/`$157f4`/`$15826`) — `algo-flow.md` §7 is exact; detail:

`$15826` subtracts with `sbcd` only the **two low BCD bytes** `$157b2/$157b3` of the long `[$157b0]` (X cleared first,
`andi #$ee,ccr`), from the constant bytes `$1586c/$1586d` = `00 10`; a borrow out of `$157b2` is lost. It then tests the
whole long for zero.

## 9. Runtime state inside the level image

`$14594`/`$146a0`/`$14862` set bit 7 of spawn byte 0; `$14a3c` sets/clears bit 7 of box byte 3; `$149f0`/`$14a12` clear
spawn bits. All of these write **into the level image at `$53400`**. That image is re-depacked from the file only when
the map number changes (`$123b0`, `algo-flow.md` §5), so dying and respawning on the same map **keeps** the spawned/
latched bits, apart from what the despawn routines clear. A port must hold a mutable copy of the image per load.

`$144d6` (count N from the word table `$144cc` = `9, 13, 10, 13, 8` indexed by `[$1239c]-1`; `dbf` from N-1 down to 0
calls `$14500(submap)`: for the spawn table `$54c00 + word[$54c00 + 8·submap + 6]`, clear bit 7 of byte 0 of every record,
stepping `4 + 4·(b3 & 3)`, until byte 0 == 0). **Corrected 2026-09-24: it is called** by `bsr.w` at `$123be` in
`load_map_if_changed` when the map is unchanged (`algo-flow.md` §13). The earlier "dead code" verdict missed it because Ghidra
had skipped those 6 bytes and the call is PC-relative; a byte scan of every undecoded gap in `$10000`–`$1a51f` found no other
undocumented call. So a new game on the already loaded map (and every demo, which replays the loaded map) re-arms the
spawn records of the first N submaps, not the others; box latches (bit 7 of box byte 3) are not touched.
