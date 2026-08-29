# Project Memory — Rick Dangerous (Atari ST) Reverse Engineering

Slow-changing knowledge about **the project itself**: what we are working on, the rules
we work under, decisions that are settled, and lessons that cost something to learn.

- Game knowledge lives in **`re/`** (entry point: `re/README.md`).
- Knowledge about **the pre-existing C/SDL port** lives in **`xrick/re/`** (entry point:
  `xrick/re/README.md`). See §9.
- Current status, open work and next steps live in **`PLAN.md`**.
- Nothing here should duplicate either. If a fact is about the *game*, it belongs in
  `re/`; if it is about *where we are*, it belongs in `PLAN.md`.

---

## 1. Identity

| | |
|---|---|
| Game | Rick Dangerous (Core Design, 1989) |
| Platform | Atari ST, Motorola 68000 |
| Ghidra project | `ghidra.xrick` → single program `atari_ram.bin` |
| Primary artifact | `re/atari_ram.bin` — 327,680-byte Hatari RAM snapshot. **Authoritative for every address in the knowledge base.** |
| Secondary artifact | `re/atari_ram_1M.bin` — full 1 MB capture, used only as the source of the complete PCM samples |
| Source build | `disks/chaos43/RICK.PRG` — the Chaos #43 compilation disk; the build the snapshot was taken from |

## 2. Hard rules

- **This is a 68K assembly project.** We reverse-engineer to *documented assembly*.
  Never decompile to C; never call `decompile_function` or `force_decompile`. All
  analysis stays in the assembly domain.
- The game is **pure assembly** — no p-code, no interpreter, no virtual machine.
- **Never open, read or reference `ghidra.xrick2` / `xrick2-prg`** (on disk at
  `ghidra.xrick2/`, or `mac/ghidra.xrick2/`). It is an untracked leftover and is
  permanently out of scope, in this session and any future one.
- Do not modify `CLAUDE.md` or `README.md`.

## 3. The target bar

`re/` must be complete enough to **mechanically re-code the game with identical
behaviour** — byte-for-byte correspondence with the original, not behavioural
similarity. Every assessment of progress is made against that bar.

## 4. Repository layout

| Path | Purpose |
|---|---|
| `MEMORY.md` | This file — project-level memory |
| `PLAN.md` | Current state, open work, next steps |
| `re/` | The knowledge base: all game knowledge, organised by topic |
| `ghidra.xrick/` | Ghidra project (the analysis) |
| `disks/` | Rick Dangerous disk images, incl. `chaos43/` |
| `attempt.0/`, `attempt.1/` | Abandoned earlier attempts, deliberately kept in place |
| `ghidra.xrick2/` | Out of scope — see §2 |
| `xrick/` | **"The port"** — a clone of the xrick C/SDL clone (nested git repo). See §9 |
| `xrick/re/` | Our knowledge base *about the port*, mirroring `re/`'s structure |
| `hatari.sh`, `env.sh` | Emulator / environment helpers |

## 5. Where knowledge lives, and which layer wins

`re/README.md` carries the full reading order. The authority order, which matters
whenever two documents disagree:

1. **Ghidra** (`ghidra.xrick`) — the only layer verified directly against bytes.
2. **`re/algo-*.md`** — exact transcriptions; source of truth for *behaviour*.
   `re/data-structures.md` and `re/strings.md` are authoritative for *data*.
3. **Everything else** — `functions.md`, `entities.md`, `rick.md` are **indexes and
   narrative** and carry no derived detail by design.

Two overrides on top of that:

- For a **byte-identical** reimplementation, `re/byte-identity.md` overrides the prose.
  The `algo-*.md` transcriptions are C-like and therefore lossy about operand *width*,
  *signedness* and *flag* semantics.
- **Do not add behavioural detail to an index file.** That layering was introduced
  2026-08-28 after `functions.md` and `entities.md` drifted three separate times by
  duplicating facts that lived elsewhere.

## 6. Provenance facts worth not rediscovering

- **The game only materialises in RAM.** `RICK.PRG` is a three-layer compressed
  executable (custom backward-LZ, an HPack trainer stub, then an LSD layer); the packed
  disk files contain no recognisable game code. All analysis is against the live dump.
- **The address base is not fixed.** Rick Dangerous is a GEMDOS program, so TOS chooses
  its load address. On the correct boot path the delta is **`-0x2054`**, which is also
  `atari_ram_1M.bin`'s offset from `atari_ram.bin`. Measure it every session; never
  hardcode it. `build_sndh.py::find_delta()` is canonical.
- **A RAM snapshot captures a *running* state, not a clean one.** Ours was taken with
  the title music mid-play. Code lifted out of it inherits whatever the program happened
  to be doing, so re-host it by calling the subsystem's own init/cleanup routines rather
  than trusting captured values.

## 7. Settled — do not re-open

