> **File role: GAPS / OPEN QUESTIONS INDEX.** This is the single consolidated
> place for everything that's wrong, unverified, or missing across the Rick 2
> reverse-engineering effort. It does not contain new evidence or new
> conclusions — it only points at what's already in
> [xrick2-wk.md](xrick2-wk.md) (the evidence log) and, for current best-known
> facts, [xrick2-ref.md](xrick2-ref.md) (the topic index). Three sections:
> (A) contradictions found between sections of the docs, (B) conclusions
> that are hedged/inferred rather than directly proven, (C) genuine gaps —
> things not yet explored at all — grouped by subsystem. Nothing here was
> fixed or resolved as part of writing this file; it's a map of what still
> needs work, produced by a full read-through of both other files on
> 2026-09-15/16.

## Consolidated Remaining Gaps (2026-09-16 audit)

Single flat table merging every still-open item from sections B and C below
(plus a couple of housekeeping items surfaced by this pass) with a
priority/complexity call, judged against the porting goal (reproduce core
game logic — struct defs, spawn/AI tables — **not** sound/render). "Live"
means it needs a Hatari capture/watchpoint/trace; "Static" means it's
answerable from Ghidra alone (once tooling allows it). Rows are sorted
roughly by priority within each cluster; use the pointer column to jump to
full reasoning.

| # | Gap | Static/Live | Priority | Complexity | Pointer |
|---|---|---|---|---|---|
| 1 | True top-level caller of `main_loop_body`/`load_map_if_changed` never found — exhaustively checked (byte-pattern + instruction scan across all disassembled code), still unlocated | Static (deeper scan) or Live (breakpoint trace) | Medium | Large | B section n/a; C#7 |
| 2 | ~~Two Ghidra code-unit-boundary bugs (`func_0x00016474`, `func_0x000123a0`)~~ **RESOLVED 2026-09-16**: `GHIDRA_MCP_ALLOW_SCRIPTS` was enabled and the server restarted, unblocking `run_script_inline`. Fixed both with `clearListing()` + `disassemble()` + `createFunction()` at `$16474` and `$123a0`, then `save_program`. `func_0x00016474` now decompiles (calls `FUN_000165a6`/`FUN_000165fc` in a loop gated by `DAT_00016472 = DAT_00016462>>3 & 3`, still needs a proper name/purpose write-up). `func_0x000123a0` now decompiles cleanly as `g_current_map_number = g_map4_special_flag._0_2_; FUN_00017760();` — confirms the earlier static read of `move.w D1,$17994` and gives it real content for the first time. | Static | — | — (done) | C11, C33 (Map/submap + Input sections) |
| 3 | Live validation of the monster-descriptor-table path for type IDs `< 0x75` (`FUN_000146a0` branch) — fully decoded from static code, never exercised by any live sample (all 4 captured actors were `>= 0x75`) — CONFIRMED BLOCKED 2026-09-16: this MCP session has no Hatari/emulator tool of any kind (checked via tool search; only Ghidra MCP tools are exposed) | Live (need a map-2+ or later-map-1 capture with a low-type-ID enemy, in a session with Hatari tooling/access) | High | Medium | B6, C17 |
| 4 | Live validation of `dispatch_spawn_record`'s detail-block trigger path (`byte2&0x80==0` branch) — never fired against real data — CONFIRMED BLOCKED 2026-09-16, same reason as #3 (no live-capture tooling in this session) | Live | High | Medium | B7, C18 |
| 5 | Bulk-decode more of each level's spawn/trigger/script byte streams — only one 13-entry map-1 sample has ever been validated; maps 2-4 and the rest of map 1 are completely unsampled — CONFIRMED BLOCKED 2026-09-16, same reason as #3 | Live (need captures at other points in the game) | High | Large | C22 |
| 6 | Live confirmation of the map-1→map-2 HNK load (currently inferred from static descriptor-table dereferencing only) | Live | Medium | Small | Loader C#6 |
| 7 | `g_collision_result_flags` exact bit meanings — only partially inferred; document itself says a Hatari watchpoint on `$15f14` is the concrete next step — CONFIRMED BLOCKED 2026-09-16, same reason as #3 (no live-capture tooling in this session) | Live | High | Small | C25 |
| 8 | Whether unused trailing detail blocks on `byte2&0x80`-set spawn headers are read by any other code path, or are dead padding | Static (re-check) or Live | Low | Small | C19 |
| 9 | `extraout_A1` register-level provenance in `FUN_000146a0` — decompiler artifact strongly suspected but not provable in Ghidra's P-code; would need real 68000 disassembly Ghidra also fails to produce here | Static (needs a Ghidra fix, see #2) | Low | Medium | B5, C20 |
| 10 | `ActorRecord`'s remaining unnamed blobs (`nUnk04`, offsets 8-13 partial, `aUnk1c`, `aUnk24`) — confirmed static dead end; needs a live sample with active move/anim byte-code that happens to touch them | Live | Low | Medium | C16 |
| 11 | Whether `$65300` double-serves as the tile-ID map array and the `$1795c` depacker's packed-source staging buffer at different load stages, vs. being a separate reused scratch address | Static/Live | Low | Small | Loader C#5 follow-up |
| 12 | Rename `g_tile_attribute_map` in Ghidra to its corrected address `$65200` (currently still labeled at the old, wrong `$65300` in the live project even though the doc correction is made) | Static (mechanical rename) | Medium | Trivial | Player physics correction, see [xrick2-ref.md](xrick2-ref.md) §Player physics |
| 13 | `compute_tile_map_ptr`'s Y-term semantics (`(probe_y&~7)*4`) — narrow per-column row stride vs. indirect per-row descriptor table at `$65300`, not pinned down; low priority since the 33-byte pitch a port needs is already confirmed | Static | Low | Medium | C26 (remaining half) |
| 14 | Submap-trigger-table bytes 2-3 — "no reader found" is an absence-of-evidence conclusion dressed as closed; could still matter if a render-only consumer exists | Static (re-check) or Live (rendering trace) | Low | Small | B11, C14 |
| 15 | `g_player_wall_contact_flag`/`g_player_ceiling_blocked_flag`/`g_player_airborne_flag` — each "plausible," single call site, not independently confirmed | Static (more call sites) or Live | Medium | Small | B2-B4 |
| 16 | `nSpawn_anim_frame` (`ActorRecord+0x3e`) candidate name — usage elsewhere unconfirmed | Static/Live | Low | Small | B8 |
| 17 | `spawn_trigger_variant_c` naming ("shootable target trigger") — gating condition confirmed, but inference to game-object meaning not confirmed against real spawn-table data using this bit | Live | Low | Small | B9 |
| 18 | `ActorRecord+0x2f`/`+0x31` as alignment padding — strong absence-of-evidence case, not positive proof; a live byte-code stream that was never captured could still write these | Live | Low | Trivial | B10 |
| 19 | `DAT_00014854`'s 4-entry LUT per-type-category semantic meaning (external-reader question already closed; internal meaning still a guess) | Static | Low | Small | B14 |
| 20 | Map-specific stairs-variant flags (`_map2_flag`/`_map4_flag`) — confirmed to select animation-cycle length, but why maps 2/4 specifically need a different length was never chased | Live/curiosity | Low | Small | C27 |
| 21 | Top-level `.HNK`-load decision caller (who first decides "load `RICK_02.HNK` now") — sits further back than the traced instruction history could reach | Live (longer trace window) | Medium | Medium | Loader C#1 |
| 22 | Whether `RICK_03`-`RICK_08.HNK` ever load via the same loader routine (only the first two loads were observed in a ~45s window) | Live (longer capture window) | Medium | Small | Loader C#2 |
| 23 | `RICK.PRG` purpose (second, 93KB non-crack executable on the disk) — completely unexplored | Static | Low | Medium | Loader C#3 |
| 24 | Crack-screen "press a key" detection never traced end-to-end (only pattern-matched) | Static/Live | Low | Small | B1 |
| 25 | Live, on-screen confirmation of the "POOKY" cheat's behavior (mechanism fully decoded statically, never watched fire in-game) | Live | Low | Trivial | Input open items |
| 26 | New undecoded callees surfaced by the gap-#33 decode: `func_0x00018186`, `FUN_0001793a`, `FUN_00017e40`, `FUN_00017c86` (demo record/playback primitives + a render-adjacent effect) | Static | Low-Medium | Medium | Input open items |
| 27 | `FUN_00007282` — shared low-level sector-read primitive under the FAT12 loader — never explored | Static | Low | Small | Loader C#4 follow-up |
| 28 | Duplicate write-up of `FUN_00014434` in wk.md (two independent full decodes, same conclusion, second unaware of the first) — annotated in place this pass, no further action needed | — (housekeeping, done) | — | — | wk.md, both `FUN_00014434`/`func_0x00014434` headings |

