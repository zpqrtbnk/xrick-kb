# review-plan.md — aligning the xrick port with the Atari ST reverse engineering

**This is the plan for `PLAN.md` T1.** T1 originally read "build the reimplementation and
diff it against the live game". That is superseded: **we are not writing a new
implementation.** We take the existing xrick port as the starting body of code and bring
it into verified agreement with `re/`.

Three passes, in this order:

1. **Data tables** — where each generated table came from, and whether it is ST or PC.
2. **Data structures** — every struct and variable: width, signedness, layout, initial
   value.
3. **Code** — every algorithm and fragment, against the matching `re/` document.

Tables first because a table of unknown provenance makes every downstream comparison
ambiguous. Structures before code because a wrong width silently changes correct-looking
code (`if (x < 0)` on a `U16` never fires), and fixing widths afterwards would invalidate
the code pass.

---

## 0. Settled ground

### 0.1 Target: **switchable** — `PLATFORM_ST` / `PLATFORM_PC`

**Decided by the user 2026-09-04.** Where the two versions genuinely differ, **both
behaviours coexist**, selected by define. Neither is deleted.

This matters because T8 established **17 confirmed PC-vs-ST behavioural differences**,
every one a genuine divergence and **none a port error**. Under a switchable scheme each
becomes a documented, testable pair rather than a silent choice.

Conventions to fix at the start of the work and then apply mechanically:

- Exactly one of `PLATFORM_ST` / `PLATFORM_PC` is defined, in `config.h`, beside the
  existing `GFXST` / `GFXPC` graphics switch — **the two are independent**: the stock
  build is already ST *graphics* with PC *logic*, which is precisely the hybrid that made
  this project's comparisons three-way ambiguous.
- Prefer a named constant defined once per platform over an `#ifdef` at each use site, so
  the 17 differences read as a table rather than as scattered conditionals.
- Every switched value cites its `xrick/re/xref.md` row.
- A build with neither (or both) defined must fail to compile, not pick a default.

### 0.2 Licence — **closed, no constraint**

The user holds the rights to the PC version. Earlier caution in
`xrick/re/provenance.md` about "All rights reserved" and a README with no terms is
**not a blocker** for modifying, building or publishing this work. That note should be
amended so it stops being read as an open question.

### 0.3 The port's comments are **not evidence**

**Instruction from the user, and it overrides how earlier documents were written:** the
`ASM nnnn` annotations, the `b02`/`w04` width markers, the slot-map commentary and the
FIXMEs record *what the port's authors believed the PC version did*. They may be wrong.

- **Ghidra is the authority.** `atari_ram.bin` for the ST, `ibmpc_cs.bin` for the PC.
- Port comments may be used to *locate* code — the `+0x17E` offset from the `ASM nnnn`
  citations is a proven finding — but never to *establish* a fact.
- Where a comment turns out wrong, fix the comment as part of the same commit.

⚠️ **Asymmetry to keep in view: we have the PC's code segment but not its data segment.**
So PC *code* can always be checked in Ghidra, while for PC *data* (maps, entity
templates, sprite tables) the port's own tables are the only record we hold. §1 is
partly about establishing how far those can be trusted.

---

## 1. Phase 1 — where do the generated tables come from?

The user's open question, and the first real work. `xrick/xrick/src/dat_*.c` is 43,264
lines — 81% of the codebase — of unknown provenance.

**Already measured, and the news is mostly good:**

