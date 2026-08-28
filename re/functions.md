# Rick Dangerous — Function Index

**This file is an index, not a reference.** It maps all **133** functions to a name, a
one-line purpose, and the document holding the authoritative detail. Behaviour,
constants and calling conventions live in the `algo-*.md` transcriptions; data layouts
live in `data-structures.md`.

> **Authority order** — when documents disagree, trust in this order:
> **1. Ghidra** (verified against bytes) → **2. `algo-*.md`** (exact transcriptions) →
> **3. everything else** (summaries and indexes, including this file).
>
> This file deliberately carries *no* derived detail. Earlier versions did, and drifted
> repeatedly — as late as 2026-08-28 it still claimed `Mshrink`, a 70-entry dispatch
> table, keyboard input, and an untraced `0x481E4`, all long since disproved. Keeping
> each fact in exactly one place is the fix.

Addresses are Atari ST physical addresses = offsets into `atari_ram.bin`.

---

## Sound and music — detail: [`algo-music.md`](algo-music.md)

| Address | Name | Purpose |
|---|---|---|
| `0x44BEE` | `blit_image_5120` | Copy a 5120-byte full-screen image into both buffers |
| `0x44C10` | `reset_sound_chip` | Zero all YM2149 registers, clear MFP interrupt state |
| `0x44CCE` | `play_music` | Start track D0 (type 1 retrigger / 2 sample / other one-shot) |
| `0x44E0C` | `music_tick` | Per-frame music driver, called from `vblank_isr` |
| `0x45006` | `setup_timer_a` | Install `timer_a_music_isr` on MFP Timer A (vector `0x134`) |
| `0x45022` | `timer_a_music_isr` | Timer-A ISR; drives sample playback |
| `0x45116` | `init_music_playback` | Initialise channel state for a new track |
| `0x451DA` | `advance_music_channels` | Step all channels one tick (procedural path) |
| `0x4522C` | `advance_channel_sequence` | Pull the next sequence command for one channel |
| `0x45342` | `process_sequence_command` | Execute one sequence opcode |
| `0x4538C` | `resolve_channel_note_period` | Note → PSG tone period via `note_period_table` |
| `0x4548A` | `trigger_channel_note` | Load an instrument and key on |
| `0x45528` | `silence_all_channels` | Key off all three PSG voices |
| `0x4556E` | `step_all_channel_coroutines` | Run the three per-channel coroutines |
| `0x45636` | `channel_coroutine_dispatch` | Self-modifying `jmp (A0)` coroutine resume |
| `0x456E8` | `channel_coroutine_state_c` | One coroutine state body |

## System, interrupts, timing, text — detail: [`algo-system.md`](algo-system.md)

| Address | Name | Purpose |
|---|---|---|
| `0x1B018` | `game_entry` | Thunk: `JMP 0x4DC2A` |
| `0x4DC2A` | `main_init_and_loop` | `Super(0x5324C)`, full init, then the per-frame main loop |
| `0x4DE2E` | `clear_screen_buffers` | Zero the screen/sprite buffer area |
| `0x4DE40` | `init_screen_and_palette` | Set video mode and load the initial palette |
| `0x4DE58` | `toggle_palette_on_space` | Poll SPACE; swap between two palette buffers |
| `0x4DF02` | `attract_mode_loop` | Cycle high-score table and title picture until keypress |
| `0x4DF5A` | `draw_title_picture` | Blit the 32 KB title bitmap from `0x23FEE` |
| `0x4922E` | `init_keyboard` | Configure the ACIA, install `keyboard_isr` on vector `0x118` |
| `0x4924E` | `acia_write` | Poll ACIA ready, write one control byte |
| `0x49262` | `keyboard_isr` | Decode IKBD packets → **joystick** state at `0x4922B` |
| `0x492EE` | `install_vblank_handler` | Install `vblank_isr` on vector `0x70` |
| `0x492FA` | `vblank_isr` | Bump the frame counter, call `music_tick` |
| `0x49310` | `vsync_wait` | Block until the next VBlank tick |
| `0x49336` | `flip_screen_buffer` | Swap displayed buffer via `0xFF8201`/`0xFF8203` |
| `0x4935E` | `xbios_setscreen` | `TRAP #14` Setscreen wrapper |
| `0x4937C` | `set_palette` | Copy 16 colour words to `0xFF8240`+ |
| `0x49394` | `palette_fade_in` | Ramp the palette up toward the target |
| `0x493FE` | `palette_fade_out` | Ramp the palette down to black |
| `0x49446` | `draw_string_xy` | `draw_string` wrapper taking (x, y) |
| `0x49466` | `draw_string` | Render an `0xFF`-terminated string to both buffers |
| `0x494AC` | `draw_glyph_string` | Text blit taking a raw screen pointer |
| `0x494E2` | `draw_glyph` | Render one 32-byte glyph |
| `0x49574` | `seed_prng_state` | Seed the PRNG with fixed constants |
| `0x49596` | `update_prng` | Advance the PRNG one step |
| `0x48F16` | `show_highscore_table` | Draw the 8-entry high-score screen |
| `0x48FCC` | `enter_highscore_name` | Name entry; contains the `POOKY9999` easter egg |
| `0x491E8` | `draw_name_entry_cursor` | Per-frame cursor for the name-entry grid |

