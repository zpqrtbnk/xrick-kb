# Rick Dangerous (Atari ST) — Knowledge Base

Reverse-engineering knowledge base for Rick Dangerous (Core Design, 1989), Atari ST /
Motorola 68000, derived from a Hatari RAM snapshot (`atari_ram.bin`) analysed in
Ghidra (project `ghidra.xrick`, program `atari_ram.bin`).

**Goal:** become complete enough to *mechanically re-code the game with identical
behaviour*. Current estimate against that bar: **~98%**. The code is fully reversed
(every function named, every non-trivial one transcribed); graphics are extracted and
visually validated; all 47 room maps render; the sound engine is packaged as a playable
SNDH, confirmed by ear with every PCM sample intact; and nine byte-identity audits have
been run to completion. The eight behavioural details that wanted a live Hatari run are
**7 resolved, 1 optional** — see `hatari.md` for the harness and the evidence.

**`../PLAN.md` is the authoritative record of what is still open.** Project-level rules,
settled decisions and method lessons are in `../MEMORY.md`.

## Authority order

When two documents disagree, trust in this order:

1. **Ghidra** (`ghidra.xrick`) — the only layer verified directly against bytes.
2. **`algo-*.md`** — exact transcriptions; the reimplementation source of truth for
   *behaviour*. `data-structures.md` and `strings.md` are authoritative for *data*.
3. **Everything else** — `functions.md`, `entities.md`, `rick.md` are **indexes and
   narrative**. They carry no derived detail by design.

**For a byte-identical reimplementation, `byte-identity.md` overrides the prose.** The
`algo-*.md` transcriptions are C-like and therefore lossy about operand *width*,
*signedness* and *flag* semantics; that document records where those differ from the
instruction encodings, and which transcriptions are deliberately non-literal.

That layering was introduced 2026-08-28 after `functions.md` and `entities.md` drifted
three separate times by duplicating facts that lived elsewhere. **Do not add
behavioural detail to an index file** — put it in the owning document and link to it.

## Read in this order

| File | Contents |
|---|---|
| `rick.md` | Project narrative: what this binary is, how it was obtained, what's known, what's left |
| `memory_map.md` | Atari ST memory layout, hardware registers, exception vectors, **capture limits** |
| `functions.md` | All 133 functions by subsystem, with behaviour and confidence |
| `data-structures.md` | All 10 structs, the level-data model, tile-attribute bits, and the sprite frame format |
| `entities.md` | The 74-entry entity dispatch table and the collision/interaction suite |
| `strings.md` | All in-game text, the character encoding, and the font mapping |
| `assets-manifest.md` | Extracted graphics: formats, palette, and what's in `assets/` |
| `hatari.md` | **Dynamic verification**: the Hatari harness, how we drive it, and the eight behavioural probes |
| `byte-identity.md` | **Fidelity audit** — mechanical checks that the KB corresponds byte-for-byte to the original; all nine complete, 15 defects found and fixed. **Read before reimplementing.** |

### Transcriptions (`algo-*.md`) — exact, re-codable pseudocode

Produced 2026-08-28. These are the reimplementation source of truth: real constants,
preserved branch order, named globals/fields, documented register calling
conventions. ~4,400 lines covering every non-trivial function.

| File | Subsystem |
|---|---|
| `algo-player.md` | `player_controller`, projectiles, player collision, death |
| `algo-render.md` | sprite blitter, background blit, HUD, level start/intro |
| `algo-entities.md` | enemy AI, scripted traps, pickups, triggers, collision suite |
| `algo-level.md` | spawning, room scroll, tile decode — **includes the tilemap encoding** |
| `algo-music.md` | PSG engine, channel coroutines — **includes the sequence opcodes** |
| `algo-system.md` | main loop, interrupts, timing, palette, text, high-score entry |

`atari_ram.bin` is the primary artifact. Ghidra plate comments carry the detailed
per-function evidence trail; these documents are the navigable summary, and where the
two ever disagree, **Ghidra is authoritative** (it is the thing that was actually
verified against bytes).

## Conventions

- Addresses are Atari ST physical addresses = offsets into `atari_ram.bin`.
- Every claim carries a confidence marker: **confirmed** (traced to disassembly or
  raw bytes), **likely** (strong inference), **guess**, or **needs dynamic
  verification** (would require a live Hatari run). Do not silently promote a guess.
- Ghidra's naming-quality gate prefixes struct fields Hungarian-style (`n`=short,
  `w`=word, `b`=byte, `p`/`a`=pointer/array). That's a tool artifact; functions use
  plain `snake_case`.

## Standing warnings

- **Never open or reference `ghidra.xrick2` / `xrick2-prg`.** Untracked leftover,
  permanently out of scope.
- ~~**Don't re-run ASCII string search.**~~ **RETRACTED 2026-08-28 — this advice was
  wrong.** The game's text *is* ASCII; it is merely **`0xFF`-terminated instead of
  NUL-terminated**, and Ghidra's ASCII analyzer had *Require Null Termination*
  enabled, so it found nothing. A scan for `0xFF`-terminated printable runs recovers
  **64 strings**: high-score names, the level names (`SOUTH AMERICA`, `EGYPT`,
  `SCHWARZENDUMPF CASTLE`, `MISSILE BASE`), the name-entry grid, and the full level
  intro stories at `0x4B8FE`+. Note the character remapping: `^` = space,
  `\` = `.`, `[` = `,`, `]` = `?`. The font at `0x1B01E` is indexed by the raw
  character byte.
- **Don't re-search for GEMDOS `Fopen`/`Fread`.** Exhaustively searched: the only
  `TRAP #1` in the snapshot is `Super(0x5324C)`. The answer is "absent", not "not yet
  found".
- **Prefer disassembly over decompiler output for data layout.** Two documented
  errors came from trusting the decompiler (a struct offset, and `lea`-loaded
  callbacks it hid entirely).
