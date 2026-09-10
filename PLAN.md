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

### T20 — Upgrade the port from SDL2 to SDL3 ✅ **DONE 2026-09-10 (WSL); Windows/vcpkg side edited but unverified**

Full detail: `build.md` (build/run instructions and the one bug found) and
`MEMORY.md` §9 (summary). Verified SDL3 exists and that 3.4.16 is the current latest
release (GitHub releases page and vcpkg's `sdl3` port agree independently); the
WSL/Makefile build uses Debian's packaged 3.2.10 instead, a real constraint (source
build of 3.4.16 hit a `libxtst-dev` dependency needing interactive sudo), not an
unrecorded shortcut.

Touched 7 SDL-using files under `xrick/xrick/src/` (`sysvid.c`, `sysevt.c`,
`sysjoy.c`, `syskbd.c`, `syssnd.c`, `system.c`, `sysarg.c`) plus the `Makefile`
(pkg-config instead of `sdl2-config`). Both `PLATFORM=ST` and `PLATFORM=PC` build
clean, same 266 warnings as the pre-T20 SDL2 baseline (none new). The audio rewrite
(T19) needed its own SDL3 migration too — SDL3's audio device is a pull-callback
model (`SDL_OpenAudioDeviceStream` + `SDL_PutAudioStreamData`), not SDL2's
fill-a-buffer one — but is otherwise unrelated to T19's engine-correctness work.

**One real bug, caught only by running it, not by review:** after a clean build the
window was entirely black despite correct audio — SDL3 apparently defaults new
textures to alpha-blended rendering where SDL2 didn't, and the game's raster texture
never populates its alpha byte (always 0), so the whole frame blended down to black.
Fixed with one `SDL_SetTextureBlendMode(texture, SDL_BLENDMODE_NONE)` call; confirmed
fixed by the user looking at the re-launched window.

`xrick.vcxproj`/`vcpkg.json` (the Windows/MSBuild path) were edited for consistency
— the source now needs `<SDL3/SDL.h>`, so leaving them on SDL2 would just not
compile — but **not built or run**, per this project's standing rule to always
build/verify in WSL (`MEMORY.md`, `build-in-wsl` memory). Confirmed the pinned
`builtin-baseline` commit already resolves `sdl3` to 3.4.16 (checked the registry's
raw `versions/s-/sdl3.json` at that exact commit), so no baseline bump was needed.
**Update, T21: the Windows side was actually built** (user granted one-time
permission to build on Windows for that task) — see T21.

### T21 — Windows project: x64-only, `bin\<Config>\` output, Release by default ✅ **DONE 2026-09-10, built and verified on Windows**

