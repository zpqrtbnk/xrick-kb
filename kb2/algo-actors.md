# Rick Dangerous 2 — enemy scripts, actor update, trigger boxes (static transcription)

Transcribed on 2026-09-19 from the 68000 disassembly in Ghidra (`prg2-ram.bin`) — no decompiler. Nothing here has been run
against the live game except where a "checked" note says so; the script decoding was checked against all four level images.
Addresses are RAM addresses. Actor records are 88 bytes (`ActorRecord`); `A6` = the record. **Two tables**: types `1..$74` (monster path `FUN_000146a0`, free slot via `$14962`) go to the 6-slot **actor table `$16b6a`**, updated by `update_actor_ai`; types ≥ `$75` (`FUN_00014862`, free slot via `$14970`) go to the 4-slot **object table `$167a2`**, updated by `update_object_slots` (`FUN_000150c0`, not transcribed here).

## 1. Actor record — fields seen in these routines

| off | use (as read in the code) |
|---|---|
| `+0` word | slot state: **0 = free, > 0 = in use, < 0 = end-of-table sentinel** (`$14970` free-slot scan: `bmi` end, `beq` found). `FUN_00014862` (types ≥ `$75`) writes `b0 & 3` as a *word* here, so it lands in byte `+1` (`F`) |
| `+1` byte `F` | behaviour flags: bit 1 = frozen/flipped (`eori #2`), bits 2–5 (`& $3c`) = **mode** (`$20/$28/$2c` = static objects), bits 2–4 (`& $1c`) = **hit reaction class**, bit 6 = hurts Rick on contact, bit 7 = the actor detonates a **falling bomb** it touches (`$15776` tests the bomb record `$16b12`, not the laser shot — corrected 2026-09-23, `algo-spawn.md` §7), bit 0 = set at construction |
| `+2` / `+6` word | x / y (screen-space y: world y − `scroll & ~7`) |
| `+$e` word | current sprite frame id (`$fe` = none) |
| `+$12` word | ≠ 0 = draw with the **masked blitter** `$1952c` (sprite pixels hidden where the tile mask bitmap `$65800` is 0 — `graphics.md` §4; set to −1 from spawn byte 3 bit 7); `+$14` word = second-draw-pass flag (`$170f2`) |
| `+$16` ptr / `+$1a` word | movement-script pointer / repeat counter |
| `+$1e` ptr / `+$22` word | animation-script pointer / wait counter |
| `+$26` / `+$28` word | hit-box width / height (descriptor bytes 0 and 1) |
| `+$2a` ptr | the spawn record this actor came from (its spawned bit is cleared on despawn) |
| `+$2e` byte `S` | runtime state bits: 3, 4 = phase-swap pending, 5 = despawn at next loop wrap, 6 = swapped-out |
| `+$30` byte | **alternate `F`** ; `+$32` / `+$36` ptr = alternate movement / animation script (the "second profile") |
| `+$3a` / `+$3c` word | last (dx, dy) |
| `+$4c` / `+$4e` word | flags used by the object slots / by static actors (`+$4e ≠ 0` = dying, shows its death animation) |
| `+$54` word | for type ≥ `$75` kind 1: `((b3 & $3c) << 1) + 8` |

## 2. The two script formats

`advance_actor_move_script` (`$172fa`) and `advance_actor_anim_script` (`$171bc`). Records are big-endian words.
Decoder and data: `kb2/decode_scripts.py` → `kb2/assets/levels/scripts.json`.

**Movement** (pointer `+$16`, counter `+$1a`; returns dx, dy = signed bytes; carry set only after a jump):

```
if pointer == 0: return (0,0), carry 0
if counter == 0:
    loop:
        w = word[p]
        if w == 0:      p += signed word[p+2]         # jump, relative to this record
                        store p; return carry 1       # (dx,dy) = (0,0)
        if w == -1:     if 0x23 <= y <= 0x148: play_sound(word[p+2]); p += 4; continue
        else:           counter = w; break
dx = signed byte[p+2]; dy = signed byte[p+3]
counter -= 1; if counter == 0: p += 4
store p; return (dx,dy), carry 0
```

