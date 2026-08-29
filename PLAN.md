# Rick Dangerous (Atari ST) — State & Plan

**Snapshot: 2026-08-29.** Where the project stands, what is still open, and what happens
next. Project rules, settled decisions and method lessons are in `MEMORY.md`; the game
knowledge itself is in `re/` and in Ghidra plate comments.

**Bar:** `re/` complete enough to *mechanically re-code the game with identical
behaviour*. Everything below is measured against that.

---

## 1. State

| Metric | Value |
|---|---|
| Functions | **133**, all named; every non-trivial one transcribed |
| Structs applied | **10**, plus typed arrays over every hard-bounded data region |
| Entity dispatch types | **74 / 74** characterised |
| Placement table | 523 slots = 476 real records + 47 per-room terminators (reconciled) |
| Knowledge base | **16 documents + 4 scripts** in `re/` |
| Extracted assets | 12 graphic PNG sheets (185 sprite frames among them), 47 room maps + 47 entity overlays, 1 playable SNDH |
| Byte-identity audits | **9 of 9 complete** — 15 defects found and fixed |
| Dynamic-verification probes | **7 of 8 resolved**; the 8th reduced to a nice-to-have |
| Hatari harness | **Working** — boots the analysed build unattended, Rick driveable under script |

**Coverage against the bar: ~98%.** This is an explicit judgement, not a measurement —
no tool here can produce a coverage number (see `MEMORY.md` §7). Converting it into a
measurement is exactly what O1 below is for.

---

## 2. Complete

**The code is fully reversed.** Every function is named and every non-trivial one is
transcribed to exact pseudocode in `re/algo-*.md` — constants as literals, branch order
preserved, register conventions documented. Re-codable from `re/` alone:

- Frame loop, timing, double buffering, VBlank/Timer-A interrupts, supervisor entry
- Player controller — movement, jump/gravity, climb, crouch, attacks, death
- The sprite blitter (aligned + shifted paths, derived transparency, clipping)
- Enemy AI (3 modes), the shared scripted-trap engine, pickups, triggers, collision
- Level data model: rooms, transitions, placements, object templates, tilemap encoding
- PSG sound engine including the sequence opcode set and sample playback
- HUD, score, lives, per-room checkpointing, game-over/respawn, attract mode
- All in-game text and the font/character encoding

**All assets are extracted and validated by observation, not inference.** Graphics
render as recognisable artwork; all 47 room maps render as coherent level geometry
(visually confirmed); the 64 strings decode; the SNDH plays — music, effects and all
three digidrums, confirmed by ear.

**Fidelity is audited, not assumed.** `re/byte-identity.md` is the standing record: nine
mechanical audits derived facts from the binary and diffed them against the documents.
Fifteen defects were found and fixed, notably both tile probes transcribed literally
(the previous "equivalent" formulation would have broken ladder detection on 8-pixel
column boundaries), six global width errors, the music engine's note index and transpose
proven **signed**, and four off-by-one loop counts. Two audits came back clean: the
entity struct's field widths, and the decompiler-hidden-dispatch class.

**Seven of the eight dynamic-verification probes are resolved.** These behavioural
details were inferred statically and flagged as wanting a live run; `re/hatari.md` §6
holds the evidence for each — tile-attribute bits and the `0x6F` row-filter mask, the
`POOKY9999` easter egg, the four name-entry glyphs, `player_touched_hazard`'s single
reader, the per-level enemy banks, the landing rebound as a bounce-surface special case,
and the song-0 transpose. The eighth (trigger-bit semantics) is O2 below.

---

## 3. Open

Four items. None of them blocks a reimplementation; the knowledge base is not known to
be missing anything structural.

### O1. Build the reimplementation and diff it against the live game — **the next step**

Static auditing has reached diminishing returns: the last three audits found four
defects between them, all in prose rather than in transcribed logic. The remaining
verification is a *test*, not a read.

The Hatari harness in `re/hatari.md` is the instrument. Boot `disks/chaos43/RICK.PRG`
from a GEMDOS drive, re-measure the address delta (expect `-0x2054`, never hardcode),
then breakpoint each major function, log register state, and diff against what
`algo-*.md` predicts. That turns the ~98% estimate into a measurement.

### O2. Trigger-bit dynamic spot-check — *optional*

All 8 trigger bits are exercised in shipped data across all 4 levels (census in
`re/entities.md`), so no transcribed path is unreachable. The *semantics* still rest on
the code transcription alone. A spot-check — step `scripted_trap_update` on a known trap
and watch a bit fire — would promote them from "transcribed" to "observed". Worth doing
opportunistically during O1, not on its own.

### O3. Two minor unanswered questions

Both are curiosities about *observable* behaviour, not holes in the specification.

