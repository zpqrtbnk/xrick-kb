# demo-solver.md — RD2 game state and tools for the T47 demo solver

`PLAN.md` T47. Port branch `solver` only (MEMORY.md §11), except `rd2_frame_step` (master).
RD1's counterpart: `kb/demo-solver.md`.

## 1. Headless core (`xrick2-core`, phase 3)

`make core2` → `build/core2/xrick2-core`. Sources: `src/rd2/*.c` minus `rd2_sys.c`, `rd2_snd.c`,
`rd2_demo.c`, `dat_rd2_sndh_engine.c`; plus `src/headless/rd2/`.

- `hl2_game.c`: `rd2_game_run` from PICKED on, one `game_main` frame per `hl2_step(joy)`. The frame
  is the game's own `rd2_frame_step` (master `2ddedc8`); boot, LOAD and MAPDONE are copied from
  `rd2_game_run` without its host hooks. New game = the `-map N` route (`[$17994]` := N).
  `hl2_step` writes the joystick byte `[$1a4fb]` first, as `rd2_demo_frame` / `RD2_JOYSEQ` do.
- `hl2_sys.c`: the VBL waits leave what they leave at a frame head: `$19216` flips (`$19234`),
  `$191e6` clears `[$19232]`. Sound silent; `[$1aa08]` is only read by the title and game over.
  Map 5's load (`rd2_sys_hang_red`) returns `HL2_HANG`.
- Checked 2026-10-01: SDL `-game 2 -map N` + `RD2_JOYSEQ` vs `xrick2-core -map N -inputs`, RAM traces
  (`RD2_TRACE` windows) byte-identical on maps 1–4, 6896 frames, to game over. 106 000 frames/s
  with rendering.

## 2. State (phases 1, 4)

`make audit2` builds `xrick2-audit` with `-DHL2_WATCH`: `rd2_wb`/`rd2_ww` mark every byte written
(`rd2_mem.h`). Every RAM write during play goes through them (the only `memcpy`s are the map
loader's and `rd2_mem_init`'s). `xrick2-audit -audit 200000`: random play on each map, marks reset
after the boot. Written ranges, then widened where random play cannot reach every path
(`hl2_regions.h`):

| range | what |
|---|---|
| `$10b5c`, `$115dc`–`$115e2`, `$1239c`–`$123a0` | S latch; shot hit, map done; map playing / loaded |
| `$12e00`–`$17800` | game variables, the 17-record chain, HUD, score (whole block, audit saw parts) |
| `$17896`, `$17990`–`$17996`, `$18180`–`$18186` | score add; game length, picker rows/choice; scene runner |
| `$184a8`, `$18562`–`$1856a`, `$18da8` | ?, PRNG, animated tiles |
| `$18ed8`–`$18ee6`, `$19232`, `$1a4fa`–`$1a4fd`, `$1a5ca`–`$1a5d0` | frame rate, screen/palette pointers; VBL counter; joysticks/key; IKBD flags, id remap |
| `$54c00`–`$56400` | submap headers, trigger and spawn tables (runtime bits), every submap |
| `$65300`–`$65800` | tile window |
| `$65800`–`$80000` | **render**: tile mask, background bitmap, screens |

Everything else is the pristine program or the map loader's copies (`rd2_load.c`), so a snapshot
also holds `[$1239e]` and a restore into another map copies that map's files back first.
`hl2_stateRender(0)` leaves the render range out (26 KB, used by the search); the search key never
hashes it. Fuzz check (`-fuzz 2000`, both modes): 16 000 restores, cross-map ones included,
0 mismatches. Not covered by random play: submaps past each map's first.

## 3. Geometry (phase 5, `hl2_obs.c`)

- Submap `s` (header `$54c00 + 8s`: block map `$56400 + w0`, max scroll `w1·8`, trigger and spawn
  tables at `$54c00 + w2/w3`): `w1 + 40` tile rows of 32 columns (the 40-row window at the
  max scroll). Tile attribute = `[$65200 + tile]` & `$7f`.
- Rick: column `(x + 4) >> 3`; **feet row** `((scroll & ~7) + y + $14) >> 3` — the row the trigger
  table compares. Standing, the floor is the row below the feet row (landing snaps `y + $14` to
  pixel 7 of its row). Standing takes 3 rows, crouching 2.
