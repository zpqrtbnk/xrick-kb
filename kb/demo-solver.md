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
| `e_rick_exitDir` | e_rick.c | 1 | yes | the edge rick left by; `map_chain` matches it (since F7, master `cf9b4f1`) |
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

**Snapshot / restore / hash (T43 phase 4, solver only, commit `2c51de6`).**
`src/headless/hl_state.[ch]`: `hl_stateSave/Load` copy the class L regions of §3
(4960 bytes; `xrick-core -list` prints them), `hl_stateHash` is FNV-1a 64 over them plus
the class K tables. File statics come from `game_hlRegions`, `e_rick_hlRegions` and
`e_them_hlRegions`, all `#ifdef HEADLESS`.
- **Fades are skipped headless** (`game.c`, `#ifdef HEADLESS`). The `fb_fadeIn/Out`
  counters are function statics in `fb.c`, which the snapshot cannot hold. A fade left
  half-done in one timeline changed the frame on which the next one ended, so
  `game_state` differed at a step boundary: 0x18 `GAMEOVER` against 0x09
  `FADEOUT__GAMEOVER`. That was the only region that differed. Fades only set the gamma. A
  game over now stays in `FADEOUT__GAMEOVER`.
- **Check (`xrick-core -fuzz`)**, per round: snapshot S; random inputs I (64 steps, hash
  each step); other inputs J (64 steps, deaths and game overs included); restore S; hash
  must equal S's; replay I; every hash must match. 47 submaps × 3 seeds × 40 rounds =
  **5600 restores, 0 mismatches.** The fuzz reaches every submap 0x00–0x2E. Only failures:
  F6 and F7, both reproduced without any restore.
- **Speed:** about 40 000 steps/s with a hash every step; save 0.3 µs, restore 0.8 µs.
- `-log <file>` writes the inputs a plain game plays to the end of a round, with byte
  0xFF = new game in the same process. `-inputs <file>` replays one.

## 9. State dump (T43 phase 5, solver only, commit `e4f8db9`)

`xrick-core ... -dump` prints one JSON object on stdout (`src/headless/hl_dump.c`):

| Key | Content |
|---|---|
| `step`, `status` | logic steps since the game started; `running` / `game_over` / `game_completed` |
| `map`, `submap`, `frow` | `env_map`, `env_submap`, `map_frow` (submap tile row at `map_map` row 0) |
| `lives bombs bullets score` | `env_*` |
| `timer` | escape timer: `e_sbonus_counting/counter/bonus` |
| `rick` | x, y, w, h, `dir`, decoded `e_rick_state`, `at_exit` |
| `entities` | live slots except Rick: `n`, `kind` (from `n & 0x7f`, as `ent_action` dispatches it), `lethal` (`n & 0x80`), box, sprite, mark, decoded flags, `trigger` box `[x0,y0,x1,y1)` (`u_trigbox`) when a TRIG flag is set |
| `marks` | this submap's placements: submap tile `row`, `x`, kind, `done` (`MAP_MARK_NACT`) |
| `exits` | `map_chain`'s connectors: `side`, `rows` = the `map_map` tile rows where `y >> 3` must lie (they move with `frow`), `to` = submap or `next_map` |
| `tiles` | `map_map` rows 0x00–0x27, one class character per tile (`tiles_legend`); screen = rows 0x08–0x1F |

Coordinates are pixels in `map_map` space; tile = (x >> 3, y >> 3). The exit test is
`x < 0` (left) or `x >= 0xE8` (right) with `dir == game_dir`.
Checked on the built-in demo: each entity's y from its mark matches (mark 8: row 45,
frow 16 → y 235); at step 942 Rick (row 17, facing right, x 230) is inside the right
exit's window [16, 18], and the trace enters submap 2 at step 943.

## 10. Port defects found by the fuzz (reachable in normal play)

Reproducers in `kb/demo-solver/` (one `CONTROL_*` byte per step, 0xFF = new game in the
same process): `xrick-core -submap <n> -inputs <file>`. Both happened with no snapshot
involved, so they were in the game logic that ships on `master`.
✅ **Both FIXED 2026-09-25, master `cf9b4f1`**, causes read in Ghidra (ST `atari_ram.bin`,
PC `ibmpc_cs.bin`).

