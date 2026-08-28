# Rick Dangerous (Atari ST) — Reverse Engineering: State & Plan

**Last reviewed: 2026-08-28.** Current state and remaining work only. Completed work
is condensed into the appendix; the knowledge itself lives in `re/` and in Ghidra
plate comments.

**Target bar:** `re/` should be complete enough to *mechanically re-code the game with
identical behaviour*. Everything below is assessed against that bar.

> **⚠️ `ghidra.xrick2` / `xrick2-prg` is an untracked leftover and must never be
> considered, opened, or referenced by this analysis, in this session or any future
> one.** Do not `connect_instance`/`open_project` against it, do not read files under
> `ghidra.xrick2/` or `mac/ghidra.xrick2/`, and do not cite it as a source of truth.

---

## 1. Current state (measured 2026-08-28)

| Metric | Value |
|---|---|
| Ghidra project / program | `ghidra.xrick` → `xrick`, single program `atari_ram.bin` |
| Primary artifact | `re/atari_ram.bin` — 327,680 byte Hatari snapshot. **Authoritative for all addresses.** |
| Secondary artifact | `re/atari_ram_1M.bin` — complete 1 MB capture, used only as the source of the full PCM samples. Loads the game **−0x2054** lower; not interchangeable |
| Functions | **133**, all named; every non-trivial one transcribed |
| Structs applied | 10, plus typed arrays over every hard-bounded data region |
| Entity dispatch types | **74/74** characterised |
| Knowledge base | 14 documents + 3 scripts in `re/` |
| Extracted assets | 12 graphic PNGs, 47 room maps (+47 entity overlays), 1 playable SNDH |
| Largest untyped region | `0x1B01E`–`0x44BED` — the graphics blob, now mostly mapped (see `memory_map.md`) |

---

## 2. Coverage against the reimplementation bar

**The code is fully reversed.** Every function is named, and every non-trivial one is
transcribed to exact pseudocode in `re/algo-*.md` (constants as literals, branch order
preserved, register conventions documented). Re-codable from `re/` alone:

- Frame loop, timing, double buffering, VBlank/Timer-A interrupts, supervisor entry
- Player controller — movement, jump/gravity, climb, crouch, attacks, death
- The sprite blitter (aligned + shifted paths, derived transparency, clipping)
- Enemy AI (3 modes), the shared scripted-trap engine, pickups, triggers, collision
- Level data model: rooms, transitions, placements, object templates, tilemap encoding
- PSG sound engine including the sequence opcode set and sample playback
- HUD, score, lives, per-room checkpointing, game-over/respawn, attract mode
- All in-game text and the font/character encoding

**All assets are extracted and validated by observation, not inference:** graphics
render as recognisable artwork, all 47 room maps render as coherent level geometry
(visually confirmed), the 64 strings decode, and the SNDH plays — music, effects and
all three digidrums.

**Verdict: ~98% of a reimplementation spec.** What remains is a short list of
behavioural details wanting a live run, plus optional completeness work. Nothing
structural, nothing blocking.

---

## 3. Remaining gaps, and how to close them

**G1 is the only gap left.** G2 and G3 were closed 2026-08-28 and are kept here
briefly, with their findings, rather than moved to the appendix — because each ended
in a conclusion worth not rediscovering.

### G1. Behavioural details that need a live run — *the only substantive gap*
Each is inferred from static reading with good confidence but has never been observed.

| Item | What is unclear |
|---|---|
| Tile-attribute bits | Bits beyond `0x02/0x04/0x10/0x20/0x40/0x80`, and the `0x6F` intermediate mask used inside the probe routines |
| `POOKY9999` easter egg | Sets flag `0x498C4` and gates the level-select menu; the rest of its effect is untraced |
| Enemy variants | Which of the 4 sprite banks × 3 AI modes is which on-screen creature, per level |
| Trigger bits | Semantics read confidently off the code, but no bit observed firing in play |
| Landing rebound | `nVelY = 0xFE - nVelY` transcribed literally; interpretation uncertain |
| Name-entry glyphs | Four non-letter glyphs (`0x36 0x37 0x3A 0x3B`), presumably END/DELETE |
| `player_touched_hazard` | Set on lethal overlap; the consumer site was never pinned down |
| Song 0 transpose | Order-list transpose of `0x1C`; decodes consistently, musical result unverified |

**Strategy.** One Hatari session, batched — they share setup and none needs more than
a breakpoint plus a memory watch. Concretely: break on `probe_player_tile_collision`
and log `player_collision_flags` against known terrain to finish the attribute bits;
set the POOKY flag by hand and observe; watch `0x4922B` while playing to confirm the
joystick decode end-to-end; step `scripted_trap_update` on a known trap to see a
trigger bit fire. Everything needed is already labelled in Ghidra, so this is
observation, not analysis. *Hatari is available — the 1 MB dump came from it.*