**2026-09-16 tooling-blocker note**: a pass was made to actually resolve
items #2-5 and #7 above rather than just describe them. Item #2 was
diagnosed in full via `read_memory`/`disassemble_bytes` (dry-run at `$16474`
shows the disassembler skips `$16474`-`$16475` and resumes at the
pre-existing stray code unit `$16476`, confirming the conflict is a
code-unit lock, not a decoding ambiguity); the fix needed Ghidra scripting
(`run_script_inline`, gated by `GHIDRA_MCP_ALLOW_SCRIPTS`), which was unset
at first but the user then enabled it and restarted the Ghidra MCP server
mid-session — **item #2 is now fixed** (see its row above). Items #3-5 and
#7 all still require a live Hatari capture/watchpoint; this MCP session
exposes no Hatari or emulator-control tool at all (confirmed via tool
search), only the Ghidra MCP toolset, and enabling Ghidra scripting does not
change that. **Items #3, #4, #5, #7 remain environment-tooling blocked** —
the next agent needs a session with Hatari MCP/tool integration to attempt
these; nothing further can be done on them from Ghidra alone.

### 2026-09-18 correction: items #3, #4, #5, #6, #7, #21, #22 are NOT blocked

The note above concludes those items are "environment-tooling blocked — the
next agent needs a session with Hatari MCP/tool integration". **That is
wrong, and it has been costing this project real progress.** Hatari does not
need to be an MCP tool; it is a CLI binary and can be driven from Bash.
Verified working on 2026-09-18:

```sh
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy hatari \
  --tos /opt/homebrew/Cellar/hatari/2.6.1/Hatari.app/Contents/Resources/tos.img \
  --sound off --fast-boot on --fast-forward on \
  --disk-a disks/rd2.st --run-vbls 900 \
  --trace psg_write --trace-file psg.txt --log-file hat.log
```

This ran headless to completion in ~60 s and produced 24 398 trace lines.
Relevant capabilities, all confirmed present in Hatari 2.6.1:

- `--trace <flags>` with `cpu_all`, `mfp_all`, `psg_write`, `os_all`,
  `gemdos`, `int`, … — **every traced event carries a cycle count and the PC
  that caused it**, which is exactly the watchpoint substitute gaps #7 and
  #10 are waiting for.
- `--parse <file>` executes debugger command scripts (breakpoints, memory
  dumps, register reads) non-interactively.
- `--run-vbls <n>` gives deterministic, bounded runs — no interactive session
  to babysit, and no `--cmd-fifo` deadlock (caveat #31 does not apply).
- A usable `tos.img` ships with the Homebrew install, and `disks/rd2.st` is
  the real game.

So the live captures needed for #3 (type-`<0x75` descriptor path), #4
(`dispatch_spawn_record` trigger path), #5 (bulk spawn/trigger streams from
maps 2-4), #6 (map-1→map-2 HNK load), #7 (`g_collision_result_flags` bits),
#21/#22 (later HNK loads) are all reachable today, scriptably, from this
machine. Re-prioritise accordingly: these are the highest-value open items
and they are no longer waiting on anything.

**Not real gaps** (listed in C as caveats, not action items): tooling
caveats #29-31 (list_globals/get_xrefs_to unreliability, Ghidra
auto-analysis gaps, Hatari `--cmd-fifo` quirks — read before doing more RE,
not "open work"); #32 render/blit/sound-adjacent items, explicitly
out-of-scope by design.

---

## A. Contradictions found

Three real contradictions were found across the ~3500 lines of `xrick2-wk.md`
(a third was missed on the first pass and added after a verification re-check
on 2026-09-16). All three have now been annotated in place with `SUPERSEDED`
notes pointing at the correct/current section. Everything else that looked
at first like a contradiction (see "checked, not a contradiction" list
below) turned out to be either a self-corrected mistake (the author
explicitly flagged the fix in the same document) or a deliberate,
clearly-labeled dual meaning.

