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
| D6b | `map_bnums` (`0x1FD8`) | — | tile-map blocks | ⚠️ **`PCST`** — exact match to `ibmpc_ds1.bin:0x523A`, absent from `atari_ram.bin` (R4.2). The ST holds no static copy: `map_expand` reads a per-submap **pointer** from `(0x495CC)`, null in our dump (R4.20). Needs an in-game ST dump |
| D7 | `ent_sprseq` (`0x88`), `ent_mvstep` (`0x310`) | — | — | ✅ **checked (R4.23, R4.24)** — both match the PC where used; both over-run their true end into adjacent data; both inert (max `sni` 244 < 261 valid records). Not changed, deliberately |
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
✅ **RESOLVED — see R3.16.** The ST's clean wrap is now applied on both platforms via
`env_addscore()`, and the PC's own behaviour was read (`0x0292`: the sixth digit gets only
`ADC AL,0x0`, so it corrupts to `':'`).

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

✅ **RESOLVED — `PCST`, and implemented.** The structural approach worked: the PC's score
adder is `0x0292`, and it has **exactly four** call sites, all now accounted for — level
bonus `0x0DEE`, super bonus `0x22BB`, enemy kill `0x24D6` (inside gozombie), pickup
`0x2585`. **None** is a second add on the explosion path, so the PC awards 50 for a
dynamite kill and the ST 100. The port was faithful to the PC; the extra 50 is now added
under `PLATFORM_ST` in `e_them.c`.

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

⚠️ ~~The sixth value (`0x29`) is **inferred**~~ — **the inference was WRONG; see R4.10.**
The data segment is now in hand and the real table is `24 24 25 25 26 26 27 27 28 28 ff`.

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

✅ **RESOLVED — see R4.21.** The whole PC box routine is now read (`0x2592`-`0x2648`).
#1: the PC's order is **collect first**, so the port was already correct and the ST is the
outlier. #2: the PC has **no** lethal-vs-Rick test; the ST's is real and is now implemented
under `PLATFORM_ST`.

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

### R3.16 — score wrap implemented ✅ **and an earlier claim of mine corrected**

**User decision 2026-09-06: apply the ST's clean wrap on both platforms.** Done via a new
`env_addscore(U32)` in `env.c`, replacing all **six** direct `env_score +=` sites
(`e_bonus.c` ×2, `e_sbonus.c` ×1, `e_them.c` ×3). No direct addition remains.

❌ **Correcting R2.3a.** I wrote that matching either original "means replacing
`env_score` with a digit array and reimplementing the adder, which is a structural change
well beyond a `#ifdef`". **That was wrong**, and the user was right to challenge it.

A digit array is only needed to reproduce the **PC's corruption** — its sixth digit gets
`ADC AL,0x0` with no range adjustment, so at overflow it becomes `':'` (`0x3A`) and the
HUD draws a non-digit. That artifact genuinely requires ASCII digits.

For the **ST's** behaviour a `U32` is *exactly* equivalent:

- `abcd` cannot produce an invalid nibble, so the ST score is always a well-formed
  decimal in `0..999999`;
- the third `abcd`'s carry-out is discarded, so the result is by definition
  `(score + delta) mod 1000000`;
- which is precisely `env_score = (env_score + delta) % 1000000`.

Two facts checked while implementing, both supporting the change:

1. **The port's HUD already renders exactly six digits** — `env_paintGame()` uses
   `static U8 s[7]` with a `for (i = 5; i >= 0; i--)` digit loop. So a score past 999,999
   was *already* displaying only its low six digits while `env_score` kept counting; the
   wrap makes the stored value agree with what was always on screen.
2. **The port has no end-of-game per-life bonus at all** — no `100000` anywhere in the
   sources, against the ST's `add_score(0x100000)` per remaining life
   (`algo-level.md:399`). That is a separate unrecorded difference, and it makes the
   overflow *less* reachable in the port than in the ST. Logged below.

Both platforms build; the game runs.

### R3.17 — end-of-game per-life bonus: present in BOTH originals, tenfold different ✅

The port had no end-of-game bonus at all. Both originals do, awarded at exactly the same
point — once the map counter reaches 4, before the completion transition.

| | ST | PC |
|---|---|---|
| site | `0x49AD2` | `0x0DD8` |
| guard | `cmpi.w #4,level_index` / `blt` | `inc [0x7D90]` / `cmp al,4` / `jnz` |
| lives | `moveq #0,d1` / `move.b [0x4B32E],d1` | `mov al,[0x7E46]` / `inc al` |
| award | `L: move.l #$00100000,d0` / `bsr add_score` / `dbra d1,L` | `mov [0x4916],al` / `mov si,0x4916` / `call 0x0292` |
| **value** | **(lives+1) × 100,000** | **(lives+1) × 10,000** |

**Why the ST is 100,000.** `add_score` (`0x4B3E4`) stores `d0` to `0x4B51E` and runs three
`abcd -(a1),-(a0)` from `0x4B522`/`0x4B329` down. So delta bytes `0x4B51F..0x4B521` pair
with score bytes `0x4B326..0x4B328`, and `0x4B326` is the top pair (10^5,10^4). With
`d0 = 0x00100000` the byte at `0x4B51F` is `0x10` — packed BCD, high nibble 1 on the
**10^5** place. `dbra` runs the body `lives+1` times.

**Why the PC is 10,000.** The adder (`0x0292`) does `add si,0x4` then walks *down* five
digits from `di = 0x4913`, so `buffer[0]` pairs with `di = 0x490F`. The score is six ASCII
digits at `0x490E..0x4913` — init `0x004C` writes `0x3030` to each of `0x490E`/`0x4910`/
`0x4912`, and the HUD (`0x2016`) copies them left-to-right starting at `0x490E`, fixing
`0x490E` as the MSD. So `0x490F` is the **10^4** place. The call site writes `lives+1`
into `buffer[0]` only; `0x4917..0x491A` are referenced by **no** instruction in the
segment (scanned all 16-bit operands in `0x4914..0x4920`), so they are static zero.

So it is the *same mechanism* with a tenfold different multiplier — not a port omission,
and not a missing feature on either side. Implemented switched in `game.c`, using
`env_addscore()`; a single multiply rather than the ST's loop, which is exact because
`env_addscore` wraps mod 1000000 and repeated addition mod m equals the summed product
mod m. `env_lives` never exceeds 6 (never incremented anywhere in the port), so
`lives+1 <= 7` and the PC's single digit cannot overflow. Both platforms build clean.

Note this raises the practical reach of the overflow documented in R3.16: on the ST a
6-life completion adds 700,000 in one go.

## Phase 4 — the PC DATA segment is now in hand

### R4.1 — `ibmpc_ds1.bin` / `ibmpc_ds2.bin` located and based ⭐

The user supplied two 64 KB data-segment dumps. Their bases were **derived, not assumed**:

| dump | base segment | evidence |
|---|---|---|
| `ibmpc_ds2.bin` | **`0x271D`**, shift 0 | the hall of fame sits at file `0x46A5`, exactly the `MOV SI,0x46A5` in the score-compare at `0x2038`; 9 entries × 28 bytes, scores descending `008000`→`000000`, names `DANGERSTU`/`SIMES`/`KEN@T@ZEN`/`BOBBLE`/`GREG@LAA`/`TELLY`/`CHIGLET`/`ANDYSPLEEN` (`@` = `0x40` = space) |
| `ibmpc_ds1.bin` | **`0x179C`**, shift 0 | `(0x271D-0x179C)*16 = 0xF810`; `ds1[0xF810+k] == ds2[k]` for **1998 of 2031** bytes (98.4%), first 32 identical. `0x179C` is the segment the code loads most (42 times) |

A first attempt put the base at shift `+0x36C` on the strength of "the implied table address appears
as a code immediate". **Rejected**: the set of 2-byte windows in the code segment covers only
4077/65536 values, so that filter is weak, and the implied delta buffers held `0x1E,0x1F,0x1A…`
rather than raw digits. The structural check is what settled it. Same failure mode as ever — a
query that cannot discriminate.

**Unexplained, recorded not guessed:** both dumps carry `DUMP1   BBI`/`DUMP2   BIN` at offset
`0x5D` and `DUMP1.BBIN`/`DUMP2.BIN` at `0x81` — exactly the DOS PSP FCB and command-tail offsets.
This does not affect the bases (which rest on content matches) but is not accounted for.

### R4.2 — the port's generated tables came from the PC binary ⭐⭐

Long-standing open question, now answered. **`map_bnums` (all 8152 bytes) matches
`ibmpc_ds1.bin` at `0x523A` byte for byte**, and `screen_imapsl` (22 bytes) at `0x9736`.
The same `map_bnums` bytes do **not** occur anywhere in `atari_ram.bin`.

So the port's tables are **PC** data, and `map_bnums` needs an ST-extracted variant like
`map_eflg_c` and `map_maps` already have. This retires the Phase 1 doubt about provenance and
turns it into concrete work.

### R4.3 — R3.17's PC value independently confirmed ✅

The static delta tables in `ds2` decode under the 10^4 pairing as:

| buffer | digits | value | consumer |
|---|---|---|---|
| `0x4916` | `[0,0,0,0,0]` | `buf[0]` written at runtime = lives+1 | end-of-game bonus (`0x0DEE`) |
| `0x491C` | `[0,0,0,0,0]` | built at runtime (`0x01CD`/`0x01D7`/`0x01E1`/`0x01EC`) | super bonus (`0x22BB`) |
| `0x4922` | `[0,0,0,0,1]` | 1 | never referenced |
| `0x4928` | `[0,0,0,5,0]` | **50** | enemy kill (`0x24D6`) |
| `0x492E` | `[0,0,5,0,0]` | **500** | pickup (`0x2585`) |

The port awards **50** per enemy kill (`e_them.c` ×3) and **500** per pickup (`e_bonus.c` ×2),
and builds the super bonus at runtime (`e_sbonus.c`) — matching all three. Had `buf[0]` been the
10^5 digit these would decode to 500 and 5000, contradicting the port. So the pairing behind
R3.17's `(lives+1) × 10,000` is confirmed by three independent data points, not just my reading
of the adder loop.

Also confirmed here: `0x4917..0x491A` are statically zero, as R3.17 argued from the absence of
any instruction referencing them.

### R4.4 — `e_them.c` finding #3 was a **port defect**, fixed ✅

R3.15 flagged `(y & 0xfe)` as "the most likely real defect". It is one, and **both
originals agree against the port**:

| | evidence |
|---|---|
| ST `0x4D5A8` | `move.w (0x4A754).l,D4` / `bclr #0,D4` / `move.w D7,D5` / `bclr #0,D5` / **`cmp.w D4,D5`** |
| PC `0x2913` | `mov ax,[0x7e82]` / `and al,0xfe` / `mov bx,[si+0x4]` / `and bl,0xfe` / **`cmp ax,bx`** |

Both load `y` as a **16-bit word**, clear **only bit 0**, and compare **16-bit**. The PC's
`and al,0xfe` touches just the low byte of `AX`, leaving `AH` intact — so it is
`y & 0xfffe`, not `y & 0x00fe`. The port's mask dropped bits 8-15, and `y` reaches `0x142`,
so an enemy a full 256 px from Rick compared *equal* and switched to `xmove` as though it
had arrived at his level.

Fixed as `(y & ~1)`, **not** platform-switched — the originals agree, the port alone was
wrong. That is defect #7.

The PC routine was identified by content, not citation: the instructions immediately
before (`mov al,[si+0x20]` / `add al,0x8` / `mov ah,[si+0x4]` / `xor ah,[si+0x2]` /
`and ah,0x4` / `inc al`) are the port's sprite formula
`sprbase + 8 + ((x ^ y) & 4 ? 1 : 0)` line for line.

### R4.5 — finding #1 (climb-up velocity) confirmed and implemented ✅

ST `0x4D5CE` `move.w #-0x200,(0x8,A0)` sits **only** on the up path (`subi.w #2,D7` at
`0x4D5C4`), after the env test passes; the down path (`addi.w #2,D7` at `0x4D5D6`) has no
such write. The PC's whole ymove (`0x2968`-`0x29B5`) never writes `[SI+0x2c]`. So this is a
genuine ST/PC difference, now switched under `PLATFORM_ST`. Both platforms build.

### R4.6 — finding #2 (climb gate) is STRUCTURAL, not an `#ifdef` ⭐

The port matches the **PC exactly** on both gates — this was worth checking, because R3.15
had only the ST side:

| gate | PC | port |
|---|---|---|
| 1 (VERT, bit `0x80`) | `0x2A24` `and al,0x7` / `cmp al,0x4`, then `cmp dx,cx` / `jnc` → `enemy.y < rick.y` | line 485 `((x & 0x07) == 0x04) && (y < E_RICK_ENT.y)` |
| 2 (CLIMB, bit `0x02`) | `0x2A7E` `and al,0xe` / `cmp al,0x4`, then `cmp dx,ax` / `jnc` → `enemy.y > rick.y` | line 499 `((x & 0x0e) == 0x04) && (y > E_RICK_ENT.y)` |

So the port needs no fix here; what it lacks is the **ST** variant. But the ST's is not a
different constant in the same shape — it is a different construction, and I stopped short
of implementing it rather than force an `#ifdef` that would be wrong:

1. **Different gate condition.** ST (`0x4D6B4`, `0x4D72C`, identical in both gates):
   `btst #3,D6` / `beq accept` / `andi.b #7,D5` / `bne reject` — i.e.
   `((x & 8) == 0 || (x & 7) == 0)`, against the PC's `(x & 7) == 4` / `(x & 0x0e) == 4`.
2. **The ST snaps the entity onto the ladder; the PC does not.**
   `x = (x & ~0x0F) | 4` (`0x4D6C2`, `0x4D73A`), gate 1 also `y = (y & ~7) | 5`
   (`0x4D6CE`), and both `clr.w (0xa,A0)` — `nPosYFrac` = 0.
3. **Different control flow.** The ST reaches its gate from `bcs 0x4D69C` at `0x4D678`,
   the **blocked** branch of the env test; the port (and PC) test VERT on the
   **not-blocked** branch.
4. **Different animation model.** The ST drives the climb sprite from `nAnimFrameIdx`
   (`0x2A`) — `clr.w` on entering the climb, `addi.w #1` per successful climb step
   (`0x4D5E4`) — where the PC and port compute it as `sprbase + 8 + ((x ^ y) & 4)`.

`OPEN — structural`, in the same class as the dynamite fuse. Item 4 also **narrows an
R3.15 claim of mine**: R3.15 listed "anim-index handling" under *Agree*. That holds for the
walking paths, not for climbing.

### R4.7 — new: entity Y despawn bound differs by one ⭐

Not previously catalogued. The PC deactivates at **`y >= 0x140`**, via a high/low byte
pair rather than a single compare:

- ymove `0x2976`: `cmp bh,0x0` / `jz ok` / `cmp bh,0x1` / `jnz kill` / `cmp bl,0x40` / `jnc kill`
- fall path `0x2A06`: `cmp dh,0x0` / `jz ok` / `cmp dl,0x40` / `jc ok` / kill

The port tests `y > ENT_YMAX` with `ENT_YMAX` = `0x140` (PC) / `0x142` (ST), so it keeps
`y == 0x140` alive where the PC kills it. **Closed: the ST compare is `0x4D34A`** —
`cmp.w #0,D1` / `bge` / `cmp.w #0x142,D1` / `ble ok`, i.e. dead when `y < 0 || y > 0x142`.
That is the port's `y < 0 || y > ENT_YMAX` exactly, so the **ST side is right and the PC
side was off by one**. Fixed via a new `ENT_YDEAD(y)` macro.

Two search notes, both instances of the same standing trap:

- The ST constant is `cmp.w #0x142,Dn` (opcode `B?7C`), **not** `cmpi.w` (`0C4?`). My
  first scan covered only `cmpi.w` and returned zero — with a *working* control (three
  `cmpi.w #0x800` gravity clamps), which is what made the empty result look trustworthy. A
  raw-word scan over the segment found it. A control proves the query shape runs; it does
  not prove the query shape is the *right* shape.
- **The fix was deliberately confined to two of the eight `ENT_YMAX` sites.** `CMP r8,0x40`
  occurs at exactly two addresses in the whole PC segment (`0x298B`, `0x2A0E`) — the two
  verified here. The PC therefore encodes its other bound checks differently, and
  `e_them.c` lines 123/315/695/722 and `e_rick.c:156` remain **unverified**; line 695 uses
  the constant with the opposite sense (`y < ENT_YMAX`) and would have been silently
  shifted by a blanket change. That is defect #8.

### R4.8 — the "Black Magic" PRNG explained, and an out-of-bounds read fixed ⭐

The port's comment says the randomizer *"is an exact copy of what the assembler code does
but I can't explain."* It is now explained — it is the PC's `FUN_0000_024a`:

```
024c  mov bx,[0x7e48]      ; state          <-> e_them_rndnbr
0250  add bx,[0x7e4a]      ; seed low       <-> *sl
0254  add bx,0xd           ;                <-> + 0x0d
0257  mov cx,[0x7e4c]      ; seed high      <-> cx = *sh
025b  add bx,cx
025d  sub al,al
025f  xor al,bl / 0261 xor al,ch / 0263 xor al,cl / 0265 xor al,bh
0267  mov bl,al            ; result back into BX's low byte
0269  mov [0x7e48],bx      ; store state WITH bl replaced   <-> e_them_rndnbr = bx
```

The port reproduces this exactly, including the subtle part — `*bl` aliases `bx`'s low
byte, so writing it before `e_them_rndnbr = bx` mirrors `mov bl,al` preceding the store.
The XOR chain `bl^bh^cl^ch` matches. **The port author's transcription was right.**

**Defect #9, fixed.** `sh` was `(U16 *)&e_them_rndseed + 2`. `e_them_rndseed` is a `U32`,
so `+ 2` on a `U16 *` is **+4 bytes — one U16 past the end of the variable**. Every read
of `*sh` was out of bounds, feeding garbage into both `bx` and `cx`. The PC's operands are
2 bytes apart (`[0x7e4a]`, `[0x7e4c]`), so the correct index is `+ 1`. `0x7e4e` — what
`+ 2` notionally addresses — is an unrelated variable with 10 references elsewhere.

**A suspicion of mine that was wrong, checked before acting.** I expected the port's `U32`
`e_them_rndseed++` to diverge from the PC, on the grounds that the PC increments only the
word at `0x7e4a`. It does not: `0x0270` is `add word[0x7e4a],0x1` immediately followed by
`0x0275` `adc word[0x7e4c],0x0` — a real 32-bit increment across the pair. The port's
single `U32` increment is exactly right.

