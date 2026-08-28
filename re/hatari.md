# Dynamic verification with Hatari

The static analysis is done. What remains (**G1** in `../reverse-plan.md`) is a short
list of behavioural details that cannot be settled by reading bytes — they need the
game *running*. This document is the standing record of how we talk to Hatari, what
has been verified about the setup, and the state of each probe.

**Status: environment verified 2026-08-28, no probes run yet.**

---

## 1. Environment — all confirmed present, nothing to install

| Thing | Value |
|---|---|
| Host | Windows 11, WSL2 **Debian 13 (trixie)** |
| Hatari | **v2.5.0**, `/usr/bin/hatari` |
| Display | **WSLg working** — `DISPLAY=:0`, `WAYLAND_DISPLAY=wayland-0` |
| hconsole | **packaged**: `/usr/share/hatari/hconsole/hconsole.py` |
| Repo from WSL | `/mnt/d/d/reverse/xrick` — no copying needed |
| Disk images | `disks/rd.st`, `disks/rd.msa` (also `rd2.st`, `RICKDA2`) |

Hatari options that matter: `--control-socket`, `--parse`, `--log-file`,
`--trace` / `--trace-file`, `--memstate`, `--memsize`, `--machine`, `--joy1`.

Relevant `--trace` flags: `psg_write`, `psg_read`, `video_color`, `video_addr`,
`cpu_disasm`, `cpu_regs`, `ikbd_cmds`, `int`, `mem`, `os_base`.

## 2. The channel

`hconsole.py` is an **importable Python module**, not just an interactive console.
That is the key fact: we script whole experiment batches in one process instead of
trading one experiment per turn.

```
re/hatari_probe.py                       (driver — we write this)
  └ imports hconsole
      └ binds an AF_UNIX socket, listens, then launches
        `hatari --control-socket <path> …`   (Hatari is the CLIENT; it connects to us)
          ├─ commands IN  → hatari-debug / hatari-event / hatari-option /
          │                 hatari-shortcut / hatari-path / hatari-toggle
          └─ results OUT  → NOT the socket. Debugger output goes to the log file.
```

**The asymmetry is the thing to remember: the control socket is command-only.**
Nothing comes back on it. Results are read by tailing the file set with the debugger's
`logfile` command (or `--log-file`). Every probe therefore has two halves: send, then
parse the log.

Useful `hconsole` methods: `debug_command(cmd)`, `insert_event(ev)`,
`send_string(text)`, `change_option(opt)`, `trigger_shortcut(s)`, `toggle_pause()`,
`kill_hatari()`, plus `Main.run(line)` and `Main.script(file)`.

Vocabulary confirmed from the source:

- **events**: `keypress`, `keydown`, `keyup`, `text`, `doubleclick`, `rightdown`,
  `rightup` (with a `Scancode` table for non-alphanumeric keys)
- **shortcuts**: `screenshot`, `savemem`, `coldreset`, `warmreset`, `recanim`,
  `recsound`, `bosskey`, `mousegrab`
- **debugger**: `breakpoint`, `cont`, `cpureg`, `disasm`, `memdump`, `memwrite`,
  `evaluate`, `info`, `history`, `lock`, `logfile`, `loadbin`, `address`, `help`

`change_option()` accepts essentially any command-line option at runtime, so `--trace`
and `--joy1` can be flipped mid-session.

### Fallback

If the socket ever misbehaves, `hatari --parse <file>` executes a debugger command
file at startup, with `:trace` breakpoints logging without ever halting the machine.
Same evidence, no interactivity. Not expected to be needed.

## 3. Step zero — re-establish the address base (mandatory)

**Every address in this knowledge base comes from one specific run's memory layout.**
Rick Dangerous is a GEMDOS program, so TOS chooses its load address; a different TOS
version or RAM size relocates the entire image and every documented address becomes
wrong by a constant.

Before any probe is trusted:

1. Run with `--machine st --memsize 1024` to match the snapshot's configuration.
2. Dump RAM once the game is running (debugger `savebin`, or the `savemem` shortcut).
3. Run **`find_delta()` from `build_sndh.py`** on the dump — it anchors on
   `reset_sound_chip`'s absolute PSG pokes (position-independent by construction) and
   self-checks the result against the music track table's type field.

Do not restate the anchor constant here; reuse that function so the two cannot drift.

If the delta is `0`, every documented address is live as-is. If not, apply it
uniformly and **record the value in §6 below**. This is a five-minute first run that
de-risks everything after it, and it already caught one wrong assumption when the 1 MB
dump turned out to sit at −0x2054.

## 4. Driving the game

Rick Dangerous is joystick-controlled. Set `--joy1 keys` (keyboard joystick emulation)
and drive with `hatari-event keypress <scancode>`; the `Scancode` class in
`hconsole.py` has cursor keys and the rest. Menus and the name-entry screen take
`send_string()` directly.

**Save states are the fixtures.** Reaching Egypt by playing is slow and
non-repeatable. Get there once, `savemem`, and start every later experiment from that
exact state with `--memstate`. This is what makes differential experiments possible at
all: change one variable, reload, compare.

Prefer **forcing** a condition with `memwrite` over playing to reach it. For the
easter egg, the trigger bits and the name-entry glyphs we do not need the condition
reached legitimately — writing the flag from a known state isolates one variable and
is stronger evidence than observation.

State files live in `re/hatari/states/` and are **not** committed (binary, large,
regenerable).

## 5. Probe plan — the G1 items

| # | Item | Technique | Status |
|---|---|---|---|
| 1 | Remaining tile-attribute bits; the `0x6F` probe mask | `:trace` breakpoint on the attribute probe logging tile + attribute + branch taken; then `memwrite` a bit onto a known tile and observe | pending |
| 2 | POOKY easter egg effect | `memwrite` the flag from a save state; screenshot + `video_color` trace | pending |
| 3 | Enemy-variant → creature mapping | `:trace` on the spawn path logging (room, placement type, variant, sprite bank) — one pass yields the whole table | pending |
| 4 | Trigger-bit behaviour | `:trace` on the placement-flag consumer | pending |
| 5 | Landing rebound `nVelY = 0xFE - nVelY` | breakpoint at the instruction, log `nVelY` before/after with player Y | pending |
| 6 | Four unidentified name-entry glyphs | `memwrite` the codes into the name buffer, screenshot | pending |
| 7 | `player_touched_hazard` consumer | value-changed breakpoint on the variable, log PC | pending |
| 8 | Song-0 transpose | `--trace psg_write --trace-file`, diff against `algo-music.md`'s predicted register writes | pending |

Items 2 and 6 end in screenshots — **visual verification is the user's call**, per the
standing decision on room renderings (`reverse-plan.md` §4).

### Beyond G1

The higher-value use of a working harness is **validating the transcriptions**: run
with a breakpoint on each major function, log the register state, and diff against
what `algo-*.md` predicts. That converts the ~98% estimate from a judgement into a
measurement — which is exactly what `analyze_function_completeness` could not do.

## 6. Findings log

*(empty — append dated entries as probes run: the measured relocation delta first,
then one entry per probe with the evidence and which document it updated)*

## 7. Gotchas

- The control socket returns **nothing**; always pair a send with a log read.
- Hatari **connects to** the socket — the driver must `bind()` and `listen()` first.
  `hconsole` already does this; a hand-rolled driver must not get it backwards.
- `hconsole` refuses to start if Hatari lacks `--control-socket` (its own compatibility
  check, aimed at Windows builds). Ours has it.
- Run Hatari from **WSL**, not from Windows — the Windows build has no control socket.
- Match `--machine st --memsize 1024`, or the relocation delta changes under you.
- `savemem` saves a Hatari *state snapshot*; a raw RAM image (what our Python tooling
  parses) comes from the debugger's `savebin`.
