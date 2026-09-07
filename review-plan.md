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

## 11. Status and conclusions — 2026-09-07

### Verified state (re-checked, not recalled)

Both platforms build with **0 errors**; binaries differ (531,776 / 530,912). `make warn`:
**179** warnings, 0 errors — *below* the 181 present before this review, in the same
pre-existing classes. **45 `PLATFORM_ST` switch sites.** All sampled code-level claims in
`review-log.md` re-verified present (20/20), and a regression scan for every superseded
pattern (truncating `y` masks, direct `env_score +=`, the old `sh` pointer, the old scroll
threshold) comes back **clean**.

### Function inventory — 198 functions in `src/`

| state | fns | files |
|---|---|---|
| **Compared against both originals** | **65** | `e_them` 11, `game` 11, `ents` 9, `maps` 9, `e_rick` 7, `env` 4, `util` 4, `e_bomb` 3, `e_box` 2, `e_bullet` 2, `e_sbonus` 2, `e_bonus` 1 |
| Partly compared | 4 | `scr_getname` (hall of fame verified; the entry UI is not) |
| **Not compared** | **47** | render 24 (`fb` 7, `tiles` 6, `sprites` 5, `rects` 2, `img` 2, `scroller` 2), intro screens 12, `sounds` 4, data helpers 5, `sysjoy` 2 |
| No counterpart in either original | 82 | `unzip` 27, `syssnd` 19, `data` 11, `sysvid` 9, `sysarg`/`system` 8, `xrick` 4, `sysevt` 3, `devtools` 1 |

**19 port defects found and fixed.** The simulation core — every entity, the player, the
map system and the game state machine — is compared.

### Conclusions

**1. The two platforms are NOT equally trustworthy, and this is the central finding.**
The port *is* the PC game: it was reverse-engineered from it, so `PLATFORM_PC` is close to
correct by construction and this review mostly *confirmed* it, fixing 19 genuine slips.
`PLATFORM_ST` is a **reconstruction** — every ST behaviour in the tree exists because I
read it out of `atari_ram.bin` and wrote it in. It has no independent provenance, far less
corroboration, and has never been executed against a real ST.

**2. Everything is verified statically.** Every claim rests on reading disassembly and
matching constants, conditions and table contents. **Nothing has been verified by running
the port and the original side by side.** That is the single largest gap between "the code
reads correctly" and "the code behaves identically".

**3. The defect pattern was overwhelmingly edge-sense and width, not logic.** Of 19
defects: seven `>` vs `>=` boundaries, four truncating masks, two out-of-bounds accesses,
one dead branch, one hybrid that matched neither original. The port author's *understanding*
was almost always right; the transcription slipped in the last bit.

**4. Three of my own claims were wrong and are retracted in place** — the inferred sprite
`0x29` (R4.10), the digit-array requirement for the score wrap (R3.16), and "`map_bnums`
needs an ST variant" (C1). Two more premises dissolved on checking (`map_frow` width; the
SPAD blocked-test). A fourth, the phantom 154th `map_connect` row, was retracted earlier.

**5. Data provenance is now settled.** The port's tables came from a PC build whose data
segment sat `0x0FBA` below `ibmpc_ds1.bin`'s. `map_blocks` is identical on both platforms;
`map_bnums` differs by two padding bytes that the submap offsets cancel exactly. The
pointers-vs-numbers model (T9) is solved: `sprite = (ST pointer - 0x2BE9E) / 0x150`.

### What remains for both builds to *truly* match their originals

**R1 — Differential testing against the originals. The biggest gap, and nothing else
substitutes for it.**
The Hatari harness already boots the analysed ST build, drives it by poking the joystick
byte, sets breakpoints and dumps RAM (`re/hatari_probe.py`; an in-game dump was produced
this session). The work is to drive **the same scripted input** into the ST original and
into `PLATFORM_ST`, and compare state frame by frame — Rick's x/y/velocity, the entity
pool, score, map row. Any divergence localises to a frame and a variable. Without this,
`PLATFORM_ST` remains unexecuted theory. DOSBox could do the same for `PLATFORM_PC`.

**R2 — The 24 render functions, for *what* is drawn, not how.**
Tile and sprite *selection*, positions, draw order, and the clipping bounds — the layer
that decides which bytes reach the screen. `maps_clip` already produced defect #18, which
suggests this layer is not clean. The SDL blitting underneath is explicitly out of scope.

**R3 — The 12 intro-screen functions and the 4 in `sounds.c`.**
`screen_imapsteps` does not match any dump under any encoding, so the level-intro
animation must be compared behaviourally. `sounds.c` is where "the right sound at the right
time" is decided.

**R4 — Close the residual open items.** The HOF qualification boundary at exactly 1000;
`scr_getname`'s entry UI; the `ent_sprseq`/`ent_mvstep` over-runs (inert, deliberately
unchanged); the ST bomb explosion phase after its fuse sentinel.

**R5 — ST artwork pixel verification (C2), lowest value.** A6 gave the frame *indices*,
which is what the logic needed. Confirming the pixel data itself is a separate exercise and
changes no behaviour.

### Honest bottom line

`PLATFORM_PC` is in good shape: derived from the PC, checked against it, 19 slips repaired.
`PLATFORM_ST` is a careful reconstruction that is **internally consistent and
instruction-backed but never executed against the original**. Until R1 is done, the correct
claim is *"matches the disassembly as read"*, not *"matches the original"*.

### Standing checks (each earned by a near-miss)

- Read bounds tests for **edge sense** — seven defects were `>` vs `>=`.
- **A control proves a query runs, not that it has the right shape** (`cmpi.w` vs `cmp.w`;
  a stride-4 scan stepping over an unaligned table).
- Locate PC code by **content signature**, never citation arithmetic — three `ASM nnnn`
  citations in `e_rick.c` alone are wrong.
- **An inference labelled as an inference is still an inference** (R4.10).
- **A row in a document is not a change in the code** — sweep periodically.
- The port's data came from a **different PC build** (R4.22); pointer-bearing tables will
  never match exactly.
- **Whitespace and block length break string-matched edits** — prefer line-anchored edits.
