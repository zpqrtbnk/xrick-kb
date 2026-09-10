# Dynamic verification with Hatari

The static analysis is done. This document is the standing record of how we talk to
Hatari, what has been verified about the setup, and the state of the eight behavioural
probes (§6) that were flagged as needing the game *running*.

**Status: harness fully working 2026-08-29.** The correct build boots unattended to
gameplay, the address base reproduces the Ghidra dump exactly, and Rick is driveable
under script. Of the eight probes, **7 are resolved and 1 is optional** — several fell
to Ghidra xref censuses rather than to watching. The harness's remaining job is
validating the transcriptions against the running game (`../PLAN.md` T1).

---

## 1. Environment — all confirmed present, nothing to install

| Thing | Value |
|---|---|
| Host | Windows 11, WSL2 **Debian 13 (trixie)** |
| Hatari | **v2.5.0**, `/usr/bin/hatari` |
| Display | **WSLg working** — `DISPLAY=:0`, `WAYLAND_DISPLAY=wayland-0` |
| hconsole | **packaged**: `/usr/shakb/hatari/hconsole/hconsole.py` |
| Repo from WSL | `/mnt/d/d/reverse/xrick` — no copying needed |
| TOS | **EmuTOS 512k 1.4 US** — `../atari/emutos-512k-1.4/etos512us.img` |
| Machine config | `--machine st --memsize 1`; status bar reads `1MB ST(WS3), EmuTOS 1.4.0` |
| Driver | `kb/hatari_probe.py` |

Relevant `--trace` flags: `psg_write`, `psg_read`, `video_color`, `video_addr`,
`cpu_disasm`, `cpu_regs`, `ikbd_cmds`, `int`, `mem`, `os_base`.

## 2. The channel

`hconsole.py` is an **importable Python module**, not just an interactive console, so
whole experiment batches run in one process.

```
kb/hatari_probe.py
  └ imports hconsole
      └ binds an AF_UNIX socket, listens, then launches
        `hatari --control-socket <path> …`   (Hatari is the CLIENT; it connects to us)
          ├─ commands IN  → hatari-debug / hatari-event / hatari-option / hatari-shortcut
          └─ results OUT  → NOT the socket. They arrive on Hatari's stdout.
```

**The control socket is command-only — nothing comes back on it.** Collect results
from stdout: `python3 kb/hatari_probe.py <probe> 2>&1 | tee run.log`. The debugger's
`logfile` command is unreliable here (it reports the file opened, but the buffer was
empty at kill).

Confirmed vocabulary: **events** `keypress/keydown/keyup/text/doubleclick/rightdown/
rightup`; **shortcuts** `screenshot/savemem/coldreset/warmreset/recanim/recsound/
bosskey/mousegrab`; **debugger** `b(reakpoint)/cont/cpureg/disasm/memdump/memwrite/
evaluate/info/history/lock/logfile/loadbin/savebin/address/help`.
`change_option()` accepts any command-line option at runtime.

## 3. Booting — use `chaos43`, **not** `rd.st`

**`disks/chaos43/RICK.PRG` is the build the Ghidra dump was taken from.** It
reproduces the documented layout exactly: delta `-0x2054`, identical to
`atari_ram_1M.bin`. Autostart it from a GEMDOS drive — no floppy, no mouse, no
compilation menu:

```
hatari --machine st --memsize 1 --tos <emutos> \
       --harddrive ~/rickhd --auto C:\RICK.PRG
```

`~/rickhd` is staged by `hatari_probe.py::stage_hd()` with `RICK.PRG`, `RICK2.PRG` and
the `RICK_*.HNK` hunks, **deliberately excluding the `AUTO` folder** — `AUTO/MENU44.PRG`
would launch the Chaos compilation menu and steal the boot.

The sequence is then:

```
trainer menu    F1 Infinite Lives / F2 Infinite Ammo / F3 Infinite Dynamite
                F4 Select Level        -- ALL DEFAULT OFF
                "Press space to play"
title screen
gameplay        entered by asserting FIRE (see §5)
```