| Table | Port | ST (`re/`) | Verdict |
|---|---|---|---|
| `map_marks` | 523 records | `placement_table[523]` @ `0x481E4` | ✅ **value-identical — 523/523 on all four comparable fields.** ST stores the band as a word, the port and the PC as a byte (PC `mark_t` stride is 5, confirmed by `ADD BX,5`); the values are the same |
| `map_connect` | 153 = 106 + 47 | 153 = 106 + 47 @ `0x478B2` | ✅ **identical, all 47 lists agree** (see `PLAN.md` T10 — an earlier "port defect" here was **our** miscount, retracted) |
| `map_submaps` | 47 | 47 room headers @ `0x47620` | ⬜ counts agree; contents unchecked |
| `map_maps` | 5 | `LevelStartInfo[5]` @ `0x4B522` | ⬜ counts agree; contents unchecked |
| `ent_entdata` | 74 × 8 packed bytes | `object_type_defs[75]` × 16 bytes @ `0x47D34` | ⚠️ **`trig_w`/`trig_h`/`snd` agree 100%; `w`/`h` differ in 3 of 74** — indices 3, 22, 23, where ST is `0/0` and the port has `24/21`. Structures differ by design (T9) |
| `map_bnums`, `map_eflg`, `ent_sprseq`, `ent_mvstep` | — | tile/attr banks, sprite tables | ⬜ **unchecked** |
| `dat_spritesST/tilesST/picsST` | — | `re/assets/*` extractions | ⬜ **unchecked** — the artwork is nominally ST already |

**So the placement and connector data is common to both versions, and the entity template
table is not.** That is exactly the mixed answer that justifies doing this properly rather
than assuming either way.

- **R1.1** Finish the census: every `dat_*.c` table against its ST counterpart, by value,
  with the comparison scripted and re-runnable. Comment-stripped, brace-depth parsing —
  **never** a naive brace regex (that error produced two phantom defects in this project).
- **R1.2** For each table record a verdict: *identical* / *differs, PC-vs-ST* /
  *differs, defect* / *no ST counterpart*.
- **R1.3** Where a table differs, decide under §0.1 whether it needs a switched variant.
  The three `ent_entdata` `w`/`h` rows are the first test case: ST leaves them `0` and
  relies on the `0x15` default row count, the port bakes in `24`/`21`. Establish whether
  that is behaviourally equivalent before switching or unifying it.
- **R1.4** **Build our own extraction from the ST binary** for every table where we want
  a known-provenance ST dataset. `re/extract_assets.py` already does this for artwork; the
  extension is the map/entity tables. Emit them in the port's own `dat_*.c` format so an
  ST build can compile against them directly, and so the diff against the existing tables
  *is* the audit.
- **R1.5** Sprite/tile/picture data: confirm the `GFXST` tables really are ST by
  byte-comparing against `re/assets/`. The sprite sheet is 212 occupied slots on our side
  (a corrected figure — it was long recorded as 185).

---

## 2. The work surface — measured

| Bucket | Lines | Files | Treatment |
|---|---|---|---|
| Generated data tables (`dat_*.c`) | 43,264 | 10 | **Phase 1** — compared as values, never read as text |
| SDL platform + `unzip.c` | 2,916 | 8 | **Out of scope** — no ST counterpart |
| **Game logic** | **6,962** | **30** | **Phases 2–3** |

The logic partitions onto our documents with nothing left over:

| Group | Lines | Files | Oracle |
|---|---|---|---|
| System / flow | 2,646 | `game.c`, `scr_*.c` (6), `control.c`, `xrick.c`, `devtools.c`, `data.c` | `re/algo-system.md` |
| Entities | 1,759 | `ents.c`, `e_them.c`, `e_box.c`, `e_bonus.c`, `e_sbonus.c`, `e_bullet.c`, `e_bomb.c` | `re/algo-entities.md` |
| Render | 1,090 | `draw.c`, `sprites.c`, `tiles.c`, `fb.c`, `rects.c`, `img.c`, `scroller.c` | `re/algo-render.md` |
| Player | 568 | `e_rick.c` | `re/algo-player.md` |
| Level / map | 557 | `maps.c`, `env.c` | `re/algo-level.md` |
| Helpers | 210 | `util.c` | probes in `algo-player.md`, `algo-entities.md` |
| Sound | 132 | `sounds.c` | `re/algo-music.md` |

---

## 3. Ground rules

- **Ghidra decides.** Not `re/`, not the port's comments, not plausibility. `re/` is a
  well-audited index into the disassembly — 50 recorded defect fixes deep — but it has
  been wrong and will be again.
