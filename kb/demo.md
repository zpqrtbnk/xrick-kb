# demo.md — demo (attract) mode for the xrick port

Plan for a `-demo` command line switch that replays a scripted sequence of control
events, timed per submap, into the game engine.

Status: **implemented** (engine, phases 1-4). The scripts themselves are still to be
recorded: `src/dat_demo.c` currently has all 0x2F rows empty. All code references below
were read from the tree and are cited `file:line`; the sections marked *(corrected)*
record where the plan was wrong and the implementation had to differ.

---

## 1. Goal

`xrick -demo` plays itself: no keyboard needed, the game runs a canned script.
The script is a list of *control events* — `(elapsed, control bit, pressed/released)` —
held per submap, and restarted from the top every time a submap is entered. When play
reaches a submap that has no script, the demo ends and the keyboard takes over in place
(§6 D1), so a partially recorded demo is useful from the first submap onwards.

Non-goals (unless asked later): recording/replaying enemy state, save-states,
verification of a replay against a checksum, demo data in the `data.zip` archive.

---

## 2. What the code already gives us

Facts established by reading the tree (not assumed):

| Fact | Evidence |
|---|---|
| Rick's input is read only from the `control_status` bitmask | `src/e_rick.c:301,338,342,409,419,425,448,488,509,521,542,547,589,620` |
| `control_status`, `control_last`, `control_active` are plain globals | `src/control.c:16-18`, `include/control.h:28-30` |
| Control bits: `UP 0x08 DOWN 0x04 LEFT 0x02 RIGHT 0x01 FIRE 0x10 EXIT 0x20 END 0x40 PAUSE 0x80` | `include/control.h:19-26` |
| Only `sysevt.c` writes those globals today | `src/sysevt.c:41-209` |
| One entity-logic step per `case CTRL_ACTION`, which calls `ent_action()` | `src/game.c:504-521` |
| Scrolling returns frames without running `ent_action()` | `src/game.c:690-714`, `src/scroller.c` has no `ent_action` call |
| Game logic uses no wall clock and no `rand()` | `grep -rn "rand()\|sys_gettime\|srand" src/*.c` → only `game.c` frame pacing and the `scr_*.c` screens |
| Submap identity is `env_submap`, 0..0x2E | `include/env.h`, `MAP_NBR_SUBMAPS 0x2F` in `include/maps.h` |
| `env_submap` is already used as a **direct index** into `map_submaps[MAP_NBR_SUBMAPS]`, so it is in range by construction | `src/maps.c:76,107,110,112,166,179`, `src/ents.c:150`; `-submap` is range-checked at `src/sysarg.c:191` |
| Submap (re)entry points, all calling `map_init()` | `src/game.c:433` (INIT_MAP), `src/game.c:676` (INIT_SUBMAP), `src/game.c:867` (in `restart()` after a death) |
| Argument parsing is a flat `strcmp` chain, easy to extend | `src/sysarg.c:150-215` |
| Makefile picks up new sources automatically (`$(wildcard src/*.c)`); the MSVC project does not | `xrick/Makefile`, `xrick/xrick.vcxproj:131-166` (ClInclude), `:169+` (ClCompile) |

**Consequence for the clock:** because the logic is deterministic and driven by
`CTRL_ACTION` passes, the demo clock must count `CTRL_ACTION` passes — *not*
milliseconds and *not* rendered frames. A tick-based script then replays identically
at any `-speed`, at any frame rate, and under emscripten.

---

## 3. Design

### 3.1 Clock

`demo_tick` = number of `CTRL_ACTION` passes since the current submap was entered,
starting at 0. Reset on every submap entry, including a restart after death.

Scrolling and fade-in frames do not advance it, which is what we want: Rick does not
move during those frames either.

### 3.2 Data model

New header `xrick/include/demo.h`:

```c
typedef struct {
  U16 tick;   /* CTRL_ACTION passes since submap entry */
  U8  ctrl;   /* one CONTROL_* bit (control.h) */
  U8  down;   /* TRUE = press, FALSE = release */
} demoevt_t;

typedef struct {
  U16 nbr;             /* number of events; 0 = no demo for this submap */
  demoevt_t *evts;     /* sorted by ascending tick; NULL when nbr == 0 */
} demoscript_t;

extern demoscript_t demo_scripts[MAP_NBR_SUBMAPS];  /* indexed by env_submap */

extern U8 demo_active;  /* TRUE while the demo is driving the controls */

extern void demo_init(void);          /* read -demo / -record; after sysarg_init */
extern void demo_enterSubmap(U16);    /* reset clock, select script */
extern void demo_cycle(void);         /* one CTRL_ACTION worth of input */
extern void demo_end(void);           /* hand the controls back; idempotent */
extern void demo_save(void);          /* write dat_demo.c when recording */
```

