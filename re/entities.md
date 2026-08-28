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
> bytes are really entries 70–73. The last entry is at `0x4AC04`; real code starts at
> `0x4AC08`. This also explains why `ObjectTypeDef` held real data for types 71–73 —
> they do have handlers (all `scripted_trap_update`).

Function-pointer array, indexed by `SpriteEntity.wType - 1`. Called from
`render_sprites` for every active slot in `sprite_list`.

| Type | Address | Name | Behavior (confidence) |
|------|---------|------|------------------------|
| 1 | `0x4C046` | `player_controller` | Rick (`sprite_list[1]`): input, jump physics, firing. **Confirmed** |
| 2 | `0x4CA5A` | `player_bullet_update` | Bullet, always slot `[2]`. 8px/frame along X, leading-edge probe at `bullet_point_x`/`_y` (`0x4BF24`/`0x4BF26`); **no range budget** — it dies on hitting tile attr 0x40 or the slot-0 block. Spawned by `player_controller` consuming `HudCounters.bBullets`. **Confirmed** |
| 3 | `0x4CAA8` | `player_dynamite_update` | Dynamite, always slot `[3]`. Fuse anim (table `0x46BF2`) → explosion (table `0x46C3E`), publishes `explosion_x/y/active`; lethal to the player too. Consumes `HudCounters.bDynamite`. **Confirmed** |
| 4–15 | `0x4D39C`… | `enemy_update_4`..`15` | 12 trivial wrappers over **`enemy_ai_update`** (`0x4D4F4`). Each selects a sprite bank: types {4,5,6}=bank 0, {7,8,9}=0xD20, {10,11,12}=0x1A40, {13,14,15}=0x2760 (4 visual variants); the first two of each triple switch to an alt bank (0x8B20 base, 0xA80 stride) when `bTriggerFlags` bit 7 is set. The 3 sub-types per visual decompile identically — differences come from placement data. **Confirmed** (wrappers); AI details below |
| 16–17 | `0x4D00C`/`0x4D020` | `destructible_pickup_16`/`17` | Crates/pots: destroyed by stick/bullet/explosion (destruction anim then despawn — the anim frames kill the player on touch), or touch-collected → per-instance A2 callback (refill effect; callback source untraced). `mark_placement_dead` on both paths. **Confirmed** |
| 18–21 | `0x4D0E2`…`0x4D0FA` | `treasure_pickup_18`..`21` | Score treasures: gfx = `type*0x150 + 0x2F70E` (shared sprite sheet — anchor into the graphics blob). Touch → `add_score`, 12-frame sparkle (gfx `0x3822E`), despawn. **Confirmed** |
| 22–23 | `0x4BE68`/`0x4BEA2` | `trigger_zone_22`/`23` | Invisible trigger points (gfx=0): player enters trigger box → despawn + A2 event callback (level exit / event; callback source untraced), one-shot when `bTriggerFlags` bit 0. Identical wrappers; difference is data-side. **Confirmed** (mechanism) |
| 24–73 | `0x4D15C` | `scripted_trap_update` (ex `entity_update_default`) | Shared **data-driven trap/hazard handler** (50 types): idle until triggered by player-touch (bit 0x80), stick (0x40), bullet (0x20), or explosion (0x10) per `bTriggerFlags`; bits 8/4 = "always lethal" (sets `wHazardActive`, kills player on overlap). Triggered → animation (`anim_frame_table`) + scripted movement (`movement_path_table`, 6-byte `{duration,dX,dY}` records), then reset-to-spawn or permanent despawn (bit 0). **Confirmed** |
| 70 | `0x4B856` | `decorative_sprite_update` | Drives slot `[12]` (intro-screen decorations): own 10-byte path format with per-step anim-table swap; no collision/triggers. **Confirmed** |

**Not part of the dispatch table**, adjacent: `hide_entity` (`0x4ABF8`) — clears the
draw-enable bit on both render-flag bytes.

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
| `0x4DA40` | `probe_entity_tile_collision` | enemy version → `tile_probe_result`; returns floor-type code |
| `0x4DA30` | `mark_placement_dead` | sets bit 7 in placement-record byte +2 → no respawn on room re-entry |
| `0x4D87C` | `kill_enemy` | dying state + upward launch + `add_score` + sound |
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
slot-0 question have all been resolved — see `reverse-plan.md`'s appendix for that
history rather than keeping strikethroughs here. Genuinely open:

1. **Tile-attribute bits beyond the known set.** Known: `0x02` ladder, `0x04` lethal,
   `0x10` one-way, `0x20` landable floor, `0x40` solid, `0x80` ladder-top
   (blocked = `& 0xD0`). The remaining bits of the 256-byte LUT, and the `0x6F`
   intermediate mask used inside the probe routines, are not accounted for.
2. **Which visual enemy variant maps to which on-screen creature per level.** The
   four sprite banks and three AI modes are known; matching them to what the player
   actually sees needs a live run or a per-level placement survey.
3. **Trigger-bit semantics in live play** — the bit meanings are read off the code
   with confidence, but no bit has been observed firing in a running game.
4. `ObjectTypeDef` entries with no placement record referencing them — unused content
   versus types only reachable via paths not yet traced.
