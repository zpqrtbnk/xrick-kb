# review-log.md — the standing record for `review-plan.md`

One row per finding. A finding with no evidence citation does not belong here.

**Verdicts:** `AGREE` (port matches ST) · `PCST` (genuine PC-vs-ST difference → switch under
`PLATFORM_ST`/`PLATFORM_PC`) · `DEFECT` (wrong on both sides) · `OURS` (our earlier claim
was wrong) · `OPEN` (not yet adjudicated).

The **absence** of a finding is auditable too: a table, field or function is only "clean"
once it has a row saying so.

---

## Phase 0 — baseline

### R0.1 — build as-is ⚠️ **partially blocked**

✅ **Unblocked and done** — the user installed SDL2 (2.32.4) and zlib (1.3.1).

| id | item | status |
|---|---|---|
| B1 | Build system | ✅ **`xrick/xrick/Makefile` added.** The tree shipped an MSVC project only, expecting `..\..\lib\SDL2-2.0.9` and `..\..\lib\zlib1211` (neither in the repo). The Makefile builds the same sources against system SDL2/zlib, carries the full warning set, filters out the `GFXPC` tables (since `config.h` selects `GFXST`), and has a `make warn` target that reproduces the R0.1 evidence |
| B2 | Build | ✅ **builds and links** — `xrick`, 530,968 bytes |
| B3 | Run | ✅ **runs** — `./xrick -data ../data -nosound` starts, initialises video, loads `path='../data'`, plays until killed, exits 0 |

**Six portability fixes were needed, all outside game logic and each marked in-place with
a `review-plan.md R0.1` comment.** None changes behaviour:

| file | issue | fix |
|---|---|---|
| `data.c` | `_strdup` is the MSVC spelling | `#define _strdup strdup` for non-MSVC |
| `sysarg.c` | `#define strcasecmp _stricmp` unconditionally | guarded with `#ifdef _MSC_VER` |
| `syssnd.c` | `SDL_RWops` callback signatures widened after SDL 2.0.9 — `seek` returns `Sint64`, `read`/`write` return `size_t` | signatures updated; bodies untouched |
| `sysvid.c` | `static U8 gamma` collides with libm's `gamma()` | renamed `vid_gamma` (file-static) |
| `sysvid.c` | `SDL_LockTexture` wants `void **`; `pixelx` used as a byte pointer | explicit casts |
| `xrick.c` | `static setConsole()` — implicit `int` return is now a hard error | `static void setConsole(void)` |
| `Makefile` | pre-C99 tentative definitions of `IMG_SPLASH`/`WAV_*` in several TUs; modern GCC defaults to `-fno-common` | `-fcommon` |

**Full-build census: 228 warnings, 0 errors.**

| class | full build | **game logic only** | meaning |
|---|---|---|---|
| `-Wconversion` | 101 | 76 | implicit narrowing — **phase 2 input** |
| `-Wsign-conversion` | 61 | 23 | signedness — **phase 2 input** |
| `-Wunused-variable` | 16 | 3 | cosmetic |
| `-Wtype-limits` | 11 | **10** | **always true/false** — see W1 |
| `-Wpointer-sign` | 10 | 0 | platform layer |
| `-Wsign-compare` | 5 | 0 | platform layer |
| `-Wparentheses` / `-Wdangling-else` / `-Wmisleading-indentation` / `-Wmaybe-uninitialized` | 14 | **0** | ✅ **all in `unzip.c` (third-party) and `data.c` (loader) — none in game logic** |
| `-Woverflow` | 1 | 1 | see W2 |

That last row is a genuine clean result: the warning classes that most often mark a real
logic bug — dangling `else`, misleading indentation, `&&`/`||` precedence, possibly
uninitialised reads — **do not occur anywhere in the 6,962 lines under review.** The
11th `-Wtype-limits` is `syssnd.c:157`, platform layer, so the game-logic count stands at
exactly ten.

| class | count | meaning |
|---|---|---|
| `-Wconversion` | 76 | implicit narrowing — **phase 2 input** |
| `-Wsign-conversion` | 23 | signedness — **phase 2 input** |
| `-Wtype-limits` | 10 | **comparison always true/false** — see W1 |
| `-Wunused-variable` | 3 | cosmetic |
| `-Wunused-but-set-variable` | 1 | cosmetic |
| `-Woverflow` | 1 | see W2 |

Conversion warnings concentrate where the game logic is densest: `e_them.c` 25,
`scr_imap.c` 11, `maps.c` 11, `scr_getname.c` 10, `e_rick.c` 8, `ents.c` 6.

---

### W1 — always-false comparisons: **ten, not the seven on record** ⭐

`xrick/re/divergences.md` §4.2 lists seven `if (x < 0)` tests on unsigned values that can
never fire. The compiler finds **ten**. Three are new to us:

| id | site | code | verdict |
|---|---|---|---|
| W1.1 | `e_bullet.c:63` | `if (E_BULLET_ENT.x <= -0x10 \|\| E_BULLET_ENT.x > 0xe8)` — `x` is `U16`, so the left-edge test is dead | `OPEN` — bullets may still expire via `U16` wrap making `x > 0xe8`; **check against ST** |
| W1.2 | `e_rick.c:132` | `if (E_RICK_ENT.y < 0 \|\| E_RICK_ENT.y > 0x0140)` — death-when-off-screen never fires upward | `OPEN` — same wrap question |
| W1.3 | `maps.c:349` | `maps_clip()`: `if (*x < 0)` on a `U16*`, and `if (*x + *width < 0)` inside it | `OPEN` — **the partial left-clip path `*width += *x; *x = 0;` is unreachable.** A rectangle straddling the left edge is either dropped whole or drawn wrong. Note the `y` branch is written against `MAPS_TOPHEIGHT_PX`, not 0, and *does* work |
| W1.4–10 | `e_rick.c:217,411`, `e_them.c:164,298,312,392,638` | already recorded in `divergences.md` §4.2 | `OPEN` |

All ten resolve in phase 2 (R2.1–R2.4) once each field's true width is established from
Ghidra. **None may be "fixed" by widening a type until the ST access width is known** —
the wrap may be load-bearing.

### W2 — `E_RICK_STRST(0xff)` overflow

`game.c:741` calls `E_RICK_STRST(0xff)`, expanding to `e_rick_state &= ~0xff`, i.e.
`&= 0xFFFFFF00`, truncated into a `U8` = 0. **Benign** — clearing all state is the
intent — but it is the only `-Woverflow` in the tree and reads as an accident.
`e_rick_state = 0` says it directly. Verdict `DEFECT` (clarity only, no behaviour change).

---

## Phase 1 — data-table provenance

The user's open question: nobody knows whether `dat_*.c` was extracted from the PC or the
ST build. **Measured so far — the answer is mixed, which is why the census is worth doing.**

| id | table | port | ST (`re/`) | verdict |
|---|---|---|---|---|
| D1 | `map_marks` | 523 records | `placement_table[523]` @ `0x481E4` | ✅ `AGREE` — **value-identical, 523/523 on every comparable field** (`ent`, `flags`, `xy`, `lt`). ST stores the band as a word; the port and the PC as a byte (PC `mark_t` stride 5, from `ADD BX,5`). Same values |
| D2 | `map_connect` | 153 = 106 + 47 | 153 = 106 + 47 @ `0x478B2` | ✅ `AGREE` — **all 47 lists match**, list 17 included |
| D3 | `ent_entdata` | 74 × 8 packed bytes | `object_type_defs[75]` × 16 @ `0x47D34` | ⚠️ `OPEN` — `trig_w`/`trig_h`/`snd` agree **74/74**; **`w`/`h` differ in 3**: idx **3, 22, 23**, ST `0/0` vs port `24/21`. Structures differ by design (T9: ST holds pointers, PC holds sprite numbers) |
| D4 | `map_submaps` | 47 × `{page,bnum,connect,mark}` | `RoomHeader[47]` @ `0x47620` | ✅ `AGREE` — **47/47 on every comparable field.** Requires translating ST *pointers* into port *indices*: `pTransitions` → connector index, `pPlacements` → mark index. All 47 translate exactly, which also independently re-confirms D1 and D2 |
| D5 | `map_maps` | 5 × `{x,y,row,submap,tune}` | `LevelStartInfo[5]` @ `0x4B522` | ⚠️ **`PCST` + `OPEN` — only 2 of 5 agree.** See D5a/D5b |
| D6 | `map_eflg` | `map_eflg_c[32]`, **run-length encoded** | two **256-byte** per-tile LUTs @ `0x49F1E` / `0x4A01E` | ⚠️ **mostly `AGREE`, two live differences** — see D6a–D6c. Not a different data model after all: `map_eflg_expand()` inflates the 32 RLE bytes into a 256-entry table, directly comparable to ours |
| D6b | `map_bnums` (`0x1FD8`) | — | tile-map blocks | ⬜ `OPEN` |
| D7 | `ent_sprseq` (`0x88`), `ent_mvstep` (`0x310`) | — | — | ⬜ `OPEN` |
| D8 | `dat_tilesST` (+ sprites, pics) | `tiles_banks[3][256]`, `U32[8]` per tile | tile banks @ `0x1D01E` / `0x1F01E` | ⚠️ **`OPEN` — and this is the one that looks genuinely unresolved.** See D8a |

### D6a — the five gameplay-critical attribute bits agree **perfectly** ✅

`map_eflg_c` is `{count, value}` RLE, expanded by `map_eflg_expand(offs)` with `offs`
`0x00`/`0x10` per tile page. Expanding both banks and comparing against our LUTs:

| bit | meaning (port / ours) | bank 0 | bank 1 |
|---|---|---|---|
| `0x80` | VERT / chase-enabling | **256/256** | **256/256** |
| `0x40` | SOLID | **256/256** | **256/256** |
| `0x20` | SPAD / bounce | **256/256** | **256/256** |
| `0x10` | WAYUP / one-way | **256/256** | **256/256** |
| `0x04` | LETHAL | **256/256** | **256/256** |
| `0x08` | FGND | 186/256 | 213/256 |
| `0x02` | CLIMB / ledge | 252/256 | 250/256 |
| `0x01` | (unnamed) | 179/256 | 201/256 |