The script array is **indexed by `env_submap`**, one entry per submap, so the struct
carries no submap id: the index *is* the id. This is the same addressing the engine
already uses for `map_submaps[env_submap]` (`src/maps.c:76` etc.), it makes
`demo_enterSubmap` an O(1) lookup instead of a search, and it needs no terminator
entry. Submaps with no demo are `{ 0, NULL }`.

`U16 tick` is sufficient: at `GAME_PERIOD 40` (ST, `include/rd1/game.h`, master
`89d0e1a`; 75 before) one tick is 40 ms, so 65535 ticks ≈ 44 minutes per submap visit —
in the full-game demo the latest event of any take is at tick 1504 (checked in
`dat_demo.c`).

Data lives in `xrick/src/dat_demo.c`, matching the existing `dat_*.c` convention
(`src/dat_ents.c`, `src/dat_maps.c`, …):

```c
static demoevt_t demo_evts_00[] = {
  {   0, CONTROL_RIGHT, TRUE  },
  {  14, CONTROL_UP,    TRUE  },
  {  16, CONTROL_UP,    FALSE },
};
/* ... */

demoscript_t demo_scripts[MAP_NBR_SUBMAPS] = {
  /* 0x00 */ { sizeof demo_evts_00 / sizeof demo_evts_00[0], demo_evts_00 },
  /* 0x01 */ { 0, NULL },
  /* ... one line per submap, 0x00 .. 0x2E ... */
};
```

All 0x2F entries are listed in order rather than using C99 designated initializers —
the tree is built by MSVC as well as gcc (`xrick/xrick.vcxproj`, `xrick/Makefile`) and
the rest of the `dat_*.c` tables are plain ordered initializers. No row-count assertion
is needed *(corrected)*: the array has a declared size, so too many rows is already a
compile error and too few are zero-filled — which is exactly the `{ 0, NULL }` "no demo"
value. Listing all 0x2F anyway keeps it obvious which submaps are still to do.

### 3.3 Injection

`xrick/src/demo.c` keeps its own mask and a cursor into the current script:

- `demo_enterSubmap(submap)` — sets `demo_tick = 0`, `demo_mask = 0`, `demo_cursor = 0`,
  and points the current script at `&demo_scripts[submap]`. An entry with `nbr == 0`
  means "no demo here" and **ends the demo** — see §3.5.
- `demo_cycle()` — when playing back, applies every event with `tick <= demo_tick`
  (advancing the cursor), updating `demo_mask`; then writes:

  ```c
  control_status = demo_mask | (control_status & (CONTROL_EXIT|CONTROL_END|CONTROL_PAUSE));
  if (!(control_status & CONTROL_EXIT))
      control_last = last_applied_bit;   /* mirrors sysevt.c behaviour */
  ```

  then `demo_tick++`.

Rationale for the mask preservation: the human must always be able to quit or pause a
running demo. `CONTROL_EXIT` is checked via `control_last` at `src/game.c:511` and via
`control_status` at `src/game.c:481`, so both must survive; hence the guard on
`control_last`.

If the event list of the *current* submap is exhausted, `demo_cycle()` leaves `demo_mask`
unchanged (a key held at the end stays held) rather than clearing it. Running out of
events is normal — a script usually stops changing keys a few ticks before Rick reaches
the exit — so it is **not** the end of the demo; only entering an unauthored submap is
(§3.5).

Real keyboard movement keys are therefore overridden every tick while the demo runs.
F1–F9 (zoom, sound, cheats) keep working — they are handled inside `sysevt.c` and never
touch `control_status`.

### 3.4 Hook points in `game.c`

Six one-line calls, all inside `#ifdef ENABLE_DEMO`. `demo.c` decides what to do, so
`game.c` carries no demo state of its own. Line numbers are as implemented:

1. `game_run()` (`src/game.c:194`) — `demo_init()`, after `sysarg_init` has run.
2. `case CTRL_ACTION:` (`src/game.c:518`) — `demo_cycle()` as the first statement of the
   case, before the `CONTROL_END` test, so the injected mask is what `ent_action()`
   (`:531`) sees this step.
3. `case INIT_MAP:` (`src/game.c:443`, next to `map_init()`) — `demo_enterSubmap(env_submap)`.
4. `case INIT_SUBMAP:` (`src/game.c:692`, next to `map_init()`) — same.
5. `restart()` (`src/game.c:890`, next to `map_init()`) — same, so a death replays the
   submap script from tick 0.
