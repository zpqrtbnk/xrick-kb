# Porting Rick Dangerous 2 into `xrick` — plan

Written 2026-09-22, after a full read of `kb2/` (all `algo-*.md`, `level-tables.md`,
`graphics.md`, `sound-ref.md`, `hnk-system.md`, `PORTING.md`, `xrick2-gaps.md`,
`xrick2-ref.md`), `MEMORY.md` §10, `PLAN.md` T24–T41, and the current port tree
(`xrick/xrick/{include,src}/{rd1,rd2}`, `Makefile`, `config.h`, `xrick.c`, `sysarg.c`,
`sysevt.c`). This file is the tracked plan for `PLAN.md` T41 step 2 (and step 3's wiring);
`PLAN.md` should link here rather than duplicate this detail.

## 0. Readiness verdict: ~~yes~~ ~~NO~~ **knowledge gaps closed 2026-09-23 (§5); user go-ahead 2026-09-24; RAM-model port in progress (§7)**

> The 2026-09-22 verdict below judged `kb2/` by its own "done" headers and by spot-reading two
> fully-transcribed routines. Starting P3 in earnest showed that many routines the transcribed
> code *calls* are only named or summarised, not transcribed — most importantly the collision
> probe and every box/point hit test, which P3d–P3g all depend on. §5 lists every gap found.
> The text below is kept as written, for the record.

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

### P1 — Data pipeline: `kb2/assets/*` → compiled-in C tables ☑ **DONE 2026-09-22**

Mirrors RD1's `dat_*.c` convention (generated, header comment says which script,
never hand-edited) and specifically the `dat_sndh_engine.c` precedent (generated
verbatim blob, no re-encoding) for P1j *and*, as it turned out, for most of P1 —
see the design note below. Generator scripts: `kb2/gen_rd2_*.py` (co-located with
the existing `kb2/extract_*.py`/`decode_*.py` they read from or import — re-ran
`kb2/extract_all.py` first to make sure the JSON/bin sources were fresh, not stale).
Outputs: `src/rd2/dat_rd2_*.c` + `include/rd2/dat_rd2_*.h`. **All compile clean**
(`gcc -fsyntax-only` over the whole `src/rd2/*.c` set, WSL, 1.3 s, zero warnings/errors).

