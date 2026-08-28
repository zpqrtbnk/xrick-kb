# Rick Dangerous — Atari ST Memory Map

Source: `re/atari_ram.bin` — Hatari RAM snapshot, 327,680 bytes (first 320 KB of Atari physical RAM, addresses `0x00000`–`0x4FFFF`).

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

**Update (2026-08-27 pass)**: the last 8,314 bytes actually inside the snapshot,
`0x4DF86`–`0x4FFFF`, were spot-checked and found to be mostly all-zero or
byte-values clustering around `0x7B`–`0x89` — consistent with **8-bit PCM audio
sample data**, not code, though this is unconfirmed (only spot-checked, not
byte-diffed against a known sample format). `find_code_gaps` confirms no orphaned
instructions there. Whether the missing ~12KB past `0x4FFFF` is more of the same
kind of data or genuinely-missing code was not determined this pass.

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
snapshot. A wider capture (`savebin` over `0x1B018`–`0x53250`, or simply a full 1 MB
dump) is still wanted to recover **two sound samples**, but it is not a blocker. The
runtime buffers (`0x63800`+, screen buffers `0x70000`/`0x78000`) are likewise outside
the capture but derivable from code.

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

The game uses **double buffering**. Two screen buffers are located at `0x70000` and `0x78000` (inferred from `draw_string` which writes to both). `flip_screen_buffer` toggles which buffer is displayed by writing to `0xFF8201/03`.

Sprite pixel data is held in a separate area starting at `0x63800` (zeroed by `clear_screen_buffers` at startup, 0x1C800 bytes = 115,712 bytes).

The sprite object list is at `0x4A702` inside the game's text segment (within the 320 KB snapshot). Entries are **0x4C bytes** each, terminated by a word of `0xFFFF`. **Confirmed (2026-08-27 pass): exactly 13 entries** (`0x4A702`–`0x4AADD`), sentinel at `0x4AADE`, immediately followed by the `sprite_type_dispatch` function-pointer table at `0x4AAE0`. Full field layout in `re/data-structures.md` (struct `SpriteEntity`).

---

## Level Loading — GEMDOS Search Result (2026-08-27 pass)

`search_instructions(mnemonic=trap)` across the entire 320KB snapshot found only
**two** TRAP instructions total: one `TRAP #14` (XBIOS, in `xbios_setscreen`) and
exactly **one** `TRAP #1` (GEMDOS), at `0x4DC34` inside `main_init_and_loop`'s init
sequence — which disassembles to **`Super(0x5324C)`** (GEMDOS 0x20, supervisor-mode
entry with `0x5324C` as the supervisor stack pointer; earlier notes misread this as
`Mshrink`, which is 0x4A), not file
I/O. **There is no `Fopen`/`Fread`/`Fclose` anywhere in this captured image.** Either
level/`.HNK` data is loaded via raw BIOS/XBIOS disk sector access (not located this
pass), or loading happens entirely before this text segment's entry point, during the
outer loader/decompression stage described in `rick.md` (which this snapshot does not
capture). This closes out `rick.md`'s old step 4 as "answered: not resolvable from
this binary" rather than leaving it as an open TODO.

---

## The 171KB Undefined Data Region (0x1B01E–0x44BED)

Coarse-mapped (not exhaustively) in the 2026-08-27 pass. See `re/data-structures.md`
for the font table. Key findings:

- **Font table** confirmed at `0x1B01E`, 32 bytes/glyph, first 32 glyphs typed. True
  glyph count still unconfirmed.
- **`0x23FEE`**: the static title-screen bitmap (32768 bytes), confirmed via
  `draw_title_picture`'s only caller (`attract_mode_loop`).
- **`0x22FEE`**: tile-graphics table (16 bytes/tile, 4 de-interleaved bitplane
  longword arrays), confirmed via `decode_level_tiles_to_cache`.
- **`0x40FEE`**: a title/menu bitmap image, confirmed via `enter_highscore_name`'s
  full-screen blit call.
- Roughly `0x1D800`–`0x33800`: dense non-zero planar-bitmap-looking data
  interspersed with zero stretches — not uniform, likely alternating sprite/tile
  sheets and padding. Hypothesized (not confirmed) correspondence to the DOS
  version's `RCH#SET.DAT` sprite-sheet files in `attempt.0/rd2/`.
- Roughly `0x33800`–`0x44BED`: mostly all-zero — consistent with an unpopulated
  level/graphics buffer at snapshot time (can't distinguish "not yet loaded" from
  "genuinely unused" from a single static snapshot).
- No embedded code found anywhere in this range (`find_code_gaps` confirms no
  orphaned instructions; spot-checks found nothing that looked like 68000 opcodes).

Most of this region is still raw, untyped bytes — this was a coarse pass, not a
full mapping. See `reverse-plan.md`'s "Remaining gaps" section.
