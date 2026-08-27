# Rick Dangerous 2 — High-Level Reverse Engineering Report

**Source**: `full_ram_dump.bin` — 1 MB Atari ST RAM captured at runtime via Hatari after copy-protection bypass  
**Ghidra project**: `xrick2-prg / full_ram_dump.bin`  
**Date**: 2026-07-02  
**Tool**: Ghidra + MCP bridge, 427 functions recovered

---

## Copy Protection Bypass

The `RD2` binary begins with magic `0x601E` (not `0x601A`), which is the **Copylock ST** signature
by Rob Northen Computing (1988–90). The first instruction is `BRA.S +30` (jump to offset 0x20),
followed by:

- `0x0020–0x00BF`: Copylock decryptor — reads floppy track 3 sector timing via `XBIOS Floprd` (TRAP #14, function 8) to derive an XOR key, then decrypts the payload
- `0x00C0`: Copyright string "Copylock ST (c)1988-90 Rob Northen Computing, U.K."
- `0x1000–0x2FFF`: Stage-2 loader — copies decompressor stub and compressed payload to RAM

Because the hard-disk version (`START.TOS` / `RICKDA2.PCH`) does not have floppy hardware available, Copylock cannot complete its timing check. Bypass was achieved by booting under **Hatari** with GEMDOS hard-drive emulation (`--harddrive /tmp/atari_hd --gemdos-drive C`), placing `START.TOS` in `AUTO/` so TOS auto-executes it, and using Hatari's debugger to dump all 1 MB of RAM at VBL #3000 (~60 seconds after boot, after full decompression).

The decrypted+decompressed game engine was found at:

| Address range | Size | Content |
|---|---|---|
| `0x16000–0x17FFF` | 8 KB | Loader / save-state patcher code |
| `0x18000–0x3FFFF` | 160 KB | Game data: sprites, level maps, music samples |
| `0x78000–0x7FFFF` | 32 KB | Screen buffers (2 × 32 KB at 0x78000 and 0x80000 area) |
| `0xC0000–0xCFFFF` | 64 KB | **GOS game engine** (main code) |

The PPGX signature (`0x50504758` = ASCII `PPGX`) appears at `0x169C4`, `0x16B04`, and `0x80000` —
used by the GXUT275 save-state utility to locate game state in RAM.

---

## GOS — Game Operating System

Rick Dangerous 2 runs a custom embedded OS called **GOS** (Game Operating System, multiple version strings: `GOS 1.00`, `GOS 1.04`, `GOS 1.05`, `GOS 1.14`, `GOS 1.15` found in the GXUT275 utility).

GOS is a **complete Atari TOS replacement** loaded at `0xC0000`. On boot it:
1. Relocates itself (walks its own relocation table, patching absolute addresses)
2. Clears BSS (0x18A0 words = ~12 KB)
3. **Reinstalls itself as TOS**: overwrites all TOS system variables in low RAM (`_sysbase`, `_membot`, `_memtop`, `_v_bas_ad`, `_nflops`, `_drvbits`, `_p_cookies`, etc.)
4. Installs exception and interrupt vectors
5. Installs a GEMDOS-compatible filesystem driver
6. Jumps to the game shell via a function pointer (`_DAT_000c0736`)

**GOS is self-contained.** No Atari TOS ROM calls are made during normal gameplay.

---

## Subsystem Map (by address)

### 1. GOS Kernel Boot — `FUN_000c02b0` (`0xC02B0`)

The kernel entry point. Runs relocation, BSS clear, then sets up the full TOS low-memory
table at warm-reset label `LAB_000c0318`:

```
_sysbase     = 0xC07FE   (GOS kernel base — fake TOS ROM pointer)
_memtop      = phystop − 0x8000   (keeps 32 KB at top of RAM for game)
_v_bas_ad    = _memtop   (video RAM at top)
_nflops      = 0         (hard disk version: no floppy)
nvbls        = 8         (8 VBL queue slots)
etv_timer    = 0xC0AAA   (GOS timer handler)
DAT_28       = FUN_000c9774  (Line A vector → GOS syscall dispatcher)
```

Warm reset is triggered by keyboard combo `0xC53` (intercepted in the IKBD handler);
it re-runs from `LAB_000c0318`.

### 2. Hardware Interrupt Handlers

| Address | Handler | Notes |
|---|---|---|
| `0xC0452` | MFP init | Clears all MFP (MC68901) interrupt enable/mask/pending regs |
| `0xC0ADA` | Idle loop | Infinite `do{}while(1)` — system halt state |
| `0xC2ADC` | **IKBD keyboard ISR** | Full keyboard decoder (see below) |
| `0xC1850` | `hdv_init` (floppy init) | Detects 0–2 floppy drives, sets `_nflops` and `_drvbits` |
| `0xC1BB2` | `hdv_bpb` (BPB query) | Returns BIOS Parameter Block for drive |
| `0xC18CC` | `hdv_rw` (sector R/W) | Low-level disk sector read/write |
| `0xC1A7C` | `hdv_mediach` (media change) | Reports disk change status |
| `0xC1E4C` | `hdv_boot` (boot sector) | Processes boot sector code |

### 3. IKBD Keyboard Decoder — `FUN_000c2adc` (`0xC2ADC`)

Fires as the ACIA serial receive interrupt (address `0x118`). Processes raw scancodes:

- **Modifier tracking** (bitmask at `unaff_A5 + 0xE7D`):
  - bit 0 = right shift (0x36/0xB6), bit 1 = left shift (0x2A/0xAA)
  - bit 2 = Ctrl (0x1D/0x9D), bit 3 = Alt (0x38/0xB8)
  - bit 4 = Caps Lock (0x3A, toggle), bits 5/6 = mouse button states
- **Cursor keys**: 0x48 up, 0x50 down, 0x4B left, 0x4D right → stored as delta `(dx, dy)` at `unaff_A5 + 0xE7A`
- **Key translation**: normal / shift / caps table lookup, result packed as `(scancode << 8) | ascii`
- **Keycode ring buffer**: result stored at `iRam000d0f34[sRam000d0f3c]` with wrap
- **Special combos**:
  - `0xC53` (Ctrl+Shift+F3 or similar) → **warm reset** (re-runs GOS kernel init)
  - `0xD53` → installs alternate code at `LAB_000c2F80` (debug mode?)

### 4. Line A GOS Syscall Dispatcher — `FUN_000c9774` (`0xC9774`)

Installed at exception vector `0x28` (Line A emulator trap). Any `A000`–`A00F` M68k instruction
triggers this handler:

```
opcode & 0xFFF → index (0–15)
(*function_table[index])()   @ DAT_000c97b2
```

Provides 16 GOS API calls accessible via `A0xx` instructions from within the game.

### 5. GEMDOS-Compatible Filesystem — `0xC3000–0xC5500`

A complete FAT12 filesystem driver covering:

| Address | Function | GEMDOS equivalent |
|---|---|---|
| `0xC8708` | Syscall dispatcher (function codes 0–0x57) | Top-level TRAP #1 handler |
| `0xC5146` | Path parser + open file | `Fopen` / `Dsetpath` |
| `0xC4C94` | Disk free space query | `Dfree` |
| `0xC5242` | Get current directory path | `Dgetpath` |
| `0xC6302` | File rename | `Frename` |
| `0xC4BAE` | Drive mount / FAT read | Internal |
| `0xC3E82` | Sector read/write through buffer cache | Internal |
| `0xC84B4` | Disk buffer manager init | Installs 4 sector buffers at `_bufl` (0x4B2) |
| `0xC1030` | BIOS table shadow | Patches `_sysbase` entry |

Sector buffers are 512 bytes each at `0xD5932`, `0xD5B32`, `0xD5D32`, `0xD5F32`
(each 0x200 bytes apart = exactly one FAT sector).

The `GEMDOS` syscall dispatcher at `0xC8708` uses a **6-byte dispatch table at `0xCF6A0`**:
- Offset +0: function pointer
- Offset +2: argument count (0–3)

### 6. Math Library

| Address | Function | Algorithm |
|---|---|---|
| `0xC9806` | Integer square root | Newton's method, 16-bit result |
| `0xC9990` | Fixed-point multiply/divide | `(a * b) / c` with sign + round |
| `0xCA05A` | Sine lookup | Pre-calculated table at `0xD0118`, 180 entries, 10× linear interpolation, input in tenths-of-degrees (0–3600) |
| `0xCA13C` | Cosine | Wrapper for sine (same table, phase offset) |

### 7. 2D Vector / Animation Engine

| Address | Function | Description |
|---|---|---|
| `0xCB530` | Clip code | Cohen-Sutherland outcode for clip rect `DAT_000d2db6/8/a/c` |
| `0xCC02A` | Path interpolation | Walks a 2D point path, inserts midpoints for smooth curves |
| `0xCBDA0` | Circular orbit | Computes `(x + cos(θ)×r, y − sin(θ)×r)` for revolving objects |
| `0xCE9F0` | Polygon fill | Scanline fill with active edge list, handles concave shapes |
| `0xCE678` | **Bitplane blitter** | Copies sprite bitplanes to screen — see below |
| `0x1E010` | Screen clear | Clears 32 000 bytes (320×200 Atari ST low-res @ `0x7D00`) |

#### Bitplane Blitter (`FUN_000ce678`)

Handles all three Atari ST resolutions:

```
DAT_000d2d7e = 1  →  1 bitplane  (ST-high,  2 colours)
DAT_000d2d7e = 2  →  2 bitplanes (ST-medium, 4 colours)
DAT_000d2d7e = 4  →  4 bitplanes (ST-low,   16 colours)  ← game mode
```

In 4-plane mode it copies 4 interleaved words simultaneously per row:
```c
*dst[0] = *src[0];   // bitplane 0 word
*dst[1] = *src[bw];  // bitplane 1 word (offset by row_words)
*dst[2] = *src[2*bw];
*dst[3] = *src[3*bw];
dst += screen_stride;  // advance by DAT_000d2d80 (160 bytes = 320px × 4bp / 8)
```

### 8. Game State Machine — `FUN_000cad70` (`0xCAD70`)

Game state record lives at `DAT_000d2d82` with fields:
- `+0`: state type (0x06 = active state)
- `+4`: state code (0x2D = some scene/screen id)
- `+8`: timer countdown

Two data sets selected by flag `*DAT_000d2d86`:
- Normal data: `DAT_000d2b8c` (12 entries)
- Alternate (e.g. saved-game continue): `DAT_000d2a70`

Timer values 1000 and 5000 (in 200 Hz ticks = 5 s and 25 s) gate state transitions.
`FUN_000c9ee2()` reads a flag (possibly joystick/key pressed) to select short vs. long timeout.

### 9. Entity / Object System

Entities are 0x46-byte (70-byte) records in a singly-linked list rooted at `PTR_PTR_000d3e3e`.
Up to 0x4B (75) handles are tracked in a 10-byte-per-slot table at `DAT_000d55d6`.

`FUN_000c8074` — entity linked-list walker:
```
for each entity in list @ PTR_PTR_000d3e3e:
    if param_1 is within entity[0..0x45]:
        check entity[+4] (type?) > 0
        access entity[+0x36] (some sub-field)
```

`FUN_000c8688` — entity cleanup by inode:
```
for slot in 0..74:
    if handle_table[slot].inode == param_1:
        free slot
```

Entity type codes 0–0x57 (88 types) are dispatched in `FUN_000c8708`.
Switch table cases clustered at `0xC88A6–0xC9544` suggest a per-type behavior dispatch.

---

## Memory Map (at runtime, 1 MB ST)

```
0x000000 – 0x0007FF   TOS low memory (exception vectors, system variables)
0x000800 – 0x015FFF   Low RAM (stack, BSS, TOS workspace)
0x016000 – 0x017FFF   Loader / save-state patcher (START.TOS decompressed)
0x018000 – 0x03FFFF   Game DATA: sprites (bitplane), level maps, sound samples
0x040000 – 0x077FFF   Game BSS / work buffers
0x078000 – 0x07FFFF   Screen buffers  (32 KB primary + 32 KB secondary for flip)
0x080000             PPGX marker block (game engine signature)
0x080001 – 0x0BFFFF   Upper RAM BSS
0x0C0000 – 0x0CFFFF   GOS game engine code (64 KB, 427 functions)
0x0D0000 – 0x0FFFFF   Upper BSS / data tables
0xFF8000 – 0xFFFFFF   Atari ST hardware registers (volatile, not in dump)
```

---

## Key Global Variables (BSS, base ~`0xD0000`)

| Address | Name / Role |
|---|---|
| `0xD027E` | `s_TEND_CPU` — cookie jar template (`_CPU`, `_MCH` cookies) |
| `0xD0118` | Sine lookup table (180 entries × 2 bytes) |
| `0xD0BDC` | BIOS shadow table (patched sysbase copy) |
| `0xD0C22` | Cookie jar array |
| `0xD1140/41` | Current scancode + shift state (set by IKBD ISR) |
| `0xD1168` | Max floppy track count (0x52 = 82) |
| `0xD2D82` | Current game state record |
| `0xD2D8A` | Current path point pointer |
| `0xD3A28` | Progress marker (PC value written before each major init step) |
| `0xD3E3E` | Entity linked list head pointer |
| `0xD55D6` | File handle table (75 slots × 10 bytes) |
| `0xD58C4` | Drive/directory current-path table |
| `0xD6360` | Game version / level identifier |

---

## Findings Summary

Rick Dangerous 2's hard-disk version ships as a PP20-compressed blob (`RICKDA2.PCH`).
When decompressed and run, it deploys a **self-contained operating system** (GOS) that:

1. **Fully replaces TOS** — rewrites all system variable pointers to its own code
2. **Provides a GEMDOS subset** — FAT12 filesystem, file I/O (Fopen/Fclose/Fread/Fwrite/Frename/Dfree), disk buffer manager
3. **Provides a custom syscall ABI** — 16 GOS calls via Line A traps (A000–A00F)
4. **Drives all hardware directly** — IKBD, MFP, VBL, palette, screen flip
5. **Runs the game engine** — 2D vector graphics, bitplane sprite blitter, sine/cosine math, path interpolation, polygon fill, a 75-slot entity system, and a state-machine game loop

The game engine's graphics are **not tile-based** at the rendering level — sprites are drawn via a
configurable bitplane blitter operating on 4 interleaved planes at 320×200×16 colours.
Level/world data (sprites, maps) lives in the large data region at `0x18000–0x3FFFF`.

The save-state mechanism (GXUT275.PRG) locates the game by scanning for the `PPGX` signature at
runtime and directly reads/writes the `0xD0000+` BSS area containing entity state and level data.