**Animation** (pointer `+$1e`, wait counter `+$22`; writes the frame to `+$0e`; carry set if a jump was taken):

```
if pointer == 0: return carry 0
if wait != 0: wait -= 1; return carry 0
loop:
    w = word[p]
    if w >= 0:   frame = w; p += 2; break                       # no wait
    if w == -1:  p += signed word[p+2]; carry = 1; continue     # jump, relative to this record
    if w == -3:  if 0x23 <= y <= 0x148: play_sound(word[p+2]); p += 4; continue
    else:        wait = word[p+2] - 1; frame = word[p+4]; p += 6; break   # ($fffe, ticks, frame)
return carry
```

**Checked:** all 420 monster scripts of the four maps (49+43+50+68 types × 2) decode; **every jump lands on a record
boundary of a script of the same kind** (36 of them into another script's records — shared tails); the "show" marker is
always `$fffe` (442 records); movement dx, dy are within −8..8, repeat counts 1..140, sound ids 18..47, anim ticks 2..196,
frame ids 34..254. Four **animation scripts live in the program** (`$1466e`, `$1468a`, `$14696`, `$12ed6`, decoded in
`scripts.json`): `$1466e` = frames 64,192,193,192 at 3 ticks each (loop); `$1468a` = the same frames with no wait (used on
map 4); `$14696` = frame 148 (the "500" sprite) for 12 ticks; `$12ed6` = frames 141, sound 19, 34, 142, 35, 143, 36, 144, 37,
145, 38 (kill explosion).

## 3. `update_actor_ai` (`$14d70`), transcribed

Bit names refer to `F` (`+1`) and `S` (`+$2e`). `despawn` = `$14a12` (clears `+0`; clears the source record's spawned bit
unless its byte 3 bit 6 is set = one-shot); `despawn_forced` = `$149f0` (always clears the spawned bit).

```
mode = F & 0x3c
if mode in (0x20, 0x28, 0x2c): goto STATIC
if F & 2:  (x, y) = actor position; goto CHECK          # frozen: no movement this call
MOVE:
    (dx, dy, carry) = advance_move_script()
    if carry:                                           # the script looped
        if S & 0x20: despawn; return
        if !(S & 0x10): goto MOVE
        if S & 0x08: S &= ~0x08 else S &= ~0x10
        if (F & 0x1c) == 0x14: S |= 0x20
        goto SWAP
    +3a, +3c = dx, dy;  x += dx;  y += dy
    if !on_screen(0 <= y < 0x128 and 0 <= x <= 0xe8): despawn_forced; return
    advance_anim_script()
CHECK:
    if [$12e2a] == 0 and (F & 0x40) and frame != 0xfe:
        w, h = +26, +28
        if F & 0x80: shot_object_test()                 # $15776
        mark_object_slots_touched(x, y, w, h)           # $15740: sets slot.+4c = -1 for each live object slot in the box
        if check_box_vs_player(x, y, w, h): [$12e2c] = -1          # "Rick hit"
    if S & 0x40: return
    if (S & 0x10) and (F & 0x20): return
    hit = dispatch_spawn_record(source record)          # §4: the record's trigger boxes
    m = F & 0x1c
    if not hit:
        if m == 0x1c: despawn
        return
    if m == 0x00: F ^= 2; return
    if m == 0x1c: return
    if m == 0x0c: despawn; return
    if !(m & 0x08): S |= 0x10; if F & 0x20: S |= 0x08; return
    S |= 0x40; if m & 0x10: S |= 0x20
SWAP:                                                   # $14ed4
    swap(F, byte[+30]);  swap(move_ptr, +32);  swap(anim_ptr, +36);  counters +1a = +22 = 0

STATIC:                                                 # $14f24  (pickup-type actors)
    if +4e != 0: goto DYING
    if !on_screen: despawn_forced; return
    advance_anim_script()
    if not check_box_vs_player(x, y, 0x18, 0x15):       # fixed 24 x 21 box
        if mode == 0x20: return
        if shot_point_1_in_box(...): [$115dc] = -1; goto KILLED
        if shot_point_3_in_box(...): goto KILLED
        if shot_point_2_in_box(x-0x10, y-0x0e, w+0x20, h+0x1d): goto KILLED
        return
    if mode == 0x20:  score += $500 (BCD, `$17810`); sound $15; +4e = -1; +12 = 0; anim = $14696; wait = 0; goto DYING
    if mode == 0x28:  [$176f4] = 6; [$176f2] = -1; sound $14; despawn         # HUD slot A count := 6
    else (0x2c):      [$17702] = 6; [$17700] = -1; sound $14; despawn         # HUD slot B count := 6
KILLED:  sound $13; +4e = -1; F |= 0x40; anim = $12ed6; wait = 0
DYING:   if !on_screen: despawn; return                # $15054 (note: despawn, not forced)
         advance_anim_script(); if it jumped: despawn; return
         if mode == 0x20: y -= 2 (the "500" floats up); return
         if check_box_vs_player(x, y, 0x18, 0x15): [$12e2c] = -1
```

`KILLED` and the pickup path both fall into `DYING` (`$15054`). The listing above is the complete rule set:
the `F & 0x1c` classes are fully defined by the branches (`m == 0` toggles freezing, `0x1c` despawns when not hit, `0x0c` despawns when hit, `0x14` sets `S |= 0x20` on a script loop, …); giving them
game-level names ("chaser", "shooter") has no basis in the code and is not attempted.

**kb2 gap #3 CLOSED 2026-09-22 — the type-`<0x75` monster-descriptor path (`FUN_000146a0`) fires live, exactly as decoded.** Live capture across maps 2/3/4 (`kb2/hatari_live_validate.py`, results in
`kb2/assets/live_validation_2026-09-22.json`): diffing each map's live spawn table against the pristine image found the "already spawned" bit (byte0 `0x80`) flip on real, in-range spawn records, and several of
them are genuine `type ≤ 0x74` monster-path records (e.g. map 2 types 1, 18, 19, 20, 21 repeatedly; map 3 type 17; map 4 types 19, 20) — not just the `type ≥ 0x75` pickup path the 2026-09-19 sample happened to
exercise. Separately, `PLAN.md` T24's gap #5 (broader script sampling) is closed the same way: 20 of 21 live actor-table samples across the three maps had their animation-script pointer sitting exactly on a
record boundary of a script decoded by `kb2/decode_scripts.py` (including two that only matched once the *in-program* shared scripts `$1466e`/`$14696` were included) — direct confirmation that the byte-code VM
runs exactly as transcribed. One sample (map 2, actor kind 89, frame 99) did not match any decoded boundary and is not explained; noted, not chased further (a single unexplained sample against 20 confirmed ones).