User request: drop the Win32/x86 configs (x64 only needed), build into
`bin\Debug`/`bin\Release` instead of `<Platform>\<Config>\`, and default to Release.
Full detail in `build.md` §2.

`xrick.vcxproj`: removed the `Debug|Win32`/`Release|Win32` `ProjectConfiguration`/
`PropertyGroup`/`ItemDefinitionGroup`/`PropertySheets` blocks; `VcpkgTriplet` no
longer needs a per-platform condition (x64-windows unconditionally); added
`<Configuration Condition="'$(Configuration)'==''">Release</Configuration>` /
`<Platform Condition="'$(Platform)'==''">x64</Platform>` before
`Microsoft.Cpp.Default.props` (must be set there, since that's what actually
consumes `$(Platform)`); set `OutDir`/`IntDir` to `$(ProjectDir)bin\$(Configuration)\`
/ `$(ProjectDir)obj\$(Platform)\$(Configuration)\`. `xrick.sln`: dropped the
`Debug|x86`/`Release|x86` solution-configuration/project-configuration-mapping
entries, reordered `Release|x64` first.

**Two real problems found only by actually building, not by reading the edited
XML:** (1) The vcxproj had never been fed through MSBuild since the T19/T20 edits —
several `<!-- ... -->` comments (added in those sessions, including this session's
own T20 edits) contained a bare `--` inside the comment body, which is invalid XML;
`MSBuild.exe` refused to parse the whole project file (`MSB4025`). Sweep-checked and
fixed every comment in `xrick.vcxproj`/`xrick.vcxproj.filters` (script: strip every
`-->`/`<!--` delimiter first, then grep the remainder for `--`, since the closing
delimiter itself legitimately contains `--`). (2) **A bare `MSBuild xrick.sln` (no
`/p:Configuration`) ignores the new Release/x64 defaults and builds Debug anyway** —
MSBuild's solution-to-project wrapper hardcodes `Configuration=Debug` before the
per-project `PropertyGroup` conditions ever get a chance to apply, and this is not
fixable from any project or solution file edit. Confirmed by building both ways;
**`build.md` now documents `MSBuild xrick.vcxproj` directly** (not `xrick.sln`) as
the command that actually honors the defaults.

vcpkg: ran `vcpkg install --triplet x64-windows` (this session, with the user's
explicit one-time permission to build on Windows — the standing rule is otherwise
WSL-only, see `MEMORY.md`'s `build-in-wsl` memory) — installed `sdl3:x64-windows@
3.4.16`, confirming T20's baseline-resolution claim against a real install, not just
the registry file. Built and ran successfully: video, audio, and the `-h` output all
confirmed working on native Windows.

**Found by playing the native build (not by review), still open:** scrolling
glitches and sprite misalignment that don't reproduce on WSL. A texture-pitch bug
was found and fixed in `sysvid_update` (`build.md` §1) but confirmed **not** the
cause — the defect persisted identically afterward. Ruled out by direct code
inspection: `rect_t` struct layout, the scroller's map-row-copy loop, and
`PLATFORM_ST` resolving identically on both builds (checked both actual compiler
invocations). Not root-caused; see `build.md` §2's note.

### T23 — Bomb fuse showed random sprites: a self-inflicted port defect ✅ **DONE 2026-09-10**

User report: dropping dynamite shows the wrong sprites during the ticking/fuse phase
("random other sprites", not a bomb). Traced to `review-log.md` A1/A6: that review
pass derived ST-native sprite-*slot* numbers from the real 68000 pointer tables
(re-verified bit-exact against `re/atari_ram.bin` — the formula itself is right) and
then used them **directly as `dat_spritesST.c` array indices**, on the unchecked
assumption that the two numberings are the same. They are, but **only through slot
`0x37`** — dumped and cross-referenced all 213 of `dat_spritesST.c`'s own per-entry
provenance comments against their array position and found the array is permuted
past that point (a different bank was extracted first, then this one). Confirmed:
the port's *original* fuse-table value that A1 "corrected" away (`0x99..0xA7`) was
already right, just expressed as the real array position rather than the ST's own
slot number — the review swapped a working value for a broken one.

**Not local to the bomb**: the same defect, same review pass, is in the box/bomb
shared explosion table (`0x90..0x94`, half its 10 entries) — `e_box.c` and
`e_bomb.c` both use it.

Fixed with a real lookup rather than picking one numbering by hand for these two
spots: `sprites_stnum_to_index[0xD5]` (`include/sprites.h`'s declaration/rationale,
`src/dat_spritesST_stmap.c`'s table), mechanically generated from
`dat_spritesST.c`'s own comments (paired each entry's array position with its
comment value, sorted by the comment value), verified a true bijection over
`0..0xD4` before using it. `e_bomb.c`'s fuse/explosion tables and `e_box.c`'s
ST-explosion table now read `sprites_stnum_to_index[...]` instead of the raw
ST-derived number — fixes this bug and any future ST-slot-derived number `>= 0x37`
used the same way. `review-log.md`'s A1 and A6 entries corrected in place rather
than left wrong. Both WSL platforms and the Windows build verified clean (no new
warnings); user confirmed fixed by playing it.

### T22 — Remove the dead `-data`/zip/zlib asset-loading path ✅ **DONE 2026-09-10**

Prompted by: now that sound comes from the compiled-in SNDH engine (T19), is the
`-data` directory still needed? **Confirmed no**, on two independent counts: (1)
`dat_sndh_engine.c` is a generated 186 KB source file — `sndh_engine_blob` is a byte
array literal compiled into the binary, nothing is loaded from a `.sndh` file at
runtime; (2) `data_file_open`/`_read`/`_close`/`_seek`/`_tell`/`_size` (`data.c`) —
the only things `-data`'s path was ever *for* — had **zero call sites anywhere in
the tree** outside their own definitions; only `data_setpath`/`data_closepath` were
ever called (from `game_run`), and they just open/close a handle nothing reads from.
`xrick/data/` on disk held only pre-T19 WAV files. Every asset (sprites, tiles,
rooms, the demo script) has been a compiled-in `dat_*.c` table this whole time —
audio (T19) was simply the last holdout.

Removed outright: `src/data.c`, `include/data.h`, `src/unzip.c`, `include/unzip.h`,
the `-data` CLI argument (`sysarg.c`/`sysarg.h`), `game_run`'s/`main`'s path
parameter, `config.h`'s `WITH_ZLIB`/`NOZLIB` toggle, and every zlib reference
(`-lz` in the Makefile, `zlib` from `vcpkg.json`, `z.lib`/`z.dll` from
`xrick.vcxproj`, `zlib1g-dev`/`zlib-devel`/`libz` from `build.md`'s dependency
lists) — zlib had no other consumer. Verified: `make clean && make` (both
`PLATFORM=ST`/`PLATFORM=PC`) drops from 266 to **216 warnings** (exactly the
`data.c`/`unzip.c`-local ones going away, none elsewhere); `./xrick` (no `-data`
argument at all) still runs correctly in WSL. `vcpkg install --triplet x64-windows`
cleanly *removed* zlib per the updated manifest; the Windows build (T21) still
builds and runs with just `SDL3.dll` next to the exe, no `z.dll`.

### T19 — Replace the port's WAV audio with the real SNDH engine ⭐ **P1-P8 DONE 2026-09-10 — P9 (knowledge-base writeup) remaining**

**Architecture, phased plan and full progress log: [`audio-sndh.md`](audio-sndh.md).**

The port had no sound engine — all 29 sounds were WAVs made by ear (`MEMORY.md` §9,
now superseded for `sounds.c`/`syssnd.c`). Implemented: the game's real lifted ST
sound engine (`re/assets/audio/rick_dangerous.sndh`'s source bytes, re-extracted
without the SNDH container by `xrick/xrick/tools/extract_sound_engine.py`) now runs
under Arnaud Carré's AtariAudio library (MIT, vendored verbatim into
`xrick/xrick/src/audio_engine/`), embedded in the binary and driven as one persistent
`AtariMachine` instance for the whole game session — not `SndhRenderer`, whose
one-subtune-at-a-time model would reset state on every trigger, wrong for a game that
layers music, SFX and two digidrums through one live engine.

Every `WAV_*`/tune symbol's ST track number is now backed by cited evidence (P3's
census, audio-sndh.md §7) — none guessed from the sound's English name. `syssnd.c`/
`sounds.c` rewritten; `dat_maps.c`'s level-tune field is now the track number directly;
dead legacy files (`dat_snd.c`, ten `wav_*.e`) removed; Makefile builds the vendored
C++ library alongside the tree's C. Both `PLATFORM=ST` and `PLATFORM=PC` build clean
in WSL (268 warnings, none new).

**A standalone verification harness (P8, not committed) caught a real bug the build
and a crash-free smoke run could not have**: the engine blob's internal absolute
references are relocated by the source dump's own load delta, and the first
implementation uploaded them at the wrong (canonical, non-delta-adjusted) address —
silently breaking every internal table lookup and hardware-vector install by
`-0x2054` while still running without crashing. Fixed, then re-verified byte-exact:
D1 delivery, `play_music` dispatch, the busy-guard behaviour (type-1/2 SFX correctly
refused while a type-0 track is active, confirmed directly rather than assumed), and
a PCM sample's data pointer all read back correct from emulated engine RAM. Also
fixed: a missing `silence_all_channels` call, and a first-`Jsr`-call reliability
quirk in the vendored library (segfaults or silently no-ops on a fresh machine; a
one-line warm-up call fixes it for the instance's remaining lifetime).

`xrick` is running interactively (real video + real audio via WSLg PulseAudio) for
the user's own by-ear pass — audible correctness is the one thing engineering
verification can't confirm. P9 (folding this into `xrick/re/`'s knowledge base) is
the only phase left.

**Regression found by playing it, 2026-09-10: sound mixing is gone.** The pre-T19
WAV mixer could play any number of sounds at once (independent PCM buffers summed
in software); the single emulated `AtariMachine` can only ever be doing one of
`{idle, tracked music, one PCM sample}` at a time, because that's a real limit of
the one YM2149 chip it emulates, enforced by the original unmodified `play_music`
code. Measured with a throwaway harness: a level's one-shot theme blocks every
gameplay sound effect for **16.30 seconds** at the start of each level. Not a bug
in this port (bit-exact original behavior, already verified faithful by P8) — but
a real usability regression worth a deliberate decision. Three options, none
implemented yet, written up with their trade-offs in `audio-sndh.md` §13.

### T18 — Demo (attract) mode in the port ✅ **ENGINE DONE 2026-09-08 — scripts to record**

**Design, decisions and verification: [`demo.md`](demo.md).**

`xrick -demo` replays a scripted sequence of control events, timed per submap, into the
game engine; `xrick -record <file>` writes one back out as a ready-to-build
`src/dat_demo.c`. The clock counts `CTRL_ACTION` passes (entity logic steps), not
milliseconds and not frames, because the port's game logic is deterministic and advances
only there — so a script replays identically at any `-speed` and any frame rate.

Engine complete and verified (zero new compiler warnings; the tree's warning total is
unchanged at 283); playback timing checked tick-exact against Rick's traced position.
The scripts themselves are the remaining work: `src/dat_demo.c` has a row for every one
of the 0x2F submaps, all empty, and the demo hands control back to the keyboard as soon
as it reaches an unrecorded one — so it is usable while only partly recorded.

Two things the implementation found that the plan had wrong, both fixed:
- `screen_introMain` never reaches `SCREEN_DONE` without a keypress — its timeout path
  loops the splash and hall of fame forever. A demo has to start the game itself.
- `sys_printf` formatted into a 1024-byte stack buffer with `vsprintf`, while
  `sysarg_fail`'s usage text is 1108 characters before expansion. `xrick -h` was already
  overrunning the frame and getting away with it; the two added help lines made it crash
  silently. Now `vsnprintf` into 4096, and `fputs` rather than `printf(s)`.

### T1 — Align the xrick port with the ST reverse engineering ⭐ **in progress**

**Plan and live status: [`review-plan.md`](review-plan.md); evidence log:
[`review-log.md`](review-log.md).**

**As of 2026-09-07 — read `review-plan.md` §11 first; it is written to be picked up cold.**

Done: phases 0, 2, 3a, 3b; the `xref.md` sweep; the whole **simulation core** — all entity
logic, the player, the map system and the game state machine (**68 of 199 functions**,
the ones with counterparts in the originals). **48 `PLATFORM_ST` switch sites. 23 defects
numbered, #18 retracted, so 22 stand fixed.** Both platforms build with 0 errors and
produce different binaries. T9 (pointers-vs-sprite-numbers) is **solved**:
`sprite = (ST pointer - 0x2BE9E) / 0x150`.

Remaining, in priority order (detail in `review-plan.md` §11.5):

1. **R1 differential testing** — the largest gap. `PLATFORM_ST` has never been *executed*
   against the original; it is a reconstruction from the disassembly. The Hatari harness
   already boots the ST build and dumps RAM in-game.
2. **A user decision**: is `GFXPC` ever to be revived? It does not compile, so
   `PLATFORM_PC` is today PC *behaviour* with ST artwork and ST audio.
3. **47 functions** — intro screens, `sounds.c`, and the render layer (what is drawn and
   when sound plays, not how SDL does it).
4. Three known port bugs in no-counterpart code; ST artwork pixel verification; and a
   short list of documented, deliberately unchanged carry-overs.

84 further functions (`unzip`, `syssnd`, `data`, `sysvid`, …) have **no counterpart** in
either original and are out of scope by the user's rule: what matters is the right sound
at the right time and the right bytes on screen, not how SDL delivers them.

**Note on item 3 and `syssnd`, 2026-09-10 (T19):** `sounds.c`/`syssnd.c` no longer need
a logic-alignment review the way the rest of item 3 does — they were rewritten to embed
and run the actual ST sound-engine bytes under 68000 emulation, so "the right sound at
the right time" is now enforced by construction rather than by re-derived C logic.
`intro screens` and the render layer's *when sound plays* still need item 3's review;
see `audio-sndh.md` for what changed and `re/algo-system.md`'s Sound section for the
current design.

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

### T4 — Sprite blitter transcription ✅ **RESOLVED 2026-09-04 — 0 defects**

`render_sprites` (`0x4B032`) was read instruction by instruction against
`algo-render.md`. The function is **290 instructions**; the two unrolled blit paths are
**122** (shifted) and **48** (aligned). **The transcription is faithful — no defects.**

This was the largest untested surface in `re/` and the likeliest remaining home for a real
defect. It is now checked, so that expectation is retired.

Verified in particular: `bchg.l #0xF,D0` supplies *both* the page flip and the branch
condition, and the `block_a`/`block_b` sense is right; all four despawn bounds and both
visibility bounds match including comparison strictness (`<=` vs `<` on the top clip,
`>=` vs `>` on the bottom); the `A`/`B` mask pair is built exactly as documented; and both
row advances total 160 (`3 x (A2)+ + 0x9A`, `1 x (A2)+ + 0x9C`).