### A1. `ActorRecord` occupancy test: "`bState_flags` alone" vs. the real combined-word test

- **Older/wrong claim**: "Last two player flags named…" section (wk.md,
  originally ~line 2136-2143, now annotated) states free-slot scanners and
  `update_actor_slots` test occupancy by reading `bState_flags`/
  `bBehavior_flags` "to skip empty slots," implying `bState_flags` alone
  (or either byte alone) signals occupancy.
- **Correct/current claim**: "Spawn/trigger table decoded against a real
  data sample" → "Follow-up: live `g_actor_table` sample from the same
  dump" (wk.md, ~line 2290-2301) shows a live capture where all 4 active
  actor slots have `bState_flags == 0`, so `bState_flags` alone cannot be
  the occupancy signal. The actual, decompile-confirmed test is the
  **combined 16-bit word `bState_flags:bBehavior_flags != 0`**.
- **Status**: The later pass itself flagged this as a "cosmetic, not
  urgent" cleanup item ("Updated open follow-ups" item 4 in that section)
  but never went back and fixed the earlier wording — it stayed
  contradictory until this audit. Now annotated in place in wk.md with a
  `SUPERSEDED` note. **Use the combined-word test for any porting work.**
- **Why it matters for porting**: a naive port that checks a single byte
  for "is this actor slot alive" will silently treat live enemies as
  free/inactive slots (or vice versa) depending on which byte it picks.

### A2. `ActorRecord`'s "`0x1d`/`0x1e`" word-offset field vs. the byte-accurate `0x3a` field

- **Older/wrong claim**: "Enemy AI: a byte-code scripting VM per actor"
  section (wk.md, ~line 1280-1302) lists a struct row for "`0x1d`/`0x1e`
  (as seen from `query_tile_and_actor_collision`'s caller-side view):
  nearest-hit actor's recorded position fields," and its own prose
  explicitly flags this as unreconciled against the byte-offset reading
  used elsewhere in the same section.
- **Correct/current claim**: "Actor record struct, verified by
  disassembly" (wk.md, ~line 1336-1408) resolves this via raw 68000
  disassembly (unambiguous byte displacements): the field in question is
  actually byte offset **`0x3a`** (`move_delta_x`, later renamed from
  `prev_x`), confirmed via `move.w (0x3a,A0),(0x15f1a).l`. The "0x1d/0x1e"
  reading was a decompiler pointer-width artifact (the decompiler
  inconsistently treats the struct base as a `short*` vs. a byte pointer
  across different functions), not a real second interpretation of that
  memory range.
- **Status**: The document already flagged this as unreconciled at the
  time, and did reconcile it two sections later — but the original,
  since-superseded row was never itself annotated. Now annotated in place
  in wk.md with a `SUPERSEDED` note. **All `ActorRecord` work anywhere
  else in the document uses byte offsets and is consistent with the
  `0x3a` reading** — this was an isolated, self-identified, and
  since-resolved false lead, not a systemic byte/word confusion.
- **Why it matters for porting**: confirms the final `ActorRecord` layout
  (as summarized in xrick2-ref.md) is internally consistent and safe to
  use as-is; no further reconciliation work is needed here.

### A3. `g_enemy_spawn_table_ptr`'s address: `$144c8` vs. the disassembly-confirmed `$144c4`

- **Older/wrong claim**: "Game engine architecture" section (wk.md,
  ~line 925) and its Ghidra-annotations list (~line 1001) both name
  `g_enemy_spawn_table_ptr`'s address as `$144c8`, given without a
  disassembly citation — an early, never-verified guess.
- **Correct/current claim**: "`FUN_00014458` per-level loader decode"
  section (wk.md, ~line 3061-3099) derives the real storage cell directly
  from decompiled code — `PTR_DAT_000144c4`, i.e. address **`$144c4`** —
  and separately confirms it's genuinely named `g_enemy_spawn_table_ptr`
  via its reader `FUN_00014542`.
- **Status**: unlike A1/A2, this one was **never flagged as unreconciled
  anywhere in the original document** — the two addresses simply coexisted
  silently, four bytes apart, until this verification pass caught it. Now
  annotated in place in wk.md (both occurrences) with a `SUPERSEDED` note.
  `xrick2-ref.md` already used the correct `$144c4` throughout, so no
  correction was needed there.
- **Why it matters for porting**: a reader who lands on the earlier section
  first and reads no further could wire up the spawn-table pointer read at
  the wrong address — a 4-byte offset is easy to miss and would read
  garbage or an adjacent unrelated global.

### Checked, found NOT to be contradictions (called out explicitly per audit instructions)

- **`/prg2-ram.bin.0` Ghidra program naming.** Every single dated section
  in `xrick2-wk.md` that names the imported RAM-dump Ghidra program uses
  `/prg2-ram.bin.0` consistently, from the very first import (explained as
  a `.0` suffix forced by a stale duplicate import still open in the
  Ghidra GUI) straight through to the final 2026-09-15 sections. There is
  no later silent drop of the `.0` suffix — every reference retains it.
  `xrick2-ref.md` never refers to the Ghidra *program* name at all (only
  to the RAM-dump *file* `prg2-ram.bin`), so there's no cross-file
  inconsistency either. No annotation needed.
- **Detail-block `byte3`'s two meanings (monster-spawn vs.
  trigger/effect).** This is a real, deliberate dual meaning, but the
  document is careful about it: the discovery itself
  ("`FUN_00014a12` and `dispatch_spawn_record` decoded…", wk.md ~line
  3287-3361) explicitly calls out "This is a completely different *use*
  of the same byte3 bit-position than `FUN_000146a0`/`FUN_00014862`'s
  ‘spawn-type’ detail blocks… two different *kinds* of table entries
  walked by two different header branches (`byte2&0x80==0` →
  trigger/effect records via `dispatch_spawn_record`; `byte2&0x80!=0` →
  monster-spawn records via `FUN_00014636`)… Worth flagging explicitly in
  the struct/table docs so a future port doesn't conflate the two." No
  section anywhere blurs the two meanings into one. The new
  `xrick2-ref.md` keeps them in clearly separate subsections (see its
  "Spawn/trigger-table grammar" topic) specifically to preserve this.