### G2. Asset-sweep completeness — ✅ CLOSED 2026-08-28
Sprite frames sit on one regular grid (stride `0x150`, all aligned 110 mod `0x150`).
`extract_assets.py` now sweeps the grid instead of walking animation tables and renders
**185 frames** rather than 124; all were inspected and every one is real artwork. The
shortfall was not orphaned content — treasures and enemy banks use *computed*
addresses that no table walk or pointer scan can see.

The last unidentified region, `0x1BBFE`–`0x1D01D` (5,152 bytes between the font and
tile bank 0), is **161 scenery tiles** in the standard 8×8 four-plane format — sky,
pyramids, sand, buildings. Rendered to `scenery_tiles.png`. **Nothing in the program
references it**, so it is cut content or loader-stage artwork; identified, use
unresolved. No further sweep is worthwhile.

### G3. Minor loose ends — ✅ CLOSED 2026-08-28
- **`level_start_info` has 5 entries, not 4.** Hard boundary: entry 5 would begin at
  `0x4B586`, which *is* `level_index`. `start_level` indexes the table with **no bounds
  check**, and `process_level_transition_point` lets `level_index` reach 4 on
  completion — so entry 4 is a deliberate "game complete" pseudo-level that displays
  the ending text and returns to attract mode without ever loading a room. A
  `LevelStartInfo` struct now exists and the full explanation is on the plate comment
  at `0x4B522`. *(The array type could not be applied: an auto-generated pointer label
  inside the range blocks it, and Ghidra rightly refuses to evict a named global.
  Cosmetic only.)*
- **Completeness metrics are not fit for purpose here.**
  `analyze_function_completeness` emits **no score at all** — it reports conformance to
  a plate-comment template (Algorithm / Parameters / Returns / Source-file sections)
  that this project deliberately does not use, our comments being evidence-and-
  correction narratives instead. It cannot produce a coverage number, so the ~98%
  figure stays an explicit estimate. Do not re-run it expecting a metric.
- **Orphaned-instruction regions** (`0x492E6`, `0x48F48`, `0x4DF86`+) are data
  mis-disassembled as code. Harmless; left as-is deliberately.

---

## 4. Settled — do not re-open

| Question | Decision |
|---|---|
| Level loading | **There is none at runtime.** Two traps total (`Super`, `Setscreen`); all four levels resident. Do not re-search for GEMDOS/BIOS I/O. |
| ASCII string search | Done — 64 strings in `strings.md`. The old "text isn't ASCII" advice was wrong and is retracted. |
| Slot-0 block pushing | **No such mechanic exists.** Slot 0 is the scripted crusher/boulder hazard, moved by `scripted_trap_update` through `A0`. |
| Missing 12,880 bytes | Recovered via `atari_ram_1M.bin`; was stack + PCM, never code. |
| Re-basing onto the 1 MB dump | **No.** `atari_ram.bin` numbering stays authoritative; convert with `1M_address = doc_address − 0x2054`. `build_sndh.py` bridges the two automatically. |
| Pixel-diffing rooms vs Hatari | **No.** The user validates renders visually and has confirmed them correct. |
| `attempt.0/`, `attempt.1/`, `disks/` | **Stay exactly where they are.** Earlier-phase material, deliberately kept in place. Do not move, archive or reorganise. |
| `ghidra.xrick2` | Permanently out of scope. |

---

## 5. Method notes worth keeping

- **Verify agent work before trusting reports.** Two of five forks in the multi-agent
  pass reported "done" after producing incoherent, self-referential output without
  doing any work; caught only by checking live Ghidra state. Both recovered when told
  plainly "you are not the orchestrator; do the work yourself; do not call Agent".
- **Prefer disassembly over decompiler output.** Four documented errors came from
  trusting the decompiler: `RoomHeader.pPlacements` (+0xA, not +5); the `lea`-loaded
  A2 effect callbacks it hid entirely; the `move.b #n,D0` AI-mode arguments it dropped
  as dead stores; and `probe_entity_tile_collision`'s carry-flag return read as a `D0`
  value.
- **Cross-check structures against raw bytes.** The `SpriteEntity` X/Y axis swap and
  the `LevelStartInfo` 4-byte base error both survived multiple passes because prose
  was never checked against the table contents.
- **Beware tables cut short by spurious functions.** `sprite_type_dispatch` was
  recorded as 70 entries for several passes because a bogus `hide_entity` function had
  been created inside it. The real count is 74 — which also explained an "impossible"
  discrepancy in `ObjectTypeDef`.