**Collision, lethality, ladders, one-way platforms and super-pads are byte-identical
across all 512 tile entries.** That is the behavioural core of the tile system.

A three-way confirmation fell out: the port's `util.c` probe masks expand to
`SOLID|SPAD|FGND|LETHAL|01` = **`0x6D`**, `…|CLIMB|01` = **`0x6F`**,
`…|WAYUP|…` = **`0x7D`** — exactly the PC binary's `AND AL,0x6D/0x6F/0x7D` and our ST
reading (S7).

### D6b — `0x02` CLIMB/ledge differs on tiles that are actually used ⭐ **candidate difference**

| bank | differing tiles | port | ST |
|---|---|---|---|
| 0 | 252, 253, (254, 255) | `0x80` | `0x82` |
| 1 | 250, 251, 252, 253, (254, 255) | `0x80` | `0x82` |

**These are not dead padding.** `map_blocks` references tile 250 fourteen times, 251
fourteen, 252 six and 253 six — **40 live references**; only 254/255 are unreferenced
(max tile index used is 253). So on the ST those tiles carry the ledge/climb bit and on
the PC they do not, and `0x02` is inside the `0x6F` centre-column mask, so it reaches the
probe result. Verdict **`PCST` candidate** — confirm in `ibmpc_cs.bin`, then switch.

### D6c — `0x08` FGND, and a claim in `re/` that needs re-examination ⚠️

`0x08` differs on 70 tiles in bank 0 and 43 in bank 1. The port **reads it**, in two
places: `sprites.c:147` and `sprites.c:240` use `MAP_EFLG_FGND` to hide entities behind
foreground tiles, and it appears in every `util.c` probe mask.

But `re/algo-entities.md` and `re/hatari.md` probe 1 both state that bits `0x01` and
`0x08` are *"inert background classes tested by no reader"*, with the ST's three LUT
readers enumerated by Ghidra xref. **That sits uneasily with the ST's own `0x6F` mask,
which contains both bits.** Either the ST accumulates them and discards them at the final
`(D0 & 0xD0)` blocked test — in which case "tested by no reader" is imprecise rather than
wrong — or a reader was missed.

✅ **Resolved 2026-09-04 — `re/` was right, and is now backed by stronger evidence.**

Reading `probe_player_tile_collision` (`0x4CD70`) to its end shows the accumulated `D0` is
AND-ed with a runtime mask (`and.b (0x4BF16).l,D0b` @ `0x4CFE4`) and then stored **whole**
to `player_collision_flags` (`move.b D0b,(0x4D00A).l` @ `0x4CFEA`) — so bits `0x01` and
`0x08` *do* survive into that variable. The question is therefore what **consumes** it.

All seven consumers are `btst.b #n,(0x4D00A).l`:

| site | bit | meaning |
|---|---|---|
| `0x4C1BA` | 5 | `0x20` SPAD/bounce |
| `0x4C24C`, `0x4C752` | 7 | `0x80` VERT/chase |
| `0x4C300`, `0x4C7A4` | 1 | `0x02` CLIMB/ledge |
| `0x4C71A` | 6 | `0x40` SOLID |
| `0x4C8B4` | 2 | `0x04` LETHAL |

plus the blocked/carry test `andi.b #0xD0` at `0x4CFF0` → bits 7, 6, 4.

**Union of every bit with any effect: `0xF6`. Bits `0x01` and `0x08` are read by nothing.**
So `re/`'s claim stands — and the evidence is now an enumeration of the *consumers* by
`btst` bit number, which is stronger than the LUT-reader xref it originally rested on.

**Consequence: FGND is a PC-only feature.** The ST computes the bit and discards it; the
port uses it for foreground masking (`sprites.c:147`, `:240`). Under the switchable scheme
the ST build simply has no foreground masking, and the 70/43 differing `0x08` values are
**inert on the ST side** — no switch needed, only a comment saying why.

### D5a — Rick's starting X differs on levels 3 and 4 ⭐ **new PC-vs-ST difference**

`map_maps[k]` and `LevelStartInfo[k]` are confirmed aligned — the `submap`/`roomIdx`
pair matches for all four real levels (`0, 9, 20, 38`) — so the rows are directly
comparable:

| map | port `x` | ST `wStartX` | port `y` / ST | port `row` / ST | verdict |
|---|---|---|---|---|---|
| 0 | 8 | 8 | 139 / 139 | 8 / 8 | ✅ agree |
| 1 | 8 | 8 | 139 / 139 | 104 / 104 | ✅ agree |
| **2** | **16** | **8** | 139 / 139 | 16 / 16 | ⚠️ **differs** |
| **3** | **16** | **8** | 139 / 139 | 16 / 16 | ⚠️ **differs** |

Everything else on those rows matches. Verdict **`PCST`** — a genuine divergence, and one
not previously on the 17-row list. Candidate for a `PLATFORM_ST`/`PLATFORM_PC` switch once
confirmed in `ibmpc_cs.bin`.

### D5b — `map_maps[4]` has no ST counterpart

Port entry 4 is `{x=0x74, y=0xC8, row=8, submap=0x26, "tune4.wav"}`. ST entry 4 reads
`{x=8, y=0x8B, row=8, roomIdx=0}` — a duplicate of entry 0's start, and `re/` records
that the 5th `pIntroText` points at the **game-ending text**, not a fifth level, with
`process_level_transition_point` treating `level_index == 4` as game-complete.

So the two builds use slot 4 for different things: the ST as an ending-text holder with
dead position fields, the port as a real map with its own start position and tune.
**`OPEN`** — resolve by reading what the PC binary does with map 4 before deciding whether
this is a divergence, a port invention, or a misreading on our side.

---

**Reading so far: the map, placement, connector and room data is common to both versions
(D1, D2, D4 — 523/523, 47/47, 47/47). The entity templates and the level start table are
not (D3, D5).**

**Method note — mandatory.** Table records are counted with comments stripped and brace
depth tracked, **never** with a naive `\{([^{}]*)\}` regex. That regex matches braces
inside comments and has produced **two** phantom defects in this project, one of which
(`map_connect`) stood for five days and reached a drafted upstream bug report before being
retracted. See `PLAN.md` T10.

---

## Corrections to our own earlier claims

| id | claim | status |
|---|---|---|
| C1 | "The port's `map_connect` holds 154 records in an array declared 153" | ❌ **`OURS` — retracted 2026-09-04.** The 154th was a commented-out record the author had *already* removed (`/* was {0000, 0x38, 0x13, 0x68} ?? - now OK */`). Table and bound are both correct |
| C2 | "`ent_entdata` has 76 initialisers against a declared 74" | ❌ **`OURS`** — same regex artifact, caught before it was reported. True count 74, exactly as declared |
| C3 | "The extra ST `object_type_defs` entry (type 74) is the intro-screen decorative sprite" | ⚠️ **imprecise.** Type 74 *is* the intro sprite's dispatch type, but its template entry is **all zeros** — `show_level_intro_screen` configures that entity by hand from its `sprite_def` argument rather than from the table |

---

## Next

- **R1.1** finish the table census (D4–D8), scripted and re-runnable.
- **R1.4** emit our own ST extraction in `dat_*.c` format, so the diff *is* the audit.
- **B1** unblock the full build — needs the user.

---

## Phase 1 applied — the ST build now uses ST tables ✅

**User instruction 2026-09-04: "when building in ST platform mode we use the ST tables."**
Done, and verified in both binaries.

### The switch itself

`config.h` gains `PLATFORM_ST` / `PLATFORM_PC`, **independent of `GFXST`/`GFXPC`** (which
select artwork only — the stock build was ST artwork on PC logic). Defining both, or
neither, is an `#error`. The default is ST, and either can be forced from the build
(`make PLATFORM=PC`) so both configurations stay buildable — the `review-plan.md` §10 risk
about an unbuilt path rotting.

**Verified:** both configurations compile and link, the binaries differ, and byte-searching
each for the two table forms confirms the right one is present and the other absent:

| | ST table bytes | PC table bytes |
|---|---|---|
| `xrick-ST` | **FOUND** | absent |
| `xrick-PC` | absent | **FOUND** |

Same result for `ent_entdata[22]`. The ST build runs.

### What was switched, and why each was safe

| table | change | basis |
|---|---|---|
| `map_eflg_c` | ST run values under `PLATFORM_ST` | The ST LUTs re-encode to **exactly 8 runs per bank**, a perfect fit for the port's existing 32-byte format — and the run **lengths are identical** to the PC's (77, 14, 4, 87, 8, 3, 59, 4 / 55, 4, 4, 144, 9, 1, 33, 6). Only the values differ, in bits `0x01`, `0x02`, `0x08`, exactly as D6a measured. This is the real fix for **D6b**: the ST build now marks tiles 250-253 `0x82` (VERT\|CLIMB) as the ST does |
| `map_maps` | start X `0x08` for maps 2 and 3 under `PLATFORM_ST` | **D5a.** Everything else on those rows already matched |
| `ent_entdata` | rows 3, 22, 23 take the ST's blank `w`/`h` | **D3** — see below |

### The `ent_entdata` rows: switched only after proving the change is inert

These three rows needed care, because types 22 and 23 are placed **13 times each** — so a
naive switch could have broken 26 live entities. Checking rather than assuming:

- **Row 3 (bomb)** — type 3 is placed **0 times** in all 523 placement records, and
  `e_bomb_init` sets the entity directly. The row is never read.
- **Rows 22/23** — `re/entities.md` records these as *"invisible trigger points (gfx=0)"*,
  which is exactly why the ST template is blank (null `anim_frame_table`, zero `w`/`h`).
  **The port already implements the same behaviour in code**: `e_sbonus_start` and
  `e_sbonus_stop` both set `ent.sprite = 0`, and test contact with `u_trigbox()`, which
  reads only `trig_x`/`trig_y`/`trig_w`/`trig_h` — **never `w`/`h`**. And `trig_w`/`trig_h`
  agree 74/74 between the builds.