- **`g_player_facing_dir` "ladder flag" mislabel** and **`_DAT_00012e2a`/
  `_DAT_00012e2c` "full-override movement flags" mislabel** (both in the
  "Stairs/ladder movement decoded" → "Correction: full decompile…"
  sections, wk.md ~line 1952-1988): both are self-corrected in place, in
  the same document, with an explicit "Correction" heading and an
  apology for the churn. No unmarked contradiction remains.
- **Open-follow-up numbering.** Numbered "Updated open follow-ups" lists
  recur roughly 20 times through the document, are renumbered per
  section, and reuse numbers (e.g. "item 7," "item 9," "item 13") for
  unrelated topics in different sections over time. This is confusing to
  navigate but is not a factual contradiction — every renumbering is
  local to its own section and the chronological, append-only structure
  makes each list's scope clear from its heading and date. This audit's
  main structural fix is exactly to stop relying on that numbering:
  section C below is the single flat, de-duplicated list that replaces
  it for porting purposes.

## B. Unverified / hedged assumptions

These are presented in the docs as best-current-understanding, but the
docs themselves hedge them ("likely," "plausible," "not yet confirmed,"
"candidate," "inference," etc.) or the evidence is one call site / one
live sample / structural-inference-only. Treat as **not yet safe to bake
into a port without a confirmation pass**, even though there's no reason
to think they're wrong.

1. **Crack-screen/intro keypress detection mechanism.** The
   `btst.b #7,($1a4fb)` / `cmpi.b #0x19,($1a4fc)` pattern in the
   `$18400`-`$18780` intro code region is inferred, not proven, to be the
   actual "press a key" detection for the crack screen and intro
   transitions. wk.md's very first "Next steps" list (item 3, ~line
   550-553) flags this as unconfirmed and it is never revisited or closed
   later in the document. Evidence: pattern-matches the expected idiom;
   missing: an actual traced call chain from the visible "press a key"
   prompt back to this code. → wk.md "What happens when the user presses
   a key" section, ~line 263-307.
2. **`g_player_wall_contact_flag` (`$12e24`).** "Plausible, not fully
   confirmed" per the document's own words — distinguished from
   `g_player_wall_push_flag` only by which branch sets it, with the exact
   semantic difference between the two not pinned down. → wk.md
   "Effects-slot corrected, four player flags named" section, ~line
   1852-1859.
3. **`g_player_ceiling_blocked_flag` (`$12e16`).** "Plausible, not
   independently confirmed — no second call site checked." → same
   section, ~line 1865-1870.
4. **`g_player_airborne_flag` (`$12e1c`).** Explicitly called "less
   certain than the previous three" — only one call site examined, and
   the surrounding code is more about scroll-delta bookkeeping than an
   obvious jump/fall test. → wk.md "Stairs/ladder movement decoded"
   section, ~line 1925-1934.
5. **`extraout_A1` == `pbVar5` (monster-descriptor pointer reused for
   alt script pointers).** Formally unresolved at the register level —
   three consecutive functions were traced and none of them write the
   register in question, which the document itself calls "a strong
   signal this is a decompiler register-tracking artifact… rather than
   real intentional data flow," and separately concludes the identity
   "by decompile-structure inference" (no code between two uses that
   could plausibly reload a different value) rather than by direct proof.
   → wk.md "Register-level trace of `FUN_000146a0`'s `extraout_A1`"
   (~line 2830-2868) and "`FUN_000146a0` fully decoded" (~line
   3106-3196, "Item 7" resolution).
6. **Monster-type descriptor table (`DAT_00053400`) format for type IDs
   `< 0x75`.** The whole `FUN_000146a0` default-branch descriptor lookup
   (width/height/behavior-flags/primary+alt script pointers, self-relative
   `int16` offsets) is decoded from static code only. Every live actor
   sample captured so far (4 actors, all `>= 0x75`) went through the
   *other*, simpler `FUN_00014862` path — this specific branch has never
   been exercised against real data. → wk.md "Live actors cross-checked
   against corrected spawn-table segmentation" (~line 2766-2803) and
   "Actor construction routines decoded" (~line 2628-2761, item 11).
7. **`dispatch_spawn_record`'s detail-block trigger path.** Same
   situation as #6 — fully decoded from code, never seen fire against a
   live sample (the 4 live actors all went through the `byte2&0x80`
   "self-as-header" branch, which never calls `dispatch_spawn_record` on
   their own detail blocks). → wk.md, same sections as #6.
8. **`nSpawn_anim_frame` candidate name (`ActorRecord+0x3e`).** Explicitly
   labeled "candidate name, unconfirmed usage elsewhere" — only confirmed
   as "a spawn-time copy of the initial `anim_frame` value," not
   confirmed to be read back by anything. → wk.md "`FUN_00014862` fully
   decoded" section, ~line 3197-3271.
9. **`spawn_trigger_variant_c` = "shootable target trigger."** The gating
   condition (`g_player_fire_cooldown` window) is concretely confirmed,
   but the function itself is deliberately left un-renamed because the
   inference from "fires within ~10 frames of firing" to "this is for
   shootable targets" is not confirmed against a concrete spawn-table
   data sample using this bit. → wk.md "Resolving the open follow-ups"
   section, ~line 1652-1665.
10. **`ActorRecord+0x2f`/`+0x31` as alignment padding.** Concluded "final"
    after checking every function reachable from the actor/object
    AI+construction call graph and finding zero accesses — a strong,
    carefully-built case, but it is still an absence-of-evidence
    conclusion, not a positive proof; a byte-code script data stream that
    was never captured live could in principle still write these. → wk.md
    "`FUN_000150c0` decoded" section, ~line 3438-3480.
11. **Submap-trigger-table bytes 2-3 as "unused or rendering-only."**
    Same absence-of-evidence pattern as #10 — every game-logic reader
    reachable from `check_submap_exit_triggers`/`FUN_00014434`/
    `FUN_00014458`/`FUN_00014542` was checked and none touch these bytes,
    but no positive confirmation (e.g. from a rendering routine) was
    ever obtained. → wk.md "Per-level table loader decoded" section,
    ~line 3017-3100.