6. `case FADEOUT__GAMEOVER:` (`src/game.c:747`) — `demo_end()` (§3.6).

### 3.5 End of demo — hand control back to the keyboard

The demo ends when `demo_enterSubmap()` is given a submap whose entry is `{ 0, NULL }`,
i.e. the chain has walked past the last authored submap. `demo_end()` then:

```c
control_status &= ~demo_mask;   /* drop any key the script was holding */
demo_mask = 0;
demo_active = FALSE;            /* sysevt.c is the sole writer again */
sys_printf("xrick/demo: end of demo at submap %#04x, keyboard control restored\n", submap);
```

Play continues seamlessly from wherever Rick is; the human takes over mid-submap. All
`if (demo_active)` hooks (§3.4) go quiet from that point on, including the screen
auto-advance of §3.6, so a subsequent map intro waits for a real keypress as usual.

Two consequences worth noting:

- With an all-empty table (phase 1, and until submaps are recorded), `-demo` hands over
  on the very first submap and the game simply plays normally. That is the desired
  behaviour, not a special case to code around.
- Dying inside an authored submap replays that submap's script from tick 0 (§3.4 hook 4);
  it does not end the demo.

### 3.6 Getting past the screens

- `screen_xrick` self-advances on a frame counter (`src/scr_xrick.c:48-67`) — nothing to do.
- `screen_introMain` **never finishes on its own** *(corrected)*. It does time out
  (`src/scr_imain.c:101,174`), but the timeout at seq 12 goes to seq 18, which fades out
  back to seq 1 — the splash and hall of fame alternate forever. `SCREEN_DONE` is only
  reached through seq 28, and seq 28 is only reached from a FIRE press at seq 4 or 13.
  The plan claimed "nothing to do" here; a `-demo` run proved otherwise by never
  starting a game. Fixed by jumping to seq 28 in demo mode on the seq 12 timeout, so the
  demo shows splash and hall of fame once each and then starts.
- `screen_introMap` **blocks on FIRE forever** (`src/scr_imap.c:113`, `seq` 10/12/13 animation
  loop). Add, in `case 10`, a demo-only frame counter that jumps to `seq = 20` after
  `DEMO_INTRO_FRAMES`. `seq 20` waits for FIRE *release* (`:141`), already satisfied.
  This keeps the animated map intro visible, which an attract mode wants.
- `screen_gameover` self-times out (`src/scr_gameover.c:74`), then `game.c` goes to
  `GETNAME`, which blocks on input (`src/scr_getname.c:107-211`). Given decision D1
  (§6), `demo_end()` is called at the top of `case FADEOUT__GAMEOVER` — one site rather
  than the three that set that state, since `demo_end()` is idempotent. The demo is
  over, so the hall-of-fame name entry is driven by the real keyboard like any other
  game, and the `GAMEOVER -> GETNAME` transition is untouched. *Derived from D1, not
  explicitly decided — say so if you want gameover to loop back to the attract screen
  instead.*

- `screen_introMap` auto-advance is counted in **animation loops, not frames**
  *(corrected)*: seq 10 is only reached every third frame (10 -> 12 -> 13 -> 10), so the
  constant is `DEMO_INTRO_LOOPS` (0x18, about five seconds at the default period).

### 3.7 Command line

In `sysarg_init` (`src/sysarg.c:150`), add before the final `else`:

```c
else if (!strcmp(argv[i], "-demo")) sysarg_args_demo = 1;
else if (!strcmp(argv[i], "-record")) { if (++i == argc) sysarg_fail("missing file"); sysarg_args_record = argv[i]; }
```

plus `extern int sysarg_args_demo; extern char *sysarg_args_record;` in
`include/sysarg.h`, and two lines in the `sysarg_fail` usage strings
(`src/sysarg.c:64,66`).

Per D2 (§6), `-demo` does **not** force a starting point: it plays whatever submap the
game starts at, which is map 1 by default and whatever `-map`/`-submap` select
otherwise (`src/game.c:793-812`). So `-demo -submap 12` replays just that submap's
script, which is also how a single script gets reviewed after recording. No code is
needed for this — it follows from hooking `demo_enterSubmap()` at the existing submap
entry points (§3.4).

Per D3, sound is untouched: `-demo` does not imply `-nosound`.

`demo_active` is set from `sysarg_args_demo` in `game_run` (`src/game.c:185` area),
after `sysarg_init` has run.

### 3.8 Recorder (how the data actually gets written)

Hand-writing tick numbers is impractical. `-record <file>`: while playing normally,
`demo_step()`'s counterpart `demo_record()` is called at the same point in
`CTRL_ACTION`, diffs `control_status` against the previous tick, and appends one line
per changed bit in *the C table's own syntax*, so the output pastes straight into
`src/dat_demo.c`:

```c
static demoevt_t demo_evts_00[] = {   /* emitted by demo_enterSubmap */
  {   0, CONTROL_RIGHT, TRUE  },
  {  14, CONTROL_UP,    TRUE  },
  {  16, CONTROL_UP,    FALSE },
};                                    /* emitted on leaving the submap */
```

Because the table is index-addressed (§3.2), the recorder must also emit the
`demo_scripts[]` line for each submap it captured, and the submaps it never entered
still need their `{ 0, NULL }` row. So `-record` writes the *whole* `dat_demo.c` — all
0x2F rows, with the captured event arrays filled in and the rest empty — rather than a
fragment to splice. No parser enters the runtime. (Optional later extension:
`-demo <file>` reading a text form back at runtime.)

Events are held in a flat pool with one block per submap; re-entering a submap (after a
death, or on a revisit) opens a new block, so **the last take wins** and re-recording a
submap is just a matter of dying or walking back into it.

The write is registered with `atexit` in `demo_init`, not called from `game_exit`
*(corrected)*: `xrick.c:88-89` routes SIGINT and SIGTERM to `exit()`, which never reaches
`game_exit`, and a take is worth keeping whichever way the game was left.

Recording is only meaningful at the port's normal deterministic pace; note in the file
header which `-speed`/PLATFORM the take was made at — the tick clock itself is
speed-independent, but a human's timing is not.

---

## 4. Files

Add:
- `xrick/include/demo.h`
- `xrick/src/demo.c` — clock, injection, recorder
- `xrick/src/dat_demo.c` — the scripts

Modify:
- `xrick/src/game.c` — 4 hooks (§3.4) + `demo_init()` in `game_run` + `demo_end()` at
  `FADEOUT__GAMEOVER` (§3.6)
- `xrick/src/scr_imap.c` — map intro auto-advance (§3.6)
- `xrick/src/scr_imain.c` — main intro auto-start (§3.6, *added: not in the original plan*)
- `xrick/src/sysarg.c`, `xrick/include/sysarg.h` — `-demo`, `-record`, usage text
- `xrick/include/config.h` — `ENABLE_DEMO`
- `xrick/src/system.c` — `sys_printf` buffer overflow (§5, *not part of the plan; the
  added help text made a latent defect fatal*)
- `xrick/xrick.vcxproj` (+ `.filters`) — add the three new files; the Makefile needs no
  change (`SRC := $(wildcard src/*.c)`)

Everything is wrapped in `ENABLE_DEMO` (`include/config.h`), following the
`ENABLE_DEVTOOLS` pattern, so a shipped binary can exclude the recorder.

---

## 5. Status and verification

Phases 1-4 (the engine) are **done**; phase 5 (the scripts) is the user's, phase 6 is
open.

| Phase | State |
|---|---|
| 1. Skeleton — `demo.h`, `demo.c`, `dat_demo.c` (0x2F empty rows), `-demo`, build wiring | done |
| 2. Clock, injection, handover | done |
| 3. Screens — main intro auto-start, map intro auto-advance, `demo_end()` at game over | done |
| 4. Recorder — `-record` | done |
| 5. Author the scripts — incremental, by the user (D4), one submap at a time | to do |
| 6. Polish — README note | to do |

### What was actually run

Built with the tree's own warning set (`make PLATFORM=ST`,
`-Wall -Wextra -Wconversion -Wsign-conversion -Wtype-limits`) under gcc 14.2:

- `demo.c` and `dat_demo.c` compile with **zero** warnings.
- The edits to `game.c`, `scr_imap.c`, `scr_imain.c` and `sysarg.c` add **no** new
  warning: every warning site in those files is on a pre-existing line.

Behaviour, run headless (`SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy`), reading Rick's
position out of the existing `xrick/ents` debug trace:

- **Handover** — with the table all empty, `-demo` starts the game by itself and prints
  `xrick/demo: end of demo at submap 0000, keyboard control restored`, then plays on
  under keyboard control. This is also what proved the `scr_imain.c` correction: before
  that fix the run never left the intro.
- **Playback timing is exact** — with a scratch script on submap 0 (`RIGHT` down at tick
  0, up at 40, `UP` down at 45, up at 48), Rick walks from x 0x0008 to 0x0058 in exactly
  40 logic steps (2 px each), stands still for exactly ticks 40-44, and the jump starts
  on tick 45.
