# WebAssembly (emscripten) build — analysis and plan

Written 2026-09-28. Every fact below was read or checked in one of these places:
- `master` at `c9c35ed`, via `git show` / `git archive` (no checkout);
- the emsdk in `D:\d\EmSdk`;
- the SDL3 3.4.16 sources vendored under `xrick/xrick/vcpkg_installed/`;
- emscripten's online docs, fetched 2026-09-28.

**Unverified** marks what was not checked. Test builds ran in the session scratchpad only;
nothing in the repo was changed apart from this file.

## 0. Toolchain check (2026-09-28, after the user's emsdk update)

`D:\d\EmSdk` now holds **emscripten 6.0.10** (`upstream/emscripten/emscripten-version.txt`,
`emcc --version`: `6.0.10 (d6c521a7…)`, clang 24.0.0git), node 24.19.0, Python 3.13.3.
The 2019 components (1.38.30 fastcomp, node 8.9.1, Python 2.7.13) are still on disk next
to it.

**Setting up the environment (Git Bash, Windows emsdk).** A plain `source emsdk_env.sh`
fails: `emsdk` runs `python`, which on this machine resolves to the Windows Store alias
("Python est introuvable"). Point it at the bundled Python first, and do not source it
through a pipe (the pipe runs it in a subshell and the variables are lost):

```bash
cd /d/d/EmSdk
export EMSDK_PYTHON="$PWD/python/3.13.3_64bit/python.exe"
source ./emsdk_env.sh
emcc --version     # 6.0.10
```

**Checked with this environment:**
- **SDL3 port.** `-sUSE_SDL=3` built on first use (cached in emsdk) and a test program ran
  under node: `SDL_Init(SDL_INIT_EVENTS)` OK, `SDL_GetVersion()` = 3004002 (**SDL 3.4.2**).