So the two encodings express the same intent — the ST in data, the port in code — and the
switch changes nothing observable. Recorded because "provably inert" is a finding, not an
excuse to skip the check.

### Not switched, deliberately

`map_maps[4]`. The ST uses that slot to carry the game-ending text with dead position
fields (`level_index == 4` means "game complete"); the port treats it as a real map with
its own start and `tune4.wav`. Changing it could alter the ending sequence, and **D5b** is
still open. Left as the port has it under both platforms, with the reasoning in a comment
at the site.

---

### D8a — the ST artwork tables ✅ **verified ST. My first conclusion was wrong — retracted.**

❌ **Retraction.** This entry previously read *"the ST artwork tables do not line up with
our ST binary"*, citing 20/256 and 3/256 contiguous matches. **That was a false negative
of my own making.** I scanned candidate bases as `range(0x1A000, 0x2C000, 32)`, which is
32-aligned to `0x1A000` — and `0x1D01E` is not congruent to `0x1A000` mod 32, so **the
scan never tested the documented bases at all.** Testing them directly settles it
immediately.

**The port's ST tiles are our ST tiles.**

| port bank | ST source | result |
|---|---|---|
| **1** | tile bank @ `0x1D01E` | **256/256 exact** |
| **2** | tile bank @ `0x1F01E` | **256/256 exact** |
| **0** | font/HUD region @ `0x1B01E` | **256/256 present**, permuted |

And the bank assignment corresponds exactly: `maps.c:110` selects
`map_tilesBank = (page == 1) ? 2 : 1`, while the ST's `wTileBankVariant` selects
`0x1D01E` for 0 and `0x1F01E` for nonzero. Page 0 → port bank 1 → `0x1D01E`; page 1 →
port bank 2 → `0x1F01E`. Bank 0 is the HUD/menu bank (`env.c` sets it for the status bar).

**Bank 0's permutation is documented in the port's own source.** Each tile carries a
comment giving its source index, and those comments are exactly the ST glyph numbers:

```
port[0][0..11] comments:  0x11 0x0a 0x0b 0x0c 0x0d 0x10 0x0f 0x12 0x13 0x14 0x15 0x16
measured ST glyph index:    17   10   11   12   13   16   15   18   19   20   21   22
```

**The format transform** (needed for any of this) is: the port's `tile_t` is `U32[8]`, one
row per element, **8 pixels at 4 bits per pixel with the leftmost pixel in the high
nibble** (`tiles_paint`, `tiles.c:79-83`); the ST stores four bitplanes, 4 bytes per row.
Converting ST → port and comparing is exact.

**Conclusion: `dat_tilesST.c` is genuine ST artwork, byte-for-byte, and needs no change
under `PLATFORM_ST`.** `dat_spritesST` and `dat_picsST` remain unchecked but the same
method now applies to them, and the presumption is now strongly that they are ST too.

**Method lesson — the fourth false negative in this project from a query that could not
have found what it sought.** Previous three: the padded-operand Ghidra search (twice), and
the comment-matching brace regex. Here: a scan stride that skipped every real candidate.
**Always include the known-expected answer in the search space and confirm the search
finds it, before reporting an absence.**

---

## Phase 2 — data structures and variable widths

### R2.1 — ST `SpriteEntity` access-width census ✅ **complete**

Method: a **program-wide** instruction search over `atari_ram.bin` for every `(d16,An)`
effective address — 256 `A0` matches across 4,608 instructions, **not truncated** — plus
the `A1` write sites in `init_entity_from_placement`. Every field's width is therefore
measured from the object code, not inferred.

| off | field | ST width(s) |
|---|---|---|
| `0x00` `0x02` `0x04` `0x06` `0x08` `0x0C` `0x0E` `0x10` `0x12` `0x14` `0x2A` `0x2C` `0x2E` `0x30` `0x3C` `0x3E` `0x40` `0x42` `0x44` | wType, nDirection, nPosX, nPosY, nVelY, nSpawnX/Y, nHitboxW/H, nRow_count, anim/path indices, trigger box, wTriggerSound | **word** |
| `0x22` `0x26` `0x32` `0x36` | gfx_data, placement ptr, anim table, movement path | **long** |
| `0x46` `0x47` `0x48` `0x49` `0x4A` | bTriggerFlags, bAnimActive, bChasing, bDying, bAiCooldown | **byte** |
| `0x07` | nPosY **low byte** | **byte** (the documented tile-snap sites) |
| `0x0A` `0x16` `0x1C` `0x3A` | nPosYFrac, both render-flag bytes, wHazardActive | ⚠️ **mixed byte *and* word** |

### R2.1a — the port's width comments are wrong; its declared types are right ⭐

`review-plan.md` §5 flagged five `ent_t` fields whose declared C type contradicts their
own comment — `x` (`b02`), `trig_x` (`b16`), `xsave` (`b1C`), `c1` (`b26`), `c2` (`b28`) —
as the likely width bugs. **The census says the opposite.** The ST accesses the
corresponding fields (`nPosX` `0x04`, `nTrigBoxXMin` `0x3C`, `nSpawnX` `0x0C`) as **words
at every site**, so `U16` is correct and **the comments are the wrong part**.

This is a direct vindication of the user's instruction of 2026-09-04 not to trust the
port's comments. Those five are **not** defects; the comments should be corrected instead.

### R2.1b — the real defect is signedness ⭐ **explains 9 of the 10 dead comparisons**

The ST treats position as **signed**: `render_sprites` does
`moveq #0,D1 / move.w (0x4,A0),D1w / cmp.w #-0x8,D1w / bge` — a signed 16-bit compare
against **−8** — and the same shape for `nPosY` against `0` and `0x142`.

The port declares `U16 x, y`, which is why `if (x < 0)` and `if (x <= -0x10)` are dead
(W1). **The fix is `S16`, not a wider type.**

⚠️ **Not applied yet, deliberately.** Changing these to `S16` makes all nine comparisons
start firing, so the behaviour behind each must be checked against the ST in the same
change — several may currently "work" by `U16` wrap (a bullet moving left wraps to
`0xFFFF` and exits via the `> 0xe8` test instead). This is a phase-3 change, made with
`e_rick.c` / `e_them.c` / `e_bullet.c`, not a blind retype. `maps.c:349` (`maps_clip`) is
separate — its arguments are rectangle coordinates, not entity fields.

### R2.1c — four mixed-width fields, one with a value consequence

- **`0x3A wHazardActive`** — tested `tst.w`, set two different ways: `move.w #0xff`
  (`0x4D080`) gives `0x00FF`, but `move.b #-0x1,(0x3a,A0)` (`0x4D170`, `0x4D284`) writes
  the **high** byte, giving `0xFF00`. Both are non-zero so the `tst.w` behaves the same,
  but **the stored value differs**. `re/data-structures.md` describes it as "0xFF while
  lethal", which is true of only one of the two writes. A reimplementation storing `0x00FF`
  everywhere is observationally equivalent *today*, but the ST does not.
- **`0x0A nPosYFrac`** — word everywhere except `clr.b (0xa,A1)` at spawn, which clears
  only the high byte.
- **`0x16`/`0x1C` render flags** — byte bit-ops (`bclr`/`bset`) plus `move.w #0x0` clearing
  flags and pad together. Already documented.

**Exit state:** every one of the 33 `SpriteEntity` fields now carries a measured ST width.
No field was left inferred.

### R2.2 — the remaining structures ✅

| port struct | ST counterpart | verdict |
|---|---|---|
| `mark_t` — 5 × `U8` | `PlacementRecord` — 6 bytes | ⚠️ ST `wSpawnBand` is a **word** (`+0`), the port's `row` is `U8`. All four remaining fields are byte on both (`btst.b`, `cmpi.b`, `move.b` at `0x496B0`-`0x49824`), and the ST stride is 6 (`lea (0x6,A0),A0`). **Values identical** (D1) |
| `connect_t` — 4 × `U8` | `TransitionWaypoint` — 10 bytes | model difference: the port stores a **submap index**, the ST a **long pointer** to the `RoomHeader` (`cmpi.l #-1,(0x4,A0)`), with `rowout`/`rowin` as words. **Lists equivalent** (D2) |
| `submap_t` — 4 × `U16` | `RoomHeader` — 14 bytes | model difference: indices vs pointers (word + three longs). **Equivalent** (D4) |
| `map_t` | `LevelStartInfo` — 20 bytes | model difference + the start-X divergence (D5a) |
| `entdata_t` — 8 packed bytes | `ObjectTypeDef` — 16 bytes with pointers | model difference by design (T9); three rows switched (D3) |
| `mvstep_t` — `{U8 count; S8 dx, dy}` | 3 **words** `{duration, dX, dY}` | ⚠️ **width and sentinel differ.** ST: `add.w D0w,D0w` ×3 → stride **6**, terminator `cmpi.w #-0x1` = `0xFFFF`, deltas added with `add.w D1w,(0x4,A0)`. Port: 3 bytes, terminator `count != 0xff`. Same intent, half the width. Values not yet compared — that is D7 |
| `hscore_t` — `{U32 score; U8 name[10]}` | 30-byte record | ⚠️ **representation difference** — see R2.2a |

### R2.2a — the high-score record: two different number representations

The ST does **not** store the score as a number. It stores **six unpacked decimal digits,
one per byte**: `+0x02` is a word holding 2 digits, `+0x04` a long holding 4. Entry 0 reads
`00 00` / `08 00 00 00` → digits `0,0,8,0,0,0` → **8000**. That layout is what makes the
insertion sort work with plain `cmp.w`/`cmp.l` on the raw bytes — big-endian unpacked
decimal compares numerically. The port stores a binary `U32`.

**All eight default entries match exactly**, once the pad byte is mapped:

| # | score | name |
|---|---|---|
| 0-7 | 8000, 7000, 6000, 5000, 4000, 3000, 2000, 1000 | SIMES, JAYNE, DANGERSTU, KEN, ROB N BOB, TELLY, NOBBY, JEZEBEL |