Caveat recorded, not fixed: the whole construction assumes a **little-endian** host
(`bl`/`bh` alias `bx`; `sl`/`sh` alias the `U32`'s halves). That is correct for matching
the PC and fine on x86/ARM-LE, but it is host-dependent, not portable C.

### R4.9 — finding #4 (the PRNG turn) is also STRUCTURAL

The port again matches the **PC** exactly, and the ST differs in three independent ways:

| | PC / port | ST |
|---|---|---|
| generator | `0x024A`: sum of two seed words + `0x0D`, XOR of the four bytes | `0x49596`: two 32-bit words — `exg d6,d7` / `rol.l #3,d7` / `subq.w #7,d7` / `eor.w d6,d7`, output byte at `0x495C7` |
| decision | `0x2B13` `and al,0x1` → **set** direction, 50/50 | `0x4D7A8` `andi.b #3,d5` / `bne` → **flip**, 1-in-4 |
| direction | signed `offsx` = `+2` / `-2` at `[SI+0x28]` | `nDirection` toggled `0` <-> `0xFF` at `(0x2,A0)`, plus `clr.w (0x2a,A0)` |

Grouped with R4.6 as `OPEN — structural`. A faithful ST variant needs a second PRNG with
its own state, a different decision rule, and the ST's flag-style direction — not an
`#ifdef` around a constant.

Verified as matching while here: the U-turn (`0x2B22` `mov al,[si+0x28]` / `neg al` /
`jnz` / `mov al,0x2`) is the port's `offsx == 0 ? 2 : -offsx` — the PC negates then tests,
the port tests then negates, same result; and the block mask `0x2AFA` `and al,0xf0` is the
port's `VERT|SOLID|SPAD|WAYUP`.

### R4.10 — the inferred explosion sprite was WRONG; corrected from the data segment ❌→✅

With `ibmpc_ds1.bin` based (R4.1), the PC's table at segment `0x179C` offset `0x8138` reads:

```
24 24 25 25 26 26 27 27 28 28 ff
```

Every sprite is **doubled in the table**, and the index is **also halved**
(`0x25AE SHR BL,1`). I had extrapolated the ascending run `0x24..0x28` to a sixth value
`0x29`; the table does not ascend past its pairs at all in the range the box reaches. So
the PC's explosion is **three** sprites over ten ticks —

```
26 26 26 25 25 25 25 24 24 24
```

— not the ascending `29 28 28 27 27 26 26 25 25 24` the inferred array produced. The port's
PC branch now holds the table as read and reproduces that sequence exactly (checked
programmatically against the dump).

Two things that keep this honest rather than lucky:

- **The doubling is corroborated.** Two independent consumers halve the index into the
  same table — `0x25AE` (box) and `0x1A89` (bomb) — so it is the table's real shape, not a
  misread of one site.
- **The segment was verified, not assumed.** `ds2` at `0x8138` holds unrelated
  `ff ff 00 00…`; only `ds1` carries a plausible table, and `ds1` is the segment the code
  loads for game data.

**The lesson, recorded because it cost a wrong value in shipped code:** an inference
labelled as an inference is still an inference. "Strictly better than an overread" was true
and still produced the wrong pixels for months. The pattern `0x24,0x25,0x26,0x27,0x28`
looked like an obvious arithmetic run — and the real data was a doubled sequence that
happens to start the same way.

**ST is structural and stays unimplemented.** `destructible_pickup_update` animates from a
**pointer** table at `0x46C3E` (`0x4D0AC` `move.w (0x2a,A0),D0` / `bclr #0,D0` /
`add.w D0,D0` / `move.l (0,A1,D0.w),D1` / sentinel `-1` / `addi.w #1,(0x2a,A0)`), so entry
*k* serves ticks 2k and 2k+1 — **ten distinct frames × 2 ticks = 20 ticks, counting up**,
against the PC's three sprites over ten ticks counting down. The ten pointers alternate
between two artwork regions (`0x37B9E`+ and `0x2EDDE`+, stride `0x150`). The port's
sprite-number model cannot express that without changing `SEQ_INIT` and the frame source.
The ST branch therefore keeps the port's five ST sprite numbers at two ticks each — the
right *shape*, explicitly not the ST's sequence — with `(cnt-1)>>1` keeping the index in
`0..4`, so the overread is gone on both platforms.

## `e_rick.c` — 2 of the 5 remaining functions done

### R4.11 — `e_rick_gozombie`: one port defect, one platform difference ✅

Located by **content**, at `0x19DA` — the port's citation "ASM 1851" is wrong, as R3.10
predicted for citation arithmetic generally.

**Defect #10, fixed.** The corpse's horizontal drift was `x > 0x80 ? -3 : +3`. Both
originals use **>=**, so at exactly `x == 0x80` the port threw the body the wrong way:

| | |
|---|---|
| ST `0x4C832` | `cmpi.w #0x80,(0x0004a752).l` / **`bge`** → `neg.w (0x0004a750).l` |
| PC `0x19EE` | `cmp al,0x80` / **`jnc`** → `mov byte[0x7d7a],0xfd` |

(The ST carries the drift in `nDirection`, the PC and port in `offsx` — same magnitude 3.)

**Genuine ST/PC difference, now switched.** The upward launch velocity:
ST `0x4C822` `move.w #-0x300,(0x0004a756).l` vs PC `0x19E5` `mov word[0x7d70],0xfc00`
(`-0x400`). The port had the PC's value on both platforms.

Also confirmed matching: `ylow = 0` (ST `0x4C816` `clr.w (0x0004a758).l`).

### R4.12 — `e_rick_z_action`: three parts confirmed, one difference fixed

Reached from the player update's zombie dispatch (`0x1546` `mov al,[0x7d75]` / `or al,al` /
`jz` / `jmp 0x195A`).

**Confirmed identical to the PC, instruction for instruction:**

- sprite `0x19`, `TEST byte[SI+0x2],0x4` → `0x1A` (`0x195A`-`0x1967`) — exactly the port's
  `(x & 0x04) ? 0x1A : 0x19`. I had briefly suspected the PC drove Rick's animation from
  the sequence pointer gozombie sets (`[0x7D9A]` ← `0x7DA9`); it does not, and that
  suspicion was wrong.
- `x += offsx` with **no bound** (`0x196B`-`0x1971`).
- the 16.16 integration with sign extension, and `offsy += 0x80` uncapped
  (`0x1999`) — which the **ST also does** (`0x4C8A8` `addi.w #0x80,(0x0004a756).l`, no
  clamp). All three builds agree here.

**Difference, fixed for the PC branch.** The tumble's end: PC `0x19A1` is
`cmp bl,0x1 / jnz ret` on y's **high byte**, then `mov byte[0x7d92],0xff`. `[0x7d92]` is
zeroed at `0x00C7`, polled by the main loop at `0x0129`, and this is its **only** setter —
so it is `STDEAD`. The PC thus ends the tumble once `y` reaches `0x100`, about `0x40` px
earlier than the port's `y > ENT_YMAX`, and never ends it when the corpse flies off the
**top** (a negative y has high byte `0xff`, not `1`).

**Two ST differences recorded, not implemented** (both T9/structural):

1. The ST **bounces** the corpse off the right edge — `0x4C886` `cmp.w #0xE8,D2` / `blt` /
   `neg.w (0x0004a750).l`, skipping the x store that frame. The PC and port move x
   unconditionally.
2. The ST's tumble animation is **counter-driven**, not x-driven: `0x4C8CA` increments
   `(0x4A778)`, wraps at 4, then `bclr #0` / `add.w D4,D4` into a pointer table at
   `0x46BE6` — 2 frames × 2 ticks — against the port's `(x & 4)` sprite pick. Its exit
   path (`0x4CA54`) is not yet read, which is why the ST branch of the death test is
   marked UNVERIFIED at the site rather than switched.

### R4.13 — `e_rick_save` / `e_rick_restore`: the FIXME resolved, no defect ✅

Located by content at `0x0D2F` (save) and `0x0D50` (restore). The port's citation
"ASM part of 0x0BBB" is **wrong** — `0x0BBB` is an EGA bitplane copy loop
(`ES:[DI+0x800/0x1000/0x1800]`). Third wrong citation in this file.

The PC save/restore is a symmetric five-item pair:

| PC live | PC saved | port |
|---|---|---|
| `[0x7D68]` crawl flag | `[0x7D88]` | `save_crawl` ✅ |
| `[0x7E82]` y (**word**) | `[0x7D8A]` | `save_y` ✅ |
| `[0x7E80]` x (**byte**) | `[0x7D89]` | `save_x` ✅ |
| `[0x7E8A]` = Rick's entity field **+0x0C** | `[0x7D8C]` | *the FIXME's `save_C0`* |
| `[0x7E38]` scroll row | `[0x7D8D]` | `save_map_row` in **`game_save()`** ✅ |

So the FIXME's *"plus some 6DBC stuff?"* is **already handled** — the port just splits it,
keeping the scroll row in `game_save()` rather than `e_rick_save()`. Not a gap.

`[0x7D68]` is confirmed as the crawl flag independently: it gates the crawl sprite at
`0x14B0` (`cmp byte[0x7d68],0` / `jz` → the jump/walk path).

`save_C0` (entity `+0x0C`) is the one genuinely unhandled item, and it is **inert for
Rick**: `[0x7E8A]` has exactly two references in the whole segment, the save and the
restore. The field is used for *other* entities (`[SI+0x0C]` at `0x1E9C`, `0x213F`), but
nothing reads Rick's copy, so saving and restoring it cannot be observed. Left out
deliberately; the FIXME can be closed.

Minor width note, recorded not changed: the PC saves x as a **byte** and y as a **word**;
the port uses `U16` for both, so an out-of-range x would round-trip differently. Not
reachable at the points save/restore run.

### R4.14 — `e_rick_action`: confirmed faithful to the PC, no defect ✅

Every branch compared against `0x1490`-`0x153B`, and all match instruction for
instruction:

| branch | PC | port |
|---|---|---|
| CLIMB | `0x149D` `mov [si+8],0xc` / `mov al,[si+2]` / `xor al,[si+4]` / `and al,0x4` / `jz` / `mov [si+8],0x18` | `((x ^ y) & 0x04) ? 0x18 : 0x0c` |
| CRAWL sound | `0x14BA` `mov al,[0x7d78]` / `inc al` / `and al,0x3` / `jnz` / `call 0x2B68` | `seq = (seq + 1) & 0x03; if (seq == 0) play` |
| CRAWL sprite | `0x14CC` `mov ah,0x7` / dir → `mov ah,0x13` / `test [si+2],0x4` / `inc ah` | `(game_dir ? 0x13 : 0x07)`, `+1` if `x & 4` |
| JUMP | `0x14F3` `mov [si+8],0x6` / dir → `0x1501` `mov [si+8],0x15` | `(game_dir ? 0x15 : 0x06)` |
| walk | `0x1506` `inc al` / `cmp al,0x14` / `jc` / sound / `mov al,0x4`; then `cmp al,0xc` / sound | `seq++; if (seq >= 0x14) {...seq = 4;} else if (seq == 0x0C) {...}` |
| walk sprite | `0x1526` `shr al,1` ×2 / `add al,0x1` / dir → `add al,0xc` | `(seq >> 2) + 1 + (game_dir ? 0x0c : 0)` |

The port's `else if` on `seq == 0x0C` is equivalent to the PC's unconditional second test:
after the wrap `AL` is `4`, which is never `0xC`.

STOP and SHOOT are now read too, and also match: `0x1466` `mov [si+8],0xb` / dir →
`0x1474` `mov [si+8],0x17`; `0x1483` `mov [si+8],0xa` / dir → `0x148E` `mov [si+8],0x16`.
**`e_rick_action` is fully verified with no defects.**

### R4.15 — `e_rick_action2`: terminal-velocity clamp matched NEITHER original ⭐ (defect #11)

The port's fall clamp was

```c
offsy += 0x0080;
if (offsy > 0x0800) { offsy = 0x0800; ylow = 0; }
```

which is the **ST's edge combined with the PC's `ylow` reset** — a mix that matches
neither build:

| | edge | clamp branch |
|---|---|---|
| ST `0x4C150` | `cmpi.w #0x800` / `ble` → clamp when `offsy` **> 0x800** | `0x4C15C` sets `offsy` **alone**; `ylow` was stored at `0x4C142` and is left as computed |
| PC `0x160A` | `cmp dh,0x8` / `jc` → clamp when `offsy` **>= 0x800** | `0x1612` `mov byte[0x7d72],0` **zeroes ylow**, then `0x1617` sets `offsy` |