One latent hazard was checked rather than assumed: `ya * 160` is computed with `.w` shifts
on a longword, so a carry out of bit 15 would be silently lost. `ya` is bounded to
`8..0xC7` by the preceding clip, giving a maximum of `0x7C60` — **no overflow is
reachable**.

Five **fidelity notes** were added to `algo-render.md` for things the C model cannot
express: `A1` is destroyed by `movea.w D6w,A1` right after `bset #1`; the shift count
lives in `D6` for the mask and plane 0 but `D0` for planes 1-3; plane 3's stores omit the
post-increment; the two paths count rows differently (`D7` directly vs shuttling through
`A5`); and `A3`/`A4` are recomputed from `A2` every row.

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

### T6 — Observe the trigger bits firing ✅ **RESOLVED 2026-09-04 — watched live**

Two Hatari runs (`re/hatari_probe.py triggers`, `triggers2`; delta `-0x2054` re-measured
and self-checked both times, cheats left off).

**Method that made it meaningful:** each bit's `btst` site executes for every trap entity
every frame regardless of the bit's value, so breakpointing it proves nothing. The probe
instead sits on each bit's **taken branch**, and on the `*_fired` sites where the hit test
also succeeded — 14 `:trace :once` detectors, so whatever `b` still lists at the end
provably never fired.

**Run 1 caught the whole chain, in causal order in the log:**

```
0x4D19A  0x80 set         armed for player-touch
   ... joystick := RIGHT ...
0x4D1B4  0x80 FIRED       player inside the trigger box
0x4D258  TRAP TRIGGERED   move.b #-1,(0x47,A0)
0x4D284  0x08 armed       lethal while TRIGGERED
```

**Run 2 caught `0x04`** (lethal while **IDLE**), the counterpart.

**Why this is the confirmation worth having.** `0x04` vs `0x08` is precisely the
distinction *Correction #1* in `algo-entities.md` had to introduce after the docs
conflated them as "always-lethal" — a wrong reading that, by that document's own account,
"survived nine byte-identity audits with the right reading two sections away". Both halves
are now **observed** on their respective branches: in level 1's opening room `0x08` fired
only *after* the boulder triggered, and `0x04` never fired there at all.