**Pad character differs**: the ST pads names with `0x5E` (the blank glyph, `re/strings.md`),
the port with `'@'` (`0x40`). Every name matches under that mapping, including
`ROB^N^BOB^` where `0x5E` doubles as a word separator. This is each build's own character
set, not a defect — but any code that writes a name must use the right pad for its
platform.

⚠️ **One consequence worth flagging for phase 3:** the ST record holds **six digits**, so
it saturates at `999999`; the port's `U32` does not. With the end-of-game bonus at
100,000 per remaining life, a maximal run can approach that ceiling, and the two builds
would then diverge. Not yet checked against the ST's score-add path.

**Exit state:** all seven structures adjudicated. Three are genuine model differences
(pointer-vs-index, packed-vs-pointer, digits-vs-binary) that follow from the two data
models and are not defects; two carry width differences (`mark_t.row`, `mvstep_t`); one
is switched already (`entdata_t`); one has a divergence recorded (`map_t`).

### R2.4 — signedness and narrowing sweep ✅

99 `-Wconversion`/`-Wsign-conversion` warnings in game logic: **60 narrow to `U16`,
16 to `U8`**, the rest are macro expansions. Adjudicated against the ST widths from R2.1.

**The 60 `U16` narrowings are correct by construction.** C promotes to `int`, computes
wide, then truncates on store; the 68000 computes at **word width throughout**
(`add.w`, `addi.w`, `move.w`). The results agree except where a 16-bit intermediate would
overflow, which the ST would also lose. No action.

**The `U8` narrowings, individually:**

| site(s) | verdict |
|---|---|
| `ylow = i` — `e_rick.c:129,190`, `e_them.c:134,305,433` | ✅ **correct** — see R2.4a |
| `ent.sprite = sprbase + ...` — `e_them.c:142,291,366,462`, `e_rick.c:523` | ✅ **port-internal.** The ST has no `sprite` field at all; it holds `gfx_data`/`anim_frame_table` **pointers** (T9). Nothing to match |
| `n &= ~ENT_LETHAL` — `e_them.c:633,699`, `maps.c:230` | ✅ benign — `~0x80` is `-129` as `int`, truncating to `0x7F`. Same class as W2's `E_RICK_STRST(0xff)`. Correct, just noisy |
| `map_frow = map_frow - rowout + rowin` — `maps.c:208` | ⚠️ **width differs — see R2.4b** |
| `game_period` — `game.c:185` | port-only (frame pacing), no ST counterpart |

### R2.4a — the fixed-point integration: the port's 16.8 really is equivalent to the ST's 16.16

The ST integrates position as **16.16**, not 8.8:

```
moveq  #0,D1
move.w (0x6,A0),D1w      ; y
swap   D1                ; y << 16
move.w (0xa,A0),D1w      ; | frac      -> 16.16 accumulator
move.w (0x8,A0),D7w      ; nVelY
ext.l  D7                ; SIGN-EXTEND  <-- nVelY is signed
lsl.l  #0x8,D7           ; vel << 8
add.l  D1,D7
swap   D7 / move.w D7w,(0x6,A0)    ; y    = high word
swap   D7 / move.w D7w,(0xa,A0)    ; frac = low  word
```

The port uses `i = (y << 8) | ylow; i += offsy; y = i >> 8; ylow = i;` — **16.8**.

**They are equivalent**, because `vel << 8` has its low 8 bits zero: the velocity add can
never alter the bottom byte of the ST's 16-bit fraction. The ST's effective precision is
therefore 8 fraction bits, exactly the port's. So `U8 ylow` is **right**, and these five
warnings are benign.

Two things fall out of reading it properly:

- **`ext.l D7` proves `nVelY` is signed** — the port's `S16 offsy` is correct. This is the
  same evidence class that shows `x`/`y` should be `S16` (R2.1b), and here the port
  already has it right.
- ⚠️ **A sub-pixel residue the port cannot reproduce.** At spawn the ST does
  `clr.b (0xa,A1)` — clearing only the **high** byte of the fraction (R2.1c). The low byte
  keeps whatever the slot's previous occupant left, and nothing ever clears or adds to it.
  It is worth at most `255/65536` of a pixel and can never affect the integer position, so
  it is unobservable — but it is a real difference between the two models, and worth
  knowing before anyone "fixes" the port to 16.16 and wonders why it still differs.

### R2.4b — `map_frow`: `U8` in the port, **word** on the ST

`world_row_base` (`0x495CA`) is accessed as a word at every site —
`add.w (0x495ca).l,D1w` (`0x49696`), `add.w …,D0w` (`0x49A2E`),
`move.w (0x495ca).l,D1w` (`0x49B1A`), `move.w D1w,(0x495ca).l` (`0x49B22`) — and
`start_level` seeds it with `move.w (0x8,A0),(0x495ca).l`.

The port declares `U8 map_frow` (`maps.h:159`) and computes
`map_frow - rowout + rowin` in `int`, truncating back to 8 bits. Shipped row values stay
well under 256 (the largest level start row is `0x68`), so no divergence is expected in
practice — but the widths differ and an intermediate that went negative would wrap at 8
bits on the port and at 16 on the ST. `OPEN`, low priority, to confirm in phase 3 alongside
`maps.c`.

### R2.3 — module-level globals ✅ (32 in game logic)

Widths mostly agree with the ST: `env_lives`/`env_bombs`/`env_bullets` are `U8` against
the ST's `bLives`/`bDynamite`/`bBullets` **bytes** in `HudCounters` (`0x4B326`); `env_map`
is `U16` against `level_index` **word**; `control_status` is `U8` against
`joystick1_state` **byte**. Two exceptions: `map_frow` (R2.4b) and the score.

### R2.3a — the score: packed BCD on the ST, binary `U32` in the port ⭐

`add_score` (`0x4B3E4`) is unambiguous:

```
move.l D0,(0x4b51e)        ; the delta, low 3 bytes = packed BCD
lea    (0x4b329),A0        ; one past the 3-byte score at 0x4B326-28
lea    (0x4b522),A1        ; one past the delta
andi   #-0x12,CCR          ; clear X and Z
abcd   -(A1),-(A0)         ; three packed-BCD adds, LSB first
abcd   -(A1),-(A0)
abcd   -(A1),-(A0)
... unpack the 3 BCD bytes into 6 display digits at 0x4B330-0x4B335 ...
move.b #-0x1,(0x4b350)     ; HUD dirty
```

So the ST score is **6-digit packed BCD**, and the third `abcd`'s carry-out is
**discarded** — no clamp. **The ST score wraps at 1,000,000 → 000000.** The port's
`U32 env_score` does not.

✅ **The score *values* match.** The ST's BCD constants read as their decimal faces:
`add_score(0x50)` = 50 and the port has `+= 50`; `add_score(0x500)` = 500 and the port has
`+= 500`; the end-of-game bonus `add_score(0x100000)` = 100,000 per life. The port's author
read the BCD correctly — no confusion between `0x500` and 1280.

⚠️ **But the wrap is reachable.** At 100,000 per remaining life plus gameplay score, a
completed run can pass 999,999, after which the ST rolls over and the port keeps counting.
`OPEN` — a `PLATFORM_ST` candidate once the PC's own behaviour is read from
`ibmpc_cs.bin`.

The port's display unpack (`env.c:71`, `for (i = 5, sv = env_score; i >= 0; i--)`) mirrors
the ST's unpack into `0x4B330`-`0x4B335`, and `scr_getname.c`'s `U32` comparisons are
equivalent to the ST's digit compares for any value below the wrap.

### R2.3b — the doubled dynamite kill score ⭐ **the port awards half**

On the ST, `kill_enemy` (`0x4D87C`) **itself** awards score:

```
0004d88c  move.l #0x50,D0
0004d892  bsr.w  add_score
0004d896  move.w #0x13,D0w / jsr play_music
```

and the caller adds a **second** `0x50` on one specific path (`enemy_ai_update` at
`0x4D542`):

```
0004d542  bsr.w  0x4cc92          ; explosion_overlaps_entity
0004d546  bcc.b  0x4d554          ; miss -> try the other test
0004d548  move.l #0x50,D0
0004d54e  bsr.w  add_score        ; <-- FIRST 0x50
0004d552  bra.b  0x4d55a
0004d554  bsr.w  0x4cc10          ; the other contact test
0004d558  bcc.b  0x4d562
0004d55a  bsr.w  kill_enemy       ; <-- adds the SECOND 0x50
```

**So an enemy killed by the explosion scores 100 on the ST; by the other path, 50.**

The port has **exactly one** score add for enemies — `env_score += 50` in
`e_them_gozombie` (`e_them.c:81`), its `kill_enemy` equivalent — and no second add on any
path. **The port awards 50 for a dynamite kill where the ST awards 100.**

`OPEN` — genuine divergence, but which kind is not yet decided: a real PC-vs-ST difference
(switch it) or a port omission (fix it). Resolve by reading the PC's `e_them` scoring in
`ibmpc_cs.bin`. This is the first *behavioural* difference phase 2 has turned up that is
not a width or representation question.

### R2.3b follow-up — attempted adjudication against the PC binary, **not resolved**

Recorded so the same ground is not covered twice. Four approaches tried, all negative:

| approach | result |
|---|---|
| Apply the `+0x17E` delta to `e_them_gozombie`'s `ASM 237B` → `0x24F9` | ✗ that region is entity **physics** (`offsy`/`ylow` handling), not the kill path. **Confirms again that the delta is per-module, not global** (`xrick/re/provenance.md`) |
| Search for score constants as 16-bit immediates (`0x50`, `0x500`, `2000`, and their decimal forms) | ✗ only `MOV AX,0x2000` at `0x1B3E`/`0x1E30`, and both are **video setup** — `MOV DS,0x271D` … `MOV [0x4907],AX` — not the super bonus |
| Locate a BCD score routine via x86 `DAA`/`DAS`/`AAA`/`AAS` | ✗ the four `0x27` candidates are bytes **inside `MOV AX,0x271D`**, not instructions. No BCD adjust found in context |
| Infer the score variable from the port's `e_sbonus.c:47-49` annotations (`6DD5`, `6DDB`, `291A-291D`) | ✗ those are **data-segment** addresses, and we hold only the code segment (`review-plan.md` §10) |