The edge is not academic. `offsy` steps `0x100, 0x180, …`, so it lands **exactly** on
`0x800` (`0x100 + 0x80×14`) on every long fall. On that frame the PC zeroes `ylow` and the
ST does not — and the port, clamping only above `0x800`, zeroed `ylow` a frame late on the
PC side while zeroing it at all on the ST side, which the ST never does.

Now switched. Both platforms build.

**The same edge exists in `e_them.c` and is inert there** — checked rather than assumed.
PC `0x2A4C` `cmp ah,0x8 / jc` (>=) vs ST `0x4D68A` `cmpi.w #0x800` / `ble` (>) and the
port's `>`; but neither enemy clamp branch touches `ylow`, and clamping a value that
already equals `0x800` to `0x800` is a no-op. No change needed.

**Confirmed matching in `action2` while here**, instruction for instruction: the crawl
env-test split (PC calls `0x113A` when crawling, `0x11BC` when not, then clears the crawl
flag if `env0 == 0` — the port's `u_envtest(..., STTST(STCRAWL), ...)` plus
`if (STCRAWL && !env0)`); the vertical block mask (`BH = 0xF0`, or `0xE0` when
`offsy < 0`, i.e. dropping `WAYUP` — `0x15AE`-`0x15BA`); `STSET(STJUMP)` (`0x15CB`);
`LETHAL` → gozombie (`0x15D0` `test cl,0x4`); the y/ylow store; the climb entry
(`test cl,0x2` + control `& 0x0C` → `offsy = 0x100`, `STCLIMB`); and `seq = 2` when
neither LEFT nor RIGHT is held (`0x1621` `and al,0x3`).

All eight `MAP_EFLG_*` values are now corroborated by the masks decoded across both
binaries: `VERT 0x80`, `SOLID 0x40`, `SPAD 0x20`, `WAYUP 0x10`, `LETHAL 0x04`,
`CLIMB 0x02`.

### R4.16 — the `y & 0xf8` tile snap truncated the high byte: FOUR sites ⭐⭐

Same defect class as R4.4, and the port **contradicted itself**, which is what exposed it:

| site | had | correct? |
|---|---|---|
| `e_rick.c:338` ceiling bonk | `y &= 0xF8` | ❌ truncating |
| `e_rick.c:352` ground align | `y &= 0xF8` | ❌ truncating |
| `e_them.c:544` ground align | `(y & 0xf8) \| 0x03` | ❌ truncating |
| `e_them.c:156` ground align | `y &= 0xfff8` | ✅ (the same author, doing it right) |

**Both originals mask the LOW BYTE ONLY**, keeping the high byte:

- PC `0x16A2` / `0x16B8` / `0x2A5B` — `and al,0xf8` (`or al,0x3`), 8-bit ops on `AL`
- ST `0x4D6F0` — `move.b (0x7,A0),D7` / `andi.b #-8,D7` / `ori.b #3,D7` / `move.b D7,(0x7,A0)`

`y` is `S16` and reaches `0x142`, so a 16-bit `& 0xf8` also cleared bits 8-15: an entity at
`y = 0x108` was snapped to `0x08` — teleported from the bottom of the world to the top.
All four now use `& ~0x07`, which reproduces the byte-wide mask exactly for every value,
**including negative y**, where even the "correct" `0xfff8` was wrong (`-8 & 0xfff8` yields
`65528`, not `-8`).

`ents.c:236` and `ents.c:288` also use `& 0xf8` but on `map_marks[].row`, a row index, not a
position — correctly left alone.

That is defects #12-#14 (three truncating sites; `e_them.c:156` was a latent-only fix).

### R4.17 — the rest of `e_rick_action2` confirmed against the PC

Compared `0x168F`-`0x1706` and `0x161E`-`0x162E` against the port's `vert_not`, super-pad
and horizontal blocks. All match:

- ceiling bonk: `and ax,ax` / `jns` → `mov word[0x7d6e],0xff` (STJUMP), low-byte snap,
  `mov byte[0x7d72],0` (ylow), `mov word[0x7d70],0` (the PC's zero vs the ST's `0x80`,
  already switched), `jmp 0x161E` → horiz
- standing: `(y & 0xf8) | 3`, ylow = 0
- super pad: `test cl,0x20` (SPAD), `js` + `cmp al,0x2` / `jc` → the port's
  `offsy >= 0x0200`; then `test byte[0x7d6c],0x8` (UP) → `mov cx,0xf800`, else
  `mov cx,0xfe` / `sub cx,bx` — the port's odd `0x00fe - offsy` is **exactly right**
- reset `offsy = 0x100` (`0x16FC`); `seq = 2` when neither LEFT nor RIGHT (`0x1621`)

All eight `CONTROL_*` bits are now corroborated too: `UP|DOWN = 0x0C` (`0x15EA`) and
`LEFT|RIGHT = 0x03` (`0x1621`) match `control.h`'s `0x08|0x04` and `0x02|0x01`.

### R4.18 — `e_rick_action2` firing / firing_not / climbing: confirmed, 3 notes

Compared `0x1702`-`0x18BA` against port lines 368-497. Everything matches, including
several things that looked odd in the port and turn out to be faithful:

- **stop/stick**: `0x1722` `mov ax,[si+4]` / `add ax,0xe` → `stop_y = y + 0x0E`;
  `mov byte[0x7d79],0x1` then, if RIGHT, `mov byte[0x7d79],0x0` / `add al,0x17` →
  `stop_x = x + 0x17`. Confirms `LEFT=1` / `RIGHT=0` in `game.h` against `[0x7D79]`.
- **bullet**: `STSHOOT`; `[0x7D86]` trigger one-shot; `[0x7EAE]` bullet-in-air;
  `[0x7E45]` bullets, `dec` — all in the port's order. `[0x7E45]` = bullets also
  **corroborates R3.17's** reading of the `0x7E45`/`0x7E46`/`0x7E47` triple.
- **jump**: `0x181E` `mov word[0x7d70],0xfa80` = `-0x580` ✓, `ylow = 0` ✓.
- **crawl vs climb-down**: `0x1848` `and al,0x3` / `jnz` (moving horizontally → crawl);
  `0x1852` `and al,0x1f` / `cmp al,0xa` / `jnc` → the port's `(x & 0x1f) < 0x0a`;
  `(x & 0xF0) | 4` align; `STCLIMB`, else `STCRAWL` and fall through to horiz.
- **super-pad** `0x00fe - offsy` and the climbing `seq = 0` on no direction
  (`0x1876` `and al,0xf`) both exact.

**The port's `/* FIXME what? */` at line 485 is explained.** `0x18AC` `jz` on
`and al,0x70` then `0x18B1` `test ch,0x80` — `CH` is the high byte of the move delta
(`0xFFFE` up, `0x0002` down), so "blocked **and moving down**" clears `STCLIMB`. It is the
climb-down-into-ground case; the port's `!(control_status & CONTROL_UP)` is equivalent,
since the delta is `-2` exactly when UP is held.

**Two differences recorded, not changed:**

1. **The climbing env test.** PC `0x18A2` calls `0x11BC`, the **plain** probe, while the
   port passes `E_RICK_STTST(E_RICK_STCRAWL)` (line 482), which selects the crawl probe
   (`0x113A`) when crawling. This matters only if `STCRAWL` and `STCLIMB` can be set at
   once — the climb entries at `0x1818`/`0x1865` do not clear `STCRAWL` — so it is
   probably reachable, but I have not proven it. `OPEN`.
2. **The bullet/bomb control test.** PC: `and al,0xc` / `cmp al,0x8` — UP set, DOWN clear,
   **other bits ignored** (`LEFT|RIGHT` were already consumed by the stop path). Port:
   `control_status == (CONTROL_FIRE|CONTROL_UP)`, an exact byte equality that additionally
   requires `PAUSE`/`END`/`EXIT` (`0x80`/`0x40`/`0x20`) to be clear. Equivalent in normal
   play; not identical.

**Checked and left alone:** `E_RICK_ENT.x &= 0xf0` (line 457) has the R4.16 shape but is
provably equivalent — the PC is byte-wide (`0x185E and al,0xf0`) and the port's `x` never
reaches `0x100`, the submap exit firing at `x >= 0xe8`.

## Phase 3b closed

### R4.19 — `map_expand`: identical in all three builds, no defect ✅

| | PC `0x0EE6` | ST `0x49E40` | port |
|---|---|---|---|
| base | `sub ah,ah` / `add ax,ax` / **`and ax,0xfff8`** / `add ax,[0x7e3a]` | `andi.w #-4,D0` / `add.l D0,D0` / `adda.l D0,A2` | `(2 * map_frow) & 0xfff8` + `map_submaps[].bnum` |
| rows | `mov dh,0xb` (11) | `move.w #0xa,D1` + `dbf` (11) | `i < 0x0b` |
| blocks | `mov cx,0x8` | `move.w #0x7,D2` + `dbf` (8) | `j < 0x08` |
| block index | `add ax,ax` ×4 (×16), `add ax,0x423a` | `lsl.l #4,D0`, `lea (0x22fee).l,A3` | `map_blocks[map_bnums[pbnum]]` |
| row stride | `add di,0x1c` after 4 tiles → `0x20` | `(0x20,A1)` / `(0x40,A1)` / `(0x60,A1)` | `map_map[0x2c][0x20]` |
| next block | `add di,-0x60` | `lea (0x4,A1),A1` | `row -= 4; col += 4` |
| next row | `add di,0x60` | `lea (0x80,A0),A0` | `row += 4; col = 0` |

The port's `(2 * map_frow) & 0xfff8` is the **PC's instruction verbatim**; the ST reaches
the same value as `2 × (frow & ~3)`. `map_map[0x2c][0x20]` is confirmed by both: 32 columns
matches the row stride, 44 rows = 11 block-rows × 4.

`[0x7E38]` is the PC's `map_frow`, which **independently corroborates R4.13**, where I
identified it as the saved scroll row purely from its save/restore pairing.

**Phase 3b is now complete.**

### R4.20 — `map_blocks` is identical PC/ST; `map_bnums` is not extractable from this dump

- **`map_blocks` (4096 bytes) matches BOTH** — `ibmpc_ds1.bin` at `0x423A` and
  `atari_ram.bin` at `0x22FEE`, byte for byte. **No ST variant needed.** One Phase 1 table
  closed.
- **`map_bnums` (R4.2) still needs an ST source.** The ST does not hold it at a fixed
  address: `0x49E42` `movea.l (0x000495CC).l,A2` reads a **pointer**, written at `0x499F6`
  by `move.l (0x2,A0),(0x000495CC).l` — i.e. from field `+2` of the submap record, the ST's
  analogue of `map_submaps[].bnum`. In `atari_ram.bin` that pointer is **`0x00000000`**, so
  the dump was taken with no submap loaded and the table cannot be read from it.
  Extracting the ST block numbers needs a dump taken **in game**, or the submap records
  walked to recover the pointers. `OPEN`.