- **F6 — segfault.** `f6_submap40.in` (submap 0x27). ASan: out-of-bounds read of `map_map`
  in `u_envtest` (`util.c:151`), called from `e_them_t2_action2` (`e_them.c:698`). UBSan
  also flagged `sprites.c:228` (index 32 of a `U8[32]`, not investigated).
  **Cause:** `x` in `e_them_t2_action2` became `S16` (R3.1), so `x < 0xe8` let a type-2
  enemy walk to x < 0. At x = −6 the probe's column `(x+4) >> 3` as U16 is 0x1FFF.
  - PC: the x move has a left bound (0x2AD3 `add al,[si+2] / jc`, 0x2AE8 `cmp al,0xe8 /
    jnc`), which the port lost. Restored.
  - ST: no bound (0x4D76C); the probe (0x4DA40) reads `0x4A17E + col + row*32` with no
    check. Columns 0x1FFF–0x2001 land at `0x4C17D + row*32 + 0..2`, inside
    `player_controller` (0x4C046–0x4C7E3). The only self-modifying code is at 0x45636, so
    the bytes are constant. `util.c` `st_offgrid` holds them: 48 rows × 3, from
    `atari_ram.bin`, rows 0x00 and 0x2F re-read in Ghidra. `render_sprites` despawns at
    X < −8 (0x4B098) or > 0xF0 (0x4B0A6) via 0x4AC3E (type := 0, placement untouched).
    Now done in `ent_action` for type-2 `e_them`. Result on the reproducer: the enemy walks
    2, 0, −2, −4, the −6 probe comes back blocked, and it turns back.
- **F7 — `sys_panic("(map_chain) can not find connector")`.** `f7_submap12.in`,
  `f7_submap42.in`, `f7_submap5.in`: Rick at x=2 after leaving by the right edge while
  climbing or jumping (`e_rick_state` 0x04 / 0x0C).
  **Cause:** `map_chain` matched `game_dir` (Rick's facing), which the climbing moves never
  update. Both originals match the edge Rick left by:
  - PC `[0x7D77]`: written only by the exit stubs (0x19B4 = 0 left, 0x19C4 = 1 right; the
    port had them commented out as `6dbd`), read only by the search (0x0D99). The search
    loop (0x0E31) has no sentinel test.
  - ST: side from X (0x49A3E–0x49A50). The sentinel (0x49A56) goes to 0x49B28:
    reposition, same room again (0x499C2).
  Fix: `e_rick_exitDir`, set at the four exits. ST: no match → same submap again. PC: the
  panic stays, since the original has no defined behaviour there. The three reproducers
  now leave through a real connector: 0x0A→0x0B, 0x28→0x29, 0x03→0x04.

Checks after the fix: all four reproducers play to the end; 47 submaps × 3 seeds × 40
rounds = 5640 restores and 5 all-submap runs, with 0 crashes and 0 mismatches; built-in demo
trace byte-identical to before; SDL build warnings unchanged (230); PC build compiles.

**Follow-ups, not done:**
- **F8** — the ST's central X despawn (< −8, > 0xF0) is applied to type-2 `e_them` only.
  Other kinds keep the port's own bounds, e.g. scripted traps restore `xsave` (`e_them.c`
  ~897) where the ST would despawn off-screen. The ST's type-2 move also has no right bound;
  the port keeps the PC's 0xE8. Unexamined.
- **F9** (solver tool only) — `-trace` with an `-inputs` file that starts new games reopens
  the trace without closing it, so the file gets NUL bytes.
