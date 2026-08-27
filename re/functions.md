# Rick Dangerous — Identified Functions

All addresses are Atari ST physical addresses (= offsets into `re/atari_ram.bin`).  
Ghidra program: `atari_ram.bin`, image base `0x000000`.

---

## Main Loop Structure

The game's text segment starts at `0x1B018` with a single `JMP $4DC2A` instruction that immediately transfers to `main_init_and_loop`.

`main_init_and_loop` runs a one-time initialization sequence (approximately `0x4DC2A`–`0x4DCCD`), then falls into the **main game loop** at `0x4DCCE`. The loop never exits under normal gameplay.

### Per-Frame Sequence (main loop at `0x4DCCE`)

Each iteration of the loop does the following, in order:

1. **HUD update** — four `hud_update_elementN` calls check dirty flags; if set, re-render the corresponding HUD element to screen.
2. **State dispatch** on two flags:
   - `0x4BF18` ("game running" boolean)
   - `0x4A74E` (secondary state flag)
3. **Active gameplay path** (both flags nonzero):
   1. `blit_backgrounds` — copy background tile data to offscreen buffer
   2. `render_sprites` — pixel-accurate sprite composite into bitplanes
   3. `bcd_countdown_timer` — decrement in-game timer
   4. `update_prng` — advance pseudo-random state
   5. `flip_screen_buffer` — wait for VBlank, swap displayed buffer
   6. `vsync_wait` — sync to next VBlank tick
   7. Loop back to `0x4DCCE`
4. **Other states** (player dying, level transition, game over) — the loop has additional branches that call different subsets of functions before looping back.

---

## Function Catalog

### Interrupt Handlers and Interrupt Setup

| Address | Name | Description |
|---------|------|-------------|
| `0x492EE` | `install_vblank_handler` | Writes `vblank_isr` address into exception vector `0x70` (68K level-4 autovector = Atari ST VBlank) |
| `0x492FA` | `vblank_isr` | VBlank interrupt service routine. Increments the frame counter byte at `0x49334`, calls a per-frame work function, then RTE |
| `0x45006` | `setup_timer_a` | Installs `timer_a_music_isr` at vector `0x134` (MFP Timer A), sets bits in MFP IERB/IMRB to enable the interrupt |
| `0x45022` | `timer_a_music_isr` | Timer A ISR. Streams one step of music data from a pointer-driven data sequence to the YM2149 PSG via `0xFFFF8800`. RTE at end |

### Synchronization

| Address | Name | Description |
|---------|------|-------------|
| `0x49310` | `vsync_wait` | Busy-waits on the frame counter byte at `0x49334`. Blocks until `vblank_isr` has fired at least once since the last call, then clears the counter and returns. This is the frame-rate governor |
| `0x49336` | `flip_screen_buffer` | Waits for a VBlank tick (same poll loop as `vsync_wait`), toggles a buffer-select bit at `0x492EC`, then writes the new screen base address to `0xFF8201` and `0xFF8203` — performs the double-buffer page flip |

### Rendering

| Address | Name | Description |
|---------|------|-------------|
| `0x4AC8C` | `blit_backgrounds` | Iterates the sprite object list at `0x4A702` (sentinel `0xFFFF`). For each entry, copies a block of pixel data from the sprite data buffer at `0x65B00+` into the offscreen screen buffer. Stride between rows is `0x94` bytes. Object record size is `0x4C` bytes |
| `0x4B032` | `render_sprites` | Iterates the same sprite object list. For each entry: (1) dispatches to a per-type update function via the jump table at `0x4AAE0`; (2) clips to screen bounds (Y: 0–0xF0, X: 0–0x142); (3) composites the sprite into the offscreen bitplane buffer using pixel-shift (ROR.L) + mask (AND) + paint (OR). Handles both word-aligned and sub-word-offset cases. Updates pointers to two screen planes (A2 and A2+8) plus a third at A2+0x10 |
| `0x494E2` | *(unnamed)* | Renders a single character from the game font into one screen buffer. Called by `draw_string` |

