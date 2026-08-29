# Rick Dangerous — Data Structures

All structs live in the Ghidra type manager for program `atari_ram.bin` (project
`xrick`). Field names/types below match Ghidra exactly (`get_struct_layout`); Ghidra's
naming-quality gate prefixes primitive fields with a Hungarian-style letter (`n`=short,
`w`=word/ushort, `b`=byte, `dw`=undefined4, `a`=byte array) — this project otherwise
uses plain snake_case for functions, so treat the prefix as a Ghidra artifact, not a
project convention.

---

## SpriteEntity (76 bytes / 0x4C)

The universal entity record. `sprite_list` (below) is a fixed array of 13 of these.
Confirmed via `render_sprites`, `blit_backgrounds`, `clear_sprite_flags`,
`init_entity_from_placement`, and (this pass) the full entity-handler suite
(`scripted_trap_update`, `enemy_ai_update`, the collision helpers, `kill_player`/
`kill_enemy`, `player_death_physics`).

> ⚠️ **AXIS CORRECTION (entity-handler pass)**: earlier passes named offset 4 "Y" and
> offset 6 "X". That was backwards. Offset **4 is X** (horizontal, playfield
> 0..~0xE8) and offset **6 is Y** (vertical) — proven two independent ways:
> `render_sprites` computes the screen address as `offset6 × 160` bytes (the ST
> low-res scanline stride) plus a byte column derived from offset 4, and gravity
> (`enemy_ai_update`, `player_death_physics`, `kill_player`'s upward launch) acts on
> offset 6 via the 8.8 fixed-point pair at 0x08/0x0A. Consequence: the "scrolled"
> axis (the room-scroll delta added by `render_sprites`) is **Y — the room scroll is
> vertical**. The functions formerly called `scroll_room_left`/`scroll_room_right`
> were therefore misnomers and have been **renamed `scroll_view_up`/`scroll_view_down`**
> (they adjust `world_row_base` by −8/+8).

| Offset | Field | Type | Confidence | Notes |
|--------|-------|------|------------|-------|
| 0x00 | `wType` | undefined2 | confirmed | Entity type; `0xFFFF` = sentinel (end of list), `0` = free slot |
| 0x02 | `nDirection` | short | confirmed | Facing/direction (0 vs nonzero). Selects mirrored sprite bank (+0xFC0) for the player; walk direction for enemies; X drift ±3 for the player's death tumble |
| 0x04 | `nPosX` | short | confirmed | X (horizontal); despawn threshold `<-8` or `>=0xF1` |
| 0x06 | `nPosY` | short | confirmed | Y (vertical); despawn threshold `<0` or `>=0x143`; world-Y range with visible window 0x40–0x100 |
| 0x08 | `nVelY` | short | confirmed | Vertical velocity, 8.8 fixed point (whole part). Gravity: +0xC4/frame for enemies (terminal 0x800), +0x80 for the dead player; `kill_player`/`kill_enemy` set −0x300 upward launch |
| 0x0A | `nPosYFrac` | short | confirmed | Fractional (low) byte pair of the Y position for the 8.8 velocity integration |
| 0x0C | `nSpawnX` | short | confirmed | Spawn X; `scripted_trap_update` resets `nPosX` from here when the entity re-idles |
| 0x0E | `nSpawnY` | short | confirmed | Spawn Y; scroll-adjusted along with `nPosY` during room scrolls |
| 0x10 | `nHitboxW` | short | confirmed | Hitbox extent along X — used by every overlap test (`entity_overlaps_player`, `entity_contains_point`, `explosion_overlaps_entity`, the tile probes). Copied from object-type-definition table +2 |
| 0x12 | `nHitboxH` | short | confirmed | Hitbox extent along Y. From definition table +4 |
| 0x14 | `nRow_count` | short | confirmed | Sprite height in rows; default `0x15` (21) if zero |
| 0x16 | `bRender_flags_a` | byte | confirmed | Buffer-A render state: bit0=draw enable, bit1=wide/narrow blit path, bit2=erase-blit-pending (set by `despawn_offscreen_entity`) |
| 0x17 | `bUnk17` | byte | — | padding byte in the render-state block |
| 0x18 | `nAnim_tick_a` | short | confirmed | Buffer-A per-entity tick counter (row loop count for `render_sprites`) |
| 0x1A | `wScreen_offset_a` | ushort | confirmed | Buffer-A computed screen pixel offset, recalculated each frame from nPosX/nPosY |
| 0x1C | `bRender_flags_b` | byte | confirmed | Same as `render_flags_a`, for the other screen buffer (double-buffered) |
| 0x1D | `bUnk1D` | byte | — | padding |
| 0x1E | `nAnim_tick_b` | short | confirmed | Buffer-B counterpart of `nAnim_tick_a` |
| 0x20 | `wScreen_offset_b` | ushort | confirmed | Buffer-B counterpart of `wScreen_offset_a` |
| 0x22 | `gfx_data` | pointer | confirmed | Pointer to sprite graphics/mask pixel data (region `0x65B00`+). Refreshed from `anim_frame_table[nAnimFrameIdx]` each tick; for enemy types 4–15 it's frame-pointer + bank-offset (see `re/entities.md`) |
| 0x26 | `placement_record_ptr` | pointer | confirmed | Back-pointer to the source level-placement record; `mark_placement_dead` sets bit 7 of its byte +2 (no respawn on room re-entry) |
| 0x2A | `nAnimFrameIdx` | short | confirmed | Index into `anim_frame_table`; advanced each tick. Sentinel `-1`: replays frames 0/1 as idle loop, or (if `wTriggerSound` bit 7 set) plays the sound again first |
| 0x2C | `nPathStepIdx` | short | confirmed | **Multi-use**: path-step index for scripted traps; AI walk timer for enemies (reload from `nAiTimerReload`); 12-frame sparkle countdown for treasure pickups |
| 0x2E | `nPathStepTick` | short | confirmed | Tick counter for the current path step |
| 0x30 | `nAiTimerReload` | short | likely | Reload value for the enemy AI walk timer (`enemy_ai_update` copies it into 0x2C at edge/turn events) |
| 0x32 | `anim_frame_table` | pointer | confirmed | Per-type table of animation-frame bitmap pointers, indexed by `nAnimFrameIdx` |
| 0x36 | `movement_path_table` | pointer | confirmed | Scripted-movement path: 6-byte records `{duration, dX, dY}`, sentinel `duration==-1` (note: dX before dY, matching the corrected axes). Type 70 uses its own 10-byte format |
| 0x3A | `wHazardActive` | short | confirmed | 0xFF while this entity is lethal-to-touch: refreshed each frame from `bTriggerFlags` bits 8/4 by `scripted_trap_update`; set on destruction for pickups. Read by `entity_touches_hazard_or_block` (enemies die on contact with hazard-active entities). Spawn seeds it from a placement flag |
| 0x3C | `nTrigBoxXMin` | short | confirmed | Trigger bounding box (player-enter detection, `trigger_box_contains_point`) |
| 0x3E | `nTrigBoxYMin` | short | confirmed | Y bounds are scroll-adjusted during room scrolls (this is why they were once misread as "scroll links") |
| 0x40 | `nTrigBoxXMax` | short | confirmed | |
| 0x42 | `nTrigBoxYMax` | short | confirmed | |
| 0x44 | `wTriggerSound` | ushort | confirmed | *(was `wTypeFlags`)* Sound/music track played when a scripted trap triggers, **with bit 7 stripped**; bit 7 set = also replay at end of animation; 0 = silent. Copied from `ObjectTypeDef.wTriggerSound`. Confirmed from the two call sites' disassembly (`move.w (0x44,A0),D0; bclr #7,D0; jsr play_music` at `0x4D25E` and `0x4D2BC`) |
| 0x46 | `bTriggerFlags` | byte | confirmed | Per-instance trigger bitmask: 0x80 player-touch, 0x40 stick jab, 0x20 bullet, 0x10 explosion, 0x08/0x04 always-lethal (feeds `wHazardActive`), 0x02 "bullet passes through", 0x01 one-shot (despawn instead of reset at path end / mark placement dead) |
| 0x47 | `bAnimActive` | byte | confirmed | `0xFF` once the triggered/hit animation sequence is running |
| 0x48 | `bChasing` | byte | confirmed | Enemy AI: homing-at-player mode (flying enemies) |
| 0x49 | `bDying` | byte | confirmed | Enemy AI: death-tumble mode (set by `kill_enemy`) |
| 0x4A | `bAiCooldown` | byte | likely | Enemy AI decision cooldown (reset to 0x19=25); spawn seeds it as `(subcell_row & 7) * 25` |
| 0x4B | `bUnk4B` | undefined1 | unconfirmed | Untouched |

**Reserved slot indices in `sprite_list`** (all confirmed): `[0]` = the **scripted
moving hazard** slot (crusher / falling boulder — see below), `[1]` = **player
(Rick)**, `[2]` = bullet, `[3]` = dynamite, `[4..8]` = hazard-capable level entities
(scanned by `entity_touches_hazard_or_block`), `[9..11]` = further level entities,
`[12]` = decorative sprite (type 74, intro screens).

### Slot 0 — resolved 2026-08-28: there is no block-pushing mechanic

Earlier drafts described slot 0 as a "solid/pushable block" whose mover was
*unlocated*. **That premise was wrong.** A program-wide search settles it:

- `0x4A706` (slot 0's `nPosX`) has **8 xrefs, all READ**. The only write touching
  `0x4A708` is `render_sprites`' global scroll-delta add at `0x4B060`, applied to
  *every* slot.
- Slot 0 is filled by `spawn_level_entity` when a `PlacementRecord` sets
  `bTriggerFlags` bit 1 (`0x02`); `init_entity_from_placement` writes it through `A1`,
  so the spawn produces no absolute reference either.
- **All 26 placement records targeting slot 0 carry types 24–73** — every one
  dispatches to `scripted_trap_update`. Their motion comes from that handler stepping
  `movement_path_table` through `A0` (writing `+4`/`+6`), which again leaves no
  absolute xref. That is precisely why every address-based hunt came up empty.
- Those types have block-sized hitboxes (16–32 wide × 16–21 tall), trigger sound
  `0x14` (one uses `0x17`), and flags `0x1F`/`0x8E`/`0x2E` — lethal both idle and
  triggered, fired by player touch, bullet or explosion.

Slot 0 is therefore the game's **crusher / falling-boulder trap**: a solid, lethal,
scripted hazard. The probes hardcode its address so a single such hazard can act as a
physical obstacle for the player (with a crouch special case), bullets and enemies.


Struct was rebuilt once via `recreate_struct` (field-split pass); total size held at
76 bytes throughout, offsets otherwise unchanged from the original creation.

⚠️ **Ghidra API note for future edits**: `remove_struct_field` on this struct
silently shrinks+left-shifts everything after the removed field — it does **not**
leave a same-size gap. `add_struct_field` at an already-occupied offset just retypes
in place rather than inserting. Neither is a safe "split one field into two"
primitive; use `recreate_struct` with the full field list instead, then re-apply
`SpriteEntity[13]` at `0x4A702` afterward (the delete+recreate step transiently
reverts callers' decompilation to raw `short*` until the array type is reapplied).

---

## sprite_list (13 × SpriteEntity, 988 bytes at 0x4A702)

Fixed array, confirmed by byte-reading: `13 × 0x4C = 0x3DC` bytes from `0x4A702` to
a `0xFFFF` sentinel word at `0x4AADE`, immediately followed by `sprite_type_dispatch`
at `0x4AAE0`. Iterated by `render_sprites`, `blit_backgrounds`, `clear_sprite_flags`
(all step by `0x4C` bytes, stop at the sentinel). Applied as Ghidra array type
`SpriteEntity[13]`.

---

## HudCounters (16 bytes at 0x4B326)

| Offset | Field | Type | Notes |
|--------|-------|------|-------|
| 0x0 | `bScore_bcd_hi` | byte | Most-significant BCD digit pair of the score |
| 0x1 | `bScore_bcd_mid` | byte | |
| 0x2 | `bScore_bcd_lo` | byte | Least-significant BCD digit pair; all three added-to by `add_score` via ABCD |
| 0x3 | `bUnk03` | byte | padding |
| 0x4 | `bBullets` | byte | **Confirmed: bullets/ammo** — `player_controller` at `0x4C524`: if zero plays the empty-click sound (track 9); else decrements it, sets the dirty flag, and writes `wType=2` into `sprite_list[2]` (spawns the bullet, sound 8). Reset to 6 by `init_hud_state`/`start_level`/`reset_player_state` |
| 0x5 | `bUnk05` | byte | padding |
| 0x6 | `bDynamite` | byte | **Confirmed: dynamite** — `player_controller` at `0x4C60E`: decrements and writes `wType=3` into `sprite_list[3]` (spawns the dynamite, row_count=0x10, X=player+4 clamped to 0xE8). Same reset pattern as bBullets |
| 0x7 | `bUnk07` | byte | padding |
| 0x8 | `bLives` | byte | **Confirmed: player's lives count** — decremented by `kill_player`; `main_init_and_loop`'s per-frame dispatch checks this for `==0` (game over) vs. nonzero (checkpoint respawn). `start_level`/`reset_player_state` deliberately do **not** reset this (persists across levels/rooms) |
| 0x9 | `bUnk09` | byte | padding |
| 0xA | `wScore_display_hi` | ushort | Nibble-packed score digits (from `bScore_bcd_hi`) ready for `hud_update_score` to render |
| 0xC | `dwScore_display_lo` | undefined4 | Nibble-packed digits from `bScore_bcd_mid`/`bScore_bcd_lo` (only the low 2 bytes actually used) |

This **corrects** the original `functions.md`'s guess of 4 distinct counters
("lives, bullets, dynamite sticks, and one other (keys?)") — there are only **3**
counters plus the score. The bullets-vs-dynamite ordering, previously flagged
"needs dynamic verification", was **resolved statically** in the entity-handler
pass by reading `player_controller`'s two fire paths (disassembly at `0x4C524` and
`0x4C60E`, see field notes above).

## HudDirtyFlags (8 bytes at 0x4B350)

| Offset | Field | Notes |
|--------|-------|-------|
| 0x0 | `bScore_dirty` | Set when score changes; cleared by `hud_update_score` |
| 0x2 | `bBullets_dirty` | Cleared by `hud_update_bullets` (ex `hud_update_element2`, icon 0xA) |
| 0x4 | `bDynamite_dirty` | Cleared by `hud_update_dynamite` (ex `hud_update_element3`, icon 0xB) |
| 0x6 | `bLives_dirty` | Cleared by `hud_update_lives` (ex `hud_update_element4`, icon 0xC) |

(Odd offsets are unused padding bytes — the four flags are word-spaced in memory
though each is only a byte wide.)

---

## CheckpointState (10 bytes at 0x4BFB8)

| Offset | Field | Type | Destination global (on restore) |
|--------|-------|------|----------------------------------|
| 0x0 | `wSaved_a752` | ushort | `0x4A752` = **`sprite_list[1].nPosX`** (the player's X, read directly — not a copy) |
| 0x2 | `wSaved_a754` | ushort | `0x4A754` = **`sprite_list[1].nPosY`** (the player's Y) |
| 0x4 | `wSaved_a750` | ushort | `DAT_0004a750` |
| 0x6 | `wSaved_95ca` | ushort | `DAT_000495ca` — scroll/world position |
| 0x8 | `bSaved_d00b` | byte | `DAT_0004d00b` |
| 0x9 | `bSaved_bf14` | byte | `DAT_0004bf14` |

> ⚠️ **Axes corrected 2026-08-28.** This table previously listed `+0` as "room-Y" and
> `+2` as "room-X" — reversed. `process_level_transition_point` shifts `0x4A754`
> right by 3 and adds it to `world_row_base` (a *row*, hence Y), and tests `0x4A752`
> for the left/right exit side (hence X). Both addresses are simply
> `sprite_list[1]`'s own `nPosX`/`nPosY` fields (`0x4A702 + 0x4C + 4/6`), not
> separate copies — consistent with the struct's X-at-+4 / Y-at-+6 layout.

**Confirmed semantics**: a **per-room** player-position checkpoint (position +
scroll state), not per-level. Writer: `save_checkpoint_state`, called only from
`init_screen_pointers` (itself called from `enter_screen_with_fade` and
`process_level_transition_point` — both room-transition code). Reader:
`restore_checkpoint_state`, called from `main_init_and_loop`'s respawn path
(death with `HudCounters.bLives` > 0). Matches Rick Dangerous's room-grid level
design: dying respawns Rick at the start of the *current room*, not the level.

---

## MusicTrackDescriptor (8 bytes each, array of 29 at 0x44F08)

| Offset | Field | Type | Notes |
|--------|-------|------|-------|
| 0x0 | `nTrack_type` | short | `1` = retrigger-style (toggles a per-channel state bit), `2` = tracked/pattern music (via `init_music_playback`), other = one-shot sample |
| 0x2 | `nParam_index` | short | For type 2: index (`<<1`) into a parallel 2-byte-stride lookup table at `0x44FF0` (`instrument_index_lookup`, not further typed — low confidence on exact record shape) |
| 0x4 | `dwData_ptr` | undefined4 | Data pointer (sequence/instrument data), consumed differently per track type |

`music_track_table` boundary confirmed at exactly 29 records (`0x44F08`–`0x44FEF`,
232 bytes) — the table ends precisely where `instrument_index_lookup` begins at
`0x44FF0`.

---

## Font Table (0x1B01E)

32 bytes per glyph, terminator byte `0xFF` in `draw_string`/`draw_glyph_string`
input strings. Confirmed base address and stride directly from `draw_string`'s
disassembly (`LEA 0x1B01E,A4; ADDA.L D1,A4` where `D1 = char_index << 5`). The first
32 glyphs (`0x1B01E`–`0x1B41E`) were typed as `byte[32][32]` and look
alphabet-shaped; beyond that the data is ambiguous (glyph 32 non-zero but less
letter-like, glyph 64 all-zero, glyphs 96/128/160/192/224 non-zero but look more
like graphic tiles than characters).

✅ **Resolved 2026-08-28 by rendering the sheet** (`assets/font.png`). The font is
**95 glyphs, `0x00`–`0x5E`**:

| Range | Contents |
|---|---|
| `0x00`–`0x09` | **digits 0–9** — which is why score digits are stored as unpacked decimal, indexing glyphs directly rather than as ASCII |
| `0x0A`–`0x0C` | the three HUD icons (bullets, dynamite, lives) |
| `0x0D`–`0x40` | assorted small graphics |
| `0x41`–`0x5A` | `A`–`Z` at their ASCII positions |
| `0x5B`–`0x5E` | `,` `.` `?` and space (`0x5E`, a blank glyph) |
| `0x5F`+ | **not font** — unrelated graphics data |

This matches the `byte[95][32]` typing an earlier pass had applied in Ghidra.

---

## Level Data Structures (placement-format pass)

The complete level-data model, decoded by tracing `spawn_level_entity` /
`init_entity_from_placement` / `init_screen_pointers` /
`process_level_transition_point` at disassembly level and validating every claim
against raw table bytes. A level is a set of vertically-scrolling **rooms** linked
left/right into a graph; entities spawn from per-room placement lists as their
world-row band scrolls into view.

### PlacementRecord (6 bytes; `placement_table` = `PlacementRecord[523]` at 0x481E4)

The master table covers **all 4 levels** (`0x481E4`–`0x48E25`, ending exactly at the
high-score table). Per-room sub-lists are terminated by a sentinel record with
`wSpawnBand == 0x00FF`. This table was previously the "523×6-byte mystery table"
cleared by `reset_block_hit_flags` — that function is now renamed
**`revive_all_placements`** (it clears the DEAD bits at new game).

| Offset | Field | Meaning |
|--------|-------|---------|
| +0 | `wSpawnBand` | World-Y band; compared `& 0xFFF8` against `world_row_base` + lookahead — the entity spawns when its band scrolls into view |
| +2 | `bTypeAndDead` | Bits 0–6 = entity type (dispatch index 1–70); **bit 7 = DEAD** (set by `mark_placement_dead` on kill/collect/fire; cleared table-wide by `revive_all_placements`) |
| +3 | `bTriggerFlags` | Copied to `SpriteEntity.bTriggerFlags`. Bit 1 (0x02): spawn into `sprite_list[0]` (the solid-block slot). Bit 2 (0x04): spawn hazard-active + skip the Y `|3` alignment nudge. Other bits = trigger sources |
| +4 | `bPosXY` | X pixel = `value & 0xF8`; Y = `(band base + (value & 7)) × 8` px |
| +5 | `bTrigBoxXY` | Trigger-box origin, same packing; the `&7` part also seeds `bAiCooldown` (×25), the `&0xF8` part feeds the patrol-range value at `SpriteEntity+0x30` |

Spawn pools: type < 0x10 → slots **[9..11]** (corrected 2026-08-28 — the loop bound
`0x4AA92` is slot 12 and the test is strict, so slot 12 is excluded; it is reserved
for the decorative sprite), with dedup by `placement_record_ptr` (a
live moving enemy is not double-spawned); type ≥ 0x10 → slots [4..8].

### ObjectTypeDef (16 bytes; `object_type_defs` = `ObjectTypeDef[75]` at 0x47D34)

Per-entity-type template data, read by `init_entity_from_placement` as
`base + (type << 4)`. **Indexed by the raw type value**, unlike
`sprite_type_dispatch` which is indexed by `type − 1`. Occupies `0x47D34`–`0x481E3`,
ending exactly where `placement_table` begins — the 75-entry count is a hard
boundary fit, with entry 74 as all-zero padding.

| Offset | Field | Meaning |
|--------|-------|---------|
| +0 | `wTriggerSound` | Sound track played when a scripted trap triggers, bit 7 stripped. **Bit 7 = also replay at end of animation.** 0 = silent. Observed: 0x14/0x15/0x18/0x19/0x1A/0x1B, plus 0x9A on entry 64 (track 0x1A + replay flag) |
| +2 | `nHitboxW` | → `SpriteEntity.nHitboxW` (drives every overlap test) |
| +4 | `nHitboxH` | → `SpriteEntity.nHitboxH` |
| +6 | `anim_frame_table` | → `SpriteEntity.anim_frame_table`; if non-null its **first entry** also seeds `gfx_data` |
| +10 | `movement_path_table` | → `SpriteEntity.movement_path_table` |
| +14 | `bTrigBoxW` | Trigger-box width in **8-pixel units** (`<<3`), added to the placement origin → `nTrigBoxXMin/XMax` |
| +15 | `bTrigBoxH` | Trigger-box height, 8-pixel units → `nTrigBoxYMin/YMax` |

The table's contents independently validate the entity-handler pass:

| Entries | Content |
|---------|---------|
| 0 | All zero (type 0 = free slot) |
| 1 | Player: hitbox 24×21, no tables (`player_controller` is bespoke) |
| 2–3 | All zero — bullet/dynamite manage their own state |
| 4–15 | Enemies: hitbox 24×21, **no** anim/path tables — `enemy_ai_update` uses hardcoded frame tables (`0x46C6A`/`0x46C7E`/`0x46C92`) |
| 16–21 | Pickups: hitbox 24×21, no tables (handlers set `gfx_data` directly) |
| 22–23 | Trigger zones: hitbox **0×0** (invisible) but trigger box 4×4 (= 32×32 px) |
| 24–73 | Scripted traps: full anim (`0x46Dxx`–`0x46Fxx`) + path (`0x470xx`–`0x475xx`) pointers; hitboxes 4×21 … 32×16 |
| 74 | All-zero terminator/padding |

⚠️ **Entries 71–73 carry real data but lie beyond `sprite_type_dispatch`'s 70
entries** (which ends at `0x4ABF8`, where `hide_entity` begins). Types 71–73 have no
handler, so they must never appear in placement data — either unused/leftover
content or an editor-side type range wider than the shipped dispatch table.

### RoomHeader (14 bytes; `room_headers` = `RoomHeader[47]` at 0x47620)

47 rooms across all levels (`0x47620`–`0x478B1`, ending exactly at the transition
tables). `cur_room_header_ptr` (`0x495D8`) tracks the active room. **Disasm-verified
offsets** (an earlier decompiler-derived comment placed `pPlacements` at +5 — wrong):

| Offset | Field | Meaning |
|--------|-------|---------|
| +0 | `wTileBankVariant` | 0 → tile gfx `0x1D01E` + attr LUT `0x49F1E`; nonzero → `0x1F01E` + `0x4A01E` |
| +2 | `pTileMap` | Room tile-map data (in the graphics blob, `0x2101E`+ for level 1) → `cur_tilemap_ptr` |
| +6 | `pTransitions` | This room's `TransitionWaypoint` list |
| +10 | `pPlacements` | This room's slice of `placement_table` |

### TransitionWaypoint (10 bytes; lists at `transition_tables` 0x478B2+, word-0x00FF sentinel)

Consumed by `process_level_transition_point` when the player walks off the
left/right playfield edge. Links are bidirectional (each room lists its way back).

| Offset | Field | Meaning |
|--------|-------|---------|
| +0 | `wExitSide` | 0 = left edge, 1 = right edge |
| +2 | `wRow` | World row; match requires `world_row_base + playerY/8` ∈ [wRow, wRow+2] |
| +4 | `pNextRoomHeader` | Destination room, or **−1 = end of level** (advances `level_index`; after level 4: game complete) |
| +8 | `wEntryRow` | `world_row_base −= wRow − wEntryRow` on transition |

### LevelStartInfo (20 bytes × 4 at **0x4B522**)

> ⚠️ **Corrected 2026-08-28.** The base is `0x4B522`, **not** `0x4B526` — the earlier
> version started 4 bytes late and mislabeled every field. Verified: the longword at
> `0x4B522` is `0x0004B8FE`, level 0's intro-text pointer.

| Offset | Field | Values (levels 0–3) |
|--------|-------|---------------------|
| +0x00 | `pIntroText` | `0x4B8FE` / `0x4BA16` / `0x4BB24` / `0x4BC28` |
| +0x04 | `wStartX` | 0x0008 (all) |
| +0x06 | `wStartY` | 0x008B (all) |
| +0x08 | `wStartWorldRow` | 0x08 / 0x68 / 0x10 / 0x10 → seeds `world_row_base` |
| +0x0A | `pRoomHeader` | `0x47620` / `0x4769E` / `0x47738` / `0x47834` |
| +0x0E | `wIntroParam` | 0x12 / 0x60 / 0x84 / 0xA8 — intro banner glyph base |
| +0x10 | `pIntroSprite` | `0x46CE2` / `0x46CFC` / `0x46D20` / `0x46D3A` |

`pIntroText` identifies the previously-unexplained gap `0x4B8FE`–`0x4BE1F`: it is the
**level intro/story text**, `0xFF`-terminated ASCII lines with `0xFE` ending the text.
A **5th** pointer (`0x4BD14`) follows the 4th entry. Its target has been decoded and
is the **game-ending text** ("...BARFIAN EMPIRE... WHAT WILL RICK DO NEXT ... ?"), not
a 5th level — see `strings.md`. Whether the array is formally 5 entries or the 5th
pointer is separate adjacent data is still unconfirmed, but the *content* is known.

### Effect callbacks (the formerly untraced A2 pointers)

Each pickup/trigger-zone type wrapper does `lea <effect>,A2` before delegating (the
decompiler hid these loads, which is why they went untraced in the entity pass):

| Type | Effect fn | Behavior |
|------|-----------|----------|
| 16 | `effect_refill_dynamite` (0x4D034) | `bDynamite = 6` — dynamite crate |
| 17 | `effect_refill_bullets` (0x4D046) | `bBullets = 6` — ammo crate |
| 22 | `effect_start_escape_timer` (0x4BE7C) | Starts the BCD countdown (20.00) + music 0x12 |
| 23 | `effect_stop_timer_award_bonus` (0x4BEB6) | Stops the timer, banks remaining time as score |

### Related globals

`cur_room_header_ptr` (0x495D8), `cur_tilemap_ptr` (0x495CC),
`cur_placement_list_ptr` (0x495DC), `tile_gfx_base_ptr` (0x495D0),
`world_row_base` (0x495CA — also saved in `CheckpointState.wSaved_95ca`),
`spawn_scan_flags` (0x495C8), `level_index` (0x4B586 — **corrects** the earlier
"life/attempt counter" guess: it's the current level number, 4 levels total),
`player_pos_x_copy`/`player_pos_y_copy` (0x4A752/0x4A754 — note the CheckpointState
field notes below had these axis-swapped, consistent with the SpriteEntity axis
correction).

---

## Sprite frame format (derived 2026-08-28)

Not a struct, but the single most important *asset* format for reimplementation.

- **0x150 (336) bytes per frame.** Confirmed three independent ways: consecutive
  pointers in animation tables differ by 0x150 (e.g. `0x2FC4E` → `0x2FD9E`);
  `treasure_pickup_update` computes `gfx = type*0x150 + 0x2F70E`; and
  `render_sprites` consumes 16 bytes/row over 21 rows (`16 × 21 = 336`).
- **16 bytes per row, 21 rows.** `render_sprites` reads four longwords per row and
  then advances the destination by 0x28 longwords (160 bytes = one ST low-res
  scanline).
- **4 bitplanes stored PLANE-MAJOR**: row `r`, plane `p` = the longword at
  `base + r*16 + p*4`; pixel `x` = bit `31-x`. A row spans 32 pixels; sprites are
  nominally 24 px wide, leaving the right 8 px blank.
- ⚠️ **This is NOT ST screen format.** Screen memory interleaves planes by *word*;
  sprite source keeps a whole longword per plane so `render_sprites` can rotate each
  plane independently for sub-word shifts. Decoding sprites as screen data yields
  noise — verified by rendering Rick's idle frame (`0x2CA6E`) both ways.
- **No stored mask.** Transparency is *derived*: `render_sprites` computes
  `mask = NOT(p0 | p1 | p2 | p3)`, i.e. colour index 0 is transparent. A
  reimplementation must derive it the same way rather than expecting mask data.
- Frame data clusters around `0x2FC4E`–`0x334xx` inside the big blob; enemy sprite
  banks are `0xD20` apart (see `re/entities.md`), with alternate banks at `0xA80`
  stride.

✅ **Visually verified 2026-08-28** by rendering every asset — see
`assets-manifest.md` and `assets/`. The title screen, sprite sheet and tile blocks
all come out as recognisable artwork, which confirms the palette, plane decoding
and base addresses together.

Related 8×8 formats (font and tiles) are **different**: 32 bytes per cell, **one
byte per plane per row** (`base + r*4 + p`). Tile banks `0x1D01E`/`0x1F01E`, 256
tiles each; block definitions at `0x22FEE` are 16 bytes = a 4×4 grid of tile
indices (a 32×32 px block).

---

## Global variables

Moved here from `functions.md` (2026-08-28) so that data lives with data. Several
entries in the old copy were stale; all below are current.

### Frame, video and RNG
| Address | Name | Type | Meaning |
|---|---|---|---|
| `0x49334` | `vblank_counter` | byte | Bumped by `vblank_isr`, polled/cleared by `vsync_wait` |
| `0x492EC` | `current_buffer` | byte (bit 7) | Toggles per frame; selects the render-target buffer |
| `0x492EA` | back-buffer base | long | Render target; `^0x8000` gives the other buffer |
| `0x4DEE2` | `target_palette` | 16 × word | Palette used by `set_palette` / `palette_fade_in/out` |
| `0x495C0`, `0x495C4` | `prng_state` | 2 × long | Seeded by `seed_prng_state`, stepped by `update_prng` |

### Player and combat
| Address | Name | Type | Meaning |
|---|---|---|---|
| `0x4922B` | `joystick1_state` | byte | **Joystick, not keyboard.** IKBD joystick-1 report: `0x01` UP, `0x02` DOWN, `0x04` LEFT, `0x08` RIGHT, `0x80` FIRE |
| `0x4922C` | last scan code | byte | Raw keyboard code; used only for ESC / P / SPACE |
| `0x4D00A` | `player_collision_flags` | byte | Player tile-probe result. Bits: `0x01` background-A *(inert)*, `0x02` ladder, `0x04` lethal, `0x08` background-B *(inert)*, `0x10` one-way, `0x20` landable floor, `0x40` solid, `0x80` ladder-top; blocked = `& 0xD0`. **`0x01`/`0x08` are never tested** — see the attribute-bit section at the end |
| `0x4D00B` | ceiling-above flag | byte | Captured while crouching; saved in `CheckpointState` |
| `0x4BF14` | `player_crouching` | byte | Non-zero while crouched (widens/shifts probes) |
| `0x4BF18` | `player_dying` | byte | `0xFF` during the death sequence. **Not "game_running"** |
| `0x4BF1A` | `dynamite_exploding` | byte | 0 = fuse phase, `0xFF` = blast phase |
| `0x4BF1E` | `stick_attack_active` | word | Non-zero while the stick jab is out |
| `0x4BF20`/`0x4BF22` | `stick_point_x`/`_y` | word | Stick-jab probe point |
| `0x4BF24`/`0x4BF26` | `bullet_point_x`/`_y` | word | Bullet leading-edge probe. **No range budget** |
| `0x4BF28` | `explosion_active` | byte | `0xFF` during blast frames 0–6 |
| `0x4BF2A`/`0x4BF2C` | `explosion_x`/`_y` | word | Blast centre |
| `0x4BF2E` | `player_touched_hazard` | byte | Set on any lethal overlap; consumer site untraced |

### Level, rooms and scrolling
| Address | Name | Type | Meaning |
|---|---|---|---|
| `0x495C8` | `spawn_scan_flags` | word | Which spawn passes to run (7 = repopulate all) |
| `0x495CA` | `world_row_base` | word | Top world row of the view; also in `CheckpointState` |
| `0x495CC` | `cur_tilemap_ptr` | long | Current room's packed tilemap |
| `0x495D0` | `tile_gfx_base_ptr` | long | `0x1D01E` or `0x1F01E` per `RoomHeader.wTileBankVariant` |
| `0x495D4` | `tile_attr_table_ptr` | long | 256-byte attribute LUT (`0x49F1E` / `0x4A01E`) |
| `0x495D8` | `cur_room_header_ptr` | long | Active `RoomHeader` |
| `0x495DC` | `cur_placement_list_ptr` | long | This room's slice of `placement_table` |
| `0x4A17E` | `room_tile_map` | byte[32×44] | Decoded tile indices, **row-major**, `0x20` bytes/row |
| `0x4A6FE` | `scroll_active` | byte | Non-zero during a scroll animation |
| `0x4A700` | `scroll_delta` | word | Per-frame scroll delta, added to Y fields by `render_sprites` |
| `0x4B586` | `level_index` | word | Current level 0–3; ≥4 = game complete |
| `0x498C2` | `furthest_level` | word | High-water mark for the level-select menu |
| `0x498C4` | POOKY flag | word | Set by the `POOKY9999` easter egg; gates the level-select menu |
| `0x4DE2C` | return-to-attract | byte | Set on game completion |

### Timer and tile probes
| Address | Name | Type | Meaning |
|---|---|---|---|
| `0x4BE18` | `timer_enable` | word | Non-zero while the escape countdown runs |
| `0x4BE1A` | `timer_tick` | word | Counts down from 25 (one BCD unit per second) |
| `0x4BE1C` | `bcd_timer` | word | BCD countdown value (starts `0x2000` = 20.00) |
| `0x4DC28` | `tile_probe_mask` | byte | Attribute mask for `probe_entity_tile_collision` |
| `0x4DC29` | `tile_probe_result` | byte | Masked probe result; carry = `& 0xD0` |

### Large tables (see their own sections above)
`placement_table` `0x481E4` · `room_headers` `0x47620` · `transition_tables`
`0x478B2` · `object_type_defs` `0x47D34` · `level_start_info` `0x4B522` ·
`sprite_list` `0x4A702` · `sprite_type_dispatch` `0x4AAE0` · `music_track_table`
`0x44F08` · `highscore_table` `0x48E26` (layout in `strings.md`) ·
`level_names` `0x49859` · `level_intro_texts` `0x4B8FE` · font `0x1B01E`

---

## Other named data regions (not yet formal structs)

| Address | Name | Shape | Notes |
|---------|------|-------|-------|
| `0x4AAE0` | `sprite_type_dispatch` | `pointer[74]` | 296 bytes, `0x4AAE0`–`0x4AC07`. See `re/entities.md` |
| `0x47D34` | `object_type_defs` | `ObjectTypeDef[75]` | **Resolved** — see "Level Data Structures" above |
| `0x4B522` | `level_start_info` | 20 bytes × 4 (+ a 5th intro pointer) | **Fully laid out** — see "Level Data Structures" above |
| `0x48E26` | high-score table | 8 × 0x1E bytes | word `score_hi`@+2, long `score_lo`@+4, name text follows |
| `0x48FA1` | name-entry char grid | 6 rows | Used by `enter_highscore_name`'s cursor picker |
| `0x481E4` | `placement_table` | `PlacementRecord[523]` | **Resolved** — see "Level Data Structures" above; the old "block hit flags" interpretation is superseded |
| `0x45720` | `note_period_table` | `word[84]` | Confirmed: 7 octaves × 12 semitones of PSG tone-period values (`0x0EEE`→`0x0020`), consumed by `resolve_channel_note_period` |
| `0x46932` | per-channel instrument table | stride 6 | Indexed by `(D0&0xFF)*6` in `init_music_playback` |
| `0x46B66` | arpeggio/vibrato table | 8 bytes/entry | Indexed by a 5-bit field in `resolve_channel_note_period` |
| `0x463CC` | default instrument data | — | Referenced by `init_music_playback`/`process_sequence_command` |
| `0x22FEE` | tile-graphics table | 16 bytes/tile, 4 de-interleaved bitplane longword arrays | Source for `decode_level_tiles_to_cache` |
| `0x23FEE` | title screen bitmap | 32768 bytes | Source for `draw_title_picture`; inside the still-unmapped `0x1B01E-0x44BED` blob (see `re/memory_map.md`) |


---

## Tile attribute bits — complete (resolved 2026-08-29)

Attribute LUTs: `0x49F1E` (bank 0) and `0x4A01E` (bank 1), 256 bytes each, selected
into `tile_attr_table_ptr` (`0x495D4`) by `init_screen_pointers`. Indexed by tile number.

Values are **mutually exclusive** apart from `0x60` (floor+solid) and `0x82`
(ladder+ladder-top) — each tile carries essentially one attribute.

| Bit | Meaning | bank0 / bank1 tiles | Verified by |
|---|---|---|---|
| `0x01` | background class A — fragments, torches, blank | 77 / 55 | rendered; **never tested** |
| `0x02` | ladder | 18 / 10 | rendered: ladder rungs |
| `0x04` | lethal | 4 / 4 | rendered: spikes |
| `0x08` | background class B — ornate wall backdrop | 87 / 144 | rendered; **never tested** |
| `0x10` | one-way platform | 8 / 9 | rendered: ledges |
| `0x20` | landable floor | 3 / 1 | only ever with `0x40` (`0x60`) |
| `0x40` | solid | 62 / 34 | rendered: brick/stone |
| `0x80` | ladder-top | 4 / 6 | only ever with `0x02` (`0x82`) |

**`0x01` and `0x08` are inert.** The LUT has exactly three readers (Ghidra xrefs on
`0x495D4`): `probe_player_tile_collision`, `probe_entity_tile_collision` and
`bullet_hit_solid_test`. The first two test only `& 0xD0` plus `0x02`/`0x04`/`0x20`/
`0x80` downstream; the third does `btst #6` (solid) alone. **No code branches on bit 0
or bit 3.** A reimplementation may copy the LUTs verbatim and never inspect those bits;
they exist to give every tile a non-zero classification.

**The `0x6F` intermediate mask is a row filter, not a bit-meaning puzzle.**
`0x6F` = `~(0x10 | 0x80)`. Both probes OR tile attributes across up to four rows and
apply `&= 0x6F` after the upper rows, so **one-way (`0x10`) and ladder-top (`0x80`) can
only be contributed by the final, bottom row** — those two attributes are detected at
the player's feet and nowhere else. Without it a ledge at head height would read as
standable. The same mask serves the identical purpose in `probe_entity_tile_collision`.
