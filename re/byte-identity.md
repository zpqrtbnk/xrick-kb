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

## Audit status — all planned audits complete

| # | Audit | Status |
|---|---|---|
| 5 | Struct-field access widths | ✅ **done — entity struct clean** |
| 6a | Literal transcription of `probe_player_tile_collision` | ✅ **done — 2 defects** |
| 6b | Literal transcription of `probe_entity_tile_collision` | ✅ **done — same shape, same tail asymmetry** |
| 7 | `dbcc` loop bounds | ✅ **done — 40 sites, 4 off-by-one prose defects fixed** |
| 8 | Sign-extension / immediate signedness | ✅ **done — 7 sites, exhaustive; 2 more defects fixed** |
| 9 | Instructions the decompiler hides | ✅ **done — only 4 indirect dispatches, all documented** |

**All nine planned audits are now complete: 15 defects found and fixed.** What remains
is not an audit but a *test*: build the reimplementation and diff its behaviour against
the live game using the Hatari harness (`hatari.md`). Static auditing has reached the
point of diminishing returns — the last three audits found 4 defects between them, all
in prose rather than in transcribed logic.

**Precedent for #8:** the music transpose was documented as
`note_period_table[b + transpose + 12]`, but the engine does `add.b` / `addi.b` / `ext.w`
— byte-width arithmetic that wraps mod 256, then *sign-extends*. Shipped songs use
negative transposes throughout (`-124, -12, -7, -5, -2`), so widened unsigned arithmetic
indexes far past the table. That defect was invisible in the C-like transcription and
only appeared when the instruction encodings were read.