**Design note, decided while implementing P1a/e/f/h**: rather than re-slicing each
map's level image into separate per-subsystem tables (tiles, block maps, trigger
table, spawn table, monster types, scenes — the original P1 breakdown), each
map's whole 73,472-byte level image is embedded as ONE raw blob
(`dat_rd2_levelimg.c`), with named offset constants matching `graphics.md`/
`level-tables.md` exactly. Reasoning: in the original game every one of those
subsystems is just an offset into this one blob (loaded at `$53400`); re-slicing
at generation time would mean re-deriving variable-length record boundaries
(spawn records) at Python level *in addition to* at C level in P3/P4, doubling the
surface for a transcription error. Embedding the blob whole means P3/P4's C code
is a direct, checkable transliteration of the 68000 pointer arithmetic — and it
mirrors `dat_sndh_engine.c`'s own precedent (RD1's sound blob is embedded whole
too, not split into named tables). Same reasoning applied to P1g's in-program
scripts (embedded as one blob spanning every entry point + every jump target,
computed mechanically by walking `decode_scripts.py`'s own decoder) and P1j's
sound engine.

| # | Table | Source | Output | State |
|---|---|---|---|---|
| P1a | Tiles (256/map) + animated tiles (32/map) | `graphics.md` §3/3b | *(inside `dat_rd2_levelimg.c`, offsets `0x4900`/`0x7100`)* | ☑ |
| P1b | Sprite banks: 2 shared (RAM-resident, not in any level image) | `graphics.md` §4 | `dat_rd2_sprites.c` | ☑ |
| P1b | Sprite banks: per-map level bank (128/map) | `graphics.md` §4 | *(inside `dat_rd2_levelimg.c`, offset `0x7600`)* | ☑ |
| P1c | Font glyphs (256) + 4 UI banners | `graphics.md` §4a/4b | `dat_rd2_font.c`, `dat_rd2_banners.c` | ☑ |
| P1d | Palette (main + grey) | `graphics.md` §2 | `dat_rd2_palette.c` | ☑ |
| P1e | Submap headers, block maps, block table (4 maps × their submaps) | `level-tables.md` §1, `graphics.md` §3a | *(inside `dat_rd2_levelimg.c`, offsets `0x1800`/`0x3000`/`0x3900`)* | ☑ |
| P1f | Trigger table, spawn table, monster type table, tile attribute table | `level-tables.md` §2–4 | *(inside `dat_rd2_levelimg.c`, offsets `0x0000`/`0x11e00`; trigger/spawn tables are chained after the headers, no fixed offset — same as the original)* | ☑ |
| P1g | Per-map actor scripts (420, in the monster type table's own descriptors) | `algo-actors.md` §2, `level-tables.md` §4 | *(inside `dat_rd2_levelimg.c`)* | ☑ |
| P1g | In-program scripts (bomb anim + 3 pickup anims + the 5-actor group's 16 scripts = 21) | `decode_scripts.py` docstring, `algo-flow.md` §10 | `dat_rd2_scripts_inprogram.c` (one blob, span computed mechanically from every entry point's reachable jump targets: `0x12e5e`–`0x15b38`) | ☑ |
| P1h | Cut-scene scripts + background images | `decode_scenes.py` docstring | *(inside `dat_rd2_levelimg.c`, offset `0x2000`)* | ☑ |
| P1i | Demo input streams: maps 1/2/4 direct; map 3 = the T25 `disks/RICKDA2/RD2[7680:8704]` candidate | `hnk-system.md`, `PLAN.md` T25; **shipped flagged reconstructed per the user's 2026-09-22 decision** (§4) | `dat_rd2_demo.c` | ☑ |
| P1j | Sound engine blob (code + tables + PSG stream data, `$19e96`–`$31eb0`) | `sound-ref.md` §1/§5/§6 | `dat_rd2_sndh_engine.c` — embedded verbatim/unpatched, mirroring `dat_sndh_engine.c`'s "upload at native address, no relocation needed" trick; the two `$3efb6` patch sites (§6.4) verified byte-exact against `prg2-ram.bin` in this session and recorded as named constants for P5 to apply at runtime, not baked into the blob | ☑ |

Every sub-step reads its source bytes directly (`prg2-ram.bin`, `map<N>_level.bin`,
`disks/RICKDA2/RD2`) — none transcribe from prose. `kb2/gen_rd2_sound.py` additionally
asserts the two patch-site bytes match what `sound-ref.md` documents before writing
anything (would abort with an `AssertionError`, not silently proceed, if they didn't —
they did match).

### P2 — Core headers (`include/rd2`) ☑ **DONE 2026-09-22**

Struct/enum definitions only, no logic. All compile clean together (`gcc -fsyntax-only`,
WSL). **Design note**: these are reimplementation structs with natural C field order/
sizes (comments cite the original's offset), the same convention `rd1/ents.h`'s `ent_t`
uses — not byte-exact memory overlays of the 68000 original, since the port doesn't
need address compatibility, only matching field meaning. Record/trigger/spawn/box
layouts use byte-index accessor macros instead of C structs (`rd2_tables.h`) precisely
*because* those ARE read directly off the embedded raw blobs, where even the small
residual risk of struct-layout assumptions is avoided entirely.

| Header | Covers | Source | Note |
|---|---|---|---|
| `rd2_record.h` | The one 88-byte record shared by all 17 live things (objects/laser/Rick/debris/bomb/actors) | `algo-actors.md` §1, `algo-objects.md`, `algo-player.md` §1 | One shared struct, not six — the three docs agree the record layout genuinely is shared (confirmed via the `+0x22` "anim counter" field, named three different ways by three consumers at the same offset). Script pointers (`+0x16` etc.) are left as opaque `U32` refs — resolving which of the port's two disjoint script blobs (per-map vs in-program) a reference means is P3f's job, a design question, not a documented game fact |
| `rd2_tables.h` | Trigger table, spawn table, trigger-box, monster-type-descriptor records | `level-tables.md` §2–4, `algo-actors.md` §4 | Byte-index macros, not structs (see above) |
| `rd2_script.h` | The two enemy byte-code script grammars | `algo-actors.md` §2 | Opcode-word constants only; the interpreter is P3f |
| `rd2_tileattr.h` | Tile-attribute bits + collision-probe result bits | `algo-actors.md` §6 | Notes that result bit 6 (platform-actor) is probe-only, never set by a raw tile value — checked against the 10 observed raw tile-attribute values, none has it set |
| `rd2_sound.h` | Sound dispatch ids `sound-ref.md` §7 actually names | `sound-ref.md` §7 | Only documented ids get a symbolic name, matching §7's own "a few more ids are reachable... not listed" — undocumented ids stay bare numbers at their call site in P3/P5, never invented |

### P3 — Engine skeleton (`src/rd2`) ◐ **resumed 2026-09-24 on the RAM model (§7)**

One module per `kb2` document, built in the dependency order the game itself uses
(`algo-flow.md` §2's skeleton dictates this):

| # | Module | Source | Notes |
|---|---|---|---|
| P3a | ☑ `rd2_game.c`/`.h`, `rd2_load.c` | disassembly `$10000`, `$10992`–`$10c22`, `$123b0`–`$12420`, `$144d6`–`$14540` | boot + `game_main` + loader, RAM model, 2026-09-24 — see note below |
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

**P3a status (2026-09-24): rewritten on the RAM model, syntax-checks clean** (WSL `gcc -fsyntax-only -Wall -Wextra`,
no warnings). `rd2_game.c` = boot `$10000` + `game_main` transliterated from the disassembly: every frame-end check is
now in place (S-key latch `[$10b5c]`, demo end / fire → PICK, ESC → TITLE, P pause, death test), `[$16902] := 0` on a
shot hit, and **MAPDONE is the literal original** including the picker-row-5 unlock and map 5 (§7). The 2026-09-22
MAPDONE adaptation is gone. `rd2_load.c` = `$123b0`/`$123ca` with the files copied from the embedded data instead of
the disk, `$144d6`/`$14500` (spawn re-arm on an unchanged map — **not** dead code, see §7), and map 5's red-border hang.
Every routine not yet written is declared by address in `rd2_game.h` with its phase; the game does not link until they exist.

### P4 — Rendering (`src/rd2`) ☐ (unblocked 2026-09-23, §5.D) — RAM model: routines write the ST screens at `$70000`/`$78000`

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
relocation fixup set, the Timer-A/Timer-C clock split, `exit()` masking Timer A).
**Corrected 2026-09-24 (§6 item 2):** do **not** clear `$1a974` (0 in the pristine state) and do **not** redirect
`$3efb6` to a zero cell: the driver must see the port's demo flag at `$3efb6` (the real game suppresses type-1/2
sounds during demos). Timer-A setup follows the boot code (`$1a978`, `algo-flow.md` §13). This is the best-specified phase in the whole
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

## 5. ~~BLOCKED~~ RESOLVED 2026-09-23 — routines called by transcribed code but not themselves transcribed

> **Resolved the same day (Ghidra reconnected; porting stopped at the user's instruction while the gaps were closed).**
> Every routine in the tables below was disassembled (no decompiler) and transcribed into `kb2/`:
> **A** → `kb2/algo-collision.md` (conflict settled: crouching test inclusive, standing strict — §8);
> **B** → `kb2/algo-spawn.md`; **C** → `kb2/algo-render.md` §1–§2, §10, `kb2/algo-flow.md` §13 (title image now extracted,
> `assets/gfx/title.png`; hall-of-fame table verified against the pristine program); **D** → `kb2/algo-render.md` §3, §7.
> Then a **complete call-site sweep** (every `jsr`/`bsr.w`/`bsr.b` in the program, 389 sites) found further callees that
> were only summarised, now also transcribed: window generation and scroll shifts, animated tiles, HUD/score, banner blit,
> slide blits and transitions, VBL and keyboard ISRs, input reader, the boot code (`algo-render.md` §1, §4–§9;
> `algo-flow.md` §13). See §6 for what this changes on the port side. The original gap tables are kept below for the record.

Found while starting P3b–P3g. Each routine below is called from a transcribed `kb2/algo-*.md` block,
but the current (disassembly-derived) docs give only a name, a one-line effect, or a summary — not
the instruction-level detail a mechanical port needs (exact rows/offsets, comparison strictness,
loop order, timing). Where older text exists it is in `xrick2-wk.md`, which is **decompiler-era**
and therefore not an admissible source (`MEMORY.md` §2). Per the user's rule, **P3 is aborted at
this point**: implementing any of these would mean inventing the missing detail. The Ghidra MCP
server was disconnected this session, so the gaps could not be closed here.

**Needed: an instruction-level transcription of each, into the relevant `kb2/algo-*.md`, before P3
resumes.**

### A. Collision and hit tests — block P3d (player), P3e (objects), P3f (actors), P3g (group)

| Routine | What `kb2/` has | What is missing |
|---|---|---|
| `$15fba` `query_tile_and_actor_collision` | `algo-actors.md` §6: row/column counts, per-row masks, actor-phase summary | Which tile rows are read relative to the probe y (where the body rows and the feet row sit), which columns relative to x+4, exact order of OR/mask; actor phase: the "within scroll range" condition, how `vy` is scaled in "feet not below `actor.y + vy + 8`", comparison strictness, the `$7fff` initial value of `[$15f18]` (named only in the decompiler-era log) |
| `$15f1e` crouch probe | `algo-player.md` §1: sets `[$12e16]` when its top rows hold a bit-1 tile | Everything else (rows, masks, result byte) |
| `$16278` 8-px probe variant (bomb) | "same with 8-px offsets and masks `$23/$27/$2b`" | Which offsets, which mask applies to which row/column |
| `$161fe` tile+hazard probe (laser shot, group shot) | name + inputs only | Whole routine |
| `$161ce` `aabb_overlap_test` | decompiler-era only | Whole routine, strictness of each compare |
| `$14b7a` `check_box_vs_player` | `algo-actors.md` §4: Rick box `[Rx+4,Rx+$14)`, `[Ry,Ry+$15)` / crouching `[Ry+5,Ry+$15)` | **Conflict**: the decompiler-era log says the crouching test is `Ry+5 <= py+h` (inclusive), the half-open range in §4 implies `<`. Needs the disassembly |
| `$14bee` / `$14c20` / `$14c5a` points 1/2/3 in box | gate conditions (§4) | The point-in-box comparisons themselves |
| `$15740` `mark_object_slots_touched`, `$15776` `shot_object_test` | one line each | Whole routines |

### B. Spawn / actor machinery — block P3f

| Routine | What `kb2/` has | What is missing |
|---|---|---|
| `$14594` `scan_enemy_spawn_list` | record fields and stop/visibility rules (`level-tables.md` §3) | Control flow: pointer `[$144c8]` handling, order of the tests, the group-flag early exit |
| `$14636` dispatch, `$146a0` monster-path constructor | field assignments (`level-tables.md` §3–4) | Order, which fields are cleared, the script-pointer resolution |
| `$14962` / `$14970` free-slot scans, `$149f0` / `$14a12` despawn, `$149c2` kill-all | one line each | Whole routines |
| `$14a3c` `dispatch_spawn_record` | condition bits and latch rule (`algo-actors.md` §4) | Box clipping ("clipped, skipped if entirely above" — not exact), loop over detail blocks, latch clear timing |
| `$14542` re-seek spawn table, `$1726e` group movement step | named only | Whole routines |

### C. Game flow — block P3b / P3c

| Routine | What `kb2/` has | What is missing |
|---|---|---|
| `$1919e` fade out, `$19134` fade in | named only | Step count and per-step wait — they set how many frames every screen change takes |
| `$1795c` title image depack, image at `$31eb0` | named only | Depack format; **the title image is not extracted at all** |
| `$18186` scene runner: `$183b4` run-frames loop, `$19316` text, `$18d00` image blit | opcode table in `decode_scenes.py`'s docstring | What one run-frames iteration does (move/animate/draw, how many vblanks), the text routine |
| `$16630`, `$18516`, `$1709e` (called by level start / transitions) | named only | Whole routines |
| `$123b0` `load_map_if_changed` | loader side (`hnk-system.md`); "LOADING..." banner use | What it draws and waits for, beyond the file load the port replaces |
| Hall-of-fame initial table at `$17d0e` | layout (`algo-flow.md` §11) | Not extracted (data — extractable once confirmed) |

### D. Rendering — block P4

| Routine | What `kb2/` has | What is missing |
|---|---|---|
| `$16658` scroll-edge trigger | the callees it dispatches to (`graphics.md` §3a) | Its own condition logic |
| `$17116` sprite entry | "(x+32, y−$38), then y minus the scroll fine offset" and clip bounds | Whether "fine offset" is `[$16462] & 7` or `[$1662e]`-based; exact clip compares |

### Not blocked

- **P5 (sound driver)** — `sound-ref.md` §6 is a complete, instruction-level spec; RD1's `syssnd.c`
  is the structural precedent. Could proceed independently if the user wants.
- The already-transcribed blocks (`algo-player.md` §2–§11 bodies, `algo-objects.md`, `algo-actors.md`
  §2–§3, `algo-flow.md` §2/§4–§11 bodies) are usable as-is once their callees above exist.

### How to unblock

Reconnect the Ghidra MCP (`prg2-ram.bin`), disassemble each routine above (no decompiler), and write
it into `kb2/` at the same level of detail as `algo-player.md` §3, with its addresses. Then resume P3
here. The two P3a `TODO`s that depend on these are unaffected in the meantime.

## 6. Consequences for the port — items 2–6 APPLIED 2026-09-24 (item 1: non-sound part done, sound blob deferred)

Found while closing §5; each needs a port-side change or a user decision before P3 resumes.

1. **P1 data source (decision needed).** `prg2-ram.bin` is a snapshot of the **running** game. The pristine program
   (`hnk.depack` of `RICK2.PRG`'s data section, 194,332 bytes, RAM = offset + `$f8b8`) is identical for the graphics,
   font, banners, palette and title data, but **differs in 121 bytes of sound-engine state** and in runtime variables inside
   the in-program-scripts span (`kb2/sound-ref.md` §9). `dat_rd2_sndh_engine.c` currently embeds the snapshot state; it must
   come from the pristine image. Recommended: embed the **whole pristine program image once** (it also carries every small
   in-program table P3 needs: start records `$14250`, picker records `$17996`, walk tables `$12e42`, debris offsets
   `$13e04`, group templates `$1586e`/`$15a2c`, the hall-of-fame table `$17d0e`, strings, the packed title image) and
   address it exactly as the disassembly does, replacing `dat_rd2_sprites/font/banners/palette/scripts_inprogram/
   sndh_engine`. The alternative is to keep the separate blobs and re-source them from the pristine image.
2. **P5 plan text is wrong on two points.** Do **not** clear `$1a974` (0 in the pristine state), and do **not** redirect
   `$3efb6` to a zero cell. The real game suppresses type-1/2 sounds during demos, so the driver must present the port's
   demo flag at `$3efb6`. Timer-A setup follows the boot code (`algo-flow.md` §13).
3. **P2 header comments to correct**: `rd2_record.h` `flags` bit 7 = "detonates a falling bomb it touches" (not a shot
   check); `rd2_tables.h` box semantics (a latched box that hits is ignored without being un-latched; sound `$17` follows
   mask bit 3, not the test that fired).
4. **Mutable level image**: spawn/box bits are written into the level image, which is only re-depacked when the map
   changes, so the port needs a per-load mutable copy that is **not** reset on death (`algo-spawn.md` §9).
5. **Input model**: the game reads the raw IKBD joystick-1 byte and the **last raw keyboard byte** (break codes included,
   `algo-flow.md` §13). Host bindings must produce exactly that, not a key-is-down state.
6. **Persistent probe globals**: the ladder probe inherits `[$15f16]` from the previous caller (`algo-collision.md` §11).
   All probe cells must stay globals.

**Honest scope note.** The pre-existing transcriptions that §5 did not flag (`algo-player.md`, `algo-objects.md`,
`algo-flow.md` §3–§11, `algo-actors.md` §3) were written from the disassembly on 2026-09-19/20. This pass re-read
`update_actor_ai` and the bomb in full (both matched, with the clarifications folded in), and spot-read the rest where a
callee needed it, but did **not** re-audit the rest of those documents instruction by instruction.

## 7. Decisions of 2026-09-24 and the RAM-model redesign

**User decisions (2026-09-24):**
- **Map 5: literal original.** Finishing map 4 in a game started from level 1 unlocks picker row 5 and advances to
  "map 5", whose load hangs with a red border, exactly as shipped (`algo-flow.md` §8, `hnk-system.md` §7). This
  **supersedes** the P3a adaptation (which re-triggered ENDING off map 4, running `run_scene(2)` on map 4's image, which
  has only scenes 0–1 — a fill-in not grounded in anything, now removed) and supersedes `PLAN.md` T28's "no unlock
  code" for the port.
- **Data source:** non-sound data comes from the **pristine program image** (depacked `RICK2.PRG`, RAM = offset + `$f8b8`),
  one generated blob. `dat_rd2_sndh_engine.c` (sound, snapshot-derived) is left untouched for now (§6 item 1 deferred).
- §6 items 2–6 are to be applied now.

**Architecture: RAM model (replaces the P2 struct design).** Yesterday's findings showed how much of the game's
behaviour lives in address-level detail: the `+0` word / `+1` byte overlap, script pointers into two different
images, the high byte of `[$15f12]`, probe cells that persist between callers, runtime bits written into the level
image, and data tables at fixed program addresses. A struct-based re-coding would have to re-derive each of these by
hand. Instead the port keeps an **emulated 68000 address space** (`rd2_mem.c`: 1 MB, big-endian accessors
`rd2_rb/rw/rl`, `rd2_wb/ww/wl`). The pristine program image is loaded at `$f8b8`, the level image at `$53400` (a
mutable copy, reloaded only when the map changes, as `$123b0` does), the stage-1 file at `$65300`, the demo stream
at `$3efc0`, and the screens at `$70000`/`$78000`. Every routine is transliterated onto those accessors at the
original addresses, with the address in a comment. The host side emulates only what the game gets from the hardware:
the VBL counter `[$19232]` (a 50 Hz tick), the IKBD bytes `[$1a4fa]`/`[$1a4fb]`/`[$1a4fc]`, the palette registers,
and presentation of the displayed screen `[$18eda]` at each flip. The sound engine runs in its own AtariMachine (P5),
so the game's reads of sound-state cells (e.g. `[$1aa08]`) must go to that machine once P5 exists.
Consequences for P1/P2: `dat_rd2_sprites/font/banners/palette/scripts_inprogram` are superseded by the program image
and removed; `rd2_record.h` becomes record-offset constants; `rd2_game.h` globals become RAM cell addresses.

**Applied 2026-09-24 (§6 items 2–6):**
- Item 2: P5 text corrected (above).
- Item 3: `rd2_record.h` is now record-offset constants (`RD2_R_*`, record bases `RD2_REC_*`), with F bit 7 = "detonates a
  falling bomb it touches"; `rd2_tables.h`: trigger bit 5 = `RD2_TRIG_B0_TUNNEL` (`[$12e14]`), bit 6 = `RD2_TRIG_B0_ARM_GROUP`
  (`[$144c2]`), box latch / sound `$17` / top-clip semantics per `algo-spawn.md` §5.
- Item 4: `rd2_load.c` writes the level image into RAM at `$53400` only when the map changes; deaths never pass through it.
- Item 5: `rd2_sys.c` — host input is fed byte by byte to the transliterated ACIA handler `$1a546`: joystick 1 as
  `($ff, byte)` on change, keys as make/break codes without repeat. Only the codes the game is known to test are mapped
  (ESC `$01`, P `$19`, S `$1f`); the name-entry keys come with P3b (`$17f22`). **Host binding note:** space is the host's
  joystick fire key, so it is not also sent as the keyboard's `$39` (the title's palette toggle, `$17cd8`); pick another
  host key for `$39` if wanted.
- Item 6: all probe cells live in emulated RAM at their addresses, so they persist between callers by construction.

**Host bridge (`rd2_sys.c`).** The VBL ISR `$1902e` (`[$19232] += 1`, music tick `$1a866`) runs once per 20 ms of host
time, inside the game's own busy-wait loops (`$19216`, `$191e6`, transliterated there), not asynchronously as on the ST.
Each VBL presents the ST screen at the video base (`$19234` → `$ff8201/$ff8203`) with the palette registers.
`rd2_mem_init` zero-fills RAM outside the program: checked over the decoded instructions (see `rd2_mem.h`), not over
code Ghidra never decoded.

**Finding 2026-09-24 — `$144d6` is live code (kb2 corrected).** `load_map_if_changed` has `bsr.w $144d6` at `$123be`
(bytes `6100 2116`), which Ghidra had skipped, so the earlier "dead code" verdict (`algo-spawn.md` §9) was wrong. On an
unchanged map the loader re-arms the spawn records of submaps `0..N-1` (`N` from `$144cc` = 9/13/10/13/8). This happens
for a new game on the loaded map and for every demo. A byte scan of every undecoded gap in `$10000`–`$1a51f` for
`bsr`/`jsr`/`jmp` found no other undocumented call; the rest are the FDC and IKBD hardware code and `$1869c → $175f2`,
already covered by `algo-render.md`. `algo-spawn.md` §9, `algo-flow.md` §13 and `sound-ref.md` (`$1a978` is called by
the boot code) were corrected.

**Map 5 (checked 2026-09-24):** descriptor `$12e08` → demo file `(0013, 0002)`, sum `$15`, not accepted by `$11f86`
→ `$11fb8` red border, forever. Before that: the LOADING banner, `$1a5d0`, `[$1239e] = 5`. Tables identical in the
pristine image and the snapshot.

**Progress log (RAM model):**
- 2026-09-24 ☑ `rd2_collide.c/.h`: probes `$15fba`/`$15f1e`/`$16278`/`$161fe`, `$1643e`, `$161ce`, `$14c8c`, hit tests
  `$14b7a`/`$14bee`/`$14c20`/`$14c5a`/`$14cb4`/`$14d04`, from the disassembly. **kb2 corrected:** `algo-collision.md` had
  the row loops running D2+1 times; each loop enters at its `dbf` (`bra` → `dbf`), so it runs D2 times (the feet row is
  then the row of `y + $14`, as it must be). Rule kept for the rest of the port: code comes from the disassembly, with
  kb2 as the guide; a mismatch is fixed in kb2 and noted here.

- 2026-09-24 ☑ `rd2_spawn.c`: `$14542`, `$14594`, `$14636`, `$146a0`, `$14862`, `$14962`/`$14970`, `$14998`, `$149c2`,
  `$149f0`, `$14a12`, `$14a3c`.
- 2026-09-24 ☑ `rd2_actors.c`: `$14d48`, `update_actor_ai` `$14d70` (incl. static actors `$14f24`), `$171bc`, `$172fa`,
  `$1726e`, `$1704c`, `$171a4`, `$15740`, `$15776`.
- 2026-09-24 ☑ `rd2_score.c`: `$1771c`, `$17760`, `$17782`, `$177a8` (HUD), `$17810`, `$1789a`, bonus timer `$157b4`/
  `$157be`/`$157f4`/`$15826`. abcd/sbcd are implemented for valid BCD operands (all operands here are).
  Found: `$17810` still sets the score dirty flag `[$176f0]` in demo mode (it only skips the addition).
- 2026-09-24 ☑ `rd2_level.c`: `$123a0`, `$14222`, `$142a0`, `$142fc`/`$13060`/`$14300`, `$12f08`, `$1300e`, `$14458`,
  `$14362`, `$14434`, PRNG `$18516`/`$18538`.

- 2026-09-24 ☑ `rd2_objects.c` (`$150a2`, `$150c0`, `$1570e`) and `rd2_player.c` (`$13096` Rick, `$13d0a`, `$13d58`,
  laser `$13e14`, bomb `$13e98`, input `$141cc`): register-level transliteration (`rd2_cpu.h`), 16.16 `swap` logic kept.
  Observed in the code (not in kb2 before): after a landing on map 3 the object code overwrites `+$c` with `$100`
  before its bounce test reads it, so objects never bounce (`$1525a`/`$15270`) — already in `algo-objects.md`. On map 4,
  `+$48` is set only when `+$a < 0` (`$1535c bpl $15366`), as `algo-objects.md` says (a first draft of the C missed it; fixed).

- 2026-09-24 ☑ `rd2_group.c`: `$15b3c`, `$15bc0` (the `exg` box juggling kept), `$15d84`, `$15e48`, `$15eca`.
- 2026-09-24 ☑ `rd2_render.c`: palette/fades, text, clear, banner, sprite walkers + `$17116`, background window
  (`$16474`/`$165a6`/`$165fc`/`$164de`/`$1653e`), animated tiles (`$175c6`/`$175f2`/`$17644`/`$17694`/`$18dac`), row
  renderer `$185a6` (from raw bytes; Ghidra misdecodes from `$185fe`), `$1856a`, `$16630`, `$18782`, scrolling
  (`$16658`/`$166ae`/`$16718`/`$16786`/`$1884c`/`$1888e`), `$188d0`, transitions `$18abe`/`$18bb2` + slides, `$18caa`.
  The two sprite blitters are implemented per pixel from `algo-render.md` §3 (both read in full on 2026-09-23); their
  shared entry was re-read here.
- 2026-09-24 ☑ `rd2_flow.c`: title/attract `$178dc`, `$1793a`, tree depacker `$1795c`, wait `$17c86`/`$17cd8`, picker
  `$17a46`/`$17b86`, `$17bda`, `$17bf4`, game over `$17c06`, hall of fame `$17e40`, name entry `$17f22`/`$1813e`, scene
  runner `$18186` with its 14 opcodes and `$18d00`. Name entry uses the joystick on a letter grid (no keyboard); its
  fire-release loop `$18080` spins without a VBL wait, so the port pumps input there (the IKBD ISR's job on the ST).
- 2026-09-24 ☑ P5 `rd2_snd.c`: the game's own engine runs unmodified on the AtariMachine (68000 + YM2149 + MFP),
  uploaded from the **pristine** program in `rd2_ram` (`$19e96`–`$31eb0`), so no snapshot blob and no patch. Shared
  cells found by listing every absolute-long operand in Ghidra's decoded code: the engine reads only `$3efb6` (demo flag)
  outside its region; the game writes `$1a5ce` and reads `$1aa08`. They are copied across (`$3efb6`/`$1a5ce` before
  each dispatch, `$1aa08` read from the machine). TICK runs at 50 Hz in the audio thread, like rd1.
- 2026-09-24 ☑ P6: `-rd <1|2>` (`sysarg.c`, `xrick.c`); `rd2_game_run()` replaces `game_run()`, `rd2_snd_*` replace
  `syssnd_*`. P7: full WSL build links (`make`), only sign-conversion warnings of the kind rd1 already has.
- 2026-09-24 P8 started: debug hooks in `rd2_sys.c` (`RD2_SHOT`/`RD2_SHOT_AT`, `RD2_EXIT_AT`, `RD2_INPUT`, inert when
  unset). A 4000-VBL run of `-rd 2` shows the title picture, the hall of fame, the attract demo on map 1 (HUD, scrolling,
  ladders, room changes, sprites) and the loop back to the title. **Not yet compared with the original** (Hatari).

- 2026-09-24 **P8 frame-exact comparison with the original**: `kb2/hatari_rd2_trace.py` boots the original in Hatari
  and saves RAM `$12e00`-`$17800` (player, objects, actors, spawn/trigger cells, all 17 records, scroll, HUD, score),
  `$54c00`-`$56400` (submap headers, trigger and spawn tables with their runtime bits) and `$70000`-`$7ffff` (both
  screens) at every hit of the frame head `$10a54`, starting at the first level start `$10a4e`; the port writes the
  same bytes at the same point (`RD2_TRACE`). **Map 1: the first 2000 frames (the attract demo, repeated through the
  title/hall-of-fame loop) are byte-identical, screens included.** Maps 2-4 via `RD2_FORCE_MAP` / the script's map
  argument (poke `[$1239c]` at `$10a36`, the method `kb2/hatari_rd2.py` already used): see below.

- 2026-09-24 Maps 2 and 4 attract demos: 1500 frames byte-identical. Map 3: identical at frame 1 (level load and
  start), diverges from frame 2 because the inputs differ: Hatari boots the cracked disk whose `RICK_05.HNK` demo is the
  corrupted file, the port plays the reconstructed stream `RD2[7680:8704]` (user decision 2026-09-22). At frame 2 the
  original's Rick jumps and pushes left, the port's stands still; nothing but input-driven state differs. Map 3 logic is
  therefore checked by the scripted-play test instead.
- Scripted play test (`RD2_JOYSEQ` / 4th argument of the Hatari script): frame 1 clears the demo flag, every frame head
  writes the same scripted byte into `[$1a4fb]` on both sides → a real game (score, lives, deaths, respawns).

- 2026-09-24 Scripted play (4000-byte pseudo-random joystick sequence, seed 12345, runs of 4-40 frames; a TEST INPUT,
  not a playthrough — Rick wanders and dies): byte-identical up to game over on every map: map 1 1192 frames, map 2
  408, map 4 682, map 3 1795. On map 3 the run goes game over → title → attract demo at frame 1796, and from 1797 it
  shows the same divergence signature as the map-3 demo (different demo streams, see above); the bytes that differ from
  a fresh demo start at 1796 are all leftovers of the played game (previous x/y, melee/shot/explosion points, probe
  cells, the laser and debris records, HUD icon buffers). Covered so far: deaths, respawns, laser, bombs, pickups,
  scrolling, game over. **Not yet covered**: submap slides across a whole map, map completion (MAPDONE/NEXT/ENDING),
  the picker, name entry — they need a real playthrough recording.

- 2026-09-24 Demo mode shared with RD1 (user request; `kb/demo.md` §7): `-demo` / `-record` now work with `-rd 2`
  (`src/rd2/rd2_demo.c`, one script per map, tick = frame head, playback/recording on `[$1a4fb]`). `-record` also
  writes `<file>.map<N>.joy` for `RD2_JOYSEQ` / Hatari. Checked: record → rebuild → `-demo` gives an identical RAM trace
  (880 frames); the `.joy` gives port = Hatari (881 frames). Route difference: replaying a `.joy` via the forced-map
  attract start (the Hatari method) instead of title → picker gave identical Rick x/y, submap and lives on all 880
  frames, but 80 bytes in `$16d7d`–`$16edd`+ differ and stay constant (not identified). Keyboard play: host keys →
  `control_status` (`src/sysevt.c`) → `joystick()` → IKBD `$ff`+byte; the scripted tests drive `joystick()`, a real
  key press was NOT tested from here (no key injector in WSL).

- 2026-09-24 Windows build (user request): `xrick.vcxproj`/`.filters` file lists and include paths brought in line
  with the Makefile after the rd1/rd2 split (`kb/build.md` §2). MSBuild Release x64 builds (3 warnings, none in rd1/rd2);
  `bin\Release\xrick.exe -rd 2` RAM trace = WSL build for 600 frames.

- 2026-09-24 Two host-side bugs found when the user ran `xrick.exe -rd 2` (black window), both on every platform, both
  missed because every earlier check read `fb`/RAM (`RD2_SHOT`, `RD2_TRACE`) and ran `-nosound`:
  1. **Black window**: `sysvid.c` scales every colour by `vid_gamma`, which starts at 0 and is set only by rd1 code.
     `rd2_sys_init` now sets it to 255 (RD2 fades in the ST palette). Checked: Windows window capture shows the title
     and the attract demo.
  2. **No sound at all, and stalls**: `rd2_snd_init` runs in `sys_init` (`xrick.c`), before `rd2_mem_init` fills
     `rd2_ram`, so the engine was uploaded as zeros; every TICK ran the emulated 68000 into data until the 1 s
     `Jsr` timeout (~54 ms of host time each), blocking the game on the sound lock (1 presented frame per ~6 VBLs).
     Now uploaded from `rd2_program` directly. Checked: 600 VBLs in 12-13 s with sound (WSL and Windows, all presented);
     SDL `disk` audio capture of 500 VBLs = varying 16-bit signal (rms 2000-3900). **By-ear check still to do.**
  Note: with `-nosound`, `rd2_snd_rw($1aa08)` returns RAM's never-updated value, i.e. "music finished", so the
  title's music waits end at once; with sound they follow the engine, as on the ST.

- 2026-09-24 **User play test (Windows `xrick.exe -rd 2`): the game starts and plays, sound is correct (by ear),
  keyboard input works.** P8's by-ear sound check is thereby done.
- 2026-09-24 **Verification and troubleshooting phase starts** (user). First requests — rd1 host behaviour in RD2,
  host code only (fb overlays and control handling; emulated RAM untouched, attract-demo RAM trace unchanged over 600
  frames):
  - **Pause box**: the original draws nothing (`$10ba6`: `jsr $191e6` until `btst #7,[$1a4fb]`, checked in the
    disassembly), so rd1's `screen_pausedtxt` (10×3 at 120,80) is drawn over the game while that loop runs, with
    the game's own font (`$3ce54`). **Resume with P, as in rd1, not fire** (user, 2026-09-24): wait for P released,
    pressed, released (host `CONTROL_PAUSE`); fire is ignored while paused. Entry is still the original's `$19` test.
  - **ESC quits the program** (rd1 `CONTROL_EXIT`, checked in `rd2_sys_pump`); it is no longer sent to the game as
    IKBD `$01` (the original's "back to the title", `$10b90`, now unreachable from the keyboard).
  - **E ends the game** (rd1 `CONTROL_END`): stop sound (`$1a5d0`), then `END_OF_RUN` = game over screen and name
    entry, as when the last life is lost. Real games only, not the attract demo.
  - **Map/submap numbers**: `M<[$1239c]>` / `S<[$16464]>` (map 1-based, submap index 0-based as `$14458` stores it)
    at 0,16 / 0,24 in the left border (black in every sampled frame), from level start until LOAD / TITLE /
    END_OF_RUN.
  Checked on Windows by posting key messages to the window and capturing it (`PrintWindow`): M01/S00 shown, P →
  PAUSED box, fire → still paused, P → resumed, E → GAME OVER → title, ESC → exit code 0. Cheats and F4–F6: `PLAN.md` T42.

**Next:** a human playthrough recorded with `-rd 2 -record`, replayed in Hatari via its `.joy` (map completion, submap
slides); then P9.