This also explains why my earlier adjacency guess failed: `map_blocks` and `map_bnums` are
contiguous on the PC (`0x423A` + `0x1000` = `0x523A`) but not on the ST — I tested
`0x22FEE + 0x1000` and got 1.9% agreement. Guessing a layout from the other platform is
not evidence.

### R4.21 — `e_box.c` R3.9 #1 and #2 resolved ✅

Both open findings closed by reading the PC's box routine (`0x2592`-`0x2648`), decoded by
hand after Ghidra mis-aligned on the `NOP` padding.

**#1 test order — the port is RIGHT, my R3.9 note framed it wrongly.** The PC is:

```
25CC  call 0x12AE          ; e_rick_boxtest
25D1  jz   0x2629          ; overlap -> COLLECT
25D6  mov al,[0x7d6a]      ; STSTOP -> stick test  (u_fboxtest via 0x1317)
25F8  mov al,[0x7eae]      ; bullet in air -> bullet test
2619  mov al,[0x7d85]      ; e_bomb_lethal -> bomb test (0x134B)
25F0  mov byte[si+0x26],0xa / or byte[si],0x80   ; explode: cnt = 10, ENT_LETHAL
2629  ...collect: n==0x10 -> [0x7e47]=6 (bombs), else [0x7e45]=6 (bullets), n=0
```

That is **collect first, then stick, bullet, bomb** — the port's order exactly. The ST's
order (stick → bullet → explosion → collect) is the outlier, so this is an ST/PC
difference and the port needs no fix. R3.9 recorded it as "port vs ST" without the PC
side; with the PC read, the port is vindicated.

The collect also re-confirms the `0x7E45`/`0x7E46`/`0x7E47` triple a third time:
`cmp al,0x10` / `jnz` selects `[0x7E47]` for bombs and `[0x7E45]` for bullets, leaving
`[0x7E46]` = lives — the reading R3.17's per-life bonus depends on.

`0x2592` is `mov bx,[si+0x12] / inc bx / or byte[bx],0x80` = the port's
`map_marks[mark].ent |= MAP_MARK_NACT`.

**#2 exploding box kills Rick — confirmed ST-only, now implemented.**

```
4D0CC  bsr 0x4D9AA / bcc 0x4D0DA / move.w #0xff,(0x0004bf2e).l
```

`(0x4BF2E)` is verified as the kill flag rather than assumed: cleared once, set at five
sites, and **tested at `0x4C06A`** — `tst.w` / `beq`, and when set it runs `bsr 0x4C7E4`
then `bra 0x4C8CA`, the kill routine followed by the death tumble decoded in R4.12.

The PC's box routine never probes Rick while exploding, so the port (PC-derived) was
correct for its platform and merely missing the ST behaviour. Added under `PLATFORM_ST`
using `e_rick_boxtest()`, which is the right analogue: `0x4D9AA` has **6 callers**
including the box's own collect path at `0x4D088`, i.e. it is the general
entity-overlaps-player probe. No early return, matching the ST — both its paths `rts` and
the animation index was already advanced at `0x4D0C2`.

**`e_box.c` is now fully compared.** Its only remaining item is the ST's 10-frame pointer
animation (R4.10), which stays structural.

## Phase 1 tables — `ent_sprseq` and `ent_mvstep`

### R4.22 — the port's data came from a DIFFERENT PC build than `ibmpc_ds1.bin` ⭐⭐

Established, not guessed. The tail of the port's `ent_mvstep` and the corresponding region
of `ds1` hold the same structure — 8-byte records of three 16-bit values plus a `0000` —
with the port's values **a constant lower**:

```
port  80 42 | 8a 76 | 35 79 | 00 00      ds1  3a 52 | 44 86 | ef 88 | 00 00
```

Across 195 records the dominant non-zero delta is **`0x0FBA`, 178 times** (with 307 exact
zeros, the terminators). A single constant offset across a whole table means these are
**pointers**, and the port's source binary had its data segment `0x0FBA` lower than the one
captured in `ibmpc_ds1.bin`.

This is consistent with `map_bnums` and `map_blocks` matching `ds1` **exactly** (R4.2,
R4.20) — those hold no pointers, so relocation cannot show up in them.

### R4.23 — `ent_sprseq`: correct, but its declared length overruns into the next table

The first **128 bytes match `ds1:0x8143` exactly**. But the last 7 of those
(`10 00 00 0c 00 04 fa`) are the **opening bytes of `ent_mvstep`**, which begins at
`ds1:0x81BC`: the real sprite-sequence data ends with the `0xff` at `0x81BB`, i.e. **121
bytes**, not 128. The port then appends 8 more it marks `/* xtra */`, reaching the declared
`ENT_NBR_SPRSEQ 0x88` = 136.

So the table is right where it is used and wrong past its true end. Sequences are walked to
an `0xff` terminator, so the trailing bytes are unreachable unless something indexes them
directly. **Not changed** — recorded, because shortening a declared array without tracing
every index is how one turns an inert oddity into a crash.

### R4.24 — `ent_mvstep`: 261 records match; the rest is a different table

- Records `0`-`260` (**785 bytes**) match `ds1:0x81BC` — with **one byte of divergence**:
  `ds1` carries an extra `0x90` at port offset `0xF`, after which the two streams realign
  and run together for the remaining 770 bytes.
- From byte 785 the port's array is the **pointer table** of R4.22, not movement steps at
  all. `mvstep_t` is `{U8 count; S8 dx, dy}`, so those 1,567 bytes parse as nonsense
  movement records.

**It is inert.** `step_no` is seeded from `ent_entdata[].sni`, whose maximum across all 79
rows is **244**, below the last valid record (261), and sequences terminate on
`count == 0xff`.

**The `0x90` is left alone, deliberately.** Two readings fit and I cannot separate them
from this dump: either the port dropped a byte when transcribing, or the two PC builds
genuinely differ here — and R4.22 proves they *are* different builds. The port's parse is
the self-consistent one (`{0x46, 8, 0}` = 70 frames, dx 8, dy 0), while the `ds1` alignment
would give `{0x90, 0x46, 0x08}` — 144 frames at dx 70, which is not plausible movement
data. Changing a table that currently produces correct behaviour, on a one-byte difference
between two builds, is not a fix.

Still unchecked in Phase 1: `dat_spritesST`, `dat_picsST` (ST artwork, a separate job).

## Group B — the seven bounded questions, all closed

### B1 `map_maps[4]` ✅ AGREE (slot is dead on all three)
The PC **does** hold a distinct 5th record at `ds1:0x80EF+32`: `x=0x74, y=0xC8, row=8` —
exactly the port's `map_maps[4]`. But `0x0DF9` `cmp al,4 / jb` means the start-position
lookup **never runs for map 4**; the PC sets the game-complete flag and returns, and the
port likewise ends at `env_map >= 0x04`. The ST's slot 4 duplicates map 0. Dead everywhere;
the port's PC-matching values are correct and inert. **No change.**

### B2 `map_frow` width ✅ concern retired — it was unfounded
The original worry ("an intermediate that went negative would wrap at 8 bits") is **wrong**:
in `map_frow - rowout + rowin` (`map_chain`, `maps.c:208`) C promotes to `int`, so no
intermediate wraps; only the final store truncates. The one expression that *can* go
negative — `map_frow = map_connect[i].rowin - 0x10` with `rowin == 0` (55 of 154 rows) — is
in the `else` of `if (sysarg_args_submap == 0)`, i.e. the **port-only `-submap` debug
option**, which has no counterpart in either original. The PC scrolls `[0x7E38]` as a word
(`inc ax` `0x0FD5` / `dec ax` `0x1043`) and the port as `U8` (`scroller.c:76/144`), which
agree over the legitimate range. **No change.**

### B3 `ent_entdata` rows 3/22/23 ✅ AGREE — the ST blanks are real
Read from `object_type_defs` at `0x47D34` (16 bytes/entry, `+2` = W, `+4` = H): entries
**3, 22, 23 are all `w=0, h=0`**, as are unused slots 0 and 2, against `0x18/0x15` for
normal entries. The port's ST branch already carries exactly this. **Verified, no change.**

### B4 the climbing env probe ⭐ **defect #15, fixed (2 sites)**
The PC has exactly **two** crawl-dependent probe pairs — non-climbing vertical
(`0x1596` crawl / `0x15AB` plain) and horizontal (`0x166D` / `0x1673`) — matching port
lines 234 and 320. Both **climbing** probes, `0x18A2` and `0x191E`, call the **plain**
entry unconditionally. The ST has no crawl parameter to this probe at all: `(0x4DC28)` is a
result **mask** (`and.b (0x4DC28).l,D0` @ `0x4DBFC`) written only from `enemy_ai_update`.
Both originals agree; the port alone passed `STCRAWL`, shortening the probe by a row
whenever `STCRAWL` and `STCLIMB` were both set. Now `FALSE` at both sites.

### B5 bullet/bomb control test ⭐ **defect #16, fixed**
PC `0x174B`: `and al,0xc / cmp al,0x8` (UP set, DOWN clear, **all other bits ignored**);
PC `0x17CD`: `test dh,0x4` for the bomb. FIRE is required upstream at `0x1713` and
LEFT|RIGHT consumed at `0x171B` — precisely the port's own flow. The port's
`control_status == (FIRE|UP)` byte-equality additionally demanded `PAUSE`/`END`/`EXIT` be
clear, and refused to act on UP+DOWN where the PC drops a bomb. Now masked.

### B6 spawn banding ⭐⭐ **defect #17, fixed**
The PC's `map_init` (`0x0E82`-`0x0EA0`, three `CALL 0x2089` with DH = first row,
DL = count) scans `frow+8`/`0x18`, `frow`/`8`, `frow+0x20`/`8` — i.e.
**`frow+0x00 .. frow+0x27`**, the same total the ST covers with its five 8-row bands. The
port's `MAPS_VISHEIGHT_TL 0x20` made it scan `frow+0x00 .. frow+0x2F`, **activating
entities eight rows below anything either original reaches**. Corrected to `0x18`, which
the port's own constants already implied: `MAP_ROW_SCRTOP 0x08 .. SCRBOT 0x1F` is `0x18`
rows, `MAP_ROW_HBTOP 0x20`, and `MAP_ROW_HBBOT` is **`0x27`** — exactly the last row both
originals scan.

