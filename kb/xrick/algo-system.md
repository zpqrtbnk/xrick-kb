# System, screens, input and sound — `scr_*.c`, `sys*.c`, `sounds.c`, `data.c`

The game state machine itself is in `architecture.md`. This file covers everything it
calls out to.

## Screens

Every screen is a re-entrant function returning `SCREEN_RUNNING` / `SCREEN_DONE` /
`SCREEN_EXIT`, driven by a `static U8 seq` state variable and called once per frame.

### `screen_xrick` — the xrick splash (`scr_xrick.c:33`)

Paints `IMG_SPLASH` (an 8-bit indexed image with its own palette, from
`src/img_splash.e`), waits 3 frames, plays `sounds/bullet.wav` as "music", waits 0x20
more, done. **Port branding, not part of the original.**

### `screen_introMain` — title and hall of fame (`scr_imain.c:37`)

Alternates two pages with fades between them, at `IMAIN_PERIOD` = 50 ms:

- **seq 1–8**: the Rick Dangerous title. `GFXST` paints `pic_splash` full-screen;
  `GFXPC` composes it from tile strings (`screen_imainrdt`, `screen_imaincdc`) with
  colour filters.
- **seq 10–18**: the hall of fame. `GFXST` paints `pic_haf` as a banner, then eight
  rows formatted with `sprintf("%06d@@@....@@@%s", score, name)`, truncated to 26 tiles,
  at (56, 40 + i·16).

Each page waits for FIRE or a `SCREEN_TIMEOUT` = 4000 ms timeout. The `seen` counter
makes the *first* FIRE press advance to the other page and the second start the game
(`scr_imain.c:105-116`). Music: `sounds/tune5.wav`, looped forever (`loop = -1`).

Default high scores are compiled in (`game.c:79-101`) and differ between `GFXST` and
`GFXPC`; they are **not persisted** — no file is written, so the table resets every run.

### `screen_introMap` — the per-map intro (`scr_imap.c:64`)

Paints `maps_intros[env_map].title` at (32, 0) and `.body` at (32, 96), then runs a
small animation in a 64×64 box at (120, 16):

```
drawcenter()  6x6 tiles starting at tn0[env_map] = {0x07,0x5B,0x7F,0xA3,0xC7}
drawtb()      top/bottom borders, alternating tiles 0x40/0x06 and 0x05/0x40
drawlr()      left/right borders, alternating tiles 0x04 and 0x2B
drawsprite()  sprites_paint(spnum, 128 + ((spx<<1) & 0x1C), 24 + (spy<<1))
```

The animation is a little bytecode: `screen_imapsofs[env_map]` selects the first step in
`screen_imapsteps[]` (`{count, dx, dy, base}`), where `base` indexes `screen_imapsl[]`, a
set of `0`-terminated sprite-number lists. `anim()` (`scr_imap.c:281`) advances one frame
per call, cycling the sprite list and stepping `spx`/`spy` by `spdx`/`spdy`, and calls
`nextstep()` when `count` hits zero. `count == 0` in the step table means "no more
steps" and stops the animation.

The first step of each map is used only as an initial position: `init()` reads
`spx = steps[step].dx`, `spy = steps[step].dy`, then `step++` (`scr_imap.c:308-317`).

Music: `sounds_setMusic(map_maps[env_map].tune, 1)` — one WAV per map, `tune0`..`tune4`.

### `screen_gameover` (`scr_gameover.c:33`)

Clears the screen, paints `screen_gameovertxt` at (120, 80), waits for FIRE or a 4 s
timeout (`GFXST` only), plays `sounds/gameover.wav` looped.

### `screen_getname` (`scr_getname.c:56`)

Returns `SCREEN_DONE` immediately if `env_score < game_hscores[7].score`. Otherwise
draws a 6×5 letter grid at (116, 64) plus a 10-character name field, moves a pointer with
the direction keys (with a 100 ms auto-repeat timeout), and appends on FIRE. Grid index
`i = x + y*6`: `< 26` letters, `26` = `.`, `27` = space (`@`), `28` = backspace, and
`(x,y) == (5,4)` = END, which inserts the score into `game_hscores` by shifting the tail
down.

### `screen_pause` (`scr_pause.c:35`)

Paints `screen_pausedtxt` at (120, 80); on un-pause repaints map, entities and HUD.

## Input — `control.c`, `sysevt.c`, `syskbd.c`

`control_status` is a bitmask of currently held actions, `control_last` the most recent
event's bit, `control_active` the window-focus flag (only updated when `ENABLE_FOCUS` is
compiled in, which it is not — so it is permanently `TRUE`).

`sysevt.c:41` maps SDL2 **scancodes** to control bits, with `syskbd_*` holding the
user-configurable codes and the arrow keys always accepted as well. Extra keys:

| Key | Action |
|---|---|
| F1 | toggle fullscreen |
| F2 / F3 | zoom out / in |
| F4 | mute |
| F5 / F6 | volume down / up |
| F7 / F8 / F9 | cheats: trainer / invincible / highlight (`game_toggleCheat`) |

`SDL_QUIT` is treated as ESC (`CONTROL_EXIT`). Quitting the game requires
`control_last == CONTROL_EXIT` in `CTRL_ACTION` (`game.c:477`), i.e. the *last* event
must have been the exit key.

