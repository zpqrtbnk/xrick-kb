# review-plan.md — aligning the xrick port with the Atari ST reverse engineering

**This is the plan for `PLAN.md` T1.** T1 originally read "build the reimplementation and
diff it against the live game". That is superseded: **we are not writing a new
implementation.** We take the existing xrick port as the starting body of code and bring
it into verified agreement with `kb/`.

Three passes, in this order:

1. **Data tables** — where each generated table came from, and whether it is ST or PC.
2. **Data structures** — every struct and variable: width, signedness, layout, initial
   value.
3. **Code** — every algorithm and fragment, against the matching `kb/` document.

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
- Every switched value cites its `kb/xrick/xref.md` row.
- A build with neither (or both) defined must fail to compile, not pick a default.

### 0.2 Licence — **closed, no constraint**

The user holds the rights to the PC version. Earlier caution in
`kb/xrick/provenance.md` about "All rights reserved" and a README with no terms is
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

| Table | Port | ST (`kb/`) | Verdict |
|---|---|---|---|
| `map_marks` | 523 records | `placement_table[523]` @ `0x481E4` | ✅ **value-identical — 523/523 on all four comparable fields.** ST stores the band as a word, the port and the PC as a byte (PC `mark_t` stride is 5, confirmed by `ADD BX,5`); the values are the same |
| `map_connect` | 153 = 106 + 47 | 153 = 106 + 47 @ `0x478B2` | ✅ **identical, all 47 lists agree** (see `PLAN.md` T10 — an earlier "port defect" here was **our** miscount, retracted) |
| `map_submaps` | 47 | 47 room headers @ `0x47620` | ⬜ counts agree; contents unchecked |
| `map_maps` | 5 | `LevelStartInfo[5]` @ `0x4B522` | ⬜ counts agree; contents unchecked |
| `ent_entdata` | 74 × 8 packed bytes | `object_type_defs[75]` × 16 bytes @ `0x47D34` | ⚠️ **`trig_w`/`trig_h`/`snd` agree 100%; `w`/`h` differ in 3 of 74** — indices 3, 22, 23, where ST is `0/0` and the port has `24/21`. Structures differ by design (T9) |
| `map_bnums`, `map_eflg`, `ent_sprseq`, `ent_mvstep` | — | tile/attr banks, sprite tables | ⬜ **unchecked** |
| `dat_spritesST/tilesST/picsST` | — | `kb/assets/*` extractions | ⬜ **unchecked** — the artwork is nominally ST already |

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
  a known-provenance ST dataset. `kb/extract_assets.py` already does this for artwork; the
  extension is the map/entity tables. Emit them in the port's own `dat_*.c` format so an
  ST build can compile against them directly, and so the diff against the existing tables
  *is* the audit.
- **R1.5** Sprite/tile/picture data: confirm the `GFXST` tables really are ST by
  byte-comparing against `kb/assets/`. The sprite sheet is 212 occupied slots on our side
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
| System / flow | 2,646 | `game.c`, `scr_*.c` (6), `control.c`, `xrick.c`, `devtools.c`, `data.c` | `kb/algo-system.md` |
| Entities | 1,759 | `ents.c`, `e_them.c`, `e_box.c`, `e_bonus.c`, `e_sbonus.c`, `e_bullet.c`, `e_bomb.c` | `kb/algo-entities.md` |
| Render | 1,090 | `draw.c`, `sprites.c`, `tiles.c`, `fb.c`, `rects.c`, `img.c`, `scroller.c` | `kb/algo-render.md` |
| Player | 568 | `e_rick.c` | `kb/algo-player.md` |
| Level / map | 557 | `maps.c`, `env.c` | `kb/algo-level.md` |
| Helpers | 210 | `util.c` | probes in `algo-player.md`, `algo-entities.md` |
| Sound | 132 | `sounds.c` | `kb/algo-music.md` |

---

## 3. Ground rules

- **Ghidra decides.** Not `kb/`, not the port's comments, not plausibility. `kb/` is a
  well-audited index into the disassembly — 50 recorded defect fixes deep — but it has
  been wrong and will be again.