**Leave F1–F3 OFF.** They patch game code and would invalidate any comparison against
`algo-*.md`. **F4 (Select Level) is the route to Egypt / Castle / Missile Base** and
removes the need for save-state fixtures — but verify first whether enabling it patches
code or merely sets `level_index`; dump RAM with it on and off and diff.

### `disks/rd.st` is a different game build — do not use it

It is a Fuzion cracktro compilation (CD#12): an `F1–F4` menu, then a `TRAINER (Y/N)?`
prompt. It has **its own loader and a different relocation** (`-0x70FE` at the trainer
prompt, `-0x7276` at the title, moving 0x178 bytes between the two). It is *not* the
analysed binary. Time was lost here before `hatari.sh` — which had pointed at
`chaos43.msa` all along — was taken seriously.

The packed disk files contain no recognisable code: the anchor appears in none of
`RICK.PRG`, `RICK2.PRG`, the `.HNK` hunks or `chaos43.msa`. The game only materialises
in RAM, so all verification must be against a live dump.

## 4. Step zero — re-establish the address base

Rick Dangerous is a GEMDOS program, so TOS chooses its load address and every
documented address shifts by a constant. Measure it every session; never hardcode.

On the correct boot path the delta is **`-0x2054`**, and it is **stable across the
title screen and gameplay** (verified repeatedly). That equals `atari_ram_1M.bin`'s
offset from `atari_ram.bin`, which is the strongest available confirmation that we are
running the analysed binary in the analysed configuration.

The measurement anchors on `reset_sound_chip`'s absolute PSG pokes — position-
independent by construction — and validates the candidate against the music track
table's type field (all 29 entries must be 0/1/2). `build_sndh.py::find_delta()` is
canonical; `hatari_probe.py::measure_delta()` mirrors it.

`savebin <file> 0 0x100000` yields a 1 MB raw image byte-compatible with
`atari_ram.bin`, so all existing Python tooling parses live dumps unchanged.

## 5. Driving the game — solved, no extra tooling

`hatari-event` **cannot press fire**: it injects *emulated* IKBD scancodes, while
`--joy1 keys` intercepts *host* SDL keys, and the event vocabulary has no joystick
verb. xdotool was considered and is **not needed**.

Instead, poke the decoded joystick byte the KB documents at **`0x4922B`**
(`joystick1_state`: `01` UP, `02` DOWN, `04` LEFT, `08` RIGHT, `80` FIRE). `keyboard_isr`
only rewrites it when an IKBD packet arrives, and with no joystick attached those are
rare — so a poke sticks. Asserting `0x80` at the title screen starts the game;
direction bits walk and jump Rick. **Verified: he walks right, the view scrolls, and
the opening boulder gives chase.**

**Turn fast-forward OFF for gameplay.** It runs ~48x realtime (measured: 7,331
`music_tick` hits in ~3 wall-clock seconds against a 50 Hz tick), so a 0.35 s poke gap
spans ~17 *emulated* seconds — far too coarse to steer with, and Rick dies to the
opening boulder while an input is still held. `to_game()` drops to realtime once boot
is done. Keep fast-forward ON for booting, which it makes ~40 s instead of minutes.

For frame-accurate input, the next step would be a breakpoint on `player_controller`
with `:file <cmds>` that pokes the byte on every frame. Not yet needed.

Save states (`savemem` + `--memstate`) remain useful as fixtures for deep-level work if
F4 turns out to patch code.

## 6. The eight behavioural probes

| # | Item | Outcome | Status |
|---|---|---|---|
| 1 | Tile-attribute bits; the `0x6F` mask | `0x6F` = `~(0x10\|0x80)`, a **row filter** so one-way/ladder-top register only at the feet. Bits `0x01`/`0x08` are two background classes that **no reader tests** (all three LUT readers enumerated via Ghidra xrefs). | ✅ **resolved** |
| 2 | POOKY easter egg effect | Sets `menu_enabled` (`0x498C4`). With `max_level_reached` (`0x498C2`) non-zero it opens the game's own **SELECT LEVEL** screen — observed on screen, all four levels. | ✅ **resolved** |
| 3 | Enemy-variant → creature mapping | Resolved statically: 476-record placement scan gives bank-per-level, and each bank rendered (`enemy_banks.png`). Tribesman / white-robed fez guard / two green soldiers; Castle and Missile Base share both soldier banks. | ✅ **resolved** |
| 4 | Trigger-bit behaviour | Census: **all 8 bits exercised** across all 4 levels. **Spot-check done 2026-09-04** (`triggers`, `triggers2`): the `0x80` -> trigger -> `0x08` chain and the `0x04`/`0x08` idle-vs-triggered split were all watched firing. Five bits (`0x40`/`0x20`/`0x10`/`0x02`/`0x01`) need a landed attack and were not reached. | ✅ **resolved** |
| 5 | Landing rebound `nVelY = 0xFE - nVelY` | **Not the normal landing path.** Gated on attribute `0x20`, carried by only 4 tiles game-wide (5 rooms). Ordinary ground is `0x40` and branches away at `4C1C0`. These are **bounce surfaces**; gravity `+0x80`/frame clamps at `0x800`, so the max rebound is `-0x702`. Breakpoint never fired across repeated falls at `nVelY` `0x08xx`–`0x0Cxx`. | ✅ **resolved** |
| 6 | Four name-entry glyphs | `0x36` = ◄ RUBOUT; `0x37`/`0x3A`/`0x3B` = `E`,`N`,`D` spelling "END". Only `0x36`/`0x37` are selectable codes; the other two are display-row continuation glyphs. | ✅ **resolved** |
| 7 | `player_touched_hazard` consumer | Exactly **one reader**: `player_controller` at `0x4C06A` (Ghidra xrefs; 6 writers). Was already correct in `algo-player.md` — the plan entry was stale. | ✅ **resolved** |
| 8 | Song-0 transpose | Transpose `0x1C` targets **pattern 8** = `80 06 10 FF`, a single note `b=6` → index 46, period `0x010C` ≈ 466 Hz. In range, deliberate: one high closing accent. No overflow. | ✅ **resolved** |

Items 2 and 6 end in screenshots — **visual verification is the user's call**.

### Probe 4 in detail — the trigger bits, watched firing (2026-09-04)

The `btst` site for each bit executes for **every** trap entity **every** frame no matter
what the bit holds, so breakpointing it proves nothing. `probe_triggers` therefore sits on
each bit's **taken branch**, and on the `*_fired` sites where the associated hit test also
succeeded — 14 detectors, all `:trace :once`, so whatever `b` still lists at the end never
fired.

**Run 1 — level 1, walking right.** Four fired, and the log shows them in causal order:

```
pc = $4b146   (0x4D19A)  0x80 set        -- armed for player-touch, every frame
  ... memwrite joystick = $08 (RIGHT) ...
pc = $4b160   (0x4D1B4)  0x80 FIRED      -- player inside the trigger box
pc = $4b204   (0x4D258)  TRAP TRIGGERED  -- move.b #-1,(0x47,A0)
pc = $4b230   (0x4D284)  0x08 armed      -- lethal while TRIGGERED
```

That is the documented chain end to end: walk right -> player enters the box -> bit `0x80`
succeeds -> `bAnimActive = 0xFF` -> the entity now takes the *animating* branch at
`0x4D278` -> bit `0x08` arms `wHazardActive`. **`0x04` never fired in that room** — the
boulder is not lethal while idle, only once rolling.

**Run 2 — via the game's own level select.** `0x04` (lethal while **IDLE**) fired, together
with `trig_fired` and `0x08` again.

**Together these confirm the `0x04`/`0x08` split in both directions.** That split is
exactly what *Correction #1* in `algo-entities.md` established after the docs had
conflated the two as "always-lethal" — a wrong reading that, by its own note, "survived
nine byte-identity audits". It is now observed, not merely re-read.

**Not reached: `0x40` (stick jab), `0x20` (bullet), `0x10` (explosion), `0x02` (both
disposal routes), `0x01` (one-shot).** Each needs Rick to *land* an attack on a trap
carrying that bit. Blind scripted play does not manage it — run 1 ended `GAME OVER` in the
opening room. Forcing them by poking bullet-active flags and coordinates would prove
reachability, which the census already establishes, not semantics; it was not done.

**Caveat on run 2's location.** The intro screen shown was the Missile Base, but the final
gameplay screenshot is level 1's opening room, so the run spanned a level-4 start and a
post-`GAME OVER` return to level 1. The `level_index` dump was taken over the word's
**high** byte only and read `00`, which is uninformative either way. So `0x04` is
confirmed to fire in shipped gameplay, but **which room it fired in is not pinned down**.

### Beyond the probes

The higher-value use of the harness is **validating the transcriptions**: breakpoint
each major function, log register state, diff against what `algo-*.md` predicts. That
turns the ~98% estimate from a judgement into a measurement — which is exactly what
`analyze_function_completeness` could not do.

## 7. Findings log

**2026-09-04 — T11, the Timer-A sample rate, measured.** `probe_timera`. No gameplay
needed: poking what `play_music`'s type-2 branch writes (`0x45000`/`0x45001` TACR/TADR,
`0x44FFC` sample start, `0x45002 = 2`) starts a digi sample deterministically, and holding
`0x45004` non-zero loops it indefinitely. The ISR advances `0x457C8` one byte per
interrupt, so the pointer is the counter. 24 readings / 19.6 s → **4915.7 bytes/s** vs the
**4915.2 Hz** predicted for `TACR=6, TADR=5`; ratio **1.0001**. Confirms
`prescaler(6) = /100` and the 2457600 Hz clock. Note `memdump $a-$b` returns **b−a bytes**,
not b−a+1, so a 4-byte request yields 3 — the low byte of the pointer was never read, and
the 256-byte resolution is why the fit is over many samples rather than one pair.

