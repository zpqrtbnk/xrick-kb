# Byte-identity audit

The goal for the reimplementation is **mechanical, byte-for-byte correspondence with
the original** — not behavioural similarity. This document records the systematic
audits run against the knowledge base to find places where a faithful-looking
reimplementation would silently diverge, the defects they found, and the audits still
outstanding.

The method throughout is the same, and it is the important part: **derive the fact
from the binary mechanically, then diff against what the documents claim.** Reading
transcriptions to check transcriptions does not work — three of the four defects below
were invisible to that approach and were found by enumeration.

Audit scripts are throwaway; the reproducible part is the recipe in each section.

---

## Audit 1 — access widths of every documented global

**Method.** Parse the canonical globals table in `data-structures.md`; get every
xref to each address (Ghidra `get_bulk_xrefs`); decode the 68000 size field of the
instruction at each reference site from the raw bytes; compare the observed width set
against the documented type.

**Result: 33 globals checked, 6 defects.** Corrected 2026-08-29.

| Global | Documented | Actual | Consequence if unfixed |
|---|---|---|---|
| `0x495C8` `spawn_scan_flags` | word | **byte** (7/7 sites) | writes the wrong byte; `0x495C9` is unreferenced |
| `0x4BF1A` `dynamite_exploding` | byte | **word** (5/5) | wrong byte set; `0x4BF1B` unmanaged |
| `0x4BF28` `explosion_active` | byte | **word** (8/8) | as above |
| `0x4DE2C` return-to-attract | byte | **word** (3/3) | as above |
| `0x4BF2E` `player_touched_hazard` | byte | **word** (7/7) | `move.w #0xff` leaves `00 FF`, not `FF` |
| `0x4BE1C` `bcd_timer` | word | **word + `sbcd` byte chain** | a binary subtract is not a BCD subtract |

Two of these deserve more than a type change:

**`0x4BF18` `player_dying` is read at two different widths.** Eight sites use byte
(`clr.b`, `tst.b`, `move.b #0xff`), but `trigger_zone_update` at `0x4BEDC` uses
**`tst.w`**, which covers `0x4BF19` as well. `0x4BF19` has **no references anywhere in
the program** and reads `00` in every dump, so the word test behaves like a byte test —
but that is a property of the *data*, not of the code. Emit `tst.w` at that site.

**`0x4BE1C` `bcd_timer` is a BCD field, not a counter.** It is loaded and tested as a
word, but decremented by an **`sbcd` borrow chain** at `0x4BE54`/`0x4BE56` that walks
downward from `lea 0x4BE20,A1`, touching `0x4BE1F` then `0x4BE1E`. The field spans
`0x4BE1C`–`0x4BE1F`. Reproduce the `sbcd` chain; a binary `-= 1` gives different digits
the moment a borrow crosses a nibble.

## Audit 2 — is any global undocumented?

**Method.** Scan the code image for absolute-long effective addresses, collect every
target landing in the data range, and diff against every hex address mentioned anywhere
in the KB.

**Result: 189 distinct targets, 181 documented.** The 8 remainders are single-reference
scanner artifacts (consecutive addresses inside a data region misparsed as code). No
real undocumented global. ✅

## Audit 3 — signed vs unsigned comparisons

The concern: a C reimplementation naturally writes `<` on a `short`, which compiles to a
*signed* branch. Where the original uses `BCS`/`BCC`/`BHI`/`BLS`, that silently diverges.

**Method.** Census every conditional branch in the code image; isolate the
unsigned-only conditions; disassemble a sample to classify each in context.

**Result: the risk is smaller than the raw count suggests, but it exposes a bigger
one.** The unsigned conditions are dominated not by unsigned comparisons but by the
**carry-flag return convention** — `bsr` followed immediately by `bcc`/`bcs`. Every
sampled site (`0x4C176`, `0x4C716`, `0x4CA90`, `0x4D062`, `0x4D1D8`) was a flag return,
not a comparison.

### The 10 functions that return their result in the carry flag

Enumerated by finding every `bsr` whose next instruction is `bcc`/`bcs` (32 call sites):

| Address | Function | carry used | called ignoring carry |
|---|---|---|---|
| `0x4D9AA` | `entity_overlaps_player` | 6 | 0 |
| `0x4DA40` | `probe_entity_tile_collision` | 6 | **1** |
| `0x4D986` | `trigger_box_contains_point` | 5 | 0 |
| `0x4CD70` | `probe_player_tile_collision` | 5 | 0 |
| `0x4CC92` | `explosion_overlaps_entity` | 3 | 0 |
| `0x4CBF0` | `stick_attack_hits_entity` | 2 | 0 |
| `0x4CC10` | `bullet_hits_entity` | 2 | 0 |
| `0x4CCFC` | `bullet_hit_solid_test` | 1 | 0 |
| `0x4CC4C` | `entity_contains_point` | 1 | **1** |
| `0x4D8B0` | `entity_touches_hazard_or_block` | 1 | 0 |

⚠️ **`probe_entity_tile_collision` and `entity_contains_point` are called both ways.**
At some sites the carry is consumed; at others the call is made purely for its **global
side effect** (`tile_probe_result`, `player_collision_flags`). A reimplementation that
turns these into plain `bool` functions and drops the global write will break exactly
those call sites — and the failure will look like unrelated collision misbehaviour.

## Audit 6 — literal transcription of `probe_player_tile_collision` ✅ DONE

**Method.** Disassemble `0x4CD70`–`0x4D006` in full and transcribe every variant
instruction by instruction, rather than describing an equivalent.

**Result: the previous transcription was wrong in a way that changes behaviour.** It
presented one shape and stated "all four variants share the shape below". They do not.

| Variant | `(x+4)&7` | `y&4` | tiles/row | stride | rows | mask after | tail |
|---|---|---|---|---|---|---|---|
| A `0x4CDB4` | ≠0 | set | 3 | `0x1E` | **4** | row 3 | **yes** |
| B `0x4CE44` | ≠0 | clear | 3 | `0x1E` | **3** | row 2 | **yes** |
| C `0x4CEC4` | =0 | set | 2 | `0x1F` | **4** | row 3 | **no** |
| D `0x4CF24` | =0 | clear | 2 | `0x1F` | **3** | row 2 | **no** |

Two defects, the second serious:

1. **Row count varies with `y & 4`** (4 rows vs 3). The old prose mentioned this but the
   pseudocode showed only the 4-row form.
2. **The 2-wide variants have no tail.** The 3-wide variants end with
   `bclr #7,D0; bclr #1,D0; or.b D1,D0`; the 2-wide variants never write `D1` and
   execute none of it. **A reimplementation applying the documented tail
   unconditionally would clear ladder (`0x02`) and ladder-top (`0x80`) whenever the
   player sits exactly on an 8-pixel column boundary, where the original preserves
   them** — i.e. intermittent, position-dependent failure to grab ladders.

The literal transcription also yields the real semantics of the `D0`/`D1` split, which
the "OR every tile in the box" formulation structurally cannot express: in the 3-wide
case ladder is detected **only in the centre tile column** and ladder-top only in the
centre column of the bottom row, because the tail strips both bits from the outer
columns before merging the middle accumulator. `data-structures.md` is updated.

