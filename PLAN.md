# Rick Dangerous (Atari ST) — State & Plan

**Snapshot: 2026-08-29.** Where the project stands, what is still open, and what happens
next. Project rules, settled decisions and method lessons are in `MEMORY.md`; the game
knowledge itself is in `re/` and in Ghidra plate comments.

**Bar:** `re/` complete enough to *mechanically re-code the game with identical
behaviour*. Everything below is measured against that.

---

## 1. State

| Metric | Value |
|---|---|
| Functions | **133**, all named; every non-trivial one transcribed |
| Structs applied | **10**, plus typed arrays over every hard-bounded data region |
| Entity dispatch types | **74 / 74** characterised |
| Placement table | 523 slots = 476 real records + 47 per-room terminators (reconciled) |
| Knowledge base | **16 documents + 4 scripts** in `re/`, plus **12 documents** in `xrick/re/` about the prior C/SDL port |
| Extracted assets | 12 graphic PNG sheets (**212** sprite frames among them, cell index = sprite number), 47 room maps + 47 entity overlays, 1 playable SNDH |
| Byte-identity audits | **22 of 22 complete** — 49 defects found and fixed (10 = port cross-check; 10b–10m = assumption sweeps) |
| Dynamic-verification probes | **7 of 8 resolved**; the 8th reduced to a nice-to-have |
| Hatari harness | **Working** — boots the analysed build unattended, Rick driveable under script |

**Coverage against the bar: ~98%.** This is an explicit judgement, not a measurement —
no tool here can produce a coverage number (see `MEMORY.md` §7). Converting it into a
measurement is exactly what O1 below is for.

---

## 2. Complete

**The code is fully reversed.** Every function is named and every non-trivial one is
transcribed to exact pseudocode in `re/algo-*.md` — constants as literals, branch order
preserved, register conventions documented. Re-codable from `re/` alone:

- Frame loop, timing, double buffering, VBlank/Timer-A interrupts, supervisor entry
- Player controller — movement, jump/gravity, climb, crouch, attacks, death
- The sprite blitter (aligned + shifted paths, derived transparency, clipping)
- Enemy AI (3 modes), the shared scripted-trap engine, pickups, triggers, collision
- Level data model: rooms, transitions, placements, object templates, tilemap encoding
- PSG sound engine including the sequence opcode set and sample playback
- HUD, score, lives, per-room checkpointing, game-over/respawn, attract mode
- All in-game text and the font/character encoding

**All assets are extracted and validated by observation, not inference.** Graphics
render as recognisable artwork; all 47 room maps render as coherent level geometry
(visually confirmed); the 64 strings decode; the SNDH plays — music, effects and all
three digidrums, confirmed by ear.

**Fidelity is audited, not assumed.** `re/byte-identity.md` is the standing record: nine
mechanical audits derived facts from the binary and diffed them against the documents.
Fifteen defects were found and fixed, notably both tile probes transcribed literally
(the previous "equivalent" formulation would have broken ladder detection on 8-pixel
column boundaries), six global width errors, the music engine's note index and transpose
proven **signed**, and four off-by-one loop counts. Two audits came back clean: the
entity struct's field widths, and the decompiler-hidden-dispatch class.

**Seven of the eight dynamic-verification probes are resolved.** These behavioural
details were inferred statically and flagged as wanting a live run; `re/hatari.md` §6
holds the evidence for each — tile-attribute bits and the `0x6F` row-filter mask, the
`POOKY9999` easter egg, the four name-entry glyphs, `player_touched_hazard`'s single
reader, the per-level enemy banks, the landing rebound as a bounce-surface special case,
and the song-0 transpose. The eighth (trigger-bit semantics) is O2 below.

---

## 3. Tasks

**One numbering scheme.** Everything actionable is a `T`-item, listed here and nowhere
else. `xrick/re/xref.md` and the `re/` documents are **state**: they say what is true,
not what to do. The history of what each pass found is in `re/byte-identity.md`.

None of these blocks a reimplementation. `re/` is not known to be missing anything
structural.

### T1 — Build the reimplementation and diff it against the live game ⭐ **the main event**

Static auditing has reached diminishing returns: twenty audits, and the last several
found nothing in the areas they covered. What remains is a *test*, not a read.

The Hatari harness (`re/hatari.md`) is the instrument. Boot `disks/chaos43/RICK.PRG`
from a GEMDOS drive, re-measure the address delta (expect `-0x2054`, never hardcode),
breakpoint each major function, log register state, and diff against what `algo-*.md`
predicts. That turns the ~98% judgement into a measurement.