- **Every change cites its evidence**: an address, an instruction, or a `kb/` section.
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
  ST build under Hatari. `kb/hatari_probe.py` already drives the ST side and pokes
  `joystick1_state` at `0x4922B`. Sample comparable state — Rick's x/y, entity slots,
  score, level/submap — not pixels.
- **R0.4** Start `review-log.md`: one row per finding — *id · file:line · evidence ·
  port value · ST value · verdict · action*. Mirrors `kb/byte-identity.md`'s role, and
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
  `kb/data-structures.md` → *SpriteEntity* and the ST instruction widths/sign-extension.
- **R2.2** The other structures: `entdata_t`, `mark_t`, `connect_t`, `submap_t`, `map_t`,
  `mvstep_t`, `hscore_t` (vs the 30-byte high-score record).
- **R2.3** Module-level and file-static variables, against `kb/data-structures.md`'s
  globals table.
- **R2.4** Signedness audit driven by R0.1's warnings plus the ST `ext.w`/`ext.l`/`cmp`
  senses. Precedent for how much this matters: the music transpose defect — byte
  arithmetic wrapping mod 256, then sign-extended.
- **R2.5** Table bounds: `ENT_ENTSNUM` (12, vs our 13-slot `sprite_list` + `0xFFFF`
  sentinel — reconcile), `ENT_NBR_SPRSEQ`, `ENT_NBR_MVSTEP`. `MAP_NBR_CONNECT` and
  `ENT_NBR_ENTDATA` are **already verified correct**.
- **R2.6** Initial values and reset state, against what `kb/` records as seeded at spawn
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

**Per file:** read the port function → read the `kb/` transcription → check both against
Ghidra → classify each difference → switch it, fix it, or record agreement. Where `kb/` is
silent, go to the disassembly and **extend `kb/`** — the knowledge base is a deliverable
of this pass, not just an input.

---

## 7. Known defects — fix on contact

Evidence already recorded and cited:

| Defect | Evidence | Fix |
|---|---|---|
| `e_them_rndseed` high half read out of bounds | `PLAN.md` T17 — PC `0x024A`/`0x0270` prove the seed is two words, low `0x7E4A` high `0x7E4C` | `sh = (U16*)&e_them_rndseed + 1` |
| Trigger-sound table indexed from the wrong base | `kb/xrick/xref.md` — `- 0x14` yields `-1` for the `0x13` entity; ten values `0x13`–`0x1C` | Correct the base |
| Seven `if (x < 0)` tests on unsigned values | `kb/xrick/divergences.md` §4.2 | Falls out of phase 2 |
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
- **`kb/` is not infallible** — 50 recorded defect fixes, and recent audits found errors
  in claims that had survived nine earlier passes.
- **Switchable code can rot.** A `PLATFORM_PC` path nobody builds will drift. R4.2 exists
  to keep both honest; CI building both configurations would be better.
- **Scope creep into "make the code nice"** — the one-finding-one-commit rule exists to
  stop it.

---

## 11. STATUS AND HANDOFF — 2026-09-07

*Written to be picked up cold. Everything here was re-verified when written, not recalled.*

### 11.1 What this task is

`xrick/` is a C/SDL2 port of Rick Dangerous, reverse-engineered from the **IBM PC** build.
T1 makes it a faithful, *switchable* reimplementation of **both** originals: `PLATFORM_ST`
and `PLATFORM_PC` select game behaviour and data, independently of `GFXST`/`GFXPC` which
select artwork. Where the two originals differ, both behaviours live in the tree behind
`#ifdef PLATFORM_ST`, with the disassembly evidence in a comment at the site.

**Three sources, and the rule for using them.** ST = `kb/atari_ram.bin` (320 KB; offsets
are addresses directly) and `kb/hatari/ram.bin` (1 MB **in-game** dump, rebase delta
`-0x2054`). PC = `kb/ibmpc_cs.bin` (code segment) plus `kb/ibmpc_ds1.bin` (data segment
`0x179C`) and `kb/ibmpc_ds2.bin` (segment `0x271D`) — **both data dumps are shift 0**, so a
DS offset is a file offset. **The port's own comments are not evidence**; verify against
the disassembly. Never decompile to C (project rule).

### 11.2 Verified build state