12. ~~**`_DAT_000115dc` as vestigial/dead.**~~ **RESOLVED 2026-09-16**: it
    is neither vestigial nor dead. `main_loop_body` (`$10a90`) itself both
    writes it (reset to `0` once per outer-loop pass) and reads it (as its
    own inner-loop's `while` continuation condition) — `get_xrefs_to`
    missed both the write and the read because they're internal to that
    function, exactly the xref-indexing gap this entry itself predicted.
    It's `main_loop_body`'s inner-loop continuation flag, set non-zero by
    `dispatch_spawn_record`/`update_actor_ai` to abort/restart the current
    inner-loop pass. → wk.md "Gap-resolution pass…" section (2026-09-16),
    "Gap #9 resolved" subsection. Also see caveat #29 below — a fourth
    confirmed instance of the same tooling gap.
13. ~~**`ActorRecord+0x54`'s exact meaning**~~ **Correction, not new
    work**: this was already resolved in the pre-existing (pre-2026-09-16)
    `FUN_000150c0` write-up in wk.md, which explicitly states that
    `FUN_000150c0`'s read of the offset `0x29`/`0x2a` counter pair (for
    type-1 `g_object_table` oscillating movers) "confirm[s] that derived
    byte `0x54` value... is indeed this oscillation's period." The prior
    audit pass that produced this gaps file simply failed to cross-
    reference that existing resolution back here. **Not an open item.** →
    wk.md "`FUN_000150c0` decoded" section, ~line 3480-3484 (pre-existing),
    cross-referenced in "Gap-resolution pass…" (2026-09-16), "Gap #21"
    subsection.
14. **`DAT_00014854`'s 4-entry initial-frame lookup table** — contents
    and exact per-type-category meaning not decoded, called "low
    priority" and left as a guess. → wk.md same section, ~line 3268-3270.
    **Partially narrowed 2026-09-16**: `get_xrefs_to` confirms all 3
    references to this address are internal to `FUN_00014862` itself — no
    external reader exists. The "is there any other reader" half of this
    question is now closed (no); the per-type-category semantic meaning
    remains an open, low-priority guess.

## C. Genuine knowledge gaps