- **F10 — the ST jumps off a ladder top from a crouch; the port climbs.** Found 2026-09-27
  on submap 0x09: the first stair step above the ladder top (row 72, cols 25-26) is 16 px up,
  the ladder-exit hop peaks 13 px (port −0x300), so the port cannot pass. ST `0x4C2FE`:
  ladder bit set → `0x4C318 tst.b crouching (0x4BF14); bne 0x4C370` → on_ground →
  `0x4C38C` ACTION: crouching = DOWN|ceiling, then UP → `move.w #-0x580` (full jump).
  So DOWN+LEFT/RIGHT (crouch; plain DOWN grabs the ladder) then UP jumps. The PC has no
  such path: stand-up at `0x1596–0x15A3` precedes `0x1808 test dh,8 / test cl,2` → climb,
  exactly as the port (`e_rick.c` firing_not). Checked: ST attrs of the ladder top here
  are `0x82` (fc/fd), same as the port; port test from state s25 (DOWN|LEFT ×2, UP|LEFT)
  → climb. ✅ **Fixed 2026-09-27, master `69894f3`** (`PLATFORM_ST` only: UP climbs only if
  `!scrawl`, last frame's crawl = the ST's crouching flag), merged into `solver`. Checked:
  crouch-then-UP from s25 now jumps; ST and PC warning counts unchanged (230/231); the
  map-1 export (s18, 4701 steps) is byte-identical after the fix. The solver finds it
  unaided (DOWN|LEFT then UP|LEFT are both in its mask set).
- **F11 — the ST re-arms the gun every frame unless UP+FIRE are held; the port did not.**
  Found 2026-09-27 on 0x0E (a second shot was needed: bridge trigger + falling enemy).
  ST `0x4C094–0x4C0A6`: `andi.b #0x81 / cmp.b #0x81 / beq / clr.b shoot_debounce (0x4BF15)`,
  every frame after the death check. All refs to 0x4BF15: 4BF4E (reset_player_state),
  4C0A6, 4C4DC/4C4E8 (FIRE+UP test/set), 4C8FA (pose). PC trigger 0x7D86: only 0x175C read,
  0x1766 set, 0x17C3 clear (FIRE without UP) = the port. ✅ **Fixed 2026-09-27, master
  `4ad51b5`** (`PLATFORM_ST` only), merged into `solver`. Not done: the reset_player_state
  clear (only matters with UP+FIRE held through a respawn). Impact on the timeline: map 1
  (s18) replays identically; from 0x0A on a held FIRE+UP fired one more bullet, so
  0x0A–0x0D were re-solved (s44 refreshed from replay; new chain s72 → …).
- **F12 — the ST moves Rick diagonally in ONE probe; the port moves Y, then X.** Found
  2026-09-27 on 0x12: under the one-way platform (row 30, cols 8–23) the only way down is to
  drop off the left end and steer right past the spike tiles (row 35, cols 4–7). In the port
  Rick dies at x=58 (needs 60): the frame that reaches row 35 applies Y at the old X, finds
  lethal, zombies, and only then would X move. ST `player_controller` (disassembly read):
  `0x4C0F6–0x4C124` new X in D2 (±2), `0x4C12A move D2,D6 / move D3,D7 / bsr 0x4CD70` probes
  **new X and new Y together**; free → `0x4C134–0x4C142` store both, gravity, LADDER_CHECK;
  blocked → `0x4C168` retry Y alone at the old X. Lethal is then read from the flags of the
  probe that succeeded. The port (`e_rick.c` e_rick_action2) does the vertical envtest at
  (old x, new y) with its own lethal/zombie, then the horizontal envtest at (new x, y).
  ✅ **Fixed 2026-09-27, master `9dd478d`** (`PLATFORM_ST` only; the PC's separate probes
  0x1596/0x15AB then 0x166D/0x1673 are what the port had), merged into `solver` (`a650de1`).
  Warnings unchanged (ST 230, PC 231). Checked: the 0x12 drop now lands (x=60 on the row-35
  frame, y 203 on the floor). A second visible effect, also the ST's: while rising, the
  diagonal probe uses the rising mask (no WAYUP), so Rick now moves sideways through one-way
  tiles on the way up, where the old separate horizontal probe was blocked by them
  (0x02: x 132 held for 3 frames before, 134/136/138 now).
  **Validation of the solved timeline (s1 → s117, 0x00–0x11), each saved leg replayed under
  F12 from its parent's stored snapshot, compared with its stored result:**
  still valid 0x00, 0x01, 0x04, 0x05, 0x08, 0x0C, 0x0D, 0x0E, 0x0F; broken 0x02 (s3→s4,
  life lost), 0x03 (s4→s7), 0x06 (s10→s11), 0x07 (s11→s12), 0x09 (s18→s19, s20→s21,
  s21→s23, s36→s37), 0x0A (s72→s73), 0x0B (s73→s74), 0x10 (s106→s108 x+2, s109→s110 misses
  the bullet crate), 0x11 (s116→s117). A full replay from a new game dies in 0x02 and is
  game over by 0x03. So the chain must be re-solved from 0x02; the legs still valid can be
  reused only if their entry state (position, lives, bombs, bullets) is reproduced.
  **Re-solved 2026-09-27 with MCP `repair`** (old chain s4 … s117): new chain ends at **s204**,
  0x12 tick 0, lives 6, bombs 5, bullets 5 — the old end exactly, score +50, 12268 steps (was
  11842). Legs: most replayed as they were (0x04, 0x05, 0x08, 0x0C–0x0F whole, and the hand
  sequences of 0x09/0x0B/0x10/0x11); re-solved from part of the old leg: 0x02, 0x03, 0x06, 0x07,
  several 0x09 legs, 0x0A exit, 0x0B approach, two 0x10 crate legs, 0x11 exit. One leg by hand:
  0x09 ladder top — the old run had shot the enemy_2 of the pillar room, the re-solve had not,
  and it followed Rick up the ladder; shot at s148 (s150), then solved to the ladder top (s151).
  A first run showed `repair` letting re-solved legs spend ammo (a bomb in 0x09, then 0x0A
  short); fixed (`6f69bf1`): same or more bombs/bullets, min_bombs = the old end's. Checked:
  `validate` legs and timeline, 78/78.