**Still `OPEN`.** The remaining method is the one that worked for `e_bomb_hit`: find the
PC's enemy-kill path **structurally** — by the shape of the code around the two contact
tests and the call that follows — rather than by constant search. Until then, whether the
port's single `+= 50` is a PC-vs-ST divergence or an omission is undecided, and it must not
be "fixed" either way.

### R2.3b ✅ **RESOLVED 2026-09-04 — genuine PC-vs-ST difference, and switched**

Settled structurally, the way `e_bomb_hit` was — not by constant search.

**Locating it.** T8 had already found the death-launch `MOV word[SI+0x2C],0xFC00` at
`0x24C8`, and the port sets `offsy = -0x0400` inside `e_them_gozombie`. So the routine is
right there — it starts at **`0x24C3`**:

```
24C3  C6 04 47              MOV  byte[SI],0x47        ; n = 0x47 (zombie)
24C6  C7 44 2C 00 FC        MOV  word[SI+0x2C],0xFC00 ; offsy = -0x400
24CB  B8 A9 7D / A3 9A 7D   MOV  [0x7D9A],0x7DA9      ; sound
24D2  56 / BE 28 49         PUSH SI / MOV SI,0x4928   ; -> the 5-digit score delta
24D6  E8 ..                 CALL 0x0292               ; <-- the score add
24D9  5E                    POP  SI
24D9  F6 44 14 01 / 74 ..   TEST byte[SI+0x14],0x01   ; ENT_FLG_ONCE
24E2  8B 5C 12 / 43 / 80 0F 80                        ; map_marks[mark].ent |= NACT
24E9  C6 44 26 02           MOV  byte[SI+0x26],0x02   ; offsx = +2
24ED  80 7C 02 80 / 73 ..   CMP  byte[SI+2],0x80
24F7  C6 44 26 FE           MOV  byte[SI+0x26],0xFE   ; offsx = -2
```

**The PC's score routine is at `0x0292`** — a five-digit *decimal* add with manual carry
(`CLC`; loop 5: `MOV AL,[DI]` / `ADC AL,[SI]` / `CMP AL,0x3A` / `SUB AL,0x0A` / `MOV [DI],AL`),
so the PC keeps the score as **5 ASCII digits**, a third representation distinct from both
the ST's packed BCD and the port's binary `U32`.

**The decisive count: `CALL 0x0292` occurs exactly 4 times in the whole segment**, and all
four are accounted for:

| site | delta ptr | what |
|---|---|---|
| `0x0DEE` | `0x4916` | level/time bonus (increments a digit, then adds) |
| `0x22BB` | `0x491C` | super bonus — adjacent to the `0x22EE` tick divider found in T8 |
| `0x24D6` | `0x4928` | **enemy kill**, inside `gozombie` |
| `0x2585` | `0x492E` | pickup — follows `MOV byte[SI],0` (despawn) |

**None is a second add on an explosion path.** So the PC awards **50** for a dynamite kill
where the ST awards **100** — verdict **`PCST`**, and the port was faithful to the PC all
along.

**Applied.** Both explosion-kill sites in the port (`e_them.c:239` and `:542`, each
`if (e_bomb_lethal && e_bomb_hit(e))`) now carry an ST-only `env_score += 50` before
`e_them_gozombie(e)`, with the evidence in a comment at the site. Both platforms build.

This is difference **#20** (17 from T8, plus D5a, D6b, and this one).

### R2.3a follow-up — the score overflow: **all three builds differ**, and none wraps the same way

The PC's adder at `0x0292` (Ghidra-confirmed, not hand-decoded):

```
0292  PUSH DS / MOV AX,0x271D / MOV DS,AX
0298  ADD  SI,0x4              ; delta -> least-significant digit
029B  MOV  DI,0x4913           ; score -> least-significant digit
029E  MOV  CX,5
02A1  CLC
02A2  MOV  AL,[DI] / ADC AL,[SI] / CMP AL,0x3A
02A8  JC   0x02B0              ; no digit overflow
02AD  SUB  AL,0x0A / CLC       ; overflow: adjust, and force carry via the CMC below
02B0  CMC / MOV [DI],AL / DEC DI / DEC SI / LOOP
02B7  MOV  AL,[DI] / ADC AL,0x0 / MOV [DI],AL   ; 6th digit -- NO range adjust
02BD  POP  DS
```

So the PC keeps **6 ASCII digits**, five of them range-adjusted in the loop and a sixth
that only receives the final carry.

| build | representation | behaviour past 999,999 |
|---|---|---|
| **ST** | 3-byte **packed BCD**, `abcd` ×3 | carry-out of the third `abcd` is **discarded** → clean wrap to `000000` |
| **PC** | **6 ASCII digits**, top one unadjusted | the top digit goes `'9'` → `0x3A` (`':'`), a **non-digit**; the HUD then draws whatever glyph sits at that index, and further increments walk up the character set |
| **port** | binary `U32` | no wrap; keeps counting |

⚠️ **Deliberately not switched — this needs a decision.** Matching either original exactly
means replacing `env_score` with a digit array and reimplementing the adder, which is a
structural change well beyond a `#ifdef` and touches the HUD draw, the high-score
comparison and `scr_getname`. And the two originals are not merely different but
*differently broken*: the ST wraps cleanly, the PC corrupts its top digit.

The divergence is only reachable above 999,999 — plausible on a completed run
(100,000 per remaining life plus gameplay score), but not in ordinary play.

**Recommendation:** leave the port's `U32` as the behaviour for both platforms and record
the deviation, unless the user wants bug-level fidelity at the overflow boundary. Flagged
for the user rather than decided unilaterally.

---

## Phase 3 — algorithms and code

### R3.1 — the signedness fix: **3 of 10 done, and it repaired a real bug**

The ten dead comparisons split cleanly once each is looked at:

| kind | sites | status |
|---|---|---|
| **local variables** | `e_rick.c:217`, `e_rick.c:411`, `e_them.c:403` | ✅ **fixed** |
| **`ent_t` fields** | `e_bullet.c:63`, `e_rick.c:132`, `e_them.c:164`, `:309`, `:323`, `:663` | ⬜ needs `ent_t.x`/`.y` → `S16` |
| **function parameter** | `maps.c:349` (`maps_clip(U16 *x, ...)`) | ⬜ needs a signature change |

**What was broken.** `e_rick_action2` declared `U16 x, y` and tested
`x = E_RICK_ENT.x - 2; if (x < 0)` for the left-edge submap exit. With `x` unsigned that
test **can never fire**, so Rick could not leave a submap leftward — at `x = 0` the port
computes `0xFFFE`, falls through to `u_envtest`, and the position wanders out of range
instead of triggering a transition. `e_them_t2_action2` had the same shape for `y` at the
top edge.

**Both originals do detect it**, by different means — which is why this is a port defect
and not a platform difference, and is fixed under **both** platforms:

- **PC:** a byte underflow — `ADD AL,0xFE` / `JC` at `0x1906`, taking the exit when
  `x < 2`.
- **ST:** a *post-move* test in the **main loop**, not the controller —
  `if (player.nPosX <= 0 || player.nPosX >= 0xE8)` at `0x4DD2E` calls
  `process_level_transition_point`, with `nPosX` signed (`cmp.w #-0x8,D1w` / `bge`).

*(Worth recording: the two originals use different **designs** here. The ST lets the
controller move Rick out of bounds and detects it centrally next frame; the PC/port detect
the would-be underflow before moving and snap `x` to `0xE2`/`0x04`. The port follows the
PC. Only the width was wrong.)*

Both sites return before the value is used as an index, so `S16` is safe at each. Verified:
type-limits warnings **10 → 7**, zero errors, both platforms build, and the game runs.

**Remaining: `ent_t.x`/`.y` → `S16`.** The ST is unambiguous — position is a signed word
(`cmp.w #-0x8,D1w` / `bge`, and `ext.l D7` on the velocity) — so `S16` is right. But the
two fields have **~128 use sites** across `e_them.c` (57), `e_rick.c` (45), `ents.c` (16)
and `util.c` (10), including array indexing (`map_map[y>>3][x>>3]`), comparisons against
unsigned constants, and right-shifts whose behaviour on negatives differs. That is its own
pass, not an incidental edit, and it is deliberately left for one.

### R3.1 (cont.) — `ent_t.x`/`.y` → `S16` ✅ **applied; a second real bug fixed**

`ents.h` now declares both fields `S16`, with the ST evidence in a comment at the site.
**type-limits warnings 7 → 1** (only `maps.c:349`, a function parameter, remains).
Zero errors; both platforms build; the game runs.

**Five of the six newly-live tests are behaviour-neutral, and it is worth being precise
about why.** Each is an `||` pair whose arms share one body:

```c
if (ent.x < 0 || ent.x > 0xe8)   /* same action either way */
```

Under `U16` the first arm was dead, but a negative value wrapped to `0xFFxx`, which **is**
`> 0xe8` — so the second arm caught it and the same body ran. Fixing the sign moves which
arm fires, not what happens. (`e_bullet.c:63` shifts by a couple of frames: the wrap fired
as soon as `x` went below 0, the signed test fires at `x <= -0x10`.)

**The sixth was a genuine defect — `e_them.c:323`, the corpse-drift clamp:**

```c
ent_ents[e].x += ent_ents[e].offsx;
if (ent_ents[e].x < 0)    ent_ents[e].x = 0;      /* was DEAD */
if (ent_ents[e].x > 0xe8) ent_ents[e].x = 0xe8;
```

Here the two arms have **opposite** bodies. With `x` unsigned the first was dead, so a
corpse drifting off the **left** edge wrapped to `0xFFxx`, satisfied `> 0xe8`, and was
snapped to the **right** edge of the screen. Both originals clamp at 0 — the PC writes
`MOV byte[SI+2],0x00` / `,0xE8` at `0x2563`/`0x2570`, its `x` being a byte so its `< 0`
test works. **Fixed under both platforms**: this is a port defect, not a platform
difference.

That makes **two real bugs** fixed by the signedness work — the left-edge submap exit
(R3.1) and this — both invisible while the fields were unsigned.

