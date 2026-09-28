# Building the port (`xrick/`)

How to build **xrick**, the C/SDL3 Rick Dangerous port that lives in `xrick/` (a
nested git repo; see `MEMORY.md` §9). Two independent build systems exist side by
side in `xrick/xrick/` — a `Makefile` for Linux/WSL, and `xrick.sln`/`xrick.vcxproj`
for native Windows via Visual Studio/MSBuild. Both build the same sources and default
to the same configuration (`PLATFORM_ST`, `GFXST` — see config.h); see §3 for the one
capability gap between them.

**T20 (2026-09-10): upgraded from SDL2 to SDL3.** **T21 (2026-09-10): the Windows
project dropped its Win32/x86 configs (x64 only now), moved output to `bin\<Config>\`
instead of `<Platform>\<Config>\`, and defaults to Release when no
`/p:Configuration`/`/p:Platform` is given.** **T22 (2026-09-10): the `-data`
directory/zip mechanism, and zlib, are gone — see §1's note.** All three are
verified — built and run on both platforms, including a real native Windows run with
user permission for this session (this project's standing rule is otherwise to always
build/verify in WSL; see `MEMORY.md`'s `build-in-wsl` note).

**2026-09-28: `./build.sh` at the top of the port repo (Git Bash) builds the Windows
desktop version (MSBuild, §2) and the web version (emscripten, §4) every time** (user
request). It first checks that it can find MSBuild (`vswhere`, or `MSBUILD`), SDL3 in
`xrick/vcpkg_installed/x64-windows`, and emsdk (`EMSDK_DIR`, default `/d/d/EmSdk`), and
stops with a message if one is missing. `./build.sh clean` rebuilds both,
`./build.sh gz` adds gzip copies of the web files. **Outputs (master `964807d`):
`build/win/`** — `xrick.exe`, `SDL3.dll`, objects in `obj/` (MSBuild `OutDir`/`IntDir`
overridden on the command line; a direct `MSBuild xrick.vcxproj` still builds into
`xrick\bin\Release\`, §2) — and **`build/web/`** (§4); both git-ignored, next to the tracked
page sources in `build/emsdk/`, which the script also checks for up front. The WSL
`Makefile` (§1) is unchanged and separate.

Both build systems were verified working as of 2026-09-10 before any of T20/T21/T22
too (T19's audio-latency investigation, see `kb/audio-sndh.md`). Exact tool versions
below are what was actually used, not guaranteed minimums; if you're on
close-but-different versions and it doesn't build, that's real information, not
something to assume away.

---

## 1. Linux / WSL (the `Makefile`)

### Dependencies

- A C11 **and** C++17 compiler pair from the same toolchain — `gcc`/`g++`. The C++
  compiler is required now: `src/audio_engine/` (AtariAudio, T19) is C++, vendored
  and compiled alongside the game's C code.
- `make`
- SDL3 development headers/libs, discovered via `pkg-config` (T20: SDL3 dropped the
  `sdl2-config`-style shell script entirely — pkg-config is now the only path)

Verified with gcc/g++ 14.2.0 and **SDL3 3.2.10** (Debian trixie's `libsdl3-dev`
package) on Debian (WSL). This is *not* the latest upstream SDL3 release (3.4.16 as
of 2026-09-02, confirmed against both the upstream GitHub releases page and vcpkg's
`sdl3` port) — building that from source hit a missing build dependency
(`libxtst-dev`, for X11 XTest) that needed interactive sudo this session couldn't
supply, so the packaged 3.2.10 was used instead; this is a real constraint, not a
preference. `pkg-config --modversion sdl3` needs to run successfully before the
Makefile will produce correct `SDL_CFLAGS`/`SDL_LIBS`.

Debian/Ubuntu (including WSL):

```sh
sudo apt install build-essential libsdl3-dev
```

Fedora:

```sh
sudo dnf install gcc gcc-c++ make SDL3-devel
```

To build the actual latest upstream SDL3 (3.4.16) from source instead of the
distro package: `git clone --branch release-3.4.16 --depth 1
https://github.com/libsdl-org/SDL.git`, then the standard CMake flow
(`-DSDL_SHARED=ON -DSDL_STATIC=OFF`, install to `/usr/local`) — but first
`sudo apt install libxtst-dev` (X11 XTest support), which the CMake configure step
fails without.

**T22: no zlib dependency any more.** It was only ever pulled in for `unzip.c`'s
`.zip`-reading support inside `data.c`, and nothing in the tree called into either
file — see this section's note below.