**Not reached — five bits: `0x40` (stick jab), `0x20` (bullet), `0x10` (explosion), `0x02`
(both disposal routes), `0x01` (one-shot).** Each needs Rick to *land* an attack on a trap
carrying that bit; blind scripted play does not manage it (run 1 ended `GAME OVER` in the
opening room). Their semantics continue to rest on the transcription — which for several
is independently corroborated by the PC binary under T8. Forcing them by poking
bullet-active flags and coordinates would demonstrate reachability, which the census in
`re/entities.md` already establishes, not semantics; it was deliberately not done.

**One honest gap:** run 2 showed the Missile Base intro but ended in level 1 after a
`GAME OVER`, and the `level_index` dump covered the word's high byte only (`00`,
uninformative). So `0x04` is confirmed to fire in shipped gameplay, but the room is not
pinned down. Full detail in `re/hatari.md` -> *Probe 4 in detail*.

### T7 — The `dbf D3w` name-entry loop ✅ **RESOLVED 2026-09-02 — statically, no live run needed**

**The loop is benign.** The concern was that the counter is the character just copied, so
the iteration count depends on entry state and the copy "generally over-runs the 10-byte
name field". It does over-run — by **exactly two bytes, onto their correct destinations**.

`D3`'s high byte decides everything, and it is provably always `0x00`: `D3` reaches
`COMMIT` holding the grid **row**, clamped to `0..4`; `move.b` never writes bits 8-15; and
`dbf` on `0x00XX` with `XX > 0` yields `0x00(XX-1)`. So the loop reduces exactly to
**"copy until the byte just copied is `0x00`"**, and terminates on a static sentinel:
`0x48FCA` = `FF`, `0x48FCB` = `00`, neither of which has **any** absolute reference in the
program (the buffer's three initialisers cover only the 10 bytes at `0x48FC0`).

Result: **always 12 bytes**, whatever is typed. Verified by modelling the loop
instruction-for-instruction in Python across typed names and both extremes of `D3`. The
destination absorbs them because the source mirrors the record tail — 10 name bytes to
`+0x12`..`+0x1B`, `FF` to `+0x1C` (the terminator slot, **correct value**), `00` to
`+0x1D` (pad). That is the last byte of the `0x1E`-byte record: **the next record is never
touched.**

Also noted: `move.w #0x0009,D2` at `0x491D0` is **dead** — `D2` is never read by the loop,
almost certainly a leftover from an intended `dbf D2`.

**The live confirmation planned for this item is unnecessary** — the behaviour is fully
determined by static data. Full write-up in `re/algo-system.md`.

### T8 — Adjudicate the port differences ✅ **RESOLVED 2026-09-02 — 17 of 17**

**Every one of the 17 measured differences is a genuine PC-vs-ST divergence. Not one was
an error by the port.**

The last two fell once the **`0x17E` address delta** was noticed: the port's `ASM nnnn`
comments are systematically `0x17E` low over the code region, so adding it lands on the
function entry. That turns the comments from vague landmarks into a lookup table. (It is
*not* global — `map_resetMarks` at `ASM 0025` sits at `0x0025` with no offset — so it is a
hypothesis to test per routine. Recorded in `xrick/re/provenance.md`.)

- **Bomb blast box** — `e_bomb_hit` at **`0x134B`** (`ASM 11CD` + `0x17E`):
  `MOV AL,[0x7EE0]` / `MOV AH,AL` / `SUB AL,4` (clamp 0 on borrow) / `ADD AH,0x20` (clamp
  `0xFF` on carry), then `MOV AX,[0x7EE2]` / `SUB AX,4` (clamp 0) / `ADD BX,0x1D`. So the
  PC box is x `[-4, +0x20]` clamped at `0xFF`, y `[-4, +0x1D]` — **the port's values
  exactly**. Ours is x `[-4, +0x1B]`, y `[-4, +0x18]`, unclamped.
- **Submap re-entry X** — `MOV word[SI+2],0x00E2` @ `0x19B9` (prev submap) and
  `MOV word[SI+2],0x0004` @ `0x19C9` (next submap): **`0xE2` / `0x04`, the port's values**.
  Ours is `0x02` / `0xE6`.

**Why the earlier searches missed it.** I had searched for `MOV AL,0xE2` (`b0 e2`) and for
a byte store to the absolute address `0x7E80`. The real instruction is
`C7 44 02 E2 00` — a **word** store through **`[SI+2]`**. The search was wrong in operand
width *and* addressing mode at once, so the validated-looking negative meant nothing. This
is the fourth instance of the same failure mode; see `MEMORY.md`.

**Two corrections produced by this pass:**

1. **A misattributed citation.** The `ADD AL,2` / `CMP AL,0xE8` at `0x1912`, previously
   cited as evidence for the *enemy corpse drift* row, is nothing of the kind: it is
   **Rick's own right-edge submap test**, inside `e_rick`'s movement code, which calls
   `u_envtest` at `0x191E`. The corpse-drift row still stands on its other evidence
   (`0x2563`/`0x2570`); the bad citation is removed.
2. **The port omits a store the original makes.** At both exits the PC writes
   `[0x7D77]` (`0x00` prev, `0x01` next) — precisely the `/*6dbd = 0x00;*/` and
   `/*6dbd = 0x01;*/` lines the port has **commented out**. That variable *is* read, at
   `0x0D99` (`MOV BL,[0x7D77]` / `CMP BL,[SI]`). The port substitutes `game_dir`, which
   may well be equivalent, but the omission is real and is now recorded.

### T9 — The `sni` → `sprbase` substitution ✅ **RESOLVED 2026-09-04 — explained**

Both sides had recorded this as unexplained; the port's author wrote *"FIXME what is this?
... Why? What is the point?"*. It is now understood, and it is **not a divergence**.

**The condition selects exactly the type-1a/1b walking enemies**, and both halves are
deterministic:

- **`e >= 9` is not allocation luck** — `ent_actvis`'s allocator routes on the entity
  number: `mark.ent >= 0x10` → `ent_creat1` → slots 4-8; `mark.ent < 0x10` →
  `ent_creat2` → slots 9-C. So `e >= 9` **is** `mark.ent < 0x10`.
- **All four trigger bits is the natural encoding for a live enemy** — killable by touch,
  jab, bullet and explosion. Not an arbitrary sentinel.

**Shipped ST data confirms it**: of the 78 `PlacementRecord`s with `bTriggerFlags & 0xF0
== 0xF0`, **75** have type `< 0x10`, and their types are exactly `4,5,7,8,10,11,13,14` —
the port's own `e_them` type 1a (`4,7,a,d`) and 1b (`5,8,b,e`). The other 3 are types
40/43, which are `>= 0x10` and route to slots 4-8 where the substitution is correctly
skipped. The port's FIXME guessed "type 1 and 2"; the data says **1a and 1b only**.

**What `sni` really holds.** For the reachable indices it is not a movement index at all
but a **second sprite number**: `spr` = `0x2F`/`0x37`/`0x41`/`0x4B` by enemy bank seeds
`ent.sprite`, while `sni` = `0x8E`/`0x7E`/`0x86`/`0x86` becomes `sprbase`, the base of
`sprite = sprbase + ent_sprseq[...]`. Type-1 enemies move under AI rather than along
`ent_mvstep` paths, so the field is dead and gets reused. This also explains the artifact
the port's author saw — a spawned-falling enemy changes sprite on landing, because
`ent.sprite` keeps its `spr`-derived value until the handler recomputes it.

**Why the ST has none of it — structural, not behavioural.** `init_entity_from_placement`
(`0x49742`) has no all-four-bits test and no slot test; the only three `andi.b #0xF0`
sites in the ST code region are the X-snap `(x & 0xF0) | 0x04`; and ST entity `+0x20` is
`wScreen_offset_b`, not a sprite base. The ST `ObjectTypeDef` is **16 bytes of real
pointers** (`anim_frame_table` `+6`, `movement_path_table` `+0xA`) against the PC's
**8 packed bytes** of sprite numbers. No "base + offset" formula ⇒ no second base ⇒
nothing to overload.

**Latent difference, unreachable in shipped data:** the PC writes only the low byte
(`MOV [SI+0x20],CL` @ `0x2198`), the port assigns the whole `U16`. They differ only if a
`spr` exceeds `0xFF`; the maximum across all 74 `ent_entdata` entries is `0x0080`.

Full write-up in `xrick/re/xref.md`.

### T10 — ~~Report the port's `map_connect` overrun~~ ❌ **RETRACTED 2026-09-04 — the defect does not exist**

**This was my error, and the report drafted on 2026-09-02 is void.** Nothing was sent
upstream, so no correction is owed to anyone but this document.

**What went wrong.** I counted the initialiser records in `dat_maps.c` with a
`\{([^{}]*)\}` regex over the **raw** text. That matches brace pairs inside **comments**.
One record in the table is commented out, and the author's note says exactly what it is:

```c
/* was {0000, 0x38, 0x13, 0x68} ?? - now OK */
```

That is the surplus list-17 connector — **already found and removed by the port's author**,
with "now OK" recording the fix. My "154 records vs a declared 153" was that dead comment.

**The truth, re-derived with comments stripped and brace depth tracked:**

| | port | ours |
|---|---|---|
| records | **153** | 153 |
| connectors + terminators | **106 + 47** | 106 + 47 |
| lists | 47 | 47 |
| `MAP_NBR_CONNECT` | `0x99` = 153 ✓ | — |
| per-list lengths | **all 47 agree**, list 17 included (2 = 2) | |

So `map_connect` is **correct**, its declared bound is **correct**, and it agrees with our
ST transition tables in every list. The earlier "46 of 47 match" was the same artifact.

**Consequences, all corrected:** `xrick/re/xref.md`'s *Settled* table listed this as the
one "Port defect" — it is now an agreement, which means **not a single difference found
against the port in this entire project turned out to be a port error.**
`re/data-structures.md` and `re/byte-identity.md` are corrected too.

**Method lesson (now in `MEMORY.md`):** I had *already* recorded this exact trap on
2026-09-04 after it nearly produced a phantom `ent_entdata` bug — and had not gone back to
recheck the earlier `map_connect` count made the same way. **When a parsing method is
found to be unsound, re-run every earlier result that used it.**

### T11 — The MFP TACR prescaler ✅ **RESOLVED 2026-09-04 — measured**

**Measured, not argued from a datasheet.** The Timer-A ISR advances `0x457C8` by exactly
one byte per interrupt, so that pointer *is* the interrupt counter. Holding the loop flag
`0x45004` non-zero makes the sample rewind instead of stopping, giving an unlimited
measuring window — and the whole thing needs no gameplay, since poking exactly what
`play_music`'s type-2 branch writes starts a sample deterministically.

**24 readings over 19.6 s fit a line at 4915.7 bytes/s. The documented table predicts
4915.2 Hz. Ratio 1.0001.** The nearest alternative divisor (`/64` → 7680 Hz) is 56 % away,
so `prescaler(6) = /100` and the 2457600 Hz clock are both confirmed.

**The scope is narrower than feared, in two ways:**

1. **Only entry [0] of `0x44FF0` is ever used.** All three type-2 tracks (8, 10, 19) carry
   `nParam_index = 0`, so `TACR=6, TADR=5` is the only pair the shipped game programs —
   and it is the pair measured. Entries [1]–[5] (7680 / 9600 / 14985 / 19819 / 30720 Hz)
   are unused data, so the divisors for TACR 1, 2 and 5 are not depended on anywhere.
2. **The old claim that "every tempo figure depends on it" was wrong** — a defect in the
   T11 write-up itself, now corrected in `algo-music.md`. Tracked music runs off the
   **50 Hz VBL** (`music_tick`), not Timer A. The prescaler governs the **digi-sample
   rate alone**.

A free cross-check fell out: unwrapping the looping pointer required the sample length,
and the gunshot measures `0x4DF86`–`0x4FCF0` = **7530 bytes** to its `0x00` terminator,
matching `assets-manifest.md`. A wrong length could not have yielded a 0.01 % linear fit.

⚠️ **Measured under Hatari's MFP emulation, not real silicon.** If Hatari's own divisor
table were wrong, the measurement would faithfully reproduce that error. Confirming on
real hardware would need an actual ST; noted rather than claimed away.

### T12 — `palette_fade_in`'s precondition ✅ **RESOLVED 2026-08-31 — verified, not assumed**

The claim "assumes the palette currently reads black" is now **proven for every call
site**. Three steps:

**1. Only three routines can write the palette.** Scanning the image for the hardware
palette base `0x00FF8240` gives exactly three stored longwords — `0x49382` (inside
`set_palette`), `0x493AE` (inside `palette_fade_in`) and `0x4940A` (inside
`palette_fade_out`). Nothing else touches `0xFF8240`. And `set_palette` has exactly
**one** caller, `0x4DE4A`.

**2. Eight of the nine `palette_fade_in` call sites have a `palette_fade_out` in the same
function.** Both routines have 9 callers; the pairing (call-site scanner validated at 31
callers for `vsync_wait`):

| `palette_fade_in` | blacked out by |
|---|---|
| `0x490A8` | `0x4903C` |
| `0x49918` | `0x498DE` |
| `0x49B48` | `0x49ACC` |
| `0x4B700` | `0x4B5F8` |
| `0x4DDEC` | `0x4DDBA` |
| `0x4DE98` | `0x4DE68` |
| `0x4DF0A`, `0x4DF38` | `0x4DF02`, `0x4DF28` |

**3. The ninth resolves through its call chain.** `0x499BC` sits in
`enter_screen_with_fade` (`0x499B8`), which is only
`bsr init_screen_pointers; bsr palette_fade_in; rts` — no blackout of its own. It has
**exactly one** caller, and that chain closes it:

```
show_selection_menu 0x499A0
  ├── bsr run_selection_menu   0x498C6
  ├── bsr start_level          0x4B588   (verified: bsr @0x499AE -> 0x4B588)
  │     └── bsr show_level_intro_screen 0x4B5F4   (sole caller, @0x4B5EA)
  │           ... 0x4B794  bsr palette_fade_out 0x493FE   <- palette goes black
  │               0x4B798  bsr reset_hud_dirty_and_redraw
  │               0x4B79C  clr.w 0x4AA92 / 0x4AAA8 / 0x4AAAE
  │               0x4B7AE  bsr spawn_player_entity 0x4BFAE
  │               0x4B7B6  rts                              <- still black
  └── bsr enter_screen_with_fade 0x499B8 -> palette_fade_in
```

Nothing between the fade-out at `0x4B794` and the return can restore the palette:
`reset_hud_dirty_and_redraw` and `spawn_player_entity` cannot reach `set_palette`, whose
only caller is `0x4DE4A`, elsewhere. **The precondition holds on every path.**
`algo-system.md` updated — the wording is now a verified contract, not an inference.

### T13 — Screen buffer bases ✅ **RESOLVED 2026-08-31 — read directly**

The inference is replaced by a direct read. `0x492EA` is the longword holding the current
screen address, and in `atari_ram.bin` it reads:

```
0x492E8:  00 00 | 00 07 80 00 | 23 fc
                 ^^^^^^^^^^^ 0x492EA = 0x00078000
0x492EB = 0x07   (-> 0xFF8201, base bits 16-23)
0x492EC = 0x80   (-> 0xFF8203, base bits 8-15)
```

`flip_screen_buffer` does `*(byte*)0x492EC ^= 0x80`, so the mid byte alternates
`0x80`/`0x00` and the longword alternates **`0x00078000`** / **`0x00070000`**. Both bases
are therefore confirmed from the value the program actually feeds the video hardware, not
inferred from `draw_string`. `memory_map.md` updated.

### T14 — Is `hide_entity` dead code? ✅ **RESOLVED 2026-08-31 — yes, with a validated query**

The concern was that `get_xrefs_to` cannot see table dispatch. Scanning the whole 320 KB
image for the stored longword `0x0004AC08` returns **zero** sites — and this time the
query is **validated against real dispatch targets**:

| Longword | Meaning | Sites |
|---|---|---|
| `0x0004D15C` | known dispatch target | **50** |
| `0x0004B856` | known dispatch target | **1**, at `0x4AC04` |
| `0x0004AC08` | `hide_entity` | **0** |

The single `0x4B856` hit lands exactly on the table slot `algo-render.md` names, which
also confirms the correction that `0x4ABF8`-`0x4AC07` are four dispatch entries
(`0x4ABF8`/`0x4ABFC`/`0x4AC00` -> `0x4D15C`, `0x4AC04` -> `0x4B856`) rather than the start
of the function.

Reading `0x4AC08` itself confirms the entry point and the transcription:
`08A8 0000 0016` = `bclr #0,(0x16,A0)`, `08A8 0000 001C` = `bclr #0,(0x1C,A0)`, `4E75` =
`rts` — the two render-flag clears exactly as documented.

**Scope of the negative:** this covers absolute 32-bit pointers plus Ghidra's
control-flow xrefs. A table of 16-bit offsets or a computed address would not be caught —
but the game's dispatch tables demonstrably use absolute longwords (50 hits on one
target), so that is the right form to search. `hide_entity` is unreachable.