## 4. Trigger boxes: `dispatch_spawn_record` (`$14a3c`, `A0` = a spawn record, `A6` = actor or 0)

The record's **detail blocks** (`b3 & 3` of them, 4 bytes each: `d0 d1 d2 d3`) are **boxes with a condition mask**:

| field | meaning |
|---|---|
| `d0` | box x in pixels (raw) |
| `d1` | box y tile: y = `d1·8 − (scroll & ~7)`; a box above the screen is clipped (`h += y`, `y = 0`) and skipped only if `h` becomes **negative** (`h = 0` is still tested) — `algo-spawn.md` §5 |
| `d2 & 0x0f` / `d2 >> 4` | width / height in 8-px units minus 1 (`((n)+1)·8`) |
| `d3` bits 0–5 | which tests apply (below); any hit fires the block |
| `d3` bit 6 | repeatable — the block is not latched |
| `d3` bit 7 | runtime **latched** flag (set on first fire unless bit 6; a latched block does not fire again; cleared when no test hits; a latched block that hits again is ignored **without** being cleared, and the scan moves on to the next block; the sound `$17` is tied to mask bit 3, whichever test fired — `algo-spawn.md` §5) |

Tests (each returns carry = hit): bit 0 = `check_box_vs_player` (Rick's box: x `[Rx+4, Rx+$14)`, y `[Ry, Ry+$15)` standing or
`[Ry+5, Ry+$15)` crouching, and never while `[$12e2a] ≠ 0`); bit 1 = shot point `([$12efa],[$12efc])` in the box, only while
`[$16902] ≠ 0` — a hit sets `[$115dc] = -1`, and `game_main` then clears `[$16902]` (**the shot is consumed**); bit 2 = point
`([$12f02],[$12f04])` while `[$16b12] ≠ 0` and `[$12efe] ≠ 0`; bit 3 = point `([$12ef6],[$12ef8])` while `[$12ef4] ≠ 0`, and
**firing it plays sound $17**; bit 4 = any of the 4 object slots (`$167a2`, skipping the caller and slots with `+4e ≠ 0`) overlaps
the box; bit 5 = any live actor (`$16b6a`, 6 slots, skipping the caller) overlaps it, using its `+26/+28` size.
A block fires → the whole call returns carry 1; no block fires → carry 0.

