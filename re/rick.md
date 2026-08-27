# Rick Dangerous — Reverse Engineering Log

**Game**: Rick Dangerous (Core Design, 1989)  
**Platform**: Atari ST (Motorola 68000)  
**Source binary**: `disks/chaos43/RICK.PRG` (93,326 bytes), from the Chaos #43 compilation disk

---

## What We Know

Rick Dangerous on Chaos #43 is not the original Core Design release. It is a cracked and re-packed version:

- The file is a **three-layer compressed executable**. Unpacking it all the way to the real game code requires running it.
- The cracker is "Andy the Arfling", using a tool called HPack. A trainer with F1–F4 cheat keys (infinite lives, ammo, dynamite, level select) was injected before the game.
- The actual decompressed game binary is **229,944 bytes** of 68K code and data, loaded at Atari physical address `0x1B018`.
- The game uses standard Atari ST hardware: the YM2149 PSG sound chip, the MFP (Multi-Function Peripheral) for timer and keyboard interrupts, hardware color palette at `0xFF8240`, double-buffered screen display.

## What We Have Done

1. **Static analysis of RICK.PRG** — fully understood the outer backward-LZ decompressor (custom, no standard packer signature), the HPack trainer stub, and the inner LSD compression layer. All documented in the technical files.

2. **Layer 1 decompression** — re-implemented in Python (`re/decompress_rick.py`). Produced `rick_decompressed.bin`, which is the outer LZ output: still contains the HPack trainer and the LSD-compressed game.

3. **Layer 2 decompression** — attempted a Python micro-emulator of the LSD decompressor. Abandoned due to self-modifying code and exception-based control flow that are impractical to replicate without a full 68K emulator.

4. **Hatari approach** — ran the game in the Hatari Atari ST emulator. The user interacted with the game until it was fully decompressed and running. A RAM snapshot was saved via Hatari's GUI (Hatari v2.6.1; the `memsave` debugger command is not available in that version). The snapshot is `re/atari_ram.bin` (327,680 bytes = first 320 KB of Atari physical RAM).

5. **Ghidra import** — `atari_ram.bin` was imported into Ghidra as a flat 68K binary at base `0x000000`. Auto-analysis found 80 functions.

6. **Main loop identification** — located the game's entry point, main loop, and key subsystems. See the technical files for details.

7. **Function labeling** — 26 functions identified and named in Ghidra. See `functions.md` for the complete catalog.

## What We Still Need To Do

The game's **high-level architecture** is mapped. The next phase is to understand the game's **logic** — how Rick moves, how enemies behave, how levels are loaded.

Suggested next steps, roughly in order:

1. **Identify the entity/object system** — the sprite object list at `0x4A702` drives both rendering passes. Each entry is 0x4C bytes. Understand the fields: position, type, state flags, animation frame, velocity.

2. **Map the type dispatch table** — `render_sprites` jumps through a table at `0x4AAE0`, one function pointer per entity type. Each pointer is a per-type update function. Enumerate and label them.

3. **Understand player input** — find where joystick/keyboard state is read and converted into player movement. The keyboard ISR installed at `0x118` and the ACIA at `0xFFFC00` are the entry points.

4. **Understand level loading** — the `.HNK` files are loaded at runtime via GEMDOS. Find the Fopen/Fread calls and trace how level data populates game state.

5. **Understand the HUD** — the four `hud_update_element` functions draw counters at fixed screen positions. Identify which counters correspond to lives, bullets, dynamite, and score.

6. **Document the music system** — `timer_a_music_isr` streams data to the YM2149. Understand the music data format and the `play_music` track table at `0x44F08`.

7. **Understand level transitions** — the main loop has distinct states for "game running", "player dying", and "level transition". Trace the control flow between them.

## Files

| File | Purpose |
|------|---------|
| `re/atari_ram.bin` | RAM snapshot from Hatari — primary analysis artifact |
| `re/decompress_rick.py` | Python reimplementation of the outer LZ decompressor |
| `re/memory_map.md` | Technical: Atari ST physical memory layout from the RAM dump |
| `re/functions.md` | Technical: complete catalog of identified functions |

The Ghidra project is `xrick` and contains three programs: `RICK.PRG` (original packed), `rick_decompressed.bin` (Layer 1 output, mostly obsolete), and `atari_ram.bin` (the live RAM dump, primary).
