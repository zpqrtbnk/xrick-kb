# What a mechanical port of Rick Dangerous 2 still needs

Rewritten 2026-09-22. The 2026-09-18 version of this file is obsolete — it predates the 2026-09-19→22 pass that extracted
every table, decoded every script, transcribed the player/object/actor/flow logic, settled the HNK/loader story, and closed
the "map 5" question. "Mechanical port" = reimplement the game faithfully on a modern host by transcribing understood logic
and extracting original data, without redesigning anything (RD1's precedent: `xrick/`, `kb/`).

A port needs four things. **All four are done, both statically and live.**

| | Area | State |
|---|---|---|
| 1 | **Game logic** — main loop, player, objects, actors, AI, physics, input, score/lives, flow | **Done.** Transcribed statically; the paths a single 2026-09-19 sample hadn't reached are now live-confirmed across maps 2/3/4 too, see §5 |
| 2 | **Game data** — HNK format/loader, levels, tables, scripts, graphics, cut-scenes | **Done.** Extracted, chain-verified, reproducible pipeline; script execution live-confirmed, see §5 |
| 3 | **Rendering** — tile/sprite/font formats, both blitters, palette, screen composition, frame draw order | **Done, fully.** Every corner closed 2026-09-22 (§4) |
| 4 | **Sound** | **Done** (`sound-ref.md`, `rick2_sfx.sndh`) |

## 1. Game logic — transcribed, not yet ported

Everything needed to reimplement gameplay is written out branch-by-branch, not just summarized:

- `kb2/algo-player.md` — `update_player_rick`, vertical/horizontal resolution, fire/melee, ladders, death, the bomb.
- `kb2/algo-objects.md` — the 4-slot object table (`update_object_slots`): gravity, per-kind movement, contacts, destroy/dying.
- `kb2/algo-actors.md` — the 6-slot actor table (`update_actor_ai`), trigger boxes (`dispatch_spawn_record`), the collision probe, tile-attribute bit meanings (derived from every consumer, not guessed).
- `kb2/algo-flow.md` — the whole `game_main` state machine: title/attract, level picker, level start/respawn, map advance, score/lives/bonus timer, submap transitions, the 5-actor mini-boss group, game over, hall of fame.
- `kb2/level-tables.md` — submap headers, trigger table, spawn table, monster type table grammars, each grammar checked against every submap in all 4 maps (chain-exact, not sampled).
- `kb2/decode_scripts.py` / `kb2/decode_scenes.py` — every one of the 420 enemy move/animation scripts and all 4 maps' cut-scene scripts decoded and self-checked (every jump lands on a record boundary; every scene's opcodes are valid).

**Live confirmation, closed 2026-09-22:** the 2026-09-19 session only live-checked map 1 (attract mode). The type-`<0x75` monster-descriptor path, the spawn table's trigger/effect branch, the exact collision-flag
bit combinations, and script execution generally were read in full from the disassembly but not watched firing on real data. `kb2/hatari_live_validate.py` closed all four across maps 2/3/4 — see §5 for the evidence.

## 2. Game data — extracted and verified, not "mostly known"

Complete pipeline, `py -3 kb2/extract_all.py`:

- `kb2/hnk.py` — both depackers (backward LZ "LSD!", the tree coder), transcribed from the game's own routines.
- `kb2/extract_hnk.py` → `kb2/assets/maps/map<N>_{demo,level_stage1,level}.bin`, `manifest.json`, `demos.json`.
- `kb2/verify_hnk.py` — 26 independent checks: archives match three sources, the game's own descriptor table, raw sectors of a second disk image, the loader's own 8-file digit table, live RAM, two loader-time snapshots, and the depacked program.
- `kb2/extract_tables.py` → `tables.json` (submap headers + trigger table + spawn table + monster types, all 4 maps, chain-verified) and `tile_attributes.json`.
- `kb2/decode_scripts.py` → `scripts.json` (420 scripts).
- `kb2/decode_scenes.py` → `scenes.json` (cut-scenes + their background images).
- `kb2/extract_levels.py` → per-submap tile-map PNGs.
- `kb2/extract_gfx.py` → tiles, tile mask, animated tiles, sprite banks, font, scene-background PNGs.