**Still open: `probe_entity_tile_collision` (`0x4DA40`)**, whose per-shape sequences at
`0x4DA7E`–`0x4DBB2` remain "outline only". Given what the player probe turned out to
hide, assume nothing about it.

## Audit 6b — literal transcription of `probe_entity_tile_collision` ✅ DONE

Disassembled `0x4DA40`–`0x4DC1E`. **Structurally identical to the player probe**, with
the same four variants, the same row counts, the same strides and the **same tail
asymmetry** (2-wide variants never write `D1` and omit `bclr #7`/`bclr #1`/`or D1,D0`).
Differences are only:

- no `clr.b ceiling_flag` on entry and **no crouch block**;
- no crouch/ceiling special case in the pushable-block test;
- results go to `tile_probe_mask` (`0x4DC28`) / `tile_probe_result` (`0x4DC29`) instead
  of `collision_mask` / `player_collision_flags`.

Also corrected while transcribing: the `A1` index expression had unbalanced parentheses
and described the tile map as `0x20` bytes **per column**; it is `0x20` bytes **per
row** (row-major), matching `algo-level.md`'s correction. And `x += 4` happens *before*
the index is computed, which the old formula obscured.

Both probes' block-bounds tests use **signed** `bge`/`blt`.

**Audit 4 is now closed** — there are no remaining deliberately-non-literal
transcriptions.

## Audit 5 — struct-field access widths ✅ DONE

**Method.** Same as Audit 1, for `(d16,An)` forms: scan the entity/player code, decode
each access's size and displacement, group by displacement, diff against the documented
entity struct.

**Result: the entity struct is clean — 29 fields observed, 0 defects.** Every field's
access width matches its documented type.

One addition: **displacement `+0x07` sees 4 byte-wide accesses** and is not a struct
field — it is the **low byte of `nPosY`**, written directly for the tile-grid snap
(`(lo & 0xF8) | 3`). That is arithmetically identical to the word form (`~7` = `0xFFF8`
leaves the high byte alone), but the access is byte-wide and should be emitted as such.

⚠️ **Methodological limit, worth recording.** Widening the scan to `A1`/`A2` produced 12
apparent "MIXED width" defects. **They are all false.** Small displacements alias across
different structs — `RoomHeader` is 14 bytes, `ObjectTypeDef` 16, plus path tables and
channel state — so `(0x4,A1)` is not `nPosX`. Verified: the long-width `(0x4,A1)` access
at `0x4D2D8` is `move.l (0x4,A1),D1; cmp.l #-1,D1`, walking a **path table with a `-1`
sentinel**. This audit is only sound when scoped to a register with known provenance
(`A0` = entity, by convention in the entity handlers). Do not "fix" anything from the
widened scan.

## Audit 8 — sign-extension / immediate signedness ✅ DONE

**Method.** Enumerate every `ext.w`/`ext.l` in the code image. Each one marks a value
deliberately widened **with sign** — precisely where a reimplementation using a wider
type, or an unsigned one, diverges.

**Result: only 7 sites program-wide**, all now accounted for.

| Site | What is widened | Status |
|---|---|---|
| `0x4C0CC`, `0x4C85C` | player `nVelY` (word) → long, then `lsl.l #8` | 8.8 fixed-point integration — already transcribed as `(i32)(i16)nVelY << 8` ✅ |
| `0x4D520`, `0x4D664` | entity `nVelY` (word) → long, then `lsl.l #8` | same, in `enemy_ai_update` ✅ |
| `0x45302` | `(note + transpose + 12)` byte → word | the transpose defect, **fixed** ✅ |
| `0x4542A` | channel `+0x17` byte → word, indexes `note_period_table` (`lea 0x2F0,PC` = `0x45720`) | **channel `+0x17` is a SIGNED byte** — corrected |
| `0x452A0` | signed byte → word index into the word table at `0x45B00` | same signed-index convention |

**Generalisation of the transpose finding:** the music engine's stored note index
(channel `+0x17`) and transpose (`+0x13`) are **signed bytes**, and *every* lookup
sign-extends before doubling into a word table. Both were documented as plain `byte`;
both are corrected. An unsigned reimplementation indexes far past `note_period_table`.

That only 7 sites exist is itself the useful result: sign-extension is rare in this
program, so this class of defect is now **exhaustively** closed rather than sampled.

## Audit 7 — `dbcc` loop bounds ✅ DONE

**Method.** Enumerate every `dbcc` in the code image, resolve each loop register's
initialiser by scanning backwards, and compare the implied `N+1` iteration count against
what the documents state.

**Result: 40 sites; 4 off-by-one defects in prose, all corrected.**

`dbf Dn` with `Dn = N` executes the body **N+1** times. The transcriptions' loop *form*
— `for (D = N; D >= 0; D--)` — is correct and does iterate `N+1` times. But the prose
and comments beside them stated the raw `N`:

| Site | Register init | Documented | Correct |
|---|---|---|---|
| `0x4DC8A` title wait | `move.w #0xAF` | "175-frame title wait" | **176** |
| `0x4DE10` game-over wait | `move.w #0x3C` | "up to 60 frames" | **61** |
| attract-mode prose | — | "175 frames each" | **176** |
| constants summary | — | "title wait 175; game-over 60" | **176 / 61** |

Two notes from the same sweep:

- **Three apparent `dbeq`/`dbpl` sites (`0x44EEC`, `0x45086`, `0x46F58`) are false
  positives** — their branch targets are *odd addresses*, impossible on a 68000, so they
  are data misparsed as code. Every genuine site is `dbf`/`dbra`.
- The name-entry loop at **`0x491E2`** reports "initialiser not found", which is exactly
  the documented quirk: `D3` is loaded from the string *inside* the loop, so there is no
  initialiser to find. Mechanical confirmation of the hand analysis.

## Audit 9 — instructions the decompiler hides ✅ DONE

The known error class: `lea`-loaded callbacks that the decompiler omitted entirely,
which caused a documented past mistake.

**Method.** Enumerate every register-indirect control transfer in the code image.

**Result: only 4 exist program-wide, and all 4 are correctly documented.** ✅

| Site | Dispatch | Documented as |
|---|---|---|
| `0x4B086` `jsr (A1)` | `sprite_type_dispatch[type-1]`, base `0x4AAE0`, stride 4 | ✅ including the **`type − 1` bias** |
| `0x4BF02` `jsr (A2)` | effect callback | ✅ the recovered A2 callbacks |
| `0x4D08E` `jsr (A2)` | effect callback | ✅ same |
| `0x4566C` `jmp (A0)` | `movea.l (0x10,A6),A0` — music channel coroutine resume | ✅ `+0x10` typed as **Coroutine resume pointer**, with all four state addresses listed |

The remaining 29 indirect-looking transfers are `jsr (abs).l` — ordinary direct calls.
So the hidden-callback class is **exhaustively closed**: there is nothing else dispatching
through a register anywhere in the program.

## Audit 10 — cross-check against an independent reversal ✅ DONE (2026-08-29)