**2026-09-04 — T6, trigger bits watched firing.** See §6 probe 4 for detail.

**2026-08-28 — harness commissioned (against the wrong disk).** Environment verified;
nothing needed installing. Automated a boot chain for `rd.st` and measured its
stage-dependent relocation. Superseded: `rd.st` is not the analysed build.

**2026-08-29 (third pass) — six of eight resolved.** Items 5 and 8 fell to reading
rather than watching. Item 5 turned on noticing that attribute `0x20` is carried by
only 4 tiles game-wide, so the rebound is a bounce-surface special case and the
breakpoint's *silence* across many falls was the confirming evidence, not a failure.
Item 8 needed only decoding the pattern the transpose actually applies to. Items 3 and
4 (enemy variants, trigger bits) remain — both need watching the game play.

**2026-08-29 (later) — four probe items resolved.** Level select reached by setting the
POOKY flag plus `max_level_reached`, with **no code patching** — the cracktro's F4 is
not needed. Items 1, 6 and 7 fell to static work once Ghidra was back: enumerating the
readers of a global is decisive in a way that reading transcriptions is not. Items 3,
4, 5, 8 remain.

**2026-08-29 — correct build, gameplay under script.** `disks/chaos43/RICK.PRG`
autostarted from a GEMDOS drive reproduces the analysed layout exactly (`-0x2054`,
matching `atari_ram_1M.bin`). Its trainer menu is keyboard-driven and exposes a level
selector. Gameplay reached and Rick driven by poking `joystick1_state`; no xdotool, no
save states, no host-key problem. Two false conclusions retracted — see §8.

## 8. Gotchas — each one cost a run

- **Never use `:quiet` as a detector.** It suppresses the per-hit `:trace` output, and
  the `b` listing has **no hit counter**, so a firing breakpoint looks identical to one
  that never fired. This produced a confident and wrong "`keyboard_isr` and
  `player_controller` never run" reading. Use **`:trace :once`** — one line on the first
  hit, then it deletes itself; still being listed by `b` means it never fired.
- **Boot the build you analysed.** Findings from `rd.st` describe a different loader.
  The repo's own `hatari.sh` pointed at `chaos43.msa` from the start.
- **Never accept a trainer / leave F1–F3 off.** They patch code.
- **Turn fast-forward off before trying to steer** (§5).
- Collect results from **stdout**, not the debugger `logfile`.
- The `screenshot` shortcut writes `grabNNNN.png` into Hatari's working directory, not
  into `kb/hatari/`. Dumps and screenshots are gitignored.
- `savemem` saves a Hatari *state snapshot*; a raw RAM image comes from `savebin`.
