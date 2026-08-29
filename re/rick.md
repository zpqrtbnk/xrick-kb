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

2. **Layer 1 decompression** — re-implemented in Python (script not retained; see the Files note below). Produced `rick_decompressed.bin`, the outer LZ output: still contains the HPack trainer and the LSD-compressed game.

3. **Layer 2 decompression** — attempted a Python micro-emulator of the LSD decompressor. Abandoned due to self-modifying code and exception-based control flow that are impractical to replicate without a full 68K emulator.

4. **Hatari approach** — ran the game in the Hatari Atari ST emulator. The user interacted with the game until it was fully decompressed and running. A RAM snapshot was saved via Hatari's GUI (Hatari v2.6.1; the `memsave` debugger command is not available in that version). The snapshot is `re/atari_ram.bin` (327,680 bytes = first 320 KB of Atari physical RAM).

5. **Ghidra import** — `atari_ram.bin` was imported into Ghidra as a flat 68K binary at base `0x000000`. Auto-analysis found 80 functions.

6. **Main loop identification** — located the game's entry point, main loop, and key subsystems. See the technical files for details.

7. **Function labeling** — 26 functions identified and named in Ghidra. See `functions.md` for the complete catalog.

8. **(2026-08-27/28) Deep passes** — a coordinated multi-agent Ghidra session plus
   three focused follow-up passes took coverage from 82 functions (27 named) to
   **133 functions, all named**, with **9 applied data structures**. The 74-entry
   `sprite_type_dispatch` table was enumerated *and* every type behaviourally
   characterised; the complete level-data model (rooms, transitions, placements,
   object-type templates) was decoded and typed. Several earlier claims were
   **corrected** along the way — notably the `SpriteEntity` X/Y axes were swapped,
   `0x4BF18` is `player_dying` not "game_running", and `0x4B586` is the level index
   not a lives counter. See `re/functions.md`, `re/data-structures.md`,
   `re/entities.md`, and `../PLAN.md` for full detail.

## What We Now Know (resolved since the last pass)

- **Entity/object system**: resolved. `sprite_list` is a fixed **13-slot** array
  (not open-ended), struct fully mapped (`re/data-structures.md`). Reserved slots:
  `[0]`=scripted moving hazard (crusher/boulder), `[1]`=player, `[2]`/`[3]`=bullet/dynamite, `[4..8]`/`[9..11]`=level
  entities, `[12]`=decorative sprite.
- **Type dispatch table**: fully resolved. All **74 entries enumerated *and*
  behaviourally characterised** (`re/entities.md`): type 1 player, 2/3
  bullet/dynamite, 4–15 enemies over a shared `enemy_ai_update` (3 AI modes), 16/17
  destructible crates, 18–21 treasures, 22/23 trigger zones, 24–73 a shared
  data-driven `scripted_trap_update`, 74 decorative. (The count was 70 for several
  passes — a spurious function had truncated the table.)
- **Level data model**: resolved. Rooms (`RoomHeader[47]`) link into a left/right
  graph via `TransitionWaypoint` lists; entities spawn from `PlacementRecord[523]`
  as their world-row band scrolls in; per-type template data comes from
  `ObjectTypeDef[75]`. All decoded field-by-field — see `re/data-structures.md`.
- **Player input**: fully resolved — and it is the **joystick**, not the keyboard.
  `keyboard_isr` decodes IKBD packets; a `0xFF` header introduces a joystick-1 report
  whose byte lands at `0x4922B` with standard Atari bits UP/DOWN/LEFT/RIGHT/FIRE =
  `0x01/0x02/0x04/0x08/0x80`. Control scheme is FIRE+direction: FIRE+L/R = stick jab,
  FIRE+UP = shoot, FIRE+DOWN = dynamite. Keyboard codes are used only for ESC, P and
  SPACE.
- **Level loading**: resolved — **there is none at runtime**. The whole program
  contains exactly two traps (`Super`, `Setscreen`); no GEMDOS, BIOS or XBIOS
  file/sector call exists anywhere, so the code cannot touch the disk. All four
  levels are already resident: 47 room headers, every tilemap in one contiguous 8 KB
  region, 523 placement records, five intro texts, and **only two tile banks** shared
  pairwise (bank 0 = South America + Egypt, bank 1 = Castle + Missile Base).
  Completing a level is pointer arithmetic through `level_start_info`. Loading
  happened once, before this snapshot, in the outer loader stage. A reimplementation
  needs no loader at all.
- **HUD**: resolved, with a correction. There are only **3 counters** (not 4) —
  the old "lives, bullets, dynamite sticks, and one other (keys?)" guess was wrong.
  Now fully pinned down and renamed: `bLives`, `bBullets`, `bDynamite` (the
  bullet-vs-dynamite ordering was resolved statically from `player_controller`'s two
  fire paths at `0x4C524`/`0x4C60E`).