**Method, and why it is a different instrument.** Audits 1–9 all derive facts from the
binary and diff them against our own documents. That cannot catch a fact we never
derived, nor a number we derived once and then copied. Audit 10 diffs our documents
against **a second, independent reverse-engineering of the same game** — the xrick C/SDL
port (`../xrick/re/`), reversed from the *PC* executable by someone else, decades ago,
with no shared method or tooling. Disagreement is then a signal that at least one side is
wrong.

**Caveat that shapes every conclusion:** the port's logic is PC-derived, so a difference
is three-ways ambiguous — genuine PC-vs-ST, port error, or our error. Only differences
that survive checking against the ST disassembly count as defects here.

**Result: ~20 facts corroborated, and defects found that nine prior audits had missed.**

| # | Defect | Class |
|---|---|---|
| 1 | Sprite grid swept only to `0x3BA9E`; the real extent is `0x3D62E` — **21 frames missing** | extraction |
| 2 | The extractor's `> 10% non-zero bytes` density filter silently discarded genuine sparse frames; "185 non-empty" was a filter artifact, never a frame count | extraction |
| 3 | `bTriggerFlags` bit `0x02` documented as "bullet passes through" — retracted; it has **two** readers (spawn-into-`sprite_list[0]` at `0x496B8`, bullet disposal at `0x4D204`) | prose |
| 4 | Bits `0x08`/`0x04` conflated as "always-lethal"; they are lethal-**while-triggered** vs lethal-**while-idle** | prose |
| 5 | `entities.md`: "the 3 sub-types per visual decompile identically" — they pass distinct AI modes | prose |
| 6 | `entities.md`: `probe_entity_tile_collision` "returns floor-type code" — it returns no register value | prose |
| 7 | `entities.md`: dispatch row labelled type **70**; it is type **74** (index 73) | prose |
| 8 | `entities.md`: `hide_entity` at `0x4ABF8`; it is at `0x4AC08` (`0x4ABF8` is dispatch index 70) | prose |
| 9 | `data-structures.md`: dispatch table "70 entries", "types 71–73 have no handler" — 74 entries, all types handled | prose |
| 10 | Ghidra plate `0x4DA40` still called `room_tile_map` "column-major" long after the docs were fixed to row-major | plate |
| 11 | `scroll_view_up`/`_down` renamed in Ghidra; three documents still said `scroll_room_left`/`_right` | naming |
| 12 | `0x4922B` was `joystick1_state` in some documents, `player_input_bitmask` in others | naming |
| 13 | `player_pos_x_copy`/`_y_copy` — misleading labels for `sprite_list[1].nPosX/.nPosY` | naming |
| 14 | `SpriteEntity.nSpawnX`'s player overload (`0x4A75A` = pre-move X) undocumented | omission |
| 15 | `0x4BF1C` "unnamed" in one document, `stick_debounce` in another | naming |
| 16 | Four "Unresolved" items already resolved elsewhere in the same or a neighbouring file | stale marker |

### Audit 10b — assumption sweep of the ST side (2026-08-30)

A second pass over `re/` itself, re-**deriving** every checkable claim instead of
re-reading it. Ten more defects, one of them consequential for a reimplementation.

| # | Defect | Impact |
|---|---|---|
| 17 | **`SpriteEntity.nVelY`'s gravity note was backwards** — it credited *living* enemies with `+0xC4` **and** a terminal clamp. Verified at instruction level, the four cases are: living player `+0x80` clamp `0x800` (`0x4C148`/`0x4C18C`), living enemy `+0x80` clamp `0x800` (`0x4D684`), dead player `+0x80` no clamp (`0x4C8A8`), dying enemy `+0xC4` no clamp (`0x4D532`) | **High** — a reimplementation reading that row gives every walking enemy 1.5× gravity |
| 18 | Title bitmap "32,000 bytes, `0x23FEE`–`0x2BB2D`" — wrong twice: `draw_title_picture` copies `0x400` × 8 longwords = **32,768**, and the stated range spans 31,552, matching neither | Medium |
| 19 | Sprite region "~`0x2C000`–`0x34000`, ~32 KB" — actually `0x2BFEE`–`0x3D62D`, **71,232 bytes**; understated by more than half | Medium |
| 20 | "`0x34000`–`0x40FED`, ~52 KB, largely zero" — the zero run actually starts at `0x3D62E` and is **entirely** zero (measured: 0 non-zero bytes in 14,784) | Low |
| 21 | `0x1BBFE`–`0x1D01D` still listed as "Not identified" in `memory_map.md` though `assets-manifest.md` had identified it as 161 scenery tiles | Low |
| 22 | `level_start_info` described as "20 bytes × 4 (+ a 5th intro pointer)"; it is `LevelStartInfo[5]` | Low |
| 23 | High-score row said "name text follows" after +4, implying +8; the name is at **+0x12**, behind 10 bytes of fixed decoration | Low |
| 24 | Title-bitmap row called the blob "still-unmapped" | Low |
| 25 | Two entity types still described as having an "untraced" A2 callback, though all four callbacks are tabulated in `data-structures.md` | Low |
| 26 | A sentence reading "the functions formerly called `scroll_view_up`/`_down` … have been renamed `scroll_view_up`/`_down`" — **self-inflicted**, by a blanket rename in audit 10 that also rewrote the historical mention | Low |

**Also promoted, by instruction census rather than argument:** `nAiTimerReload` (0x30)
and `bAiCooldown` (0x4A) from *likely* to **confirmed**, and `bUnk4B` from *unconfirmed*
to **confirmed unused** — `(0x4b,A0)` returns zero matches across all 4,608
instructions, so "untouched" is now measured, not assumed.

**The 171 KB data region is now gapless.** All ten regions re-measured: every size
matches its stated range, every region starts where the previous one ends, and the last
ends at `0x44BEE` — the first byte of code. Nothing in `0x1B01E`–`0x44BED` is
unaccounted for.

**The unreferenced-`ObjectTypeDef` question, closed by census.** Walking all 523 placement slots gives 70
distinct types, none outside 1–74. The four never placed are exactly 1, 2, 3 and 74 —
player, bullet, dynamite, decorative sprite — all spawned by code. No unused content,
no untraced path.

**Method note.** Every one of these had been read past repeatedly. They fell out in a
single pass once the rule changed from *read the claim* to *re-derive the claim*. Two
were arithmetic contradictions visible in the document itself (a stated range that did
not match its stated size), which no amount of re-reading had caught.

### Audit 10c — second assumption sweep (2026-08-30)

Ran the same re-derive-don't-re-read method again over the areas 10b had not touched.
**One missing fact, and a large body of claims that verified exactly.**

**The defect — an undocumented, load-bearing sentinel.** `sprite_list` is
`SpriteEntity[13]` at `0x4A702`, ending at `0x4AADD`; `sprite_type_dispatch` starts at
`0x4AAE0`. The 2 bytes between had been read as alignment padding. They are not: they
hold `FF FF`, a 14th `wType` word, and **all three list walkers terminate on it alone**
— `render_sprites` (`cmp.w #-0x1,D0w` @ `0x4B03E`), `clear_sprite_flags` (`0x4AC1E`),
`blit_backgrounds` (`0x4AC98`), each stepping `lea (0x4c,A0),A0`. **None uses a count of
13.** The word has no xrefs, so nothing sets it at runtime — it must be part of the
initial state. A reimplementation that allocates exactly 13 entries and relies on the
sentinel walks into the dispatch table. Now documented in `data-structures.md`; also
closes the slot-12 question in `xrick/re/xref.md`.

