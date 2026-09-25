# demo-solver.md — RD1 game state for the T43 demo solver

Phase 1 of `PLAN.md` T43. It lists every writable variable in the RD1 build and says
which ones a snapshot must hold, which ones carry from one submap to the next, and which
ones the snapshot can ignore.

Scope: **RD1, `PLATFORM_ST` (default build), port tree `xrick/xrick/`, 2026-09-25.**

## 1. Method

1. Every `src/*.c` and `src/rd1/*.c` file (the same set as the `Makefile`, minus the three
   `*PC.c` data files) was compiled in WSL with `-O0 -g -DPLATFORM_ST`, one object per file.
2. `nm -S` on each object, keeping only the writable symbol types `d D b B C`. This finds
   globals, file `static`s and function `static` locals (shown as `name.N`) mechanically.
   **230 symbols.** Read-only (`const`) data is type `r` and is excluded.
3. Each symbol was classified by reading where it is written (grep for assignments, `++/--`,
   compound assignment, `&sym`) and read.
4. Cross-checked against the original's global table (`kb/data-structures.md` "Global
   variables") and, for the random generator, against the original bytes in
   `kb/atari_ram.bin`. **The Ghidra MCP was down this session**, so there was no Ghidra
   cross-check. The byte check stands in for it only where noted.

Limits:
- A write through a pointer alias would not show up in grep. Mitigation: the phase 4 hash
  also covers the class K tables, so any hidden write shows up as a hash mismatch.
- `-O0` keeps all statics. Only the ST build is covered. The PC-only statics
  (`e_them.c:411-431`, `bx cx bl bh cl ch sl sh`) do not exist in it.

## 2. Classes

| Class | Meaning | In snapshot | In hash |
|---|---|---|---|
| **L** | game logic state: changes what happens next | yes | yes |
| **K** | table that is never written (grep), constant in practice | no | yes (guard) |
| **H** | host / presentation / timing / sound: never affects logic | no | no |
| **D** | demo engine state (`src/demo.c`) | handled by phase 3 | no |

"Carried" = survives a submap entry (`INIT_SUBMAP`, `game.c:689`: `map_init()` →
`ent_reset()` + map re-expand). This is what chains the submaps together (T43 D6).

## 3. Class L — the snapshot

| Symbol | File | Bytes | Carried? | Notes |
|---|---|---|---|---|
| `ent_ents` | ents.c | 598 | **Rick (slot 1) only** | `ent_reset` (`ents.c:59`) zeroes `.n` for slot 0 and 2..; respawned from marks by `ent_actvis`. Rick's x/y at entry = where he left the previous submap |
| `map_marks` | dat_maps.c | 2615 | **yes, whole game** | `MAP_MARK_NACT` set when a thing is killed/collected (`e_bonus.c:60/79`, `e_box.c:153/169`, `e_sbonus.c:85`, `e_them.c:95`). Cleared only by `map_resetMarks` (`game.c:845`, game start) |
| `map_map` | maps.c | 1408 | no | re-expanded by `map_expand`; shifted by the scroller |
| `map_eflg` | maps.c | 256 | no | re-expanded by `map_eflg_expand` |
| `map_frow` | maps.c | 1 | yes | set by `map_chain` (`maps.c:208`), scroller, map start |
| `env_lives` `env_bombs` `env_bullets` | env.c | 1 each | yes | bombs/bullets := 6 at a new map (`game.c:652-653`), after a death (`restart()`), from crates (`e_box.c:165-167`) |
| `env_score` | env.c | 4 | yes | |
| `env_map` `env_submap` | env.c | 2 each | yes | |
| `env_trainer` `env_invicible` | env.c | 1 each | yes | cheats; must be FALSE in a demo |
| `env_changeSubmap` | env.c | 1 | — | write-only: written at `env.c:69`, `maps.c:162`, never read |
| `e_rick_state` | e_rick.c | 1 | yes (STOP bit cleared) | `ent_reset` clears `E_RICK_STSTOP` |
| `e_rick_atExit` `e_rick_stop_x` `e_rick_stop_y` | e_rick.c | 1/2/2 | yes | |
| e_rick statics `scrawl trigger offsx ylow offsy seq tumble_seq` | e_rick.c:41-51 | 1–2 each | yes | |
| e_rick statics `save_crawl save_x save_y` | e_rick.c:54-55 | 1/2/2 | yes | death checkpoint (`e_rick_save`) |
| `save_map_row` | game.c:116 | 1 | yes | death checkpoint |
| `game_state` | game.c:117 | 4 | — | is `CTRL_ACTION` at every tick boundary |
| `game_dir` | game.c | 1 | yes | Rick's facing; read by e_rick, e_bullet, maps |
| `e_bomb_lethal` | e_bomb.c | 1 | reset | cleared by `ent_reset` |
| `e_bomb_ticker` `e_bomb_xc` `e_bomb_yc` | e_bomb.c | 1/1/2 | yes (stale) | the bomb entity itself is dropped at entry |
| `e_bullet_offsx` `e_bullet_xc` `e_bullet_yc` | e_bullet.c | 1/2/2 | yes (stale) | same |
| `e_sbonus_bonus` `e_sbonus_counter` `e_sbonus_counting` | e_sbonus.c | 2/1/1 | yes | the escape timer (original `0x4BE18`–`0x4BE1F`) |
| **`st_rnd_a` `st_rnd_b`** | e_them.c:42-43 | 4 each | yes today; **reset per segment under T43 D1/D5** | ST generator |
| `e_them_rndseed` `e_them_rndnbr` | e_them.c:34/39 | 4/2 | — | **PC generator. Unused in the ST build** (`#ifndef PLATFORM_ST`, `e_them.c:406`). `rndseed++` still runs (`game.c:533`) |
| `control_status` `control_last` `control_active` | control.c | 1 each | — | input; the solver sets it each tick |
| `sysarg_args_map` `sysarg_args_submap` | sysarg.c | 4 each | — | start point only (`game.c:817-823`); rewritten at end of game (`game.c:436-437`) |