The cheats (`game.c:130`): trainer sets lives/bombs/bullets to 6 and stops them being
consumed; invincible clears `MAP_EFLG_LETHAL` from every environment probe and makes
`e_rick_gozombie` a no-op; highlight forces sprites in front and ORs `0x10` into every
sprite pixel. Note `env_trainer = ~env_trainer` (bitwise NOT, not `!`) — the flag toggles
between 0 and 0xFF, which works because it is only ever tested for truth.

## Sound — `sounds.c`, `syssnd.c`

⚠️ **Superseded 2026-09-10 (T19).** Everything below this line described the
pre-T19 port, whose WAV mixer is retired. Kept as a historical record of what the
port *used to* do, not a description of the current tree — see the replacement
description first.

**The port now emulates the PSG — for real, not a re-synthesis.** `T19` (design:
`audio-sndh.md`) replaced the WAV mixer with Arnaud Carré's AtariAudio library
(MIT, vendored into `src/audio_engine/`), which contains a Musashi 68000 core plus
YM2149/MFP68901 emulation. `src/dat_sndh_engine.c` embeds the *actual* sound-engine
machine code and tables lifted from `atari_ram_1M.bin` (the same source `kb/`'s own
`rick_dangerous.sndh` uses, `kb/build_sndh.py`) — 58,944 bytes, `xrick/xrick/tools/
extract_sound_engine.py` re-derives it from the dump on demand (never hand-edited).

`syssnd.c` holds one persistent `AtariMachine` instance for the whole process, created
in `syssnd_init()`. `sound_t` is no longer a PCM buffer — it is `{U8 track; S8 d1;}`,
the ST `music_track_table` index and the `play_music()` D1 value the *original* game
used at that sound's own call site (not a caller-supplied "loop count" any more). Every
`WAV_*` in `sounds.c` is a compile-time descriptor built from `audio-sndh.md` §7's
census (cross-referenced against `kb/algo-player.md`/`algo-entities.md`, not guessed
from the sound's English name). `syssnd_play_track(track, d1)` calls into the emulated
`play_music` through one of two 8-byte hand-assembled trampolines (`moveq #0/1,d1 ;
jmp play_music`) — `AtariMachine::Jsr()` only ever sets D0, and every real ST call site
uses D1 ∈ {0,1}, so two trampolines cover every case. The SDL audio callback ticks
`music_tick` once per 50 Hz frame-equivalent and pulls one emulated sample per output
sample (`AUDIO_S16SYS`, not the old `AUDIO_U8`).

**One documented, verified quirk of the *original engine itself*, not the port**:
`play_music`'s type-1 (SFX) and type-2 (sample) dispatch refuse to interrupt an active
type-0 (tracked-music) track — confirmed by direct RAM read-back in a standalone test
harness, not assumed from the disassembly transcription alone. This is why level
themes being **one-shot** (`D1=0`, `audio-sndh.md` §7) matters mechanically: gameplay
SFX are silently swallowed for as long as a type-0 track stays "active" in the
engine's own state, and only play once the intro jingle has run to completion and the
engine returns to idle. `music_tick`'s own "song finished, no loop → `reset_sound_chip()`"
path is what returns the engine to idle for a one-shot track; a looping track (the
attract-mode theme) never does, by design.

The entity trigger sound is now `WAV_ENTITY[(trigsnd & 0x7F) - 0x13]` (`e_them.c`,
zero-guarded — see `pm-baty.md` G8), directly indexing `sound_t` descriptors whose
`track` field **is** `trigsnd`'s value (`0x13`-`0x1C`, i.e. `19`-`28`) — no WAV rip
involved any more. All ten slots are populated (T19 closed the old "slot 9 has no
WAV" gap, `pm-baty.md` G8 (c), since the engine already contains every track).

## Data files — `data.c`

`data_setpath(name)` accepts either a directory or a `.zip`. With `WITH_ZLIB` the ZIP
path uses the bundled `unzip.c`; `data_file_seek/tell/size` are **unimplemented for
ZIP** and return -1 (or leave `s` uninitialised, in `data_file_size`). The default path
is `"data.zip"` (`xrick.c:119`); `-data <path>` overrides it. The emscripten build
preloads the loose `data/` directory instead.

## Video — `sysvid.c`

SDL2 window + renderer + streaming texture, `SDL_RenderSetLogicalSize(320, 200)`.
Default zoom `SYSVID_ZOOM` = 2, max 4. `sysvid_update(rect_t*)` converts the 8-bit
indexed `fb` through the gamma-scaled display palette into the texture, then
`SDL_RenderCopy` + `SDL_RenderPresent` the whole thing — so the dirty-rectangle list
saves palette conversion work but not presentation.

## Command line — `sysarg.c`

`-fullscreen`, `-help`/`-h`, `-speed <ms>`, `-keys <up,down,left,right,fire>`,
`-zoom <n>`, `-map <n>`, `-submap <n>`, `-vol <n>`, `-nosound`, `-data <path>`.

`-map`/`-submap` feed `init()` (`game.c:748-767`), which contains an explicit "dirty
hack to determine frow by chaining submaps": it scans `map_maps[]` to find the owning
map, then scans `map_connect[]` for a `RIGHT` connector into that submap and derives
`map_frow = rowin - 0x10` with a "WHY 0x10??" comment. Debug plumbing, not game logic.