**Everything else checked out, exactly.** Recorded because "verified" is only meaningful
if the negative results are listed too:

| Claim | Result |
|---|---|
| `RoomHeader[47]` @ `0x47620` ends at `transition_tables` | exact |
| All 47 `pTileMap` inside `0x2101E`–`0x22FED`, distinct, first at `0x2101E` | exact; deltas 72–584 (packed variable-length) |
| All 47 `pTransitions` inside the transition-table region | exact |
| All 47 `pPlacements` inside `placement_table`, first at `0x481E4` | exact |
| `wTileBankVariant` ∈ {0, 1} | exact |
| `MusicTrackDescriptor[29]` type field all ∈ {0,1,2} | exact — validates `build_sndh.py::find_delta()`'s heuristic |
| The 3 type-2 descriptors carry the PCM pointers `0x4DF86` / `0x4FCF2` / `0x50DA8` | exact, and matches `memory_map.md`'s independent derivation; `0x50DA8` lies past the 320 KB snapshot, which is why the 1 MB capture was needed |
| `note_period_table` `0x0EEE` → `0x0020`, 84 entries, monotonic | exact |
| Font `byte[95][32]` @ `0x1B01E` ends exactly at the scenery block | exact |
| `level_start_info[5]` ends at `0x4B586` = `level_index` (9 xrefs), then code at `0x4B588` | exact — **independently confirms the 5-entry count**; 4 entries would leave 20 bytes unexplained |
| Palette @ `0x4DEE2`: 16 words, all valid `0x0RGB`, channels 0–7 | exact |
| All five level-intro texts, byte length to the `0xFE` terminator | all five exact (280 / 270 / 260 / 235 / 259) |
| `strings.md`'s own extraction script: 66 runs, 2 named false positives → 64 strings | reproduces exactly; `GAME`/`OVER` addresses correct (the regex's stray leading `p` is the tail of a `bra.w`) |
| **All 16 tile-attribute bit counts** across both LUTs | all 16 exact |
| Attribute exclusivity: only `0x60` and `0x82` are multi-bit | exact, both banks |
| Every tile has a non-zero classification | exact — zero zero-valued entries in either bank |

**Method note.** 10b found ten defects; 10c found one. That is the expected shape of a
converging audit, and the negative results above are the evidence that the remaining
surface was actually examined rather than skipped.

### Audit 10d — third assumption sweep (2026-08-30)

**No defects found in `re/`.** Three previously-unmeasured quantities were measured, one
open question closed, and one defect found in *the port*.

**Measured for the first time:**

| Quantity | Result |
|---|---|
| Dynamite fuse table `0x46BF2` | **17 entries**, terminator `0x46C36` |
| Dynamite explosion table `0x46C3E` | **10 entries**, terminator `0x46C66` |
| All 27 dynamite frame pointers | every one on the `0x150` sprite grid, indices **33–147** — an independent re-check of the 212-slot extent found in audit 10 |
| `TransitionWaypoint` census | **106 waypoints across 47 lists**, no runaways |

**The transition region now closes exactly**, which it never had before:
`106 × 10 + 47 × 2 = 1154` bytes `= 0x478B2`–`0x47D33`, ending precisely at
`object_type_defs`. This also *proves the sentinel is 2 bytes rather than a full 10-byte
record* — the arithmetic closes no other way — and leaves no room for an unaccounted
waypoint.

**Re-verified, unchanged:** the per-room placement walk really does give
**476 records + 47 terminators = 523**, walked room by room from
`RoomHeader.pPlacements` rather than taken on trust from the earlier note.

**A defect in the port, not in us** (`xref.md` -> *Settled*, connector count). The port's `map_connect` holds 107
connectors + 47 terminators = **154 records in an array it declares as
`MAP_NBR_CONNECT = 0x99` = 153**. Per-list counts match ours in **46 of 47 positions in
the same order** — which incidentally confirms the two projects' room orderings agree —
with the sole difference at list 17 (port 3, ours 2). Two independent arguments put us
right: our region arithmetic closes exactly, and **the port's own constant equals our
106 + 47**. So the surplus record overruns the port's own declaration.

**Method note.** This is what a converging audit looks like: 10 defects, then 1, then 0.
The value of this pass was not defect-finding but *quantification* — three numbers that
had never been measured, and a hard boundary that now confirms the transition table the
same way `placement_table` and `object_type_defs` were already confirmed.

### Audit 10e — fourth assumption sweep (2026-08-30)

Target: `ObjectTypeDef[75]`, the largest table never field-censused, plus the HUD
structs. **Two documentation defects, one new structural finding, one new open item.**

| # | Defect | Detail |
|---|---|---|
| 27 | **`anim_frame_table` range was wrong at both ends** | Doc said scripted-trap anim tables live in `0x46Dxx`–`0x46Fxx`. Measured: **`0x46C3A`–`0x4708A`** — below `0x46D00` *and* past `0x46FFF` into the `0x470xx` band the doc reserved for paths. The two ranges are adjacent (`path` = `0x47092`–`0x475BE`), not separated |
| 28 | **`wTriggerSound` census was 40 % complete** | Doc listed "0x14/0x15/0x18/0x19/0x1A/0x1B, plus 0x9A on entry 64". Actual: **ten consecutive values `0x13`–`0x1C`**, plus `0x9A` on **two** entries. Four values (`0x13`, `0x16`, `0x17`, `0x1C`) were missing and the `0x9A` count was wrong |

**New structural finding — types 67 and 68 share the dynamite explosion animation.**
Their `anim_frame_table` is `0x46C3A`: a **null longword followed by the entire
explosion table** `player_dynamite_update` uses at `0x46C3E`, terminator included. The
null entry 0 is precisely what `scripted_trap_update`'s "frame 0 is a one-time intro
frame, loop restarts at index 1" rule expects, and `gfx_data == 0` makes `render_sprites`
clear the draw-enable bit (`cmpa.l #0x0,A6` @ `0x4B106`). So these two trap types are
**invisible until triggered, then play the explosion**. This sharing is *why* the anim
range starts below the previously-claimed band — defect 27 and this finding are the same
fact seen from two directions.

**New open item — 26 undocumented bytes at `0x4B336`–`0x4B34F`.** Between `HudCounters`
(ends `0x4B335`) and `HudDirtyFlags` (starts `0x4B350`). Not blank: a regular `FF` +
seven `00` pattern at **stride 8**. No instruction references any address in the range
(operand searches for `0x0004b33…` return only the six score digits; `0x0004b34…`
returns nothing). Per `MEMORY.md` §8 an empty absolute search does not prove absence —
this may be register-indirect, as the slot-0 hazard was. **Recorded as unresolved, not
as padding.**