- **`EMSCRIPTEN` macro.** It is *not* defined on the command line. It appears only after
  `#include <emscripten.h>`, with a warning ("macro 'EMSCRIPTEN' has been marked as
  deprecated: use `__EMSCRIPTEN__` instead"). `__EMSCRIPTEN__` is defined.
- **`-fcommon`.** Two files each with the tentative definition `int tent;` link fine.
- **`master` sources, compiled as they are:** all 67 C files (`src`, `src/rd1`, `src/rd2`,
  PC data tables excluded, as in the `Makefile`) and the 8 C++ files of `src/audio_engine`
  compile with `emcc`/`em++ -sUSE_SDL=3 -fcommon -O2 -DPLATFORM_ST` (C++: `-std=c++17`).
  The only diagnostic is the `EMSCRIPTEN` deprecation warning. They **link** with `em++`
  into `xrick.js` (186 KB) + `xrick.wasm` (2.1 MB).
- **But the web code paths are compiled out.** `llvm-nm` on the objects: `rd1/game.c` has
  no `emscripten_set_main_loop`, `sysevt.c` calls `SDL_WaitEvent`, and `rd1/syssnd.c`
  calls `SDL_CreateMutex`. So the native paths were built and the page would block in
  `while (game_state != EXIT)`. With `-DEMSCRIPTEN` the same three files compile against
  SDL3 and `syssnd.c` no longer references `SDL_CreateMutex`.
- **Not run in a browser.** The link was not run in a browser.

Project note: the rule is "build in WSL by default", but this emsdk is Windows-native, so
it is driven from Git Bash. **Decided (user, 2026-09-28): keep Git Bash** with the Windows
emsdk for the web build.

## 1. How it was done (2019)

**History.** Commits on `master`:
- `6a3e86c` 2019-05-12 "Import EmSdk build script";
- `bf1833a` 2019-05-27;
- player script: `59f335c`, `2c203b6`, `9c090b9` (2019-05-27..29);
- C-side fix: `c2aef3d` 2019-06-04 "Fixing Emscripten loop and timing".

**`build/emsdk/build.sh`** (bash, run in a scratch dir `build.tmp`):
1. Adds `/c/python27-x64` to `PATH` and sources `/d/d/EmSdk/emsdk_env.sh`.
2. Compiles every `xrick/src/*.c` (one flat directory) with
   `emcc f.c -o f.bc -I include -s USE_SDL=2 -D NOZLIB -O2`.
3. Links with `emcc *.bc -o xrick.js -s USE_SDL=2 -s FORCE_FILESYSTEM=1 -O2
   --preload-file data@/data`, producing `xrick.js`, `xrick.wasm` and `xrick.data`.
4. Copies `player.js`, gzips everything into `gz/`, and reminds to set
   `Content-Type: application/wasm` (`.wasm`), `application/octet-stream` (`.data`) and
   `Content-Encoding: gzip`.

Paths are hard-coded to the author's machine at the time.

**`build/emsdk/player.js`** (jQuery; the HTML page is not in the repo):
- **Start.** Sets `Module.noInitialRun = true`. A "click/touch to play" overlay calls
  `Module.callMain(args)`, which also unlocks audio (plus an explicit `<audio>` unlock on
  iOS).
- **Arguments.** Taken from the query string (`?demo` becomes `-demo`), then
  `-data /data -keys S-D-O-K-SPACE -zoom 1` are added.
- **Data file.** `locateFile` loads `*.data` from `http://www1.xrick.net/`.
- **Touch.** The touch pad and on-page buttons dispatch synthetic `keydown`/`keyup` events
  that carry only `keyCode`.

**C side** (still on `master`, all behind `#ifdef EMSCRIPTEN`):
- `rd1/game.c` uses `emscripten_set_main_loop(game_loop, fps, 1)` with
  `fps = (24 * GAME_PERIOD) / game_period`. It skips `sys_sleep` and, on `EXIT`, cancels
  the loop.
- `sysevt.c` polls instead of calling `SDL_WaitEvent`.
- `rd1/syssnd.c` creates no mutex.
- `config.h` turns off `ENABLE_LOG`.

## 2. What changed in the port since then

| change (ticket) | effect on the web build |
|---|---|
| RD1/RD2 split into `src/rd1/`, `src/rd2/` (2026-09-22) | `build.sh` compiles only `src/*.c`, so most of the game is missing |
| SDL2 → **SDL3** (T20) | needs `-sUSE_SDL=3` (checked: works, SDL 3.4.2) |
| zlib and disk assets dropped (T22); everything compiled in | no `data/` on `master` (0 files): `--preload-file`, `FORCE_FILESYSTEM`, `NOZLIB` and `.data` must go |
| `-data` option removed from `sysarg.c` | `player.js` still passes `-data /data`, so `sysarg_fail` calls `exit(1)` at start |
| AtariAudio engine in **C++17** (T19) | compile with `em++`, link with `em++` (checked: compiles and links) |
| `-fcommon` needed (tentative definitions) | same with emcc (checked: works) |
| `PLATFORM_ST` / `PLATFORM_PC` mandatory (`config.h` `#error`) | pass `-DPLATFORM_ST`; leave out the PC data tables |
| RD2 engine (`-rd 2`) | blocking loops, no web path (§5) |
| T43 demo loop (`-demo`, loops at the end of the game) | nothing web-specific; `?demo` in the URL |

## 3. Tool changes that matter

- **emscripten 6.0.10.** Latest per `ChangeLog.md`. The SDL3 port came in 4.0.4 and has
  not been experimental since 6.0.10. The deprecated `EMSCRIPTEN` macro moved into
  `emscripten.h` in 5.0.4 (checked, §0). Python ≥ 3.10 is required (bundled).
- **Runtime exports.** `Module.callMain` must be listed in
  `-sEXPORTED_RUNTIME_METHODS=callMain` (default empty). "Don't run `main`" is
  `-sINVOKE_RUN=0`. The settings reference no longer mentions `Module.noInitialRun`
  (**unverified** whether it is still honoured).
- **Build steps.** Build with `-c … -o f.o` or one `emcc`/`em++` call; the fastcomp-era
  `-o f.bc` step is obsolete.
- **SDL3 in the browser** (vendored 3.4.16 source and docs):
  - Keys are mapped from `KeyboardEvent.code` (`Emscripten_HandleKey` →
    `Emscripten_MapScanCode(keyEvent->code)`), so events carrying only `keyCode` are
    unknown keys.
  - Audio is dropped until the user interacts with the page.
  - `SDL_LockMutex(NULL)` is a no-op.
  - vsync is off unless set; SDL recommends a `requestAnimationFrame` (fps 0) main loop.
  - The `<canvas>` must have no border or padding.

## 4. Would `master` work in a browser today?

**No.** It compiles and links (§0), but:
1. **The page hangs.** The `EMSCRIPTEN` guards are dead with 6.0.10, so the native loop
   runs and never returns control to the browser.
2. **The script is stale.** `build.sh` and `player.js` are out of date; in particular,
   `-data` makes the game `exit(1)` at start.
3. **Timing is wrong.** The web loop runs at `24 * GAME_PERIOD / game_period` = **24 fps**
   at the default. Native runs one frame per `GAME_PERIOD` = 75 ms (13.3 fps), so the web
   game plays about 1.8× too fast. The fps is also fixed at start, so the screens that
   change `game_period` (`scr_imain.c`, `scr_gameover.c`) keep the same speed.
4. **The touch controls are dead.** They send events without `code` (§3).
5. **RD2 cannot run.** Its loops block (§5).

## 5. RD2: what it needs (documented for phase W2, not planned in detail)

RD2 is a transcription of the 68000 flow. It never returns to a frame loop:
- **Blocking loops.** `for (;;)` state loops in `rd2_flow.c` (lines 32, 181, 325, 434,
  508); busy waits such as `while (!FIRE())`, `while (FIRE())` and
  `while (rd2_snd_rw(0x1aa08) != 0)`; the pause loops in `rd2_game.c:107-108`.
- **Frame wait.** `rd2_191e6` (VBL) spins on `rd2_sys_pump()`, which polls events, runs
  the joystick and **`sys_sleep`s** until the next 50 Hz tick (`rd2_sys.c:282-297`).
- **Exits.** `rd2_sys_pump` calls `exit(0)` on window close or ESC.

**Options:**
- **A. ASYNCIFY (recommended).** Link with `-sASYNCIFY` and make the sleep in
  `rd2_sys_pump` an `emscripten_sleep(ms)`, which hands control back to the browser.
  Every loop then yields through the one place where the engine already waits for the
  VBL. Restrict the instrumentation to the call paths that reach `emscripten_sleep`
  (`-sASYNCIFY_ONLY=…` or `ASYNCIFY_ADD`/`REMOVE` lists) to limit code size and slow-down;
  size it after a first build. The busy waits that do not go through `rd2_sys_pump` need
  checking one by one: each must reach `rd2_191e6`/`rd2_sys_pump` or it spins forever.
  RD1 can keep `emscripten_set_main_loop`; ASYNCIFY does not affect it.
- **B. Restructure as a per-frame state machine.** Faithful but very large; it would
  rewrite the transcription the KB validates line by line. Not recommended.
- **C. Run RD2 on a pthread (web worker)** with rendering proxied to the main thread.
  Needs COOP/COEP headers and a threads build (a build with threads cannot also run
  without them); rendering must stay on the main thread. Not recommended.

**Other RD2 points:**
- `rd2_snd.c` creates its mutex unconditionally, which is harmless without threads
  (**unverified** at run time).
- The debug hooks (`RD2_INPUT`, `RD2_SHOT`, `RD2_TRACE`, `RD2_JOYSEQ`, …) read
  environment variables and write files. Under emscripten `getenv` sees only what
  `Module.ENV` sets, and files go to MEMFS. That is fine; the hooks are simply unused on
  the web.
- `exit(0)` in the pump ends the runtime. The page should show "game over / reload"
  instead of a frozen canvas.
- RD2 audio has the same user-gesture constraint as RD1.
- In phase W1 the RD2 sources stay compiled in, since `xrick.c` references
  `rd2_game_run`, but `-rd 2` is refused on the web with a clear message.

## 6. Plan — phase W1: RD1 in the browser

Each step is a separate, documented commit on `master`, like F10–F13. Each is checked
before the next.

**W1.1 Build script.**
- Replace `build/emsdk/build.sh` with a script (or an `emmake make web` target) that
  mirrors the `Makefile`:
  - C sources `src/*.c`, `src/rd1/*.c` and `src/rd2/*.c`, minus the PC data tables;
  - C++ sources `src/audio_engine/**/*.cpp`;
  - the `Makefile`'s `-I` list;
  - `-DPLATFORM_ST -fcommon -O2 -sUSE_SDL=3`.
- Link with `em++` using `-sINVOKE_RUN=0 -sEXPORTED_RUNTIME_METHODS=callMain`, and
  `-sALLOW_MEMORY_GROWTH=1` if needed.
- Remove `--preload-file`, `FORCE_FILESYSTEM`, `NOZLIB` and the Python 2 / hard-coded
  paths. Output goes to a git-ignored `build.web/`.
- Check: a clean build, and the warning count recorded.

**W1.2 Macro.**
- Replace `EMSCRIPTEN` with `__EMSCRIPTEN__` in `config.h`, `rd1/game.c`, `sysevt.c` and
  `rd1/syssnd.c`. Include `<emscripten.h>` under `__EMSCRIPTEN__`.
- Check: `llvm-nm` shows `emscripten_set_main_loop` in `game.o`, no `SDL_WaitEvent`
  reference in `sysevt.o`, and no `SDL_CreateMutex` in `syssnd.o`.

**W1.3 Timing.**
- Replace the fixed-fps loop with `emscripten_set_main_loop(web_frame, 0, 1)`
  (`requestAnimationFrame`). `web_frame` accumulates real time and runs `game_loop()`
  once per elapsed `game_period`, reading the current value each time so runtime changes
  apply. Cap the catch-up (e.g. 4 steps) after a tab switch.
- Game logic is tick-based, so determinism does not depend on this (demo: `kb/demo.md`).
- Check: logic steps per second in the browser equal the native rate (13.3/s at the
  default).

**W1.4 Web-only arguments.**
- Under `__EMSCRIPTEN__`, refuse `-rd 2` with a message, and nothing else.
- `-data` stays gone; it is dropped from the page instead (W1.5).

**W1.5 Page.**
- A new minimal `index.html` + `player.js` in `build/emsdk/` (in this repo; moved to `xrick/emsdk/` on 2026-09-28), with no
  jQuery and no external host. The player does **not** start in demo mode by default. A
  player setting (a constant at the top of `player.js`, e.g. `startInDemo = false`)
  switches it on; `?demo` in the URL overrides it for one visit:
  - a canvas with no border or padding;
  - a click/touch-to-start overlay (unlocks audio) that calls
    `Module.callMain(args)`;
  - query-string arguments (`?demo`, `?speed=`, `?zoom=`, `?keys=`);
  - touch pad and buttons that send
    `new KeyboardEvent(type, {code: 'KeyS', key: 's', bubbles: true})`;
  - F-key buttons (sound, cheats), END and PAUSE as before.
- Check in a local server: `emrun`, or a static server with
  `Content-Type: application/wasm`.

**W1.6 Audio.**
- The AtariAudio / Musashi SNDH engine runs in the SDL3 audio callback on the main
  thread. Measure its cost per frame in the browser (performance panel) and check
  playback after the start click.
- If it is too slow: raise the buffer size, or render ahead.

**W1.7 Determinism check (T43 method).**
- Add a small web-only way to save `-trace` from MEMFS (a JS download of
  `FS.readFile`).
- Run `?demo&trace=…` and compare the trace with the native `xrick -demo -trace`: they
  should be identical line for line (the native SDL trace already equals the headless
  one).
- Then the user watches the demo, and a game played by hand, in Chrome and Firefox.

**W1.8 Packaging.**
- gzip or brotli, plus the `Content-Type` / `Content-Encoding` headers. No COOP/COEP
  (no threads).
- Document it in `kb/build.md`. Update `kb/xrick/architecture.md` and `algo-system.md`,
  which still describe the 2019 build.

**Decisions (user, 2026-09-28):**
- Toolchain: the Windows emsdk via Git Bash (§0).
- The web page lives in this repo, in `build/emsdk/` -- later `xrick/emsdk/` (user: `build/` is output only, fully git-ignored).
- No demo at start, but a player option to start in demo mode (W1.5).

## 7. Phase W2 — RD2 (after W1)

1. ASYNCIFY build (option A): `emscripten_sleep` in `rd2_sys_pump`; audit every loop
   listed in §5 so that each yields.
2. Narrow the instrumentation (`ASYNCIFY_ONLY`) and measure the size and speed cost.
3. Web handling of the `exit(0)` sites.
4. Remove the `-rd 2` refusal from W1.4. The page offers a game switch (`?rd=2`).
5. Checks: RD2 attract demo and a hand-played game in the browser. A trace comparison
   with native needs RD2's `RD2_TRACE` output made downloadable, like W1.7.

## 8. Status of phase W1 (2026-09-28) — merged into `master`

Developed on branch `wasm` (forked from `master` `c9c35ed`), **merged into `master`
2026-09-28** (fast-forward to `1002ceb`) and the branch deleted, at the user's request.
Then `build-wasm.sh` became **`./build.sh`**, which builds the Windows desktop version
(MSBuild) **and** the web version every time, after checking that it finds MSBuild,
SDL3 (vcpkg) and emsdk (master `d0ed44f`, `kb/build.md` intro and §4). Outputs since
master `964807d`: web in **`build/web/`**, desktop in **`build/win/`** (the web page
sources are checked up front). Since master `461f61a` the page sources live in **`xrick/emsdk/`** with the other sources and `build/` is output only, fully git-ignored.

| step | commit | result |
|---|---|---|
| W1.1 build script | `720c037`, `1002ceb`, `d0ed44f` | mirrors the `Makefile`; moved to `./build-wasm.sh` at the top of the repo, registers emsdk itself first and reports failures; then renamed `./build.sh`, also running the desktop MSBuild build, with up-front checks for MSBuild, SDL3 and emsdk (user, 2026-09-28); LF and executable in git |
| W1.2 `__EMSCRIPTEN__` | `aaaaf1e` | web paths compiled in (checked with `llvm-nm`); native unchanged (ST 230 / PC 231) |
| W1.3 timing | `69a0a35` | `requestAnimationFrame` loop, one step per `game_period` of real time — **see the open question below** |
| W1.4 `-rd 2` refused | `15c5684` | message shown on the page (after W1.5a) |
| W1.5a exit / logging | `38d0c81` | logging on for the web; `EXIT_RUNTIME` + `emscripten_force_exit` on Esc; `_fflush` exported |
| W1.5 page | `5fa4904` | new `index.html` + `player.js`; `startInDemo = false` option |
| W1.6 audio | — | WebAudio context running (48000 Hz, ScriptProcessorNode 4096); the `?speed=2` run kept ~300 steps/s with audio on, so no CPU problem seen. **Not heard**: headless Chrome cannot tell whether it sounds right |
| W1.7 determinism | — | headless Chrome over the DevTools protocol: `?demo&speed=2&trace` = native SDL trace, **byte-identical over 37013 lines** (whole game + start of loop 2); `?rd=2` and Esc messages checked |
| W1.8 packaging, docs | — | `./build.sh gz` (wasm 2.1 MB → 0.82 MB); `kb/build.md` §4 written |

Web warning baseline: 168 (clang), after W1.5a.

**Open question: the game speed.** At the default `GAME_PERIOD` (75 ms):
- the **native** build runs **~25.7 logic steps/s** in the demo (measured, WSL SDL,
  dummy drivers). Its timer takes `tm` *before* sleeping (`game.c` `game_loop`:
  `tmx = tm; tm = now; tmx = tm - tmx; if (tmx < period) sleep(period - tmx)`), so the
  measured interval includes the previous sleep and frames alternate between a full
  sleep and none: on average one step per `period/2`;
- the **web** build (W1.3) runs **12.6 steps/s** measured (13.3 nominal): one step per
  `game_period`, i.e. **half the native speed**;
- the 2019 web build's fixed 24 fps was close to the native effective rate, which may
  be why it was chosen.
The logic is tick-based, so this changes pace only, not determinism. Options:
(A) the web matches the native effective rate (one step per `game_period/2`);
(B) keep the nominal rate on the web and fix the native timer on `master` (the whole
game would play half as fast as today); (C) measure the ST original's logic rate in
Hatari first, then set both. **User to decide.**

**Option C done (user, 2026-09-28): the ST original measured in Hatari** (`kb/hatari.md`
§7, 2026-09-28): gameplay runs **one logic step per 2 VBLs = 25 steps/s = 40 ms per
step** (606 of 608 main-loop iterations standing, 425 walking; only room redraws and
the respawn take longer). So today: native ≈ 37.5 ms/step (7% fast, and jittery:
frames alternate between a full sleep and none), web W1.3 = 75 ms/step (half speed),
ST = 40 ms/step.

Every period in the port goes through the same native timer, so each one runs at about
half its nominal value today: `GAME_PERIOD` 75 → ~37.5 ms, `SCROLL_PERIOD` 24 → ~12,
`IMAIN_PERIOD` and the game-over screen 50 → ~25, and the fades (`period/2`). Only the
gameplay rate was measured on the ST.

**Done (user go, 2026-09-28): master `89d0e1a`**, merged into `wasm` (`05e43f3`, plus
the `web_frame` comment `806fc8f`):
1. The native timer schedules one frame per `game_period` (the next frame is due one
   period after the previous one was due; a late frame restarts the schedule).
   `GAME_PERIOD` is **40** on the ST, 38 on PC (unmeasured: the pace it had).
   `SCROLL_PERIOD` 12, `IMAIN_PERIOD` 25 and game over 25, halved to keep their pace.
2. Native checks: demo at default speed 23.9 logic steps/s in the `-trace` (scroll
   frames and room redraws excluded, like the ST's 24.0 when walking);
   `-demo -speed 2 -trace` byte-identical to the previous native trace over 37013
   lines; warnings ST 229 / PC 230.
3. Web, rebuilt with `./build-wasm.sh clean gz` (now `./build.sh`) from a fresh bash (168 warnings), in
   headless Chrome: `?demo&trace` runs **23.6 logic steps/s** at default speed (native
   23.9); `?demo&speed=2&trace` is **byte-identical to the native trace over 55026
   lines** (107 segments, more than two demo loops).

**2026-09-29 — black canvas on Chrome/macOS (M1), fixed on master `0eb6eda`.** The game
ran (sound) but the canvas stayed black. Cause: the palette's alpha was never set
(`pald[].a` = 0), and SDL3 creates the WebGL canvas with an alpha channel (default
`gl_config.alpha_size` 8), so every frame was colour with alpha 0: an invalid
premultiplied value that Chrome/macOS shows as transparent (the user's console check:
WebGL context present, canvas 640×400, a red CSS background showed through), while
Chrome/Windows and iOS Safari showed the colours. Fix: `sysvid_setDisplayPalette` sets
alpha 255 for all entries. Checked in headless Chrome: the framebuffer pixel read right
after drawing went from alpha 0 to 255. **Open:** no sound on iPhone (Safari and
Firefox) with the speaker icon showing — most likely iOS silent mode muting Web Audio;
proposed fix (not done): `navigator.audioSession.type = 'playback'` plus a silent
`<audio>` element started in the start tap, as the 2019 player did.

**2026-09-29 — web player for any host page, and iPhone sound (master `f033ec5`).**
`xrick/emsdk/player.js` now takes its page layout from `window.xrickPlayer` (set by the
page before loading `player.js`; defaults = `index.html`): `start`, `label`, `status`,
`buttons`, `pad`, `saveTrace`, `startInDemo`, and `wasmUrl`. The last one is served
through `Module.locateFile`, so the generated `xrick.js` no longer needs hand edits (the
user's CMS page had patched it for `/media/1vqhdi1t/xrick.wasm`; their backup is
`web.1/`, left untouched). Missing elements are skipped; start hides the overlay and
shows the canvas with inline styles. iPhone sound: in the start tap,
`navigator.audioSession.type = 'playback'` where available, a silent looping `<audio>`
on iOS/iPadOS (as the 2019 player did), then SDL's AudioContext resumed. Checked in
headless Chrome on `index.html` and on a CMS-like page (wasm from the media URL); the
iOS path only mechanically (faked user agent) — **to confirm on an iPhone**. The CMS page
needs:
`<script>window.xrickPlayer = { start: '#xrick', label: '#xrick span', status: '#player_console', buttons: '#controls1 div[data-code]', wasmUrl: '/media/1vqhdi1t/xrick.wasm' };</script>`
before `player.js`.

**2026-09-29 — map and starting-room selector (master `701a038`), `-vol` fix (`fba490d`).**
Above the game: one drop-down of "<game> - <map>" entries ("RD1 - South America",
"RD1 - Egypt", "RD1 - Schwarzendumpf Castle", "RD1 - Missile Base"; RD2 entries later in
the same list, adding `-rd 2`), then the starting room, "start of map" by default. Both
lock when the game starts; a new choice needs a page reload. Start of map → `-map N`,
a room → `-submap N` (1-based). Built by `player.js` inside the `selector` element
(default `#select`; the CMS page adds e.g. `<div id="xrick-select"></div>` and
`selector: '#xrick-select'` in `window.xrickPlayer`); the URL (`?map=`, `?submap=`)
pre-selects. All ST submaps are valid starts (each has a rightward `map_connect`
entry; checked). Demo mode not handled yet. Separately, `sysarg.c`'s `-vol` checked the
submap number instead of the volume (`-submap 11+` before `-vol` failed to start); fixed.
Still open there: `-vol` stores N−1, so `-vol 1` = default volume and `-vol 0` is
rejected although the help says 0 is silence.