**T1 subsumes several smaller items** — it exercises the blitter (T4), the trigger bits
(T6) and the name-entry loop (T7) as a side effect of running the game.

### T2 — ~~Bullet probe points: one or two?~~ ✅ **RESOLVED 2026-08-31**

**We have exactly one, and both consumers read it unmodified.** The full xref set for
`0x4BF24`/`0x4BF26` is six + four references:

| Function | Site | Use |
|---|---|---|
| `player_controller` | `0x4C5AA`, `0x4C5C8`, `0x4C5E8` | seeds the point at the muzzle (leading edge) |
| `player_bullet_update` | read `0x4CA5E`, write `0x4CA9C` | the ±8 step, in lockstep with `nPosX` |
| `bullet_hits_entity` | `0x4CC1A` / `0x4CC20` | `move.w` straight into D1/D2, then `bsr entity_contains_point` — **no adjustment** |
| `scripted_trap_update` | `0x4D1EC` / `0x4D1F2` | `move.w` straight into D0/D1, then `bsr trigger_box_contains_point` — **no adjustment** |

So the ST tests **trigger boxes at the bullet's leading edge**, not at a centre point.
The port's second point (`e_bullet_xc = x + 0x0C`, used for triggers, boxes and bonuses)
has no counterpart here. For *enemy* hits the two sides agree — both use the leading
edge. The difference is confined to trigger tests, and is now recorded as state in
`xrick/re/xref.md`. Whether the PC build really had two points is part of T8.

### T3 — ~~Verify the third `0x19` site independently~~ ✅ **RESOLVED 2026-08-31**

**It is genuine, and at two instruction sites, not one.** `0x4BE1A` has three
references, all word-wide:

- `subi.w #0x1,(0x4BE1A)` @ `0x4BE32` — the per-frame decrement (`bcd_countdown_timer`)
- `move.w #0x19,(0x4BE1A)` @ `0x4BE3C` — reload after each tick (`bcd_countdown_timer`)
- `move.w #0x19,(0x4BE1A)` @ `0x4BE84` — initial set (`effect_start_escape_timer`)

So the three `0x19` uses on our side are **independent**: a *byte* store in
`enemy_ai_update` (`0x4D574`), a *word multiply* in `init_entity_from_placement`
(`0x497FE`), and *word* stores in two timer functions. Different widths, different
functions, different purposes. **The "we propagated one reading into three documents"
worry is disposed of** — `0x19` genuinely recurs in the ST build, where the port has
three unrelated values (20, 32, 30).

*Method note: the first search (`0x4be1a`) returned zero because Ghidra renders these
operands **padded** (`(0x0004be1a).l`) — the mirror of the O6 trap, where they were
unpadded. Searching the bare substring `4be1a` matches both forms, and the query was
validated against `4be18` (7 hits) before the negative was trusted.*

### T4 — Instruction-level check of the sprite blitter transcription

`algo-render.md`'s `render_sprites` shift path is the one large transcription never
compared against the disassembly line by line — 290 instructions of rotate-and-mask
across two unrolled paths. The likeliest remaining home for a real defect.