### T15 — Provenance of `atari_ram.bin` ✅ **RESOLVED 2026-08-31 — no check required**

Previously raised as the project's load-bearing assumption: because layer-2 decompression
was abandoned as impractical, every fact in `re/` is read out of a Hatari RAM snapshot
that had never been cross-checked against what `RICK.PRG` produces.

**Closed by the user, who produced the artifact:** `atari_ram.bin` is their own dump of
Hatari's RAM, taken from the game running correctly. Its provenance is **attested at
first hand and is fully trusted**. No re-dump, diff, or decompressor work is needed, and
the layer-2 decompressor does not need to be reproduced for this purpose.

*Evidence type: direct attestation by the person who created the file* — not a check run
inside this project, and recorded as such so the basis stays visible.

### T16 — "the engine is always clean" ✅ **RESOLVED 2026-08-31 — verified, plus one defect found**

**The ordering claim is true.** The first `play_music` executed after boot is
`play_music(5, 1)` at `0x4DC62`, inside `main_init_and_loop`'s init sequence
(`0x4DC2A`–`0x4DCCD`) — before `attract_mode_loop`, before `NEW_GAME` (`0x4DC9E`), before
the per-frame main loop (`0x4DCCE`). Track 5 is **type 0**, so `init_music_playback` runs
and zeroes the per-channel work area before anything else can sound. All 22 type-1/2 call
sites are in gameplay code (`0x4BE9A`–`0x4D89C`), reachable only from the main loop, and
`RESTART` (`0x4DC90`) re-plays track 5 before re-entering attract mode. The type-1/2 skip
of `init_music_playback` is safe in the shipped game.