**What was wrong before and is now fixed:** the game has 4 maps, not 5 — "level 5" is a sequel tease, dead code, never playable on any release (`kb2/hnk-system.md` §7, `PLAN.md` T28, settled by the user). `RICK_05.HNK` (map 3's demo) is a genuine crack corruption with a known-correct replacement from a second disk image (`hnk-system.md` §6).

**What is left:** T37 (non-zero bytes past the block-map extent) is closed — proven unused margin, not read by anything. T36 (how the crack corrupted `RICK_05.HNK`) stays a parked curiosity — a Copylock-weak-sector
hypothesis is consistent with the evidence but not provable without the physical original disk; not needed for the port, since the correct bytes are already recovered from a second disk image.

## 3. Rendering — done, fully

`kb2/graphics.md` has the full screen model: 320×200, 4-plane, playfield 256×192 at (32,8); tile format (8×8, 40 B, 4 planes + 1 mask byte); the tile-ID window and its scroll-shift machinery (including a proof
that it never over-reads a submap's own block-map data — 6 rows of margin, always); both sprite blitters transcribed instruction-by-instruction (plain: OR-into-background with colour-0 transparency; masked:
the same gated by the tile-mask bitmap; a third mode draws a solid silhouette for the hit flash); the frame-by-frame draw order (background → objects → laser → Rick → debris → bomb → actors → HUD text →
vblank + buffer flip); the text/glyph blitter's exact column/row addressing; the HUD's 4 columns (score + 3 icon-strip counters, all on row 0) and which icon each draws; the 4 fixed UI banners
("CONGRATULATIONS!"/"HALL OF FAME"/"SELECT LEVEL"/"LOADING...") decoded and extracted to PNG; the submap-transition slide's two blit routines (role and direction confirmed; the Atari bitplane-shuffle
arithmetic itself deliberately not modelled, out of the user's stated scope — a port reimplements the visual effect from the already-decoded tile maps, not this transient hardware trick).

Genuinely open, low priority, not needed for the port (`PLAN.md` T39): where `RICK2.PRG` keeps the shared sprite banks before it unpacks itself — irrelevant, since they're already extracted correctly
straight from live RAM.

## 4. Sound — complete

Unchanged from before: `rick2_sfx.sndh` plays all 92 in-game sounds correctly; `sound-ref.md` has the 92-entry dispatch table, the three playback types, the bytecode grammar, the instrument records, and the volume tables. A port can emulate the YM2149 and play the same data, or pre-render. `$1a5d0`'s role (a direct YM2149 silence-everything write) and every sound id `algo-flow.md` uses are now identified (`PLAN.md` T33, closed).

## 5. Live validation — DONE 2026-09-22

`kb2/hatari_rd2.py` boots the game headlessly in WSL Hatari and dumps RAM; it did the 2026-09-19 map 2–4 checks (level images byte-exact). `kb2/hatari_live_validate.py` (user lifted "no live run for now")
closed everything that was only statically read, capturing maps 2/3/4 in real (attract-mode) play — evidence in `kb2/assets/live_validation_2026-09-22.json`:

- The monster-descriptor path for type IDs `< 0x75` (`FUN_000146a0`) — **confirmed firing live**: the spawn table's "already spawned" bit flipped on genuine low-type records across all three maps.
- `dispatch_spawn_record`'s trigger/effect branch (spawn byte 2 bit 7 clear) — **confirmed firing live**: found and watched real trigger-path records (map 2 type 122, map 4 types 26/3) get consumed.
- The exact combinations of collision-probe result bits (`algo-actors.md` §6) — **confirmed**: 120 live samples, every value a combination of the documented bits 0–4, zero exceptions (bits 5–7 simply weren't
  exercised by this capture window — absence of evidence, not a contradiction).
- Script/table execution beyond the one map-1 sample from 2026-09-19 — **confirmed**: 20 of 21 live actor-table samples across the three maps had their script pointer sitting exactly on a decoded record
  boundary (`kb2/decode_scripts.py`'s output), including matches against the shared in-program scripts. One sample (map 2, actor kind 89) didn't match anything decoded and is noted, not explained.

One early attempt crashed the emulated 68000 (bus-error fault loop) when chaining 250 one-shot breakpoints at the same address with no gap between rearms; spacing samples to every 15th hit fixed it —
see `kb2/hatari_live_validate.py`'s comments if reusing this technique elsewhere.

**Static and live reverse-engineering of Rick Dangerous 2's logic and data are now both complete.** Nothing blocks starting the port.

## 6. Not started at all: the port itself

- **Decided 2026-09-22 (`PLAN.md` T41): one executable, not two.** RD2 does **not** get its
  own `xrick2/` tree. `xrick/xrick/` (the port) now has `include/rd1`, `include/rd2`,
  `src/rd1`, `src/rd2` alongside a common platform layer (SDL video/audio/input/args,
  the vendored Atari chip emulator) at top. RD1's engine/data have already been moved
  into `rd1/`; `rd2/` exists but is still empty — step 1 was the reorg only, no RD2 code
  yet. The end goal is a single `xrick` binary, game selected at runtime by `-rd [1|2]`.
- RD2's engine is **not a data-only swap into RD1's engine** — it's a structurally
  different architecture (88-byte `ActorRecord`, script-driven movement/animation, two
  actor tables per `kb2/algo-actors.md`) — so porting it is a full implementation against
  `rd2/`, reusing only the common platform layer, not RD1's `ents.c`/`maps.c`/etc.
- No byte-identity comparison method exists for RD2 (RD1 has `kb/byte-identity.md`).

## Suggested order, once the user wants to proceed

1. Close the small static items in §2/§3/§4 (a day or two of Ghidra reads, no live run).
2. If desired, do the live-validation pass in §5.
3. Port the logic into `xrick/xrick/{include,src}/rd2/` (skeleton already exists —
   `PLAN.md` T41 step 1) and build a differential/byte-identity harness against the
   original — all the logic is already transcribed in the `algo-*.md` files. Then wire
   `-rd 2` into `sysarg.c`/`xrick.c` (T41 step 3) to select it at runtime alongside RD1.