**Verified exact, no change:** every other `ObjectTypeDef` claim — entry 0, entries 2–3
and entry 74 all-zero; entry 1 and entries 4–21 hitbox 24×21 with no tables; entries
22–23 hitbox 0×0 with a 4×4 trigger box; `movement_path_table` range; 13 distinct
hitbox pairs with W 4–32 and both `(4,21)` and `(32,16)` present; entry 64's `0x9A`. Also
`HudCounters` and `HudDirtyFlags` are complete and correct as documented — all four
dirty flags including `bScore_dirty`, ending exactly at `init_hud_state` code.

**And it fed the port comparison** (`xref.md` -> *Settled*, trigger-sound table): the ten-value sound set confirms the
port author's guess of "10 of them", while showing his `- 0x14` index base is one too
high — the single `0x13` entity would read `WAV_ENTITY[-1]`.

### Audit 10f — fifth assumption sweep (2026-08-30)

Target: the **music engine tables**, the largest surface never mechanically checked.
`algo-music.md` and `data-structures.md` turned out to describe the *same three
addresses differently*, so the sweep began by adjudicating those from `play_music` and
`init_music_playback`. **Four defects, all in `data-structures.md`; `algo-music.md` was
right throughout.**

| # | Defect | Detail |
|---|---|---|
| 29 | **`MusicTrackDescriptor.nTrack_type` — types 0 and 2 were swapped** | Doc: "`2` = tracked/pattern music, other = one-shot sample". `play_music`'s dispatch (`cmpi.w #0x1,(A0)` @ `0x44CE0`, `cmpi.w #0x2` @ `0x44CE8`, fallthrough = 0) shows **`0` = song** (`jsr init_music_playback` @ `0x44D02`), **`1` = SFX**, **`2` = digi sample**. A reimplementation following the old text routes songs to the sampler and samples to the tracker |
| 30 | **`nParam_index` semantics wrong** | The `<<1` into `0x44FF0` applies to **type 2 only**, and `0x44FF0` is the **sample-rate table** (TACR/TADR), not `instrument_index_lookup`. Type 0's param is a song number (`×6`), type 1's an SFX index (`×13`, `mulu.w #0xd` @ `0x44D6C`) |
| 31 | **`0x46932` called a "per-channel instrument table"** | It is the **song table**: `n*6`, then three words read as offsets *relative to `0x46932`* giving each channel's stream (`0x4513E`–`0x45158`). Nine songs |
| 32 | **`0x46B66` called the "arpeggio/vibrato table"** | It is the **pitch-envelope segment table** (`lea (0x1780,PC),A0` @ `0x453E4`). Vibrato is separate, in `channel_coroutine_state_c` |

**Also sharpened:** `0x463CC` is the **instrument table at 10 bytes/entry** — proven by
the instrument-slot table `init_music_playback` builds at `0x450FD`, three runs of
`0,10,20,…,70` (`moveq 0xa,D1` @ `0x451B2`) — not merely "default instrument data".

**Two new hard boundaries, from a census of all 29 descriptors** (9 songs with params
exactly `0`–`8`; 17 SFX with params `0`–`18`; 3 samples, all param `0`):

- 9 songs ↔ the song table at `0x46932` being exactly `9 × 6` bytes;
- SFX indices reach 18, so the descriptor table needs **20** entries at 13 bytes:
  `0x46426 + 20 × 13 = 0x4652A` — **precisely the pattern-data base**, confirming both
  the stride and the count.

**Verified exact, no change:** every PC-relative target in `init_music_playback` lands
on an `algo-music.md` claim — channel states `0x45098`/`0x450BA`/`0x450DC` (stride
`0x22`), song table `0x46932`, instrument base `0x463CC`, instrument-slot table
`0x450FD` (3×8), song-active flag `0x45096`; and in `play_music`, voice state `0x4543C`
(stride `0x1A`) and the SFX table `0x46426`.

**Method note.** The trigger here was not a suspicious number but **two documents
disagreeing about one address**. That is a cheap, mechanical thing to scan for, and it
found four defects in a subsystem four previous sweeps had left alone.

### Audit 10g — sixth assumption sweep (2026-08-30)

**No defects in `re/`.** Two mechanical scans came back clean, one long-standing
placeholder was resolved, and one loosely-stated fact was made precise.

**Scan 1 — every `name`/`0xADDR` pair in `re/*.md` against Ghidra's symbol table.**
Five hits, **all false positives**: range notations of the form
`` `0x4D00C`/`0x4D020` … `destructible_pickup_16`/`17` `` where the regex paired the
first name with the last address. No document names a function at another function's
start address. *(This is the scan that would have caught the `hide_entity` `0x4ABF8`
error from audit 10 — it is now clean.)*

**Scan 2 — access widths of the 25 globals carrying a stated type.** Spot-verified six
across the range, every access in the program: `vblank_counter` (6 × byte),
`scroll_active` (6 × byte), `scroll_delta` (4 × word), `stick_attack_active`
(7 × word), `world_row_base` (10 × word), `furthest_level` (7 × word). All match.
`scroll_view_up`/`_down` were confirmed to do `subi.w #8` / `addi.w #8` on
`world_row_base` and `+8` / `−8` on `scroll_delta` — the −8/+8 note in
`data-structures.md` is exact.

**Resolved — `CheckpointState`'s four `DAT_…` placeholders.** The struct listed four
destination globals as raw Ghidra auto-names although all four are named elsewhere in
the same document: `0x4A750` = `sprite_list[1].nDirection`, `0x495CA` =
`world_row_base`, `0x4D00B` = `ceiling_flag`, `0x4BF14` = `player_crouching`. Layout
re-verified against `save_checkpoint_state` (six moves, word×4 + byte×2) and the struct
**ends exactly at `0x4BFC2`**, that function's first instruction — a hard boundary for
the 10-byte size. Also newly recorded: `restore_checkpoint_state` calls
`reset_player_state` **first**, then restores, then `spawn_player_entity` — an ordering
a reimplementation must preserve. No `DAT_` placeholders remain anywhere in `re/`.

**Made precise — what the `−0x2054` delta actually does.** Every document said the 1 MB
dump is "shifted by −0x2054" without saying what shifts. Measured:

- static data is **byte-identical** (font, sprite grid, `placement_table`,
  `object_type_defs`, `music_track_table` — 64-byte samples at five bases);
- stored **pointers** shift by exactly −0x2054 — `sprite_type_dispatch` **74/74**,
  `RoomHeader` pointer fields **141/141**;
- non-pointer struct fields are identical — `wTileBankVariant` **47/47**.

**Relocate pointers, not data.** A naive byte-diff shows the pointer tables as
"different", which is correct, not corruption — that is exactly what flagged
`sprite_type_dispatch` mid-check here before the cause was identified. Recorded in
`memory_map.md`.

### Audit 10h — seventh sweep: literal transcription check (2026-08-30)

A different instrument from 10b–10g. Those censused *tables*; this one compares
`algo-system.md`'s **transcriptions** against the disassembly instruction by instruction
— the surface I had flagged as remaining. Eight functions checked in full.

**Zero defects. One fidelity nuance recorded.**