**Use in the spawn scan** (`$14594`): a record with `b2` bit 7 **clear** is a *trigger record*: `dispatch_spawn_record` is called with
`A6 = 0`; if a box fires, the record's type (`b0`) is **spawned** through `$14636` (so it is "spawn an enemy/effect when Rick
enters / shoots / drops something into this box"). Records with `b2` bit 7 set spawn when they scroll into range. Type `$78`
starts the bonus countdown (`$157be`: active flag `[$157ac]`, bonus `[$157b0] = $2000` BCD, timer `[$157ae] = $19`, sound $11);
type `$7c` (`$157f4`) stops it, adds the bonus to the score, plays sound 1 and marks the record spawned.

## 5. HUD counters (static)

Three 14-byte text-slot records at `$176f2`, `$17700`, `$1770e` (values read from the RAM **snapshot** — the pristine program has count 0 in all three, set by `$1771c`/`$17760` before first use; `algo-flow.md` §13): pending flag `+0`,
count `+2`, column `+4`, glyph `+5`, then the glyph buffer. Slot A: count 6, column 13, glyph `$0a` (lightning bolt); slot B:
count 5, column 21, glyph `$0b`; slot C: count 5, column 30, glyph `$0c` (Rick's head). `FUN_00017760` resets A and B to 6 at
every level start; pickups of mode `$28` / `$2c` set them to 6. Score pickup mode `$20` = 500 points. Roles read in
`algo-player.md`: **slot A (bolts) = laser shots left** (decremented by `$13d58`), **slot B = bombs left** (decremented when a bomb
is thrown), **slot C (`count` at `$17710`) = lives** (decremented at Rick's death, `$13a84`).

## 6. Tile + actor collision probe (`query_tile_and_actor_collision`, `$15fba`)

Inputs: `[$15f0e]` = x, `[$15f10]` = y, `[$15f12]` = vertical velocity (sign used), `[$15f16]` = also test actors. Outputs: `[$15f14]` =
combined flag byte, `[$15f18]` = y of a platform actor found, `[$15f1a]`/`[$15f1c]` = that platform's last (dx, dy) (`actor +3a/+3c`).
Tile ids come from the window (`compute_tile_map_ptr` `$1643e` → `$65300 + (Y & ~7)·4 + (X + 4) >> 3`, row pitch 32); each id
is looked up in the 256-byte **attribute table at `$65200`** (image `0x11e00`; per-map values in
`kb2/assets/levels/tile_attributes.json`; values used: `00 02 03 04 08 1c 20 80 82 84`, bit 7 is always masked out below).

- Rows probed: 4 if `(Y & 7) >= 4`, else 3 body rows, plus one **feet row**; columns: 2 if `(X+4) & 7 == 0`, else 3.
- **Aligned** (2 columns): body rows OR both tiles, keep `& $2a` (bits 1, 3, 5); feet row OR both, keep `& $7f`.
- **Unaligned** (3 columns): body rows: outer columns `& $22` (bits 1, 5) and the middle column `& $2a`; feet row: outer
  columns OR'd and kept `& $27` (bits 0, 1, 2, 5), middle column `& $7f`.
- If `[$15f12] < 0` (moving up) bit 2 (`$04`) is cleared. `FUN_00016278` is the same with 8-px offsets and masks `$23/$27/$2b`.
- **Actors** (only when `[$15f16] != 0`; walks `$16b6a` until the sentinel, skipping free slots): an actor whose byte `+1` bit 7 is set
  is solid: if bit 6 is also set its box (`+2,+6,+26,+28`) is tested against the probe box (16 wide at `x+4`, height `[$161cc]` = 21);
  overlap sets flag bit 1, and if this actor is the highest so far (`actor.y <= [$15f18]`) and the probe's feet (`y + $14`) are not
  below `actor.y + vy + 8`, also flag bit 6 with `[$15f18] = actor.y` and platform (dx, dy) = (0, 0). With bit 6 clear the actor is a
  one-way platform only while `[$15f12] >= 0`: a 16 × 1 strip at the probe's feet overlapping the actor's box **narrowed to height = (high byte of `[$15f12]`) + 8** (not the actor's own `+28`) sets flag bit 6, `[$15f18] = actor.y`
  and the platform (dx, dy) = the actor's last movement (`+3a`, `+3c`).
- **Reaction of the object code** (`FUN_000150c0`): flag bit 5 destroys the object, bit 6 = landed on ground/platform, bits 2 and 1 =
  slopes/walls that reset its vertical speed.

**Attribute bits as consumed** (from the transcribed player, object and bomb code — `algo-player.md` §10, `algo-objects.md`, `algo-player.md` §11): bit 5 (`20`) kills / destroys, bit 6 (`40`) = standing on a platform actor,
bit 1 (`02`) solid (blocks sideways movement, head), bit 2 (`04`) floor (feet row), bit 3 (`08`) ladder tile present, bit 4 (`10`) ladder-top entry, bit 0 (`01`) per-map surface property (map 1 jump `-$200`, map 2 conveyor,
map 3 bounce, map 4 walk speed 1, map 5 rebound), bit 7 (`80`) never seen by these consumers (all masks clear it). Observations on which tiles carry them: bit 1 (`02`) orange girder tops and rock, bit 5 (`20`) a single rare tile
per map (a blue checker tile on map 1), `04`/`08`/`1c` ladder-like and metal edge tiles, bit 7 most background panels. The per-map values are in `assets/levels/tile_attributes.json`.

**kb2 gap #7 CLOSED 2026-09-22 — every live `[$15f14]` value seen decomposes exactly into the bits above, no exceptions.** 120 live samples of the probe's result byte (`kb2/hatari_live_validate.py`, chained
one-shot breakpoints on this routine's single `rts` at `$161c8`, spread across maps 2/3/4 during real attract-mode play): the distinct values seen were `0x00, 0x02, 0x03, 0x06, 0x07, 0x08, 0x0a, 0x1c, 0x1f`
(`kb2/assets/live_validation_2026-09-22.json`). Every one of these is a combination of bits 0–4 only — e.g. `0x1c` = bits 2+3+4 (floor + ladder-present + ladder-top, the exact combination `algo-player.md` §10
predicted for a ladder-top entry) and `0x1f` adds bit 0+1 on top (an adjacent solid/surface-property column OR'd in, per the unaligned-probe rule above). No sample ever set bit 5, 6 or 7 in this particular
capture window (not a contradiction — just situations this 28-second-per-map sample didn't happen to hit), and none ever showed a bit outside the documented 0–4 set.

## 7. Instruction-level companions (2026-09-23)

The collision probe, every box/point test and its comparison strictness: `algo-collision.md` (note: the crouching
edge of `check_box_vs_player` is **inclusive**, `algo-collision.md` §8 — §4 above gives half-open ranges that are
imprecise on that one edge). Spawn scan, constructors, free-slot/despawn, `dispatch_spawn_record`, script steppers:
`algo-spawn.md`. `update_actor_ai` (§3) was re-read against the disassembly on 2026-09-23 and matches on every branch.
