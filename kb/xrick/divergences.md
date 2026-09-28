# Divergences — where the port is not the game

A catalogue of everything in the port that is **not** faithful to an original, grouped by
why. Read this before treating any port behaviour as evidence.

## 1. Deliberate additions (not in any original)

| Thing | Where |
|---|---|
| The xrick splash screen | `scr_xrick.c`, `img_splash.e` |
| Cheats: trainer (F7), invincible (F8), highlight (F9) | `game.c:130`, `env.c:25-27` |
| The `T`/`I`/`H` cheat row and the `Mnn`/`Snn` map/submap readout, always visible | `env_paintXtra`, `env.c:95` |
| Fullscreen, zoom, volume, mute keys | `sysevt.c:84-112` |
| `-map`, `-submap`, `-speed`, `-vol`, `-nosound`, `-data`, `-keys` | `sysarg.c` |
| `env_depth` toggle (disable the foreground-tile depth test) | `env.c:29` |
| ~~WAV audio in place of the PSG~~ — **resolved 2026-09-10, T19**: `syssnd.c` now runs the real lifted PSG engine under 68000 emulation (AtariAudio); `data/sounds/*.wav` is unused legacy data, not deleted. See `algo-system.md`'s Sound section | `syssnd.c`, `src/audio_engine/`, `src/dat_sndh_engine.c` |
| The whole SDL platform layer | `sys*.c` |

## 2. Timing and frame model

The original is interrupt-driven at a fixed video rate. The port is a cooperative state
machine with a **software sleep** to a target period:

- `GAME_PERIOD` = 75 ms ≈ 13.3 fps (`game.h:783`), not 50/60 Hz.
- The period is changed at runtime: 24 ms while scrolling (`scroller.h:1179`), 50 ms on
  the intro screens, `period/2` during fades.
- Under emscripten the loop is driven by `requestAnimationFrame` at a derived fps
  (`game.c:203`), so timing is browser-dependent.
- The frame produced by cycle *n* is presented at the top of cycle *n+1*
  (`game.c:238`) — one frame of latency by construction.
- *(Port, since master `89d0e1a`, 2026-09-28: the software sleep really holds one
  frame per period now (it used to run at about half), and `GAME_PERIOD` is 40 ms on
  the ST = the original's gameplay rate measured in Hatari: one main-loop iteration
  per 2 VBLs, 25 steps/s (`../hatari.md` 2026-09-28). Still no VBlank model — only the
  average gameplay rate matches.)*

**Consequence:** any per-frame quantity (gravity steps, bomb fuse 45 frames, sbonus tick
30 frames, latency 0x14 frames, walk-cycle period) is expressed in *game cycles*, and a
game cycle is not the original's frame. The *counts* are comparable; the wall-clock
durations are not.

## 3. Known-incomplete, by the author's own admission

Each of these is a place where our `kb/` is the better source, not a discrepancy:

| Marker | Location | What is unknown |
|---|---|---|
| ~~"FIXME what is this? ... What is the point?"~~ | `ents.c:254-268` | ✅ **RESOLVED 2026-09-04 (T9)** — the condition selects the type-1a/1b walking enemies, for which `sni` is a second sprite number (the walk-cycle base), not a movement index. See `xref.md` |
| "Black Magic (tm) ... I can't explain" | `e_them.c:480-494` | the type-2 direction randomiser |
| "FIXME why trig_x (b16) ??" | `e_them.c:202` | that `trig_x` doubles as the type-1a patrol range |
| "I dont have the table yet ... must rip the data off the game" | `e_them.c:691-696` | the entity trigger-sound table |
| "FIXME save_C0 = E_RICK_ENT.b0C; plus some 6DBC stuff?" | `e_rick.c:537, 558` | part of Rick's checkpoint state is not saved |
| "b01 in ASM code but never used", "w0C ... never used" | `ents.h:580, 584` | two entity fields dropped |
| "FIXME should return next submap number, or 0" | `maps.c:155` | — |
| "WHY 0x10??" | `game.c:765` | the `-submap` frow derivation |
| "FIXME +8?" (×5) | `maps.c:254,299`, `sprites.c:216,301`, `ents.c:317` | the ST vertical offset is empirical |
| "FIXME is this true?" | `tiles.h:1660` | the tile-bank assignment comment |

## 4. Code defects in the port

These are real bugs in the C, independent of fidelity. They matter because a behaviour
observed by *running* the port may be a bug rather than a faithful reproduction.

**4.1 — The randomiser reads out of bounds.** `e_them.c:348`:

```c
static U16 *sh = (U16 *)&e_them_rndseed + 2;
```

`e_them_rndseed` is a `U32`. `(U16*)&seed + 2` points two `U16` slots past the start —
i.e. **past the end of the object**. The intent is `+ 1` (the high half). The code also
relies on little-endian layout for `bl`/`bh`/`cl`/`ch`. Type-2 enemy direction choices in
the port are therefore not evidence about the original's.

