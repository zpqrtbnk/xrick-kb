# Rick Dangerous — Level, Scroll & Tile Algorithms (`0x495E0`–`0x49F1E`)

Exact transcription of the 18 functions in `0x495E0`–`0x49F1E`: entity spawning, the
level/room transition machinery, the room scroll animation, and the tile decode
pipeline. **Includes the previously-unknown tilemap encoding** (§ "Level graphics
data model").

All addresses are Atari ST physical addresses = offsets into `re/atari_ram.bin`.
Struct/field names follow `re/data-structures.md`. Ghidra plate comments hold the raw
evidence; this file is the re-codable form. Everything below is transcribed from
**disassembly**, not decompiler output.

## Conventions

This is hand-written 68000 assembly with **register-passed arguments** and no stack
frames. Each function below states its register contract. Notation:
`(0x4,A1).w` = 16-bit read/write at `A1+4`; `.b`/`.l` = 8/32-bit.

`dbf Dn,target` loops **n+1** times (it exits when the counter goes to −1), so
`move.w #0x7,D2 ; dbf D2` is **8** iterations. Every loop count below is already
converted to the true iteration count.

---

## Level graphics data model (the headline result)

The room geometry is a **three-level indirection**, and — importantly — **there is no
compression anywhere**. Every stage is a flat array.

```
RoomHeader.pTileMap  →  block-index stream   (1 byte per block, uncompressed)
        │
        │  decode_level_tiles_to_cache: block → 4×4 tile indices
        ▼
room_tile_map @0x4A17E  →  tile-index map    (1 byte per tile, 32 cols × 44 rows)
        │                                     collision reads this directly
        │  decode_two_tile_columns: tile → 8×8 pixels
        ▼
screen buffer                                (4-plane ST low-res)
```

### 1. Block-index stream (`RoomHeader.pTileMap`, e.g. `0x2101E` for room 0)

A plain byte array. **One byte = one block index.** No RLE, no terminator — the
extent is implied by how much the decoder reads.

- **8 bytes per block-row** (8 blocks across).
- A block is **4 tiles wide × 4 tiles tall** = 32×32 pixels.
- 8 blocks × 4 tiles = **32 tile columns** per row, which is exactly the `0x20`-byte
  row stride of `room_tile_map`.

Vertical indexing: `decode_level_tiles_to_cache` reads from
`cur_tilemap_ptr + (world_row_base & ~3) * 2`. Since one block-row spans 4 tile rows
and occupies 8 bytes, advancing `world_row_base` by 4 advances the source by 8 bytes
— i.e. `(wrb & ~3) * 2` is exactly "block-row index × 8".

### 2. Block definition table (`0x22FEE`, 16 bytes/block)

`block_defs[block] = 0x22FEE + block*16`, a **4×4 grid of tile indices** stored
row-major (4 bytes per sub-row).

### 3. Tile-index map (`room_tile_map` @ `0x4A17E`)

- **32 columns × 44 rows**, 1 byte per tile, **`0x20` bytes per row**, row-major.
- Total `0x580` bytes (`0x4A17E`–`0x4A6FD`), ending immediately before the scroll
  flag `0x4A6FE` and the scroll delta `0x4A700` — a hard boundary confirming the size.
- Indexed by collision code as `room_tile_map[(Y/8)*0x20 + (X/8)]`.

### 4. Tile graphics (`tile_gfx_base_ptr` = `0x1D01E` or `0x1F01E`)

`tile_gfx[tile] = base + tile*32`. **32 bytes per tile = 8×8 pixels, 4 bitplanes,
4 bytes per pixel-row** (one byte per plane).

### 5. Tile attributes (`tile_attr_table_ptr` = `0x49F1E` or `0x4A01E`)

A flat **256-byte LUT**, one attribute byte per tile index (`0x49F1E`–`0x4A01D`
exactly). Observed values: `0x01` background/decorative, `0x40` solid, `0x82` wall
group.

The two banks (`0x1D01E`+`0x49F1E` vs `0x1F01E`+`0x4A01E`) are selected together by
`RoomHeader.wTileBankVariant`.

### Validation performed

Room 0 (`room_headers[0]`: `wTileBankVariant=0`, `pTileMap=0x2101E`), with
`LevelStartInfo[0].wStartWorldRow = 8`:

- Source offset = `0x2101E + (8 & ~3)*2` = `0x2102E`.
- Bytes there are `0x46` (block 70) repeated — the first 40 bytes of the stream are
  all `0x46`, i.e. 5 uniform block-rows.
- `block_defs[70]` = `0x22FEE + 70*16` = `0x2344E` =
  `D9 DA D9 DA | DB DC DB DC | D9 DA D9 DA | DB DC DB DC` — a 4×4 block built from a
  repeating 2×2 tile motif, exactly the shape of a tiled rock texture.
- `tile_attr[0xD9..0xDC]` = `0x40` (solid), read from `0x49F1E+0xD9`.

So the room opens with five block-rows of solid rock. The encoding, the block table,
the map geometry and the attribute LUT are all mutually consistent. **Confirmed.**

---

## Screen geometry constants

| Constant | Value | Meaning |
|---|---|---|
| Scanline stride | `160` bytes | ST low-res, 320 px × 4 planes |
| Playfield origin | `+0x510` from buffer base | `1296 = 8 scanlines × 160 + 16 bytes`, i.e. y=8, x=32 px |
| Playfield size | `128` bytes × `192` rows | 256 px wide × 192 px tall |
| Buffer toggle | `bchg #15` on `0x492EA` | the two buffers are `0x8000` apart |
| Backdrop cache | `0x66010` | clean playfield without sprites |
| Scroll staging | `0x63810` / `0x6D810` | pre-rendered scroll strips |

---

# Functions

## `revive_all_placements` — 0x495E0

```
revive_all_placements()            // no args, no return
```
```c
A0 = 0x481E4;                      // placement_table
for (D0 = 523; D0 != 0; D0--) {    // move.w #0x20a,D0 ; dbf → 523 iterations
    A0[2] &= 0x7F;                 // clear bTypeAndDead bit 7 (DEAD)
    A0 += 6;                       // sizeof(PlacementRecord)
}
```
Notes: clears the DEAD bit across the whole 523-record table so killed enemies,
collected pickups and fired one-shot triggers respawn. Called once per new game.

## `spawn_screen_entities` — 0x49600

```
spawn_screen_entities()            // D0 preserved (saved/restored on stack)
```
```c
if (spawn_scan_flags & 0x02) {     // bit 1: full/初 population — three lookahead bands
    spawn_level_entity(D0 = 0x08);
    spawn_level_entity(D0 = 0x10);
    spawn_level_entity(D0 = 0x18);
}
if (spawn_scan_flags & 0x04)       // bit 2: scrolled up   → band at offset 0
    spawn_level_entity(D0 = 0x00);
if (spawn_scan_flags & 0x01)       // bit 0: scrolled down → band at offset 0x20
    spawn_level_entity(D0 = 0x20);
```
Notes: `D0` is the **lookahead row offset** added to `world_row_base` when matching
`PlacementRecord.wSpawnBand`. `spawn_scan_flags` (`0x495C8`) is set to `7` by
`init_screen_pointers` (populate everything), `4` by `scroll_room_left`, `1` by
`scroll_room_right`.

## `spawn_level_entity` — 0x4964C

```
spawn_level_entity(D0.w = lookahead row offset)     // all regs preserved
```
```c
// --- 1. is any pool slot free at all? ---
for (A1 = &sprite_list[4]; A1 < 0x4A9AE; A1 += 0x4C)
    if (A1->wType == 0) goto have_slot;
for (A1 = &sprite_list[9]; A1 < 0x4AA92; A1 += 0x4C)
    if (A1->wType == 0) goto have_slot;
if (sprite_list[0].wType != 0) return;      // even the block slot is busy
have_slot:

// --- 2. walk this room's placement list ---
A0 = cur_placement_list_ptr;
D1 = D0 + world_row_base;                   // target band
for (;;) {
    D2 = A0->wSpawnBand;                    // (A0).w
    if (D2 == 0x00FF) return;               // sentinel: end of room list
    if ((D2 & 0xFFF8) == D1) {
        if (!(A0->bTypeAndDead & 0x80)) {   // skip DEAD
            if (A0->bTriggerFlags & 0x02) { // block entity → slot 0 only
                if (sprite_list[0].wType == 0)
                    init_entity_from_placement(A0, A1 = &sprite_list[0], D0);
            } else {
                // pool select by type
                A1 = &sprite_list[4];  A2 = 0x4A9AE;      // slots 4..8
                if ((int8)A0->bTypeAndDead < 0x10) {
                    A1 = &sprite_list[9];  A2 = 0x4AA92;  // slots 9..11
                }
                for (; A1 < A2; A1 += 0x4C) {
                    if (A1->wType != 0) continue;
                    if ((int8)A0->bTypeAndDead >= 0x10) {
                        init_entity_from_placement(A0, A1, D0);
                    } else {
                        // dedup: don't respawn a mover that is already live
                        for (A3 = &sprite_list[9]; A3 != 0x4AA92; A3 += 0x4C) {
                            if (A3->wType != 0 && A3->placement_record_ptr == A0)
                                goto next_record;      // already alive
                        }
                        init_entity_from_placement(A0, A1, D0);
                    }
                    break;
                }
            }
        }
    }
next_record:
    A0 += 6;
}
```
Notes / corrections:
- **Pool B is slots 9..11, NOT 9..12.** The bound is `0x4AA92`, which *is* slot 12,
  and the loop is `A1 < bound` — so slot 12 is excluded, reserved for the decorative
  sprite (type 70). `re/data-structures.md` currently says `[9..12]`.
- Type test is a **signed byte** compare (`cmpi.b #0x10 / bge`); safe because the DEAD
  bit is already excluded, so values are 0..0x7F.
- The dedup scan always walks pool B, which is correct since it is only reachable for
  `type < 0x10`.
- Step 1 only proves *some* slot is free; step 2 re-searches the type-appropriate pool
  and may find none, in which case the record is silently skipped.

## `init_entity_from_placement` — 0x49742

```
init_entity_from_placement(A0 = PlacementRecord*, A1 = SpriteEntity*, D0.w = row base)
```
```c
A1->placement_record_ptr = A0;                    // (0x26)
D2 = A0->bTypeAndDead;                            // raw byte; DEAD already clear
A1->wType = D2;                                   // (0x00).w
A2 = 0x47D34 + (D2 << 4);                         // &object_type_defs[type]

A1->nHitboxW      = A2->nHitboxW;                 // (0x10) ← def+2
A1->nHitboxH      = A2->nHitboxH;                 // (0x12) ← def+4
A1->wTriggerSound = *(word*)A2;                   // (0x44) ← def+0
A1->movement_path_table = *(long*)(A2+0xA);       // (0x36) ← def+0xA
A1->nTrigBoxXMax  = (byte)A2[0xE] << 3;           // (0x40) width, 8-px units
A1->nTrigBoxYMax  = (byte)A2[0xF] << 3;           // (0x42) height
A1->gfx_data = 0;                                 // (0x22)
A2 = *(long*)(A2+0x6);                            // anim_frame_table
A1->anim_frame_table = A2;                        // (0x32)
if (A2 != 0) A1->gfx_data = *(long*)A2;           // first frame

// position from bPosXY
D2 = A0->bPosXY;  D1 = D2 & 0xF8;  D2 = (D2 & 7) + D0;  D2 <<= 3;
if (!(A0->bTriggerFlags & 0x04)) D2 = (D2 & ~7) | 3;    // half-cell nudge
A1->nPosY   = D2;    // (0x06)
A1->nPosX   = D1;    // (0x04)
A1->nSpawnX = D1;    // (0x0C)
A1->nSpawnY = D2;    // (0x0E)

// trigger box from bTrigBoxXY (dual-purpose byte)
D2 = A0->bTrigBoxXY;  D1 = D2 & 0xF8;  D2 &= 7;
A1->bAiCooldown = D2;                             // (0x4A) temporarily = subrow
D2 = (D2 + D0) << 3;
A1->nTrigBoxYMin  = D2;                           // (0x3E)
A1->nTrigBoxYMax += D2;                           // (0x42) = YMin + H*8
A1->bAiCooldown   = (byte)(A1->bAiCooldown * 25); // (0x4A) subrow × 0x19
A1->nTrigBoxXMin  = D1;                           // (0x3C)
A1->nAiTimerReload= D1;                           // (0x30) same byte, AI reuse
A1->nTrigBoxXMax += D1;                           // (0x40) = XMin + W*8

A1->wHazardActive = 0;                            // (0x3A)
if (A0->bTriggerFlags & 0x04) A1->wHazardActive = 0xFF;
A1->bTriggerFlags = A0->bTriggerFlags;            // (0x46)
A1->nAnimFrameIdx = 0;  A1->nPathStepIdx = 0;  A1->nPathStepTick = 0;
A1->bAnimActive = 0;                              // (0x47)
A1->nDirection  = 0x00FF;                         // (0x02).w — faces "left"
A1->bChasing    = 0;                              // (0x48)
*(byte*)(A1+0x0A) = 0;                            // high byte of nPosYFrac only
A1->nVelY       = 0x0100;                         // (0x08)
A1->bDying      = 0;                              // (0x49)
```
Notes:
- The `|3` nudge is applied **only when `bTriggerFlags` bit 2 is clear**; hazard-active
  objects sit on the exact cell boundary.
- `clr.b (0xa,A1)` clears **only the high byte** of the `nPosYFrac` word, not the whole
  word. A faithful reimplementation should do the same.
- Confirms the axis convention: `(0x04)` receives `bPosXY & 0xF8` (X), `(0x06)`
  receives the row-derived value (Y).

## `run_selection_menu` — 0x498C6

```
run_selection_menu()               // result in level_select_choice (0x498C0)
```
```c
level_select_choice = 0;                       // 0x498C0
if (menu_enabled == 0 || max_level_reached == 0) return;   // 0x498C4, 0x498C2
palette_fade_out();
vsync_wait();
clear_both_screen_buffers();
blit_image_5120(A0 = 0x437EE);                 // menu backdrop bitmap
// draw one label per unlocked level
D2 = max_level_reached;  D0 = 8;  D1 = 8;  A0 = 0x49858;
do { draw_string_xy(D0, D1, A0);  D1 += 3;  A0 += 0x1A; } while (D2-- );
palette_fade_in();
D2 = 0; D1 = 9;
for (;;) {                                     // cursor loop
    draw_string_xy(D0=?, D1, A0 = 0x48F48);    // draw cursor
    vsync_wait(); vsync_wait(); vsync_wait(); vsync_wait();
    if (player_input_bitmask & 0x80) break;    // FIRE → confirm
    draw_string_xy(A0 = 0x48F4A);              // erase cursor
    if (player_input_bitmask & 0x01) {         // UP
        D2--; D1 -= 3;
        if (D2 < 0) { D2 = 0; D1 = 9; }        // clamp to top
    } else if (player_input_bitmask & 0x02) {  // DOWN
        D2++; D1 += 3;
        if (D2 > max_level_reached) { D2--; D1 -= 3; }   // clamp to bottom
    }
}
level_select_choice = D2;
```
Notes: **partial input-bit mapping recovered here** — `player_input_bitmask`
(`0x4922B`) bit 0 = UP, bit 1 = DOWN, bit 7 = FIRE/confirm. (The player-controller
transcription owns the full mapping; this is independent corroboration.)
Menu label stride is `0x1A` bytes, rows 3 apart. Gated by `0x498C4` — the flag set by
the `"POOKY9999"` easter egg — so the level-select menu is a **cheat-only** screen.
**Needs dynamic verification:** the `D0` (x) argument to the cursor `draw_string_xy`
is set before the loop and not visibly reloaded; confirm on hardware.

## `show_selection_menu` — 0x499A0

```
show_selection_menu()
```
```c
run_selection_menu();
level_index = level_select_choice;     // 0x4B586 ← 0x498C0
start_level();
enter_screen_with_fade();
```

## `enter_screen_with_fade` — 0x499B8

```
enter_screen_with_fade()
```
```c
init_screen_pointers();
palette_fade_in();
```

## `init_screen_pointers` — 0x499C2

```
init_screen_pointers()
```
```c
A0 = cur_room_header_ptr;                       // 0x495D8
tile_gfx_base_ptr   = 0x1D01E;                  // 0x495D0
tile_attr_table_ptr = 0x49F1E;                  // 0x495D4
if (*(word*)A0 != 0) {                          // RoomHeader.wTileBankVariant
    tile_gfx_base_ptr   = 0x1F01E;
    tile_attr_table_ptr = 0x4A01E;
}
cur_tilemap_ptr        = *(long*)(A0 + 0x2);    // 0x495CC ← pTileMap
cur_placement_list_ptr = *(long*)(A0 + 0xA);    // 0x495DC ← pPlacements
spawn_scan_flags = 7;                           // 0x495C8 — populate all bands
scroll_active    = 0;                           // 0x4A6FE
save_checkpoint_state();
render_new_screen();
```
Notes: offsets `+0x2` and `+0xA` are **disassembly-verified** (an older
decompiler-derived comment wrongly placed `pPlacements` at `+5`). Note the two tile
banks switch graphics *and* attributes together.

## `process_level_transition_point` — 0x49A20

```
process_level_transition_point()
```
```c
D4 = 0;                                          // "fade in at end" flag
D0 = (player_pos_y_copy >> 3) + world_row_base;  // 0x4A754 → world row
A0 = cur_room_header_ptr->pTransitions;          // (0x6, header)
D2 = (player_pos_x_copy > 0) ? 1 : 0;            // 0x4A752 → exit side
                                                 // off the left makes X ≤ 0
for (;;) {
    D3 = A0->wExitSide;                          // (A0).w
    if (D3 == 0x00FF) goto reposition;           // sentinel: no match
    if (D3 == D2) {
        D1 = D0 - A0->wRow;                      // (0x2,A0)
        if (D1 >= 0 && D1 <= 2) break;           // matched within a 3-row window
    }
    A0 += 0xA;                                   // sizeof(TransitionWaypoint)
}

cur_room_header_ptr = A0->pNextRoomHeader;       // (0x4,A0)
if (A0->pNextRoomHeader == -1) {                 // ---- END OF LEVEL ----
    if (max_level_reached != 3) {                // 0x498C2
        D0 = level_index + 1;
        if (D0 >= max_level_reached) max_level_reached = D0;
    }
    level_index++;                               // 0x4B586
    if (level_index >= 4 && level_select_choice != 0) {
        palette_fade_out();
        goto game_complete;
    }
    if (level_index >= 4) {                      // award remaining lives
        D1 = HudCounters.bLives;
        do { add_score(D0 = 0x100000); } while (D1--);
    }
    start_level();
    D4 = 0xFF;
    if (level_index < 4) goto do_init;           // next level
game_complete:
    D4 = 0;
    return_to_attract = 0xFF;                    // 0x4DE2C
    goto finish;
}
// ---- ordinary room-to-room move ----
D0 = A0->wRow - A0->wEntryRow;                   // (0x2,A0) − (0x8,A0)
world_row_base -= D0;

reposition:
if (D2 != 0) player_pos_x_copy = 0x02;           // came out the right → enter left
else         player_pos_x_copy = 0xE6;           // came out the left  → enter right
do_init:
init_screen_pointers();
finish:
if (D4 != 0) palette_fade_in();
```
Notes:
- **`0x4A752` is X and `0x4A754` is Y** — proven here: `0x4A754` is shifted right by 3
  and added to `world_row_base` (a row), while `0x4A752` decides left/right. This
  contradicts the `CheckpointState` field notes (see corrections).
- The end-of-game bonus is `0x100000` BCD (100,000 points) **per remaining life**,
  looped `bLives + 1` times (`dbf` semantics).
- The `reposition` label is also reached on the sentinel path, so a player who walks
  off an edge with no matching waypoint is still shunted to the opposite edge and the
  room is re-initialised.

## `render_new_screen` — 0x49B52

```
render_new_screen()
```
```c
decode_level_tiles_to_cache();
render_screen_twice();
```

## `render_screen_twice` — 0x49B5C

```
render_screen_twice()              // all regs preserved
```
```c
A0 = 0x4A27E;                      // room_tile_map + 0x100 → tile row 8
A1 = (screen_base ^ 0x8000) + 0x510;         // back buffer playfield
decode_two_tile_columns(A0, A1, D0 = 23);    // 24 tile rows = 192 scanlines
copy_column_block(A0 = A1, A1 = 0x66010, D0 = 191);   // save clean backdrop
blit_backgrounds();
spawn_screen_entities();
render_sprites();
flip_screen_buffer();
vsync_wait();
// repeat for the other buffer, restoring from the cached backdrop
A0 = 0x66010;
A1 = (screen_base ^ 0x8000) + 0x510;
copy_column_block(A0, A1, D0 = 191);
blit_backgrounds();
render_sprites();
flip_screen_buffer();
vsync_wait();
```
Notes: "twice" = both screen buffers are painted, so the double buffer is coherent
after a room change. `0x66010` becomes the sprite-free backdrop that
`blit_backgrounds` later restores from.

## `scroll_room_left` — 0x49BD6  ⚠️ **misnomer: this scrolls the view UP**

```
scroll_room_left()                 // really: scroll_view_up
```
```c
world_row_base -= 8;               // 0x495CA — 8 tile rows = 64 px
decode_level_tiles_to_cache();
scroll_active = 0xFF;              // 0x4A6FE
scroll_delta  = +8;                // 0x4A700 — added to entity Y each frame
scroll_step   = 0;                 // 0x49D8A
for (;;) {                                   // 8 animation frames
    D0 = scroll_step;
    A0 = 0x4A35E - (D0 << 5);                // room_tile_map row 15, walking up
    A1 = 0x63810 + (7 - D0) * 0x500;         // staging strip
    decode_two_tile_columns(A0, A1, D0 = 0); // one tile row
    A0 = A1;
    A1 = (screen_base ^ 0x8000) + 0x510;
    copy_column_block(A0, A1, D0 = 191);
    if (scroll_step == 7) break;
    blit_backgrounds();
    render_sprites();
    flip_screen_buffer();
    vsync_wait();
    scroll_step++;
}
spawn_scan_flags = 0x04;           // 0x495C8 — spawn the newly-revealed band
finish_scroll_transition();
```

## `scroll_room_right` — 0x49C78  ⚠️ **misnomer: this scrolls the view DOWN**

```
scroll_room_right()                // really: scroll_view_down
```
```c
world_row_base += 8;
decode_level_tiles_to_cache();
scroll_active = 0xFF;
scroll_delta  = -8;
scroll_step   = 0;
for (;;) {
    D0 = scroll_step;
    A0 = 0x4A47E + (D0 << 5);                // room_tile_map row 24, walking down
    A1 = 0x6D810 + D0 * 0x500;
    decode_two_tile_columns(A0, A1, D0 = 0);
    A1 -= 0x7300;                            // rebase into the staging strip
    A0 = A1;
    A1 = (screen_base ^ 0x8000) + 0x510;
    copy_column_block(A0, A1, D0 = 191);
    if (scroll_step == 7) break;
    blit_backgrounds();
    render_sprites();
    flip_screen_buffer();
    vsync_wait();
    scroll_step++;
}
spawn_scan_flags = 0x01;
finish_scroll_transition();
```
Notes on both scrollers: `world_row_base` moves by 8 tile rows (64 px) in one step at
the *start*, then the 8-frame loop reveals the new content 8 px at a time by sliding
the source window. `scroll_delta` (`0x4A700`) is consumed by `render_sprites` to shift
live entities with the world. The mirror-image staging bases (`0x63810` counting down
vs `0x6D810` counting up, the latter rebased by `−0x7300`) are what make the two
directions share the same inner code shape.

## `finish_scroll_transition` — 0x49D18

```
finish_scroll_transition()
```
```c
A0 = (screen_base ^ 0x8000) + 0x510;
copy_column_block(A0, A1 = 0x66010, D0 = 191);   // new backdrop ← scrolled screen
blit_backgrounds();
render_sprites();
flip_screen_buffer();
vsync_wait();
A0 = 0x66010;
A1 = (screen_base ^ 0x8000) + 0x510;
copy_column_block(A0, A1, D0 = 191);             // paint the other buffer
blit_backgrounds();
scroll_active = 0;                               // 0x4A6FE
scroll_delta  = 0;                               // 0x4A700
spawn_screen_entities();
render_sprites();
flip_screen_buffer();
vsync_wait();
```

## `decode_two_tile_columns` — 0x49D8C

Renders a band of the tile map into a 4-plane buffer. The name refers to the two
tiles that share each 16-pixel plane group.

```
decode_two_tile_columns(A0 = tile-index src, A1 = dest, D0.w = tile rows − 1)
                                                        // all regs preserved
```
```c
A4 = tile_gfx_base_ptr;                 // 0x1D01E or 0x1F01E
do {                                    // D0+1 tile rows
    A3 = A1;
    for (int i = 0; i < 16; i++) {      // move.w #0xf,D1 ; dbf → 16 groups
        D2 = *A0++;                     // left tile index
        A2 = A4 + (D2 << 5);            // tile*32
        write_tile_column_to_objbuf(A2, A3);        // bytes 0,2,4,6 = left 8 px
        D2 = *A0++;                     // right tile index
        A2 = A4 + (D2 << 5);
        A3 += 1;
        write_tile_column_to_objbuf(A2, A3);        // bytes 1,3,5,7 = right 8 px
        A3 += 7;                        // next 16-px plane group (8 bytes total)
    }
    A1 += 0x500;                        // 8 scanlines × 160
} while (D0-- );
```
Notes: 16 groups × 2 tiles = **32 tiles = 256 px** per row, matching the map's 32
columns. `A0` advances 32 bytes per tile row, i.e. exactly one `room_tile_map` row.
The `+1` / `+7` split is what interleaves two 8-px tiles into one 16-px plane group.

## `copy_column_block` — 0x49DD2

```
copy_column_block(A0 = src, A1 = dst, D0.w = rows − 1)   // all regs preserved
```
```c
do {
    for (int i = 0; i < 32; i++) *(long*)A1++ = *(long*)A0++;  // 32 longs = 128 B
    A0 += 0x20;  A1 += 0x20;            // 128 + 32 = 160 = one scanline
} while (D0-- );
```
Notes: a 256-px-wide (128-byte) blit with a 160-byte stride — copies just the
playfield column and skips the HUD margin. The 32 `move.l`s are fully unrolled.

## `decode_level_tiles_to_cache` — 0x49E28

**Expands the block-index stream into the tile-index map.**

```
decode_level_tiles_to_cache()      // no args; clobbers D0-D2, A0-A3
```
```c
A0 = 0x4A17E;                                    // room_tile_map
D0 = world_row_base;
D1 = (D0 & 3) * 0x20;
A0 -= D1;                                        // fine vertical alignment
A2 = cur_tilemap_ptr + ((D0 & ~3) * 2);          // block-row index × 8 bytes
for (int row = 0; row < 11; row++) {             // move.w #0xa,D1 ; dbf → 11
    A1 = A0;
    for (int col = 0; col < 8; col++) {          // move.w #0x7,D2 ; dbf → 8
        D0 = *A2++;                              // block index
        A3 = 0x22FEE + (D0 << 4);                // &block_defs[block]
        *(long*)(A1 + 0x00) = *(long*)A3;        // 4 tile indices, sub-row 0
        *(long*)(A1 + 0x20) = *(long*)(A3 + 4);  // sub-row 1
        *(long*)(A1 + 0x40) = *(long*)(A3 + 8);  // sub-row 2
        *(long*)(A1 + 0x60) = *(long*)(A3 + 12); // sub-row 3
        A1 += 4;                                 // next block = 4 tile columns
    }
    A0 += 0x80;                                  // 4 map rows (4 × 0x20)
}
```
Notes: writes `11 × 0x80 = 0x580` bytes — the whole map. The `-(wrb & 3)*0x20` bias
lets the decoder write a window that is offset by the sub-block scroll remainder, so
the map stays aligned to the current scroll position without re-shifting it.

## `write_tile_column_to_objbuf` — 0x49E88

```
write_tile_column_to_objbuf(A2 = tile gfx (32 B), A3 = dest)   // A2,A3 preserved
```
```c
for (int row = 0; row < 8; row++) {   // fully unrolled in the original
    A3[0] = *A2++;                    // plane 0
    A3[2] = *A2++;                    // plane 1
    A3[4] = *A2++;                    // plane 2
    A3[6] = *A2++;                    // plane 3
    A3 += 0xA0;                       // 160 = one scanline
}
```
Notes: writes one byte per plane per row — the **high** byte of each plane word when
`A3` is even (left 8 px of the group), the **low** byte when `A3` is odd (right 8 px).
That is exactly how `decode_two_tile_columns` packs two tiles per group. The final
row uses `move.b (A2),(0x6,A3)` without post-increment (harmless; the pointer is dead).

---

## Corrections for the orchestrator

1. **`re/data-structures.md` — `CheckpointState` axes are swapped.** It says
   `wSaved_a752` = "player room-Y" and `wSaved_a754` = "player room-X". The reverse is
   true: `process_level_transition_point` shifts `0x4A754` right by 3 and adds it to
   `world_row_base` (a row → Y), and tests `0x4A752` for the left/right exit side (X).
   The `player_pos_x_copy` / `player_pos_y_copy` labels already in Ghidra are correct;
   only the CheckpointState prose is wrong.
2. **`re/data-structures.md` — spawn pool B is slots `[9..11]`, not `[9..12]`.** The
   loop bound `0x4AA92` is slot 12 and the test is strict (`A1 < bound`). Slot 12 is
   reserved for the decorative sprite, consistent with `re/entities.md`.
3. **`scroll_room_left` / `scroll_room_right` are misnomers** — they scroll the view
   **up** and **down** respectively (`world_row_base −= 8` / `+= 8`). Suggested names:
   `scroll_view_up` / `scroll_view_down`.
4. **`room_tile_map` is 32 columns × 44 rows**, `0x20` bytes per **row** (row-major).
   `re/data-structures.md` describes it as "0x20 bytes per 8px column, column-major".
5. The level-select menu is **cheat-gated** by `0x498C4` (the `POOKY9999` flag), so it
   is unreachable in normal play — relevant to the outstanding
   "`run_selection_menu`'s exact trigger condition" question.
