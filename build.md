# Building the port (`xrick/`)

How to build **xrick**, the C/SDL2 Rick Dangerous port that lives in `xrick/` (a
nested git repo; see `MEMORY.md` §9). Two independent build systems exist side by
side in `xrick/xrick/` — a `Makefile` for Linux/WSL, and `xrick.sln`/`xrick.vcxproj`
for native Windows via Visual Studio/MSBuild. Both build the same sources and default
to the same configuration (`PLATFORM_ST`, `GFXST` — see config.h); see §3 for the one
capability gap between them.

Both are verified working as of 2026-09-10 (T19's audio-latency investigation, see
`audio-sndh.md`). Exact tool versions below are what was actually used, not
guaranteed minimums; if you're on close-but-different versions and it doesn't build,
that's real information, not something to assume away.

---

## 1. Linux / WSL (the `Makefile`)

### Dependencies

- A C11 **and** C++17 compiler pair from the same toolchain — `gcc`/`g++`. The C++
  compiler is required now: `src/audio_engine/` (AtariAudio, T19) is C++, vendored
  and compiled alongside the game's C code.
- `make`
- SDL2 development headers/libs, discovered via `sdl2-config` (not pkg-config)
- zlib development headers/libs (`-lz`)

Verified with gcc/g++ 14.2.0 and SDL2 2.32.4 on Debian (WSL). Any reasonably recent
distro's packages should work; `sdl2-config --version` needs to run successfully
before the Makefile will produce correct `SDL_CFLAGS`/`SDL_LIBS`.

Debian/Ubuntu (including WSL):

```sh
sudo apt install build-essential libsdl2-dev zlib1g-dev
```

Fedora:

```sh
sudo dnf install gcc gcc-c++ make SDL2-devel zlib-devel
```

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
./xrick -data ../data
```

`-data ../data` isn't optional in practice — the default data path resolves
differently and `../data` (i.e. `xrick/data`, the sibling of `xrick/xrick/`) is where
the game's assets actually live. `./xrick -h` lists the rest of the CLI (`-demo`,
`-submap`, `-nosound`, `-vol`, etc.).

Under WSL specifically: audio goes out through WSLg's PulseAudio → RDP audio-channel
path, which has substantial fixed latency (see `audio-sndh.md` §11 and the T19
session that chased this down) — expected behavior for that path, not a bug in the
build. For latency-sensitive audio testing, build natively on Windows instead (§2).

---

## 2. Windows (Visual Studio / MSBuild)

### Dependencies

- **Visual Studio 2022 or later** with the **"Desktop development with C++"**
  workload — specifically the **MSVC v143 toolset** and a **Windows 10/11 SDK**.
  Verified with Visual Studio "18 Insiders"
  (`C:\Program Files\Microsoft Visual Studio\18\Insiders\`); both v143 (14.44) and a
  newer bundled toolset (14.51) were present and v143 was what the project was set
  to use. If your VS install only has an older toolset (e.g. v142/VS2019), either
  install the v143 component via the VS Installer or retarget the project
  (`xrick.vcxproj`'s four `<PlatformToolset>` entries) to whatever you have.
- **vcpkg**, in manifest mode, for SDL2 and zlib. Recent VS installs bundle one under
  `VC\vcpkg\vcpkg.exe` inside the VS install directory — that's what was used here;
  a standalone vcpkg install works too. `xrick/xrick/vcpkg.json` is the manifest
  (declares `sdl2` and `zlib`, pinned to a `builtin-baseline`). The old
  `..\..\lib\SDL2-2.0.9` / `..\..\lib\zlib1211` paths this project historically
  expected are gone — neither was ever present in the repo, which is why the
  solution didn't build before T19.

### One-time setup

```powershell
# Register vcpkg's MSBuild integration for your user account (writes a per-user
# props file; does not touch the repo). Only needs doing once per machine.
& "C:\Program Files\Microsoft Visual Studio\18\Insiders\VC\vcpkg\vcpkg.exe" integrate install

# Restore SDL2 + zlib for whichever platform(s) you're building. Manifest mode
# installs into xrick\xrick\vcpkg_installed\<triplet>\ (gitignored), not globally.
cd xrick\xrick
& "C:\Program Files\Microsoft Visual Studio\18\Insiders\VC\vcpkg\vcpkg.exe" install --triplet x64-windows
& "C:\Program Files\Microsoft Visual Studio\18\Insiders\VC\vcpkg\vcpkg.exe" install --triplet x86-windows   # only if you also need Win32
```

Adjust the vcpkg path to wherever your own VS install (or standalone vcpkg) actually
lives. This step downloads and builds SDL2/zlib from source the first time (took
about 40 seconds per triplet here) and is cached after that.

### Build

Command line (what was actually used to verify this):

```powershell
cd xrick\xrick
& "C:\Program Files\Microsoft Visual Studio\18\Insiders\MSBuild\Current\Bin\amd64\MSBuild.exe" xrick.sln /p:Configuration=Release /p:Platform=x64 /t:Build
```

`Configuration` is `Debug` or `Release`; `Platform` is `x64` or `x86` (the solution's
name for the project's `Win32` platform — `/p:Platform=Win32` is rejected by MSBuild
at the solution level, `x86` is what `xrick.sln` actually maps). All four
combinations build clean as of this writing.

Or open `xrick\xrick.sln` in Visual Studio and Build Solution — should work the same
way through the same manifest, though the command-line path above is the one this
was actually tested with. If the IDE doesn't auto-restore the vcpkg manifest, run
the `vcpkg install --triplet ...` step above manually first.

A post-build step copies `SDL2.dll` and `z.dll` from `vcpkg_installed\<triplet>\bin\`
next to the built exe automatically (vcpkg's own auto-deploy didn't engage with this
project's style of integration, so this is done explicitly in `xrick.vcxproj`).

### Output and run

| Config | Platform | Binary |
|---|---|---|
| Release | x64 | `xrick\xrick\x64\Release\xrick.exe` |
| Debug | x64 | `xrick\xrick\x64\Debug\xrick.exe` |
| Release | x86 (Win32) | `xrick\xrick\Release\xrick.exe` |
| Debug | x86 (Win32) | `xrick\xrick\Debug\xrick.exe` |

```powershell
cd xrick\xrick\x64\Release      # or wherever your config landed, per the table above
.\xrick.exe -data ..\..\..\data # x64 configs: 3 levels up to xrick/data
# .\xrick.exe -data ..\..\data  # x86/Win32 configs: only 2 levels up
```

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

## 4. Not covered here

`xrick/README.md` mentions emscripten build adjustments ("so it can build with
emscripten"). Neither build path above touches that, and it was not exercised or
verified as part of this document — treat any emscripten build claim as unverified
until someone actually runs it.