Total L size: about 5 KB, most of it `map_marks` + `map_map` + `ent_ents`. A snapshot is a
plain copy of these, with no pointers. `ent_rects` / `game_rects` are pointers, but class H.

## 4. Class K — constant in practice (hash guard only)

`ent_entdata ent_mvstep ent_sprseq ent_actf` (dat_ents.c / ents.c),
`map_blocks map_bnums map_connect map_eflg_c map_maps maps_intros map_submaps`
(dat_maps.c), `e_box.c` `sp[]` (`sp.0`, non-const but only read), `demo_scripts` +
`demo_evts_*` (dat_demo.c; replaced by T43 output).

## 5. Class H — excluded

- Render/tiles: `fb urects draw_SCREENRECT draw_STATUSRECT ent_rects game_rects r.0
  prev_h.0 map_tilesBank tiles_bank tiles_filter env_depth env_highlight` (read only by
  paint code: `ents.c:378/397/415/445`, `env.c:170`, `sprites.c`), env HUD strings
  `c.0 s.1 s.2`, all `dat_pics*`/`dat_sprites*`/`dat_tiles*`/`dat_screens`/`IMG_*`.
- Timing: `game_period tm tmx game_waitevt`, scroller `period n.0 n.1` (all 0 / restored
  at every tick boundary: `CTRL_SCROLL` → `SCROLL_UP/DOWN` runs to `SCROLL_DONE` → `CTRL_ACTION`, `game.c:605-731`).
- Sound: `stopped.0` (`e_rick.c:639`, only under `ENABLE_SOUND`, gates a sound effect),
  `WAV_*`, all of `syssnd.c`.
- Screens (`scr_*.c`), `game_hscores`, `sysvid/sysevt/syskbd/system` statics, the other
  `sysarg_args_*`.

## 6. Class D — demo engine (`src/demo.c`)

`set recording script tick cursor mask segment last drove pool pool_used pool_full
rec_open rec_first rec_nbr rec_len` (`demo.c:46-68`). Headless play does not use them;
phase 3 records the solver's output through the same `demoevt_t` format.

## 7. Findings