## Level, spawning, scroll, tiles — detail: [`algo-level.md`](algo-level.md)

| Address | Name | Purpose |
|---|---|---|
| `0x495E0` | `revive_all_placements` | Clear the DEAD bit on all 523 `PlacementRecord`s |
| `0x49600` | `spawn_screen_entities` | Call `spawn_level_entity` per `spawn_scan_flags` bit |
| `0x4964C` | `spawn_level_entity` | Find a free slot, match a placement record, spawn |
| `0x49742` | `init_entity_from_placement` | Fill a `SpriteEntity` from placement + `ObjectTypeDef` |
| `0x498C6` | `run_selection_menu` | Level-select menu (cheat-gated by the POOKY flag) |
| `0x499A0` | `show_selection_menu` | Draw that menu |
| `0x499B8` | `enter_screen_with_fade` | Fade out, load the room, fade in |
| `0x499C2` | `init_screen_pointers` | Load tilemap/transition/placement pointers from `RoomHeader` |
| `0x49A20` | `process_level_transition_point` | Walk `TransitionWaypoint`s; advance room or level |
| `0x49B52` | `render_new_screen` | Hard room cut: decode + draw, no scroll |
| `0x49B5C` | `render_screen_twice` | Prime both buffers after a hard cut |
| `0x49BD6` | `scroll_view_up` | Scroll the view up (`world_row_base -= 8`) |
| `0x49C78` | `scroll_view_down` | Scroll the view down (`world_row_base += 8`) |
| `0x49D18` | `finish_scroll_transition` | Settle after a scroll; respawn screen entities |
| `0x49D8C` | `decode_two_tile_columns` | Consume sub-tile scroll remainder |
| `0x49DD2` | `copy_column_block` | Bulk-copy decoded tile data into the blit buffer |
| `0x49E28` | `decode_level_tiles_to_cache` | Expand packed tilemap into `room_tile_map` |
| `0x49E88` | `write_tile_column_to_objbuf` | Scatter one tile column into the object buffer |

## Rendering and HUD — detail: [`algo-render.md`](algo-render.md)

| Address | Name | Purpose |
|---|---|---|
| `0x4AC08` | `hide_entity` | Clear draw-enable on both buffers. **Dead code — no callers** |
| `0x4AC16` | `clear_sprite_flags` | Reset type and render flags on all 13 slots |
| `0x4AC3E` | `despawn_offscreen_entity` | Free a slot and schedule a final erase-blit |
| `0x4AC8C` | `blit_backgrounds` | Restore background under each sprite footprint |
| `0x4B032` | `render_sprites` | Dispatch each entity, clip, and composite the sprite blit |
| `0x4B358` | `init_hud_state` | Zero score, set bullets/dynamite/lives = 6, force redraw |
| `0x4B3BC` | `hud_update_score` | Redraw the score if dirty |
| `0x4B3E4` | `add_score` | Add a 3-byte BCD delta and repack display digits |
| `0x4B460` | `hud_update_bullets` | Redraw the bullet count (icon `0xA`) |
| `0x4B494` | `hud_update_dynamite` | Redraw the dynamite count (icon `0xB`) |
| `0x4B4C8` | `hud_update_lives` | Redraw the lives count (icon `0xC`) |
| `0x4B4FC` | `draw_hud_count` | Build and draw an icon-repeat counter string |
| `0x4B588` | `start_level` | Load `level_start_info`, place Rick, restock, show intro |
| `0x4B5F4` | `show_level_intro_screen` | Draw the level banner and story text |
| `0x4B7DA` | `clear_both_screen_buffers` | Zero both 32000-byte buffers |
| `0x4B7FE` | `reset_hud_dirty_and_redraw` | Clear buffers, force all HUD elements |
| `0x4B83A` | `clear_screen_buffer_32000` | Zero one screen buffer |

## Entities: AI, traps, pickups, collision — detail: [`algo-entities.md`](algo-entities.md)