- **Music system**: mostly resolved. `music_track_table` confirmed at exactly **29
  records**. Full per-tick engine mapped: `music_tick` -> `advance_music_channels`
  (procedural path) / `step_all_channel_coroutines` -> `channel_coroutine_dispatch`
  (self-modifying coroutine path, 3 PSG channels confirmed) -> `resolve_channel_note_period`
  (confirmed 84-entry PSG tone-period table). The **sequence opcode set and the
  sample-playback path are now decoded too** — see `re/algo-music.md`.
- **Level transitions**: resolved. `main_init_and_loop`'s full per-frame dispatch
  is now documented (`re/functions.md`) — room-transition controller, active
  gameplay, game-over, and respawn paths are all traced. Checkpointing is
  **per-room** (not per-level): `save_checkpoint_state`/`restore_checkpoint_state`
  round-trip the player's position every time Rick enters a new room.

## Where We Stand

**`../PLAN.md` is the authoritative record of current state and open work**; this is
just the orientation.

The goal is a knowledge base sufficient to *mechanically re-code the game with
identical behaviour*. Measured against that bar we are roughly **98%** there.

**The code itself is fully reversed.** Every function is named and every non-trivial
one is transcribed to exact pseudocode in `re/algo-*.md`. The tilemap encoding and
the music sequence opcodes — the last two undecoded formats — were closed by the
2026-08-28 transcription pass. Graphics are extracted and visually validated, all 47
room maps render, and the sound engine is packaged as a playable SNDH — confirmed by
ear, with all three PCM samples complete (including the death "waaaaa"). The 1 MB
capture `atari_ram_1M.bin` supplied the samples the original dump was missing.

Since then, two further passes closed the remaining doubt. The eight behavioural
details that wanted a live Hatari run are **7 resolved, 1 optional** (`re/hatari.md`),
and nine **byte-identity audits** ran to completion, finding and fixing 15 defects
(`re/byte-identity.md`). What is left is not analysis but a test: build the
reimplementation and diff it against the live game.

> ⚠️ `atari_ram_1M.bin` loads the game at a **different base address** (everything
> shifted by **−0x2054**). All addresses in `re/` and Ghidra use `atari_ram.bin`
> numbering. **Decided: we do not re-base.** Convert instead:
> `1M_address = doc_address − 0x2054`.

## Do Not Do

- **Never inspect, open, or reference `ghidra.xrick2`/`xrick2-prg`** (on disk at
  `ghidra.xrick2/` or `mac/ghidra.xrick2/`). It's an untracked leftover, permanently
  out of scope for this analysis.
- ~~**Don't re-run ASCII string search.**~~ **RETRACTED 2026-08-28 — the advice was
  wrong and cost us the game text for several passes.** Text *is* ASCII, but
  `0xFF`-terminated rather than NUL-terminated, and Ghidra's analyzer required NUL
  termination. Scanning for `0xFF`-terminated printable runs yields 64 strings
  (level names, high-score table, intro stories at `0x4B8FE`+). `^`=space, `\`=`.`,
  `[`=`,`, `]`=`?`.
- **Don't re-search for GEMDOS Fopen/Fread.** Already done exhaustively (see "What We
  Now Know" above) — the answer is "not present in this snapshot," not "not yet
  found."

## Files

| File | Purpose |
|------|---------|
| `re/atari_ram.bin` | RAM snapshot from Hatari — primary analysis artifact |
| `re/memory_map.md` | Technical: Atari ST physical memory layout, capture limits |
| `re/functions.md` | Technical: complete catalog of all **133** functions (all named) |
| `re/data-structures.md` | Technical: all 10 structs, the level-data model, sprite frame format |
| `re/entities.md` | Technical: the 74-entry dispatch table and entity behaviour map |
| `re/strings.md` | Technical: all in-game text, character encoding, font mapping |
| `re/algo-*.md` | **Exact re-codable pseudocode** for every non-trivial function (6 files) |
| `re/byte-identity.md` | The nine fidelity audits and the defects they found |
| `re/hatari.md` | The dynamic-verification harness and the eight behavioural probes |
| `../PLAN.md` | **Authoritative** current state, open work, and next steps |
| `../MEMORY.md` | Project rules, settled decisions, method lessons |

Note: `re/decompress_rick.py`, referenced by earlier versions of this file, is **not
present** in the repo. The Layer-1 decompressor work described above produced it at
the time but it was not kept; the Hatari snapshot route superseded it.

The Ghidra project is `xrick` (at `ghidra.xrick/`) and currently contains **one**
program, `atari_ram.bin` — the live RAM dump, primary and only analysis target. (An
earlier version of this note claimed three programs including `RICK.PRG` and
`rick_decompressed.bin`; those are not present in the current project.) The
`ghidra.xrick2`/`xrick2-prg` project elsewhere in the repo is an unrelated, untracked
leftover — see "Do Not Do" above.