**Residual: 39 new `-Wsign-conversion` warnings** (144 → 182 total), every one the same
benign class — `S16` meeting a `U16` interface (`u_envtest(U16 x, U16 y, …)`,
`e_bullet_init`, `map_maps[].x`) at points where the value is positive. None indicates a
semantic problem. The principled follow-up is to make the position **interfaces** signed
too, since the ST treats position as signed throughout; deferred so it is not mixed in
with a behavioural change.

⚠️ **Thresholds still need adjudicating.** Making a test live is not the same as making it
right: e.g. the port despawns an enemy at `x < 0` while the ST's `render_sprites` uses
`cmp.w #-0x8` (`x < -8`). Each newly-live threshold is now a phase-3 file-review item.

### R3.1 (cont.) — `maps_clip`'s dead left-clip branch: ✅ **harmless, and matching the ST. No change.**

The last `-Wtype-limits` site, `maps.c:349`. `maps_clip(U16 *x, …)` tests `if (*x < 0)`
and, inside it, `if (*x + *width < 0)` — both dead on unsigned parameters, so the partial
left-clip path (`*width += *x; *x = 0;`) is unreachable. My earlier note (W1.3) called this
"a rectangle straddling the left edge is either dropped whole or drawn wrong".

**Checking the ST before changing anything shows the current behaviour is right.**

All five callers mask with `x & 0xfff8` into a `U16`, so a negative x arrives as a large
unsigned value, fails `*x > MAPS_WIDTH_PX`, and the rectangle is **dropped entirely**.
And that is exactly what the ST does — `render_sprites` stage 3 (`algo-render.md`, audited
at instruction level in T4):

| axis | ST behaviour | port behaviour |
|---|---|---|
| **X** | `if (nPosX < 0) { bclr flags; continue; }` — **all-or-nothing**, no partial clip | rect dropped whole via the large-value path |
| **Y** | partial clip, advancing the source pointer by `clipped * 16` | partial clip against `MAPS_TOPHEIGHT_PX` |

The asymmetry — X all-or-nothing, Y partially clipped — is **present in both builds**, and
the port's `y` branch is written against `MAPS_TOPHEIGHT_PX` rather than 0 precisely
because it must partially clip.

**So the dead branch is unreachable *and* its logic would be wrong if reached**: making the
parameters signed would enable a left-edge partial clip that neither original performs.
Left exactly as it is, with the reasoning recorded. The one remaining `-Wtype-limits`
warning is therefore **expected and correct**, not an outstanding defect.

*(Method note: this is the second time in this phase that the ST turned a plausible-looking
"fix" into a divergence — the first being the five `||` pairs that were already
behaviour-neutral. Reading the oracle before editing is doing real work here, not
ceremony.)*

### R3.2 — despawn/bounds thresholds ✅ adjudicated

The thresholds the `S16` work made visible. **This divergence pre-dates that change** —
under `U16` the wrap routed negative values into the `> 0xe8` arm, masking it.

| bound | ST | PC | port | verdict |
|---|---|---|---|---|
| vertical limit | **`0x142`** — `cmp.w #0x142,D2w` @ `0x4B0C8` (`render_sprites`) and @ `0x4D352` (`scripted_trap_update`) | **`0x140`** — `CMP AX,0x140` @ `0x10E3`, `0x2742`; **no `0x142` compare exists in the segment** | `0x140` | ⚠️ **`PCST`** — switched |
| horizontal U-turn | *none* | `0xE8` — `CMP AL,0xE8` @ `0x2773`, `0x245C` | `0xE8` | ⬜ **structural**, see below |

**Applied:** `ENT_YMAX` in `ents.h`, `0x142` under `PLATFORM_ST` and `0x140` otherwise,
replacing the constant at all **seven** sites in `e_them.c` and `e_rick.c`. Both platforms
build, the binaries differ, the game runs.

Note the **architecture** differs too, and only the constant was switched: the ST despawns
**centrally** in `render_sprites` for every entity, while the PC and the port test **per
entity** inside each action handler. Aligning the architecture would be a rewrite with no
behavioural gain.

**The horizontal U-turn bound is not switchable.** A program-wide search for `#0xe8` in the
ST finds five sites — `render_sprites` (visibility clip), `player_controller` ×2 (Rick's
clamp), `player_death_physics`, and `main_init_and_loop` (the submap transition) — and
**none in `enemy_ai_update`**. The ST's enemies reverse on **terrain** (the tile probe),
not on a coordinate; the PC and port reverse on `x > 0xE8`. That is a difference of
*mechanism*, not of constant, so there is nothing to `#ifdef`: making the ST build faithful
would mean deleting the bound and relying on terrain, which changes enemy behaviour in ways
this review cannot yet verify. **Recorded as a structural divergence, deliberately not
changed.**

⚠️ Also worth separating: the ST's `0xF0`/`-8` pair in `render_sprites` stage 1 is its
**despawn** window, while `0xE8`/`0` in stage 3 is its **visibility** window — two distinct
bounds. The port has no equivalent of the wider despawn window at all; entities leave play
by the per-handler tests instead.

### R3.6 — `util.c` / `e_rick_boxtest`: the player hitbox ✅ **two differences, one of them new**

T8 had recorded a single hitbox difference (`+0x11` vs `+0x12`). Reading both originals
instruction by instruction shows **two**.

**PC `u_boxtest` @ `0x12BC`:**
```
MOV AL,[DI+2] / ADD AL,0x11 / MOV AH,[SI+2] / CMP AL,AH / JC   -> FALSE if x+0x11 <  e.x
SUB AL,0x0C            (AL = x+5)
ADD AH,[SI+0x0E]       (AH = e.x + e.w)      / CMP AH,AL / JC  -> FALSE if e.x+e.w <  x+5
MOV AX,[DI+4] / ADD AX,0x14 / CMP AX,BX / JC                   -> FALSE if y+0x14 <  e.y
MOV AX,[DI+4] / CMP byte[DI],0x1 / CMP byte[0x7D68],0          -> crawl adjust, Rick only
```

**ST `entity_overlaps_player` @ `0x4D9AA`:**
```
D0 = px+5-w ; cmp.w (0x4,A0),D0w ; bge  -> FALSE if px+5   >= e.x+e.w
D0 += w ; addi.w #0xD  (= px+0x12) ; blt -> FALSE if px+0x12 <  e.x
D0 = py (+8 if crawling) - h ; bge      -> FALSE if py' >= e.y+e.h
D0 += h ; addi.w #0x14 ; (-8 if crawling); blt -> FALSE if py+0x14 < e.y
```

| edge | PC / port | ST | note |
|---|---|---|---|
| right | `x + 0x11` | **`x + 0x12`** | known (T8) — the ST box reaches one pixel further right |
| **left** | `e.x+e.w < x+5` (strict) | **`x+5 >= e.x+e.w`** | ⭐ **new** — the ST box is one pixel tighter on the left |
| top | `py' > e.y+e.h-1` | `py' >= e.y+e.h` | ✅ identical (`> n-1` is `>= n`) |
| bottom | `y + 0x14` | `y + 0x14` | ✅ identical |

A detail worth recording: the ST adds `8` for crawling before the **top** test and
**subtracts it again** before the bottom one, so the bottom edge is crawl-independent —
which is exactly why the port's bottom test correctly carries no crawl term. The port had
that right.

**Applied** as a `PLATFORM_ST` / `PLATFORM_PC` pair in `e_rick_boxtest`, with both
disassemblies quoted at the site. Both platforms build; the game runs.

This is difference **#22** (and the second found by reading a routine the project had
already "checked" — the first being the vertical bound). It is a reminder that a row in
`xref.md` recording *one* difference in a function does not mean the function has been
compared line by line.

### R3.6b — `u_trigbox`: the trigger box ✅ **two more differences**

The trigger box is what fires every scripted trap, so its edges matter.

**PC `u_trigbox` @ `0x13ED`** — the port matches it *exactly*, clamp included:
```
MOV AL,[SI+0x16] / CMP AL,BL / JNC fail    -> FALSE if trig_x >= x     (EXCLUSIVE low)
BX = (n & 0x7F)*8 + 0x932C ; AH = trig_w ; AH *= 8 ; ADD AH,AL
JNC skip / MOV AH,0xFF                     -> saturating byte CLAMP at 0xFF
CMP AH,CH / JC fail                        -> FALSE if xmax < x        (inclusive high)
```

**ST `trigger_box_contains_point` @ `0x4D986`:**
```
cmp.w (0x3c,A0),D0w / blt fail             -> FALSE if x < XMin        (INCLUSIVE low)
cmp.w (0x3e,A0),D1w / blt fail
cmp.w (0x40,A0),D0w / bgt fail             -> FALSE if x > XMax        (inclusive high)
cmp.w (0x42,A0),D1w / bgt fail
```

| aspect | PC / port | ST |
|---|---|---|
| lower edge (both axes) | **exclusive** — `x > trig_x` required | **inclusive** — `x >= XMin` required |
| upper edge | inclusive | inclusive ✅ same |
| `xmax` overflow | **clamped to `0xFF`** (`MOV AH,0xFF`) | **no clamp** — `XMax` is a precomputed *word* (`0x40`/`0x42`) written by `init_entity_from_placement` without saturation, and it **can** exceed `0xFF`: `trig_x` reaches `0xF8` and `trig_w*8` adds up to another 32 |

So an ST trigger box is one pixel larger on its left and top edges, and is not truncated
near the right edge of the playfield. Both are switched under `PLATFORM_ST`, with the two
disassemblies quoted at the site. Both platforms build; the game runs.

Differences **#23** and **#24**.

**Pattern worth noting.** `util.c` is 210 lines — the smallest file in the review — and its
four probe functions have now yielded **four** differences (`u_boxtest` ×2, `u_trigbox` ×2),
none of which T8's constant-hunting found. T8 asked "is this constant the same?"; a
line-by-line read asks "is this *routine* the same?", and the answer keeps being no in
small ways that a constant search cannot see: comparison *senses* (`blt` vs `JNC`),
saturation, and off-by-one edges.