- **Every change cites its evidence**: an address, an instruction, or a `re/` section.
- **NEVER ASSUME ANYTHING — ALWAYS CHECK** (`CLAUDE.md`). This project has been bitten
  four times by searches that structurally could not find what they sought, and twice by a
  regex that counted braces inside comments — the second of which stood for five days as a
  reported defect. **Validate every query against a known-present control, and when a
  method proves unsound, re-run every earlier result that used it.**
- **No behaviour-preserving cleanups.** No renaming sweeps, no reformatting, no
  refactoring for taste. Every diff traces to a fidelity finding or it is noise.
- **One finding, one commit.** The audit trail is the deliverable.

---

## 4. Phase 0 — baseline

- **R0.1** Build as-is (`GFXST`, SDL2). Record the toolchain and **all** warnings —
  `-Wall -Wextra -Wconversion` output is itself phase-2 evidence, since every implicit
  narrowing is a candidate width bug.
- **R0.2** Run it; capture reference screenshots and a scripted demo run.
- **R0.3** Stand up the A/B harness: one input script driven into both the port and the
  ST build under Hatari. `re/hatari_probe.py` already drives the ST side and pokes
  `joystick1_state` at `0x4922B`. Sample comparable state — Rick's x/y, entity slots,
  score, level/submap — not pixels.
- **R0.4** Start `review-log.md`: one row per finding — *id · file:line · evidence ·
  port value · ST value · verdict · action*. Mirrors `re/byte-identity.md`'s role, and
  makes the **absence** of a finding auditable too.

---

## 5. Phase 2 — data structures and variable widths

Highest-value target, with direct evidence it will pay: `divergences.md` §4.2 already
records **seven `if (x < 0)` tests on unsigned values that can never fire**.

The port's `ent_t` carries width markers in its field comments, and five contradict the
declared C type — `x` (`b02`), `trig_x` (`b16`), `xsave` (`b1C`), `c1` (`b26`),
`c2` (`b28`) are all declared 16-bit but marked byte.

⚠️ **Per §0.3 those markers are not evidence.** And width is a **per-access-site**
question, not per-field: our ST `nPosX` is a short, while the PC binary uses *both* widths
on the same field — `MOV word ptr [SI+2],0x00E2` at `0x19B9` against byte loads elsewhere.
Our own side has the same pattern: `nPosY`'s low byte is accessed directly at `+0x07` at
four sites. **This is a census, not a search-and-replace.**

- **R2.1** `ent_t` — every field, every read and write site, against
  `re/data-structures.md` → *SpriteEntity* and the ST instruction widths/sign-extension.
- **R2.2** The other structures: `entdata_t`, `mark_t`, `connect_t`, `submap_t`, `map_t`,
  `mvstep_t`, `hscore_t` (vs the 30-byte high-score record).
- **R2.3** Module-level and file-static variables, against `re/data-structures.md`'s
  globals table.
- **R2.4** Signedness audit driven by R0.1's warnings plus the ST `ext.w`/`ext.l`/`cmp`
  senses. Precedent for how much this matters: the music transpose defect — byte
  arithmetic wrapping mod 256, then sign-extended.
- **R2.5** Table bounds: `ENT_ENTSNUM` (12, vs our 13-slot `sprite_list` + `0xFFFF`
  sentinel — reconcile), `ENT_NBR_SPRSEQ`, `ENT_NBR_MVSTEP`. `MAP_NBR_CONNECT` and
  `ENT_NBR_ENTDATA` are **already verified correct**.
- **R2.6** Initial values and reset state, against what `re/` records as seeded at spawn
  and at level start.

**Exit criterion:** every field and global has a recorded verdict with a citation.

---

## 6. Phase 3 — algorithms and code fragments

File by file against the §2 oracle, ordered by documentation quality and coupling to
phase 2:

- **R3.1 Entities** (1,759) — largest block, best documented, and where most of the 17
  differences live. `ents.c` first: `ent_actvis` is now fully understood on both sides,
  including the T9 `sni`→`sprbase` overload.
- **R3.2 Player** (568) — `e_rick.c`. Dense in constants (gravity `+0x80` clamp `0x800`,
  jump `-0x580`, bounce `0xFE - nVelY`), all verified three ways.
- **R3.3 Level/map** (557) — `maps.c`, `env.c`. Includes the submap-exit values.
- **R3.4 Render** (1,090) — **semantic** alignment only: sprite/tile selection, clipping
  bounds, trigger points. *Not* blitter mechanics — the port's renderer is an SDL rewrite
  with no ST counterpart worth matching. `algo-render.md` is instruction-audited (T4).
- **R3.5 System/flow** (2,646) — largest by line count, but much is SDL scaffolding.
- **R3.6 Helpers** (210) — `util.c`: `u_envtest`/`u_boxtest`, confirmed identical in all
  32 reachability cells.
- **R3.7 Sound** (132) — track identity and trigger points; the port has no tracked-music
  engine.

**Per file:** read the port function → read the `re/` transcription → check both against
Ghidra → classify each difference → switch it, fix it, or record agreement. Where `re/` is
silent, go to the disassembly and **extend `re/`** — the knowledge base is a deliverable
of this pass, not just an input.

---

## 7. Known defects — fix on contact

Evidence already recorded and cited:

| Defect | Evidence | Fix |
|---|---|---|
| `e_them_rndseed` high half read out of bounds | `PLAN.md` T17 — PC `0x024A`/`0x0270` prove the seed is two words, low `0x7E4A` high `0x7E4C` | `sh = (U16*)&e_them_rndseed + 1` |
| Trigger-sound table indexed from the wrong base | `xrick/re/xref.md` — `- 0x14` yields `-1` for the `0x13` entity; ten values `0x13`–`0x1C` | Correct the base |
| Seven `if (x < 0)` tests on unsigned values | `xrick/re/divergences.md` §4.2 | Falls out of phase 2 |
| `6dbd` store omitted at both submap exits | `PLAN.md` T8 — PC writes `[0x7D77]` `0x00`/`0x01`; it **is** read at `0x0D99` | Restore, or prove `game_dir` equivalent |

*(The `map_connect` "overrun" previously listed here was retracted — see `PLAN.md` T10.)*

---

## 8. Phase 4 — verification

- **R4.1** A/B harness on a scripted run per level, comparing sampled state.
- **R4.2** A probe per switched difference, confirming each build exhibits its own value —
  17 rows × 2 platforms.
- **R4.3** Regression against the R0.2 reference run.
- **R4.4** `review-log.md` complete: every table, field and function carrying a verdict.

---

## 9. Excluded

Rewriting the SDL layer, build system or `unzip.c`; performance, portability, features;
reformatting or renaming for taste; reading the `dat_*.c` tables as text rather than
comparing them as values.

---

## 10. Risks

- **PC-side data cannot always be adjudicated.** We hold the PC code segment, not its
  data. Where the port's tables are the only record of PC data, "verify with Ghidra" is
  not available and the verdict must say so.
- **`re/` is not infallible** — 50 recorded defect fixes, and recent audits found errors
  in claims that had survived nine earlier passes.
- **Switchable code can rot.** A `PLATFORM_PC` path nobody builds will drift. R4.2 exists
  to keep both honest; CI building both configurations would be better.
- **Scope creep into "make the code nice"** — the one-finding-one-commit rule exists to
  stop it.

---

## 11. Status — 2026-09-05

### Build state

Both platforms build clean and the game runs. `make PLATFORM=ST` (default) and
`make PLATFORM=PC` produce **different binaries**, verified byte-wise. **26 `PLATFORM_ST`
switch sites across 12 files.** 182 compiler warnings, all classified (R2.4); the single
remaining `-Wtype-limits` is expected and correct (R3.1 `maps_clip`).

### ✅ Achieved

