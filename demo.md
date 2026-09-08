# demo.md — demo (attract) mode for the xrick port

Plan for a `-demo` command line switch that replays a scripted sequence of control
events, timed per submap, into the game engine.

Status: **plan only, nothing implemented**. All code references below were read from
the tree at the time of writing and are cited `file:line`.

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

extern U8 demo_active;                          /* set by -demo */
extern demoscript_t demo_scripts[MAP_NBR_SUBMAPS];  /* indexed by env_submap */

extern void demo_enterSubmap(U16 submap); /* reset clock, select script */
extern void demo_step(void);              /* one CTRL_ACTION worth of input */
```

The script array is **indexed by `env_submap`**, one entry per submap, so the struct
carries no submap id: the index *is* the id. This is the same addressing the engine
already uses for `map_submaps[env_submap]` (`src/maps.c:76` etc.), it makes
`demo_enterSubmap` an O(1) lookup instead of a search, and it needs no terminator
entry. Submaps with no demo are `{ 0, NULL }`.

`U16 tick` is sufficient: at `GAME_PERIOD 75` (`include/game.h:27`) one tick is ~75 ms,
so 65535 ticks ≈ 82 minutes per submap.

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
the rest of the `dat_*.c` tables are plain ordered initializers. A
`sizeof demo_scripts / sizeof demo_scripts[0] == MAP_NBR_SUBMAPS` static assertion (or
a runtime check in `demo.c`) catches a miscounted table.

### 3.3 Injection

`xrick/src/demo.c` keeps its own mask and a cursor into the current script:

- `demo_enterSubmap(submap)` — sets `demo_tick = 0`, `demo_mask = 0`, `demo_cursor = 0`,
  and points the current script at `&demo_scripts[submap]`. An entry with `nbr == 0`
  means "no demo here" and **ends the demo** — see §3.5.
- `demo_step()` — applies every event with `tick <= demo_tick` (advancing the cursor),
  updating `demo_mask`; then writes:

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

If the event list of the *current* submap is exhausted, `demo_step()` leaves `demo_mask`
unchanged (a key held at the end stays held) rather than clearing it. Running out of
events is normal — a script usually stops changing keys a few ticks before Rick reaches
the exit — so it is **not** the end of the demo; only entering an unauthored submap is
(§3.5).

Real keyboard movement keys are therefore overridden every tick while the demo runs.
F1–F9 (zoom, sound, cheats) keep working — they are handled inside `sysevt.c` and never
touch `control_status`.

### 3.4 Hook points in `game.c`

Four edits, all guarded by `if (demo_active)`:

1. `case CTRL_ACTION:` (`src/game.c:504`) — call `demo_step()` as the first statement of
   the case, before the `CONTROL_END` test, so the injected mask is what `ent_action()`
   (`:517`) sees this step.
2. `case INIT_MAP:` (`src/game.c:433`, next to `map_init()`) — `demo_enterSubmap(env_submap)`.
3. `case INIT_SUBMAP:` (`src/game.c:676`, next to `map_init()`) — same.
4. `restart()` (`src/game.c:867`, next to `map_init()`) — same, so a death replays the
   submap script from tick 0.

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
- `screen_introMain` self-advances on `SCREEN_TIMEOUT` (`src/scr_imain.c:97,166`) — nothing to do.
- `screen_introMap` **blocks on FIRE forever** (`src/scr_imap.c:113`, `seq` 10/12/13 animation
  loop). Add, in `case 10`, a demo-only frame counter that jumps to `seq = 20` after
  `DEMO_INTRO_FRAMES`. `seq 20` waits for FIRE *release* (`:141`), already satisfied.
  This keeps the animated map intro visible, which an attract mode wants.
- `screen_gameover` self-times out (`src/scr_gameover.c:74`), then `game.c:741` goes to
  `GETNAME`, which blocks on input (`src/scr_getname.c:107-211`). Given decision D1
  (§6), the consistent handling is to call `demo_end()` on entry to
  `FADEOUT__GAMEOVER` (`src/game.c:508` and `:564`): the demo is over, so the hall-of-fame
  name entry is driven by the real keyboard like any other game. No change to the
  `GAMEOVER -> GETNAME` transition itself. *Derived from D1, not explicitly decided —
  say so if you want gameover to loop back to the attract screen instead.*

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
still need their `{ 0, NULL }` row. Simplest: have `-record` write the *whole*
`dat_demo.c` at exit — all 0x2F rows, with the captured event arrays filled in and the
rest empty — rather than a fragment to splice. That also keeps the row count correct by
construction. Either way no parser enters the runtime. (Optional later extension:
`-demo <file>` reading a text form back at runtime.)

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
- `xrick/src/game.c` — 4 hooks (§3.4) + `demo_end()` at `FADEOUT__GAMEOVER` (§3.6) + `demo_active` init
- `xrick/src/scr_imap.c` — demo auto-advance (§3.6)
- `xrick/src/sysarg.c`, `xrick/include/sysarg.h` — `-demo`, `-record`, usage text
- `xrick/xrick.vcxproj` (+ `.filters`) — add the three new files; the Makefile needs no
  change (`SRC := $(wildcard src/*.c)`)

Optional guard: wrap everything in `ENABLE_DEMO` in `include/config.h`, following the
`ENABLE_DEVTOOLS` pattern (`include/config.h:66-67`). Recommended, so the shipped
binary can exclude the recorder.

---

## 5. Phases

1. **Skeleton** — `demo.h`/`demo.c`/`dat_demo.c` with all 0x2F script rows `{ 0, NULL }`,
   `-demo` argument, build wiring. Verify: `make PLATFORM=ST` clean under the existing
   `-Wall -Wextra -Wconversion -Wsign-conversion` set, and `./xrick -demo` plays exactly
   like `./xrick` (empty first submap ⇒ immediate handover, §3.5).
2. **Clock + injection + handover** — the four `game.c` hooks and `demo_end()`. Verify
   with a hand-written two-event script (`RIGHT` down at tick 0, up at tick 20) on
   submap 0: Rick walks, then the keyboard works again on the next submap.
3. **Screens** — map-intro auto-advance, `demo_end()` at `FADEOUT__GAMEOVER`. Verify:
   `-demo` reaches gameplay with no keypress.
4. **Recorder** — `-record`. Verify: record a take, regenerate `dat_demo.c`, replay,
   compare the on-screen result.
5. **Author the data** — incremental, by the user (D4): one submap at a time, recorded
   then hand-tuned. The table already has a row for every submap from phase 1, so each
   new script is a self-contained edit and the demo simply runs further before handing
   over.
6. **Polish** — README note, `-demo`/`-record` usage text.

Phases 1–4 are the engine and are independent of how much demo content exists.

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
