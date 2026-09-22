# Porting Rick Dangerous 2 into `xrick` — plan

Written 2026-09-22, after a full read of `kb2/` (all `algo-*.md`, `level-tables.md`,
`graphics.md`, `sound-ref.md`, `hnk-system.md`, `PORTING.md`, `xrick2-gaps.md`,
`xrick2-ref.md`), `MEMORY.md` §10, `PLAN.md` T24–T41, and the current port tree
(`xrick/xrick/{include,src}/{rd1,rd2}`, `Makefile`, `config.h`, `xrick.c`, `sysarg.c`,
`sysevt.c`). This file is the tracked plan for `PLAN.md` T41 step 2 (and step 3's wiring);
`PLAN.md` should link here rather than duplicate this detail.

## 0. Readiness verdict: **yes**

`kb2/PORTING.md`'s own bar — "all four areas done, both statically and live" — checks
out against the documents themselves, not just their headers:

- **Logic** (`algo-player.md`, `algo-objects.md`, `algo-actors.md`, `algo-flow.md`,
  1,058 lines total): register-level pseudocode with a cited instruction address for
  every state variable and every branch, in the same style `kb/algo-*.md` reached for
  RD1 before its port began. Spot-read confirms the density (§1 of this review pulled
  `update_player_rick`'s vertical-resolution block and `update_object_slots` in full).
- **Data** (`level-tables.md` + `kb2/extract_*.py` + `kb2/assets/`): trigger/spawn/
  monster tables chain-verified over all 58 submaps; 420+4 scripts decoded with every
  jump landing on a record boundary; reproducible pipeline (`extract_all.py`).
- **Rendering** (`graphics.md`, 242 lines): screen model, both blitters transcribed
  instruction-by-instruction, frame draw order (§5) with call-site addresses, all
  formats extracted to PNG/JSON and visually checked.
- **Sound** (`sound-ref.md`, 282 lines): dispatch table (92 ids), three playback types,
  and — critically for porting — §6 already states the *exact* engineering requirements
  for a standalone build (relocation fixup set, the two-clock split, the one 4-byte
  deviation), in the same shape RD1's `dat_sndh_engine.c`/T19 needed.
- **Live validation** closed 2026-09-22: the four items that were static-only (monster
  descriptor path, spawn trigger branch, collision-probe bits, script boundaries) are
  now confirmed against real play on maps 2/3/4, not just map 1.

**Non-blocking gaps carried forward** (do not re-open, do not block on them):
T39 (sprite bank pre-unpack storage location — extraction already works from live RAM
regardless), T36 (`RICK_05.HNK` corruption cause — the correct replacement bytes are
already recovered from a second disk image), and one unexplained live actor sample
(map 2, kind 89, frame 99).

**One real open decision, not a gap**: map 3's demo-input stream is a *reconstructed
candidate* from `disks/RICKDA2/RD2`, unverified against an original (`PLAN.md` T25). The
port must pick a fallback (P1i below) — this is a decision, not missing knowledge.

**Scaffolding already exists** (`PLAN.md` T41 step 1, done 2026-09-22): the RD1/RD2
split, `include/rd2` + `src/rd2` as empty placeholders swept by the `Makefile`
(`CSRC := $(wildcard src/*.c) $(wildcard src/rd1/*.c) $(wildcard src/rd2/*.c)`,
`-Iinclude/rd2 -Isrc/rd2`), common platform layer (SDL video/audio/input/args, the
vendored `audio_engine/` 68000+YM2149 emulator) untouched and reusable as-is.

## 1. Ground rules (carried from `MEMORY.md`/`CLAUDE.md`, apply unchanged to this port)

- **Mechanical translation only.** Every `.c` function ported from a `kb2/algo-*.md`
  block cites the source address(es) in a comment, the way RD1's port comments cite
  `ASM nnnn`. No new design, no "cleaner" restructuring of documented control flow.
- **Never assume — check.** Where `kb2` marks something unverified or low-priority-open
  (T39, T36, the one live sample), the port code says so in a comment; it is not
  silently resolved by picking a plausible value.
- **Build only in WSL** (`build-in-wsl` memory). The Windows `.vcxproj` gets touched only
  if/when the user asks, same as RD1's history (T20/T21).
- **RD1 is not touched.** Nothing in `include/rd1`/`src/rd1`/the common layer changes
  except the minimal, explicitly-scoped coupling edits in P6.
- **`-rd [1|2]` is the end state**, not a stretch goal — `PLAN.md` T41's whole point is
  one executable. Do not build a separate binary or tree.
- Hatari runs (headless capture or a visible window) are pre-authorized for
  verification at any point in this plan (`hatari-runs-authorized` memory) — no need to
  ask before using `kb2/hatari_rd2.py` / `hatari_live_validate.py` again.

## 2. Step plan

Numbered `P1`–`P10`, meant to be worked in order (each phase's output is the next
phase's input) except where marked parallel-safe. Status column: `☐` not started,
`◐` in progress, `☑` done. Update in place as work proceeds — this file is the tracker,
the way `review-plan.md` was for T1.

### P1 — Data pipeline: `kb2/assets/*` → compiled-in C tables ☐

Mirrors RD1's `dat_*.c` convention (generated, header comment says which script,
never hand-edited) and specifically the `dat_sndh_engine.c` precedent (generated
verbatim blob + relocation fixups) for P1j. New generator scripts live under
`kb2/gen_rd2_*.py` (co-located with the existing `kb2/extract_*.py` they read from,
same conventions: `kb2/README.md`'s rules — re-read bytes, don't trust prior claims);
outputs go to `src/rd2/dat_*.c` + `include/rd2/dat_*.h`.

| # | Table | Source | Output |
|---|---|---|---|
| P1a | ☐ Tile banks (game + mask + animated, per map) | `graphics.md` §3/3a/3b, `extract_gfx.py` | `dat_rd2_tiles.c` |
| P1b | ☐ Sprite banks (2 shared + 4 per-map) | `graphics.md` §4, `extract_gfx.py` | `dat_rd2_sprites.c` |
| P1c | ☐ Font glyphs + 4 UI banners | `graphics.md` §4a/4b | `dat_rd2_font.c`, `dat_rd2_banners.c` |
| P1d | ☐ Palette (main + grey) | `graphics.md` §2 | `dat_rd2_palette.c` |
| P1e | ☐ Level tile maps, submap headers, block maps (4 maps × their submaps) | `level-tables.md` §1, `extract_levels.py` | `dat_rd2_levels.c` |
| P1f | ☐ Trigger table, spawn table, monster type table | `level-tables.md` §2–4, `extract_tables.py` → `tables.json` | `dat_rd2_tables.c` |
| P1g | ☐ Actor scripts (420 + 4 in-program) | `algo-actors.md` §2, `decode_scripts.py` → `scripts.json` | `dat_rd2_scripts.c` |
| P1h | ☐ Cut-scene scripts + background images | `decode_scenes.py` → `scenes.json` | `dat_rd2_scenes.c` |
| P1i | ☐ Demo input streams: maps 1/2/4 direct; map 3 = the T25 `disks/RICKDA2/RD2` candidate, **decided 2026-09-22 by the user: ship it, flagged reconstructed/unverified-original in the generator's header comment and in `dat_rd2_demo.c`'s own comment** | `hnk-system.md`, `PLAN.md` T25 | `dat_rd2_demo.c` |
| P1j | ☐ Sound engine blob + relocation fixups + patch site | `sound-ref.md` §6 (exact requirements already enumerated) | `dat_rd2_sndh_engine.c` |

Each sub-step's script re-derives from the JSON/PNG/bin artifact (or, where finer
detail is needed than the JSON carries, from `prg2-ram.bin` directly) — not by hand
transcription — and is checked the same way RD1's tables were: record counts,
boundary sentinels, a round-trip comparison against the source bytes where practical.

### P2 — Core headers (`include/rd2`) ☐ — depends on P1's field tables being final

Struct/enum definitions only, no logic: `ActorRecord` (88 B, `algo-actors.md` §1),
the object-table record (`algo-objects.md` fields), spawn/trigger record layouts
(`level-tables.md` §2–3), script opcode set (`algo-actors.md` §2), tile-attribute bits,
sound id enum (`sound-ref.md` §2/§7). One header per subsystem, named `rd2_*.h`.

### P3 — Engine skeleton (`src/rd2`) ☐ — depends on P1, P2

One module per `kb2` document, built in the dependency order the game itself uses
(`algo-flow.md` §2's skeleton dictates this):

| # | Module | Source | Notes |
|---|---|---|---|
| P3a | ☐ `rd2_game.c`/`.h` | `algo-flow.md` §1–2 | `game_main`/`frame_loop` skeleton, the per-frame state machine entry point that will become `rd2_game_run()` (P6) |
| P3b | ☐ `rd2_flow_title.c` | `algo-flow.md` §3, §4, §11 | title/attract, crack-key gate, level picker, name-entry, hall of fame |
| P3c | ☐ `rd2_level.c` | `algo-flow.md` §5–9 | level start/respawn, submap transition, map advance/endings, score/lives/bonus timer |
| P3d | ☐ `rd2_player.c` | `algo-player.md` (full, incl. §11 bomb) | `update_player_rick` |
| P3e | ☐ `rd2_objects.c` | `algo-objects.md` | 4-slot object table |
| P3f | ☐ `rd2_actors.c` | `algo-actors.md` §3–4, §6 | 6-slot actor table, script VM, trigger boxes, collision probe |
| P3g | ☐ `rd2_actorgroup.c` | `algo-flow.md` §10 | 5-actor mini-boss group (`update_actor_group`/`init_actor_group`) |
| P3h | ☐ `rd2_hud.c` | `algo-actors.md` §5 | HUD counters |

Each function carries the source address range in its comment, same convention as
RD1's port. Build against stub rendering (P4 not needed yet) to get logic compiling
and, once P4d/P5 exist, driveable under the demo streams from P1i for a first
behavioural check (P8).

### P4 — Rendering (`src/rd2`) ☐ — depends on P1a–P1d, P2; can start alongside late P3

| # | Module | Source |
|---|---|---|
| P4a | ☐ `rd2_tiles.c` | `graphics.md` §3, §3a (tile blit + scroll-window machinery) |
| P4b | ☐ `rd2_sprites.c` | `graphics.md` §4 (plain blitter, masked blitter, hit-flash silhouette) |
| P4c | ☐ `rd2_draw.c` | `graphics.md` §5 (exact frame draw order: background → objects → laser → Rick → debris → bomb → actors → HUD text → vblank/flip) |
| P4d | ☐ `rd2_screens.c` | `graphics.md` §4b, `algo-flow.md` §9/§11 (banners, submap-transition slide, name-entry redraw, hall-of-fame view) |

Reuses common `fb.c`/`img.c`/`rects.c` where their contract fits (framebuffer,
palette fade, rectangle dirty-tracking); RD2-specific composition (the circular
256-line background bitmap, the tile-window formula, the two blitters) is new code,
not adapted from RD1's `sprites.c`/`tiles.c`, which model a different hardware layout.

### P5 — Sound (`src/rd2` + reuse common `src/audio_engine/`) ☐ — depends on P1j

`rd2_syssnd.c`, structurally parallel to RD1's `syssnd.c` (T19): one persistent
`AtariMachine` instance, `sound-ref.md` §6's requirements applied directly (the
relocation fixup set, the Timer-A/Timer-C clock split, the `$3efb6`→zero-cell
redirect, `exit()` masking Timer A). This is the best-specified phase in the whole
port — §6 already reads like an implementation checklist.

### P6 — Wire-up: `-rd [1|2]` dispatch ☐ — depends on P3a existing (at least a stub)

`PLAN.md` T41 step 3, the last piece of the "one executable" goal:

- `config.h`: add an `RD1`/`RD2` selector analogous to the existing `PLATFORM_ST`/
  `PLATFORM_PC` pair — but this one is a **runtime** choice (`-rd`), not a build-time
  macro, since both games' object files link into the same binary.
- `game.h`/`game.c` → behind a function-pointer table or an explicit
  `rd1_game_run()`/`rd2_game_run()` pair selected in `xrick.c`'s `main()` after
  `sysarg_init()` parses `-rd`.
- `sysarg.c`: `-rd <1|2>` flag; game-specific bounds (`-map`/`-submap` limits, currently
  `MAP_NBR_MAPS`/`MAP_NBR_SUBMAPS` from RD1's `maps.h`) become per-game, looked up
  after `-rd` is known.
- `sysevt.c`: `game_toggleCheat()` call becomes per-game (RD2 has its own cheat, the
  POOKY-equivalent crack-key path in `algo-flow.md` §3 — confirm whether it is even a
  runtime toggle or purely a title-screen key sequence before assuming symmetry with
  RD1's cheat keys).
- `sysvid.c`'s `fb.h`/`img_icon.e` coupling and `xrick.c`'s `game.h` include: resolved
  per T41 step 1's "known follow-on coupling" list — each site either becomes
  game-neutral (common `fb.h` truly is generic — RD1's per-game HUD rect layout moves
  into `rd1_fb_layout` or equivalent) or dispatches like `game_run` does.

### P7 — Build & link ☐ — depends on P1–P6 all present (even as stubs)

`make clean && make -j4` in WSL. Success bar: single `xrick` binary, `-rd 1` and
`-rd 2` both select and run without crashing to at least their title screen. No new
warnings beyond RD1's existing baseline for files RD2 doesn't touch.

### P8 — Functional verification ☐ — depends on P7

- **Demo-stream replay check**: feed the P1i demo streams into the ported input path
  and compare the resulting play trace against `kb2/assets/live_validation_2026-09-22.json`
  where that JSON has comparable samples (script-pointer boundaries, collision-probe
  bit values) — the closest thing to a differential harness without a live Atari
  capture of the *port* itself.
- **Manual play**, all 4 maps, via Hatari-authorized side-by-side (user does the visual
  judgment call, per `MEMORY.md`'s "pixel-diffing is not required" precedent for RD1 —
  same standard applies here unless the user says otherwise).
- Sound: by-ear pass, same as RD1's T19 P9 — engineering checks can't confirm audible
  correctness.

### P9 — Fidelity audit pass ☐ — depends on P8 (needs a playable build to audit against)

RD2 analogue of `kb/byte-identity.md`: once the first playable build exists, sweep
each ported function against its `algo-*.md` source systematically (not just the spots
checked during P3–P5) and log defects the way `review-log.md` does for RD1. This is
explicitly flagged in `PORTING.md` as "the single biggest gap before absolute fidelity
can be claimed" — budget real time for it, not a token pass.

### P10 — Documentation ☐ — ongoing, closed out last

- `PLAN.md` T41: mark step 2 done, step 3 done, link this file.
- `kb2/PORTING.md` §6: update once the port starts existing (currently says "not
  started at all").
- A new `kb2/port-log.md` (or fold into `xrick2-ref.md`) recording defects found
  during the port, mirroring RD1's `review-log.md` — anything `kb2/algo-*.md` itself
  turns out to have gotten wrong under this closer reading belongs there too, fed back
  into the source document per `MEMORY.md`'s "a correction left unfolded is invisible"
  lesson.

## 3. Dependency graph (for parallelizing where it's safe)

```
P1 (data) ──┬─→ P2 (headers) ──┬─→ P3 (engine)  ──┐
            │                  ├─→ P4 (render)   ─┼─→ P6 (wire-up) → P7 (build) → P8 (verify) → P9 (audit) → P10 (docs)
            │                  └─→ P5 (sound)    ─┘
            └── P1i needs a user decision (map 3 demo fallback) before it can close
```

P1's ten sub-steps are independently parallel-safe (different source tables, different
output files). P3/P4/P5 can proceed in parallel once P2 is stable, but P3a
(`game_main` skeleton) should land first since every other P3 module is a callee of it.

## 4. Open decision — resolved 2026-09-22

**P1i**: user decided to ship the T25 `disks/RICKDA2/RD2` map-3 demo candidate, marked
reconstructed/unverified-original in the generated file's own header comment. Nothing
in P1–P10 is blocked now.