| | state |
|---|---|
| **Phase 0** baseline | **Complete.** `Makefile` added; six portability fixes; both platforms build and run |
| **Phase 2** data structures | **Complete.** 33 `SpriteEntity` fields measured program-wide; 7 other structs adjudicated; 32 globals compared; all 99 conversion warnings classified |
| **Phase 3a** entities | **Complete at the level attempted.** `ents.c` (5 logic fns, 4 rendering out of scope), `util.c`, `e_bullet.c`, `e_bomb.c`, `e_box.c`, `e_bonus.c`, `e_sbonus.c` compared; `e_them.c` compared at constant/condition level against the full 238-instruction ST oracle |
| **Phase 3b** level/map | **Complete.** `env.c` is entirely rendering (out of scope); `maps.c` has 5 rendering fns (out of scope) and 4 logic fns, of which 3 are compared. Only `map_expand` remains |
| **`xref.md` sweep** | **Complete.** All 25 rows checked; **14 had never been applied**, 12 now are |

**Results: 38 differences catalogued · 26 switch sites · 6 port defects fixed · 3 plausible
"fixes" correctly refused · 1 self-inflicted regression caught.**

The six defects: the left-edge submap exit, the corpse clamp inverting direction, a bullet
missing an entity's top scanline, the box explosion sprite overread, the bullet's right
bound, and the trigger-sound index reading `WAV_ENTITY[-1]`.

### 🔴 Remaining

**Code not yet compared — 3 groups, ~70 functions:**

| group | files | fns | note |
|---|---|---|---|
| System / flow | `game.c`, `scr_*.c` ×6, `control.c`, `xrick.c`, `data.c`, `devtools.c` | ~28 | much is SDL scaffolding |
| Render | `sprites.c`, `tiles.c`, `fb.c`, `draw.c`, `rects.c`, `img.c`, `scroller.c` | ~23 | semantic alignment only — no blitter matching |
| Player | `e_rick.c` | 5 of 7 | `e_rick_boxtest` and the exits done |
| Sound | `sounds.c` | 4 | track identity / trigger points |

**Open findings needing a decision or the PC side:**

1. **Score overflow representation** — needs the **user's** decision. ST wraps at
   1,000,000; PC corrupts its top digit; port never wraps. Matching either means replacing
   `env_score` with a digit array.
2. **`e_them.c` ×4** (R3.15) — climb velocity, climb gate masks, the `y & 0xfe` compare
   (likely a real defect), the PRNG turn.
3. **`e_box.c` ×3** (R3.9) — test order, exploding box killing Rick, animation model.
4. **Dynamite fuse** — structural rewrite, not an `#ifdef`.
5. **Spawn banding** — the port scans 8 rows further down than the ST.
6. **`map_maps[4]`**, **`map_frow` width**, **`e_box.c` sprite `0x29`** (inferred, not read).

**Phase 1 tables still unchecked:** `map_bnums`, `ent_sprseq`, `ent_mvstep`,
`dat_spritesST`, `dat_picsST`.

### Recommended order from here

1. **`e_them.c` finding #3** (`y & 0xfe`) — cheapest likely-real defect outstanding.
2. **The score decision** — it blocks nothing else but has been open longest.
3. **`e_rick.c`'s 5 remaining functions** — the last dense-logic file.
4. **`map_expand`** — finishes 3b outright.
5. Phase 1 leftovers, then render/system/sound last.

### Standing checks (each earned by a near-miss)

- Read bounds tests for **edge sense**, not just constants — the ST excludes equality on
  lower edges where the PC includes it, in **five** routines now.
- Read counter loops for **decrement order** — `e_bonus.c` was 11 frames, not 12.
- Locate PC code by **content signature**, never citation arithmetic (R3.10).
- **Re-read any site an earlier change made live** (R3.7).
- **Check a field exists before referencing it** — the port has no `dir`; enemy direction
  is the sign of `offsx` (R3.14).
- **A row in `xref.md` is not a change in the code** — sweep periodically (R3.14).