**F1 — the ST port did not advance the random generator once per frame.**
✅ **FIXED 2026-09-25**, port commit `7b601ba`: the generator is `e_them_rndstep()`, now also
called once per `CTRL_ACTION`, after `ent_action()`. Trace check: tick n+1's `rng a` equals
tick n's `rng b`. Original finding:
The original calls `update_prng` (`0x49596`) from two places. Both were checked in
`kb/atari_ram.bin`: `bsr` `61 00 b8 5a` at `0x4DD3A` (the render path of the main loop,
`kb/algo-system.md` "RENDER") and `61 00 bd f6` at `0x4D79E` (`enemy_ai_update`). Both
resolve to `0x49596`. The port advances `st_rnd_a/b` only at `e_them.c:669-674`, which is
the per-decision call. The per-frame call is missing. So enemy random turns in the ST port
differ from the original. `kb/xrick/xref.md:240-245` describes the two callers but does not
flag the gap. Consequence for T43: once F1 is fixed, every solved script is invalid.
**Settle F1 before phase 9.** Not yet read: exactly which frames reach the RENDER path
(scroll and death frames branch back to `MAIN_LOOP` in `algo-system.md`).

**F2 — the D5 seed values match the original.** `seed_prng_state` (`0x49574`,
`kb/algo-system.md:544`) produces `0x121901F9/0x160566F9`. The RAM dump holds exactly
`12 19 01 f9 16 05 66 f9` at `0x495C0`. These are also the port's static initialisers.

**F3 — the carried state is larger than ammo + score.** On top of `env_*`, Rick's entity,
facing, `e_rick` statics, the escape timer and above all `map_marks` (what has been killed
or collected so far) all flow into the next submap. Solving in order (T43 D6) covers all of
it, because the snapshot is taken at the real entry state.

**F5 — the 4 human scripts no longer play through.** Since F1, enemies turn differently,
and headless and SDL both show Rick dying in submap 0x02 until game over at step 1947.
Expected: T43 D2 replaces the scripts.

**F4 — the PC generator still runs in the ST build.** `e_them_rndseed++` (`game.c:533`) runs
in the ST build but nothing reads it there. It does no harm. It is listed so D1's reset does
not have to touch it on ST.

## 8. Tools (port tree `xrick/xrick/xrick/`)

**Segment reseed (T43 phase 2, commit `7be9851`).** `demoset_t.enter` is called by
`demo_enterSegment` on every segment entry while a script plays or records, never in
normal play. RD1 passes `e_them_rndreset()`: ST `0x121901F9/0x160566F9`, PC `0/0`.

**`-trace <file>`** (both builds). One line per logic step and one per segment entry:

    E <step> <submap> <rng a> <rng b>
    T <step> <submap> <ctrl> <rng a> <rng b> <lives> <bombs> <bullets> <score> <rick state> <n:x,y,sprite> x12

`<step>` counts `CTRL_ACTION` passes since the game started. `<ctrl>` is the
`CONTROL_*` mask that step used.

**`xrick-core`** (T43 phase 3, `make core`, WSL). The RD1 game logic compiled unchanged with
`-DHEADLESS`, linked with `src/headless/hl_sys.c` (host stubs: no video, sound, input or
timing) and `src/headless/xrick_core.c` (CLI). API in `include/rd1/game.h`:
`game_hlStart()`, `game_hlStep(ctrl)` → `GAME_HL_STEP / OVER / END`, `game_hlSteps()`.
One step = frames run until one `CTRL_ACTION` has run and its frame is painted. Scroll,
fade and restart frames are included; the map intro is skipped (it writes no game state,
checked by grep). `fb` is still drawn in memory.

    xrick-core [-demo] [-trace <file>] [-steps <n>] [-scramble <n>]

Checks run 2026-09-25 (ST build):
- **Headless = SDL.** `xrick -demo -trace` with SDL dummy drivers vs `xrick-core -demo -trace`:
  the traces are byte-identical over the full demo run: 1947 steps + 8 segment entries =
  1955 lines, up to the game over in submap 0x02 (F5). Port commit `0ede083`.
- **Reseed.** `xrick-core -demo -scramble 12345` gives a byte-identical trace to the
  unscrambled run over all 1947 steps, including 5 restarts after deaths. Without `-demo`
  the scrambled generator is kept, as it is in normal play.
- **Speed.** 100 000 steps in 0.29 s (Rick idle in submap 0x00), about 350 000 steps/s.