**Method:** read `nTrack_type` from all 29 `MusicTrackDescriptor` records at `0x44F08`,
then enumerate all **27** `play_music` (`0x44CCE`) call sites and classify each by the D0
literal preceding it.

**Defect found on the way — `assets-manifest.md` had the type-0 census wrong.** It read
"subtunes 1–8 are the only type-0 tracks". There are **nine**: tracks `0`–`7` **and `27`
(0x1B)**. Track 27's `nParam_index` is `8`, the ninth entry of the 9×6 song table at
`0x46932`, independently confirming the nine-song count. It reaches `play_music` through
the entity trigger-sound range (`0x13`–`0x1C`), not as a literal. Corrected.

**Also corrected in passing:** three call sites take a computed track number
(`0x44E5A` the engine's own loop restart, `0x4D26C`/`0x4D2CC` entity trigger sounds), and
`0x4B6FC` is `D0 = level_index` — `0x4B6F2`'s `moveq #0,D0` is immediately overwritten by
`move.w (0x4B586).l,D0`. A naive "nearest preceding literal" scan misreads that site as
`D0 = 0`; it is a runtime value, always in the type-0 range `0`–`7`.

### T17 — The port's `e_them_rndseed` pointer ✅ **RESOLVED 2026-08-31 — it is a real bug**

Both prior readings were inferences about the author's intent. The PC binary settles them.

The randomiser is a subroutine at `0x024A` in `re/ibmpc_cs.bin`, followed immediately by
the seed increment at `0x0270` — **the exact address the port annotates as `(0270)`**,
which confirms the correspondence independently:

```
024C  MOV BX,[0x7E48]     ; e_them_rndnbr
0250  ADD BX,[0x7E4A]     ; + seed LOW word
0254  ADD BX,0x0D
0257  MOV CX,[0x7E4C]     ; seed HIGH word
025B  ADD BX,CX
025D  SUB AL,AL / XOR AL,BL / XOR AL,CH / XOR AL,CL / XOR AL,BH / MOV BL,AL
0269  MOV [0x7E48],BX
0270  ADD word [0x7E4A],1 / ADC word [0x7E4C],0    ; 32-bit increment
```

The `ADD`/`ADC` pair proves the seed is **32 bits held as two words** — low `0x7E4A`,
high `0x7E4C` — and the randomiser reads **both**. The high half is therefore
`(U16*)&e_them_rndseed + 1`. The port's `+ 2` addresses four bytes past a four-byte
object. **Confirmed defect in the port**; `divergences.md`'s warning that the port's enemy
randomness is not evidence about the original's is upheld.

**The XOR chain is transcribed correctly** — the PC's `AL` temporary fold is equivalent to
the port's three `*bl ^=` statements.

**The "Black Magic" is explained.** Add the running value, both halves of the free-running
frame-counter seed, and 13; fold all four bytes of `BX`/`CX` into the low byte by XOR;
test bit 0 for the direction. The author could not explain it because they never had the
seed's two-word layout — the same gap that produced the `sh` bug.

**Relation to T8's "zero port errors".** No contradiction: T8 concerned 17 measured
*behavioural constants*, and the port read its build correctly in every one. This is a
different category — a C-level pointer slip in the transcription, not a misreading of the
original. It is also **not** the same question as T9 (`sni`→`sprbase`), which stays open.

**Three-way note.** Our ST build does not share this design at all: it has a genuine
two-longword PRNG (`seed_prng_state` `0x49574`, `update_prng` `0x49596`, fixed seeds
`0x121901F9`/`0x160566F9`), consumers testing `prng_b & 3`. The PC's accumulate-and-fold
scheme and the ST's PRNG are independent implementations — consistent with the S6 finding
already recorded in `byte-identity.md`.

**Note.** Two further "needs verification" markers in `re/` are **already covered** and are
not new items: the `dbf D3w` name-entry loop (`algo-system.md`) is **T7**, and the
trigger-bit dynamic spot-check (`entities.md`, `hatari.md` probe 4) is **T6**.

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
| **T8: PC code segment arrives, 13 of 17 adjudicated** | 08-31 | `re/ibmpc_cs.bin` (PC code segment) verified to correspond to the port's cited addresses — decisively at `map_resetMarks`, where `MOV CX,0x20B` (523) and `ADD BX,5` sit exactly at the cited `0x0025`. **Twelve differences confirmed as genuine PC-vs-ST divergences; zero port errors.** One new difference found (ceiling-bonk velocity: PC zeroes it, ST sets `0x80`) and eight new three-way agreements, including the arbitrary super-pad `0xFE` and `−0x800`. Four rows remain, blocked on locating the code, not on evidence |
| **pm-baty inventory** | 09-09 | `pm-baty/` compared file-by-file against its base (xrick #021212, commit `28297ba`, identified via SDL 1.2 headers + 1998-2002 copyrights). Normalized token-level diffs; 16 files identical, ST sprite/tile/ents data byte-identical. Non-cosmetic deltas catalogued in `pm-baty.md`: 9 gameplay (G1 speed 75→60ms, G2 map-1 submap 0x12 skipped, cheats gone, zombie guards, bonus anim, bullet/enemy edge behavior, `WAV_ENTITY[-20]` OOB fix, sound flush on submap change) + 6 presentation (video rewrite w/ filter, status-bar overlay layout, intro rework, PC hiscore table, keys). Direction caveat: some deltas may be pre-021212 upstream, not pm-baty edits |
| **pm-baty disposition + G8 analysis** | 09-09 | Decision: only **G2** and **G8** are port candidates; the rest ignored as pm-baty-specific. G8 dissected — the wakeup line hides 3 defects: (a) `snd==0` should be **silent** (ST census) but xrick indexes `WAV_ENTITY[-19/-20]` — 26 trigger-flagged placements with `snd==0` sit in **Egypt** alone (types 0x18/0x19/0x1a/0x25/0x26/0x49), the likely "jewel freeze"; pm-baty guards this, rework does not. (b) base off-by-one — rework fixed (R3.12a base 0x13), pm-baty did not. (c) ten ST tracks vs nine shipped `ent*.wav` — slot 9 NULL, silently swallowed. Full fix = pm-baty guard + rework base + tenth WAV. Details in `pm-baty.md` |
| **G8(a) adjudicated against ST/PC** | 09-09 | Why the rework is still broken on (a): R3.12a only examined the ten **non-zero** `snd` values and fixed the base; `snd==0` was never tested. Originals verified at instruction level: **ST guards on zero at both `play_music` sites** (`0x4D262 tst.w/beq` at FIRE, `0x4D2C6-8` at the bit-7 replay site — decoded from `re/atari_ram.bin`); **PC plays no wakeup sound at all** (`ibmpc_cs.bin 0x2836-0x2860`, located by the unique `step_no=step_no_i` signature `8b 44 22 89 44 24`; body = zombie guard + lethal bits + step init only). So the aligned fix is the ST rule: play only when non-zero. New side finding **(d)**: the ST replay-at-anim-end (bit 7, two `0x9A` entries) is absent from the port. (c) accepted for now: ship ent0-8, fix later |
| **G8(a) fixed in the port** | 09-09 | `e_them.c` wakeup now zero-guarded, ST-aligned: `(trigsnd & 0x7F) != 0` (mirrors ST `bclr #7` + `tst.w/beq` at `0x4D262`), under `PLATFORM_ST && ENABLE_SOUND` per the defect-21 precedent (PC verified silent at wakeup). Slot-9 NULL note added in `sounds.c` (c accepted). Built in **WSL** `make` — clean, no new warnings; headless smoke run boots Egypt (`-data ../data -submap 10`) without panic; visible window launched for visual verification. Sound defect (OOB/wild pointer) is gone; (d) replay-at-anim-end stays open. Uncommitted |
| **G2 adjudicated — port already correct, closed** | 09-09 | First **content-level** three-way compare of the 47 connect lists (D2/10d had only compared counts). New PC structure located: room headers **47×8 bytes at `ds1:0x84CC`** `{variant, pTileMap, pTransitions, pPlacements}` (room 0 → `0x523A` bnums, `0x88EF` marks), 6-byte waypoints `{side, row, pDest, entry}`, `0xff` list terminator, `0x00FF` = end-of-level; 106 waypoints, same as ST. **46/47 lists identical ST == PC == port on every field** (port dir is the known LEFT=1 flip). Sole divergence = room 0x11 waypoint 2: ST → 0x12@0x18 (bidirectional), PC → 0x13@0x68 (forward path skips Egypt room 0x12; still enterable backwards from 0x13). Port holds the ST value — BigOrno`s 021212 edit replaced his PC source value, which ds1 corroborates byte-exact. pm-baty = PC routing. **No port change needed**; optional `PLATFORM_PC` ifdef noted in `pm-baty.md` |
| **G2 fixed: PLATFORM_ST/PC split applied** | 09-09 | Per user request, both platforms made truthful rather than ST-only. `dat_maps.c` submap 0x11 record now `#ifdef PLATFORM_ST` `{0,0x38,0x12,0x18}` `#else` `{0,0x38,0x13,0x68}` `#endif`, same pattern as the file`s existing `map_maps`/`map_eflg_c` splits. Verified in **WSL**: both `make PLATFORM=ST` and `make PLATFORM=PC` build clean; a standalone dumper linked against the compiled `dat_maps.o` printed the actual runtime array contents under each macro (not just inspected source) — confirmed ST and PC values land correctly with neighboring records and the list terminator unaffected; both full builds pass a headless smoke run at submap 0x11. G2 closed, uncommitted |
| **T20: SDL2 → SDL3** | 09-10 | Verified SDL3 exists and 3.4.16 is the current latest (GitHub releases page + vcpkg's `sdl3` port agree independently); WSL build used Debian's packaged **3.2.10** instead (source build of 3.4.16 blocked on a `libxtst-dev` dependency needing interactive sudo). Migrated all 7 SDL-using files (window/renderer/texture API, pull-model audio via `SDL_OpenAudioDeviceStream`, event-type renames, joystick API, mutex renames) plus the Makefile (`pkg-config` instead of `sdl2-config`). Both `PLATFORM=ST`/`PLATFORM=PC` build clean, 266 warnings, none new. **Caught by running it, not by review**: the window was all-black after a clean build — SDL3 apparently defaults textures to alpha-blended rendering, and the game's texture alpha byte is always 0 — fixed with one `SDL_SetTextureBlendMode(..., SDL_BLENDMODE_NONE)` call, confirmed by the user looking at the relaunched window. `xrick.vcxproj`/`vcpkg.json` (Windows/MSBuild path) edited for consistency but not built — WSL-only build rule stands |
| **T21: Windows x64-only, `bin\<Config>\`, Release default** | 09-10 | User granted one-time permission to build on Windows. Dropped Win32/x86 from `xrick.vcxproj`/`xrick.sln`; output moved to `bin\Debug`/`bin\Release`; added Release/x64 defaults for a bare `MSBuild xrick.vcxproj`. Found two real problems only by building: existing `<!-- -->` comments had invalid bare `--` inside them (`MSB4025`, project wouldn't even parse) — swept and fixed all of them; and `MSBuild xrick.sln` (vs `xrick.vcxproj` directly) ignores the new defaults and always builds Debug, an unfixable MSBuild solution-wrapper behavior — `build.md` now says to build the `.vcxproj`. `vcpkg install --triplet x64-windows` installed `sdl3@3.4.16` for real, confirming T20's baseline claim against an actual install. Built and ran on native Windows: video/audio/`-h` all confirmed. **Found by playing it, still open**: scrolling glitches + sprite misalignment on Windows only, not WSL; a real texture-pitch bug was found and fixed in `sysvid_update` but confirmed not the cause (symptom persisted identically) |
| **T22: removed `-data`/zip/zlib** | 09-10 | Confirmed both the SNDH engine is fully compiled-in (T19, `dat_sndh_engine.c` is a 186 KB generated array) and `data_file_{open,read,close,seek,tell,size}` had zero callers anywhere in the tree — `-data`'s path was only ever fed to `data_setpath`, which opened a handle nothing read from. `xrick/data/` held only pre-T19 WAV leftovers. Deleted `data.c`/`data.h`/`unzip.c`/`unzip.h` outright; removed the `-data` CLI arg, `game_run`'s/`main`'s path parameter, `config.h`'s `WITH_ZLIB` toggle, and every zlib reference (Makefile `-lz`, `vcpkg.json`, `xrick.vcxproj`'s `z.lib`/`z.dll`, `build.md`'s package lists) — zlib had no other consumer. Verified: WSL warnings 266→216 (exactly the two deleted files' own warnings, confirming no other file needed them); `./xrick` runs with no `-data` arg; `vcpkg install` cleanly uninstalled zlib per the updated manifest; Windows build still runs with just `SDL3.dll` |
| **T23: bomb-fuse sprite bug, self-inflicted** | 09-10 | User report: dropping dynamite shows random sprites during the fuse phase. Root cause was this project's own `review-log.md` A1/A6 pass, not the original port: it derived correct ST-native sprite-slot numbers (re-verified bit-exact) but used them directly as `dat_spritesST.c` array indices, which only matches slot number through `0x37` — dumped all 213 array entries' own provenance comments and found it permuted past that, confirming the port's original value (discarded by A1 as "wrong") was actually already correct. Same defect also in the box/bomb shared explosion table (`e_box.c`/`e_bomb.c`, half its 10 entries). Fixed with a generated `sprites_stnum_to_index[]` lookup (`sprites.h`, `dat_spritesST_stmap.c`), mechanically derived and verified as a true bijection, not hand-picked; wired into both tables; `review-log.md`'s A1/A6 corrected in place. User confirmed fixed by playing it |
