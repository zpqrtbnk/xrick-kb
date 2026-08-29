# Project Memory: Rick Dangerous (Reverse Engineering)

## Project Identity

- **Name**: Rick Dangerous I & II (...)
- **Author**: 
- **Platform**: Atari ST (and many others)
- **Genre**: Platform
- **Ghidra project name**: xrick, xrick2

## Key Facts

This is a **68K assembly** project.

We are reverse-engineering to **documented assembly source code**.

- NEVER decompile to C
- NEVER use `decompile_function` or `force_decompile`
- All analysis stays in the assembly domain
- This is a pure ASSEMBLY game, there is NOT p-code, no interpreter or virtual machine

## File Structure

Top-level files:

| File | Purpose |
|------|---------|
| **PLAN.md** | Remaining unknowns, progress and next steps |
| **MEMORY.md** | This file — analysis process notes and progress log |

Sub-directories:
| Directory | Purpose |
|-----------|---------|
| `attempt.*/` | Abandoned attempts at reverse-engineering the game |
| `disks/` | Rick Dangerous disk images |
| `ghidra.xrick/` | Ghidra project files for Rick Dangerous |
| `ghidra.xrick2/` | Ghidra project files for Rick Dangerous (II) |
| `re/` | Knowledge base of Rick Dangerous — all game knowledge organized by topic |
| `re2/` | Knowledge base of Rick Dangerous (II) — all game knowledge organized by topic |
| `xr/` | Source code (in C) of the original "xrick" remake of the game |

Knowledge base files in `re/`: see `re/README.md` for a full list.

---