Grouped by subsystem, each a real "not yet explored" item, not a
disagreement or a hedge. Pointers are into `xrick2-wk.md` for evidence.
33 items total (plus 1 explicitly out-of-scope category, listed
separately at the end). **Updated 2026-09-16**: items #4, #5, #8, #9,
#10, #12, #13, #15, #21, #28 resolved this pass (struck through, with
resolution summaries and wk.md pointers inline); #11 partially resolved;
#7 and #14 re-confirmed still open with sharper next steps; one new item
(#33, the demo/attract-mode subsystem) surfaced and added.

### Loader / HNK pipeline (6)

1. **Top-level `.HNK`-load decision caller.** Whoever first decides "go
   load `RICK_02.HNK` now" and kicks off the sector read sits further
   back than a 200,000-instruction history buffer could reach (consumed
   entirely by the FDC busy-wait loop). Never found. → wk.md "Live trace:
   who calls the depacker" section, ~line 357-461.
2. **Whether `RICK_03.HNK`-`RICK_08.HNK` ever load via the same loader
   routine**, e.g. on later level transitions — no third load was
   observed in the ~45s window after the first two, and the window was
   never extended. → wk.md "Next steps" item 4, ~line 554-562.
3. **What `RICK.PRG`** (the other, 93KB non-crack-intro executable on the
   disk) **is for.** Its name never appears in any RAM dump captured so
   far; not investigated at all beyond noting its existence. → wk.md
   intro section, ~line 44-47, and "Next steps" item 5, ~line 563-565.
4. ~~**`$705e`/`$7136`**~~ **RESOLVED 2026-09-16**: `FUN_0000705e`
   decodes a boot-sector/BPB-style disk-geometry structure into working
   globals; `FUN_00007136` is a hand-rolled FAT12 directory-search +
   cluster-chain follower (8.3 filename match against a template, packed
   12-bit FAT entry decode with odd/even nibble handling, 0x400-byte
   cluster copy). The loader bypasses GEMDOS entirely with its own
   minimal FAT12 reader. `FUN_00007282` (shared low-level sector-read
   primitive both call) remains unexplored, low priority. → wk.md
   "Gap-resolution pass…" (2026-09-16), "Gap #4 resolved" subsection.
5. ~~**`$1795c`**~~ **RESOLVED 2026-09-16**: not a relocate/merge step —
   it's a **second, distinct depacker**, a Huffman-style bit-tree
   decoder (structurally different from `lz_depack_backward`), which
   decompresses the monster-descriptor table (`$53400`,
   `DAT_00053400`) from a packed form staged at `$65300`. Open follow-up:
   whether `$65300` doubles as `g_tile_attribute_map`'s buffer at a
   different point in the load sequence, or is a separate reused scratch
   address — not reconciled. → wk.md "Gap-resolution pass…" (2026-09-16),
   "Gap #5 resolved" subsection.
6. **Live confirmation of the map-1→map-2 HNK load.** The claim that
   finishing map 1 triggers `load_and_depack_hnk_file('3')`/`('4')` is
   derived entirely from static descriptor-table dereferencing, never
   confirmed by an actual in-game playthrough + breakpoint trace. → wk.md
   same list, item 6, ~line 751-754.

### Main loop dispatch (4)

7. **Who calls `main_loop_body` (`$10a90`) itself**, and who calls
   `load_map_if_changed` (`$12394`) each frame — the true VBL-synced
   top-level dispatcher has never been located. **Re-confirmed still
   open 2026-09-16**: both `get_function_callers` and `get_xrefs_to`
   return zero results for both addresses — consistent with (not
   resolving) the documented xref-indexing-gap tooling caveat (#29). A
   byte-pattern scan of the raw `.bin` for `bsr`/`jsr` operand encodings
   of these two addresses is the concrete next step, not yet attempted.
   → wk.md "Open follow-ups from this investigation" item 3, ~line
   741-743; "Gap-resolution pass…" (2026-09-16), "Gap #7" subsection.
   **Pursued further and re-confirmed blocked, 2026-09-16**: a
   `search_byte_patterns` for `JSR`-absolute-long encodings of both
   targets found nothing; `search_instructions` for `bsr` with either
   address as an operand, across all 6459 currently-disassembled
   instructions program-wide, found zero matches; the large 38KB
   `find_code_gaps` region immediately before `main_loop_body` turned out
   to be data (a string buffer), not a hidden caller. The true caller is
   not disassembled as code anywhere in the current Ghidra project — it's
   either in one of the dump's other still-undisassembled regions, or
   reached via an indirect call. Exhaustively checked, still open.
8. ~~**`FUN_000170ce`** (via thin wrapper `$170b6`) **and
   `FUN_000191e6`**~~ **RESOLVED 2026-09-16**: `FUN_000170b6` and
   `FUN_0001709e` are both trivial wrappers calling `FUN_000170ce`, which
   calls `FUN_000170d4` then `FUN_000170f2` — together an edge-latched
   per-actor one-shot sound/effect trigger scan (sound-adjacent, out of
   primary scope, but mechanism now understood). `FUN_000191e6` is
   **not** an infinite loop — real disassembly shows a bounded,
   VBL-interrupt-synced delay-wait (busy-wait on the `$19232` VBL counter
   vs. a target in `$18ed8`, then resets the counter to 0) — confirms the
   "decompiler artifact" hedge was correct, with the actual mechanism now
   nailed down. → wk.md "Gap-resolution pass…" (2026-09-16), "Gap #8
   resolved" subsection.
9. ~~**Exact write site of `sRam000115dc`**~~ **RESOLVED 2026-09-16**: it
   is set to `0` directly inline in `main_loop_body`, immediately after
   the submap-complete/normal-frame if/else block, right before the
   per-frame simulation calls — not inside `wait_for_vblank`'s callee.
   See also assumption B12 above, corrected in the same pass: this same
   write/read pair being internal to `main_loop_body` is why
   `get_xrefs_to` missed it. → wk.md "Gap-resolution pass…" (2026-09-16),
   "Gap #9 resolved" subsection.
10. ~~**`$149c2`/`$142fc`**~~ **RESOLVED 2026-09-16**: `FUN_000149c2` is a
    death-sequence step calling `FUN_000149f0` (clears a per-slot "used"
    high-bit flag) 10 times total. `FUN_000142fc` (created as a Ghidra
    function this pass — it had no function record despite being a real
    call target) is the submap reload/respawn routine: resets Rick's
    position/facing/flags, re-runs the per-level loader chain
    (`FUN_00014458`, `func_0x00016474`, `FUN_00016630`, `FUN_000157b4`,
    `FUN_00014542`), and re-scans the enemy spawn list under a guard
    flag. → wk.md "Gap-resolution pass…" (2026-09-16), "Gap #10 resolved"
    subsection.

### Map/submap transition (5)

11. **Several submap-load helper functions remain undecoded** —
    **FULLY CLOSED 2026-09-16**: `FUN_000170b6`/`FUN_0001709e` are
    trivial wrappers around `FUN_000170ce` (see #8). `FUN_00016630`
    (resets scroll sub-pixel accumulators) and `FUN_000157b4` (trivial —
    resets one flag) are fully decoded, both reached as callees of the
    newly-created `FUN_000142fc` (see #10). `FUN_000188d0`,
    `FUN_00018b5c`, `FUN_00018c50` all decompile as screen-scroll
    column/row blit loops (0xbf-iteration byte-shuffling copies between
    fixed tile/sprite buffers, scroll-offset-dependent addressing) —
    confirmed render/blit, out of scope by design (see item #32).
    **`func_0x00016474` remains genuinely blocked, but the cause is now
    fully diagnosed**: raw bytes at `$16474` (`48 E7 E0 E0`) are a valid
    `movem.l {D5-D7,A5-A7},-(SP)` prologue — the real, correct function
    entry — but Ghidra's project already has an incorrect, pre-existing
    code-unit boundary asserted two bytes later at `$16476` (from a
    stray earlier auto-analysis pass), which blocks placing a new
    instruction/function at `$16474`. This is a fixable Ghidra
    housekeeping issue (clear the wrong code unit at `$16476`, then
    re-disassemble from `$16474`), not an unknowable gap — just not
    fixable with the MCP tools available this pass. **A second,
    identical instance was found 2026-09-16** at `func_0x000123a0`
    (see item #33) — same bug shape (a wrong 2-bytes-late code unit
    blocking the real instruction), confirming this is a systemic
    Ghidra-project housekeeping issue rather than a one-off. → wk.md
    "`_DAT_00014592` resolved" section, ~line 2870-2923;
    "Gap-resolution pass…" and "Second gap-resolution batch…"
    (2026-09-16).
12. ~~**`FUN_0001726e`**~~ **RESOLVED 2026-09-16**: decompiles as the
    same byte-code movement-script-VM machinery documented elsewhere,
    reused against a dedicated screen-transition state block rather than
    a full `ActorRecord` — not a separate custom routine. → wk.md
    "Gap-resolution pass…" (2026-09-16), "Gap #12 resolved" subsection.
13. ~~**Map-4 alternate handler (`$17bf4`) and the map-5 special
    ending branch (`$10bf2`)**~~ **RESOLVED 2026-09-16**: `FUN_00017bf4`
    is trivial — a demo-mode guard around one further (render-adjacent,
    out-of-scope) call, and surfaced a previously-undocumented
    `_g_demo_mode_active` global. `$10bf2` was never a separate function
    at all — it's the inline label `LAB_00010c00` inside `main_loop_body`
    itself; there was nothing further to decompile. → wk.md "The main
    loop and the map-advance trigger" section, ~line 654-716;
    "Gap-resolution pass…" (2026-09-16), "Gap #13 resolved" subsection.
14. **Submap-trigger-table bytes 2-3** — see assumption #11 above; closed
    as "no reader found," which is a real gap dressed as a conclusion —
    could still matter if a rendering-only consumer exists.
15. ~~**`FUN_00015b3c`'s "restore canned actors" table**~~ **FULLY
    RESOLVED 2026-09-16 (readers now confirmed too)**: fully decoded —
    restores slots 0-3 from the `DAT_0001586e` template (position,
    anim/move script pointers, fixed flags) and primes their animation;
    separately clears slot 5 to inert. `DAT_00015b38 = 0x14` (20) is a
    **screen-transition countdown**, decremented by `FUN_00015eca`.
    `DAT_00015b3a = 0` is a **separate, unrelated cooldown**: the respawn
    timer (reset to `0x32`=50) for a newly-discovered mechanic —
    `g_actor_table[5]` is a dedicated single-instance "homing hazard"
    actor, (re)spawned by `FUN_00015d84` on this cooldown, aimed at the
    player via a discrete direction-vector computation, moved/collision
    -checked each frame by `FUN_00015e48` (can trigger
    `_g_player_death_trigger`). → wk.md "Second gap-resolution batch…"
    (2026-09-16), "New finding: `g_actor_table` slot 5" subsection.

### `ActorRecord` / actor system (6)

16. **`ActorRecord`'s remaining unnamed blobs** — `nUnk04` (offset 4),
    `aUnk08` bytes not otherwise explained (offsets 8-13, partially:
    0x08=0/0x0a=2/0x0c=0x100 known constants but purpose unnamed),
    `aUnk1c` (28-29), `aUnk24` (36-37). Confirmed dead end for *static*
    analysis — every function reachable from the actor/object
    construction+update call graph was checked and none touch them; would
    need either a live RAM sample with active enemy move/anim-script
    byte-code that happens to write these, or accepting them as
    likely-dead. → wk.md "Last player stairs flags named" section,
    ~line 2119-2176, and "Actor-spawn-init routines checked" section,
    ~line 2063-2118.
17. **Live validation of the type-`<0x75` monster-descriptor-table path**
    (see assumption #6) — a genuine gap in *data*, not just confidence;
    would need a live capture from later in the game (map 2+, or later
    in map 1) with an active low-type-ID enemy.
18. **Live validation of `dispatch_spawn_record`'s detail-block trigger
    path** (see assumption #7) — same kind of gap, needs a live capture
    where a `byte2&0x80==0` header's detail blocks actually fire.
19. **Whether `byte2&0x80`-set headers' unused trailing detail blocks are
    consumed by any other code path**, or are simply dead padding for
    that header type — left open, no candidate reader found. → wk.md
    "Live actors cross-checked…" section, ~line 2794-2803.
20. **`extraout_A1` register-level provenance** (see assumption #5) —
    formally untraceable in Ghidra's P-code for this function; would need
    real 68000 disassembly (which Ghidra also fails to produce for this
    function — see methodology caveats) to close definitively.
21. ~~**`ActorRecord+0x54`'s exact game meaning**~~ **RESOLVED
    (pre-existing, see B13 correction above)**: confirmed to be the
    oscillation period for `g_object_table` type-1 movers, read by
    `FUN_000150c0`. **`DAT_00014854`'s 4-entry LUT contents** (see
    assumption #14) — mechanics confirmed, per-type-category semantics
    still an open, low-priority guess; confirmed 2026-09-16 to have zero
    external readers via `get_xrefs_to`.

### Spawn/trigger-table grammar (2)

22. **Bulk-decoding more of each level's actual script/table byte
    streams.** Everything documented (header+detail grammar, movement/
    animation script opcodes, monster-descriptor table shape) has been
    validated against exactly **one** live sample: a 13-entry run of
    map-1's spawn table (**with the corrected variable-length
    header+detail segmentation**, not the earlier flat 4-byte-stride
    misread — see item #23) and one enemy's move+anim scripts. None of
    maps 2-4's content, and no later part of map 1, has been sampled at
    all — still a real, open gap. → wk.md "Move/animation script opcode
    formats decoded" and "Spawn table record grammar corrected"
    sections, ~line 2358-2539.
23. ~~**Records 22+ of the sampled spawn-table byte stream** parse as
    positionally-incoherent~~ **RESOLVED 2026-09-14 (gaps.md text was
    stale until 2026-09-16)**: this was an artifact of decoding the
    table with a flat 4-byte stride. The table actually uses
    **variable-length records** (a 4-byte header + 0-3 trailing 4-byte
    detail blocks, count given by header byte3 bits 0-1), terminated by
    a header with `byte0==0`. Re-walking the *same* sample with correct
    segmentation finds a clean, unambiguous 13-header/92-byte table
    ending at offset `0x5c`, with no leftover "records 22+" — they were
    never real records, just detail blocks and post-terminator bytes
    misread as independent 4-byte entries under the wrong stride. The
    "records 46-53 repeating pattern" question is moot for the same
    reason. → wk.md "Spawn table record grammar corrected" section
    (2026-09-14), "This resolves follow-up item 1" paragraph.

### `g_object_table` subsystem (1)

24. ~~**`g_object_table`'s own construction/spawn routine**~~ **RESOLVED
    2026-09-16**: not a separate function at all — `handle_screen_edge_
    and_respawn`'s `LAB_00015cc8` block (reached when a screen-edge
    transition finishes) hand-inlines a `g_object_table[0]` construction
    directly, field-by-field at fixed `$167a2`-relative offsets,
    positioned at Rick's post-transition location and paired with a
    sound-effect call (`FUN_0001a6aa`) using a sound-ID from
    `FUN_00017810`. There is no generic object-spawn constructor
    analogous to the enemy side's `FUN_00014636` — this is the *only*
    place anything writes a fresh entry into `g_object_table`. → wk.md
    "Second gap-resolution batch…" (2026-09-16), "Gap #24 RESOLVED"
    subsection.

### Player physics (3)

25. **`g_collision_result_flags` exact bit meanings** — only partially
    inferred (bit `0x20` = died/trapdoor, `0x02`/`0x04` = blocked
    direction, `0x08`/`0x10` = ledge/step detection, `0x40` = teleport-
    to-explicit-position); the document itself says this is "best done
    live: set a Hatari watchpoint on `$15f14`" — never done. → wk.md
    "Input abstraction and tile/actor collision, decoded" section,
    "Remaining open follow-ups" item 3, ~line 1148-1161.
26. ~~**`query_tile_and_actor_collision`'s per-probe-direction offset
    table**~~ **MOSTLY RESOLVED 2026-09-16**: the 3 x-taps are literally
    3 consecutive map-array bytes (X computed as `(g_collision_probe_x+4)
    >>3`, tile-column granularity); row count is 2 or 3 gated by
    `g_collision_probe_y&7<4`; both row-probe loop variants land on a
    uniform 33-byte row pitch. **Still open**: `compute_tile_map_ptr`'s
    Y-term (`(probe_y&~7)*4`) implies either an unexpectedly narrow
    per-column row stride or an indirect per-row descriptor table at
    `$65300` — which of the two, and why, wasn't pinned down; low
    priority since the effective 33-byte pitch/3-adjacent-column pattern
    (what a port actually needs) is already confirmed. → wk.md "Gap #26
    partially resolved: collision probe's exact tap geometry"
    (2026-09-16).
27. **Map-specific stairs-variant flags' deeper rationale.**
    `g_player_stairs_variant_map4_flag`/`_map2_flag` are confirmed to
    select an animation run-cycle length, but *why* maps 2 and 4 need a
    different cycle length was never chased. → wk.md "Last player stairs
    flags named" section, ~line 2119-2132.

### Input (1)

28. ~~**`FUN_000161fe`**~~ **RESOLVED 2026-09-16**: a combined tile+
    hazard-actor collision probe — reads the tile-attribute byte via
    `compute_tile_map_ptr`, then (only if tile bit `0x02` isn't already
    set) additionally scans `g_actor_table` for occupied "hazard" actors
    (`bBehavior_flags & 0xc0 == 0xc0`) via `point_in_box_test`, OR-ing
    bit `0x02` into `g_collision_result_flags` on a hit. Clarifies that
    bit `0x02` is a combined tile-OR-hazard-actor flag, at least for this
    call site — not fully reconciled against other bit-`0x02` call sites
    (see gap #25). → wk.md "Remaining open follow-ups" item 1 in the
    "Input abstraction and tile/actor collision" section, ~line
    1150-1153; "Gap-resolution pass…" (2026-09-16), "Gap #28 resolved"
    subsection.

### Tooling / methodology caveats (not gaps in the game's logic, but real caveats for anyone continuing this work)

29. **`list_globals`/`get_xrefs_to` unreliability for certain symbols.**
    Documented at least 3 times (`g_submap_trigger_table_ptr`,
    `g_screen_exit_trigger_flag`'s real address, and generally) — these
    tools can silently miss real, already-named symbols or real
    references. Always cross-check with `audit_global` or
    `get_function_pcode` before concluding a symbol is unread/unnamed. →
    wk.md "Submap-trigger table format decoded" (~line 2540-2602) and
    "`_g_screen_exit_trigger_flag` resolved" (~line 2925-2958) sections.
    **Fourth confirmed instance, 2026-09-16**: `get_xrefs_to` on
    `_DAT_000115dc` missed both the write and the read that turned out to
    be internal to `main_loop_body` itself (see former-B12/gap #9 above).
    Also, `get_function_callers`/`get_xrefs_to` on `main_loop_body` and
    `load_map_if_changed` both return zero results despite both functions
    obviously being called by something (gap #7) — left open rather than
    treated as proof of "no callers," per this same caveat.
30. **Ghidra's raw-dump auto-analysis leaves large swaths of code
    un-disassembled with no recorded xrefs**, and `disassemble_function`/
    `get_function_by_address` can report a degenerate 1-byte body for a
    function the decompiler otherwise walks correctly (seen on
    `check_submap_exit_triggers` and `FUN_000146a0`). Always prefer
    `get_function_pcode`/`decompile_function` over raw
    disassembly-listing tools when a function seems to have "0 xrefs" or
    "empty" disassembly — it may just be an analysis gap, not a dead or
    mislabeled symbol. → wk.md same two sections as above.
31. **Hatari `--cmd-fifo` automation gotchas**: `hatari-stop` can
    deadlock a scripted fifo session (emulation must be left running,
    not paused, while issuing fifo commands); and killing a stuck Hatari
    process can unlink its fifo special file from under a *different*
    still-running instance, after which a shell redirect into the
    now-missing path silently creates a regular file instead of erroring
    (symptom: fifo commands stop working with zero error output; check
    `ls -la` shows `prw-------`). → wk.md "Gotcha: Hatari's `--cmd-fifo`
    and pausing don't mix well" section, ~line 151-170.

### Demo/attract-mode subsystem (1, new 2026-09-16)

33. ~~The demo-playback branch inside `main_loop_body` is undecoded.~~
    **RESOLVED 2026-09-16.** `_g_demo_mode_active` confirmed (via
    `get_xrefs_to(0x3efb6)`) to be the *same* global as the already-
    documented `g_demo_mode_active` (`$3efb6`) — not a new subsystem.
    All 8 of the 9 gated callees were `create_function`'d and decoded:
    `func_0x00017a46` is a level-picker screen (joystick-driven,
    writes `g_map4_special_flag`) gated by a newly-found cheat flag;
    `func_0x0001771c` resets that screen's shared scratch state;
    `func_0x00010c28` is an unrelated one-shot hardware-vector-backup
    routine (out of scope); `func_0x0001789a` is a sound-sequence-end
    wait loop (sound-adjacent); `func_0x00017bda` plays a fanfare +
    triggers a render-adjacent effect on non-demo completion;
    `func_0x00017c06` is a generic "press fire to continue" wait loop;
    `func_0x00017f22` is a 5-character name-entry screen that contains
    a genuine **"POOKY" cheat code** (typing that name sets a flag byte
    at `$1798e` that unlocks the manual level-picker in
    `func_0x00017a46`); `func_0x000178dc` is the demo/attract-mode
    *entry* sequencer (4 record/playback rounds, then sets
    `_g_demo_mode_active`), confirming that global's setter. The 9th,
    `func_0x000123a0`, remains blocked — but its root cause is now
    understood as a **second confirmed instance** of the same Ghidra
    code-unit-boundary bug already diagnosed for `func_0x00016474` (see
    gap entry above): the real instruction (`move.w D1,$17994`, 6
    bytes) starts 2 bytes before Ghidra's existing wrong code unit.
    → wk.md "Gap #33 resolved: demo-mode branch's callees decoded, and
    the 'POOKY' cheat found" (2026-09-16).

### Out of scope by design (not a real gap — listed here only so nothing looks "missing")

32. **Render/blit routines.** Never located among the traced per-frame
    calls, and deliberately not pursued — "render/blit routines" work is
    explicitly excluded from this reverse-engineering effort's scope
    (game-logic-only focus), reaffirmed repeatedly throughout the later
    sections of `xrick2-wk.md` (e.g. ~line 1026-1029, 1610-1611,
    1643-1644, 1752-1753, 3488). Likewise **`FUN_0001a6aa`'s** sound-
    effect-ID parameter meaning and the **`PTR_DAT_000176f4`** visual/
    sound-effect request slot are both sound/render-adjacent and
    intentionally not decoded further (wk.md ~line 1821-1837, 2432-2438).
    Do not treat these as unfinished work items for the game-logic port —
    they are deliberately deferred to whatever separately handles
    rendering/audio.
