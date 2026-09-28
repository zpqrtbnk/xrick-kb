# Architecture — build layout, module map, and the frame loop

## Repository layout (clone root = `xrick/`)

```
xrick/
  README.md              project description (no licence terms)
  xrick.sln              MSVC solution
  data/sounds/*.wav      29 WAV files, shipped as loose data (see assets.md)
  build/emsdk/build.sh   emscripten build: per-file emcc -> .bc, link to xrick.js/.wasm
  build/emsdk/player.js  web page glue
  xrick/
    xrick.vcxproj, xrick.rc, resource.h, icons/   MSVC project + Win32 resources
    include/*.h          25 headers
    src/*.c              51 C files
    src/*.e              12 generated blobs, #included as C initialisers
```

`.e` files are not compiled on their own; they are `#include`d. Two kinds exist:
`img_splash.e` / `img_icon.e` (image data included by `scr_xrick.c` / `sysvid.c`) and,
until 2026-09-10, `wav_*.e` (legacy embedded PCM) — deleted along with `dat_snd.c` as
part of T19's sound-engine rewrite (`audio-sndh.md`), confirmed unreferenced first.
`sdlcodes.e` is an SDL keycode table.

## Layering

The port has a clean three-layer separation, and the boundary matters for us because the
bottom layer mostly has **no counterpart at all** in the original:

| Layer | Files | Corresponds to, in the original |
|---|---|---|
| Game logic | `game.c`, `ents.c`, `e_*.c`, `maps.c`, `util.c`, `env.c`, `scroller.c`, `scr_*.c` | The 68000 game code |
| Drawing model | `fb.c`, `tiles.c`, `sprites.c`, `img.c`, `draw.c`, `rects.c` | The blitter and screen handling |
| Platform | `sys*.c` (`sysvid`, `syssnd`, `sysevt`, `sysarg`, `sysjoy`, `syskbd`), `xrick.c`, `data.c`, `unzip.c` | **Nothing** — replaces ST hardware, TOS, and the disk loader. **Exception since T19: `syssnd.c` now embeds and runs the actual ST sound-engine code under 68000 emulation** (`src/audio_engine/`) — the one platform file with a direct original counterpart, even though it still exists to bridge SDL audio out |

`draw.c:17` states the intent: "This is the only file which accesses the video." That is
no longer literally true (the frame buffer moved to `fb.c`), but the principle holds —
game code writes 8-bit indexed pixels into a 320×200 array and never touches SDL.

## The frame buffer

`fb.c:25` — `U8 fb[FB_HEIGHT][FB_WIDTH]` = `U8 fb[200][320]`, one byte per pixel, the
byte being a palette index. This is the port's central abstraction: everything paints
into it, and `sysvid_update()` blits the dirty rectangles to an SDL texture.

For `GFXST` the palette has **32 entries** (`fb.c:40`): 16 game colours plus 16
"highlight" variants used by the `env_highlight` cheat, which ORs `0x10` into the pixel
value (`sprites.c:242`). Values are 8-bit R/G/B triples in `fb.c:41-69`. Fading is done
by scaling the whole palette through a `gamma` value 0–255 (`sysvid.c:139-141`), not by
touching pixels.

## Entry point and top-level flow

```
main()                          xrick.c:111
  sys_init(argc, argv)          xrick.c:53   -> sysarg_init, SDL_Init, sysvid_init,
                                                syssnd_init, atexit/signal handlers
  game_run(path)                game.c:178   path = -data argument, else "data.zip"
    data_setpath(path)                       directory or .zip (zlib)
    loadData() -> sounds_load()              caches 23 WAVs
    game_period = 75 ms (GAME_PERIOD)
    loop: game_loop()                        native: while (state != EXIT)
                                             emscripten: emscripten_set_main_loop
    game_exit() -> freeData, data_closepath
  sys_shutdown()
```

## The frame loop — `game_loop()` (`game.c:221`)

One pass per displayed frame, in this fixed order:

1. **Timer.** `tmx = now - previous; if (tmx < game_period) sys_sleep(game_period - tmx)`.
   Native only — under emscripten the timing is delegated to the browser's
   `requestAnimationFrame` at `fps = (24 * GAME_PERIOD) / game_period` (`game.c:203`).
2. **Video.** `sysvid_update(game_rects)` — pushes the rectangles that the *previous*
   cycle declared dirty. Note the ordering: the frame produced by cycle *n* is displayed
   at the start of cycle *n+1*.
3. **Sound.** Nothing; mixing happens in the SDL audio callback thread.
4. **Events.** `sysevt_wait()` if `game_waitevt` (paused), else `sysevt_poll()`.
5. **`game_cycle()`** — runs the state machine until a state `return`s, which is the
   signal that a frame is ready and `game_rects` describes what changed.

`game_period` is 75 ms by default (≈13.3 fps), overridable with `-speed`. It is
temporarily replaced during scrolling (24 ms, `scroller.h:1179`), the intro screens
(50 ms) and fades. **There is no VBlank, no interrupt, and no fixed 50 Hz tick** — the
original's timing model is not reproduced. See `divergences.md`.

## The game state machine — `game_cycle()` (`game.c:278`)