| Function | Result |
|---|---|
| `seed_prng_state` `0x49574` | **exact**, including the derived constants. Recomputed independently: `0x09121967 << 8 = 0x12196700`; `D7.w := 0x6700`; `− 7 = 0x66F9`; `0x6700 ^ 0x66F9 = 0x01F9`. Final `prng_a = 0x121901F9`, `prng_b = 0x160566F9` — both as documented |
| `update_prng` `0x49596` | **exact** — `exg`, `rol.l #3`, `subq.w #7`, `eor.w`, and the store order (`prng_a` receives the *old* `prng_b`) |
| `draw_string_xy` `0x49446` | **exact**, including the `bclr #0,D0` subtlety where Z reflects the **old** bit. The stated formula `(x>>1)*8 + (x&1) + y*1280` is arithmetically identical to the code's `lsl#8 → copy → lsl#2 → add` |
| `draw_string` `0x49466` | **exact**, including the `bchg #0,D0` old-bit semantics and the `+8` step |
| `draw_glyph_string` `0x494AC` | **exact** — the `A1→A2` save/restore around the call, and the same `bchg` stepping applied to a pointer |
| `draw_glyph` `0x494E2` | behaviourally exact; see the nuance below |
| `set_palette` `0x4937C` | **exact** — 16 words to `0xFF8240` via `dbf` |
| `palette_fade_in` `0x49394` | **exact**, and notably it already captured that **`D4` does double duty** as both the blue threshold and the outer `dbf` counter (D2/D3 are decremented explicitly, D4 by the `dbf`). The "a component with target `T` is incremented on exactly `T` of the 8 steps" claim verifies: the increment fires when `T > D4` and `D4` runs 7→0 |

**The nuance — `draw_glyph` is unrolled, and the transcription is rolled.** The real
routine performs **seven** `lea (0xa0,A1),A1` advances for its eight rows (the eighth
needs none) and reads its **32nd byte with no post-increment** (`move.b (A4),(0x6,A1)`).
The rolled `for (row = 0; row < 8; row++) { …; A1 += 0xA0; }` therefore leaves A1 one
scanline further on and advances A4 32 times rather than 31. **Unobservable**: A4 is
restored from the stack and both callers reload A1 — `draw_string` recomputes it per
glyph, `draw_glyph_string` saves it in A2 across the call. Recorded at the function so a
reimplementer does not depend on A1's exit value.

**Method note.** This is the first sweep to test transcriptions rather than tables, and
it is markedly slower per claim — eight functions for one nuance, against whole tables
per defect in 10b–10f. It also came back essentially clean, which is the more useful
signal: the transcription pass that produced these documents was accurate at the
instruction level, and audits 6/6b/8 had already swept the two tile probes and the
signedness class. The remaining untested transcriptions are `algo-render.md`'s blitter
and `algo-music.md`'s sequence opcodes.

### Audit 10i — eighth sweep: `algo-music.md` sequence opcodes (2026-08-30)

The second of the two transcriptions flagged as untested. **Zero defects; two fidelity
notes, both about *why* a correct-looking C form is correct.**

**`process_sequence_command` `0x45342` — verified instruction by instruction.** Every
branch, every PC-relative target resolved: `lea (-0x255,PC)` → `0x450FD`
(instrument-slot table), `lea (0x1072,PC)` → `0x463CC` (instrument table). The opcode
map — `0x80`–`0x88` select instrument, `0xFF` end-of-pattern, `0x89`–`0xBF` mixer
nibble, `0xC2` return, else skip 3 — is exactly as transcribed.

**Note 1 — the transcription depends on an unstated precondition.** *Both* range tests
are **signed** (`cmp.b #-0x78; bgt` and `cmp.b #-0x40; bge`), and the unsigned C forms
(`<= 0x88`, `< 0xC0`) agree with them **only over `0x80`–`0xFF`**. A byte in
`0x00`–`0x7F` would take the mixer path in C but the 3-byte skip in the original. The
document annotated the *first* comparison as signed but not the second, and stated no
precondition.

It is safe, and I checked why rather than assuming: **every call site guards on bit 7.**
`advance_channel_sequence` does `tst.b (A0); bpl` before both `bsr`
(`0x452C0`→`0x452C2`, `0x452CE`→`0x452D0`), so `0x00`–`0x7F` are consumed as *notes*
and never reach the routine. Now recorded at the function, with the warning that calling
it from anywhere else re-opens the signedness question.

**Note 2 — the `0xC2` case is not a local return.** It is `beq.w 0x451D8`, a branch into
`init_music_playback`'s `rts` — a shared-tail optimisation. Behaviourally a return, so
the transcription is right, but control flow leaves the function. The same trick appears
at `0x45330` (`bne.w 0x451D8`).

