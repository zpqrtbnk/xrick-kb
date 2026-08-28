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
| Knowledge base | 12 files in `re/`, ~6,000 lines |
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

**What is not yet in `re/`: the asset bytes.** Graphics, tilemaps and music data are
located and their formats documented, but nothing has been extracted or visually
validated. That is the bulk of the remaining distance to a working reimplementation,
and it is **deferred by decision**.

**Verdict: ~85% of a reimplementation spec.** The remaining 15% is almost entirely
asset extraction plus a short list of behavioural details wanting a live run.

---

## 3. Gap register

### A. Assets not extracted — *deferred by decision*
Formats and anchors are recorded and ready: sprite frames are **0x150 bytes = 21 rows
× 16 bytes, 4 interleaved bitplanes, transparency derived as `NOT(p0|p1|p2|p3)`
(colour 0), no stored mask**; frames cluster `0x2FC4E`–`0x334xx`; treasures at
`type*0x150 + 0x2F70E`; enemy banks `0xD20` stride (alt banks `0xA80`); tile graphics
`0x1D01E`/`0x1F01E`; tile bitmaps 16 bytes each at `0x22FEE`; title bitmap `0x23FEE`;
menu bitmap `0x40FEE`; font `0x1B01E` (32 bytes/glyph). Rendering a frame is also the
cheapest possible *validation* of these claims — none has been visually checked.

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

### C. Level loading
Unresolved and possibly moot. The only GEMDOS trap is `Super()`; there is no file
I/O in the snapshot. Either raw BIOS/XBIOS sector access (never searched for) or it
happened before the snapshot. All level data is already resident, so a
reimplementation may not need this at all.

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

1. **Asset extraction** (Gap A) — the single largest remaining piece, and now the only
   thing between the KB and a buildable reimplementation. Offline Python over
   `re/atari_ram.bin`: dump sprite frames, tiles, the font and the two full-screen
   bitmaps to PNG plus a manifest. Doubles as validation of every format claim.
   *Deferred by user decision; pick up when assets are wanted.*
2. ~~**Hunt the slot-0 block writer**~~ — ✅ **DONE 2026-08-28.** There is no block
   pusher; slot 0 is the scripted crusher/boulder hazard. See Gap D. Method note: the
   searches failed because the writes go through `A0`/`A1`, not absolute addresses —
   when an address-based hunt comes up empty, check whether the access is
   register-indirect before concluding the code is missing.
3. ~~**Reconcile `functions.md` / `entities.md`**~~ — ✅ **DONE 2026-08-28.** Demoted to
   indexes rather than reconciled: duplicated facts were the drift mechanism, so the
   fix was to remove the duplication, not to re-sync it. `functions.md` is now a
   133-row address→name→purpose→owning-document map (271→185 lines); `entities.md` is
   a type→handler map; the globals table moved to `data-structures.md` with six stale
   entries corrected.
4. **Dynamic-verification pass** once Hatari is available — the list (Gap D) is now
   short enough to batch in one session.
5. **Wider memory capture** — only to recover the two missing sound samples.

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
| Index demotion | 08-28 | `functions.md`/`entities.md` demoted to indexes; globals moved to `data-structures.md`; authority order documented in `README.md` |
| KB review | 08-28 | Stale content purged; `sprite_type_dispatch` corrected to **74 entries**; `hide_entity` relocated to `0x4AC08`; `bullet_range_remaining` → `bullet_point_x/y`; `CheckpointState` axes fixed |
