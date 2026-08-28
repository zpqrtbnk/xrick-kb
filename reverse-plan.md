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
| Source artifact | Hatari RAM snapshot, 327,680 bytes (`0x00000`–`0x4FFFF`) |
| Functions | **133**, all named; every non-trivial one transcribed |
| Structs defined & applied | 9 |
| Entity dispatch types | **74/74** characterised |
| Knowledge base | 14 files in `re/`, ~6,300 lines, + 11 extracted PNGs |
| Largest untyped region | `0x1B01E`–`0x44BED` (170,960 bytes) — the graphics blob |
| Program bytes not captured | 12,880 (`0x50000`–`0x5324F`) — **stack + audio only, not code** |

---

## 2. Coverage against the reimplementation bar

**The code is fully reversed.** Every function is named, and every non-trivial one is
transcribed to exact pseudocode in `re/algo-*.md` (constants as literals, branch order
preserved, register conventions documented). The following are re-codable from `re/`
alone:

- Frame loop, timing, double buffering, VBlank/Timer-A interrupts, supervisor entry
- Player controller — movement, jump/gravity, climb, crouch, attacks, death
- The sprite blitter (aligned + shifted paths, derived transparency, clipping)
- Enemy AI (3 modes), the shared scripted-trap engine, pickups, triggers, collision
- Level data model: rooms, transitions, placements, object templates, **tilemap encoding**
- PSG sound engine including the **sequence opcode set** and sample playback
- HUD, score, lives, per-room checkpointing, game-over/respawn, attract mode
- All in-game text and the font/character encoding

**Graphics are extracted and visually validated** (`re/assets/`, 11 PNGs;
`assets-manifest.md`). **Audio is decoded but not rendered** — the PSG sequences and
three PCM samples have documented formats but have never been synthesised.

**Verdict: ~95% of a reimplementation spec.** Code fully reversed; graphics extracted
and visually validated. What remains is audio rendering, room-map rendering (both
unblocked), and a short list of behavioural details wanting a live run.

---

## 3. Gap register

### A. Assets — ✅ EXTRACTED AND VALIDATED (2026-08-28)
`re/extract_assets.py` renders every located graphic to `re/assets/` (11 PNGs), and
`re/assets-manifest.md` documents the formats. **Validated by looking at the output**:
the title screen, sprite sheet and tile blocks all come out as recognisable artwork,
which confirms the palette, plane decoding and base addresses simultaneously.

Extracted: 16-colour palette, 95-glyph font, 2×256 tiles, 2×256 assembled 32×32
blocks, 124 sprite frames, the title screen, and three 320×32 banners.

Findings from doing it:
- **Sprite data is plane-major**, not ST screen format — each row stores one longword
  per bitplane so `render_sprites` can rotate planes independently. Decoding it as
  screen data yields noise. This is a trap for any reimplementation.
- **The font extent is settled**: 95 glyphs, `0x00`–`0x5E`, with digits at `0x00`
  (hence unpacked-decimal scores) and `A`–`Z` at ASCII positions.
- **`0x40FEE` is three 320×32 banners**, not a full-screen image — which explains
  `blit_image_5120`'s otherwise odd 5120-byte size.

Still unrendered: **audio** (PSG sequences and the three PCM samples are decoded but
not synthesised) and **whole-room maps** (the tilemap encoding and blocks are both
available, so this is now straightforward).

### B. Incomplete capture — closed as a code concern
`p_tbase 0x1B018 + p_tlen 0x38238 = 0x53250`; the snapshot ends at `0x50000`, so
12,880 bytes are missing. Proven **not to be code**:
- No instruction targets the region. The single `0x50000`+ operand in all 4,611
  instructions is `Super()`'s stack-pointer argument, not a memory access.
- The game calls **`Super(0x5324C)`** (GEMDOS 0x20), so `0x5324C` is the supervisor
  stack top and the stack grows *down into* the uncaptured region.
- No structural table references it (apparent hits are 6-byte movement-path records
  `{duration=5, dX=1}` reading as the longword `0x00050001`).
- What does point there is **PCM sample data**: `music_track_table` tracks 8, 10 and
  19 → `0x4DF86`, `0x4FCF2`, `0x50DA8`. Track 19 lies entirely inside the gap and
  track 10's sample must run past the cut.

→ A wider Hatari capture would recover two sound samples. Not on the critical path.

