# kb2 — Rick Dangerous 2 (Atari ST) knowledge base

Everything learned about **Rick Dangerous 2** (Core Design, 1990, Atari ST /
68000) lives here: the RAM captures it was all derived from, the reverse-
engineering documents, and the one finished artifact.

Rick Dangerous **1** is a different game and a separate effort — see `../re/`
(built from `disks/chaos43/RICK.PRG` and its own RAM dump).

## Contents

| File | What it is |
|---|---|
| `xrick2-ref.md` | **Start here.** Topic-organised index of current best-known facts per subsystem, each with a pointer to its evidence. |
| `xrick2-wk.md` | The evidence log: full decompiles, addresses, struct layouts, reasoning. Append-only, chronological. 4522 lines. |
| `xrick2-gaps.md` | Every contradiction, hedged assumption and open question, with a prioritised consolidated table at the top. |
| `PORTING.md` | What a mechanical port still needs, by area, with a suggested order of attack. |
| `sound-ref.md` | The sound engine, complete. Separate from the three above because sound was explicitly out of scope for the logic effort — it was then done anyway, and finished. |
| `build_sndh.py` | Builds `rick2_sfx.sndh` from `prg2-ram.bin`. Run from anywhere; paths are script-relative. |
| `rick2_sfx.sndh` | **Finished artifact.** All 92 in-game sounds as a standard SNDH file. Confirmed working. |
| `prg2-ram.bin` | 1 MB ST RAM snapshot, attract-mode demo running. The source for essentially all live validation, and the input to `build_sndh.py`. |
| `dump_hnkload_hit1.bin` | 1 MB snapshot at the moment `RICK_01.HNK` loads (`A1=$3EFC0`). |
| `dump_hnkload_hit2.bin` | 1 MB snapshot at the moment `RICK_02.HNK` loads (`A1=$65300`). |

All three `.bin` files are flat images with **file offset == ST physical
address**, verified — so any address in the docs can be read directly out of
them, and they are what the Ghidra project `../ghidra.xrick2/xrick2-prg.gpr`
was imported from (program `/prg2-ram.bin.0`).

## Scope

The reverse-engineering effort targets a **mechanical port of the game
logic**: struct definitions, spawn/trigger tables, enemy AI, physics, input.
Render/blit was excluded by design and is untouched. Sound was also excluded,
then solved separately and completely (`sound-ref.md`).

For what a port would still need beyond this, see `xrick2-gaps.md`'s
consolidated table and `PORTING.md`.

## Conventions worth knowing before adding to this

- Disassembly comes from Ghidra MCP tools only, never raw byte inspection or
  another disassembler.
- `list_globals` / `get_xrefs_to` have been caught silently missing real
  references at least three times — cross-check with `audit_global` or
  `get_function_pcode` before concluding a symbol is unread.
- Prefer raw 68000 disassembly over the decompiler for byte-vs-word struct
  offsets; the decompiler has produced a real, documented contradiction there.
- Re-read the bytes for any load-bearing address rather than trusting a claim
  in a document. The sound effort found four separate misread addresses that
  had been recorded as "confirmed", one of which caused a shipped regression.