✅ **Confirmed against the PC binary 2026-08-31 (`../../PLAN.md` T17).** This was an
inference until `kb/ibmpc_cs.bin` became available; it is now proven. The original
randomiser is at `0x024A`, and the seed increment immediately after it at `0x0270` — the
address the port itself annotates at `game.c:484` — is `ADD word[0x7E4A],1` /
`ADC word[0x7E4C],0`, a true 32-bit increment across **two words**: low `0x7E4A`, high
`0x7E4C`. The randomiser reads both (`ADD BX,[0x7E4A]` then `MOV CX,[0x7E4C]`), so the
high half is one `U16` past the start. `+ 1` is correct and `+ 2` is a genuine defect.
The XOR chain, by contrast, is transcribed faithfully. Full disassembly in
`algo-entities.md` → *Type 2*.

**4.2 — Unsigned comparisons against zero can never fire.** `x` and `y` in `ent_t` are
`U16`, yet the code repeatedly tests them for negativity:

- `e_rick.c:217` `if (x < 0)` after `x = E_RICK_ENT.x - 2` — the left-edge submap exit;
- `e_rick.c:411` the same in the climbing path;
- `e_them.c:164` `if (ent_ents[e].x < 0 || ...)`;
- `e_them.c:298`, `e_them.c:312`, `e_them.c:392`, `e_them.c:638` similarly;
- `e_rick.c:132` `if (E_RICK_ENT.y < 0 || ...)` in the zombie fall;
- `maps.c:349` `if (*x < 0)` in `maps_clip`.

In practice underflow wraps to a large value, and the paired `> 0xE8` / `> 0x140` test
catches it — so most of these accidentally work. `scroller.c:63` does it correctly with
`if (ent_ents[i].y & 0x8000)`. The left-edge exit at `e_rick.c:217` is the one to watch:
it relies on the wrapped value **not** being caught by the `>= 0xE8` branch, which it is
not, because that branch is in the `else`.

**4.3 — `sprites_paint2` for `GFXPC` does not compile.** `sprites.c:96-180` references
undeclared identifiers (`ymap`, `xmap`, `cmax`, `xm`, `xp`). It is inside
`#ifdef GFXPC`, which is off, so it is never compiled. **The PC graphics path is
broken**; only `GFXST` builds.

**4.4 — `ENABLE_DEVTOOLS` does not compile.** `game.c:299` assigns `game_state =
INIT_GAME`, an enumerator that does not exist (the enum has `INIT`, `INIT_MAP`,
`INIT_SUBMAP`).

**4.5 — `data_file_size` on the ZIP path returns an uninitialised value.**
`data.c:132-148`: the `WITH_ZLIB` branch is an empty "not implemented" block, and `s` is
returned unset.

**4.6 — ~~`syssnd_play` channel search can read `channel[-1]`~~ — moot, 2026-09-10 (T19).**
`syssnd.c` was rewritten to drive the real engine directly; there is no `channel[]` mix
array left to have this bug. Left here as a record of a defect in the pre-T19 WAV mixer,
not a claim about the current file.

**4.7 — `env_trainer = ~env_trainer`** (`game.c:143`) — bitwise complement of a `U8`
used as a boolean. Works, but toggles 0 ↔ 0xFF.

**4.8 — `sprites_clear` is dead code** (`sprites.c:267`) — nothing calls it.

**4.9 — `ents_clearAll` is an empty function** (`ents.c:337`).

**4.10 — ~~`dat_snd.c` duplicates six symbols defined in `sounds.c`~~ — resolved
2026-09-10 (T19).** `dat_snd.c` and the ten `wav_*.e` files it went with were confirmed
unreferenced (grepped) and deleted as part of the sound-engine rewrite. See `assets.md`.

## 5. Structural choices that are not the original's

- **The `ent_t` struct is a normalised C record**, not the original layout. Field widths
  were chosen for C convenience (`U16 x` where the original had a byte-plus-word pair,
  `S16 c1/c2` for two different byte fields). **Widths and signedness in the port are
  not evidence.** Our `kb/byte-identity.md` exists precisely because those properties
  matter, and the port discards them.
- **`c1`/`c2` overloading** via `#define` is a port idiom for what the original did by
  reusing struct offsets; the *meanings* are evidence, the mechanism is not.
- **Six extra fields** were added to `ent_t` (`prev_n/x/y/s`, `front`, `trigsnd`) to
  support dirty-rectangle rendering and the entity trigger-sound path (`trigsnd`, still
  used post-T19 — it now carries the ST track number directly into `syssnd_play`
  rather than indexing a WAV array). They have no original counterpart.
- **The rendering model** (8-bit indexed frame buffer, dirty-rect list, palette-ramp
  fades) is entirely the port's. See `algo-render.md`.
- **Slot 12** is a scratch record for `u_envtest`, not an entity (`util.c:97`).
- **High scores are not persisted.** The table resets to the compiled-in defaults every
  run; there is no save file.

## 6. Where the port may be reproducing the *PC* game rather than the ST one

Flagged for investigation, not asserted:

- The default hall-of-fame names differ between `GFXPC` and `GFXST` (`game.c:79-101`),
  so the author knew of at least one data difference between the two originals.
- The bomb sprite fixup (`e_bomb.c:74-79`) proves the sprite *sets* differ.
- Sprite counts differ: 155 (PC) vs 213 (ST).
- Tile banks differ: 4 (PC) vs 3 (ST).
- The whole logic layer is annotated with PC addresses only (`provenance.md`).

Any behavioural difference we find against our ST reversal must be checked against this
list before it is called an error.