### Text and HUD

| Address | Name | Description |
|---------|------|-------------|
| `0x49466` | `draw_string` | Renders a `0xFF`-terminated string to both screen buffers (`0x70000` and `0x78000`). Each byte is a character index; font data is at `0x1B01E` (32 bytes per glyph). `D0` is the screen position offset |
| `0x49446` | `draw_string_xy` | Wrapper around `draw_string`. Converts (x=D0, y=D1) coordinates to a linear screen offset and calls `draw_string`. Character cells are 8 pixels wide; screen row stride is 1280 bytes |
| `0x4B4FC` | `draw_hud_count` | Fills a 6-character buffer with blank characters (`0x5E`), then overwrites the first `D1` positions with icon character `D2`, then calls `draw_string`. Used to render icon-count HUD elements (lives, ammo, etc.) |
| `0x4B3BC` | `hud_update_element1` | Checks dirty flag at `0x4B350`. If set: renders the static HUD element at screen offset `0x10` from the data at `0x4B330`, then clears the flag |
| `0x4B460` | `hud_update_element2` | Checks dirty flag at `0x4B352`. If set: calls `draw_hud_count` with count from `0x4B32A`, icon character `0xA`, screen offset `0x31`. Clears flag |
| `0x4B494` | `hud_update_element3` | Checks dirty flag at `0x4B354`. If set: calls `draw_hud_count` with count from `0x4B32C`, icon character `0xB`, screen offset `0x51`. Clears flag |
| `0x4B4C8` | `hud_update_element4` | Checks dirty flag at `0x4B356`. If set: calls `draw_hud_count` with count from `0x4B32E`, icon character `0xC`, screen offset `0x78`. Clears flag |

HUD dirty flags (`0x4B350`–`0x4B356`) are set by game logic when the corresponding counter changes. The four elements likely correspond to lives, bullets, dynamite sticks, and one other (keys?).

### Palette and Screen Setup

| Address | Name | Description |
|---------|------|-------------|
| `0x4DE40` | `init_screen_and_palette` | Calls `xbios_setscreen` to set the video mode, then calls `set_palette` to load the initial palette from `0x4DEE2`, then zeros a state word |
| `0x4935E` | `xbios_setscreen` | Thin wrapper: pushes args and executes `TRAP #14` (XBIOS), function 5 (Setscreen) |
| `0x4937C` | `set_palette` | Copies 16 color words from A0 into hardware palette registers `0xFF8240`–`0xFF825E` |
| `0x49394` | `palette_fade_in` | Animates the palette from black toward the target at `0x4DEE2`. Over 8 steps, increments each RGB component of each of 16 palette entries by 1 per step if it is below the target. Calls `vsync_wait` between steps. Writes directly to `0xFF8240` |

### Sound and Music

| Address | Name | Description |
|---------|------|-------------|
| `0x44C10` | `reset_sound_chip` | Writes `0` to all 14 YM2149 PSG registers via `0xFFFF8800`/`0xFFFF8802`. Clears MFP interrupt registers `0xFFFFFA19` and `0xFFFFFA1F`. Zeroes music state variables at `0x45096`–`0x45005` |
| `0x44CCE` | `play_music` | Starts music playback. D0 = track index (looks up entry in table at `0x44F08`, stride 8 bytes). D1 = variant (0 = loop, 1 = one-shot). Three track types handled: type 0 = direct sample via `0x45116`, type 1 = tracked music with sequence table, type 2 = pattern-based. Sets up data pointers for `timer_a_music_isr` |

### Sprite Object List

| Address | Name | Description |
|---------|------|-------------|
| `0x4AC16` | `clear_sprite_flags` | Iterates sprite object list at `0x4A702`. For each entry, zeros the type word (offset 0) and two flag words (offsets `0x16` and `0x1C`). Stops at sentinel `0xFFFF`. Called at level start and on player death to reset sprite visibility state |