Both platforms build with **0 errors**; the binaries differ. `make warn` gives **182**
warnings, 0 errors, all in pre-existing classes. (Two are above the historical 180: they
are `-Wtype-limits` on the `y < 0` half of `ENT_YDEAD` at the two sites where the local `y`
is `U16`. Behaviour is still correct — the unsigned upper bound catches a wrapped-negative
exactly as the PC's unsigned compare does. See the warning-census note in `review-log.md`.)
**48 `PLATFORM_ST` switch sites.**

Build from **WSL**, not the Windows shell:
`wsl -e bash -lc 'cd /mnt/d/d/reverse/xrick/xrick/xrick && make PLATFORM=ST'`

### 11.3 Function inventory — 199 functions in `xrick/xrick/src/`

| state | fns | files |
|---|---|---|
| **Compared against both originals** | **68** | `e_them` 11, `game` 11, `ents` 9, `maps` 9, `e_rick` 7, `e_bomb` 4, `env` 4, `util` 4, `e_box` 2, `e_bullet` 2, `e_sbonus` 2, `scroller` 2, `e_bonus` 1 |
| **Remaining** | **47** | `scr_imap` 8, `fb` 7, `tiles` 6, `sprites` 5, `scr_getname` 4 (HOF half done), `sounds` 4, `dat_picsST` 3, `img` 2, `rects` 2, `dat_maps`/`dat_spritesST` 1 each, `scr_gameover`/`scr_imain`/`scr_pause`/`scr_xrick` 1 each |
| **No counterpart in either original** | **84** | `unzip` 27, `syssnd` 19, `data` 11, `sysvid` 9, `sysarg` 4, `system` 4, `xrick` 4, `sysevt` 3, `sysjoy` 2, `devtools` 1 |

**23 defects were numbered; #18 was retracted after proving unsafe, so 22 stand fixed.**

### 11.4 Key facts a new session needs

- **T9 / A6 is SOLVED.** ST animation frames are *pointers*; the port uses *sprite
  numbers*. The map is `sprite index = (ST pointer - 0x2BE9E) / 0x150`, where `0x150` is
  `sizeof(sprite_t)` under `GFXST`. Derived from one anchor, it then correctly predicted
  five other tables the port already used. This unlocked the dynamite fuse, the box
  explosion and the corpse tumble.
- **The port's data came from a different PC build** than `ibmpc_ds1.bin` — its data
  segment sat `0x0FBA` lower. Pointer-bearing tables will therefore never match exactly;
  value tables do.
- `ENT_YDEAD(y)` in `ents.h` is the verified despawn predicate: ST `y < 0 || y > 0x142`,
  PC `y < 0 || y >= 0x140`. All six PC entity bound checks are located and mapped:
  `0x10E3`, `0x2976`, `0x2A06`, `0x23AD`, `0x2742`, `0x278B`.
- **Sound is ST-derived on both platforms.** The ST's `play_music` is `0x44CCE` and has 25
  call sites; the port has 25 trigger points. The PC used PC-speaker beeps and is **not**
  the reference for audio.
- The Hatari harness works: `python3 kb/hatari_probe.py boot` (from WSL) boots the
  analysed ST build, reaches gameplay and dumps 1 MB to `kb/hatari/ram.bin`.

### 11.5 What remains — in priority order

**R1 — Differential testing. The single largest gap; nothing substitutes for it.**
`PLATFORM_ST` is a *reconstruction*: every ST behaviour is in the tree because it was read
out of the disassembly and written in. **It has never been executed against the original.**
The harness already boots the ST build, drives it by poking the joystick byte at
`0x4922B`, sets breakpoints and dumps RAM. The work: feed identical scripted input to the
ST original and to `PLATFORM_ST`, and compare state per frame (x/y/velocity, entity pool,
score, map row); any divergence localises to a frame and a variable. DOSBox could do the
same for the PC. Until this is done, the honest claim is *"matches the disassembly as
read"*, not *"matches the original"*.

**R2 — A decision only the user can make: is `GFXPC` ever to be revived?**
`config.h` is `#define GFXST` / `#undef GFXPC`; the GFXPC sprite path **does not compile**
(`sprites_paint2` assigns `x_fb` twice, leaving `y_fb` unset, and references undeclared
`xmap`/`ymap`), and the Makefile excludes the PC data tables. So **`PLATFORM_PC` is PC
*behaviour* rendered with ST artwork and ST audio.** If GFXPC is not to be revived, say so
explicitly and describe the target as "PC behaviour" — do not leave it ambiguous.

**R3 — The 47 remaining functions**, for *what* is drawn and *when* sound plays, not *how*
SDL does it:
- `scr_imap` 8 — the level intro. Its table `screen_imapsteps` matches **no** dump under
  byte, LE16 or BE16 encodings, so it must be compared behaviourally, not by content.
- `sounds` 4 plus the four `sounds_setMusic` sites. `WAV_SBONUS2` is the one port sound
  not yet pinned to an ST track.
- `tiles` / `sprites` / `fb` / `img` / `rects` — selection, positions and clipping bounds.
  `fb`'s fades are an 8-step gamma ramp with no counterpart in either original.
- `scr_getname` — the hall-of-fame half is verified on both platforms; the entry UI is not.

**R4 — Three known port bugs, unfixed, in no-counterpart code** (`kb/xrick/divergences.md`
4.4-4.6): `ENABLE_DEVTOOLS` does not compile (`game.c:299` assigns the nonexistent
`INIT_GAME`); `data_file_size` returns an uninitialised value on the ZIP path;
`syssnd_play` can dereference `channel[-1]`.

**R5 — ST artwork pixels** (`dat_spritesST`, `dat_picsST`, `dat_tilesST`) have never been
verified byte-for-byte. Lowest value of the remaining work: A6 verified the frame
*indices*, which is what the game logic actually needed.

**R6 — Documented carry-overs, deliberately unchanged.** `map_maps[4]`: the port treats map
4 as a real map with its own start and tune, where **both** originals treat index 4 as
"game complete" (the slot is dead on all three, so it is inert). `ent_sprseq` and
`ent_mvstep` over-run their true ends into adjacent data (inert; the maximum `sni` is 244,
below the 261 valid records). `e_them.c`'s dying-enemy bound test has no PC counterpart and
fires a frame late; it is aligned to `ENT_YDEAD` and documented rather than deleted.

### 11.6 Method — the standing checks, each earned by a near-miss

- Read bounds tests for **edge sense**. Eight of the defects were `>` versus `>=`.
- **A control proves a query runs; it does not prove the query has the right shape.** A
  `cmpi.w` scan missed the ST's `cmp.w`; a `move.w #N,D0` scan missed four `moveq` sites; a
  stride-4 scan stepped over an unaligned table; three encodings existed for the same bound
  check where only one had been found.
- Locate PC code by **content signature**, never citation arithmetic. Three `ASM nnnn`
  comments in `e_rick.c` alone are wrong.
- **An inference labelled as an inference is still an inference** — an "obvious" ascending
  sprite run turned out to be a doubled table.
- **Check every consumer before changing shared code.** Defect #18 was reverted for exactly
  this: making `maps_clip`'s dead branch live broke `sprites_paint2`, which cannot take a
  signed x.
- **A row in a document is not a change in the code**, and neither is a claim in
  `review-log.md`. Sweep both periodically — 14 `xref.md` rows had never reached the code.
- **Editing files:** build the whole string, call `.encode('latin-1')`, and only then open
  `'wb'` and write. `open(f, 'w', encoding='latin-1')` truncates *before* encoding, so a
  stray non-latin-1 character emptied `e_them.c` and it had to be recovered from git.
  Prefer line-anchored edits; tabs-versus-spaces and off-by-one block lengths have broken
  string-matched edits.

### 11.7 Where the evidence is

`review-log.md` — one section per finding, in order, each with disassembly citations.
Sections R0.x-R4.x are phases 0-4; then group B (the seven bounded questions), group A (the
six structural items), group G (`game.c` and the screens), R2/R3/R4 (render, sound,
residuals) and I2/I3/I4 (the final audit items). `kb/xrick/xref.md` is the PC-vs-ST
difference worksheet; `kb/xrick/divergences.md` lists port bugs; `kb/*.md` is the ST
knowledge base; `kb/hatari.md` documents the emulator harness.