A `while(1)` over `switch (game_state)`; `break` continues within the same frame,
`return` ends the frame. States (`game.c:52-66`):

```
XRICK ──> XRICK_CLR ──> [DEVTOOLS] ──> MAIN_INTRO ──> INIT
  splash    palette                     title/HoF     lives=6 bombs=6 bullets=6
                                                      score=0, place Rick

INIT ──> MAP_INTRO (only if entering a map at its first submap) ──> INIT_MAP
INIT ──> INIT_MAP  (otherwise)

INIT_MAP ──> if env_map >= 4: FADEOUT__GAMEOVER      (end of game)
             else: map_init, game_save, fb_clear, maps_paint, env_paintGame/Xtra,
                   full-screen refresh ──> FADEIN__CTRL_ACTION ──> CTRL_ACTION

                 ┌─────────────────────── the play loop ────────────────────────┐
CTRL_ACTION ──> ent_action(); e_them_rndseed++      (END -> gameover, EXIT -> exit)
CTRL_PAUSE  ──> pause pressed -> PAUSE_PRESSED1; focus lost -> PAUSED; else CTRL_RICK
CTRL_RICK   ──> dead -> RESTART or FADEOUT__GAMEOVER; atExit -> NEXT_SUBMAP; else PAINT
PAINT       ──> game_paintEntities(); return frame ──> CTRL_SCROLL
CTRL_SCROLL ──> y >= 0xCC -> SCROLL_UP; y <= 0x60 -> SCROLL_DOWN; else CTRL_ACTION
                 └──────────────────────────────────────────────────────────────┘

NEXT_SUBMAP ──> map_chain() ? INIT_SUBMAP
                            : (bullets=6, bombs=6, env_map++) NEXT_MAP
NEXT_MAP    ──> Rick to map start, map_frow/env_submap from map_maps[] ──>
                FADEOUT__MAP_INTRO ──> MAP_INTRO
RESTART     ──> restart(): clear DEAD|ZOMBIE, 6 bombs/bullets, e_rick_restore,
                map_frow = save_map_row, map_init, repaint ──> CTRL_ACTION
GAMEOVER ──> GETNAME ──> XRICK_CLR   (loops back to the attract sequence)
```

Pause is a four-state handshake (`PAUSE_PRESSED1`, `1B`, `PAUSED`, `PAUSE_PRESSED2`)
that debounces key press and release and drives `syssnd_pause` and `screen_pause`.

**Structural note for comparison:** the original is an interrupt-driven loop with a
VBlank handler; the port is a cooperative state machine that returns to the host once
per frame. The *order of operations inside one frame* is nevertheless explicit and
comparable: entity actions, then Rick's death/exit check, then paint, then scroll.

## Sequence inside one gameplay frame

```
ent_action()          ents.c:481   for each slot 0..ENT_ENTSNUM-1 with n != 0:
                                     k = n & 0x7f
                                     k == 0x47      -> e_them_z_action
                                     k >= 0x18      -> e_them_t3_action
                                     else           -> ent_actf[k](slot)
e_them_rndseed++      game.c:484   one increment per frame, feeds the t2 randomiser
game_paintEntities()  game.c:788   env_clearGame -> ents_paintAll -> env_paintGame
                                   game_rects = STATUSRECT -> ent_rects
```

Rick is slot 1 and is therefore acted **after** slot 0 (the "stops Rick" entity) and
**before** the bullet (2), bomb (3) and all enemies (4..C). This ordering is load-bearing
for collision outcomes and is a prime comparison target.

## Build

- **MSVC**: `xrick.sln` + `xrick/xrick.vcxproj`, links SDL2 and (optionally) zlib;
  `WITH_ZLIB` is on unless `NOZLIB` is defined (`config.h:49`).
- **emscripten**: `build/emsdk/build.sh` compiles each `src/*.c` to `.bc` with
  `-s USE_SDL=2 -D NOZLIB -O2`, links to `xrick.js` + `xrick.wasm`, and preloads
  `data/` into the virtual FS at `/data`. Paths inside the script are hard-coded to the
  original author's machine (`/d/d/EmSdk`, `/d/d/Rick Dangerous/wip/xrick-vs19`) and
  would need editing to run here. *(2019 tree, as analysed. The current web build is a
  rewrite on branch `wasm`: `kb/build.md` §4, `wasm.md`.)*
- Compile-time switches, all in `config.h`: `GFXST`/`GFXPC`, `ENABLE_LOG`,
  `ENABLE_JOYSTICK` (off), `ENABLE_SOUND` (on), `ENABLE_CHEATS` (on), `ENABLE_FOCUS`
  (off), `ENABLE_DEVTOOLS` (off), `DEBUG` (on — enables `DEBUG_ENTS`, `DEBUG_MAPS`,
  `DEBUG_AUDIO`, `DEBUG_VIDEO`, `DEBUG_VIDEO2` in `debug.h`).

Note `ENABLE_DEVTOOLS` is off and cannot be turned on as-is: the `DEVTOOLS` case in
`game_cycle` assigns `game_state = INIT_GAME`, an identifier that does not exist
(`game.c:299`). Dead code.
