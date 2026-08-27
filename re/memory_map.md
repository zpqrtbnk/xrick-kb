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

The sprite object list is at `0x4A702` inside the game's text segment (within the 320 KB snapshot). Entries are **0x4C bytes** each, terminated by a word of `0xFFFF`.
