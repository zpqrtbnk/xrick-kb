# Provenance — where the port came from, and how far it can be trusted

## Origin

From the clone's own `README.md` (**claimed**):

> **xrick** is a clone of Rick Dangerous, produced by carefully reverse-engineering the
> PC and Atari versions of the game, and re-coding in C.

The repository is a re-publication of code that was previously distributed only as ZIP
files from `http://www.bigorno.net/xrick`. It contains, per that README:

- the "Dec 12th, 2002" release (`#021212`), the last one published in 2002;
- the "May, 2005" release (`#050500`), never released, "a bit cleaner";
- an SDL → SDL2 port;
- adjustments for building with emscripten.

The working tree at `c2aef3d` is the **`050500`** tree (`xrick/include/config.h:19`),
already converted to SDL2 and emscripten-capable. The other releases are not present as
separate directories or tags in this clone — `git tag` is empty and `master` is the only
branch. **Verified.**

## The logic is PC-derived; the artwork is ST

This is the fact that governs every comparison we will make.

**Evidence that the logic came from the IBM PC version:**

1. Every algorithm comment cites a 16-bit address of PC shape: `ASM 12CA` (e_rick
   action), `ASM 2520` (ent_reset), `ASM 0FBC` / `103E` (the environment probe),
   `ASM 113E` (box test), `ASM 0cc3` (map init), `ASM 0c08` (map chain). These live in a
   `0x0000`–`0x2FFF` space, consistent with an MS-DOS `.EXE` segment offset and
   inconsistent with the ST build, whose code our RE places at `0x48000`+.
   **Verified** across `e_rick.c`, `ents.c`, `maps.c`, `util.c`, `e_them.c`.
2. Comments name PC hardware and PC data conventions as the baseline and treat ST as the
   deviation: `sprites.h:1255` describes a sprite as "4 columns and 0x15 rows of
   (U16 mask, U16 pict), each pair representing 8 pixels (**cga encoding**, two bits per
   pixel)" — that is the primary description; the ST format is added afterwards.
3. `e_bomb.c:74` — "Atari ST dynamite sprites are not centered the way **IBM PC sprites
   were** ... need to adjust things a little bit", followed by a `GFXST`-only
   `x += 4; y += 5` fixup. The PC layout is the reference frame being corrected *to*.
4. Absolute RAM addresses appear as PC-side annotations: `e_sbonus.c:47-49` marks
   `e_sbonus_counting` as `6DD5`, `e_sbonus_counter` as `6DDB`, `e_sbonus_bonus` as
   `291A-291D`; `util.c:88-89` marks the two environment-flag outputs as `6DBA` and
   `6DAD`; `game.c:484` marks the RNG seed increment as `(0270)`.

**Evidence that the artwork is ST:** `config.h:22` defines `GFXST` and undefines
`GFXPC`. The ST data files (`dat_tilesST.c`, `dat_spritesST.c`, `dat_picsST.c`) are the
ones compiled. The default high-score table also differs by variant (`game.c:79-101`),
with the `GFXST` list being SIMES / JAYNE / DANGERSTU / KEN / ROB'N'BOB / TELLY / NOBBY /
JEZEBEL. **Verified.**

**Consequence for the comparison.** The port is a *hybrid*: PC game logic driving ST
pixels. Our `../` is a pure ST 68000 build. Therefore:

- Agreement between the two is strong evidence about the game's *design*, since it
  survives two independent reversals of two different ports.
- Disagreement has three possible causes, and they must be distinguished before any
  conclusion is drawn:
  1. the PC and ST builds genuinely differ (Core Design changed the code per platform);
  2. the port author made an error or a deliberate simplification;
  3. **we** made an error.

Nothing in this directory may assume cause (2) by default.

## ✅ The PC code segment is now on hand, and the addresses check out

`kb/ibmpc_cs.bin` (65,535 bytes) is a dump of the game's **code segment on an IBM PC**,
imported into the Ghidra project as `x86:LE:16:Real Mode` at base `0000:0000`. Dense
8086 code occupies `0x0000`-`0x2FFF` (82-96% non-zero per 4 KB); beyond `0x3000` the
segment is essentially empty. **Every address the port cites falls inside that populated
range** (`0x0025`-`0x2792`).

**Correspondence is confirmed**, most cleanly at `map_resetMarks`, which the port cites
as `ASM 0025`:

```
0000:001F  MOV BX, 0x88F0          ; map_marks base (PC data segment)
0000:0022  MOV CX, 0x20B           ; 0x20B = 523  <- the mark count
0000:0025  AND byte ptr [BX], 0x7F ; clear MAP_MARK_NACT (0x80)   <- cited address
0000:0028  ADD BX, 5               ; mark_t stride = 5 bytes
0000:002B  LOOP 0000:0025
```

That is the port's `map_resetMarks` instruction for instruction, at the cited offset,
with **523** and the **5-byte mark stride** both visible as immediates.

Two further structural confirmations: the box-test code near `0000:12B9` uses
`ADD AL,0x11` against `[SI+2]` and `[SI+0x0E]` — matching `ent_t`'s documented `x` at
`b02` and `w` at `b0E`, and the port's `x + 0x11` box formula; and the tail of
`ent_actvis` near `0000:21CE` zeroes `[SI+0x28]`, `[SI+0x2A]`, `[SI+0x2C]` (`c2`,
`ylow`, `offsy`) before `ADD DI,5` to step to the next mark.

