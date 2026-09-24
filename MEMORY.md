# Project Memory — Rick Dangerous (Atari ST) Reverse Engineering

Slow-changing knowledge about **the project itself**: what we are working on, the rules
we work under, decisions that are settled, and lessons that cost something to learn.

- Game knowledge lives in **`kb/`** (entry point: `kb/README.md`).
- Knowledge about **the pre-existing C/SDL port** lives in **`kb/xrick/`** (entry point:
  `kb/xrick/README.md`). See §9.
- Current status, open work and next steps live in **`PLAN.md`**.
- Nothing here should duplicate either. If a fact is about the *game*, it belongs in
  `kb/`; if it is about *where we are*, it belongs in `PLAN.md`.

---

## 1. Identity

| | |
|---|---|
| Game | Rick Dangerous (Core Design, 1989) |
| Platform | Atari ST, Motorola 68000 |
| Ghidra project | `ghidra.xrick` → single program `atari_ram.bin` |
| Primary artifact | `kb/atari_ram.bin` — 327,680-byte Hatari RAM snapshot. **Authoritative for every address in the knowledge base.** |
| Secondary artifact | `kb/atari_ram_1M.bin` — full 1 MB capture, used only as the source of the complete PCM samples |
| **PC artifact** | `kb/ibmpc_cs.bin` — 65,535-byte dump of the **IBM PC** build's code segment, in the Ghidra project as `x86:LE:16:Real Mode` at base `0000:0000`. Dense 8086 code in `0x0000`–`0x2FFF`. **Its offsets are exactly the `ASM nnnn` addresses in the xrick port's comments** (verified at `map_resetMarks`: `MOV CX,0x20B` = 523 marks, `ADD BX,5`, at the cited `0x0025`). This is what makes PC-vs-ST questions answerable — see `PLAN.md` T8 |
| **PC data segments** | `kb/ibmpc_ds1.bin` = segment **`0x179C`**, `kb/ibmpc_ds2.bin` = segment **`0x271D`**, both **shift 0** (a DS offset is a file offset directly). Bases were derived from content, not assumed: the hall of fame lands at `ds2:0x46A5`, matching the code's `MOV SI,0x46A5`, and `ds1[0xF810+k] == ds2[k]` over the 2031-byte overlap (98.4%). `0x179C` holds the map/level tables (`map_bnums` at `0x523A`), `0x271D` the score (`0x490E`, six ASCII digits), score deltas (`0x4916`+) and HOF. **The port's generated tables were extracted from the PC build** — `map_bnums` matches `ds1` byte for byte and is absent from `atari_ram.bin`. Both dumps carry unexplained `DUMP1`/`DUMP2` PSP-shaped strings at `0x5D`/`0x81` |
| Source build | `disks/chaos43/RICK.PRG` — the Chaos #43 compilation disk; the build the snapshot was taken from |
| **ST sprite pointers to port sprite numbers (T9 solved)** | ST animation tables hold **pointers**; the port holds **sprite numbers**. `index = (ST pointer - 0x2BE9E) / 0x150`, where `0x150` = `sizeof(sprite_t)` under `GFXST` (`U32[0x54]`). Derived from one anchor (the death-tumble table at `0x46BE6` vs the port's sprites `0x19`/`0x1A`), it then correctly predicted five further tables the port already used — walk `0x46BC2`, crawl `0x46BDA`, climb `0x46B9E`, box explosion `0x46C3E`, dynamite fuse `0x46BF2`. Every pointer in the region divides exactly. |

## 2. Hard rules

- **NEVER ASSUME ANYTHING — ALWAYS CHECK.** The first rule, added to `CLAUDE.md` on
  2026-08-29 at the user's explicit instruction after repeated violations. Before
  writing any claim, run the check that proves it: read the bytes, run the xref, list
  the files. Never write "verified"/"confirmed" unless the check actually ran; never
  state a count or address from memory or from another document; never call something
  unused, absent or safe to delete without a lookup. When two sources disagree, go to
  the disassembly rather than picking the more plausible one. If a check is
  impractical, say so and mark the claim unverified. **And on 2026-08-31 the user extended it:
  an assumption may not simply sit in a document marked "unverified" — every one must be
  promoted to a numbered `T` task in `PLAN.md` and the site annotated with its number.
  "Zero assumptions" means zero *untracked* assumptions.** The sweep that established
  this produced T11-T17; re-run it with the assumption-language regex in the work log
  before claiming the knowledge base is clean.

  **As of 2026-09-04 that sweep is clean: T11 was the last one, and it is measured.**
  Every assumption promoted to a T-item (T11-T17) is now resolved. Two of them turned out
  to contain their own defects — the T11 write-up wrongly claimed "every tempo figure"
  depended on the prescaler (music is VBL-driven; only the digi-sample rate depends on
  it), and T16's source passage had the type-0 track census wrong. **Check the claim that
  motivates a task, not just the task.**
- **T9 solved 2026-09-04: the `sni`->`sprbase` overload is a PC-only consequence of the
  PC's 8-byte `entdata_t` holding sprite *numbers* where the ST's 16-byte `ObjectTypeDef`
  holds *pointers*.** Not a behavioural divergence. When the two builds appear to differ
  structurally, check whether the data models differ before calling it a divergence.
- **Parsing C initialisers with a `\{([^{}]*)\}` regex counts brace pairs inside
  comments.** It made `ent_entdata` look like 76 records against a declared 74 — the same
  shape as the real `map_connect` bug — and I nearly reported a second instance. Stripping
  comments and tracking brace depth gives the true count, **74, exactly as declared**.
  Re-derive with a second method before reporting a defect that pattern-matches a known
  one. **And when a method is found unsound, re-run every earlier result that used it** —
  the same regex had produced the `map_connect` "overrun" on 2026-08-30, which stood for
  five days and got as far as a drafted upstream bug report before being retracted on
  2026-09-04. The table was correct all along; the phantom 154th record was a
  commented-out line the port's author had already removed.
- **Net result: not one difference found against the xrick port in this entire project
  turned out to be a port error.** All 17 T8 rows are genuine PC-vs-ST divergences, T9 is
  a data-model consequence, and the two "port defects" we thought we had — the connector
  overrun and the `ent_entdata` excess — were both our own miscounts. The remaining real
  port bugs are the ones the author flagged himself plus the `rndseed +2` pointer.
- **Correction, 2026-09-10: one of "the port's own bugs" wasn't the port's bug — it was
  ours.** A1/A6 (`review-log.md`) replaced the port's dynamite-fuse and box/bomb-explosion
  sprite numbers with ones derived from the ST's raw pointer tables, on the unchecked
  assumption that an ST-derived sprite-slot number can be used directly as a
  `dat_spritesST.c` array index. It can't past slot `0x37` — the array is permuted there
  (extraction order, not a bug in the array) — and the port's *original* numbers were
  already the correct array positions. The "fix" broke a working animation; user-reported
  (bomb fuse showing random sprites), confirmed by reading `dat_spritesST.c`'s own
  per-entry provenance comments, fixed with a generated `sprites_stnum_to_index[]` lookup
  (`sprites.h`/`src/dat_spritesST_stmap.c`) so any future ST-slot-derived number translates
  correctly instead of needing this rediscovered by hand. Both `e_bomb.c` and `e_box.c`
  corrected and re-documented; user confirmed fixed by playing it.
- **T1 was rescoped on 2026-09-04: no new reimplementation.** The task is to review and
  align the **existing xrick port** against `kb/` — data structures and variable widths
  first, then algorithms. Plan in `review-plan.md`; `PLAN.md` T1 points at it. Surface is
  ~7k lines of real logic; the rest is generated tables and SDL glue.
- **T1 ground rules set by the user 2026-09-04:** (a) target is **switchable** —
  `PLATFORM_ST` / `PLATFORM_PC`, both behaviours coexist, neither deleted; (b) **the
  licence question is closed** — the user holds the rights to the PC version; (c) **the
  port's comments are not evidence** — they record what its authors *believed* the PC did
  and may be wrong, so verify in Ghidra (`atari_ram.bin` ST, `ibmpc_cs.bin` PC); (d) the
  provenance of the generated `dat_*.c` tables is unknown and may need re-extracting from
  the ST binary.
- **Measured on the table question (2026-09-04):** the port's `map_marks` is
  **value-identical** to our `placement_table` (523/523 on every comparable field) and
  `map_connect` matches in all 47 lists — but `ent_entdata` `w`/`h` differ in 3 of 74
  entries (indices 3, 22, 23: ST `0/0`, port `24/21`). So the map data is common to both
  versions and the entity templates are not.

  **`atari_ram.bin` is trusted absolutely and needs no provenance check** — the user
  dumped it themselves from Hatari with the game running correctly (attested
  2026-08-31). Do not re-raise it as an assumption; the layer-2 LSD decompressor never
  needs to be reproduced for this purpose.
  **Violations that prompted this rule:** claiming "confirmed by an xref census" for
  `0x4BF12/13/15/1C` before running one (the census, once run, disproved the claim);
  nearly adding `*.gbf` to `.gitignore` on the assumption it was Ghidra scratch, when
  `git ls-files` shows those files are tracked database content.
- **This is a 68K assembly project.** We reverse-engineer to *documented assembly*.
  Never decompile to C; never call `decompile_function` or `force_decompile`. All
  analysis stays in the assembly domain. **Applies to RD1 *and* RD2, however it would be
  done** (Ghidra's decompiler, external tool, or our own). **Restated 2026-09-19 by the
  user** after a confusion between *disassembling* and *decompiling*: both games were
  written directly in assembly, so there is no C to recover and any C output is fiction.
  **Disassembling is fine — use Ghidra for it; never write our own disassembler.
  Ghidra's p-code (`get_function_pcode`) is also fine** (user, 2026-09-19): it is not C.
  Forbidden tools are those that emit C: `decompile_function`, `force_decompile`.
  (A short-lived 2026-09-19 note here saying Ghidra's decompiler was OK was a
  misunderstanding and is withdrawn.)
- The game is **pure assembly** — no p-code, no interpreter, no virtual machine.
- ~~**Never open, read or reference `ghidra.xrick2` / `xrick2-prg`.**~~ **REVERSED
  2026-09-19 at the user's explicit instruction.** `ghidra.xrick2` and `kb2/` are now the
  in-scope **Rick Dangerous 2** project — see §10. The old "untracked leftover" premise
  is gone (both are tracked in git since commit `b7f0a39`).
- Do not modify `CLAUDE.md` or `README.md`. **One authorised exception exists:** the
  "never assume" rule at the top of this section was added to `CLAUDE.md` on 2026-08-29
  on the user's explicit instruction. Do not revert it as a rule violation.

## 3. The target bar

`kb/` must be complete enough to **mechanically re-code the game with identical
behaviour** — byte-for-byte correspondence with the original, not behavioural
similarity. Every assessment of progress is made against that bar.

## 4. Repository layout

| Path | Purpose |
|---|---|
| `MEMORY.md` | This file — project-level memory |
| `PLAN.md` | Current state, open work, next steps |
| `kb/` | The knowledge base: all game knowledge, organised by topic |
| `ghidra.xrick/` | Ghidra project (the analysis) |
| `disks/` | Rick Dangerous disk images, incl. `chaos43/` |
| `attempt.0/`, `attempt.1/` | Abandoned earlier attempts, deliberately kept in place |
| `ghidra.xrick2/` | Ghidra project `xrick2-prg` — **Rick Dangerous 2**, in progress. See §10 |
| `kb2/` | Knowledge base for Rick Dangerous 2 (entry point `kb2/xrick2-ref.md`). See §10 |
| `xrick/` | **"The port"** — a clone of the xrick C/SDL clone (nested git repo). See §9 |
| `kb/xrick/` | Our knowledge base *about the port*, mirroring `kb/`'s structure |
| `hatari.sh`, `env.sh` | Emulator / environment helpers |

## 5. Where knowledge lives, and which layer wins

`kb/README.md` carries the full reading order. The authority order, which matters
whenever two documents disagree:

1. **Ghidra** (`ghidra.xrick`) — the only layer verified directly against bytes.
2. **`kb/algo-*.md`** — exact transcriptions; source of truth for *behaviour*.
   `kb/data-structures.md` and `kb/strings.md` are authoritative for *data*.
3. **Everything else** — `functions.md`, `entities.md`, `rick.md` are **indexes and
   narrative** and carry no derived detail by design.

Two overrides on top of that:

- For a **byte-identical** reimplementation, `kb/byte-identity.md` overrides the prose.
  The `algo-*.md` transcriptions are C-like and therefore lossy about operand *width*,
  *signedness* and *flag* semantics.
- **Do not add behavioural detail to an index file.** That layering was introduced
  2026-08-28 after `functions.md` and `entities.md` drifted three separate times by
  duplicating facts that lived elsewhere.

## 6. Provenance facts worth not rediscovering

- **The game only materialises in RAM.** `RICK.PRG` is a three-layer compressed
  executable (custom backward-LZ, an HPack trainer stub, then an LSD layer); the packed
  disk files contain no recognisable game code. All analysis is against the live dump.
- **The address base is not fixed.** Rick Dangerous is a GEMDOS program, so TOS chooses
  its load address. On the correct boot path the delta is **`-0x2054`**, which is also
  `atari_ram_1M.bin`'s offset from `atari_ram.bin`. Measure it every session; never
  hardcode it. `build_sndh.py::find_delta()` is canonical.
- **A RAM snapshot captures a *running* state, not a clean one.** Ours was taken with
  the title music mid-play. Code lifted out of it inherits whatever the program happened
  to be doing, so re-host it by calling the subsystem's own init/cleanup routines rather
  than trusting captured values.

## 7. Settled — do not re-open

| Question | Decision |
|---|---|
| Level loading at runtime | **There is none.** Two traps total (`Super`, `Setscreen`); all four levels resident. Do not re-search for GEMDOS/BIOS/XBIOS I/O — the answer is "absent", not "not yet found". |
| ASCII string search | Done — **64 strings** in `kb/strings.md`. Text is ASCII but **`0xFF`-terminated**; Ghidra's analyzer had *Require Null Termination* on. The old "text isn't ASCII" advice is **retracted**. |
| Slot-0 block pushing | **No such mechanic exists.** Slot 0 is the scripted crusher/boulder hazard, moved by `scripted_trap_update` through `A0`. |
| The missing 12,880 bytes | Recovered via `atari_ram_1M.bin`; was stack + PCM, never code. |
| Re-basing onto the 1 MB dump | **No.** `atari_ram.bin` numbering stays authoritative; convert with `1M_address = doc_address − 0x2054`. |
| Pixel-diffing rooms against Hatari | **No.** The user validates renders visually and has confirmed them correct. |
| Completeness metrics | `analyze_function_completeness` emits **no score at all** — it measures conformance to a plate-comment template this project deliberately does not use. Do not re-run it expecting a coverage number. |
| `disks/rd.st` | **Not the analysed build.** A Fuzion cracktro compilation with its own loader and a different, stage-dependent relocation. Boot `disks/chaos43/RICK.PRG`. |
| Trainer keys F1–F3 | **Leave off.** They patch game code and would invalidate any comparison against `algo-*.md`. |
| `attempt.0/`, `attempt.1/`, `disks/` | **Stay exactly where they are.** Do not move, archive or reorganise. |
| `ghidra.xrick2` | ~~Permanently out of scope~~ — **in scope since 2026-09-19** (Rick Dangerous 2, §10). |

## 8. Method lessons

- **Prefer disassembly over decompiler output.** Four documented errors came from
  trusting the decompiler: `RoomHeader.pPlacements` (+0xA, not +5); the `lea`-loaded A2
  effect callbacks it hid entirely; the `move.b #n,D0` AI-mode arguments it dropped as
  dead stores; and `probe_entity_tile_collision`'s carry-flag return read as a `D0` value.
- **Derive facts mechanically, then diff against the documents.** Reading transcriptions
  to check transcriptions does not work — most byte-identity defects were invisible to
  that approach and only appeared under enumeration of the raw encodings.
- **A disagreeing outside source finds what self-review cannot.** Nine byte-identity
  audits never noticed that the sprite sheet was 21 frames short; the port disagreeing
  about a count did, immediately. Where a second reversal exists, diff numbers against it
  before auditing prose again.
- **A correction written into a leaf document but never folded into the document it
  corrects is invisible.** Four of the six `algo-*.md` files ended with a block of
  corrections the authoring fork deliberately did not apply — 26 items in total. **None
  of the blocks was ever processed**, which is exactly how the wrong reading of
  `bTriggerFlags` bit `0x02` survived nine audits while the right one sat two sections
  away in the same file. **Never leave a correction in "to apply" state** — apply it to
  the owning document, or file it in `PLAN.md`. All 26 were swept on 2026-08-29 and the
  four blocks are now closed records, not to-do lists.
- **A rename applied in Ghidra but not in the documents is the same failure in reverse.**
  `scroll_view_up`/`scroll_view_down` had been renamed in the program while three
  documents still said `scroll_room_left`/`scroll_room_right`; `0x4922B` was
  `joystick1_state` in some files and `player_input_bitmask` in others. Ghidra is
  authoritative (§5), so **after any rename, sweep `kb/` for the old name.**
- **A fact corrected in the documents can still be stale in the Ghidra plate comments.**
  `room_tile_map` was fixed to row-major in `data-structures.md` long before the plate at
  `0x4DA40` stopped saying "column-major". Corrections propagate in both directions.
- **When two documents disagree about one bit, suspect two readers before suspecting an
  error.** Bit `0x02` genuinely has two unrelated consumers (`0x496B8` spawn routing,
  `0x4D204` bullet disposal); each document had found one of them and generalised.
- **Validate the query before trusting a negative result.** "No instruction references
  `0x4B336`–`0x4B34F`" was asserted from an operand search for `0x0004b34…`, but Ghidra
  renders absolute operands **without leading zeros** (`lea (0x4b340).l, A0`) — the
  pattern could not have matched whatever the truth was. The region turned out to be four
  HUD render buffers with four `lea`s pointing at them. **Both prefix forms fail
  somewhere**: Ghidra renders some absolute operands padded (`(0x0004be1a).l`) and others
  unpadded (`(0x4b340).l`), so `0x0004be1a` and `0x4be1a` each miss half the cases.
  **Search the bare hex substring** (`4be1a`), which matches both — and **when a search
  returns nothing, first prove the search can find something**: run it against a case you
  know exists. Both traps have now bitten once each, in opposite directions.
- **Fourth instance, 2026-09-04 (review of the port):** a scan for the ST tile banks used
  `range(0x1A000, 0x2C000, 32)`, which is 32-aligned to `0x1A000` — and `0x1D01E` is not
  congruent mod 32, so the sweep **never tested the documented bases**. It produced
  "20/256, the artwork does not match", which I reported. Testing the bases directly gives
  **256/256**. The rule is now sharper: **put the known-expected answer inside the search
  space and confirm the search finds it, before reporting any absence.**
- **Settled: the port's `dat_tilesST.c` is genuine ST artwork.** Bank 1 = ST `0x1D01E`,
  bank 2 = ST `0x1F01E` (both 256/256 exact), bank 0 = the font/HUD region at `0x1B01E`,
  all present but permuted — and the permutation is recorded in the port's own per-tile
  comments (`/* 0x11 */` = ST glyph 17). Port tile format is `U32[8]`, 8 pixels at 4bpp,
  leftmost pixel in the high nibble.
- **Beware filters in the extraction scripts, not just in the analysis.** The sprite
  sweep discarded genuine frames on a `> 10% non-zero bytes` heuristic, and the reported
  "185 frames" was that filter's output presented as a fact about the game. Any threshold
  in a tool becomes a claim in a document unless it is stated.
- **When sweeping for the end of a table, trim trailing blanks — do not stop at the
  first blank.** The sprite grid has a genuine interior gap at slot 127; stopping there
  truncates a 212-frame sheet to 127.
- **Cross-check structures against raw bytes.** The `SpriteEntity` X/Y axis swap and the
  `LevelStartInfo` 4-byte base error both survived multiple passes because prose was
  never checked against the table contents.
- **An empty address-based search does not mean the code is absent.** The slot-0 "block
  mover" was hunted for passes because both the spawn and the motion write through
  address registers. When a program-wide search for writes to a known global comes up
  empty, ask whether the access is register-indirect.
- **Beware tables cut short by spurious functions.** `sprite_type_dispatch` read as 70
  entries for several passes because a bogus function had been created inside it. The
  real count is 74.
- **Check analyzer options before concluding "absent".** The ASCII Strings analyzer's
  *Require Null Termination* default hid every string in the game.
- **Enumerating the readers of a global is decisive** in a way that reading
  transcriptions is not. Several probes that looked like they needed a live run fell to
  a Ghidra xref census instead.
- **Verify agent work before trusting reports.** Two of five forks in the multi-agent
  pass reported "done" after producing incoherent, self-referential output without doing
  any work; caught only by checking live Ghidra state. Both recovered when told plainly
  "you are not the orchestrator; do the work yourself; do not call Agent".
- **Never use Hatari's `:quiet` as a detector.** It suppresses per-hit output and the
  breakpoint listing has no hit counter, so a firing breakpoint looks identical to one
  that never fired. Use `:trace :once`.

## 9. "The port" — xrick, the prior C/SDL clone

Registered 2026-08-29. A second, independent reverse-engineering of Rick Dangerous
already exists: **xrick**, by "bigorno" (Arnaud Nolen), 1998–2005, re-coded in C on SDL.
It is cloned into `xrick/` (its own nested git repo, remote
`https://github.com/zpqrtbnk/xrick.git`, commit `c2aef3d`, version string `050500`).
Our analysis of it lives in `kb/xrick/` — 12 documents mirroring `kb/`'s structure, with
`kb/xrick/xref.md` as the comparison worksheet.

**As of 2026-09-22 (`PLAN.md` T41) the port is no longer RD1-only.** The goal is one
`xrick` executable that plays either game via a runtime `-rd [1|2]` flag. Its project
dir, `xrick/xrick/` (`include/`, `src/`), was split into a common platform layer (SDL
video/audio/input/arg-parsing, the vendored Atari-chip emulator) plus `include/rd1`,
`include/rd2`, `src/rd1`, `src/rd2`. RD1's whole engine and compiled-in data now live
under `rd1/`; `rd2/` is an empty placeholder — RD2's port (from `kb2/`, see §10) has not
started, and when it does it is a full implementation, not a data swap, because RD2's
engine is architecturally different (§10). Everything in this section (§9) still
describes **RD1's** analysis of the port specifically; it has no RD2 counterpart yet.

Facts worth not rediscovering:

- **The port's logic is PC-derived; only its artwork is Atari ST.** Every algorithm
  comment cites PC-style addresses (`ASM 12CA`, `ASM 0FBC`) in a `0x0000`–`0x2FFF` space;
  the build is configured `GFXST` for graphics only. A behavioural difference against our
  ST reversal may therefore be a genuine PC-vs-ST difference, a port error, **or ours** —
  three candidates, and none may be assumed. This governs every comparison.
- **Adjudicated: of 17 measured port-vs-ST differences, 15 are now settled against the
  PC code segment, and the port was right every time — zero port errors.** Fourteen are
  genuine PC-vs-ST divergences (Core Design changed constants per platform); one, the
  ceiling-bonk velocity, we had not even noticed. The remaining two — bomb blast box,
  submap re-entry X — need their routines located by structure, not by constant search.
  The practical lesson: **when the port disagrees with us on a constant, the prior should
  now be "the PC build differs", not "the port is wrong".** Our values were never the
  error.
- **`ibmpc_cs.bin` responds well to Ghidra's `run_analysis`** (74/75 functions from a raw
  segment dump). Identifying a routine by *structure* — masks, strides, the shape of the
  loop — is far more reliable than searching for a constant, because the same constant
  may not exist as a literal at all. `FUN_0000_11bc` = `u_envtest`, `FUN_0000_12bc` =
  `u_boxtest`, `FUN_0000_2089` = `ent_actvis`.
- **The port's `ASM nnnn` comments are offset by `+0x17E` over the code region** —
  confirmed on `u_envtest` (`103E`→`0x11BC`), `u_boxtest` (`113E`→`0x12BC`), `e_bomb_hit`
  (`11CD`→`0x134B`), `e_bomb_action` (`18CA`→`0x1A48`), `e_rick_gozombie`
  (`1851`→`0x19CF`). **Not global**: `map_resetMarks` (`0025`) sits at `0x0025` with no
  offset. Use it as a per-routine hypothesis, always confirmed by structure at the target.
  This is what finally closed T8 — it turns the comments into a lookup table.
- **T8 finished 17/17: every difference was a genuine PC-vs-ST divergence, zero port
  errors.** When the port disagrees with us on a constant, assume the builds differ.
- **The failed-query trap has now bitten four times.** Latest: searching `MOV AL,0xE2` and
  a byte store to absolute `0x7E80` for the submap re-entry X, when the real instruction is
  `C7 44 02 E2 00` — a **word** store through **`[SI+2]`**. Wrong operand width *and*
  wrong addressing mode at once. Before trusting any negative, ask what encodings the
  thing could plausibly have, and validate against a known-present control.
- **`ASM nnnn` comments do not map onto ST addresses.** No constant offset exists; they
  are different executables for different CPUs. Never try to translate them.
- **The port is a playable reconstruction, not a fidelity project.** It normalises struct
  layouts into C types, drops two entity fields as "never used", and its own comments
  admit it cannot explain several mechanisms. It discards exactly the width/signedness
  information that `kb/byte-identity.md` exists to capture.
- **The port had no sound engine — until 2026-09-10.** All audio used to be pre-rendered
  WAVs made by ear; there was no PSG data anywhere. **T19 (`kb/audio-sndh.md`) changed
  this**: `syssnd.c` now runs the actual lifted ST sound-engine code under real 68000
  emulation (Arnaud Carré's AtariAudio, vendored), the same bytes `kb/algo-music.md`
  and `kb/assets/audio/rick_dangerous.sndh` document. Every `WAV_*` symbol's ST track
  number is cited evidence (`kb/audio-sndh.md` §7), not guessed. Still true: this is the
  port *importing* `kb/`'s own extraction, not a second independent reading, so it
  does not cross-validate `algo-music.md` the way other port-vs-ST comparisons do.
- **It also has no timing model** — a 75 ms software-slept state machine, no VBlank, no
  interrupts. Per-frame *counts* are comparable; durations are not.
- **Licence is unsettled.** Source headers say "All rights reserved" and point at a
  README that carries no terms. Use the port as a reference for understanding only; do
  not copy its code into this project's output without settling this.
- **T20 (2026-09-10): the port's SDL dependency is now SDL3, not SDL2.** Verified SDL3
  exists and 3.4.16 is the latest release (cross-checked against the upstream GitHub
  releases page and vcpkg's `sdl3` port, independently agreeing). The WSL/Makefile
  build uses Debian's packaged **3.2.10**, not that latest — building 3.4.16 from
  source hit a missing `libxtst-dev` build dependency that needed interactive sudo
  this session couldn't supply; this is a real constraint, recorded rather than
  silently settled for. Full detail, including a real bug the migration introduced
  (an all-black window, fixed with one `SDL_SetTextureBlendMode` call, found only by
  the user actually looking at the running window): `kb/build.md`.
- **T21 (2026-09-10): the Windows/MSBuild path was actually built** (user's one-time
  permission for that task; the standing rule below is otherwise unchanged) — x64
  only now, outputs to `bin\<Config>\`, defaults to Release. Found a still-open,
  Windows-only rendering defect (scrolling glitches, sprite misalignment) not
  reproducible on WSL; a real texture-pitch bug was fixed along the way but
  confirmed not the cause. `kb/build.md` §2.
- **T22 (2026-09-10): the `-data` directory and zlib are both gone.** Every asset,
  including the sound engine (T19), was already compiled in; `-data`'s file-reading
  code had zero callers. `kb/build.md` §1.

Cross-validated (both sides independent): the 523-record placement table, 47 rooms, all
eight tile-attribute bits, all five common trigger bits, the enemy spawn-slot pools
9–11 / 4–8, the placement X/Y bit packing, the `-0x580` jump impulse, `+0x80` gravity
with a `0x800` clamp, the super-pad rebound `0xFE - vel`, bullet speed ±8, the 50/500/2000
score values, the 3-row room-transition window, the `0xCC` and `0xE8` thresholds, the
player hitbox vertically, and the dynamite `+4/+5` / `-4/-5` offsets with the
`(+0x0C, +0x0A)` explosion centre. The numeric pass is complete: **7 agree, 9
remain open, 1 was our defect.** Seven semantic questions are still open. Worksheet:
`kb/xrick/xref.md`.

- **A port comment saying "this is a fix for the ST version" may be describing the ST
  version faithfully.** The dynamite `+4/+5` spawn offset is written in the port as a
  `GFXST` fudge to compensate for ST sprite centring; the ST original performs exactly
  that offset, and its inverse at detonation. Read the port's *code*, not its
  rationalisations.
- **The nine surviving differences are all small integers in otherwise identical
  algorithms** (20 vs 25, `-0x400` vs `-0x300`, a 5 px blast edge, a 1 px hitbox shift).
  That pattern reads as two builds tuned differently, not as either side misreading. The
  one difference that did *not* fit — a count off by 27 — was ours.

**Two findings landed on our side and are fixed:** the sprite sheet was 21 frames short
(see §8), and `kb/data-structures.md` carried two conflicting readings of placement flag
bit `0x02`. The latter is resolved — **the bit has two unrelated readers**, which is why
two half-right descriptions coexisted: `spawn_level_entity` (`0x496B8`) routes the
placement into `sprite_list[0]`, and `scripted_trap_update` (`0x4D204`) picks the spent
bullet's disposal route. "Bullet passes through" is retracted; the bullet is consumed
either way.

---

## 10. Rick Dangerous 2 (registered 2026-09-19)

Two games, two reverse projects, one repo. **Do not mix their addresses** — RD1's are in
`atari_ram.bin` numbering, RD2's in `prg2-ram.bin` numbering.

| | Rick Dangerous 1 | Rick Dangerous 2 |
|---|---|---|
| Ghidra project | `ghidra.xrick` | `ghidra.xrick2` (`xrick2-prg`) |
| Knowledge base | `kb/` | `kb2/` (start at `kb2/xrick2-ref.md`) |
| Executable | `disks/chaos43/RICK.PRG` (93,326 B) | `disks/chaos43/RICK2.PRG` (140,202 B; md5 identical to `kb2/assets/RICK2.PRG`) |
| Status | **Complete.** Port lives in `xrick/xrick/{include,src}/rd1` | **Static+live reverse complete, port not started.** Target: `xrick/xrick/{include,src}/rd2` (same binary as RD1, see §9 and `PLAN.md` T41) |

- Both executables sit on the **same** disk, `chaos43`. `RICK_01`–`RICK_08.HNK` on it are
  RD2's level archives (RD1 has no runtime level loading, §7).
- The Ghidra project holds 7 programs (names read from the `.prp` files 2026-09-19; the
  `Ben Daglish` SNDH import has since been deleted): `GXUT275-rw.PRG`, `full_ram_dump.bin`,
  `prg2-ram.bin`, **`prg2-ram.bin.0` (the one the docs analyse; MCP name `prg2-ram.bin`, path
  `/prg2-ram.bin.0`, 68000, base 0, 1 MB, 151 functions)**, and `rick2_sfx.sndh` + `.0`/`.1`.
  `RICK2.PRG` itself is not imported — like RD1, the game code is analysed from a RAM dump.
- `kb2/` documents were written on a Mac (`/opt/homebrew` Hatari paths). On this Windows
  box, Hatari is `../atari/hatari-v2.6.1-488-g51ed999/hatari.exe` or `/usr/bin/hatari` in WSL.
- **Rules for RD2 (user decisions, 2026-09-19):** the "never assume" rule applies.
  **No decompiling to C, ever** (§2) — **`kb2/` was written partly from Ghidra decompiler
  output, so its decompiler-derived claims must be re-derived from disassembly**
  (`PLAN.md` T24 step 7). **Rendering is in scope, but only as far as an SDL port needs it**: extract the assets
  (sprites, tiles, palette) and understand how the screen is composed. Atari video-hardware
  details (bitplane tricks, shifter registers, blitter mechanics) are *not* a goal.
- **RD2 boot disk: available since 2026-09-19** — `disks/chaos43_noauto.st` (plus
  `chaos43_backup.msa`, `disks/tools/msa_convert.py`; untracked in git so far). Checked: FAT12
  walk shows every file identical to `disks/chaos43/`, `AUTO/MENU44.PRG` renamed `.DIS`. Boots
  in WSL Hatari 2.5.0 with **`kb2/hatari_rd2.py`** (`--disk-a`, `--auto A:\RICK2.PRG`, SPACE at
  the crack screen); the live RAM then equals `kb2/prg2-ram.bin` (main loop 100%, level image
  100%). Same address base as `prg2-ram.bin` — no relocation delta.
- Work items and next steps: `PLAN.md` **T24**.
- **The small `RICK_01/03/05/07.HNK` files are attract-mode demo input recordings, not level data**
  (loaded to `$3EFC0`; `(count, joystick-state)` pairs, count 0 = end; verified in the disassembly and
  live, `PLAN.md` T25). `RICK_05.HNK` (map 3's) is **junk** (`Rob Northen Comp…`, 512 B, no terminator).
  **HNK system rebuilt 2026-09-20 — read `kb2/hnk-system.md`** (user: the old `RICK_nn.bin` were model-made and possibly bogus; source of truth = the HNK files + the program). Summary: `.HNK` = LSD!-packed contiguous sector ranges of the
  original disk; per map the game has two descriptors (`$12dd4`): small = **demo input recording** (2 sectors, `(count, state)` pairs), large = **level image** (LSD! + the game's tree coder → 73 472 B at `$53400`); the program embeds a mini FAT12 file loader
  at `$7000` (`RICK_0<digit>.HNK`, digit picked from the descriptor's END sector at `$11f86`, only 8 values accepted = **4 maps**). `hnk.depack` == the raw sectors of the original-disk image `disks/RICKDA2/RD2` for 7 of 8 files (independent proof);
  `RICK_05.HNK` = crack error (512 wrong bytes), the real map-3 demo is `RD2[7680:8704]`. Files now: `kb2/assets/maps/map<N>_{demo,level_stage1,level}.bin` (generated by `kb2/extract_hnk.py`; `kb2/verify_hnk.py` re-checks; `kb2/extract_all.py` runs everything).
  **Settled 2026-09-22 by the user (direct knowledge of the original boxed release): the game has 4 maps, full stop.** "Level 5" (the "COMPLETE ALL 5 LEVELS" message after map 4, and the matching `game_main`/picker code) is a **tease for a future game**, never a real or cut level — not on this disk, not on the original. Consistently, the loader's fixed `RICK_0?.HNK` naming (only the last digit patched) and its 8-entry end-sector table cap addressable files at `RICK_01`..`RICK_08.HNK`, so the tease could never have loaded anything even if reached (`$11fb8`, infinite loop). **Port ships 4 maps** (`kb2/hnk-system.md` §7, `PLAN.md` T28, CLOSED). The old `kb2/assets/levels/RICK_0N.bin` and `orig/` are deleted (`kb2/assets/README.md` still describes them — it is a README, not edited without permission).
- Ghidra edits 2026-09-19 (user go-ahead): `main_loop_body` (mis-aligned at `$10a90`) replaced by
  **`game_main` `$10992`–`$10c27`** with labels `level_start` `$10a30`, **`frame_loop` `$10a54`** (per frame);
  `load_map_if_changed` is now `$123b0` (the old `$12394` "function" was on `0xFF` data — deleted).
  Program now 159 functions (10 auto-created as a side effect, unreviewed). Details: `PLAN.md` T24
  "Second pass". Poking `$1239c` from outside does not force a map; `kb2/hatari_rd2.py` uses breakpoints
  at `$10a36`/`$10a3c` (in `level_start`) instead.
- **Graphics (2026-09-19)**: screen 320×200 4-plane ST low-res; playfield 256×192 at (32,8); tiles 8×8 40 B
  (4 plane bytes + 1 extra byte per row, 256 per map, in the level image at `0x4900`); sprites 32×21 336 B
  (4 longword planes per row, transparency = colour 0), 4 banks (2 shared in RAM `$37274`/`$3a844`, 2 in the level
  image at `0x7600`). Extracted by `kb2/extract_gfx.py`; formats and open points: `kb2/graphics.md`, `PLAN.md`
  T26. **Level layouts are extracted too** (submap headers at image `0x1800` → block maps `0x3000` → 4×4-tile blocks
  `0x3900` → tiles; `kb2/extract_levels.py`, verified 40/40 rows against live RAM on all 4 maps).
- **Trigger/spawn/monster tables extracted (2026-09-19)**: `kb2/level-tables.md`, `kb2/extract_tables.py`. Chain check
  over all 58 submaps exact; 106 triggers, 769 spawn records, monster types 49/43/50/68. Scripts decoded
  (`kb2/decode_scripts.py`, 420 scripts + 4 in-program) and actor update / trigger boxes transcribed: `kb2/algo-actors.md`;
  player controller `kb2/algo-player.md` (full, incl. the bomb §11). Palette = table at `$18ee6` (one for all maps; a grey second palette at `$18f06` toggles with SPACE on the title). Checkpoint: `PLAN.md` T27.
- **Static transcription complete for maps 1–4 (2026-09-20)**: `kb2/algo-player.md` (Rick + bomb), `kb2/algo-objects.md` (4-slot object table), `kb2/algo-actors.md` (6-slot actors, trigger boxes, collision probe),
  **`kb2/algo-flow.md`** (game_main state machine, title/attract, level picker, level start/respawn, map advance and endings, score/lives/bonus timer, submap transition, 5-actor group, hall of fame; **2 vblanks per frame**),
  `kb2/decode_scenes.py` → `assets/levels/scenes.json` (cut-scene scripts + their background images = glyph matrices of the font, `gfx/scene_map*_image*.png`), `kb2/hnk-system.md`. Sprite blit facts (`graphics.md` §4): `+$12 ≠ 0` = masked blitter (mask = tile extra byte, bitmap `$65800`), not a mirror; hit flash = silhouette.
  Open reads: T30–T33, T36–T38 (T28 CLOSED: 4 maps, no level 5 ever); live-run gaps #3/#4/#7 parked.
- **All static reverse-engineering CLOSED 2026-09-22** (`PLAN.md` T26/T27/T30–T33/T37/T38, `kb2/PORTING.md` rewritten): text/glyph blitter (`$19272`/`$1925a`) and `$194ce`'s 4 UI banners fully decoded and
  extracted to PNG (`gfx/banner_*.png` — "CONGRATULATIONS!"/"HALL OF FAME"/"SELECT LEVEL"/"LOADING..."); demo-input bit mapping confirmed identical to live input; the submap-transition slide blits and the
  160-byte-pitch background/mask builder (`$188d0`) read; `$1a5d0` = direct YM2149 silence; the tile-window's `w1÷4+6` header formula proved to always leave 6 rows of scroll margin (closes the old "read past
  a submap's end?" question); who rewrites palette colour 1 = nobody (only the STE-only spare bit, not a runtime effect); which HUD slot draws which icon = ammo/bolt, bombs/bullet, lives/Rick's-head, all on
  HUD row 0.
- **Live validation CLOSED 2026-09-22, same day, user lifted "no live run for now"** (`PLAN.md` T27, `kb2/hatari_live_validate.py`, evidence in `kb2/assets/live_validation_2026-09-22.json`): forced maps 2/3/4
  in real attract-mode play and confirmed live all four remaining kb2 gaps — **#3** monster-descriptor path (type `<0x75`) fires (spawn-bit flips on real low-type records, all 3 maps); **#4** `dispatch_spawn_record`'s
  trigger-path branch (`b2` bit7 clear) fires (map 2 type 122, map 4 types 26/3); **#7** every live collision-probe byte (120 samples, values `0x00,02,03,06,07,08,0a,1c,1f`) decomposes into the documented bits,
  zero exceptions; **#5** 20/21 live actor script pointers land exactly on a decoded script boundary. Engineering note: chaining 250 one-shot breakpoints at the same address with instant rearm crashed the
  emulated 68000 (bus-error fault loop) twice; spacing rearms to every 15th hit fixed it. **Rick Dangerous 2's reverse-engineering — logic, data, rendering, sound, static and live — is now complete.**
  Remaining, all low-priority/parked, none blocking: **T39** (shared sprite bank storage location pre-unpack), **T36** (RICK_05.HNK's corruption — a Copylock-weak-sector hypothesis, unprovable without the
  physical disk), and one unexplained live sample (map 2, actor kind 89).
- Ghidra MCP: connected, `prg2-ram.bin` open (2026-09-19). Pass `program: "prg2-ram.bin"`.
  `list_globals` / `list_data_items_by_xrefs` returned **nothing** although `get_xrefs_to` works
  (a known unreliability, `kb2/xrick2-ref.md`) — use xrefs, not those listings. `ghidra.xrick2/
  xrick2-prg.lock` was removed; `.lock~` is held by the running Ghidra and goes when it closes.
- **`RICK_05` / HNK state is UNSURE** (user, 2026-09-19): expect another cleanup phase around the
  HNK files before the level data can be trusted (`PLAN.md` T25, T24 step 3).
- **2026-09-23 — RD2 gap closure (porting paused by the user until agreed).** Lessons worth keeping:
  - **A readiness check must enumerate callees, not read headers.** The 2026-09-22 "ready" verdict for the RD2 port was
    wrong: the collision probe, every hit test and many render/flow routines were only named or summarised in `kb2/`.
    Method that settles it: list every `jsr`/`bsr.w`/`bsr.b` target (`search_instructions` with the exact mnemonics;
    plain `bsr` matches nothing) and check each against the docs.
  - **`prg2-ram.bin` is a snapshot of the running game, not its start state.** The pristine program is `hnk.depack` of
    `RICK2.PRG`'s data section (= `FILE.DRS`), loaded so that RAM = offset + `$f8b8`. Graphics, font, banners, title and
    palette are identical, but the sound engine differs in 121 bytes of state, and the MFP table `$11606`, HUD counts,
    screen-pointer parity and PRNG were snapshot values. Several "in the image" statements in `kb2/` were snapshot artifacts.
  - **Ghidra leaves real code undecoded** (the boot code `$10000`–`$1010c`, parts of the scene runner). Use
    `disassemble_bytes(..., restrict_to_execute_memory=false)`, read raw bytes where it skips 2 bytes, and use
    `search_byte_patterns` on an absolute operand (validated on a known reference) — xrefs and `search_instructions`
    both missed a write at `$181c0`.
  - New docs: `kb2/algo-collision.md`, `kb2/algo-spawn.md`, `kb2/algo-render.md`, `kb2/algo-flow.md` §13,
    `kb2/sound-ref.md` §9. T39 closed. Port-side consequences: `port-rd2.md` §6.
- **2026-09-24 — RD2 port resumed on the RAM model** (`port-rd2.md` §7): emulated 1 MB big-endian RAM, pristine program
  at `$f8b8`, routines transliterated at their original addresses; map 5 literal (unlock row 5, red-border hang).
  - **"No caller" needs a byte scan of Ghidra's gaps.** `$144d6` was declared dead, yet `bsr.w $144d6` sits at `$123be`
    in bytes Ghidra skipped; PC-relative calls escape `search_byte_patterns` on the absolute target too. Method: take
    `find_code_gaps`, decode `61xx`/`6100 dddd`/`4eb9`/`4ef9`/`4eba`/`4efa` at every even address in each gap, resolve targets.
  - **Frame-exact verification against the original (P8)**: `kb2/hatari_rd2_trace.py` (Hatari, one-shot breakpoint chain
    at `$10a54`; re-arming at the current PC fires at once, so chain through `$10a5c`) vs the port's `RD2_TRACE` hook.
    Same RAM windows incl. both screens → byte-compare per frame. Map-1 attract demo: 2000 frames identical.
  - **Git Bash heredocs collapse `\n` in inline Python** (twice produced raw newlines inside C strings): edit such
    text with the Edit/Write tools instead.
  - **Status 2026-09-24**: RD2 is playable (`xrick -rd 2`, WSL and Windows); the user confirmed sound and keyboard
    by playing. **Verification and troubleshooting phase** now. RD2 carries rd1's host extras (PAUSED box, ESC =
    quit, E = end game, M/S numbers) as fb overlays and control handling, never in emulated RAM; cheats and
    F4–F6 are `PLAN.md` T42 (later).
  - **RAM-exact is not "works"** (2026-09-24): traces and `RD2_SHOT` read `fb`/RAM and ran `-nosound`, so a black window
    (host gamma 0) and a sound engine uploaded as zeros (init-order bug) both slipped through. Check the real window
    (Windows: `PrintWindow`, flag 2) and the audio (`SDL_AUDIO_DRIVER=disk`, `SDL_AUDIO_DISK_OUTPUT_FILE`, S16) too.