## 11. Solver (T43 phase 6, solver only, commit `bb999b1`)

`src/headless/hl_solve.[ch]`; CLI `xrick-core -solve | -chain <n>` with `-beam` (128),
`-maxsteps` (3000), `-to`, `-out <file>` (one control mask per step, replayed by
`xrick-core -reseed -inputs`), `-save`/`-load` (snapshot files, same build only),
`-stuck <file>` (the best state of a failed search), `-noclosures`, `-v` (up to 3).

**Setting.** The generator is reseeded at every segment entry (`game_hlReseed`), as a
demo plays (D1). A submap starts at its tick 0 (`game_hlSettle` after a new game, or the
step after an exit). Every `game_hlStep` is exactly one `CTRL_ACTION`: headless
fade-in now ends the frame, so a new map's tick 0 is its own step.

**Goal.** `hl_solveTarget`: the connector to the highest submap above this one, else
the next map. Not "next map first": submap 0x00 has a next-map connector on its left
edge at Rick's start rows. Pruned: Rick zombie/dead, fewer lives, game over, any other
submap.

**Search** (what worked, in the order it was needed):
- *Time-synchronous beam.* States go into buckets by step count. Each bucket keeps its
  `beam` best, at most 4 per Rick tile (a plain beam collapsed onto one spot). Waiting and
  56-step dynamite programs only compete with states of the same age. A plain beam ranked
  by steps + distance always dropped them, and could not wait for a bomb or a trap.
- *Programs.* One mask held 2/4/8 steps (FIRE+DOWN excluded). Dynamite: drop, run
  left/right 12 or 24 steps, stand until 56 steps (fuse 34 + explosion 20, lethal 7).
  Skipped while a bomb ticks or none are left.
- *Distance.* Dijkstra backwards from the exit rows, over:
  - the submap's block rows plus one `map_map` height (0x28 rows): `map_expand` reads past
    the submap's own blocks, and submap 0x01 is left along rows beyond its 0x6c own rows;
  - Rick's footprint, anchor `((x+4)>>3, y>>3)`, 2 wide × 3 tall, or 2 tall where he
    crawls (the 0x03 tunnel);
  - one-way floors crossed upwards only, except at ladder tops;
  - a climb up costing 3 without a ladder.
