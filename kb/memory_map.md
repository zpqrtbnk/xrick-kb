# Rick Dangerous — Atari ST Memory Map

Source: `kb/atari_ram.bin` — Hatari RAM snapshot, 327,680 bytes (first 320 KB of Atari physical RAM, addresses `0x00000`–`0x4FFFF`).

---

## Atari ST Physical Memory Layout

| Address Range | Contents |
|---------------|---------|
| `0x00000`–`0x003FF` | 68K exception vector table (256 vectors × 4 bytes) |
| `0x00400`–`0x007FF` | Atari ST TOS system variables |
| `0x00800`–`0x015CF3` | TOS workspace: screen buffers, desktop, file manager data |
| `0x015CF4`–`0x015CFF` | Environment string area (starts with `PATH=…`) |
| `0x01AF18`–`0x01AF17` | GEMDOS basepage for RICK.PRG |
| `0x01B018`–`0x052FFF` | Rick Dangerous game: text segment (229,944 bytes of code + data) |
| `0x053000`–`0x062FFF` | BSS / uninitialized data (zeroed) |
| `0x063800`–`0x07FFFF` | Screen buffers and sprite pixel buffers (zeroed by `clear_screen_buffers`) |

The snapshot cuts off at `0x4FFFF`. The game's text segment nominally ends at `0x53250`, just past the snapshot boundary; the last ~12 KB of the text segment is not captured.

The in-snapshot tail `0x4DF86`–`0x4FFFF` (8,314 bytes) is **PCM sample data** —
confirmed, not merely suspected: `music_track_table` track 8 points at `0x4DF86`
exactly, and track 10 at `0x4FCF2`. See the resolution below.

**✅ Resolved (2026-08-28 reachability analysis)**: the missing region is exactly
**`0x50000`–`0x5324F` = 12,880 bytes** (`p_tbase 0x1B018` + `p_tlen 0x38238` =
`0x53250`; snapshot ends at `0x50000`). It contains **no code**:

- **Nothing executes there.** Of all 4,611 disassembled instructions, the only
  operand in that range is `Super()`'s stack-pointer argument — not a memory access.
- **The game calls `Super(0x5324C)`** (GEMDOS 0x20), so `0x5324C` is the top of the
  **supervisor stack**, which grows *downward into* the uncaptured region.
- **No structural table references it.** Room headers, transitions, object-type defs,
  the placement table and the dispatch table all scan clean. (Apparent hits elsewhere
  are movement-path records — `{duration=5, dX=1}` reads as the longword `0x00050001`.)
- **What does point there is PCM sample data.** `music_track_table` tracks 8, 10 and
  19 → `0x4DF86`, `0x4FCF2`, `0x50DA8`; track 19 lies entirely inside the gap and
  track 10's sample must continue past the cut. The in-snapshot tail is 100% non-zero
  with no trailing padding, consistent with a sample running right up to the boundary.

**Consequence:** the program's *code* is fully captured and fully reversible from this
snapshot.

✅ **The two truncated sound samples were recovered 2026-08-28** from
`kb/atari_ram_1M.bin`, a complete 1 MB capture. ⚠️ That dump loads the game at a
**different base address** — everything shifted by **−0x2054** — so it is *not* a
drop-in replacement. This file and the whole knowledge base use `atari_ram.bin`
numbering; **decided: we do not re-base**. Convert with
`1M_address = doc_address − 0x2054`.

**What "shifted" actually means — measured 2026-08-30.** The delta is a *relocation*,
so the two dumps differ selectively, and this had never been stated precisely:

| Content | Between the two dumps |
|---|---|
| Static data (font, sprite grid, `placement_table`, `object_type_defs`, `music_track_table`) | **byte-identical** — verified over 64-byte samples at five bases |
| Stored **pointers** | **shifted by exactly −0x2054** — `sprite_type_dispatch` **74/74** entries, `RoomHeader`'s `pTileMap`/`pTransitions`/`pPlacements` **141/141** fields |
| Non-pointer struct fields | identical — e.g. `RoomHeader.wTileBankVariant` **47/47** |

So when reading the 1 MB dump: **relocate pointers, do not relocate data.** A naive
byte-diff of the two files will show the pointer tables as "different" and that is
correct behaviour, not corruption — it is what flagged `sprite_type_dispatch` in this
check before the cause was identified.

The track-19 PCM sample at `0x50DA8` (past the 320 KB snapshot) sits at 1M offset
`0x4ED54` and is real waveform data there — confirming it is recoverable only from the
1 MB capture.

The runtime buffers (`0x63800`+, screen buffers `0x70000`/`0x78000`) are outside both
captures but derivable from code.

---

## Key TOS System Variable Values

Recovered from the RAM dump:

| Variable | Address | Value | Meaning |
|----------|---------|-------|---------|
| `_membot` | `0x432` | `0x00015CF4` | Start of user memory |
| `_memtop` | `0x436` | `0x000F8000` | End of user memory (~992 KB machine) |
| `_run` | `0x47A` | `0x00E02F76` | Current process PD (ROM address = TOS/Desktop) |

---

## RICK.PRG Basepage — `0x1AF18`

The GEMDOS basepage was located by scanning for the self-referential `p_lowtpa` pointer.

| Field | Offset | Value | Meaning |
|-------|--------|-------|---------|
| `p_lowtpa` | `+0x00` | `0x0001AF18` | Start of TPA (= basepage address itself) |
| `p_hitpa` | `+0x04` | `0x000F8000` | End of TPA = full user memory |
| `p_tbase` | `+0x08` | `0x0001B018` | Text segment start = **game entry point** |
| `p_tlen` | `+0x0C` | `0x00038238` | Text segment length = 229,944 bytes |
| `p_dbase` | `+0x10` | `0x00053250` | Data segment start (dlen = 0, so BSS follows immediately) |
| `p_bbase` | `+0x18` | `0x00053250` | BSS segment start (blen = 0 in basepage; actual BSS determined by game init) |
| `p_env` | `+0x2C` | `0x0001AF0C` | Environment string pointer |

---

## Game Code Location

| Address | Contents |
|---------|---------|
| `0x1B018` | First instruction: `JMP $0004DC2A` — jumps immediately to `main_init_and_loop` |
| `0x1B01E` | Game font data (32 bytes per character, used by `draw_string`) |
| `0x4DC2A` | `main_init_and_loop` — initialization sequence + main game loop |
| `0x4DCCE` | Main loop start (first instruction the loop returns to each frame) |

---

## Hardware Registers Used

| Address | Register | Usage |
|---------|---------|-------|
| `0xFF8240`–`0xFF825E` | Video color palette (16 × word) | `set_palette`, `palette_fade_in` write colors here each frame |
| `0xFF8201` / `0xFF8203` | Video screen base address (high / mid byte) | `flip_screen_buffer` writes here to switch displayed buffer |
| `0xFFFF8800` / `0xFFFF8802` | YM2149 PSG register select / data | `reset_sound_chip` clears all registers; `timer_a_music_isr` streams music data |
| `0xFFFA07` / `0xFFFA13` | MFP IERB / IMRB (interrupt enable/mask B) | `setup_timer_a` sets bit 5 (Timer A) in both |
| `0xFFFA0F` | MFP ISRB (interrupt in-service B) | `timer_a_music_isr` clears bit 5 at end of ISR |
| `0xFFFC00` / `0xFFFC02` | ACIA status / data (keyboard/MIDI) | `acia_write` waits on status, writes control bytes |

---

## Exception Vectors Installed by the Game

| Vector address | Exception | Handler installed |
|----------------|-----------|------------------|
| `0x00000070` | Level 4 autovector = **VBlank** | `vblank_isr` at `0x492FA` |
| `0x00000118` | MFP interrupt (keyboard) | Keyboard ISR at `0x49262` |
| `0x00000134` | MFP Timer A | `timer_a_music_isr` at `0x45022` |

---

## Screen Buffer Layout

The game uses **double buffering**. Two screen buffers are located at `0x70000` and `0x78000` (✅ **confirmed 2026-08-31, T13** — read directly, not inferred: the screen-address longword at `0x492EA` holds `0x00078000` in `atari_ram.bin`, and `flip_screen_buffer` XORs bit 7 of the mid byte `0x492EC`, alternating the base between `0x00078000` and `0x00070000`. These bytes go straight to the video base registers `0xFF8201`/`0xFF8203`). `flip_screen_buffer` toggles which buffer is displayed by writing to `0xFF8201/03`.

Sprite pixel data is held in a separate area starting at `0x63800` (zeroed by `clear_screen_buffers` at startup, 0x1C800 bytes = 115,712 bytes).

The sprite object list is at `0x4A702` inside the game's text segment (within the 320 KB snapshot). Entries are **0x4C bytes** each, terminated by a word of `0xFFFF`. **Confirmed (2026-08-27 pass): exactly 13 entries** (`0x4A702`–`0x4AADD`), sentinel at `0x4AADE`, immediately followed by the `sprite_type_dispatch` function-pointer table at `0x4AAE0`. Full field layout in `kb/data-structures.md` (struct `SpriteEntity`).

---

## Level Loading — resolved: there is none at runtime

`search_instructions(mnemonic=trap)` across the entire snapshot finds only **two**
TRAP instructions: one `TRAP #14` (XBIOS `Setscreen`) and one `TRAP #1` (GEMDOS),
the latter at `0x4DC34` being **`Super(0x5324C)`** — supervisor-mode entry, with
`0x5324C` as the supervisor stack pointer. (Earlier notes misread this as `Mshrink`,
which is function `0x4A`.) There is no `Fopen`/`Fread`/`Fclose`, no BIOS `Rwabs` and
no XBIOS `Floprd` anywhere: **the code cannot touch the disk at all.**