### Timers and Game State

| Address | Name | Description |
|---------|------|-------------|
| `0x4BE28` | `bcd_countdown_timer` | Checked only if flag at `0x4BE18` is nonzero. Decrements tick counter at `0x4BE1A`; when it hits zero, resets to 25 and uses SBCD (subtract BCD) to decrement the BCD timer value stored at `0x4BE1E`/`0x4BE20`. Clears the enable flag when the BCD value reaches zero |
| `0x49596` | `update_prng` | Advances the game's PRNG state. Reads two 32-bit words from `0x495C0` and `0x495C4`, performs ROL.L #3, subtract, XOR, and writes them back. Called once per frame in the active gameplay path |

### Hardware / OS Initialization

| Address | Name | Description |
|---------|------|-------------|
| `0x4DE2E` | `clear_screen_buffers` | Zeroes `0x1C800` bytes (115,712 bytes) starting at `0x63800` using a `clr.l (A0)+` / `dbf` loop. Clears sprite pixel buffers and screen memory before game start |
| `0x4922E` | `init_keyboard` | Configures the ACIA at `0xFFFC00`: calls `acia_write` with `0x12` and `0x14` (control/data rate bytes). Installs a keyboard ISR at exception vector `0x118` (MFP interrupt) pointing to `0x49262` |
| `0x4924E` | `acia_write` | Polls `0xFFFC00` bit 1 (ACIA transmit-ready) until set, then writes D0 to `0xFFFC02` |

### Entry Point

| Address | Name | Description |
|---------|------|-------------|
| `0x1B018` | `game_entry` | Text segment start. Contains only `JMP $0004DC2A` — transfers immediately to `main_init_and_loop` |
| `0x4DC2A` | `main_init_and_loop` | Initialization + main game loop. Init sequence: Mshrink, `clear_screen_buffers`, `init_screen_and_palette`, `install_vblank_handler`, `init_keyboard`, `setup_timer_a`, `reset_sound_chip`, `play_music`, load level data, etc. Loop at `0x4DCCE` |

---

## Key Global Variables

| Address | Name (inferred) | Type | Description |
|---------|----------------|------|-------------|
| `0x4A702` | `sprite_list` | Array of 0x4C-byte records | Sprite/entity object list, terminated by `0xFFFF` word |
| `0x4AAE0` | `sprite_type_dispatch` | Table of function pointers | One entry per sprite type (index = type word - 1). Called by `render_sprites` |
| `0x4BF18` | `game_running` | byte | Nonzero while a level is actively running |
| `0x4A74E` | `state_flag` | word | Secondary game state (player alive / transition) |
| `0x4B350`–`0x4B356` | `hud_dirty_flags` | 4 × byte | One per HUD element; set when value changes, cleared after redraw |
| `0x4B32A`–`0x4B32E` | `hud_counters` | 3 × byte | Raw counts rendered by `hud_update_element2/3/4` |
| `0x49334` | `vblank_counter` | byte | Incremented by `vblank_isr`, polled and cleared by `vsync_wait` |
| `0x492EC` | `current_buffer` | byte (bit 7) | Toggles each frame; selects which screen buffer is the render target |
| `0x495C0`, `0x495C4` | `prng_state` | 2 × longword | PRNG state words updated by `update_prng` |
| `0x4DEE2` | `target_palette` | 16 × word | Target palette used by `set_palette` and `palette_fade_in` |
| `0x4BE18` | `timer_enable` | word | Nonzero when the BCD countdown timer is active |
| `0x4BE1A` | `timer_tick` | word | Tick counter (counts down from 25); drives BCD timer update rate |
| `0x4BE1E`–`0x4BE20` | `bcd_timer` | 4 bytes BCD | In-game BCD timer value, decremented by `bcd_countdown_timer` |
| `0x44F08` | `music_track_table` | Array of 8-byte records | Track descriptors indexed by track number; used by `play_music` |
