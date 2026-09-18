# What a mechanical port of Rick Dangerous 2 still needs

Assessment written 2026-09-18, against the state of `xrick2-ref.md`,
`xrick2-gaps.md` and `sound-ref.md`. "Mechanical port" = reimplement the game
faithfully on a modern host by transcribing understood logic and extracting
original data, without redesigning anything.

A port needs four things. The RE effort has deliberately covered one and a
half of them.

| | Area | State |
|---|---|---|
| 1 | **Game logic** — main loop, actors, AI, physics, input | ~90% understood, narrowly validated |
| 2 | **Game data** — levels, tables, scripts, graphics | Formats mostly known; **almost nothing extracted** |
| 3 | **Rendering** — tile/sprite formats, palette, screen model | Essentially untouched, by design |
| 4 | **Sound** | **Done** (`sound-ref.md`, `rick2_sfx.sndh`) |

## 1. Game logic — understood, but validated against a single sample

What is solid: the 50 Hz main loop (`main_loop_body` @ `$10a90`), the 88-byte
`ActorRecord` with ~48 named fields and its dual behaviour-profile swap, the
enemy AI byte-code VM (both the movement and animation script formats decoded
to opcode level and checked byte-for-byte against real script data), the
4-slot `g_object_table` subsystem including its one hand-inlined construction
site, player physics and the unified tile+actor collision primitive, the
input abstraction including attract-mode demo playback.

The real weakness is **breadth of validation, not depth of understanding**.
Essentially everything live was checked against one capture: map 1, attract
mode, a 13-entry spawn table, four actors that all happened to have type IDs
`>= 0x75`. Consequences:

- `FUN_000146a0` (the monster-descriptor path for type IDs `< 0x75`) is fully
  decoded but **has never run against real data**.
- `dispatch_spawn_record`'s trigger/effect branch (`byte2&0x80 == 0`) has
  likewise never fired against real data.
- `g_collision_result_flags` bit meanings are partly inferred, never watched.
- A handful of `ActorRecord` fields have no observed reader.

None of this blocks starting a port; all of it will bite during debugging,
because these are exactly the paths where a wrong guess produces plausible-
but-wrong behaviour. **All of it is now cheaply answerable** — see §5.

## 2. Game data — the biggest gap, and the most mechanical

This is under-represented in `xrick2-gaps.md` because that document indexes
*understanding*, and this is a gap in *extraction*. A port is mostly data: you
cannot ship map 2 because you understand the record grammar.

Needed, none of it extracted yet:

- **Tile maps** for every map/submap (the tile-ID array at `$65300`, the
  attribute table at `$65200`).
- **Spawn tables and submap-trigger tables** per level — grammar known, one
  13-entry map-1 table ever decoded.
- **The monster-descriptor table** `DAT_00053400` — per-type width, height,
  behaviour bits, and both script-pointer pairs. This is the single most
  port-ready structure in the game and it has not been dumped in full.
- **Move/anim byte-code scripts** for every enemy type.
- **Sprite and tile graphics** (see §3).

The good news: the path to all of it is open and understood. The content lives
in `RICK_01`–`RICK_08.HNK`, and **both** depackers are identified — the
backward LZ at `$7400` (`lz_depack_backward`, `"LSD!"`-gated entry at `$73f0`)
and the separate Huffman-style bit-tree decoder at `$1795c` that unpacks the
monster-descriptor table. Writing a standalone host-side depacker for those
two formats is ordinary, verifiable work: decode an `.HNK` offline, and check
the result byte-for-byte against the same region of `dump_hnkload_hit2.bin`,
which captured a real post-load image. That single test makes the whole
extraction pipeline self-verifying.

Estimate: this is the largest remaining chunk, and also the least risky.

## 3. Rendering — untouched, and the real unknown

Excluded from the RE scope by design, which was the right call for
understanding logic, but a port needs it. What is missing is not the blit code
(a port reimplements drawing anyway) but the **data formats and the screen
model**:

- Sprite format and the sprite/frame index used by `anim_frame`.
- Tile graphics format and how a tile ID maps to pixels.
- Palette, and the ST screen layout in use (almost certainly 320×200 4-plane).
- How the horizontal scroll works (three blit loops identified at
  `$188d0`/`$18b5c`/`$18c50`, labelled render-adjacent and not decoded).
- The shared visual/sound effect request slot `PTR_DAT_000176f4`.

Worth noting the precedent: **sound was also "out of scope", and turned out to
be very tractable once actually attacked** — the engine was intact, the data
was all present, and the whole thing resolved to one 92-entry table plus two
clocks. Rendering is plausibly similar in character: the hard part is the
formats, and the formats are sitting in the same RAM dumps.

## 4. Sound — complete

`rick2_sfx.sndh` plays all 92 in-game sounds correctly. For a port you do not
need the SNDH wrapper, you need what is in `sound-ref.md`: the 92-entry
dispatch table, the three playback types, the bytecode grammar, the 13-byte
instrument records, and the type-2 sample streams with their three volume
tables. A port can either emulate the YM2149 and run the same data, or
pre-render. Nothing here is unknown.

## 5. The unlock: Hatari is scriptable from the shell, today

`xrick2-gaps.md` concluded that the highest-priority open items were blocked
on "a session with Hatari MCP/tool integration". That was a mistake — Hatari
is a CLI binary and runs headless from Bash. Verified 2026-09-18 (full
invocation and capability list in `xrick2-gaps.md`, "2026-09-18 correction"):
`--trace` with per-event cycle counts **and the PC that caused each event**,
`--parse` for scripted breakpoints, `--run-vbls` for deterministic bounded
runs, a bundled `tos.img`, and `disks/rd2.st` is the real game.

That converts the four "blocked" high-priority gaps into a morning's work, and
it enables the thing that matters most for a port:

**Differential testing.** Run the original in Hatari, run the port, compare
state frame by frame. This is not speculative — the sound effort failed for 24
passes precisely because it had no such oracle, and succeeded once every claim
was checked against the actual bytes. For a port, the equivalent is a trace of
the original's actor table, player position and collision results per frame,
diffed against the port's. Build that harness *before* writing gameplay code,
not after.

## Progress

**Step 1 is DONE (2026-09-18).** Both depackers are transcribed from the
game's own code and verified byte-exact four independent ways; all 8 archives
and all 4 level images are extracted. See `assets/README.md` for the pipeline,
the verification, and the level-image layout discovered so far. `hnk.py` is the
tool. This closes the largest item in §2 and makes the rest of §2 (locating
the individual tables inside the 73472-byte level image) a data-navigation
problem rather than a decoding one.

Steps 2-5 remain.

## Suggested order

1. ~~**Depacker + extraction pipeline** (§2), verified against
   `dump_hnkload_hit2.bin`.~~ **DONE** — see above.
2. **Hatari capture harness** (§5) — per-frame state traces from the real game.
3. **Close the four live gaps** (§1) using #2, now cheap.
4. **Rendering formats** (§3) — the genuine unknown; attack it the way sound
   was attacked, data first.
5. **Port the logic** (§1), differential-tested against #2 continuously.

Sound (§4) is done and can be dropped in whenever.