That is not a gap — it is the answer. **All four levels are already resident**:

- 47 `RoomHeader`s covering every level (entry rooms 0, 9, 20, 38)
- every room tilemap, in one contiguous ~8 KB region (`0x2101E`–`0x22F76`)
- 523 `PlacementRecord`s spanning all levels
- five intro texts (four levels plus the ending) and all four level names
- **only two tile banks**, shared pairwise: bank 0 (`0x1D01E`) serves South America
  and Egypt, bank 1 (`0x1F01E`) serves the Castle and Missile Base

Completing a level is pure pointer arithmetic: `process_level_transition_point` sees
`pNextRoomHeader == -1`, bumps `level_index`, and `start_level` reads the next entry
room from `level_start_info`. No I/O, no decompression, no load pause.

All loading happened **once**, before this snapshot's entry point, during the outer
loader/HPack decompression stage described in `rick.md`. **A reimplementation needs
no loader at all** — just the resident tables.

---

## The 171KB Data Region (0x1B01E–0x44BED) — **fully mapped**

**Completely accounted for, with no gaps** (asset-extraction pass 2026-08-28;
boundaries re-measured from the binary 2026-08-30). Every region below was confirmed by
decoding it and looking at the result — see `kb/assets-manifest.md` — and every start
address equals the previous region's end, from `0x1B01E` through to the first byte of
code at `0x44BEE`.

| Range | Size | Contents |
|---|---|---|
| `0x1B01E`–`0x1BBFD` | 3,040 | **Font**: 95 glyphs × 32 bytes (8×8, 4 planes, byte-per-plane) |
| `0x1BBFE`–`0x1D01D` | 5,152 | **Scenery tiles**: 161 × 32 bytes, same 8×8 format. Real artwork (sky, clouds, pyramids, dunes) — **referenced by nothing in the program**; see `assets-manifest.md`. *(Was "Not identified" until 2026-08-28.)* |
| `0x1D01E`–`0x1F01D` | 8,192 | **Tile bank 0**: 256 × 32-byte tiles — levels 0–1 |
| `0x1F01E`–`0x2101D` | 8,192 | **Tile bank 1**: 256 × 32-byte tiles — levels 2–3 |
| `0x2101E`–`0x22FED` | 8,144 | **Room tilemaps**, all 47 rooms, contiguous |
| `0x22FEE`–`0x23FED` | 4,096 | **Block definitions**: 256 × 16 bytes (4×4 tile indices) |
| `0x23FEE`–`0x2BFED` | **32,768** | **Title screen.** `draw_title_picture` copies exactly `0x400` iterations × 8 longwords = `0x8000` bytes (`move.w #0x3ff,D0w` … `dbf` at `0x4DF6C`–`0x4DF80`). The *visible* screen is 32,000 bytes; the extra 768 land in the buffer's slack, since the two screen buffers are `0x8000` apart (`bchg #15`). **Corrected 2026-08-30** — was "32,000, `0x23FEE`–`0x2BB2D`", which matched neither the blit size nor its own end address |
| `0x2BFEE`–`0x3D62D` | **71,232** | **Sprite frames**: 212 × `0x150`, plane-major. **Corrected 2026-08-30** — was "~`0x2C000`–`0x34000`, ~32 KB", understating the region by more than half |
| `0x3D62E`–`0x40FED` | 14,784 | **Entirely zero** — measured, not estimated: zero non-zero bytes in the whole range. Padding, not an unfilled buffer (see note below) |
| `0x40FEE`–`0x44BED` | 15,360 | **Three 320×32 banners** (5120 bytes each) |

The banner block ends at exactly `0x44BEE`, which is the first byte of code
(`blit_image_5120`) — a hard boundary confirming there are exactly three banners.

**About the zero regions:** an earlier pass could not tell "not yet loaded" from
"genuinely unused". That is now settled — since the program performs **no disk I/O at
all** and every level's data is already resident, nothing is waiting to be loaded.
The zero stretches are padding or runtime scratch, not unfilled asset buffers.

⚠️ Two earlier entries here were wrong and are corrected above: `0x22FEE` is the
**block-definition** table (16 bytes = a 4×4 grid of tile *indices*), not tile
graphics — the tile bitmaps live at `0x1D01E`/`0x1F01E` at 32 bytes each; and
`0x40FEE` is banner artwork, not a full-screen bitmap.

- No embedded code found anywhere in this range (`find_code_gaps` confirms no
  orphaned instructions; spot-checks found nothing that looked like 68000 opcodes).

Most of this region is still raw, untyped bytes — this was a coarse pass, not a
full mapping. The asset sweep is nonetheless considered complete; see `../PLAN.md` §3.