### R3.6c — `u_fboxtest` (bullet / point-in-entity) ✅ **a port defect plus three divergences**

The point-in-entity test, used for bullet hits. Read against both originals:

| edge | PC `@0x1317` | ST `@0x4CC4C` | port (before) | verdict |
|---|---|---|---|---|
| X lower | `x > ent.x` (excl) — `CMP AL,BL`/`JNC` | `x >= ent.x` (**incl**) — `cmp.w D1w,D0w`/`bgt` | `x > ent.x` | `PCST` |
| X upper | `x <= ent.x+w` | `x <= ent.x+w-1` — `subi.w #1` before the add | `x <= ent.x+w` | `PCST` |
| **Y lower** | **`y >= ent.y` (incl)** — `CMP DX,AX`/`JC` | **`y >= ent.y` (incl)** — `bgt` | **`y > ent.y`** | ⚠️ **`DEFECT`** |
| Y upper | `y <= ent.y+h` | `y <= ent.y+h-1` | `y <= ent.y+h` | `PCST` |

⭐ **The Y lower bound is a genuine port defect.** *Both* originals accept `y == ent.y` —
the PC by `CMP DX,AX / JC` (fails only when `y < ent.y`) and the ST by `bgt` — but the port
wrote `ent_ents[e].y >= y`, rejecting it. A bullet arriving exactly on an entity's top
scanline missed. **Corrected on both platforms.**

The other three are real PC-vs-ST divergences and are switched: the ST's box **includes**
its left column and is **one pixel shorter** on both upper edges (note the `subi.w #0x1`
before each `add.w` — the ST computes `ent.x + w - 1`, a genuine inclusive-extent
convention, where the PC computes `ent.x + w`).

Both platforms build; the game runs. Differences **#25**, **#26**, **#27**, plus the
defect.

**`util.c` is now fully reviewed** — 210 lines, and it has produced **7 differences and
1 port defect**, none of which nine previous audits had found. The reason remains
structural: every one of them lives in a comparison *sense* or an off-by-one extent, not
in a constant that a byte search could match.

### R3.7 — `e_bullet.c` ⚠️ **including a regression I introduced, caught by reading the original**

**The bullet bounds were wrong on both sides, and one of the errors was mine.**

PC `e_bullet_action` @ `0x1A01` is unambiguous:
```
left  : ADD AL,[SI+2] / JNC 0x1A44   -> byte underflow: deactivate when x < 0
right : CMP AL,0xE8   / JNC 0x1A44   -> deactivate when x >= 0xE8   (0x1A44: MOV byte[SI],0)
```

The port had `x <= -0x10 || x > 0xe8` — **sixteen pixels late on the left, one late on the
right**.

⚠️ **The right-hand off-by-one was a pre-existing port defect. The left-hand one I caused.**
While `x` was `U16` the `<= -0x10` test was dead, and the wrap routed a negative x into
`> 0xe8`, which *accidentally reproduced* the PC's `x < 0`. Making `x` signed (R3.1) turned
that accident off and left the literal `-0x10` in charge. **This is exactly the risk I
flagged when deferring the retype — "some currently work by `U16` wrap" — and it is why
each newly-live site had to be read rather than assumed.** Both bounds now match the PC,
on both platforms.

The ST has **no explicit bounds test at all**: `player_bullet_update` @ `0x4CA5A` moves the
probe, calls the terrain test, and deactivates on carry — relying on the map border being
`SOLID`. The PC's bounds are kept under both platforms as a guard, since without them a
negative `x` would index `map_map` out of range; the ST reaches the same outcome through
its data rather than a test. Recorded rather than blindly copied.

### R3.7a — ST bullets are stopped by moving blocks; PC bullets pass through ⭐ **#28**

The ST's bullet terrain test (`0x4CCFC`) does **two** things:

```
btst.b #0x6,(0,A0,D7w)        ; tile attribute bit 6 = SOLID  -> blocked
tst.w (0x4A702)               ; sprite_list[0].wType -- the block entity
cmp against (0x4A706)+(0x4A712) and (0x4A708)+(0x4A714)
                              ; blocked iff bx <= px < bx+w and by <= py < by+h
```

The PC's equivalent (`0x1115`) is **tile-only** — it ends `AND AL,0x40 / RET`, with no
entity test of any kind. The port matched the PC.

So on the ST a bullet is stopped by a moving block; on the PC it flies straight through.
Added under `PLATFORM_ST`, with both disassemblies at the site. Both platforms build; the
game runs.

### R3.8 — `e_bomb.c`: the blast box ✅ **a T8 finding finally applied, plus a fourth edge-sense difference**

T8 adjudicated the blast box back on 2026-09-02 but the result was never carried into the
code. Re-derived here from the disassembly rather than trusted from the note:

**ST `explosion_overlaps_entity` @ `0x4CC92`** works from the blast **centre**
(`explosion_x/y` at `0x4BF2A`/`0x4BF2C` = `bomb.x+0x0C`, `bomb.y+0x0A`):
```
D0 = ex-0x10-w ; cmp.w (0x4,A0),D0w ; bge  -> FALSE if ex-0x10 >= e.x+w
D0 += 0x1F + w  (= ex+0x0F)         ; blt  -> FALSE if ex+0x0F <  e.x
D1 = ey-0x0E-h                      ; bge  -> FALSE if ey-0x0E >= e.y+h
D1 += 0x1C + h  (= ey+0x0E)         ; blt  -> FALSE if ey+0x0E <  e.y
```

In bomb-entity coordinates: **ST `x ∈ [bx-4, bx+0x1B]`, `y ∈ [by-4, by+0x18]`** —
confirming T8's figures exactly, and derived independently this time.

| aspect | PC / port | ST |
|---|---|---|
| X upper | `bx + 0x20` | **`bx + 0x1B`** |
| Y upper | `by + 0x1D` | **`by + 0x18`** |
| lower edges | `<` (includes equality) | **`>=` (excludes it)** — ⭐ the fourth such sense difference found |
| `0xFF` clamp when `bx >= 0xE0` | **present** | **absent** |
| clamp-at-zero on the lower edge | **present** | **absent** — the ST works in signed words throughout |

So the PC's blast is five pixels larger on both upper edges, and its two clamps exist only
because its arithmetic is byte-wide. Switched under `PLATFORM_ST`. Both platforms build;
the game runs.

**Observation.** This is now the **fourth** routine where the ST excludes equality on a
lower edge and the PC includes it (`e_rick_boxtest`, `u_trigbox`, `u_fboxtest`,
`e_bomb_hit`). That is not four coincidences — it looks like a systematic convention
difference between the two codebases, and it means **every** remaining box or bounds test
should be read for edge *sense*, not just for its constants. Noted as a standing check for
the rest of phase 3.

### R3.9 — `e_box.c` ⚠️ **an out-of-bounds read, plus three unadjudicated differences**

**The defect (fixed).** `explode()` sets `cnt = SEQ_INIT = 0x0A`; the next call evaluates
`sp[cnt >> 1]` = **`sp[5]`** *before* the decrement, on a **five**-element array. The PC
indexes identically —
```
25AB MOV BL,[SI+0x26] / SHR BL,1 / ADD BX,0x8138 / MOV AL,[BX] / MOV [SI+8],AL
25BB DEC byte[SI+0x26] / JNZ                 ; decrement AFTER the index is used
```
walking indices `5,4,4,3,3,2,2,1,1,0` — ten ticks, **six** distinct sprites. So the port's
array is one short and the first explosion frame showed whatever byte followed it.

⚠️ The sixth value (`0x29`) is **inferred** from the ascending run `0x24..0x28`, not read:
the PC's sprite table at `0x8138` is in its **data** segment, which we do not hold. An
inferred sprite is strictly better than a non-deterministic overread, but it is labelled as
inferred at the site and should be confirmed if the data segment ever becomes available.

**Three further differences, recorded but NOT changed** — each needs the PC's box path read
in full before it can be classified, and none is a safe guess:

| # | ST (`destructible_pickup_update` @ `0x4D058`) | port |
|---|---|---|
| 1 | **test order**: stick (`0x4CBF0`) → bullet (`0x4CC10`) → explosion (`0x4CC92`) → *then* player-collect (`0x4D9AA`) | **collect first**, then stick, bullet, bomb |
| 2 | an exploding box **kills Rick** — `bsr 0x4D9AA` inside the animate branch, then `move.w #0xFF,(0x4BF2E)` @ `0x4D0D2` | **no such test.** `ENT_LETHAL` is never compared against Rick anywhere in the port (only `e_them.c:55,59,748`, enemy-vs-entity) |
| 3 | animation is **10 frame pointers × 2 ticks** from a table at `0x46C3E` with a `-1` sentinel (`bclr #0` on the index holds each frame twice) | 6 sprite **numbers** over 10 ticks |

#1 matters in play: with the ST's order, touching a box while the stick is out **explodes**
it; with the port's, it is **collected**. #2 is potentially significant — on the ST you can
be killed by a box you just blew up. #3 is the familiar pointers-vs-numbers model
difference (T9) and is not actionable.

`OPEN` — the PC's box routine around `0x25A3`-`0x2619` is partly read (stick and bullet
tests via `CALL 0x1317`) but its collect path and any lethal-vs-Rick test have not been
located yet.

### R3.10 — attempt to build a PC function map from the `ASM nnnn` citations ❌ **not viable**

Adjudication is increasingly bottlenecked on *locating* PC code, so I tried to turn the
port's 35 `ASM nnnn` citations into a lookup table using the `+0x17E` delta and Ghidra's
78 recovered functions. **It does not work, for two independent reasons.**

**1. The delta is genuinely not constant.** Confirmed by content, not by arithmetic:

| citation | function | actual | delta |
|---|---|---|---|
| `113E` | `u_boxtest` | `0x12BC` | `+0x17E` |
| `1199` | `u_fboxtest` | `0x1317` | `+0x17E` |
| `126F` | `u_trigbox` | `0x13ED` | `+0x17E` |
| `11CD` | `e_bomb_hit` | `0x134B` | `+0x17E` |
| `1851` | `e_rick_gozombie` | `0x19CF` | `+0x17E` |
| **`237B`** | **`e_them_gozombie`** | **`0x24C3`** | **`+0x148`** |