### B7 `maps_clip` left edge ⭐ **defect #18, fixed**
`maps_clip(U16 *x, ...)` tested `if (*x < 0)` — dead by construction. It is **reachable**:
`ent_addrect()` declares `U16 x` but is called with `ent_ents[i].x`, an `S16` that goes
negative as an entity leaves the left edge (`ents.c:407-432`). A negative x arrived as
`0xFFxx`, fell into the `else`, tripped `*x > MAPS_WIDTH_PX` and the **whole rectangle was
dropped** — so the entity's erase rectangle was skipped and it smeared off the left edge.
Fixed by reading the value back as `S16` inside `maps_clip`, rather than converting five
call sites and their callers; `<= 0` rather than `< 0`, since a zero-width rectangle is not
worth queuing.

## Group A — the six structural items, all implemented

### A6 ⭐⭐⭐ the pointers-vs-numbers model (T9) — **SOLVED**

The root cause under A1, A2, A4 and A5, open since T9. The ST holds animation frames as
**pointers**; the port holds **sprite numbers**. They are related by a single affine map:

```
sprite index = (ST pointer - 0x2BE9E) / 0x150
```

`0x150` is `sizeof(sprite_t)` — `typedef U32 sprite_t[0x54]` under `GFXST`, i.e. exactly the
stride between consecutive ST frame pointers. The base was derived from **one** anchor: the
death-tumble table at `0x46BE6` holds `0x2DF6E`/`0x2E0BE`, and the port draws the tumble
with sprites `0x19`/`0x1A`.

It then **predicts, without further fitting**, the sprite numbers the port already uses in
five other places — which is what makes it evidence rather than a curve fit:

| ST table | decoded | port already used |
|---|---|---|
| `0x46BC2` | `02 03 04 05 06` | walk, `(seq >> 2) + 1` |
| `0x46BDA` | `07 08` | crawl, `0x07` `+1` on `x & 4` |
| `0x46B9E` | `0C 18` | climb, `0x0C` / `0x18` |
| `0x46BE6` | `19 1A` | tumble (the anchor) |
| `0x46C3E` | `90 24 91 25 92 26 93 27 94 28` | box explosion `0x24..0x28` |

Every pointer in the region divides exactly — remainder 0 in all cases, none out of range
(`< SPRITES_NBR_SPRITES 0xD5`). The port's own sprite sheet and the ST's are the same
ordering.

*Method note:* the first table scan found nothing because it stepped by 4 from an aligned
origin and `0x46BE6` is not 4-aligned relative to it. Re-scanned at every byte offset.

### A1 — dynamite fuse ✅ implemented
ST fuse = the 17 pointers at `0x46BF2` -> `0x22 0x23 0x81..0x8F`, each held **two** ticks
(`0x4CAC8` `bclr #0,D0 / add.w D0,D0`), so 34 fuse ticks; `E_BOMB_TICKER` is `0x2B` on ST
(34 + 9) against the PC's `0x2D` (45). The port had the right *shape* — two frames then
fifteen — but the wrong second range, `0x99..0xA7` instead of `0x81..0x8F`.
**The port's `x -= 4` / `y -= 5` at detonation is confirmed exactly right**: `0x4CB06` sets
the lethal flag then does `subi.w #4` on x and `subi.w #5` on y. Its author's comment was
faithful, as R3.13 suspected.

### A2 — `e_them` climb gate ✅ implemented
Both gates: condition `((x & 8) == 0 || (x & 7) == 0)`, `y <= rick.y` (gate 1, inclusive) /
`y > rick.y` (gate 2), then `x = (x & ~0x0F) | 4`, gate 1 also `y = (y & ~7) | 5`, both
`ylow = 0`. **The control-flow worry from R4.6 dissolved on inspection**: the ST's carry is
`(env & 0xD0) != 0` (`0x4DC0E` `andi.b #-0x30,D0 / bne`) = VERT|SOLID|WAYUP, so a VERT tile
sets it and the explicit VERT test re-selects the very case the port reaches through
`!(env1 & 0x70)` then `env1 & VERT`. No restructuring needed.

### A3 — `e_them` PRNG turn ✅ implemented
Second generator added: two 32-bit words, `exg / rol.l #3 / subq.w #7 / eor.w` (`0x49596`),
seeded from the values in `atari_ram.bin`. Decision `(byte & 3) == 0` -> **flip** `offsx`,
against the PC's `and al,0x1` -> **set** it. The ST's gate is its frame counter
(`cmpi.w #8,(0x2a,A0)` @ `0x4D790`) where the port's is the position (`(x & 0x1e) == 8`);
both fire every 8 steps, so the gate is left as the port has it and only the generator and
rule are switched. The PC's "Black Magic" locals are now `#ifndef PLATFORM_ST`.

### A4 — `e_box` ST explosion ✅ implemented
Ten frames `0x90 0x24 0x91 0x25 0x92 0x26 0x93 0x27 0x94 0x28`, two ticks each,
`SEQ_INIT` `0x14` on ST (20 ticks, counting **up**) against the PC's `0x0A` (10, counting
down). Indices verified to span exactly 0..9.

### A5 — `e_rick` corpse ✅ implemented
(a) The tumble sprite is **tick-driven** on the ST: a counter wrapping at 4, `bclr #0`,
giving `0x19 0x19 0x1A 0x1A` — not the port's `(x & 4)`.
(b) The corpse **bounces off both edges** (`0x4C86E`-`0x4C892`): moving left with
`nx <= 0`, or right with `nx >= 0xE8`, negates the drift and **skips** the x store that
frame. The port drifted straight through.

## The SPAD blocked-test item — inert, closed

Flagged while resolving A2: the ST's env-test carry is `(env & 0xD0) != 0` (`0x4DC0E`
`andi.b #-0x30,D0 / bne`) = VERT|SOLID|WAYUP, which **excludes SPAD (0x20)**, where the PC
masks with `0xF0`/`0xE0` and the port with `0x70`. On its face a falling enemy would drop
through a super pad on the ST but land on it on the PC.

**It cannot happen.** Every SPAD tile also carries SOLID, which *is* in the ST's mask:

| source | SPAD tiles | SPAD **without** SOLID |
|---|---|---|
| ST per-tile LUT `0x49F1E` (page 0) | 3 | **0** |
| ST per-tile LUT `0x4A01E` (page 1) | 1 | **0** |
| port `map_eflg_c` ST, pages 0/1 | 3 / 1 | **0 / 0** |
| port `map_eflg_c` PC, pages 0/1 | 3 / 1 | **0 / 0** |

The four tiles are `0xBE`, `0xBF`, `0xC0` (page 0) and `0xD8` (page 1), and all four have
SOLID set. The ST's carry is therefore set for every SPAD tile regardless, and the mask
difference can never change an outcome. `AGREE` in effect. No change.

*(Method note: my first expansion of `map_eflg_c` produced 512 tiles per page. The real
`map_eflg_expand` advances `i` twice per iteration — `j = map_eflg_c[offs + i++]` inside a
`for (... i++)` — so it reads **8** pairs per page, not 16.)*

## C1 — ST `map_bnums` ✅ RESOLVED by an in-game dump; **no code change needed**

**The dump was produced here**, with the existing harness: `re/hatari_probe.py boot` boots
`disks/chaos43/RICK.PRG` under Hatari, drives to gameplay by poking the joystick byte, and
`Session.to_game()` already calls `dump_ram()` -> `savebin 0 0x100000`. The run reported
`delta = -0x2054`, the track-table self-check **PASS**, and the `player_controller`
breakpoint **fired** — so the snapshot is genuinely in gameplay. Output:
`re/hatari/ram.bin` (1,048,576 bytes).

`(0x495CC)`, null in `atari_ram.bin`, now holds **`0x0001EFCA`**, and the table there is
`46 46 46 46 …` — the port's `map_bnums` head. The table's extent is confirmed by what
follows it: `map_blocks` begins immediately at `+0x1FD8`, matching `MAP_NBR_BNUMS`.

**The ST table is the port's with exactly two `0x00` bytes missing at `+0x1A88`** —
`port[0x1A8A:] == ST[0x1A88:]`, **1358/1358 bytes, 100%**. The first 6,792 bytes are
identical, and the two tails have identical value histograms.

**And the offsets compensate exactly.** The ST's room header is
`{U16 page; U32 blocks_ptr; U32 connect_ptr; U32 mark_ptr}` (14 bytes; `[0]`'s pointer is
the table base itself). Deriving each submap's offset as `blocks_ptr - 0x1EFCA`:

- submaps **0-37**: identical to the port's `bnum`
- submaps **38-46**: exactly **`-2`**, matching the two missing bytes

Those nine are precisely level 4 (`map_maps[3].submap == 0x26 == 38`). Verified directly:
for **all 47 submaps**, `ST_table[ST_offset .. +0x78] == port_table[port_bnum .. +0x78]`.

**So the rendered maps are identical.** The 2-byte difference is a layout artifact between
the two builds — the PC carries two padding bytes the ST does not, and each build's offsets
account for its own table. ❌ **R4.2's "`map_bnums` now needs an ST variant" is retracted**:
the port's PC table with PC offsets is exactly equivalent. `AGREE`.

## Group G — game state machine (`game.c`) and intro screens

### G1 ⭐ scroll threshold — **defect #19**, and a spurious switch removed

The port had the low scroll trigger platform-switched, `0x5F` on ST and `0x60` on PC, from
an `xref.md` row that read the two constants as a genuine difference. **They are the same
test written two ways:**

```
PC  0x018B  cmp al,0x60  / jnc skip   ->  scrolls when y <  0x60
ST  0x4DD0E cmpi.w #0x5f / bgt skip   ->  scrolls when y <= 0x5F
```

The port's PC branch used `y <= 0x60`, scrolling one row early at exactly `y == 0x60`,
where **neither** original scrolls. Fixed to `<= 0x5f` and the `#ifdef` deleted. The high
threshold needs no switch either — PC `0x017E cmp al,0xcc / jc` and ST `0x4DD1E
cmpi.w #0xcc / blt` both scroll up at `y >= 0xCC`, which the port already had.

### G2 — `init()` ✅ AGREE
PC `0x0032`-`0x0083`: `[0x7E46]=6` lives, `[0x7E45]=6` bullets, `[0x7E47]=6` bombs, score
set to `"000000"` (three `MOV word,0x3030`), Rick's x/y from the map table at `0x80EF`,
then `[0x7E8C]=0x18` and `[0x7E8E]=0x15`. Every one matches the port. Those last two also
**confirm the `ent_t` layout independently**: Rick's base is `0x7E7E`, so `+0x0E` is `w` and
`+0x10` is `h` — exactly the port's `b0E`/`b10` field comments.