- **An empty address-based search does not mean the code is absent.** The slot-0
  "block mover" was hunted across several passes and never found, because both the
  spawn and the motion write through address registers (`A1`, `A0`) rather than
  absolute addresses — so no xref or operand search could ever match. When a
  program-wide search for writes to a known global comes up empty, ask whether the
  access is register-indirect before concluding the logic is missing or elsewhere.
- **A RAM snapshot captures a *running* state, not a clean one.** Code lifted out of
  it inherits whatever the program happened to be doing — here the snapshot was taken
  with the title music mid-play, and every routine that assumed prior initialisation
  misbehaved until the state was explicitly cleared. When re-hosting lifted code,
  reset the subsystem with its *own* init/cleanup routines rather than trusting the
  captured values.
- **Ghidra analyzer defaults can hide data.** The ASCII Strings analyzer had *Require
  Null Termination* enabled, so it reported zero strings for a game whose text is
  entirely `0xFF`-terminated ASCII. Check analyzer options before concluding "absent".

---

## Appendix — completed work log (condensed)

| Pass | Date | Outcome |
|---|---|---|
| Baseline | pre-08-27 | 82 functions, 27 named; no structs; skeleton only |
| Housekeeping + structs | 08-27 | 5 structs applied; sprite list confirmed 13 slots; HUD corrected to 3 counters + score |
| Multi-agent pass (5 forks) | 08-27 | → 129 functions; dispatch enumerated; per-room checkpointing; sound engine mapped; GEMDOS search negative |
| Entity-handler pass | 08-27 | All dispatch types characterised; **axis correction** (4=X, 6=Y); `player_dying`; bullets/dynamite resolved |
| Placement-format pass | 08-27 | Placement/room/transition/level-start formats decoded; `0x481E4` identified; effect callbacks found |
| Type-table pass | 08-28 | `ObjectTypeDef[75]`; `wTypeFlags` → `wTriggerSound` |
| Reachability analysis | 08-28 | Missing 12,880 bytes proven to be stack + PCM, not code |
| **Transcription pass (6 forks)** | 08-28 | ~4,400 lines of exact pseudocode; **tilemap encoding** and **music opcodes** decoded; `Super()`, joystick input, row-major tilemap, AI modes, carry-flag returns all corrected |
| String extraction | 08-28 | `re/strings.md`: 64 strings, font-validated encoding; intro-text gap explained; **ending text** found |
| Slot-0 investigation | 08-28 | **No block-pushing mechanic exists** — slot 0 is the scripted crusher/boulder hazard, moved by `scripted_trap_update` via `A0`; confirmed by all 26 slot-0 placement records carrying types 24–73 |
| SNDH packaging | 08-28 | Sound engine lifted into a 29-subtune SNDH with a hand-assembled relocating stub; all opcodes and displacements verified |
| Room rendering + data typing | 08-28 | All 47 rooms rendered (validates the tilemap decode end-to-end); hard-bounded data regions given array types and labels in Ghidra |
| Asset extraction | 08-28 | 11 PNGs rendered and visually validated; sprite format found to be plane-major; font extent settled at 95 glyphs; `0x40FEE` identified as three banners |
| Index demotion | 08-28 | `functions.md`/`entities.md` demoted to indexes; globals moved to `data-structures.md`; authority order documented in `README.md` |
| Audio complete | 08-28 | Rebuilt SNDH from the 1 MB capture: all three PCM samples intact incl. the death sample; **confirmed by listening**. Superimposed-'ding' defect fixed (`silence_all_channels` + interrupt-masked copy) |
| Room render fix | 08-28 | Rooms were cut short at the bottom: only each room's own block-index stream was drawn, but the player sees one further screenful from the next stream. Added a 6-block-row margin; renderer verified free of off-by-one |
| G2 + G3 closure | 08-28 | Sprite extraction switched to a grid sweep (124 → **185** frames); the 5 KB post-font gap identified as **161 unreferenced scenery tiles**; `level_start_info` proven to have **5** entries (entry 4 = the game-complete pseudo-level); completeness metrics found unfit for purpose |
| Plan/KB consistency | 08-28 | Gap register refactored to genuinely open items only; settled decisions collected into a do-not-re-open table; stale audio/capture claims purged from `rick.md` and `memory_map.md` |
| KB review | 08-28 | Stale content purged; `sprite_type_dispatch` corrected to **74 entries**; `hide_entity` relocated to `0x4AC08`; `bullet_range_remaining` → `bullet_point_x/y`; `CheckpointState` axes fixed |