`+0x17E` holds across the directly-called helpers and breaks on the entity handlers.

**2. Ghidra's function list does not cover the handlers.** `0x24C3` — verified by content
(`MOV byte[SI],0x47`, `MOV word[SI+0x2C],0xFC00`) — is **not** in the recovered list, which
jumps from `0x2263` to `0x265A`. Entity handlers are reached through a **dispatch table**,
so they generate no direct call and the analyser never marks them. The gap is precisely
where the remaining review work lies.

**And the arithmetic cannot be validated statistically**: with 78 function starts in a
~12 KB span, most candidate deltas hit *something*. The tally (`+0x17E` leading with 7 of
34) is well inside what coincidence produces, so it is not evidence.

**Conclusion, adopted as method:** locate PC routines by **content signature** — a
distinctive constant, store, or call shape taken from the port's C — and confirm
structurally at the target. That is how every successful location in this review was
actually made (`e_bomb_hit` via `ADD BX,0x1D`, `gozombie` via `0xFC00`, the score adder via
its `CALL` count). Citation arithmetic may *suggest* a neighbourhood; it must never be
trusted to land.

### R3.11 — `e_bonus.c`: the port's rise animation matched **neither** original ⭐

| build | on collect |
|---|---|
| **PC** `@0x2575` | `CALL 0x12AE` (box test) / `JZ` / **`MOV byte[SI],0`** / score / sound / `OR byte[BX],0x80`. **Deactivated immediately — no rise animation at all.** |
| **ST** `treasure_pickup_update @0x4D102` | `add_score(0x500)`, `mark_placement_dead`, **`move.w #0xC,(0x2c,A0)`**, `play_music(0x11)`; each later frame `subi.w #1,(0x2c,A0)` → `bne`: sparkle frame + **`subi.w #2,(0x6,A0)`**, `beq`: despawn. Counter 12 gives **eleven** animated frames, a **22 px** rise |
| **port (before)** | `seq = 1`, sprite `0xad`, `front = TRUE`, **`y -= 8`**, then `seq` 1..9 with `y -= 2` — **26 px over ten frames** |

So the port invented a middle path: an ST-flavoured rise (it even uses the ST sprite number
`0xad` **unconditionally**, which is wrong under `GFXPC`) with parameters matching neither
side — an initial `-8` the ST does not have, and nine frames where the ST has eleven.

Each platform now gets its own: **PC instant deactivate; ST a 12-counter yielding eleven
`y -= 2` frames.** Both build; the game runs.

**Care taken on the frame count.** My first reading said "12 frames, 24 px". Re-reading the
decrement order — `subi.w #1` *then* `bne` to animate, `beq` to despawn — the twelfth tick
despawns without animating, so it is **11 frames / 22 px**. Counter semantics of this kind
are exactly where an off-by-one slips in, and the disassembly settles it rather than the
constant.

Differences **#34** (rise present/absent) and **#35** (frame count and initial offset).

## Phase 3a / 3b — session of 2026-09-05

### R3.12 — four **already-adjudicated** differences that had never reached the code ⭐

Scanning `e_them.c`'s physics constants against the ST found that several T8 rows were
catalogued in `xref.md` but never applied — the same gap `e_bomb.c`'s blast box had. Each
was re-verified against the disassembly before switching, not taken from the note:

| item | PC / port | ST | evidence |
|---|---|---|---|
| death launch | `-0x400` | **`-0x300`** | `move.w #-0x300,(0x8,A0)` @ `0x4D886` |
| **dying** gravity | `+0x80` | **`+0xC4`** | `addi.w #0xC4,(0x8,A0)` @ `0x4D532`, no clamp |
| stick-jab stun | `0x14` (20) | **`0x19`** (25) | `move.b #0x19,(0x4a,A0)` @ `0x4D574` |

Switched — the stun via a new `ENT_STUN` constant in `ents.h`, the other two in place.
The *living*-enemy gravity (`+0x80` clamped at `0x800`, `0x4D684`/`0x4D68A`) was checked
too and **already agrees**, so only the dying path changed.

### R3.12a — a fifth port defect: the trigger-sound index base ⚠️ **out-of-bounds read**

`e_them.c:721` indexed `WAV_ENTITY[(trigsnd & 0x1F) - 0x14]`. Verified against the port's
**own** `ent_entdata`: the ten distinct non-zero `snd` values are `0x13`–`0x1C`, and
`0x13 - 0x14` = **−1** — an out-of-bounds array read every time that entity triggers.
With base `0x13` the ten values map exactly onto `WAV_ENTITY[0..9]`, filling the array.

This needed no platform judgement: the port's data and its index disagree with each other,
so it is wrong on both. **Corrected on both platforms.**

### R3.13 — structural findings, recorded not changed

- **`ent_action` dispatch.** Port: `k = n & 0x7f`, with special cases `k == 0x47` and
  `k >= 0x18`. ST `render_sprites`: `sprite_type_dispatch[wType - 1]`, **no mask, no
  special cases** — because the ST does not pack `ENT_LETHAL` into the type byte at all;
  it keeps `wHazardActive` in its own field (`0x3A`). A data-model difference, not a
  constant.
- **Spawn banding.** Port `map_init` calls `ent_actvis` over **three row ranges**
  (`TOP=8`, `VIS=0x20`, `BOT=8` → `frow+0 .. frow+0x2F`). ST `spawn_screen_entities` calls
  `spawn_level_entity` with **five discrete lookahead offsets** `0x00, 0x08, 0x10, 0x18,
  0x20`, gated by `spawn_scan_flags`, matching `wSpawnBand` on an 8-row granularity —
  reaching `frow+0x27`. **The port therefore scans eight rows further down than the ST.**
  Flagged: changing spawn banding without a live comparison is too risky to do blind.
- **`env.c` is entirely rendering** (`env_paintGame`, `env_paintXtra`, `env_clearGame`) —
  no ST counterpart, out of scope. So 3b's real logic surface is only `map_expand` and
  `map_init`; the other seven `maps.c` functions are rendering or already done.

### R3.14 — the `xref.md` sweep ⭐ **the highest-yield action of the whole review**

Suspecting that adjudicated differences were not reaching the code, I checked all **25**
`xref.md` "genuine difference" rows against the source. **Fourteen had never been
applied** — every T8 row except the handful applied during earlier phase-3 sessions.

Applied this session, each re-verified against the disassembly first:

| row | PC | ST | where |
|---|---|---|---|
| Spawn latency seed | `<<5` (x32) | **x25** | `ents.c` |
| Placement bit for the spawn Y `+3` nudge | `0x02` | **`0x04`** | `ents.c` |
| Super-bonus tick divider | `0x1E` (30) | **`0x19`** (25) | `e_sbonus.c` |
| Player trigger-box probe X | `+0x0C` | **`+0x0B`** | `RICK_PROBE_DX`, 2 sites |
| Submap re-entry X | `0xE2` / `0x04` | **`0xE6` / `0x02`** | `SUBMAP_REENTRY_*`, 4 sites |
| Enemy corpse drift | `x += ±2`, clamped | **`dir ? y+1 : x-1`**, no clamp | `e_them.c` |
| Ladder-exit upward velocity | `-0x300` | **`-0x200`** | `e_rick.c` |
| Ceiling-bonk velocity | `0` | **`0x80`** | `e_rick.c` |
| Scroll trigger, low threshold | `0x60` | **`0x5F`** | `game.c` |
| Stick-jab stun | `0x14` | **`0x19`** | `ENT_STUN` |
| Dying gravity | `+0x80` | **`+0xC4`** | `e_them.c` |
| Death launch | `-0x400` | **`-0x300`** | `e_them.c` |

**Still unapplied, and why:**

- **Dynamite fuse** — structural, not a constant: PC a 45-tick counter, ST a 17-frame
  table plus 10 explosion frames. Needs a rewrite of `e_bomb_action`, not an `#ifdef`.
- **Type-2 ladder-grab masks** — the port's climb conditions (`(x & 7) == 4`,
  `(x & 0x0e) == 4`) do not correspond to the ST's (`(x & 8) == 0 || (x & 7) == 0`,
  `x = (x & ~0xF) | 4`) at all. A mechanism difference; see R3.15.
- **Bullet probe points** — the port already keeps both a centre and a leading edge, so
  the row is satisfied as written.

**Caught while applying:** I wrote `ent_ents[e].dir` for the corpse drift — a field that
does not exist. The port carries enemy direction as the **sign of `offsx` (`c1`)**, with no
separate field; the ST has `nDirection` at `0x02`. Corrected before building.

### R3.15 — `e_them.c` compared at constant/condition level; four findings left open

The full ST oracle (`enemy_ai_update`, `0x4D4F4`, **238 instructions**) covers in one
routine what the port splits across 11 functions. Diffing constants and conditions:

**Agree:** living gravity `+0x80` clamped `0x800`; resting `0x100`; ground snap
`(y & 0xF8) | 3` (`andi.b #-0x8` / `ori.b #0x3` @ `0x4D6F0`); the 16.16 integration;
anim-index handling.

**Open — recorded, not changed** (each needs the PC side located before it can be
classified):

| # | ST | port |
|---|---|---|
| 1 | climbing up sets `offsy = -0x200` (`0x4D5CE`) | leaves `offsy` untouched in the `ymove` path |
| 2 | climb gate `(x & 8) == 0 \|\| (x & 7) == 0`, then `x = (x & ~0xF) \| 4` (`0x4D6B4`-`0x4D6CA`) | `(x & 0x07) == 0x04` / `(x & 0x0e) == 0x04` |
| 3 | chase Y compare uses `bclr #0` on **words** (`0x4D5AE`) | `(y & 0xfe)` — which also discards bits 8-15, and `y` reaches `0x142` |
| 4 | mode-2 turn on `prng & 3` (`0x4D79E`-`0x4D7AC`) | `e_them_rndnbr` sequence (`divergences.md` 4.1) |

#3 is the most likely real defect of the four: `y & 0xfe` cannot be right for a 16-bit `y`.
