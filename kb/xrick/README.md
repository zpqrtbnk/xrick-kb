# xrick — Knowledge Base for "the port"

Knowledge base for **xrick**, a pre-existing clone of Rick Dangerous produced by
reverse-engineering the game and re-coding it in C on top of SDL. This directory
documents *the port as it exists*, so that it can later be compared, function by
function and table by table, against our own reverse-engineering of the Atari ST
binary in `../`.

**This directory describes someone else's work.** It is not a second opinion on the
original game and carries no authority over `../`. Where the port and our RE
disagree, that disagreement is a *finding to be investigated*, recorded in
`divergences.md` and `xref.md` — never silently resolved in either direction.

## Identity

| | |
|---|---|
| Project | xrick, by "bigorno" (Arnaud Nolen), 1998–2005, SDL2 update 2019 |
| Repository | `https://github.com/zpqrtbnk/xrick.git` |
| Commit analysed | `c2aef3d` "Fixing Emscripten loop and timing" (branch `master`) |
| Version string | `VERSION "050500"` — the unreleased "May 2005" tree |
| Language | C89-flavoured C, ~10 000 lines of logic + ~55 000 lines of generated data tables |
| Platform layer | SDL2 (video, audio, events, timing); optional zlib; builds for Win32 (MSVC `.vcxproj`) and emscripten/WASM |
| Graphics variant built | **`GFXST`** — Atari ST artwork (`config.h`); `GFXPC` (IBM CGA) exists but is not the configured build |
| Location on disk | `xrick/` (the clone), sources under `xrick/xrick/src` and `xrick/xrick/include` |

## The single most important fact

**The port's game logic was reverse-engineered from the IBM PC version, and only its
artwork is Atari ST.** Every algorithmic comment in the source cites 16-bit PC-style
addresses (`ASM 12CA`, `ASM 2520`, `ASM 0FBC`), whereas our knowledge base is built on
ST physical addresses in the `0x48000`–`0x49FFF` range. Where the two describe the
same behaviour, that is genuine cross-validation. Where they differ, the difference may
be **PC-versus-ST**, not an error on either side. See `provenance.md`.

## Read in this order

| File | Contents |
|---|---|
| `provenance.md` | Where the port came from, what it was derived from, what its comments mean, and how far it can be trusted |
| `architecture.md` | Build layout, module map, the frame loop and the game state machine, the platform layer |
| `data-model.md` | Every struct, every table, sizes, coordinate systems, and the flag bits |
| `algo-player.md` | Rick: movement, jump, climb, crawl, stop/fire, death |
| `algo-entities.md` | The entity system: slots, dispatch, the four enemy types, pickups, bomb, bullet |
| `algo-level.md` | Maps, submaps, blocks, expansion, chaining, scrolling, mark activation |
| `algo-render.md` | Frame buffer, tiles, sprites, depth, rectangles, HUD |
| `algo-system.md` | Screens, input, sound, timing, data files, command line |
| `assets.md` | What data ships in the port, in which encoding, and where it came from |
| `divergences.md` | Port-specific hacks, dead code, known bugs, and PC/ST split behaviour |
| `xref.md` | **The comparison worksheet** — port ↔ `../` correspondence, matches found, and open questions |

## Conventions used here

- File references are relative to the clone root, e.g. `xrick/src/e_rick.c:143`.
- "ASM nnnn" quoted from a source comment is reproduced verbatim and is **the port
  author's PC-side address**, never one of ours.
- Facts are marked **verified** (read directly in the source at the cited line),
  **inferred** (follows from the source but not stated), or **claimed** (asserted by a
  source comment or the README, not independently checked).
- Sizes and counts were measured from the data tables, not taken from the `#define`s,
  wherever the two could differ; both are given when they disagree.