### C. Level loading — moot, and now demonstrably so
There is no runtime disk access: the whole program contains exactly two traps
(`Super`, `Setscreen`) — no GEMDOS, BIOS or XBIOS file/sector call anywhere.
**All four levels are fully resident**: 47 room headers, all tilemaps in one
contiguous 8 KB region, 523 placement records, five intro texts, and — crucially —
**only two tile banks**, shared pairwise (bank 0 = South America + Egypt, bank 1 =
Castle + Missile Base). Level completion is pure pointer arithmetic through
`level_start_info`. Loading happened once, before this snapshot, in the outer
loader stage. A reimplementation needs no loader at all.

### D. Behavioural details wanting a live run
- The `"POOKY9999"` easter egg's full effect (flag `0x498C4` is set in
  `enter_highscore_name`; it gates the level-select menu, but the rest is untraced).
- The `player_touched_hazard` consumer site.
- ~~Slot-0 block pushing~~ — ✅ **RESOLVED 2026-08-28: no such mechanic exists.** The
  premise was wrong. Slot 0 holds a **scripted moving hazard** (crusher / falling
  boulder): spawned there when a `PlacementRecord` sets `bTriggerFlags` bit 1, and
  moved by `scripted_trap_update` stepping `movement_path_table` through `A0`. All 26
  slot-0 placement records carry types 24–73, i.e. all dispatch to that handler.
  `0x4A706` has 8 xrefs, all READ; the sole write near it is `render_sprites`' global
  scroll delta. Because both the spawn and the motion write through address registers,
  no absolute-address search could ever have found them — the reason earlier passes
  kept coming up empty.
- The landing rebound `nVelY = 0xFE - nVelY`, transcribed literally; interpretation
  uncertain.
- `tile_probe_result` bits beyond `0x02/0x04/0x10/0x20/0x40/0x80`, and the `0x6F`
  intermediate mask in the probe routines.
- Four non-letter glyphs (`0x36 0x37 0x3A 0x3B`) in the name-entry grid, presumably
  END/DELETE controls.
- The order-list transpose of `0x1C` at the end of song 0 channel 0 (decodes
  consistently; musical result unverified).

### E. Housekeeping
- Orphaned-instruction regions at `0x492E6` (two ISR flag *bytes* mis-disassembled),
  `0x48F48`, `0x4DF86`+ (PCM data). Cosmetic.
- `analyze_function_completeness` / `analyze_global_completeness` never run — would
  replace the estimated coverage figure with a measured one.
- A 5th `LevelStartInfo`-adjacent pointer exists (the ending text). Whether the array
  is formally 5 entries or the 5th is separate data is unconfirmed.
- ~~`functions.md`/`entities.md` drift~~ — ✅ **fixed 2026-08-28**: both demoted to
  pure indexes, the globals table moved to `data-structures.md`, and an explicit
  **authority order** (Ghidra → `algo-*.md` → indexes) documented in `re/README.md`.

---

## 4. Proposed next tasks

1. **Render whole rooms.** Everything needed now exists — the tilemap encoding
   (`algo-level.md`), the block/tile graphics (`assets/`), and `RoomHeader`. Producing
   a PNG per room would validate the tilemap decode end-to-end and give a visual map
   of all 47 rooms. Cheapest remaining high-value item.
2. **Audio.** Render the PSG sequences and the three PCM samples to WAV using
   `algo-music.md`. Two samples are partly outside the capture (Gap B).
3. **Dynamic-verification pass** once Hatari is available — the Gap D list is short.
4. **Wider memory capture** — recovers the two truncated sound samples.
5. **Sweep for unreferenced sprite frames** — the 124 extracted are those reachable
   from animation tables; a linear sweep of the graphics blob would find any orphans.

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
| Asset extraction | 08-28 | 11 PNGs rendered and visually validated; sprite format found to be plane-major; font extent settled at 95 glyphs; `0x40FEE` identified as three banners |
| Index demotion | 08-28 | `functions.md`/`entities.md` demoted to indexes; globals moved to `data-structures.md`; authority order documented in `README.md` |
| KB review | 08-28 | Stale content purged; `sprite_type_dispatch` corrected to **74 entries**; `hide_entity` relocated to `0x4AC08`; `bullet_range_remaining` → `bullet_point_x/y`; `CheckpointState` axes fixed |