| Address | Name | Purpose |
|---|---|---|
| `0x4B856` | `decorative_sprite_update` | Type 74; drives slot 12 on intro screens |
| `0x4BE20` | `stop_bcd_timer` | Clear the countdown-enable flag |
| `0x4BE28` | `bcd_countdown_timer` | Tick the BCD escape timer |
| `0x4BE68` | `trigger_zone_22` | Wrapper → `trigger_zone_update` + start-timer effect |
| `0x4BE7C` | `effect_start_escape_timer` | Start the 20.00 countdown, play track `0x12` |
| `0x4BEA2` | `trigger_zone_23` | Wrapper → `trigger_zone_update` + stop-timer effect |
| `0x4BEB6` | `effect_stop_timer_award_bonus` | Stop the timer, bank remaining time as score |
| `0x4BEDC` | `trigger_zone_update` | Invisible trigger zone; invokes the `A2` effect |
| `0x4BF30` | `reset_player_state` | Restart-a-life initialiser; restock bullets/dynamite |
| `0x4BFAE` | `spawn_player_entity` | Set `sprite_list[1].wType = 1` |
| `0x4BFC2` | `save_checkpoint_state` | Save per-room checkpoint |
| `0x4C000` | `restore_checkpoint_state` | Restore it on respawn |
| `0x4D00C` | `destructible_pickup_16` | Dynamite crate wrapper |
| `0x4D020` | `destructible_pickup_17` | Ammo crate wrapper |
| `0x4D034` | `effect_refill_dynamite` | `bDynamite = 6` |
| `0x4D046` | `effect_refill_bullets` | `bBullets = 6` |
| `0x4D058` | `destructible_pickup_update` | Shared crate logic: break, collect, or kill |
| `0x4D0E2`–`0x4D0FA` | `treasure_pickup_18`–`21` | Treasure wrappers (gfx `type*0x150 + 0x2F70E`) |
| `0x4D102` | `treasure_pickup_update` | Shared treasure logic: score, sparkle, despawn |
| `0x4D15C` | `scripted_trap_update` | **Shared handler for types 24–73** — the trap engine |
| `0x4D39C`–`0x4D4E2` | `enemy_update_4`–`15` | 12 wrappers: AI mode in `D0.b` + sprite bank |
| `0x4D4F4` | `enemy_ai_update` | Shared enemy AI: patrol / seek / chase / die |
| `0x4D87C` | `kill_enemy` | Death launch, score, mark placement dead |
| `0x4D8B0` | `entity_touches_hazard_or_block` | Test vs. slot 0 and hazard-active slots 4–8 |
| `0x4D986` | `trigger_box_contains_point` | Point-in-trigger-box test |
| `0x4D9AA` | `entity_overlaps_player` | Entity hitbox vs. Rick (crouch-adjusted) |
| `0x4DA30` | `mark_placement_dead` | Set the DEAD bit so the object never respawns |
| `0x4DA40` | `probe_entity_tile_collision` | Enemy tile probe; **returns via carry flag** |

## Player — detail: [`algo-player.md`](algo-player.md)

| Address | Name | Purpose |
|---|---|---|
| `0x4C046` | `player_controller` | Type 1. Input, movement, jump, climb, crouch, attacks |
| `0x4C7E4` | `kill_player` | Start the death sequence; decrement `bLives` |
| `0x4C846` | `player_death_physics` | Tumbling-body physics with wall bounce |
| `0x4C8B2` | `player_sprite_update` | Lethal-tile check, then frame selection (continuation) |
| `0x4C8C2` | `player_select_anim_frame` | Frame selection without the lethal check |
| `0x4CA5A` | `player_bullet_update` | Type 2; bullet motion and solid test |
| `0x4CAA8` | `player_dynamite_update` | Type 3; fuse → explosion, publishes the blast point |
| `0x4CBF0` | `stick_attack_hits_entity` | Stick-jab hit test |
| `0x4CC10` | `bullet_hits_entity` | Bullet hit test; consumes the bullet |
| `0x4CC4C` | `entity_contains_point` | Generic point-in-hitbox test |
| `0x4CC92` | `explosion_overlaps_entity` | Blast-radius test |
| `0x4CCFC` | `bullet_hit_solid_test` | Bullet vs. tile / slot-0 block |
| `0x4CD70` | `probe_player_tile_collision` | Player tile probe → `player_collision_flags` |

---

## Cross-references

- **Entity type → handler**: [`entities.md`](entities.md) (74-entry dispatch table)
- **Struct, table and global layouts**: [`data-structures.md`](data-structures.md)
- **In-game text and font encoding**: [`strings.md`](strings.md)
- **Memory map, hardware registers, capture limits**: [`memory_map.md`](memory_map.md)
- **Open questions and plan**: [`../reverse-plan.md`](../reverse-plan.md)

## Level loading — resolved: there is none

The program contains exactly two traps (`Super`, `Setscreen`) and no file or sector
call of any kind, so it cannot touch the disk. All four levels are already resident,
sharing just two tile banks. A reimplementation needs no loader. Details in
`memory_map.md`. **Do not re-run the GEMDOS search** — the answer is "absent", not
"not yet found".