| Question | Decision |
|---|---|
| Level loading at runtime | **There is none.** Two traps total (`Super`, `Setscreen`); all four levels resident. Do not re-search for GEMDOS/BIOS/XBIOS I/O — the answer is "absent", not "not yet found". |
| ASCII string search | Done — **64 strings** in `re/strings.md`. Text is ASCII but **`0xFF`-terminated**; Ghidra's analyzer had *Require Null Termination* on. The old "text isn't ASCII" advice is **retracted**. |
| Slot-0 block pushing | **No such mechanic exists.** Slot 0 is the scripted crusher/boulder hazard, moved by `scripted_trap_update` through `A0`. |
| The missing 12,880 bytes | Recovered via `atari_ram_1M.bin`; was stack + PCM, never code. |
| Re-basing onto the 1 MB dump | **No.** `atari_ram.bin` numbering stays authoritative; convert with `1M_address = doc_address − 0x2054`. |
| Pixel-diffing rooms against Hatari | **No.** The user validates renders visually and has confirmed them correct. |
| Completeness metrics | `analyze_function_completeness` emits **no score at all** — it measures conformance to a plate-comment template this project deliberately does not use. Do not re-run it expecting a coverage number. |
| `disks/rd.st` | **Not the analysed build.** A Fuzion cracktro compilation with its own loader and a different, stage-dependent relocation. Boot `disks/chaos43/RICK.PRG`. |
| Trainer keys F1–F3 | **Leave off.** They patch game code and would invalidate any comparison against `algo-*.md`. |
| `attempt.0/`, `attempt.1/`, `disks/` | **Stay exactly where they are.** Do not move, archive or reorganise. |
| `ghidra.xrick2` | Permanently out of scope. |

## 8. Method lessons

- **Prefer disassembly over decompiler output.** Four documented errors came from
  trusting the decompiler: `RoomHeader.pPlacements` (+0xA, not +5); the `lea`-loaded A2
  effect callbacks it hid entirely; the `move.b #n,D0` AI-mode arguments it dropped as
  dead stores; and `probe_entity_tile_collision`'s carry-flag return read as a `D0` value.
- **Derive facts mechanically, then diff against the documents.** Reading transcriptions
  to check transcriptions does not work — most byte-identity defects were invisible to
  that approach and only appeared under enumeration of the raw encodings.
- **Cross-check structures against raw bytes.** The `SpriteEntity` X/Y axis swap and the
  `LevelStartInfo` 4-byte base error both survived multiple passes because prose was
  never checked against the table contents.
- **An empty address-based search does not mean the code is absent.** The slot-0 "block
  mover" was hunted for passes because both the spawn and the motion write through
  address registers. When a program-wide search for writes to a known global comes up
  empty, ask whether the access is register-indirect.
- **Beware tables cut short by spurious functions.** `sprite_type_dispatch` read as 70
  entries for several passes because a bogus function had been created inside it. The
  real count is 74.
- **Check analyzer options before concluding "absent".** The ASCII Strings analyzer's
  *Require Null Termination* default hid every string in the game.
- **Enumerating the readers of a global is decisive** in a way that reading
  transcriptions is not. Several probes that looked like they needed a live run fell to
  a Ghidra xref census instead.
- **Verify agent work before trusting reports.** Two of five forks in the multi-agent
  pass reported "done" after producing incoherent, self-referential output without doing
  any work; caught only by checking live Ghidra state. Both recovered when told plainly
  "you are not the orchestrator; do the work yourself; do not call Agent".
- **Never use Hatari's `:quiet` as a detector.** It suppresses per-hit output and the
  breakpoint listing has no hit counter, so a firing breakpoint looks identical to one
  that never fired. Use `:trace :once`.

## 9. "The port" — xrick, the prior C/SDL clone

Registered 2026-08-29. A second, independent reverse-engineering of Rick Dangerous
already exists: **xrick**, by "bigorno" (Arnaud Nolen), 1998–2005, re-coded in C on SDL.
It is cloned into `xrick/` (its own nested git repo, remote
`https://github.com/zpqrtbnk/xrick.git`, commit `c2aef3d`, version string `050500`).
Our analysis of it lives in `xrick/re/` — 11 documents mirroring `re/`'s structure, with
`xrick/re/xref.md` as the comparison worksheet.

Facts worth not rediscovering:

- **The port's logic is PC-derived; only its artwork is Atari ST.** Every algorithm
  comment cites PC-style addresses (`ASM 12CA`, `ASM 0FBC`) in a `0x0000`–`0x2FFF` space;
  the build is configured `GFXST` for graphics only. A behavioural difference against our
  ST reversal may therefore be a genuine PC-vs-ST difference, a port error, **or ours** —
  three candidates, and none may be assumed. This governs every comparison.
- **`ASM nnnn` comments do not map onto ST addresses.** No constant offset exists; they
  are different executables for different CPUs. Never try to translate them.
- **The port is a playable reconstruction, not a fidelity project.** It normalises struct
  layouts into C types, drops two entity fields as "never used", and its own comments
  admit it cannot explain several mechanisms. It discards exactly the width/signedness
  information that `re/byte-identity.md` exists to capture.
- **The port has no sound engine.** All audio is pre-rendered WAVs made by ear; there is
  no PSG data anywhere. `re/algo-music.md` and our SNDH have no counterpart, and the port
  can contribute nothing there.
- **It also has no timing model** — a 75 ms software-slept state machine, no VBlank, no
  interrupts. Per-frame *counts* are comparable; durations are not.
- **Licence is unsettled.** Source headers say "All rights reserved" and point at a
  README that carries no terms. Use the port as a reference for understanding only; do
  not copy its code into this project's output without settling this.

Already cross-validated on first reading (both sides independent): the 523-record
placement table, 47 rooms, all eight tile-attribute bits, all five common trigger bits,
the enemy spawn-slot pools 9–11 / 4–8, the placement X/Y bit packing, the `-0x580` jump
impulse, `+0x80` gravity with a `0x800` clamp, and the super-pad rebound `0xFE - vel`.
Seventeen numeric discrepancies and seven semantic ones are listed in `xrick/re/xref.md`.

**One finding lands on our side, not the port's:** `re/data-structures.md` gives two
conflicting readings of placement flag bit `0x02` (line 261 "spawn into `sprite_list[0]`"
vs line 67 "bullet passes through"). The port corroborates the first. This is an internal
inconsistency to fix regardless of the comparison.