### G3 — `restart()` ✅ AGREE, and a port FIXME answered
PC `0x00C7` does, in the port's order: clear `[0x7D92]` (STDEAD) and `[0x7D75]` (STZOMBIE),
`[0x7E7E]=1`, bullets 6, bombs 6, then `CALL 0x0D50`. So the port's
`ent_ents[1].n = 1; // FIXMEwhy??` is simply what the PC does. `CALL 0x0D50` is
`e_rick_restore`, **corroborating R4.13's identification**, and it restores `map_frow`
inside itself where the port restores it separately in `game.c` — same net effect.

### G4 — death path ✅ AGREE
PC `0x0134`: `mov al,[0x7e46] / dec al / mov [0x7e46],al / jnz restart`, else game over.
That is the port's `if (env_trainer || --env_lives)` exactly (`env_trainer` being a port
cheat). Ammo reset on map change also matches (`[0x7E45]`/`[0x7E47]` = 6, PC `0x0DC8`).

### G5 — hall of fame ✅ **both tables verified against their own binaries**

| | source | result |
|---|---|---|
| port `GFXPC` table | `ibmpc_ds2.bin:0x46A5` | **exact** — all 8 names and scores, in order |
| port `GFXST` table | `atari_ram.bin:0x48E38`, stride `0x1E` | **exact** — SIMES, JAYNE, DANGERSTU, KEN, ROB^N^BOB, TELLY, NOBBY, JEZEBEL, leading BCD `008000` |

The PC table has a **ninth** row (`000000`, blank) which is *not* a hall-of-fame entry: the
qualification loop at `0x203D` is `mov si,0x46a5 / mov cx,0x8` — **8** entries. So the
port's 8-entry array and its `game_hscores[7]` threshold are right.

`OPEN`, minor: the port qualifies on `env_score >= game_hscores[7].score` where the PC's
digit compare (`jc` = strictly less) appears to need *greater than*. A difference only at
exactly 1000; the PC's equal-digit continuation was not traced.

### G6 — `scr_imap.c` tables
`screen_imapsl` (22 bytes) matches `ibmpc_ds1.bin:0x9736` **exactly**.
`screen_imapsteps` (23 records of 4 `U16`) matches **nothing** in any dump under byte,
LE16 or BE16 encodings — the port has reformatted it, so this screen must be compared
behaviourally rather than by content. `OPEN`.

## R2 — the render layer (24 functions), swept for *what* is drawn

Scope per the user: which bytes reach the screen and when, not how SDL puts them there.

### R2.1 ⭐ `scroller.c` — **defect #20**, entity despawn during scroll
The PC translates entities with **one shared routine** (`0x10B2`) used by both scroll
directions, applying **both** bounds on every entity, every step:

```
10CA  add word[si+0x1e],bx     ; ysave += delta      (+0x1E = ysave)
10CD  add word[si+0x18],bx     ; trig_y += delta     (+0x18 = trig_y)
10D0  mov ax,[si+0x4] / add ax,bx
10D5  test ah,0x80 / jz        ; y <  0      -> mov byte[si],0
10E3  cmp ax,0x140 / jc        ; y >= 0x140  -> mov byte[si],0
```

The port **split** them — `scroll_up` kept only `y < 0`, `scroll_down` only
`y > 0x0140` — and used `>` where the PC uses `>=`, so an entity sitting exactly on
`0x140` survived a scroll the PC would have removed. Both now use `ENT_YDEAD()`, which
also supplies the right per-platform bound: the ST's is `0x142`, not `0x140`
(`0x4B0C8 cmp.w #0x142,D2 / ble`, and `0x4D352`). `0x140` does not appear as a comparison
anywhere in the ST.

Everything else in `scroller.c` **agrees**: 8 steps (`mov cx,0x8` @ `0x0F87`), entity
delta `±8` (`mov bx,0xfff8`; ST `move.w #-8,(0x4A700)` @ `0x49C8C`), `map_frow++/--`
(`0x0FD5`/`0x1043`), and the end-of-scroll bands — PC `add dh,0x20 / mov dl,8`
(`frow+0x20..0x27`) and `mov dl,8` at `frow+0` — exactly the port's
`MAP_ROW_HBTOP/HBBOT` and `HTTOP/HTBOT`. The field offsets `+0x1E`/`+0x18`/`+0x4`
independently re-confirm `ent_t`'s `w1E`/`w18` layout.

### R2.2 ❌ **defect #18 was WRONG and is reverted** — my error, caught here
B7 made `maps_clip`'s dead left-clip branch live by reading `*x` back as `S16`. That was
unsafe, and I did not check the shared consumers before changing it.

`maps_clip` is called by `ent_addrect` **and** by `sprites_paint2`/`maps_paintRect`.
`sprites_paint2` takes `U16 x` and guards its column loop with `x + c < x0`; a negative x
arrives there as `0xFFxx`, so that guard cannot fire and the left-hand columns would be
drawn at wrapped coordinates instead of skipped. `ent_draw` passes `ent_ents[i].x`
unguarded, so the path is live.

`maps_clip` is restored to its original form, with the branch documented as deliberately
dead and *why* it must stay so. **The underlying bug is real and is now fixed at the
caller that needed it**: `ent_addrect` clamps a negative x to 0 with reduced width before
clipping, so the erase rectangle covers the visible part instead of being dropped — which
was the actual smearing symptom. Partial left-clipping of *sprites* still requires the
sprite path to carry a signed x; that refactor is not done.

### R2.3 — `tiles.c` ✅ AGREE
Bank and flag-LUT selection match the ST instruction for instruction:

```
499CA  move.l #0x1d01e,(0x495d0)   ; default tile bank
499D4  move.l #0x49f1e,(0x495d4)   ; default per-tile flag LUT
499DE  tst.w (A0) / beq            ; the submap record's +0 field = page
499E2  move.l #0x1f01e,(0x495d0)   ; page != 0 -> the other bank
```

i.e. the port's `map_tilesBank = page == 1 ? 2 : 1` and
`map_eflg_expand(page == 1 ? 0x10 : 0x00)`. `tst.w (A0)` also re-confirms that `page` is
field `+0` of the ST submap record, as derived in C1. `TILES_NULL 0xFE` /
`TILES_CRLF 0xFF` list walking is a port construct with no counterpart.

### R2.4 — `sprites.c`: two latent bugs in code that never compiles
`config.h` is `#define GFXST` / `#undef GFXPC`, and the Makefile excludes the `dat_*PC.c`
tables, so the **GFXPC** variants cannot be built at all. Recorded, not changed, because a
fix here cannot be compiled or tested:

- `sprites_paint2` (GFXPC, line 96): `x_fb = y_map - MAPS_FB_Y;` assigns `x_fb` a second
  time; `y_fb` is never set and is then used in `fb_at(x_fb, y_fb)`.
- the same function references `xmap`/`ymap`, which are not declared (`x_map`/`y_map` are).

The compiled **GFXST** variant is sound: it clips through `maps_clip`, honours
`MAP_EFLG_FGND` for depth, and its `+8` vertical fudge matches the identical one in
`maps_paintRect` — an ST-artwork alignment constant, consistent between the two.

### R2.5 — `fb.c`, `img.c`, `rects.c`: port mechanisms, no counterpart
`fb_fadeIn`/`fadeOut` are 8-step **gamma ramps** via `sysvid_setGamma`. Neither original
fades that way — the ST rewrites the hardware palette, the PC the EGA registers — so the
step count and curve are the port's own. What is comparable is *where* fades occur, and
those are the state-machine transitions already checked in G1-G4 (the ST does
`palette_fade_out()` before the game-complete path, matching `FADEOUT__GAMEOVER`).
`rects_new`/`rects_free` are the dirty-rectangle allocator, and `img_paintPic`/`paintImg`
paint the port's own `img_t` structs. All are `how`, not `what`. Out of scope by the
user's rule, and recorded as such rather than left ambiguous.

## R3 — sound triggers and intro screens

### R3.1 ⭐ sound: **25 ST trigger points, 25 port trigger points** — and one missing sound

`sounds.c`'s four functions are loading and plumbing. What matters is *where* sound is
triggered, so I enumerated both sides.

The **PC is not the reference here**. Its audio is inline PC-speaker code — only two
regions exist (`0x0355`-`0x035D`, `0x2B4D`-`0x2B78`), reached from a handful of sites
(`0x2B68` is `in al,0x61 / and al,0xfc / out 0x61,al` with delay loops). The port's WAV set
(bullet, bomb, explode, pad, bonus, die, entity…) follows the **ST's sampled audio**, so
the ST's `play_music` (`0x44CCE`) is the thing to compare against. It has **25** call
sites; the port has **25** `syssnd_play`/`sounds_setMusic` sites.

Confirmed mappings, against the track map in `re/assets-manifest.md`:

| ST track | trigger | port |
|---|---|---|
| 8 | fire path after decrementing bullets | `e_bullet.c:47` `WAV_BULLET` |
| 9 | dynamite fuse | `e_bomb.c:135` `WAV_BOMBSHHT` |
| 10 | dynamite + destructible pickup | `e_bomb.c:174` and `e_box.c:192` `WAV_EXPLODE` |
| 12, 13 | `player_select_anim_frame` | `e_rick.c` walk ×3 / crawl |
| 14, 15 | `player_controller` jump/land | `e_rick.c:497`, `:562` `WAV_JUMP` |
| 16 | crate collected | `e_box.c:157` `WAV_BOX` |
| 17 | treasure pickup | `e_bonus.c:58`, `:77` `WAV_BONUS` |
| 19 | `kill_player` **and** `kill_enemy` | `e_rick.c:125` and `e_them.c:90` `WAV_DIE` |
| `0x13`-`0x1C` | entity trigger sounds | `e_them.c:886` `WAV_ENTITY[...]` |

Track 19 is worth noting: the manifest records that `play_music`'s type-2 branch ignores
`D1`, so Rick's death and an enemy's death play the *same* sample — which is exactly what
the port does.

**Defect #21 — the ST clicks when you fire an empty gun; the port was silent.**

```
4C524  tst.b (0x0004b32a).l     ; bBullets
4C52A  bne -> fire normally
4C530  move.w #0x9,D0 / moveq #1,D1 / jsr play_music / return
```

