# pm-baty vs xrick — non-cosmetic change inventory

**Status: COMPLETE** — all 66 pm-baty game sources reviewed against baseline (28 vendored
SDL 1.2 headers excluded as third-party).

## Goal
Compare every `*.c` / `*.h` in `pm-baty/` against the xrick port it derives from, and list
only changes that affect gameplay/behavior (ignoring reformatting, renames, file moves and
other cosmetics).

## Baseline identification (verified)
- pm-baty vendors SDL **1.2** headers → predates master's SDL2 migration (`c630025`).
- pm-baty copyright headers say `1998-2002`; `9b5617c` (#050500) says `1998-2019`,
  `28297ba` (#021212) says `1998-2002`; pm-baty `rick.c` matches #021212 `xrick.c` structure.
- **Baseline: commit `28297ba` "Import #021212 version"**, in a scratch worktree.
- Effective baseline build config (`include/config.h` of #021212): **GFXST**, `ENABLE_SOUND`,
  `ENABLE_CHEATS`, `DEBUG`; `ENABLE_JOYSTICK`, `ENABLE_FOCUS`, `ENABLE_DEVTOOLS` **undefined**.
  Differences are classified against this *effective* build, so removing `#ifdef GFXPC` or
  `control_active` code is a no-op (dead code in the effective baseline).

## Attribution caveat (unverified direction)
Some differences may come from pm-baty's true upstream being an *earlier* 2002 xrick
snapshot rather than deliberate pm-baty edits. Evidence: at the changed `dat_maps.c` entry,
#021212 itself carries `/* was {0000,0x38,0x13,0x68} ?? - now OK */` — the "was" value is
exactly pm-baty's value. Affected findings are marked *(direction unverified)*. Everything
below is reported as **pm-baty vs #021212**, which is what can be proven from this repo.

## Method
- `normalize.py` (scratchpad): strips comments, collapses whitespace, removes spaces
  around punctuation, canonicalizes integer literals (octal/dec/hex → hex), one statement
  per line. Cosmetic reformatting then diffs to zero.
- `diff -u` on normalized pairs; every non-empty diff reviewed by hand.
- pm-baty flattened `src/`+`include/`; PC/ST data files merged. The merged data files were
  additionally diffed against the ST-only baseline files.

## Global architectural changes
- **GFXPC path deleted** (code + `dat_*PC.c` data). No effective impact (baseline built GFXST).
- **External-data layer deleted**: `data.c/h`, `unzip.c/h`, `img.c` gone; no `data.zip`.
  Graphics/maps compiled in; **sounds loaded from plain `sounds/*.wav` files via stdio**
  (baseline: from data.zip via the data layer). Same WAV file names.
- **config.h deleted**; conditionals resolved: sound always on, **joystick always on**
  (baseline effective build had none), **cheats removed**, devtools/focus code dropped.
- **Windows-only port**: `vsprintf_s`/`fopen_s`/`sprintf_s`, errors via `MessageBox`,
  caption "Rick Dangerous", window icon removed.

## Findings — gameplay-affecting

- **G1 — game speed: `GAME_PERIOD` 75 → 60 ms** (game.h). Frame period drops from 75ms
  (~13.3 fps) to 60ms (~16.7 fps): the whole game runs ~25% faster. Additionally game.c
  re-derives the period each frame and runs the **intro-map screen at half period**
  (double speed) — baseline used one period everywhere.
- **G2 — map routing: map 1 submap 0x11 exit re-routed** (dat_maps.c). Baseline
  `{0000,0x38,0x12,0x18}` → pm-baty `{0000,0x38,0x13,0x68}`: the exit leads to submap
  0x13 at x=0x68 instead of submap 0x12, which pm-baty marks "NOT PLAYABLE - skipped".
  Matching guard in sysarg.c: `-submap 0x12` is redirected to 0x13. *(direction
  unverified — see caveat; #021212's comment shows pm-baty's value is the older one.)*
- **G3 — cheats removed** (game.c/h, e_rick.c, ents.c, util.c, draw.c, sysevt.c):
  F7 (trainer: unlimited lives/ammo), F8 (never die), F9 (show hidden entities) all gone,
  along with the cheat-state HUD letters.
- **G4 — "zombie" (dying) guards added** *(pm-baty additions)*:
  - e_bonus.c / e_sbonus.c / e_box.c: bonuses, speed-bonus triggers and ammo boxes can no
    longer be collected while Rick is dying.
  - e_bomb.c: while Rick is dying the bomb skips its explosion phase (no explode sound,
    no lethal blast, no sprite switch — it just times out).
  - e_them.c (type 1): while Rick is dying, enemies skip the stick-latency and
    touch-kill tests.
- **G5 — bonus pickup animation removed** (e_bonus.c): baseline animates the bonus
  (sprite 0xad floating up for ~9 frames) before it disappears; pm-baty removes it
  instantly. Score identical (+500). *(direction unverified)*
- **G6 — bullet left-edge range** (e_bullet.c): despawn condition `x <= -0x10` →
  `x <= 0x1`; a bullet fired left disappears ~17px earlier at the screen edge.
  *(direction unverified)*
- **G7 — walking enemies at screen edge** (e_them.c): baseline turns the enemy around
  (`offsx = -offsx`) when `x<0 || x>0xe8`; pm-baty **deactivates** it (`n=0`) when
  `x<1 || x>0xe8`. *(direction unverified)*
- **G8 — out-of-bounds sound index fixed** (e_them.c wakeup): baseline plays
  `WAV_ENTITY[(trigsnd&0x1f)-0x14]` unconditionally — when `trigsnd&0x1f == 0` that
  reads `WAV_ENTITY[-20]`; pm-baty guards with `if ((trigsnd&0x1f) != 0)`. Bug fix.
- **G9 — sound channels cleared on submap entry** (game.c): `syssnd_pause(FALSE,TRUE)`
  added at INIT_BUFFER and CHAIN_END — sounds no longer carry across submap changes.

## Findings — presentation / UI (player-visible, not game logic)

- **P1 — video backend rewritten** (sysvid.c, system.h, sysevt.c): fixed 640×480×32bpp,
  zoom fixed at 2, **fullscreen by default** (Alt+Enter toggles), hardcoded 16-color ST
  palette (baseline: 8bpp palettized, 32-entry palette, windowed default, F1 fullscreen,
  F2/F3 zoom 1–4, `-fullscreen`/`-zoom` args). New **smoothing filter, on by default,
  toggled with F7** (bilinear-ish blend, applied above y=0xdc). Picture letterboxed
  20px down (480 − 400 = 80 px).
- **P2 — screen layout** (draw.c, ents.c): baseline ST build reserves the top 8px row
  for the status bar and shifts map+sprites down by 8; pm-baty draws the map at y=0 and
  **overlays the status bar at y=8 on the map**, using the baseline's *PC* status
  coordinates, and restores map background tiles behind unused ammo/lives slots
  (`draw_clearStatus()` removed; `draw_drawStatus()` does its own restore).
- **P3 — intro/attract rework** (scr_imain.c, scr_xrick.c deleted, screens.h,
  dat_screens.c, dat_pics.c):
  - xrick's own splash screen (`screen_xrick`) deleted.
  - `pic_splash` replaced by a small banner image drawn 216×22 at (0x32,0x10) with the
    `screen_imaincdc` text ("…1989 CORE DESIGN / PRESS SPACE TO START", text altered)
    — baseline ST drew a 320×200 full-screen splash.
  - `pic_haf` (hall-of-fame header) replaced, drawn 192×22 at (0x40,4) vs full-width.
  - Attract cycling simplified: starts on the hall of fame, and **fire starts the game
    immediately** (baseline forced you through both screens once before starting).
  - `screen_imainrdt` (PC-mode title text) deleted — dead in effective baseline.
- **P4 — default high-score table** (game.c): pm-baty ships the baseline's *PC* name
  table (DANGERSTU, KEN, JAYNE…) instead of the ST table (SIMES, JAYNE, DANGERSTU…).
- **P5 — game-over screen** (scr_gameover.c): baseline clears the framebuffer before
  drawing "GAME OVER"; pm-baty doesn't (text drawn over the last frame).
- **P6 — keys** (sysevt.c vs deleted syskbd.c): movement keys identical (Z/X/O/K +
  arrows, Space); **pause P → Pause key, end-game E → End key**; `-keys` rebinding
  removed; Alt+F4 quits; **F4 mute is shadowed when Alt is held**; new F10 handler
  clears the EXIT bit (purpose unclear); F1–F3 (fullscreen/zoom) gone (see P1).

## Findings — no gameplay impact (noted for completeness)
- CLI reduced (sysarg.c): `-fullscreen`, `-zoom`, `-keys`, `-data`, long `-nosound`,
  `-help` removed; `-s/--speed`, `-n/--nosound`, `--help` added; `-map` kept undocumented.
  Off-by-one fixed for `-submap` in map 1 (`>0` → `>=0`). Both versions share the same
  `-vol` validation bug (it checks `sysarg_args_submap`).
- `sys_printf` now pops a MessageBox; debug/IFDEBUG output removed everywhere.
- Ammo decrement moved after `e_bullet_init`/`e_bomb_init` (e_rick.c) — order irrelevant.
- `ent_actvis` local `y` U16 → S16 (ents.c) — same low-16-bit arithmetic, same S16 result.
- Casts added throughout (MSVC warning hygiene) — checked, all value-preserving.
- `U32` = `unsigned long` vs `unsigned int` (system.h) — same size on Win32.

## Per-file inventory

| pm-baty file | baseline file(s) | non-cosmetic delta |
|---|---|---|
| control.c/h | src/control.c, include/control.h | `control_active` removed — dead in effective baseline (no `ENABLE_FOCUS`). None. |
| dat_ents.c | src/dat_ents.c | **identical** (token-level) |
| dat_maps.c | src/dat_maps.c | **G2** (single connection record; all other data identical) |
| dat_pics.c | src/dat_picsPC+ST.c | PC data dropped; `pic_congrats` identical; **`pic_haf`, `pic_splash` replaced** (P3) |
| dat_screens.c | src/dat_screens.c | `screen_imainrdt` deleted, `screen_imaincdc` text altered (P3); rest identical |
| dat_snd.c | src/dat_snd.c | none (ifdef flattening only) |
| dat_sprites.c | src/dat_spritesPC+ST.c | PC data dropped; **ST data identical** |
| dat_tiles.c | src/dat_tilesPC+ST.c | PC data dropped; **ST data identical** |
| draw.c/h | src/draw.c, include/draw.h | **P2**; `draw_img`/`draw_infos`/`draw_clearStatus` removed; G3 |
| e_bomb.c/h | src/e_bomb.c, include/e_bomb.h | h identical; **G4** (zombie guard) |
| e_bonus.c/h | src/e_bonus.c, include/e_bonus.h | h identical; **G4, G5** |
| e_box.c/h | src/e_box.c, include/e_box.h | h identical; **G4** |
| e_bullet.c/h | src/e_bullet.c, include/e_bullet.h | h identical; **G6** |
| e_rick.c/h | src/e_rick.c, include/e_rick.h | h identical; **G3** (cheat removal); rest none |
| e_sbonus.c/h | src/e_sbonus.c, include/e_sbonus.h | h identical; **G4** |
| e_them.c/h | src/e_them.c, include/e_them.h | h identical; **G4, G7, G8** |
| ents.c/h | src/ents.c, include/ents.h | h: `ENT_XRICK`→`ENT_RICK` rename only; c: G3, P2 (+8 rect offset), rest none |
| game.c/h | src/game.c, include/game.h | **G1, G3, G9, P3 (XRICK state), P4**; focus-pause removal dead in baseline |
| img.h | include/img.h | **identical** |
| maps.c/h | src/maps.c, include/maps.h | h identical; c: none (debug removal, casts) |
| pics.h | include/pics.h | **identical** |
| rects.c/h | src/rects.c, include/rects.h | **identical** |
| resource.h | resource.h | icon define removed — build-only |
| rick.c | src/xrick.c | data.zip setup removed (global) |
| scr_gameover.c | src/scr_gameover.c | **P5** |
| scr_getname.c | src/scr_getname.c | none (GFXPC removal, casts) |
| scr_imain.c | src/scr_imain.c | **P3** |
| scr_imap.c | src/scr_imap.c | none (GFXPC removal, casts) |
| scr_pause.c | src/scr_pause.c | none (GFXPC filter removal) |
| screens.h | include/screens.h | `screen_imainrdt`, `screen_xrick` removed (P3) |
| scroller.c/h | src/scroller.c, include/scroller.h | h identical; c: none (debug, casts) |
| sprites.h | include/sprites.h | none (GFXPC block removal) |
| sysarg.c | src/sysarg.c | CLI reduced; `-submap` fixes + 0x12→0x13 redirect (G2) |
| sysevt.c | src/sysevt.c (+ deleted syskbd.c) | **P6, P1** (Alt+Enter, F7 filter), G3 |
| sysjoy.c | src/sysjoy.c | none per se — but now compiled in (baseline effective build had no joystick) |
| syssnd.c/h | src/syssnd.c, include/syssnd.h | h: ifdef only; c: WAVs via stdio instead of data layer (global) |
| system.c/h | src/system.c, include/system.h | MessageBox errors; syskbd/zoom/palette APIs removed (P1/P6) |
| sysvid.c/h | src/sysvid.c, include/sysvid.h | h identical; c: **P1** rewrite |
| tiles.h | include/tiles.h | none (GFXPC block removal) |
| util.c/h | src/util.c, include/util.h | h identical; c: G3 (cheat2), rest none |
| sdl/*.h (28) | — | excluded: vendored SDL 1.2 headers, third-party |

Baseline files with no pm-baty counterpart: `config.h` (resolved), `data.h/data.c`,
`unzip.h/unzip.c`, `img.c` (data layer — global), `debug.h` (debug macros),
`devtools.h/devtools.c` (dead in baseline), `syskbd.c` (hardcoded into sysevt.c — P6),
`scr_xrick.c` (P3), `xrick.c` (→ `rick.c`), `sounds.*`/`fb.*`/`env.*` etc. exist only in
later master commits, not in #021212.

## Disposition (decided 2026-09-09)
Only **G2** and **G8** are candidates to copy over to the port (`xrick/`, `rework`).
Everything else (G1, G3–G7, G9, P1–P6) is accepted as pm-baty-specific and ignored.

## G8 deep-dive — the wakeup trigger-sound line (relates to the "jewel in Egypt" freeze)

The single line `syssnd_play(WAV_ENTITY[(trigsnd & 0x1F) - base], 1)` in `e_them.c`'s
`wakeup:` hides **three distinct defects**; pm-baty and the rework each fix a different one:

| # | defect | #021212 | pm-baty | rework today |
|---|---|---|---|---|
| a | `snd == 0` means **silent** on the ST (`wTriggerSound` census, `kb/data-structures.md:409`), but xrick plays anyway → index `0 − base` = **−20/−19**, an OOB read of a wild `sound_t*` | broken | **fixed** (G8 guard `(trigsnd&0x1f) != 0`) | **FIXED 2026-09-09** (`e_them.c` wakeup: `(trigsnd & 0x7F) != 0` guard, PLATFORM_ST only — the PC plays nothing here) |
| b | index base: data holds `0x13`–`0x1C`, so base `0x14` sends `snd=0x13` (type 0x3B, map 4) to index **−1** | broken | broken | **fixed** (R3.12a, base `0x13`) |
| c | ST has **ten** tracks `0x13`–`0x1C`; the port ships only `ent0`–`ent8` (nine), so with base `0x13`, `snd=0x1C` (type 0x3C, map 4 only) → `WAV_ENTITY[9]` = NULL — safely swallowed by `syssnd_play`'s NULL guard (present since #021212), but that tenth sound never plays | n/a (b masks it) | n/a (b masks it) | silent no-op |

**Egypt connection (verified in the port's own data):** every entity type ≥ 0x18
dispatches to `e_them_t3_action` (`ents.c` — `k >= 0x18` catch-all), whose `wakeup:`
plays the trigger sound. Egypt (submaps 0x9–0x13) contains **26 placements** of six
t3 types with `snd == 0x00` — types 0x18, 0x19, 0x1a, 0x25, 0x26, 0x49 — and **all 26
carry trigger bits** (mostly `TRIGRICK`), so each of them reaches the unguarded play
with index −19/−20. What gets played is whatever pointer happens to live that far
before `WAV_ENTITY[0]` (only 14 `WAV_*` pointers precede it in `sounds.c`): if that
memory reads as NULL the call is silently rejected, otherwise `syssnd_play` copies
`sound->buf`/`sound->len` from a wild pointer and the audio callback mixes from it —
crash or freeze depending on the garbage. That build/layout dependence is why it was a
long-running, hard-to-pin issue. The "jewel" is one of those six snd==0 triggered
scenery types (visual identification of which type is the jewel: not done).

**What pm-baty is doing:** restoring the original's "trigger sound 0 = silent" rule
that xrick dropped. **Complete fix for the port = pm-baty's guard (a) + rework's base
0x13 (b)**; (c) needs either a tenth WAV (`ent9.wav`) or an accepted silent slot 9.

### What the originals do at wakeup (verified 2026-09-09, instruction level)
- **ST** (`kb/atari_ram.bin`, decoded by hand): both `play_music` call sites guard on
  zero. FIRE site: `0x4D25E move.w (0x44,A0),D0; 0x4D262 tst.w D0; 0x4D264 beq.s
  0x4D272` — zero skips the play. End-of-anim replay site: `0x4D2BC move.w; 0x4D2C0
  bclr #7,D0` (skip if replay bit clear) then `0x4D2C6 tst.w D0; 0x4D2C8 beq.s` (skip
  if zero). Matches the `kb/algo-entities.md:112` transcription; the abbreviated quote
  in `kb/data-structures.md:66` merely elided the `tst/beq`.
- **PC** (`kb/ibmpc_cs.bin` `0x2836`–`0x2860`, decoded by hand; located via the unique
  `step_no = step_no_i` signature `8b 44 22 89 44 24` at `0x285A`): the wakeup body is
  zombie-guard → lethal-bit update → `sproffs=1; step_count=0; step_no=step_no_i` —
  **no sound call at all**. The PC plays nothing at wakeup (consistent with defect #21's
  silent empty-gun path). So the port's `WAV_ENTITY` playback is BigOrno's ST/Amiga
  approximation (his own FIXME admits the table was missing), and **ST is the reference**
  for its semantics: play only when non-zero.
- **Why rework missed (a)**: R3.12a's evidence set was the ten distinct **non-zero**
  `snd` values — it fixed the index arithmetic and never examined `snd == 0`; the ST's
  call-site zero-guard had been recorded as "0 = silent" in the data docs but the elided
  disassembly quote never got cross-checked against the port's unguarded line.
- **(d) side finding, open**: the ST has a *second* play site — replay at end of
  animation when bit 7 of `wTriggerSound` is set (`0x9A` on two entries). The port has
  only the wakeup site and strips bit 7, so the replay semantics are dropped
  entirely (initial trigger sound still correct: `0x9A & 0x7F = 0x1A`). Not part of a/b/c.

### Fix applied to the port (2026-09-09, branch `rework`, uncommitted)
- `xrick/src/e_them.c` wakeup: play is now zero-guarded and ST-masked —
  `if ((trigsnd & 0x7F) != 0) syssnd_play(WAV_ENTITY[(trigsnd & 0x7F) - 0x13], 1)` —
  wrapped `#if defined(PLATFORM_ST) && defined(ENABLE_SOUND)` per the defect-21
  precedent (PC verified silent at wakeup). `& 0x7F` mirrors the ST's `bclr #7`
  (the old `& 0x1F` gave identical results on the real data but was not the ST form).
  Evidence comment at the site cites the ST/PC disassembly. Old FIXME block removed.
- `xrick/src/sounds.c`: comment documenting the accepted-NULL slot 9 (c).
- Verified: WSL `make` builds clean (no new warnings — the `-Wconversion` census
  set is untouched); 3 s headless smoke run boots into Egypt (`-data ../data
  -submap 10`, SDL dummy drivers) without panic; index range with the guard is
  provably [0,9] for every value in `ent_entdata` (census: 0, 0x13–0x1C, 0x9A).
- Status: **(a) fixed, (b) already fixed, (c) accepted** — the OOB/wild-pointer
  defect is gone. **(d) remains open** (deliberate).

## G2 deep-dive — dat_maps.c `map_connect` adjudicated against ST and PC (2026-09-09)

**Verdict: the port's current table is exactly correct (ST-aligned); no change needed.
pm-baty's G2 value is the PC routing — a genuine PC-vs-ST platform difference.**

Full content-level three-way comparison (new — the earlier D2/audit-10d checks compared
per-list *counts* only):

- **ST** (`kb/atari_ram.bin`): walked all 47 `RoomHeader.pTransitions` lists from
  `0x47620` (14-byte headers), decoding all 106 ten-byte `TransitionWaypoint`s.
- **PC** (`kb/ibmpc_ds1.bin`): located the PC's room-header table — **47 × 8-byte
  headers at ds1:`0x84CC`**, `{wTileBankVariant, pTileMap, pTransitions, pPlacements}`
  as LE words (room 0 → tilemap `0x523A` = the known `map_bnums` match, placements
  `0x88EF` = the marks table, found by byte-searching the port's first four
  `map_marks` records). Waypoints are **6-byte** records `{U8 side, U8 row,
  U16 pDestHeader, U16 entryRow}`, list terminator a single `0xff`, and
  `pDest == 0x00FF` = end of level. 106 waypoints, same as ST.
- **Port** (`dat_maps.c`): 47 lists via `map_submaps[].connect`, with the known
  encoding flip `dir: port LEFT=1/RIGHT=0` vs `ST wExitSide 0=left/1=right`
  (game.h `LEFT 0x01, RIGHT 0x00`) — the flip applies uniformly to all 106 records.

**Result: 46/47 lists identical across ST == PC == port on every field.**
The single divergence, room 0x11 (Egypt), waypoint 2 (right edge, row 0x38):

| source | destination | entry row |
|---|---|---|
| ST | room **0x12**, entry 0x18 | bidirectional pair with 0x12's left exit (0,0x18,→0x11,0x38) |
| PC | room **0x13**, entry 0x68 | *not* bidirectional: 0x13's left exit at row 0x68 goes to **0x12** |
| port (021212, current) | room 0x12, entry 0x18 = **ST** | |
| pm-baty | room 0x13, entry 0x68 = **PC** | |

So on the **PC the forward path skips Egypt room 0x12** — but the room is NOT
unreachable: rooms 0x12 and 0x13 keep their full lists on the PC too (identical to ST),
so backtracking left from 0x13 at row 0x68 still enters 0x12. pm-baty's comment
"NOT PLAYABLE - skipped" overstates it. BigOrno's #021212 comment
`/* was {0000,0x38,0x13,0x68} ?? - now OK */` is him replacing the PC routing (his
data source) with the ST/Amiga routing — the captured PC build (ds1) has exactly the
pre-021212 value, corroborating both.

### Fix applied to the port (2026-09-09, branch `rework`, uncommitted)
The user asked for both platforms to be truthful rather than leaving PC as a latent
option. `xrick/src/dat_maps.c`, submap 0x11's second `map_connect` record is now
split on the port's existing `PLATFORM_ST`/`PLATFORM_PC` macro (same pattern already
used for `map_maps` and `map_eflg_c` in this file):
```c
#ifdef PLATFORM_ST
  {0000, 0x38, 0x12, 0x18},
#else /* PLATFORM_PC */
  {0000, 0x38, 0x13, 0x68},
#endif
```
with an evidence comment citing both dumps and this section. `MAP_NBR_CONNECT` (153)
is unaffected — exactly one record either way.

**Verified (WSL):**
- `make PLATFORM=ST` and `make PLATFORM=PC` both build clean, no new warnings.
- A standalone dumper linked against `dat_maps.o` under each `-DPLATFORM_*` printed
  the compiled `map_connect[0x34]` record directly (not just read the source):
  ST → `{0000, 0x38, 0x12, 0x18}`, PC → `{0000, 0x38, 0x13, 0x68}` — surrounding
  records (`0x33`, `0x35`) identical and the list terminator unmoved.
- Both full builds pass a 3 s headless smoke run (`-data ../data -submap 17`,
  SDL dummy drivers) with no panic.

**Disposition:** G2 **closed**. `PLATFORM_ST` (default) plays the ST routing;
`PLATFORM_PC` plays the true PC routing. pm-baty's value is reproduced only under
`PLATFORM_PC`, never silently under the default ST build.

## Progress log
- 2026-09-09: baseline identified & verified (#021212, `28297ba`); normalized diffs for
  all 57 mapped pairs; 16 pairs token-identical; ST sprite/tile/ents data verified
  identical; all remaining diffs hand-reviewed; findings G1–G9, P1–P6 recorded.
  **Review complete.**