- **The name-entry commit loop at `0x491E2` over-runs the name field.** `dbf D3w` tests
  the full word while `move.b (A2)+,D3` writes only the low byte, so the iteration count
  depends on entry state as well as on the characters typed. A reimplementation just
  emits `dbf D3w` and is correct by construction — the object code is the specification
  — but *what the player actually sees* has never been characterised. Model the loop in
  Python and confirm one case live. See `re/algo-system.md`.
- **Some `ObjectTypeDef` entries have no placement record referencing them.** Unused
  content, or types reachable only by paths not yet traced? Unresolved. See
  `re/entities.md`.

### O4. Accepted as-is

Known, understood, and deliberately not being fixed:

- **161 scenery tiles at `0x1BBFE`–`0x1D01D`** (standard 8×8 four-plane format, rendered
  to `scenery_tiles.png`) are referenced by **nothing in the program** — cut content or
  loader-stage artwork. Identified; use unresolved. No further asset sweep is worthwhile.
- **The `LevelStartInfo` array type cannot be applied in Ghidra**: an auto-generated
  pointer label inside the range blocks it and Ghidra rightly refuses to evict a named
  global. The struct exists and the full explanation is on the plate comment at
  `0x4B522`. Cosmetic only.
- **Orphaned-instruction regions** (`0x492E6`, `0x48F48`, `0x4DF86`+) are data
  mis-disassembled as code. Harmless; left alone.

---

## Appendix — work log

| Pass | Date | Outcome |
|---|---|---|
| Baseline | pre-08-27 | 82 functions, 27 named; no structs; skeleton only |
| Housekeeping + structs | 08-27 | 5 structs applied; sprite list confirmed 13 slots; HUD corrected to 3 counters + score |
| Multi-agent pass (5 forks) | 08-27 | → 129 functions; dispatch enumerated; per-room checkpointing; sound engine mapped; GEMDOS search negative |
| Entity-handler pass | 08-27 | All dispatch types characterised; **axis correction** (4=X, 6=Y); `player_dying`; bullets/dynamite resolved |
| Placement-format pass | 08-27 | Placement/room/transition/level-start formats decoded; `0x481E4` identified; effect callbacks found |
| Type-table pass | 08-28 | `ObjectTypeDef[75]`; `wTypeFlags` → `wTriggerSound` |
| Reachability analysis | 08-28 | The missing 12,880 bytes proven to be stack + PCM, not code |
| **Transcription pass (6 forks)** | 08-28 | ~4,400 lines of exact pseudocode; **tilemap encoding** and **music opcodes** decoded; `Super()`, joystick input, row-major tilemap, AI modes, carry-flag returns all corrected |
| String extraction | 08-28 | `re/strings.md`: 64 strings, font-validated encoding; ending text found |
| Slot-0 investigation | 08-28 | **No block-pushing mechanic exists** — slot 0 is the scripted crusher/boulder hazard |
| SNDH packaging | 08-28 | Sound engine lifted into a 29-subtune SNDH with a hand-assembled relocating stub |
| Room rendering + data typing | 08-28 | All 47 rooms rendered (validates the tilemap decode end-to-end); hard-bounded data regions typed and labelled |
| Asset extraction | 08-28 | PNGs rendered and visually validated; sprite format found to be plane-major; font extent settled at 95 glyphs |
| Index demotion | 08-28 | `functions.md`/`entities.md` demoted to indexes; authority order documented in `re/README.md` |
| Audio complete | 08-28 | SNDH rebuilt from the 1 MB capture: all three PCM samples intact incl. the death sample; **confirmed by listening**; superimposed-'ding' defect fixed |
| Room render fix | 08-28 | Rooms were cut short at the bottom; added the 6-block-row margin the player actually sees |
| Asset + loose-end closure | 08-28 | Sprite extraction switched to a grid sweep (124 → **185** frames); the 5 KB post-font gap identified as 161 unreferenced scenery tiles; `level_start_info` proven to have **5** entries (entry 4 = the game-complete pseudo-level) |
| KB review + consistency pass | 08-28 | Stale content purged; `sprite_type_dispatch` corrected to **74** entries; `hide_entity` relocated; `CheckpointState` axes fixed |
| Hatari harness | 08-28/29 | Commissioned, then switched to the analysed build (`chaos43/RICK.PRG`); `-0x2054` delta reproduced; gameplay driven under script by poking `joystick1_state` |
| Dynamic-probe pass | 08-29 | 7 of 8 items resolved — several by Ghidra xref census rather than by watching |
| **Byte-identity audit (9 audits)** | 08-29 | 15 defects found and fixed; both tile probes transcribed literally; signedness of the music engine established; struct widths and hidden dispatches proven clean |