**The `ASM nnnn` comments are offset by a constant `+0x17E` — discovered 2026-09-02.**
This was initially read as "citations land a few bytes off". They do not: over the code
region they are systematically **`0x17E` low**, and adding `0x17E` lands on the function
entry exactly:

| Port comment | Routine | `+0x17E` | Confirmed at that address |
|---|---|---|---|
| `ASM 103E` | `u_envtest` | `0x11BC` | prologue `PUSH AX/CX/BX/DX`, masks `0x6D`/`0x6F`/`0x7D` |
| `ASM 113E` | `u_boxtest` | `0x12BC` | `ADD AL,0x11` against `[SI+2]`/`[SI+0x0E]` |
| `ASM 11CD` | `e_bomb_hit` | `0x134B` | `MOV AL,[0x7EE0]`, the `-4`/`+0x20`/`+0x1D` box |
| `ASM 18CA` | `e_bomb_action` | `0x1A48` | bomb ticker `[0x7D81]` decrement at `0x1A47` |
| `ASM 1851` | `e_rick_gozombie` | `0x19CF` | sets `[0x7D70]` (`offsy`) |
| `ASM 17DC` | `e_rick_z_action` | `0x195A` | — |

⚠️ **The delta is NOT global, and must not be relied on.** `map_resetMarks` (`ASM 0025`)
sits at `0x0025` with **no** offset, and `e_them_gozombie` (`ASM 237B`) is at `0x24C3` —
**`+0x148`**, verified by content. `+0x17E` holds for the directly-called helpers and
breaks on the dispatch-reached entity handlers. Nor can it be checked statistically: with
78 recovered functions in ~12 KB, most candidate deltas hit something by chance. **Locate
by content signature and confirm structurally** (see `../../review-log.md` R3.10).
So the segment is not uniformly shifted — different modules landed at different
offsets than the port author's disassembly. Treat `+0x17E` as a strong hypothesis to test
per routine, not a universal transform, and always confirm by structure at the target.

**Consequence: the port's numbers can now be checked against the PC build directly** —
the question that `PLAN.md` T8 exists to answer.

## What "ASM nnnn" comments are, and are not

They are the port author's cross-references into their own disassembly of the PC
executable, left in place as documentation. They are useful in exactly two ways:

- as **structure**: they tell us which C function corresponds to one original routine,
  and where the author split one routine into two (`e_rick_action` / `e_rick_action2`)
  or merged several (`e_them_t1_action` covering both 1a and 1b).
- as **identity**: two functions carrying the same address (e.g. `e_them_t1a_action`
  and `ent_actf[0x07]`, both `2452`) are the same original routine reached from
  different dispatch slots.

⚠️ **They are not evidence of anything.** *(User instruction, 2026-09-04.)* The
`ASM nnnn` citations, the `b02`/`w04` width markers, the slot-map commentary and the
FIXMEs all record **what the port's authors believed the PC version did** — and they may
be wrong. Use them to *locate* code; never to *establish* a fact. Ghidra decides:
`atari_ram.bin` for the ST, `ibmpc_cs.bin` for the PC.

They are **not** addresses we can look up in `atari_ram.bin`, and no attempt should be
made to map them arithmetically onto ST addresses. There is no known constant offset;
they are different executables for different CPUs.

## Confidence in the port as a description of the original

The port is a *playable reconstruction*, not a fidelity project. Its own comments
repeatedly admit uncertainty, and those admissions are the honest boundary of what it
can tell us:

- ~~`ents.c:254-263` — "FIXME what is this? when all trigger flags are up, then use
  `.sni` for `sprbase`. Why? What is the point?"~~ ✅ **Resolved 2026-09-04 (T9)** — see
  `xref.md`. The port read its build correctly; only the *reason* was missing.
- `e_them.c:480-486` — the entity direction randomiser is described as **"Black Magic
  (tm) ... an exact copy of what the assembler code does but I can't explain."**
- `e_them.c:202` — "FIXME why `trig_x` (b16) ??" where the field is reused as a step
  limit for type-1a patrols.
- `e_them.c:691-696` — "the sound should come from a table, there are 10 of them but I
  dont have the table yet. must rip the data off the game..."
- `maps.c:155` — "FIXME should return next submap number, or 0."
- `game.c:734` — "FIXME some dirty hacks here".
- `ents.h:580, 584` — two entity fields are documented as present "in ASM code but never
  used" and are commented out of the C struct (`b01`, `w0C`).
- `e_rick.c:537-540, 558-561` — the save/restore of Rick's state is explicitly
  incomplete: "FIXME save_C0 = E_RICK_ENT.b0C; plus some 6DBC stuff?"

Treat every such marker as **a place where the port is known-weaker than our RE**, and
therefore a place where our RE is the better source rather than a discrepancy to
reconcile. They are collected in `divergences.md`.

## Licence and reuse

Source headers carry: "Copyright (C) 1998-2019 bigorno (bigorno@bigorno.net). All rights
reserved. The use and distribution terms for this software are contained in the file
named README". The clone's `README.md` at `c2aef3d` does **not** contain licence terms —
it is a project description only. The bundled `unzip.c` / `unzip.h` are Gilles Vollant's
zlib-licensed code and are third-party.

✅ **Closed 2026-09-04 — no constraint.** The user holds the rights to the PC version.
The absent README terms are not an obstacle to modifying, building or publishing work
derived from this port. Earlier text here treated it as an open question; it is not.
See `../../review-plan.md` §0.2.