Track 9 is shared with the dynamite fuse, so the sound is `WAV_BOMBSHHT`. Added under
`PLATFORM_ST` only: the **PC is silent on this path too** (`0x1776`
`mov al,[0x7e45] / and al,al / jnz / ret`, no speaker call), so it is a platform
difference, not an omission on both sides.

Three port sites are not yet pinned to a track — `WAV_PAD`, `WAV_STICK`, `WAV_SBONUS2`.
All three are in `player_controller`/`effect_*` territory, which is where the manifest's
unattributed track 11 and the 14/15 pair live. Plausible, not proven; left `OPEN`.

### R3.2 ❌ correction to `re/assets-manifest.md`'s track map
Its note *"Remaining subtunes (1–8, 21–29) have no literal call site"* is **wrong for
subtunes 6, 7, 8**. Re-scanning the 25 sites across both encodings:

- **19** load the track with `move.w #N,D0` — tracks 8-19, the documented table;
- **4** with **`moveq #N,D0`** — track 7 @ `0x4BEC2`, track 5 @ `0x4DC62`/`0x4DC94`,
  track 6 @ `0x4DDC6`;
- **2** load `D0` indirectly — the entity trigger path.

The original scan matched only the `move.w` form. Same encoding-blindness as the `cmpi.w`
scan that missed the ST's `cmp.w` (R4.7). Corrected in place in the manifest.

### R3.3 — intro screens
`scr_imap.c` is table-driven from `screen_imapsteps`, which matches **no** dump under byte,
LE16 or BE16 encodings (R2/G6) — the port reformatted it, so the level-intro animation
cannot be verified by content and needs behavioural comparison (R1). Its *flow* is sound
and checkable: paint title/body, start the per-map tune, fade in, animate until FIRE, wait
for release. The per-map tune (`map_maps[].tune`) corresponds to the ST's type-0 song
tracks, consistent with the four literal music sites found in R3.2.

`scr_gameover`, `scr_imain`, `scr_pause`, `scr_xrick` are each a single screen-state
function whose only game-visible effects are the music they start and the state they
return; those transitions were already checked in G1-G4. `OPEN` for behavioural
comparison, nothing further verifiable statically.

## R4 — residual items

### R4a ✅ hall-of-fame boundary — **my concern was unfounded**
I flagged that the port qualifies on `env_score >= game_hscores[7].score` where the PC's
digit compare (`jc` = strictly less) looked like it needed *greater than*. Tracing the
whole loop settles it: at `0x206B`, after all six digits compare **equal**, the PC jumps to
`0x207A` — the **qualified** path. So the PC qualifies on `>=` too and the port matches
exactly. No change.

### R4b ⭐ ST bomb explosion phase — implemented
The phase after the fuse sentinel is now read in full. `0x4CAAC` `tst.w (0x0004bf1a).l /
bne` routes an already-detonated bomb to `0x4CB5A`, and there:

```
4CB60  addi.w #0xc,D0 -> (0x4bf2a)    ; blast centre x = x + 0x0C
4CB70  addi.w #0xa,D0 -> (0x4bf2c)    ; blast centre y = y + 0x0A
4CB82  lea (0x46c3e).l,A0             ; the BOX's ten-frame table, reused
4CB8E  cmp.w #7,D0 / blt              ; index >= 7 CLEARS the lethal flag
4CB9A  bclr #0,D0 / add.w D0,D0       ; two ticks per frame
```

- **The blast centre `+0x0C` / `+0x0A` is exactly what the port already had** ✓
- The ST explosion is **20 ticks, ten frames** from the *same table as the box*
  (`0x90 0x24 0x91 0x25 0x92 0x26 0x93 0x27 0x94 0x28`), not the port's five own frames
  `0xa8..0xac`;
- and it stops being **lethal after 7 ticks**, where the port stayed lethal throughout.

Implemented under `PLATFORM_ST` via a shared helper. Timing re-derived rather than
assumed: `E_BOMB_TICKER 0x37` with `elapsed = TICKER - 1 - ticker` yields exactly **34
fuse ticks (17 frames x2)** and **20 explosion ticks (10 frames x2)** — checked
programmatically; the first attempt (`0x36`) gave 33 fuse ticks and left one frame with a
single tick.

### R4c — three unpinned sounds, now pinned by their surrounding code
| ST track | pinned by | port |
|---|---|---|
| **11** | `0x4C4AE` sets `(0x4BF1C)` = 0xFF, guarded at `0x4C44A`/`0x4C4A2` by `tst.w` / `bne` — a **one-shot latch**, exactly the port's `stopped` static | `WAV_STICK` |
| **14** | `0x4C3D4` `move.w #-0x580,(0x0004a756).l` immediately before — the jump velocity verified in R4.18 | `WAV_JUMP` |
| **15** | `0x4C212` sits between `move.w #0x00FE,D4` (`0x4C1DE`) and `move.w #0xF800` (`0x4C22C`) — the super-pad launch | `WAV_PAD` |

This refines the manifest's "14, 15 — jump / land cues": **14 is the jump, 15 is the super
pad**. `WAV_SBONUS2` remains unpinned. Noted while here: the ST has **two** stop paths, one
of which sets the latch *without* sound (`0x4C456`), where the port has a single latched
site.

### R4d — `ent_sprseq` / `ent_mvstep` over-runs: unchanged, by decision
Both over-run their true ends into adjacent data (R4.23/R4.24) and both are provably inert
(max `sni` 244 < 261 valid records; sequences terminate on `0xff`). Shortening a declared
array without tracing every index is how an inert oddity becomes a crash. Left as is.

## Items 2, 3, 4 from the audit

### I2 ✅ the ST death-tumble end — **VERIFIED**, marker removed
The `/* UNVERIFIED for ST */` at `e_rick.c` is gone. The ST genuinely does **not** end the
tumble inside the player update: `0x4C846`-`0x4C8A8` integrates y and applies gravity with
no bound test, and `0x4CA54` — the exit I had never read — is only
`movem.l (SP)+ / rts`. The corpse leaves through `render_sprites`:

```
4B0B4  moveq #0,D2 / move.w (0x6,A0),D2
4B0BA  cmp.w #0,D2   / bge -> else bsr 0x4AC3E   (despawn)
4B0C8  cmp.w #0x142,D2 / ble -> else bsr 0x4AC3E (despawn)
```

That is exactly `y < 0 || y > 0x142`, which is what the port's ST branch already expressed
with `ENT_YMAX = 0x142`. **Same condition, different home** — the port was right.

### I3 ⭐ the remaining `ENT_YMAX` sites — **defects #22 and #23**
The reason six sites were unverified is that I had only found two PC encodings. There are
**three**, and the PC's entity bound checks number **exactly six**, all now located:

| PC | encoding | port site |
|---|---|---|
| `0x10E3` | `cmp ax,0x140` | scroll translate (defect #20) |
| `0x2976` | `cmp bh,0/1` + `cmp bl,0x40` | t2 ymove (R4.7) |
| `0x2A06` | `cmp dh,0` + `cmp dl,0x40` | t2 fall (R4.7) |
| `0x23AD` | **`cmp dx,0x140`** | t1 fall — **defect #22** |
| `0x2742` | `cmp ax,0x140` | restore from xsave/ysave — **defect #22** |
| `0x278B` | `and ah,ah` / `cmp ah,1` / `cmp al,0x40` | scripted move — **defect #23** |

- **#22** (two sites): both despawn at `y >= 0x140`; the port had `> ENT_YMAX`, one row too
  high. `0x2742` also re-confirms `xsave`/`ysave` at `+0x1C`/`+0x1E` for a third time.
- **#23**: the scripted-move path stores iff y is in range — the exact complement of the
  despawn predicate — and it **accepts `y == 0`**, which the port's `y > 0` rejected. Now
  `!ENT_YDEAD(y)`.
- The seventh port site, the **dying-enemy** test, has **no PC counterpart at all**; a
  dying enemy leaves via the general mechanisms. It also tests the *pre-integration* y, so
  it fires a frame late. Left in place (deleting a despawn on no evidence is riskier) but
  aligned to `ENT_YDEAD` and documented as a port addition.

### I4 — `e_them.c`: all 11 functions now have instruction-level anchors
The contact sequences were the missing piece. Mapping the PC's callers of
`e_rick_boxtest` (`0x12AE`), `u_fboxtest` (`0x1317`) and `e_bomb_hit` (`0x134B`) gives
**distinct clusters per entity type**, and each matches the port's order:

| PC cluster | order | port |
|---|---|---|
| `0x2342`-`0x2382` | fbox, bomb, fbox, **rickbox last** | `e_them_t1_action` |
| `0x2864`-`0x28D1` | **rickbox first**, fbox, bomb, fbox | `e_them_t2_action` |
| `0x268F`-`0x269F` | `test [si],0x80` then rickbox alone | `e_them_t3_action` |

`t3_action` matches instruction for instruction, `ENT_LETHAL = 0x80` included; the port's
extra `!STZOMBIE` is redundant, since the PC's `e_rick_boxtest` guards internally at
`0x12AE`. `t3_action2` opens on `[SI+0x26]` in the PC and `sproffs` (= `c1`, offset
`0x26`) in the port. The bullet test at `0x2323` matches including the `+0x18` applied on
one direction only. `t1a`/`t1b` are trivial wrappers.

**Honest limit:** this is structural and constant-level verification with instruction
anchors at every decision point — not a literal transcription of all ~600 PC instructions
in these routines. `u_themtest` has no separate PC call (the equivalent test is inline,
ending in the `JMP 0x24C4` at `0x2320`).

### Process failure worth recording
While editing `e_them.c` I wrote a comment containing a non-latin-1 character. Python's
`open(f,'w',encoding='latin-1')` **truncates before encoding**, so the write raised after
emptying the file — `e_them.c` went to 0 bytes and the link failed. Recovered from
`HEAD` (which held the session's earlier work) and the four post-commit edits re-applied.
**Fix adopted: build the whole string, `.encode('latin-1')` it, and only then open `'wb'`
and write** — an encoding error now raises with the file untouched.

**Warning census note.** `make warn` went 180 -> 182, both new ones `-Wtype-limits` at the
two `ENT_YDEAD` sites where the local `y` is `U16` (`e_them.c:118` and `:777`), so the
`(y) < 0` half is dead there. **The behaviour is still correct**: an unsigned `y >= 0x140`
catches a wrapped-negative y, which is precisely how the PC does it — `0x23AD cmp dx,0x140
/ jc` and `0x278B`'s byte-pair test are both unsigned. The clause is redundant at those two
sites, not wrong. The third `-Wtype-limits` is the long-standing, deliberately dead
`maps_clip` branch.