- *Ranking.* f = 4 × distance + 2 × control changes − 8 × placements done
  (`MAP_MARK_NACT`) − 32 × traps defused (spawned lethal, no longer lethal) + 64 while a
  wall entity stands (slot 0, `ENT_FLG_STOPRICK`).
- *Death map (closures).* After a failed search, tiles with ≥ 32 deaths and ≥ 4 deaths
  per surviving visit are closed and the search restarts, at most 8 times. The earlier
  50% rule also closed an enemy's beat on 0x01's only way on. Undone if no visited tile
  can reach the exit any more.
- *Stuck* = no distance gain for 400 steps.
- *Polish:* short input runs take a neighbour's mask while the replay still reaches the
  exit.

**Pilot result (submaps 0x00–0x03, one run, 3.5 min):**

| Submap | Steps | Input runs | Search | Notes |
|---|---|---|---|---|
| 0x00 | 287 | 7 | 18 s | |
| 0x01 | 440 | 22 | 97 s | closure of the trap shaft needed; human demo took 640 steps |
| 0x02 | 138 | 5 | 15 s | |
| 0x03 | 768 | 32 | 77 s | two dynamite puzzles: stone head (wall), two corridor traps |

1633 steps, 6 lives kept, score 5637. `xrick-core -reseed -inputs` of the output, in a
fresh process, enters 0x01/0x02/0x03/0x04 at steps 287/727/865/1633. Not yet played
through the SDL build's demo engine (phase 10 export).

**What the solver is not told:** nothing map-specific. Two things were found by
experiment from `-stuck` snapshots, on submap 0x03:
- Rick cannot fire while crawling, so the stone head must be bombed standing, from the
  right.
- The corridor traps each need their own bomb, and lose `ENT_LETHAL` instead of
  disappearing.