### Build

```sh
cd xrick/xrick
make                 # PLATFORM=ST (default) — release-ish build, full warning set
make PLATFORM=PC     # PLATFORM=PC instead — see config.h; GFXST art either way
make warn            # syntax-only pass over the game logic, no link (see Makefile's own comment)
make clean
```

Output: `xrick/xrick/xrick` (an ELF binary, always named `xrick` regardless of
`PLATFORM`; `make clean` before switching `PLATFORM` if you want to avoid relinking
confusion, since object files aren't tagged by platform either).

### Run

```sh
cd xrick/xrick
./xrick
```

**T22: no `-data <path>` argument any more, and none is needed.** Every asset —
sprites, tiles, room/level data, the demo script, and (since T19) the sound engine
itself — is a compiled-in `dat_*.c` table; nothing is read from disk at runtime.
Confirmed before removing it: `data_file_open`/`_read`/`_close`/`_seek`/`_tell`/
`_size` (`data.c`, the only thing `-data`'s path ever fed) had zero call sites
anywhere in the tree outside their own definitions — only `data_setpath`/
`data_closepath` were ever called (from `game_run`), and they did nothing but
open/close a handle that was never read from. `xrick/data/` on disk turned out to
hold only the pre-T19 era's WAV files, nothing the running game still needs; `data.c`,
`data.h`, `unzip.c` and `unzip.h` are deleted outright, and `game_run`/`main` no
longer take or thread through a path at all. `./xrick -h` lists the rest of the CLI
(`-demo`, `-submap`, `-nosound`, `-vol`, etc.).

Under WSL specifically: audio goes out through WSLg's PulseAudio → RDP audio-channel
path, which has substantial fixed latency (see `kb/audio-sndh.md` §11 and the T19
session that chased this down) — expected behavior for that path, not a bug in the
build. For latency-sensitive audio testing, build natively on Windows instead (§2).

**T20 bug found and fixed by running it, not by reading the diff:** after the SDL3
migration the game built clean and ran (audio confirmed by ear), but the window was
entirely black — caught only by the user actually looking at the WSLg window, since
neither the compiler nor a crash-free exit could have shown it. Root cause: the
game's raster texture packs `pald[i].a` as always `0` (alpha was never meant to carry
anything for this opaque framebuffer blit); SDL2 apparently defaulted new textures to
a blend mode that ignores alpha, SDL3 apparently does not, so an all-zero alpha
channel blended the whole frame down to the black `SDL_RenderClear()` colour
underneath it. Fixed with one explicit `SDL_SetTextureBlendMode(texture,
SDL_BLENDMODE_NONE)` in `sysvid_init` — this is a hypothesis about *why*, backed by
the fix working, not by reading SDL3's source for its actual default.

A second, separate rendering bug was found the same way on the **Windows** build
(§2) — `sysvid_update` computed the destination pointer into the locked SDL texture
from `fb_width * 4` instead of the *actual* pitch `SDL_LockTexture` hands back,
producing scrolling glitches/sprite misalignment on whatever backend pads texture
rows. Fixed to use the real `pitch` value. This did **not** fix the Windows visual
defect that prompted the investigation — see §2's note; the pitch fix is real and
correct on its own terms (no longer assumes an unpadded texture) but the actual
reported bug (glitchy scrolling, sprite mismatches, reproducible only on the native
Windows build, not WSL) is still open and unexplained.

---

## 2. Windows (Visual Studio / MSBuild)

### Dependencies

- **Visual Studio 2022 or later** with the **"Desktop development with C++"**
  workload — specifically the **MSVC v143 toolset** and a **Windows 10/11 SDK**.
  Verified with Visual Studio "18 Insiders"
  (`C:\Program Files\Microsoft Visual Studio\18\Insiders\`); both v143 (14.44) and a
  newer bundled toolset (14.51) were present and v143 was what the project was set
  to use. If your VS install only has an older toolset (e.g. v142/VS2019), either
  install the v143 component via the VS Installer or retarget the project to
  whatever you have.
- **vcpkg**, in manifest mode, for SDL3 (T20: was `sdl2`; T22: zlib dropped). Recent
  VS installs bundle one under `VC\vcpkg\vcpkg.exe` inside the VS install directory —
  that's what was used here; a standalone vcpkg install works too.
  `xrick/xrick/vcpkg.json` is the manifest (declares `sdl3` only, pinned to a
  `builtin-baseline`) — that pinned baseline commit was confirmed (via the registry's
  raw `versions/s-/sdl3.json` at that exact commit) to resolve `sdl3` to **3.4.16**,
  the same latest upstream release cited in §1. The old `..\..\lib\SDL2-2.0.9` /
  `..\..\lib\zlib1211` paths this project historically expected are gone — neither
  was ever present in the repo, which is why the solution didn't build before T19.

### One-time setup

```powershell
# Register vcpkg's MSBuild integration for your user account (writes a per-user
# props file; does not touch the repo). Only needs doing once per machine.
& "C:\Program Files\Microsoft Visual Studio\18\Insiders\VC\vcpkg\vcpkg.exe" integrate install

# Restore SDL3 for x64 (the only platform the project builds, T21). Manifest mode
# installs into xrick\xrick\vcpkg_installed\x64-windows\ (gitignored), not globally.
cd xrick\xrick
& "C:\Program Files\Microsoft Visual Studio\18\Insiders\VC\vcpkg\vcpkg.exe" install --triplet x64-windows
```

Adjust the vcpkg path to wherever your own VS install (or standalone vcpkg) actually
lives. This step builds SDL3 from source the first time (~30s, measured this
session) and is cached after that; re-running it after a `vcpkg.json` change (e.g.
T22's zlib removal) cleanly uninstalls whatever's no longer declared.

### Build

Command line (what was actually used to verify this, T21/T22):

```powershell
cd xrick\xrick
& "C:\Program Files\Microsoft Visual Studio\18\Insiders\MSBuild\Current\Bin\amd64\MSBuild.exe" xrick.vcxproj /t:Build
```

**Build the `.vcxproj` directly, not `xrick.sln`.** T21 added defaults so a bare
invocation with no `/p:Configuration`/`/p:Platform` builds Release/x64 — confirmed by
building both ways: `MSBuild xrick.vcxproj` (no switches) picks up the defaults and
produces `bin\Release\`; `MSBuild xrick.sln` (also no switches) ignores them and
builds `Debug` regardless, because MSBuild's solution wrapper hardcodes
`Configuration=Debug` when none is passed *before* the per-project defaults ever get
a chance to apply — a solution-file-level behavior with no per-file fix. Pass
`/p:Configuration=Release /p:Platform=x64` explicitly if you do build through the
`.sln` (e.g. from the IDE's Build Solution, which has its own configuration
dropdown and isn't affected by this).

Win32/x86 no longer exists as a target (T21) — the project now declares only
`Debug|x64` and `Release|x64`.

**2026-09-24 (RD1/RD2 split):** the project's file lists had not followed the split into
`include|src/rd1|rd2`. They now mirror the Makefile: every `*.c` in `src`, `src\rd1`, `src\rd2`
except the three `dat_*PC.c` (67 files, same as `make`), plus the audio engine; include paths
`include;include\rd1;include\rd2;src;src\rd1;src\rd2` (the Makefile's `INC`). `PLATFORM_ST` comes
from `config.h`'s default. `.filters` regenerated (rd1/rd2/audio_engine sub-folders). Checked:
Release x64 builds with 3 warnings, all in shared files outside rd1/rd2 (`sysarg.c` C4045, `sysvid.c` 2× C4101);
`xrick.exe -rd 2` RAM trace (`RD2_TRACE`, 600 frames of the attract demo) byte-identical to the WSL build.
When files are added to or removed from `src`/`include`, update the `.vcxproj` too.

A post-build step copies `SDL3.dll` from `vcpkg_installed\x64-windows\bin\` next to
the built exe automatically (vcpkg's own auto-deploy didn't engage with this
project's style of integration, so this is done explicitly in `xrick.vcxproj`); T22
dropped the equivalent `z.dll` copy since nothing links zlib any more.

### Output and run

| Config | Binary |
|---|---|
| Release (default) | `xrick\xrick\bin\Release\xrick.exe` |
| Debug | `xrick\xrick\bin\Debug\xrick.exe` |

```powershell
cd xrick\xrick\bin\Release      # or bin\Debug
.\xrick.exe
```

**T22: no `-data` argument needed here either** — see §1's note; it applies
identically on Windows.

**Open, unexplained Windows-specific rendering defect (2026-09-10, found by the
user running the native build, not by review):** scrolling glitches and sprite
misalignment that do **not** reproduce on the WSL build of the identical source.
Ruled out by direct inspection so far: `sysvid_update`'s texture-pitch assumption
(real bug, fixed — see §1 — but confirmed **not** the cause, since the defect
persisted afterward with the exact same symptoms); `rect_t`'s struct layout
(no packing pragmas or bitfields, identical on GCC/MSVC for x86-64); the
`map_map` row-copy loop in `scroller.c` (plain portable C); config.h's
`PLATFORM_ST`/`PLATFORM_PC` selection (both builds resolve to `PLATFORM_ST`
identically — confirmed from the actual `cl.exe`/`gcc` invocations in each build
log, neither passes an explicit `-D`/`/D` for it, both fall through to config.h's
same default). Not yet root-caused; needs a side-by-side screenshot comparison of
the same room/submap on both builds, or a memory-diff of the CPU framebuffer between
the two, to make further progress — guessing further from source reading alone
wasn't productive.

---

## 3. Known gap between the two build systems

The Makefile has a `PLATFORM=PC` switch (`config.h`'s `PLATFORM_ST`/`PLATFORM_PC`,
game behaviour only — art stays `GFXST` either way per `config.h`). **The vcxproj has
no equivalent** — it always builds `PLATFORM_ST` (config.h's default when neither
macro is defined) and, like the Makefile, excludes the PC-variant data files
(`dat_picsPC.c`, `dat_spritesPC.c`, `dat_tilesPC.c` — including them alongside the ST
versions would collide on symbol names at link time, same reason the Makefile filters
them out). Building `PLATFORM_PC` natively on Windows would need a
`PreprocessorDefinitions` addition to `xrick.vcxproj`; not done, since nothing in the
T19 audio work needed it.

## 4. Web (emscripten), RD1 only — on `master`

Analysis, plan and status: `../wasm.md`. Developed on branch `wasm`, merged into
`master` 2026-09-28 (the branch is deleted). Phase W1 = RD1 in the browser; `-rd 2` is
refused on the web until phase W2.

**Toolchain.** emsdk in `D:\d\EmSdk` (emscripten 6.0.10), driven from **Git Bash** (user
decision 2026-09-28; the emsdk is Windows-native). **`build.sh` registers the emsdk
environment itself** — a plain Git Bash needs nothing sourced beforehand. It first
checks that `EMSDK_DIR` (default `/d/d/EmSdk`) exists and holds `emsdk_env.sh` and
`upstream/emscripten/emcc`, sets `EMSDK_PYTHON` to emsdk's bundled python (plain `python`
is the Windows Store alias here) and sources `emsdk_env.sh` in its own shell; if `emcc` is
still missing it prints emsdk's output and stops.

**Build** — the web build is the second half of `./build.sh` (after the desktop build),
at the top of the port repo next to `build/` and `demo.sh`; the page files stay in
`build/emsdk/`:

```bash
./build.sh          # desktop + web, incremental; web into build/web/, desktop into build/win/ (both git-ignored)
./build.sh clean    # both from scratch -- needed for the web after a header change
./build.sh gz       # also gzip copies of the web files in build/web/gz/
```

Same sources and flags as the `Makefile` (PC data tables left out, `-fcommon`,
`-DPLATFORM_ST`, the warning set), SDL3 from emscripten's port (`-sUSE_SDL=3`), linked
with `em++` (`-sINVOKE_RUN=0 -sEXIT_RUNTIME=1`, `callMain`/`FS`/`_fflush` exported).
Output: `index.html`, `player.js`, `xrick.js` (~190 KB), `xrick.wasm` (~2.1 MB;
~0.8 MB gzipped). 168 clang warnings at `wasm` W1.5a — the web baseline, not comparable
with gcc's 230.

**Run.** Serve `build/web/` over http with `.wasm` as `application/wasm` (e.g.
`emrun build/web/index.html`), click the page to start (that also unlocks sound).
URL options: `?demo`, `?speed=N`, `?zoom=N`, `?keys=L-R-U-D-F`, `?nosound`, `?trace`
(adds a "download trace" button). `startInDemo` at the top of `player.js` makes the
page start in demo mode (off by default).

**Checked** (headless Chrome driven over the DevTools protocol): the demo's `-trace` is
byte-identical to the native SDL build's (55026 lines, 107 segments, after master
`89d0e1a`); gameplay pace 23.6 logic steps/s at default speed vs 23.9 native (40 ms
period = the ST's 25 steps/s; scroll frames are not in the trace); `?rd=2` refusal and
Esc ("game ended") shown on the page; audio context running at 48000 Hz.