- Exit = trigger record: Rick clamped at x 0 (left) / `$e8` (right) on feet row `b1`; he arrives in
  submap `b2` at the opposite side with his feet on row `b3`.
- Measured: walk 2 px/frame; jump peak 33 px, 23 frames in the air (map 1 floor); bomb fuse 40
  frames, blast lethal ~7 frames; after a laser shot, fire alone re-arms it (`[$12e26]`).
- **Thrown bomb** (fire + down + left/right at the drop, `algo-player.md` §4, §11): measured
  2026-10-02 on the start floor of each map, thrown right from x 0: x 3, 5, 7, 9, 11, 13, 14, …,
  52, 53, 54 — stops 54 px away, explodes at frame 40 there (10 frames). A plain drop stays at x 0.
  The surface-bit variants (map 1 stop, map 2 no slowing, map 4 double) were not measured: those
  start floors have no surface bit.
- **Platforms and lifts are actors/objects** (probe actor part, `algo-collision.md` §2): map 1
  submap 5 cannot be climbed on tiles alone.
- **Switches**: trigger boxes (`algo-actors.md` §4) fired by the shot (mask 2), a bomb (4) or melee
  (8). They despawn blocking actors (hit class `$0c`) or change an actor's profile (class `$08`, e.g.
  a lift). The box can be far from the actor: map 1 submap 2's exit creature (type 18, row 111)
  dies when Rick punches x 24..32, row 114, the other end of the corridor.

## 4. Solver (phase 6, `hl2_solve.c`, `hl2_switch.c`)

As RD1 (`kb/demo-solver.md` §11): time-synchronous beam over held joystick bytes (2/4/8 frames;
laser, melee, bomb programs), pruning deaths/other submaps, state-key dedup, `f = 4·distance +
2·changes`, polish pass. RD2 specifics:

- Distance field: Dijkstra on (feet row, column, rows risen) — 2 columns, crawl through 2-row gaps
  at extra cost, jump ≤ 4 rows, ladders, one-way floors upwards; rising higher than a jump or going
  down through a floor costs `RELAX` (8) per row, standing in for lifts.
- Route: Dijkstra over (submap, entry row, entry column) nodes, edges = exits the field reaches.
- A leg's goal is a specific exit (target submap **and** entry row) or a waypoint (on the ground,
  not on a ladder, on the row, ±1 column).
- When an exit is not found, `hl2_switch.c` fires the submap's unfired switches one by one
  (waypoint next to the box, then walk 0–12 frames and act until the box's latch or its actor
  changes), searching the exit again after each.

## 5. MCP server (phase 7, `src/headless/rd2/mcp2_server.py`)

Modelled on RD1's (`kb/demo-solver.md` §12). Stdio JSON-RPC, no dependencies, one `xrick2-core`
process per call; states = snapshot + inputs + parent in `build/mcp2/` (env `XRICK2_MCP_WORK`).
Snapshots belong to the build that wrote them; `validate` replays the timeline from a new game.
Registered in `.mcp.json` as `xrick2` with a literal WSL path (the other two entries use
`${REVERSE}`, which was unset in the 2026-10-02 session).

| tool | what |
|---|---|
| `new_game`, `load_joy` | a root state on map N; a state from a `.joy` (e.g. `build/rd2solve/map1_to_submap1.joy`) |
| `observe` | `-dump` + `-distance`: rick (feet row, col), exits, records, spawns, switches (index for `fire_switch`), `route_exit`, tiles |
| `step`, `trace` | joystick inputs `[controls, frames]` (UP DOWN LEFT RIGHT FIRE); trace returns `-steplog` lines |
| `solve` | `-chain n` with hints (exit, waypoint, beam, max_steps, min_bombs, min_laser, switches); a failed leg's committed stages/switches are kept (`partial`) |
| `fire_switch` | `-switch i`: reach the box, punch / shoot / drop / throw until it fires |
| `validate`, `repair` | as RD1: timeline or legs; re-solve the legs of an old chain on a new parent |
| `export` | the timeline from map 1 as `.joy` and `dat_rd2_script.c` (`joy2script.py`) |