**Beyond the pilot (same build, from 0x04's start snapshot, 2026-09-26):** 0x04 → 488
steps (16 runs, 57 s) and 0x05 → 316 steps (12 runs, 50 s) solved. **0x06 not found**
after 507 s (every restart used). Not examined yet.

### 11.1 Session 2026-09-26 (port commits `ff47a40` … `501fdaa`)

**End to end, pilot:** `xrick-core -reseed -inputs <solution> -record <file>` makes the demo
engine write `dat_demo.c` (record mode reseeds on segment entry, as the solver assumes).
The SDL build with that file, `xrick -demo -trace`, gives a byte-identical trace to the
headless replay over all of 0x00–0x03: 1637 lines, submaps entered at steps 287 / 727 /
865 / 1633. Files: `kb/demo-solver/pilot_dat_demo.c`, `pilot_inputs.bin`.

**Solver changes, each forced by a submap:**
- *Jumps in the field* (0x06): states (anchor, k), k = rows risen since standing or on a
  ladder, at most 4 (offsy −0x580, +0x80 a step: 33 px). 3 made 0x06 unreachable.
- *Walls in the field* (0x03, 0x06): one field per subset of standing wall placements
  (`ENT_FLG_STOPRICK`). Entering a standing wall costs 16 tiles, once. A wall stands while
  out of view (ONCE traps respawn — ST too, `scripted_trap_update` PATH_END) or while in
  slot 0 at its spawn point. Replaced a slot-0 penalty that kept the beam away from walls.
- *Dynamite programs* start with 2 idle steps: Rick cannot fire the step after crawling
  (`scrawl`). They end at 36 steps (before the blast; 0x07) or 58 (after it; 0x03).
- *0x07's exit wall slides* along its row at 8 px/step when blown. Found from a `-stuck`
  state: retreat 18–24 steps, jump at step 36–39. Bomb-in-play states get a quarter of the
  beam and are ranked among themselves by clearance from the bomb.
- *Retries escalate:* first the dead end (3×3 around the stuck tile) is closed, deadly
  tiles from the second failure on.
- *Tried and dropped:* drop-and-escape programs; a value per bomb held (both broke 0x06
  / 0x07).
- `-distance`, `-record`, `-save` after `-inputs`, jitter count (runs < 4 steps).

**Results.** From start snapshots: 0x03 610, 0x06 947, 0x07 712 steps. One chain from a
new game: 0x00–0x05 in 2268 steps, then 0x06 fails with **0 bombs** left (0x03's solution
used more dynamite than before).

**Chain backtracking** (`hl_solveMinBombs`, commits `175dc03`, `501fdaa`): when submap s
fails, s−1 is re-solved keeping more bombs.
- First version reset later requirements and cycled (0x03–0x06 four times, over an hour).
  Fixed; the fixed version has not been re-run.
- Open: a failed search costs 2–25 min, so backtracking is slow. Whether 0x04/0x05 can
  pass a bomb through is unknown: 0x04 failed keeping 1 in 450 s.

## 12. MCP server (T43 phase 7, solver only, port commit `d5dcdce`)

`src/headless/mcp_server.py`: MCP over stdio (newline JSON-RPC, no dependencies), started
by Claude Code through `.mcp.json` (`wsl -e python3 …/mcp_server.py`). Each call runs
`xrick-core` (`make core` first) on snapshot files in `xrick/xrick/xrick/build.mcp/`
(ignored by git). Env: `XRICK_CORE`, `XRICK_MCP_WORK`.

**States.** Every tool works on a state: a snapshot at a step boundary, with its parent
and the inputs that led there. The timeline of a state (all inputs from the new game)
is what `export` turns into `dat_demo.c`.

| Tool | What it does |
|---|---|
| `new_game` | new game settled at the first submap's tick 0 (`-chain 0 -save`); optional `submap` (not exportable) |
| `observe` | the `-dump` JSON plus the solver's `distance` line; `full=false` drops tiles and marks |
| `step` | play `[[controls, steps], …]` (`"RIGHT"`, `"UP\|LEFT"`, `"FIRE\|DOWN"`, `"NONE"`) → new state |
| `solve` | the solver to the forward exit, or to `waypoint` `[row, col]`; hints `min_bombs`, `forbid` `[[r0,c0,r1,c1],…]`, `beam`, `max_steps`, `no_closures` → new state |
| `list_states` | id, parent, steps, note |
| `export` | the timeline → `dat_demo.c` via the demo recorder (`-reseed -inputs … -record`) |

**Coordinates** for waypoints and forbid are anchors in submap tiles: row = `(y>>3)+frow`,
col = `(x+4)>>3`, the same as `rick.anchor` in the dump. A tile row `i` of the dump's
`tiles` is submap row `frow + i`.

**Checked** (scripted session): new game → 20 steps right → `solve` to 0x01 (267 steps)
→ `export` gives a `dat_demo.c` reaching 0x01 at step 287. Also launched from Windows
(`wsl -e python3 …`). Claude Code picks up the new server after a restart or `/mcp`.

**Added 2026-09-27 (port commit `f8486bb`)** — after F12 broke half the timeline:
- `trace(state, inputs, every, max_lines, save)`: one line per step (or every n, doubled until
  ≤ max_lines): counters, rick `[x, y, state, anchor row, anchor col]`, entities
  `[slot, kind, x, y, lethal]`. Backed by `xrick-core -inputs … -steplog <file> [-every n]`.
- `validate(state, mode)`: `legs` replays each leg from its parent's stored snapshot and compares
  its end (submap, lives, bombs, bullets, rick x/y) with the stored one; `timeline` replays from
  the new game and stops at the first difference.
- `repair(old, from, onto, backoff, max_legs, beam, timeout)`: ports the legs after `from` up to
  `old` onto `onto`. A leg that still does its job (same submap and lives; inside a submap, rick
  within one tile of the old end) is kept; otherwise re-solved to the same goal (the next submap
  with `min_bombs` = the old end's bombs, or the old end tile as a waypoint), first from `backoff`
  (30) steps before its first life loss, then from the leg's start; a solver leg reuses its hints.
- `observe`: every scripted trap carries `script` — `steps` `[frames, dx, dy]` from
  `ent_entdata[].sni`, `awake`, and `at` `[step, frames into it]` when awake.
- `solve` stores its hints (`waypoint`, `min_bombs`, …) in the state's metadata, for `repair`.
Checked: `validate` reproduces the F12 map-1 result; `repair` of s3→s4 kept 46 of 138 steps and
re-solved the rest to the old end (0x03, lives 6, bombs 6, bullets 5, x 2 y 133).

## 13. Ammo: restock points and ammo-only obstacles (phase 9)

A map exit refills bombs and bullets to 6 (`game.c`, end of submap chain). Crates refill
their kind to 6. Maps (from the `next_map` exits): 1 = 0x00–0x08, 2 = 0x09–0x13,
3 = 0x14–0x25, 4 = 0x26–0x2E. Generated 2026-09-27 from `xrick-core -submap n -dump` marks
(`kind` crate_*; traps whose only trigger is bomb / bullet). "Bomb-only" does not mean
on the route: 0x09 (106) and 0x0B (134) were; the others are not checked yet.

| submap | crates (row) | bomb-only traps | bullet-only traps |
|---|---|---|---|
| 0x03 | bullets r25 | 35 36 37 | |
| 0x04 | bombs r69 | 51 | |
| 0x06 | bombs r33, bullets r53 | 58 | |
| 0x07 | bullets r45 | 72 | |
| 0x08 | | 98 99 | |
| 0x09 | | 106 | |
| 0x0B | | 134 | |
| 0x0D | bullets r41 | | |
| 0x0E | bombs r81 | | 166 169 174 |
| 0x0F | bullets r25 | 184 187 | |
| 0x10 | bullets r53, bombs r81 | 193 | |
| 0x12 | bombs r27 | | |
| 0x13 | | 229 231 | |
| 0x14 | | 246 247 | |
| 0x15 | bombs r37, bullets r37 | | |
| 0x17 | | 273–277 | |
| 0x1A | bullets r65, bombs r73 | | |
| 0x1C | bombs r85 | 317 318 320 | |
| 0x1E | | 336 337 | |
| 0x20 | bullets r43, bullets r81 | | |
| 0x22 | bullets r85 | | |
| 0x23 | bombs r57 | | |
| 0x25 | bullets r21 | | |
| 0x29 | bullets r26, bombs r38 | | |
| 0x2A | | 468 | |
| 0x2D | bombs r109 | | |
| 0x2E | | 516–521 | |

Submaps not listed have neither. Use: plan per map which crates to take (waypoint to the
crate, `min_bombs` on the legs that must not spend), since the solver only values bullets
weakly (BULLET_VALUE 2) and bombs not at all. Crate pockets can be traps (0x0D: an enemy
patrols the room above; kill it first).

## 14. Map 3 castle: the exit wiring (phase 9)

`map_connect` read from the port's `dat_maps.c` (probe program, 2026-09-27; dir 1 = LEFT,
0 = RIGHT; "out" = the connector's rowout, "in" = rowin in the target). Rooms 0x15 and 0x16
are identical: an upper corridor (rows 20–27) and a lower one (rows 32–39), not connected
inside the room. The forward route through them:

| from | exit | to |
|---|---|---|
| 0x14 | right, row 64 | 0x15 row 24 (upper) |
| 0x15 upper | left → 0x14 · right → 0x16 row 24 (upper) | |
| 0x15 lower | left → 0x16 row 24 (upper) · right → 0x16 row 32 (lower) | |
| 0x16 upper | left → 0x15 row 24 (upper) · **right → 0x15 row 32 (lower)** | |
| 0x16 lower | left → 0x15 row 32 · **right → 0x17 row 32** | |

So: 0x15 upper → R → 0x16 upper → R → 0x15 lower → R → 0x16 lower → R → 0x17. The solver's
default target (the highest forward submap) cannot see this; steer it with `solve(to=…)` plus a
waypoint at the corridor end on the wanted side (`forbid` does not stop an exit through the
forbidden edge). Further loops ahead: 0x19 (L row 24 → 0x18, R row 24 → 0x18 row 32, R row 32 →
0x1A), 0x1A (R row 80 → 0x19), 0x1B (both row-24 exits → 0x1B itself), 0x1C (R row 80 → 0x19),
0x1D (R row 24 → itself), 0x1E (R row 24 → 0x17). Full table: rerun the probe over 0x14–0x26.
