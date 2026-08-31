# Rick Dangerous — Entity/Sprite Type System

**Role: the entity type → handler index.** All **74** dispatch types are
behaviourally characterised. This file maps *type → address → handler → one-line
behaviour*; the exact algorithms live in
[`algo-entities.md`](algo-entities.md) and [`algo-player.md`](algo-player.md), and
field layouts in [`data-structures.md`](data-structures.md).

> **Authority order:** Ghidra → `algo-*.md` → this file. Keep derived detail out of
> here; duplicated behaviour is what caused this document to drift in earlier passes.

## sprite_type_dispatch (0x4AAE0, `pointer[74]`, 296 bytes)

> ⚠️ **Corrected 2026-08-28: 74 entries, not 70.** Earlier passes cut the table short
> at `0x4ABF8` because a spurious `hide_entity` function had been created there; those
> bytes are really **indices 70–73** (= types 71–74). The last entry is at `0x4AC04`;
> real code starts at `0x4AC08`. This also explains why `ObjectTypeDef` held real data
> for types 71–74 — they do have handlers: indices 70–72 (types 71–73) are
> `scripted_trap_update`, and index 73 (type 74) is `decorative_sprite_update`.
>
> **Re-verified 2026-08-29** by dumping all 74 pointers from `atari_ram.bin`. The whole
> table decomposes into exactly the runs tabulated below, with no gaps and no surprises.

Function-pointer array, indexed by `SpriteEntity.wType - 1`. Called from
`render_sprites` for every active slot in `sprite_list`.

| Type | Address | Name | Behavior (confidence) |
|------|---------|------|------------------------|
| 1 | `0x4C046` | `player_controller` | Rick (`sprite_list[1]`): input, jump physics, firing. **Confirmed** |
| 2 | `0x4CA5A` | `player_bullet_update` | Bullet, always slot `[2]`. 8px/frame along X, leading-edge probe at `bullet_point_x`/`_y` (`0x4BF24`/`0x4BF26`); **no range budget** — it dies on hitting tile attr 0x40 or the slot-0 block. Spawned by `player_controller` consuming `HudCounters.bBullets`. **Confirmed** |
| 3 | `0x4CAA8` | `player_dynamite_update` | Dynamite, always slot `[3]`. Fuse anim (table `0x46BF2`) → explosion (table `0x46C3E`), publishes `explosion_x/y/active`; lethal to the player too. Consumes `HudCounters.bDynamite`. **Confirmed** |
| 4–15 | `0x4D39C`… | `enemy_update_4`..`15` | 12 trivial wrappers over **`enemy_ai_update`** (`0x4D4F4`). Each selects a sprite bank: types {4,5,6}=bank 0, {7,8,9}=0xD20, {10,11,12}=0x1A40, {13,14,15}=0x2760 (4 visual variants); the first two of each triple switch to an alt bank (0x8B20 base, 0xA80 stride) when `bTriggerFlags` bit 7 is set. **The 3 sub-types per visual are *not* interchangeable**: each wrapper passes a distinct `D0.b` **AI mode** — 0 = step-counted patrol, 1 = player-seeking, 2 = random + the only chase-capable mode (`move.b #0/1/2,D0b` at `0x4D39C`/`0x4D3BE`/`0x4D3E0`). Only the mode-0 and mode-1 wrappers carry the bit-7 alt-bank test; mode-2 has none. **Confirmed** (wrappers); AI details in `algo-entities.md` §3 |
| 16–17 | `0x4D00C`/`0x4D020` | `destructible_pickup_16`/`17` | Crates/pots: destroyed by stick/bullet/explosion (destruction anim then despawn — the anim frames kill the player on touch), or touch-collected → per-instance A2 callback (refill effect — the `lea <effect>,A2` load; see *Effect callbacks* in `data-structures.md`). `mark_placement_dead` on both paths. **Confirmed** |
| 18–21 | `0x4D0E2`…`0x4D0FA` | `treasure_pickup_18`..`21` | Score treasures: gfx = `type*0x150 + 0x2F70E` (shared sprite sheet — anchor into the graphics blob). Touch → `add_score`, 12-frame sparkle (gfx `0x3822E`), despawn. **Confirmed** |
| 22–23 | `0x4BE68`/`0x4BEA2` | `trigger_zone_22`/`23` | Invisible trigger points (gfx=0): player enters trigger box → despawn + A2 event callback (the `lea <effect>,A2` load: type 22 starts the escape timer, type 23 stops it and banks the remaining time; see *Effect callbacks* in `data-structures.md`), one-shot when `bTriggerFlags` bit 0. Identical wrappers; difference is data-side. **Confirmed** (mechanism) |
| 24–73 | `0x4D15C` | `scripted_trap_update` (ex `entity_update_default`) | Shared **data-driven trap/hazard handler** (50 types): idle until triggered by player-touch (bit 0x80), stick (0x40), bullet (0x20), or explosion (0x10) per `bTriggerFlags`; bits 8/4 = "always lethal" (sets `wHazardActive`, kills player on overlap). Triggered → animation (`anim_frame_table`) + scripted movement (`movement_path_table`, 6-byte `{duration,dX,dY}` records), then reset-to-spawn or permanent despawn (bit 0). **Confirmed** |
| 74 | `0x4B856` | `decorative_sprite_update` | Drives slot `[12]` (intro-screen decorations): own 10-byte path format with per-step anim-table swap; no collision/triggers. The **last** table entry, dispatch index 73 at `0x4AC04`. **Confirmed** |

