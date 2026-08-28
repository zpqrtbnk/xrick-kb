# Dynamic verification with Hatari

The static analysis is done. What remains (**G1** in `../reverse-plan.md`) is a short
list of behavioural details that cannot be settled by reading bytes — they need the
game *running*. This document is the standing record of how we talk to Hatari, what
has been verified about the setup, and the state of each probe.

**Status: harness working end-to-end 2026-08-28.** The game boots unattended to the
title screen under script control, RAM dumps out in the same form as `atari_ram.bin`,
and the relocation delta is measured and self-checked automatically. No probes run yet.

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
| TOS | **EmuTOS 512k 1.4 US** — `../atari/emutos-512k-1.4/etos512us.img` (outside the repo) |
| Machine config | `--machine st --memsize 1` — from the pre-existing `hatari.sh`; the status bar reads `1MB ST(WS3), EmuTOS 1.4.0` |
| Driver | `re/hatari_probe.py` — boots, drives the menus, dumps RAM, measures the delta |

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

## 3. Booting the game — `disks/rd.st` is not a bare game disk

It is a **Fuzion cracktro compilation (CD#12)**. Booting it lands on a menu:
`F1 CHASE HQ / F2 RICK / F3 SUPER SPRINT / F4 QUARTZ`. Selecting F2 (Atari scancode
`0x3C`) then hits a second prompt:

```
TRAINER (Y/N) ?
```

**Always answer N.** A trainer *patches the game code* (infinite lives and so on), so
answering Y would silently invalidate every comparison against `algo-*.md`. This is
not a preference; it is a correctness requirement for the whole exercise.

`re/hatari_probe.py` automates the full chain — boot → F2 → N → title screen — and it
runs unattended. Verified working 2026-08-28.

Debugger syntax confirmed on this build: `savebin <filename> <address> <length>`.
`savebin <f> 0 0x100000` yields a 1 MB raw image byte-identical in form to
`atari_ram.bin`, so all existing Python tooling parses it unchanged.

## 4. Step zero — re-establish the address base (mandatory, EVERY session)

**Every address in this knowledge base comes from one specific run's memory layout.**
Rick Dangerous is a GEMDOS program, so TOS chooses its load address; a different TOS
version or RAM size relocates the entire image and every documented address becomes
wrong by a constant.

**Measured result: the delta is real, and it is not stable across boots.**

Two runs of the *identical* command, same disk and same config, produced:

| Run | Delta vs `atari_ram.bin` |
|---|---|
| 1 (stopped at the trainer prompt) | `-0x70FE` |
| 2 (through to the title screen) | `-0x7276` |

A 0x178-byte difference between otherwise identical boots. The cracktro loader does
not place the game deterministically, so **the delta can never be hardcoded, cached,
or carried between sessions.** Every probe run must measure it first and rebase every
address before use. `hatari_probe.py` does this automatically and refuses to report a
delta that fails its self-check.

The measurement anchors on `reset_sound_chip`'s absolute PSG pokes — position-
independent by construction — and validates the candidate against the music track
table's type field (all 29 entries must be 0/1/2). `build_sndh.py::find_delta()` is
the canonical implementation; `hatari_probe.py::measure_delta()` mirrors it and
returns the reason on failure.

For reference, `atari_ram_1M.bin` sits at `-0x2054` relative to `atari_ram.bin`.

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

**2026-08-28 — harness commissioned.** Environment verified (nothing needed
installing). Established that `rd.st` is a Fuzion cracktro requiring F2 + a trainer
prompt, and that the trainer must be declined. Automated the boot chain in
`hatari_probe.py`; confirmed `savebin` produces an `atari_ram.bin`-compatible image.
**Key result: the relocation delta varies between identical boots (`-0x70FE` vs
`-0x7276`), so it must be re-measured every session.** No G1 probe run yet.

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
- **Never accept the trainer.** It patches code; observations would not match the
  transcriptions.
- **Never hardcode the relocation delta** — see §4. Measure, self-check, then rebase.
- The `screenshot` shortcut writes `grabNNNN.png` into Hatari's working directory, not
  into `re/hatari/`. Dumps and screenshots are gitignored (large, regenerable).