Audits 10h and 10i sampled the other hard transcriptions (`algo-system.md`'s eight small
functions, `algo-music.md`'s sequence opcodes) and found none, so expectations should be
modest — but this is the largest untested surface. Partly subsumed by T1.

### T5 — ~~Reconcile the entity-dispatch shapes~~ ✅ **RESOLVED 2026-08-31**

**They were never different.** The port writes type numbers in hex, we write them in
decimal — `0x10` = 16, `0x12` = 18, `0x16` = 22, `0x18` = 24 — so the port's "24
`ent_actf` entries plus a `>= 0x18` catch-all" *is* our types 0–23 dispatched
individually with 24–73 sharing `scripted_trap_update`. Same partition, different base.
Full mapping now in `xrick/re/xref.md` → *Entity type dispatch*.

**One genuine structural divergence, and it is an implementation choice rather than a
disagreement about the game:** how a dying enemy is marked.

- The port **rewrites the type** — `e_them_gozombie` sets `n = 0x47`, so the dispatcher
  routes the corpse to `e_them_z_action`.
- We set a **flag** — `kill_enemy` (`0x4D87C`) does `move.b #-0x1,(0x49,A0)`
  (`bDying = 0xFF`) and **never writes `wType`**; `enemy_ai_update` branches on it at
  entry (`tst.b (0x49,A0)` @ `0x4D4F4`).

Confirmed by a program-wide search: the immediate `0x47` occurs **nowhere** (validated
against a control that returns its expected hits). So ST type 71 (= `0x47`) is an
ordinary `scripted_trap_update` entry with no special meaning — which is consistent with
the placement census, where 71 appears as a normal trap type.

The other asymmetry is our **type 74** (`decorative_sprite_update`, intro screens), which
the port has no equivalent for because it builds its map intro from `screen_imapsteps`.

### T6 — Observe the trigger bits firing

All eight `bTriggerFlags` bits are exercised in shipped data across all four levels (the
census is in `re/entities.md`), so no transcribed path is unreachable. But the
*semantics* rest on the code transcription alone; no bit has been watched firing in a
running game. Breakpoint `scripted_trap_update`'s trigger scan on a known trap.
Opportunistic during T1.

### T7 — Characterise the `dbf D3w` name-entry loop

At `0x491E2` the commit loop's counter is the *character just copied*, so the iteration
count depends on entry state as well as on what was typed, and the copy over-runs the
10-byte name field. A reimplementation is correct by emitting `dbf D3w` — the object
code is the specification — but **what the player actually sees has never been
characterised.** Model it in Python, then confirm one case live. See `re/algo-system.md`.

### T8 — Adjudicate the port differences (needs the PC side)

Seventeen measured differences against the xrick port remain unadjudicated. They are
tabulated as state in `xrick/re/xref.md` → *Unadjudicated*.

**Our value is certain in every case** — each is read directly from instruction
encodings. What is unknown is whether the port's differing value is a genuine PC-vs-ST
difference or a port error, and **that is a question about the PC build.** An Atari run
cannot answer it: it would only re-confirm the side that is not in dispute.

**Method:** a DOSBox run of PC Rick Dangerous, or a disassembly of the PC executable.
Neither is currently in scope. Until then this stays open by design, not by neglect.

### T9 — Explain the `sni` → `sprbase` substitution

When all four trigger flags are set *and* the slot is ≥ 9, `ent_actvis` replaces
`sprbase` with `entdata.sni & 0xFF`. The port does the same and states plainly that it
cannot explain why. **Neither side knows.** No obvious instrument; would likely fall out
of watching a submap-3 trap under T1.

### T10 — Report the port's `map_connect` overrun upstream *(courtesy, optional)*

The port's connector table holds 154 records in an array it declares as 153
(`MAP_NBR_CONNECT = 0x99`), the surplus being a third connector in list 17 where we and
the port's own constant have two. Worth reporting to the upstream repository. No effect
on our work.

---

## 4. Accepted — deliberately not tasks

Known, understood, and not being pursued:

- **161 scenery tiles at `0x1BBFE`–`0x1D01D`** (standard 8×8 four-plane format, rendered
  to `scenery_tiles.png`) are referenced by **nothing** in the program — cut content or
  loader-stage artwork. Identified; use unresolved. No further asset sweep is worthwhile.
- **The `LevelStartInfo` array type cannot be applied in Ghidra**: an auto-generated
  pointer label inside the range blocks it and Ghidra rightly refuses to evict a named
  global. The struct exists and the full explanation is on the plate comment at
  `0x4B522`. Cosmetic only.
- **Orphaned-instruction regions** (`0x492E6`, `0x48F48`, `0x4DF86`+) are data
  mis-disassembled as code. Harmless; left alone.

---

## Appendix — work log

| Pass | Date | Outcome |
|---|---|---|
| Baseline | pre-08-27 | 82 functions, 27 named; no structs; skeleton only |
| Housekeeping + structs | 08-27 | 5 structs applied; sprite list confirmed 13 slots; HUD corrected to 3 counters + score |
| Multi-agent pass (5 forks) | 08-27 | → 129 functions; dispatch enumerated; per-room checkpointing; sound engine mapped; GEMDOS search negative |
| Entity-handler pass | 08-27 | All dispatch types characterised; **axis correction** (4=X, 6=Y); `player_dying`; bullets/dynamite resolved |
| Placement-format pass | 08-27 | Placement/room/transition/level-start formats decoded; `0x481E4` identified; effect callbacks found |
| Type-table pass | 08-28 | `ObjectTypeDef[75]`; `wTypeFlags` → `wTriggerSound` |
| Reachability analysis | 08-28 | The missing 12,880 bytes proven to be stack + PCM, not code |
| **Transcription pass (6 forks)** | 08-28 | ~4,400 lines of exact pseudocode; **tilemap encoding** and **music opcodes** decoded; `Super()`, joystick input, row-major tilemap, AI modes, carry-flag returns all corrected |
| String extraction | 08-28 | `re/strings.md`: 64 strings, font-validated encoding; ending text found |
| Slot-0 investigation | 08-28 | **No block-pushing mechanic exists** — slot 0 is the scripted crusher/boulder hazard |
| SNDH packaging | 08-28 | Sound engine lifted into a 29-subtune SNDH with a hand-assembled relocating stub |
| Room rendering + data typing | 08-28 | All 47 rooms rendered (validates the tilemap decode end-to-end); hard-bounded data regions typed and labelled |
| Asset extraction | 08-28 | PNGs rendered and visually validated; sprite format found to be plane-major; font extent settled at 95 glyphs |
| Index demotion | 08-28 | `functions.md`/`entities.md` demoted to indexes; authority order documented in `re/README.md` |
| Audio complete | 08-28 | SNDH rebuilt from the 1 MB capture: all three PCM samples intact incl. the death sample; **confirmed by listening**; superimposed-'ding' defect fixed |
| Room render fix | 08-28 | Rooms were cut short at the bottom; added the 6-block-row margin the player actually sees |
| Asset + loose-end closure | 08-28 | Sprite extraction switched to a grid sweep (124 → **185** frames — *later corrected to 212, see audit 10*); the 5 KB post-font gap identified as 161 unreferenced scenery tiles; `level_start_info` proven to have **5** entries (entry 4 = the game-complete pseudo-level) |
| KB review + consistency pass | 08-28 | Stale content purged; `sprite_type_dispatch` corrected to **74** entries; `hide_entity` relocated; `CheckpointState` axes fixed |
| Hatari harness | 08-28/29 | Commissioned, then switched to the analysed build (`chaos43/RICK.PRG`); `-0x2054` delta reproduced; gameplay driven under script by poking `joystick1_state` |
| Dynamic-probe pass | 08-29 | 7 of 8 items resolved — several by Ghidra xref census rather than by watching |
| **Byte-identity audits 1–9** | 08-29 | 15 defects found and fixed; both tile probes transcribed literally; signedness of the music engine established; struct widths and hidden dispatches proven clean |
| **"The port" registered and analysed** | 08-29 | xrick (bigorno, C/SDL) cloned into `xrick/`; knowledge base written to `xrick/re/` (12 docs); PC-derived-logic caveat established; ~20 facts cross-validated on first reading; 17 numeric + 7 semantic questions queued in `xrick/re/xref.md`; one internal inconsistency found on **our** side (placement flag `0x02`) |
| **Port comparison, numeric pass (Q1–Q17)** | 08-29 | Every question answered on our side; 7 closed as agreement, 9 open as real differences, 1 closed as **our defect**: the sprite sheet was short by 21 frames and a density filter had been dropping sparse ones. `extract_assets.py` fixed, `sprites.png` re-rendered at **212** frames with cell index = sprite number. Gravity and corpse-drift questions narrowed to the dying path / enemy corpse only. New Q18 raised (bullet probe point: one on our side, two on the port's) |
| **Audit 10 — consistency sweep vs the port** | 08-29 | First *external* cross-check. ~20 facts corroborated; **16 defects** found that nine self-referential audits had missed: sprite sheet 21 frames short + a density filter dropping real frames; `bTriggerFlags` bit `0x02` and bits `0x04`/`0x08` misdescribed; the dispatch-table row mislabelled type 70 (is 74) and `hide_entity` at the wrong address; `data-structures.md` still claiming 70 entries / unhandled types; a Ghidra plate still saying "column-major"; four naming splits between Ghidra and the docs; and **26 unapplied corrections** across four `algo-*.md` files, all now closed |
| **Assumption sweep of the ST reverse-engineering** | 08-30 | Every claim re-derived rather than re-read. Fixed: the `nVelY` gravity note (had `+0xC4` on *living* enemies with a terminal clamp — actually living player/enemy `+0x80` clamp `0x800`, dead player `+0x80` no clamp, dying enemy `+0xC4` no clamp, all four verified at instruction level); the title bitmap (**32,768** bytes, not 32,000, and its stated range matched neither); the sprite region (**71,232** bytes, not "~32 KB"); `level_start_info` 4→**5** entries; the high-score name offset (+8 → **+0x12**); two "untraced" effect-callback claims long since traced; a rename-mangled sentence of my own making. Promoted 3 fields from *likely*/*unconfirmed* to **confirmed** by instruction census. **The 171 KB data region is now gapless and fully mapped**, every size measured, ending exactly at the first code byte. **O3 item 2 resolved**: the only unplaced types are the 4 code-spawned ones |
| **Second assumption sweep (audit 10c)** | 08-30 | Re-derived the areas 10b had not covered. **One defect**: the 2 bytes at `0x4AADE` before `sprite_type_dispatch` are not padding but the `0xFFFF` **`sprite_list` terminator** — all three walkers (`render_sprites`, `clear_sprite_flags`, `blit_backgrounds`) stop on it and **none is bounded by a count of 13**; it has no xrefs, so it must be seeded in the initial state. Documented, and closes `xrick/re/xref.md` S3. Verified-exact with no change: all 47 `RoomHeader` pointer sets, the 29 music descriptors (incl. the three PCM pointers), `note_period_table`, the font and `level_start_info` boundaries, the 16-word palette, all five intro-text lengths, `strings.md`'s 66→64 extraction, and **all 16 tile-attribute bit counts** |
| **Third assumption sweep (audit 10d)** | 08-30 | **Clean — zero defects in `re/`.** Measured four things never measured before: the dynamite fuse table (**17** entries) and explosion table (**10**), all 27 frame pointers on the sprite grid at indices 33–147, and a full `TransitionWaypoint` census (**106** across 47 lists). The transition region now **closes exactly** — 106×10 + 47×2 = 1154 = `0x478B2`–`0x47D33`, ending at `object_type_defs` — which also proves the sentinel is 2 bytes, not a 10-byte record. Re-walked the per-room placement lists: 476 + 47 = 523 confirmed room by room. Closed xref Q11 with real numbers and found **a defect in the port** (Q20): its `map_connect` has 154 records in a 153-declared array, differing from us in 1 of 47 lists |
| **Fourth assumption sweep (audit 10e)** | 08-30 | Censused `ObjectTypeDef[75]` field by field — the largest table never checked. **2 defects**: the scripted-trap `anim_frame_table` range was wrong at *both* ends (really `0x46C3A`–`0x4708A`, overlapping the band the doc reserved for paths), and the `wTriggerSound` census listed only 6 of the **10** consecutive values `0x13`–`0x1C`. **New finding**: types **67/68 share the dynamite explosion table** via a null intro frame at `0x46C3A` — invisible until triggered, then they play the explosion; that is *why* the anim range starts low. **New open item O6**: 26 structured-but-unreferenced bytes between the two HUD structs. Fed xref Q21 — the port's guess of 10 entity sounds was right, but its `- 0x14` index base is one too high |
| **Fifth assumption sweep (audit 10f)** | 08-30 | Audited the **music engine tables**, the last untouched surface. Started from a cheap mechanical signal — *two documents describing the same address differently* — and found **4 defects, all in `data-structures.md`**: `MusicTrackDescriptor` types **0 and 2 swapped** (0 = song, 1 = SFX, 2 = digi sample, per `play_music`'s dispatch), the `nParam_index` semantics, `0x46932` mislabelled a "per-channel instrument table" (it is the **song table**, 9×6), and `0x46B66` mislabelled "arpeggio/vibrato" (it is the **pitch-envelope segment table**). Sharpened `0x463CC` to a 10-byte-stride instrument table. **Two new hard boundaries**: 9 songs ↔ the 9×6 song table, and the SFX table's 20 entries × 13 bytes ending exactly at the pattern-data base `0x4652A`. `algo-music.md` was right throughout |
| **Sixth assumption sweep (audit 10g)** | 08-30 | **Clean — zero defects.** Two mechanical scans came back empty: every `name`/`0xADDR` pair in `re/*.md` checked against Ghidra's symbol table (5 hits, all range-notation false positives — the scan that *would* have caught the `hide_entity` error), and access widths for the globals (6 spot-checked across every access in the program, all matching). **Resolved** `CheckpointState`'s four `DAT_…` placeholders — no `DAT_` names remain in `re/` — plus its hard boundary at `0x4BFC2` and the restore ordering (`reset_player_state` → restore → `spawn_player_entity`). **Made precise**: the `−0x2054` delta is a *relocation* — static data byte-identical, stored pointers shifted (74/74 dispatch, 141/141 RoomHeader), non-pointer fields identical (47/47). Relocate pointers, not data |
| **Seventh sweep (audit 10h) — transcriptions, not tables** | 08-30 | First sweep to compare `algo-*.md` **transcriptions** against the disassembly instruction by instruction. Eight `algo-system.md` functions checked in full: `seed_prng_state` (constants recomputed), `update_prng`, `draw_string_xy`, `draw_string`, `draw_glyph_string`, `draw_glyph`, `set_palette`, `palette_fade_in`. **Zero defects** — the `bclr`/`bchg` old-bit semantics and `palette_fade_in`'s double-duty `D4` (blue threshold *and* outer `dbf` counter) were all already captured. One fidelity nuance recorded: `draw_glyph` is **unrolled** (7 advances for 8 rows, 32nd byte without post-increment) where the transcription is rolled — unobservable, since A4 is restored and both callers reload A1 |
| **Eighth sweep (audit 10i)** | 08-30 | `algo-music.md`'s sequence opcodes, the second "hardest remaining" transcription. `process_sequence_command` verified instruction by instruction, PC-relative targets resolved. **Zero defects**, two fidelity notes: (1) both range tests are **signed**, so the unsigned C form is valid **only because every call site guards on bit 7** (`tst.b (A0); bpl` at `0x452C0`/`0x452CE`) — checked rather than assumed, and now stated at the function; (2) the `0xC2` case is `beq.w 0x451D8`, a branch into `init_music_playback`'s `rts`, not a local return. **`algo-render.md`'s blitter shift path is now the one large untested transcription** |
| **S5/S6/S7 resolved (audit 10j)** | 08-30 | The three port-side hypotheses, settled against our disassembly. **S5 false** — the ST's two ladder-grab sites are *byte-identical*; the port's asymmetry is port-side, and the ST rule (`(x&8)==0 \|\| (x&7)==0`, then snap `x=(x&0xF0)\|4`) differs from both port forms → new **Q22**. **S6 false** — ours is a real two-longword PRNG (`update_prng`, 2 callers, 1 consumer, turn on 1-in-4); the port's mixer picks direction 1-in-2. Unrelated, though both step a generator per frame. **S7 true and exact** — tabulating bit reachability across {upper,foot}×{outer,centre}, **all 32 cells agree**: ladder-top only from the centre foot column, one-way only from the foot row, ladder only from the centre column. Strongest corroboration in the comparison |
| **O6 resolved** | 08-30 | The "26 unexplained bytes" at `0x4B336`–`0x4B34F` turned out to be **four 8-byte HUD render buffers** (score/bullets/dynamite/lives — 6 glyph cells + `0xFF` `draw_string` terminator + pad), addressed by four `lea`s at `0x4B3C8`/`0x4B46C`/`0x4B4A0`/`0x4B4D4` and filled by `draw_hud_count`. Solved statically; **no Hatari run needed**. The earlier "nothing references it" claim was an artifact of an operand search using zero-padded addresses (`0x0004b34`) where Ghidra renders them unpadded (`0x4b340`) — a search that could not have matched. Lesson added to `MEMORY.md` §8 |
| **T2 and T3 resolved** | 08-31 | **T2**: the bullet has **one** probe point on the ST — seeded at the muzzle as the leading edge, stepped ±8, and read **unmodified** by both `bullet_hits_entity` (`0x4CC1A`/`0x4CC20`) and `scripted_trap_update` (`0x4D1EC`/`0x4D1F2`). So triggers are tested at the leading edge; the port's separate centre point has no ST counterpart. **T3**: the escape-timer divider is genuinely `0x19` at **two** sites (`0x4BE3C`, `0x4BE84`), word-wide — so the three `25`s are independent instruction sites of differing widths, not one reading propagated. Both searches were validated before their negatives were trusted |
| **T5 resolved** | 08-31 | The entity-dispatch "shape mismatch" was a **base mismatch** — the port writes types in hex, we write decimal; `0x18` = 24, so its `ent_actf[0..0x17]` + `>= 0x18` catch-all is exactly our 0–23 individual + 24–73 shared. One real divergence: the port marks a dying enemy by **rewriting the type** to `0x47`, we by setting the **`bDying` flag** (`0x4D87C`, `wType` untouched) — and the immediate `0x47` occurs nowhere in our program, so ST type 71 is an ordinary trap. Plus our type 74, which the port has no equivalent for. Mapping table added to `xref.md` |