*(This row was labelled "70" until 2026-08-29. It is **type 74** — dispatch index 73 —
which is why `sprite_list[12]` is described elsewhere as "the type-74 decorative
sprite". Type 70 is an ordinary `scripted_trap_update` entry inside the 24–73 run.)*

**Not part of the dispatch table**, adjacent: `hide_entity` (`0x4AC08`) — clears the
draw-enable bit on both render-flag bytes. *(Not `0x4ABF8`; that address is dispatch
index 70, and the spurious function once created there is what truncated the table.)*

## Shared enemy AI (`enemy_ai_update`, 0x4D4F4 — types 4–15)

Three AI modes, selected by the `D0.b` argument each type wrapper passes (the
decompiler hides this `move.b`, so read the disassembly):

| Mode | Behaviour |
|---|---|
| 0 | step-counted patrol |
| 1 | player-seeking |
| 2 | random turns; the only chase-capable mode |

Plus a shared death-tumble state. **Exact thresholds, gravity constants, turn rules
and frame tables: [`algo-entities.md`](algo-entities.md).**

## Collision/interaction helper suite (all renamed this pass)

| Address | Name | Role |
|---------|------|------|
| `0x4D986` | `trigger_box_contains_point` | point vs. entity trigger box (`nTrigBoxXMin`..`nTrigBoxYMax`, 0x3C–0x42) |
| `0x4D9AA` | `entity_overlaps_player` | entity hitbox (`nHitboxW/H` @0x10/0x12) vs. Rick (crouch-adjusted) |
| `0x4CC4C` | `entity_contains_point` | generic point-in-hitbox; wrappers: `stick_attack_hits_entity` (`0x4CBF0`), `bullet_hits_entity` (`0x4CC10`, destroys the bullet on hit) |
| `0x4CC92` | `explosion_overlaps_entity` | entity vs. explosion center (`explosion_x/y`), ~31×28 box |
| `0x4CCFC` | `bullet_hit_solid_test` | bullet vs. tile attr 0x40 / slot-0 block |
| `0x4CD70` | `probe_player_tile_collision` | player footprint vs. `room_tile_map` attrs → `player_collision_flags`; captures ceiling bit into `0x4D00B` when crouching |
| `0x4DA40` | `probe_entity_tile_collision` | enemy version → `tile_probe_result`; **returns no register value** — the epilogue restores D0–D7/A0–A1, so the only outputs are the carry flag (`blocked`) and that global |
| `0x4DA30` | `mark_placement_dead` | sets bit 7 in placement-record byte +2 → no respawn on room re-entry |
| `0x4D87C` | `kill_enemy` | dying state + upward launch + `add_score(0x50)` + track `0x13`. **On the explosion path the 0x50 is awarded twice** — `enemy_ai_update` adds one at `0x4D548` before calling this, which adds another |
| `0x4D8B0` | `entity_touches_hazard_or_block` | overlap vs. slot 0 or any hazard-active slot 4–8 |
| `0x4C7E4` | `kill_player` | `player_dying`=0xFF, `bLives`–1, death bounce |
| `0x4C846` | `player_death_physics` | tumbling body (gravity + wall-bounce X drift) |
| `0x4C8B2` | `player_sprite_update` | lethal-tile check → `kill_player`; selects Rick's sprite frame from state flags (tables `0x46B96`–`0x46BE6`; +0xFC0 = left-facing bank) |
| `0x4C8C2` | `player_select_anim_frame` | same selector without the lethal-tile check (death path) |

## Slot assignments (confirmed)

`[0]` **scripted moving hazard** — crusher/boulder; solid *and* lethal, moved by
`scripted_trap_update`'s path stepping, **not** pushable (see `data-structures.md`) ·
`[1]` Rick · `[2]` bullet · `[3]` dynamite · `[4..8]` hazard-capable level entities
(scanned by `entity_touches_hazard_or_block`) · `[9..11]` more level entities ·
`[12]` decorative sprite (type 70).

## What's still open

The placement-record format, the object-type table, the dispatch-table extent and the
slot-0 question have all been resolved — see `../PLAN.md`'s appendix for that
history rather than keeping strikethroughs here. Genuinely open:

1. **Trigger-bit semantics in live play** — the bit meanings are read off the code with
   confidence and the census below shows every bit is exercised in shipped data, but no
   bit has been observed firing in a running game. (`PLAN.md` T6.)
2. ~~`ObjectTypeDef` entries with no placement record referencing them — unused content
   versus types only reachable via paths not yet traced.~~ ✅ **RESOLVED 2026-08-30 by
   census.** Walking all 523 placement slots (476 records + 47 terminators) and
   collecting `bTypeAndDead & 0x7F` yields **70 distinct types**. The four types of
   1–74 that never appear are exactly **1, 2, 3 and 74** — player, bullet, dynamite and
   the decorative sprite — and every one of those is **spawned by code, not by
   placement data**: `spawn_player_entity` for 1, `player_controller` for 2 and 3, and
   slot 12 / the intro screens for 74. No type is referenced outside 1–74.
   **So there is no unused content and no untraced path**; the table is exactly as
   large as it needs to be.

Two former entries here are now **resolved** and have moved to their owning documents:
the full **tile-attribute bit set**, including the `0x6F` row-filter mask and the
correction of `0x20` from "landable floor" to **bounce surface**, is in
`data-structures.md`; the **enemy-variant → creature mapping** is in the table below.


---

## Enemy visual variants — resolved 2026-08-29

Placement scan over all 476 records, plus rendering each bank
(`hatari/enemy_banks.png`). The Egypt identification was **visually confirmed by the
user**; the others follow from the same rendered sheet. The three AI modes inside each
triple share a bank and are
visually identical — **the creature is determined by the triple, i.e. by the level**;
`aiMode` changes only behaviour.

| Types | Bank | Creature | Levels used in |
|---|---|---|---|
| 4, 5, 6 | `0x0000` | hunched **tribesman** with headdress, orange/brown | South America (rooms 0–8) |
| 7, 8, 9 | `0x0D20` | **guard in white robe with red fez** ✅ *user-confirmed* | Egypt (rooms 9–19) |
| 10, 11, 12 | `0x1A40` | **green-helmeted soldier** | Castle (20–37) *and* Missile Base (38–46) |
| 13, 14, 15 | `0x2760` | **second green soldier variant** | Castle (type 14 only) and Missile Base |

Alt banks (`0x8B20` + `0xA80` stride), selected when `bTriggerFlags` bit 7 is set on
the placement, hold a visually different creature per slot — bank `0x8B20` renders an
orange animal-like figure rather than a humanoid.

Levels do **not** each get their own enemy art: Castle and Missile Base share both
green-soldier banks, which is why only two distinct guard sprites cover 27 rooms.

## `bTriggerFlags` — every bit is exercised

Census over all 476 placement records. No bit is dead, and all four levels use all
eight, so none of the transcribed semantics describes an unreachable path.

| Bit | Uses | S.America | Egypt | Castle | Missile |
|---|---|---|---|---|---|
| `0x01` | 84 | 13 | 21 | 34 | 16 |
| `0x02` | 26 | 6 | 11 | 4 | 5 |
| `0x04` | 73 | 15 | 24 | 14 | 20 |
| `0x08` | 189 | 37 | 59 | 43 | 50 |
| `0x10` | 117 | 21 | 21 | 49 | 26 |
| `0x20` | 86 | 13 | 17 | 37 | 19 |
| `0x40` | 93 | 14 | 19 | 41 | 19 |
| `0x80` | 238 | 47 | 62 | 65 | 64 |

The commonest whole-byte values are `0x88` (×102), `0xF0` (×70), `0x00` (×167) and
`0x8C` (×26). This establishes **reachability**, not semantics: the meanings still come
from the code transcription in `algo-entities.md`. A dynamic spot-check of one bit
would be a useful confirmation but the risk of misreading is now low.