**Assessment.** Both of the "hardest remaining" transcriptions have now been sampled at
instruction level (`algo-system.md`'s eight functions in 10h, the sequence opcodes here)
and **neither produced a defect** — only preconditions and control-flow idioms that were
true but unstated. Combined with audits 6/6b (the two tile probes, transcribed
literally) and 8 (signedness, swept exhaustively), the transcription layer is now
sampled across its hardest cases. `algo-render.md`'s blitter shift path remains the one
large untested transcription.

### Audit 10j — the three port-side hypotheses (S5, S6, S7), 2026-08-30

The last untested items in the comparison worksheet: three claims about the *port* that
could only be settled against our disassembly. **All three resolved; no defect in
`re/`, and one very strong corroboration.**

**S5 — "type-2 enemies use two different ladder-grab masks". FALSE for the ST.** The
port has `(x & 0x07) == 0x04` after a fall and `(x & 0x0e) == 0x04` from the ground.
`enemy_ai_update`'s two sites are **byte-identical instruction pairs** — `btst.l #0x3,D6`
(`08060003`) at `0x4D6B4` and `0x4D72C`, `andi.b #0x7,D5b` (`02050007`) at `0x4D6BC` and
`0x4D734`. One rule, both sites: accept ⟺ `(x & 8) == 0` OR `(x & 7) == 0`, then snap
`x = (x & 0xF0) | 4`. The asymmetry is port-side; the rule itself differs from both port
forms and the enemy x-snap is absent from the port. Now tabulated in `xref.md` ->
*Unadjudicated*.

**S6 — "the port's randomiser shape is a testable hypothesis". FALSE.** Ours is a real
two-longword PRNG (`update_prng` `0x49596`, verified exact in audit 10h), seeded to fixed
constants, with exactly **two callers** — `main_init_and_loop` `0x4DD3A` (per frame) and
`enemy_ai_update` `0x4D79E` (per decision) — and exactly **one** consumer of its output,
`move.b (0x495C7).l,D5b; andi.b #0x3` at `0x4D7A2`: a mode-2 enemy turns on a **1-in-4**
chance. The port's ad-hoc byte mixer picks a *direction* 1-in-2. Different generator,
consumption and decision rule. *One design point does agree:* both step a global
generator once per frame and consult it per decision.

**S7 — "the tile-probe asymmetry is the same subtlety seen from both sides". TRUE, and
exactly so.** The two sides express the masking completely differently — the port with
explicit per-column/per-row masks, we with `0x6F` on the accumulated upper rows plus the
3-wide-only `D0 &= ~0x80; D0 &= ~0x02; D0 |= D1` (centre column accumulated separately in
`D1`). Tabulating which of the 8 attribute bits can reach the result across
{upper,foot} × {outer,centre}: **all 32 cells agree.** The identical three-way
asymmetry — ladder-top only from the **centre column of the foot row**, one-way only
from the **foot row**, ladder only from the **centre column** — is exactly what forced
audits 6/6b to re-transcribe both probes literally after an "equivalent" formulation
broke ladder detection on 8-pixel boundaries.

**Why S7 matters more than the rest.** It is a non-obvious three-bit asymmetry, encoded
two entirely different ways, in two independent reversals of two different executables,
decades apart — and it matches cell for cell. Of everything in this comparison, it is
the strongest evidence that both sides have the tile probe right.

### Audit 10k — O6 resolved: the "unexplained" HUD region (2026-08-30)

**One defect, and it was mine from audit 10e.** The 26 bytes at `0x4B336`–`0x4B34F`,
filed as an open unknown with an `FF`-at-stride-8 pattern that "no instruction
references", are **four 8-byte HUD render buffers**:

| Buffer | Terminator | Contents | `lea` |
|---|---|---|---|
| `0x4B330`–`0x4B335` | `0x4B336` | score, 6 digits | `hud_update_score` @ `0x4B3C8` |
| `0x4B338`–`0x4B33D` | `0x4B33E` | bullets | `hud_update_bullets` @ `0x4B46C` |
| `0x4B340`–`0x4B345` | `0x4B346` | dynamite | `hud_update_dynamite` @ `0x4B4A0` |
| `0x4B348`–`0x4B34D` | `0x4B34E` | lives | `hud_update_lives` @ `0x4B4D4` |

The `FF`s are `draw_string` terminators. `draw_hud_count` (`0x4B4FC`) blanks six cells
with glyph `0x5E`, writes `D1` icon glyphs right-aligned, and calls `draw_string`. The
values are constant, which is why nothing writes them and why the region is identical
across both captures — a fact I had already measured and misread as evidence of mystery
rather than of constancy.

**The methodological failure is the real content here.** The claim "no instruction
references any address in the range" rested on an operand search for `0x0004b34…`.
Ghidra renders absolute operands **without leading zeros** — `lea (0x4b340).l, A0` — so
that query **could not have matched anything in the range**, whatever the truth. I
reported a negative from a search incapable of returning a positive, and then reasoned
from it (invoking the register-indirect precedent to explain an absence that was an
artifact of my own pattern).

`MEMORY.md` §8 now carries the rule: **when a search returns nothing, first prove the
search can find something** — run it against a case known to exist. Two earlier searches
in this same session had used the padded form successfully (`0x0004b33` did match
`(0x0004b330).l` where the operand happened to be rendered padded), which is exactly what
made the inconsistency invisible.

**Cost/benefit note.** This was solved statically in a few minutes by scanning the image
for longwords pointing into the range — three hits, all inside `hud_update_*`. The
planned Hatari watchpoint run would have found the same thing more slowly. Scan for
pointer constants *before* reaching for the emulator.

### Audit 10l — T2 and T3 (2026-08-31)

Two cheap static tasks from `PLAN.md`. **No defects; both questions closed, and one
search-methodology point worth keeping.**

**T2 — the bullet has one probe point, not two.** Complete xref set for
`0x4BF24`/`0x4BF26`: `player_controller` seeds it at the muzzle (`0x4C5AA`, `0x4C5C8`,
`0x4C5E8`); `player_bullet_update` steps it +/-8 (`0x4CA5E` read, `0x4CA9C` write); and
**both consumers read it unmodified** — `bullet_hits_entity` does
`move.w (0x4BF24),D1w` / `move.w (0x4BF26),D2w` straight into `entity_contains_point`
(`0x4CC1A`/`0x4CC20`), and `scripted_trap_update` does the same into
`trigger_box_contains_point` (`0x4D1EC`/`0x4D1F2`). No call site adjusts the point.

So the ST tests **trigger boxes at the bullet's leading edge**. The port's separate
centre point (`x + 0x0C`) has no ST counterpart; for *enemy* hits the two agree. The
difference is confined to trigger tests and is now state in `xrick/re/xref.md`.

**T3 — the third `0x19` is genuine, at two sites.** `0x4BE1A` carries
`subi.w #0x1` @ `0x4BE32`, `move.w #0x19` @ `0x4BE3C` (reload) and `move.w #0x19` @
`0x4BE84` (`effect_start_escape_timer`) — all word-wide. Combined with the byte store at
`0x4D574` and the word multiply at `0x497FE`, our three `25`s are **independent
instruction sites of differing widths**, not one reading copied into three documents.
The concern raised when the "25 cluster" was first noticed is disposed of.

**Methodology — the padded/unpadded trap, seen from the other side.** The first T3
search used `0x4be1a` and returned **zero**. That is the mirror of the O6 failure: there
Ghidra rendered the operands *unpadded* (`0x4b340`) and the padded query missed; here it
renders them *padded* (`(0x0004be1a).l`) and the unpadded query missed. **Neither prefix
form is reliable.** Search the bare hex substring (`4be1a`), which matches both — and,
per the rule now in `MEMORY.md` §8, validate the query against a case known to exist
before trusting a negative. Here `4be18` was used as the control and returned 7 hits.

### Audit 10m — T5, the entity-dispatch reconciliation (2026-08-31)

**No defect. The two "shapes" were the same partition written in different bases.**

The port's dispatch reads as "24 `ent_actf` entries, plus everything `>= 0x18` to
`e_them_t3_action`, plus `0x47` to `e_them_z_action`", against our 74 types. Aligning
the bases dissolves it: `0x10` = 16, `0x12` = 18, `0x16` = 22, **`0x18` = 24**. The
port's catch-all boundary is exactly where our shared `scripted_trap_update` run begins,
and every group below it maps one-to-one:

`0x01`→1 player · `0x02`→2 bullet · `0x03`→3 dynamite · `0x04`–`0x0F`→4–15 enemies
(4 banks × 3 modes both sides) · `0x10`–`0x11`→16–17 destructible pickups ·
`0x12`–`0x15`→18–21 treasures · `0x16`–`0x17`→22–23 trigger zones · `>= 0x18`→24–73 traps.

**One real divergence, and it is an implementation choice.** How a dying enemy is
marked:

- the port **rewrites the type** (`e_them_gozombie`: `n = 0x47`), routing the corpse to
  a dedicated handler;
- we set a **flag** — `kill_enemy` @ `0x4D87C` is `move.b #-0x1,(0x49,A0)`
  (`bDying = 0xFF`) and **never writes `wType`**; `enemy_ai_update` tests it at entry
  (`tst.b (0x49,A0)` @ `0x4D4F4`).

Verified by a program-wide operand search: the immediate `0x47` appears **nowhere** in
4,608 instructions. The negative was trusted only after validating the query form
against a control (`#0x13, D0w`, which returns its two expected hits in `kill_player`
and `kill_enemy`). Consequence: ST type 71 (= `0x47`) is an ordinary
`scripted_trap_update` entry — consistent with the placement census, which finds 71 used
as a normal trap type.

The remaining asymmetry is our **type 74** (`decorative_sprite_update`), which the port
lacks because it builds its map intro from `screen_imapsteps` rather than from entity
types — already recorded when the object-type table sizes were reconciled.

**Note on where this belongs.** The mapping is *correspondence*, so it went into
`xrick/re/xref.md` → *Entity type dispatch*, and the dispatch row left the
unadjudicated-differences table. Nothing changed in `re/` — our side was right
throughout; only the comparison was unreconciled.

**The structural finding.** Four of the six `algo-*.md` files ended with a block of
corrections the authoring fork had deliberately *not* applied — 26 items in total, none
ever processed. Defects 3–6 were sitting in those blocks, correctly identified, while the
wrong text stayed in the documents they corrected. **A correction parked in a leaf
document is invisible to every audit.** That is now a standing rule (`MEMORY.md` §8), and
all 26 items are applied or explicitly superseded.

**What this says about the "diminishing returns" judgement below.** It was wrong in one
specific way: static auditing had reached diminishing returns *against our own
documents*. It had not reached diminishing returns against an outside source. The nine
audits were all self-referential; the first genuinely external check found sixteen
problems in an afternoon, at zero emulator cost.

## Audit status — all planned audits complete

| # | Audit | Status |
|---|---|---|
| 5 | Struct-field access widths | ✅ **done — entity struct clean** |
| 6a | Literal transcription of `probe_player_tile_collision` | ✅ **done — 2 defects** |
| 6b | Literal transcription of `probe_entity_tile_collision` | ✅ **done — same shape, same tail asymmetry** |
| 7 | `dbcc` loop bounds | ✅ **done — 40 sites, 4 off-by-one prose defects fixed** |
| 8 | Sign-extension / immediate signedness | ✅ **done — 7 sites, exhaustive; 2 more defects fixed** |
| 9 | Instructions the decompiler hides | ✅ **done — only 4 indirect dispatches, all documented** |
| 10 | Cross-check against an independent reversal (the xrick port) | ✅ **done — ~20 facts corroborated, 16 defects fixed** |
| 10b | Assumption sweep: re-derive every checkable claim in `re/` | ✅ **done — 10 defects fixed, 3 fields promoted, region map closed** |
| 10c | Second sweep: tables, strings, palette, attribute LUTs | ✅ **done — 1 defect (the `0x4AADE` sentinel); ~16 claim groups verified exact** |
| 10d | Third sweep: fuse/explosion tables, transition + placement census | ✅ **done — 0 defects in `re/`; 4 quantities measured, transition region closed, 1 port defect found** |
| 10e | Fourth sweep: `ObjectTypeDef[75]` field census, HUD structs | ✅ **done — 2 defects, 1 structural finding, 1 new open item** |
| 10f | Fifth sweep: music engine tables, cross-document conflicts | ✅ **done — 4 defects, 2 new hard boundaries** |
| 10g | Sixth sweep: name/address scan, global widths, relocation model | ✅ **done — 0 defects; placeholders resolved, relocation model measured** |
| 10h | Seventh sweep: literal transcription check, `algo-system.md` (8 functions) | ✅ **done — 0 defects, 1 fidelity nuance** |
| 10i | Eighth sweep: `algo-music.md` sequence opcodes | ✅ **done — 0 defects, 2 fidelity notes** |
| 10j | S5/S6/S7 — the three port-side hypotheses | ✅ **done — 0 defects; S5 and S6 false, S7 an exact 32/32 match** |
| 10k | O6 — the "unexplained" `0x4B336`–`0x4B34F` region | ✅ **done — 1 defect (mine, from 10e); four HUD render buffers, solved statically** |
| 10l | T2 (bullet probe points) and T3 (the third `0x19`) | ✅ **done — 0 defects; both closed** |
| 10m | T5 — entity-dispatch reconciliation | ✅ **done — 0 defects; a base mismatch, not a shape mismatch** |
| 10n | T12/T13/T14/T16 — the assumption T-items | ✅ **done — 1 defect; all four claims promoted from assumed to measured** |

**All audits are complete: 50 defects found and fixed** (15 from audits 1–9, 16 from
audit 10, 10 from 10b, 1 from 10c, 0 from 10d, 2 from 10e, 4 from 10f, 1 from 10k, 1 from
10n). What remains is not an audit but a *test*: build the reimplementation and diff
its behaviour against the live game using the Hatari harness (`hatari.md`).

### Audit 10n — the assumption T-items (2026-08-31)

Prompted by the user's rule that **no assumption may sit in a document**: every one must
become a numbered task. Four were cleared by measurement rather than argument.

| Item | Was | Now |
|---|---|---|
| T12 `palette_fade_in` starts from black | inferred contract | **proven**: `0x00FF8240` is referenced by exactly 3 instructions (`set_palette` `0x49382`, fade-in `0x493AE`, fade-out `0x4940A`), `set_palette` has 1 caller; 8 of 9 fade-in sites pair with a fade-out in the same function, the 9th closes through `show_selection_menu` → `start_level` → `show_level_intro_screen` (fade-out `0x4B794`) |
| T13 screen bases | inferred from `draw_string` | **read**: `0x492EA` = `0x00078000`; `flip_screen_buffer` XORs bit 7 of `0x492EC`, giving `0x70000`/`0x78000` |
| T14 `hide_entity` dead | `get_xrefs_to` → none (blind to table dispatch) | **scanned**: `0x0004AC08` stored 0 times, against 50 for `0x0004D15C` and 1 for `0x0004B856` — query validated |
| T16 engine clean before SFX | unverified ordering claim | **traced**: first `play_music` after boot is track 5 (type 0) at `0x4DC62`, inside init, before the main loop; all 22 type-1/2 sites are gameplay-only |

**The one defect (#50): `assets-manifest.md` had the type-0 census wrong** — "subtunes 1–8
are the only type-0 tracks". Reading `nTrack_type` from all 29 records at `0x44F08` gives
**nine**: tracks `0`–`7` *and* `27` (0x1B), whose `nParam_index` = 8 is the ninth entry of
the 9×6 song table at `0x46932`. The stated 9-onward bug boundary is therefore not a clean
type split.

**Method lesson.** Two of these were negatives from queries that could not have found the
thing — the same class as the padded-operand trap. `get_xrefs_to` cannot see table
dispatch; a "nearest preceding literal" scan misreads `0x4B6FC` as `D0 = 0` when
`moveq #0,D0` is immediately overwritten by `move.w (0x4B586).l,D0`. **Validate the query
against a known-present control before trusting a negative** — now applied every time.

Static auditing against *our own documents* has reached the point of diminishing returns
— audits 7–9 found 4 defects between them, all in prose. Static auditing against an
*outside* source has not: audit 10 found 16 in one pass. Prefer external diffs over
further self-review.

**Precedent for #8:** the music transpose was documented as
`note_period_table[b + transpose + 12]`, but the engine does `add.b` / `addi.b` / `ext.w`
— byte-width arithmetic that wraps mod 256, then *sign-extends*. Shipped songs use
negative transposes throughout (`-124, -12, -7, -5, -2`), so widened unsigned arithmetic
indexes far past the table. That defect was invisible in the C-like transcription and
only appeared when the instruction encodings were read.