- **Recorder** — `-record /tmp/rec.c`, killed with SIGTERM, wrote a complete,
  well-formed `dat_demo.c`: correct header, all 0x2F rows, `#ifdef ENABLE_DEMO` guard.
  `-demo -record` together print the override notice and record only.
- **Warning total unchanged** — a clean rebuild of this tree and of a clean `git archive
  HEAD` build both report exactly **283** warnings.

### One defect found on the way, and fixed

`xrick -h` printed nothing at all once the two `-demo` / `-record` help lines were added.

`sys_printf` (`src/system.c`) formatted into `char s[1024]` with **`vsprintf`**, and
`sysarg_fail`'s sound-branch usage text is **1108 characters** of literal before its
`%d`/`%s` are expanded. So `-h` was already writing past the end of the stack frame in
the stock tree — a build from `git archive HEAD` prints the usage fine, purely by luck of
the frame layout. The added lines pushed it far enough to die silently.

Fixed at the source rather than by shortening the help: `vsnprintf` bounded by
`sizeof s`, buffer raised to 4096 so the usage text is not truncated, and `printf(s)`
replaced by `fputs(s, stdout)` — `s` is data and may contain a `%`, which `-record
<file>` makes reachable with a filename. Verified: `-h` now prints in full, including the
new options.

Not yet verified: how it looks on screen (no display was used), and a round trip of a
real recorded take through `dat_demo.c` — both need a human at the keyboard.

### Using it

```sh
xrick -demo                  # play the built-in scripts, then hand over
xrick -demo -submap 12       # replay one submap's script
xrick -record src/dat_demo.c # play by hand; the file is written on exit
```

`-record` overrides `-demo`. The file is written on any normal exit (ESC, closing the
window, SIGINT, SIGTERM) — see §3.8.

---

## 6. Decisions

Settled on 2026-09-08; the sections above are written to match.

- **D1 — End of demo: hand control back to the keyboard.** Once play passes the last
  authored submap, the demo stops and the human takes over in place, mid-game. No
  attract loop, no exit. Implemented as `demo_end()` on entering a submap whose script
  row is `{ 0, NULL }` (§3.5). Running out of *events* inside an authored submap is not
  the end — the last mask is simply held (§3.3).
- **D2 — The demo starts wherever the game starts:** map 1 by default, or whatever
  `-map`/`-submap` select. `-demo` forces nothing (§3.7).
- **D3 — Sound stays on.** `-demo` does not imply `-nosound` (§3.7).
- **D4 — Space for every submap up front.** `dat_demo.c` carries all 0x2F rows from
  phase 1, empty; scripts get recorded and filled in one map at a time (§5 phase 5).

One point derived from D1 rather than decided: on game over the demo ends too, so the
hall-of-fame name entry uses the real keyboard (§3.6). Say so if you would rather it
loop back to the attract screen.

## 7. Shared with RD2 (2026-09-24)

`src/demo.c` / `include/demo.h` are now game-agnostic (moved out of `rd1/`). A game hands the
core a `demoset_t`: its script array, the number of segments and how to write a recording back.
`demo_enterSegment` replaced `demo_enterSubmap`; `demo_cycle` (RD1, drives `control_status`) is
unchanged in behaviour, and `demo_play` / `demo_record` expose the same clock to other adapters.

| | RD1 (`src/rd1/game.c`) | RD2 (`src/rd2/rd2_demo.c`) |
|---|---|---|
| segment | submap, reset on entry and on death | map 1..4, reset at level start `$10a4e` only |
| tick | `CTRL_ACTION` pass | game_main frame head `$10a54` |
| playback writes | `control_status` | joystick byte `[$1a4fb]` |
| recording reads | `control_status` | `[$1a4fb]` (what `$141cc` sees) |
| generated file | `src/rd1/dat_demo.c` | `src/rd2/dat_rd2_script.c` + `<file>.map<N>.joy` |

RD2 plays/records only real games (`[$3efb6] == 0`); the game's own attract demo keeps its
`(count, state)` stream. RD2 `-demo` starts from a game begun by hand (title, picker); the run's end
(`END_OF_RUN`, or ESC to the title) hands the keyboard back. The `.joy` file (one joystick byte per
frame from level start) is the `RD2_JOYSEQ` / `kb2/hatari_rd2_trace.py` input.

Checked 2026-09-24 (WSL): RD2 recording driven through the host joystick path (`RD2_INPUT`), 881
frames of map 1; `-demo` playback of it rebuilt as `dat_rd2_script.c` = byte-identical RAM trace
for all 880 compared frames; the `.joy` under Hatari vs the port (forced-map route) = identical for
881 frames. RD1: builds, `-demo` ran 90 s without error — no RD1 trace comparison was made.
