> **File role: WORK LOG.** This is the detailed, evidence-heavy reverse-engineering
> log for Rick 2 (`RICK2.PRG`) — full decompiles, disassembly excerpts, addresses,
> struct layouts, and the reasoning behind each conclusion, written as a
> chronological session log (newest findings appended at the end; earlier
> sections may show questions later resolved further down). This file is
> append-only historical evidence: nothing is ever deleted from it, but
> documentation audits (2026-09-16, and a 2026-09-22 sweep that found
> three more, now-corrected claims later re-verified directly against the
> disassembly) added inline `SUPERSEDED` annotations at points where an
> earlier statement was later corrected — each annotation points forward
> to the section (or, for the 2026-09-22 batch, to `kb2/xrick2-ref.md`)
> with the corrected finding.
> Use this file when you need the actual evidence for a claim. For a fast,
> topic-organized summary of what's currently established, see
> [xrick2-ref.md](xrick2-ref.md) instead; for a consolidated list of every
> contradiction, unverified assumption, and genuine open question found
> across both documents, see [xrick2-gaps.md](xrick2-gaps.md).

# Investigating the .HNK files

## Question

On `disks/chaos43`, alongside `RICK.PRG` and `RICK2.PRG`, there are 8 chunk
files:

```
RICK_01.HNK      68 bytes
RICK_02.HNK   27976 bytes
RICK_03.HNK     166 bytes
RICK_04.HNK   32450 bytes
RICK_05.HNK      76 bytes
RICK_06.HNK   31982 bytes
RICK_07.HNK     118 bytes
RICK_08.HNK   34178 bytes
RICK.PRG      93326 bytes
RICK2.PRG    140202 bytes
```

Open question: when the crack intro (`RICK2.PRG`, see [xrick2-ref.md](xrick2-ref.md))
is showing its "press a key" screen, is the full game already resident in
memory, or are the `.HNK` files loaded afterward (i.e. after the keypress,
before/during the real game intro)?

## What we know so far (inference only, not yet verified)

- The `.HNK` files come in 4 small/large pairs:
  `(68, 27976)`, `(166, 32450)`, `(76, 31982)`, `(118, 34178)`.
  This pattern (one tiny file + one large file per pair) looks like 4
  resources each split into a small header/metadata chunk and a larger data
  blob — plausibly per-level graphics, tilemaps, or music data.
- This is *not* proof of load timing — naming/size alone doesn't tell us
  whether the loader reads these before or after the crack screen's
  keypress.
- `RICK.PRG` (93KB) and `RICK2.PRG` (140KB) are two different executables on
  the disk. We've been booting `RICK2.PRG` directly (see rick2.md); haven't
  yet investigated what `RICK.PRG` is for (original uncracked game? a
  different loader stage?).

## Decision on approach

Asked the user how to determine load timing empirically/statically; chose:
**disassemble RICK2.PRG in Ghidra** to find the code paths that open/read
the `.HNK` files, and determine whether that loading logic runs before the
intro's keypress-wait loop or only after it.

(Two other options considered but not chosen for now: live-tracing GEMDOS
`Fopen` calls via Hatari's debugger/cmd-fifo while running the boot
sequence, or doing both. Revisit if static analysis alone isn't conclusive.)

## RAM dumps captured

Two live memory dumps of the running game were taken via Hatari's debugger
(`hatari-debug savebin 0 0x100000` over `--cmd-fifo`, see `xrick2-ref.md`'s
automation section), saved to `prg2-ram.bin` (full 1MB ST RAM, always
overwritten in place — treat as "latest snapshot", not versioned history):

1. **First attempt (discarded as unreliable):** dumped only ~4s after the
   crack-screen keypress. Too early — the user determined the game intro
   wasn't actually playing yet at that point (no sound/music underway), so
   this dump likely still shows loader/setup state rather than the running
   intro.
2. **Second attempt (current `prg2-ram.bin`):** waited 20s after the
   keypress before touching anything, to give the intro time to actually
   start playing (music/sound should be audible by then). At the moment of
   this dump, captured the CPU's live state via the debugger (see below) as
   a hint for where the game's code/data actually live in the dump.

Two more full 1MB dumps were captured in a later session, this time timed to
land exactly at the moment `RICK_01.HNK` and `RICK_02.HNK` are loaded (see
"Pinpointing exactly when RICK_01.HNK / RICK_02.HNK load" below for the full
methodology):

3. **`dump_hnkload_hit1.bin`** — captured 2026-09-11 15:45:59 CEST
   (`mtime` down to the second), ~2.7s after the crack-screen keypress
   (sent 15:45:57 CEST), at VBL frame counter value **`$0066` (102)**. PC at
   capture = `$73f0` (the depacker's real entry, validating the `"LSD!"`
   magic), with `A1 = $0003EFC0` pointing at a buffer whose first 32 bytes
   are byte-for-byte identical to `disks/chaos43/RICK_01.HNK`'s header.
   **This is the RICK_01.HNK load.**
4. **`dump_hnkload_hit2.bin`** — captured 2026-09-11 15:46:01 CEST,
   ~4.4s after the same keypress (~1.7s after hit 1), at VBL frame counter
   value **`$00CE` (206)** — 104 VBL frames (~2.08s at 50Hz) after hit 1. PC
   at capture = `$73f0` again, with `A1 = $00065300` pointing at a buffer
   byte-for-byte identical to `disks/chaos43/RICK_02.HNK`'s header.
   **This is the RICK_02.HNK load.**

No third hit on the same breakpoint occurred in the ~45s the trace was left
running afterward (game execution continued normally, VBL counter kept
advancing) — in this run, exactly two `.HNK` loads happen back-to-back
shortly after the crack-screen keypress, and they are RICK_01 then RICK_02,
~2 seconds apart.

### Live execution hint (from the second dump)

CPU registers/disassembly sampled right around the dump (via
`hatari-debug cpureg` / `hatari-debug disasm`, emulation left running, not
paused — see gotcha below):

- **PC at dump time: `$191FA`** — instruction `cmp.w $19232,d1`, part of a
  tight loop (`bgt.b` from `$19200` branching back to `$191FA`). Reads as a
  VBL/timer-sync wait loop — plausible for intro animation/music timing.
- Execution was seen moving within roughly **`$18600`–`$19200`** across two
  samples a couple seconds apart — a stable, narrow code region, not a
  one-off transient address. This is a strong candidate for "the intro's
  main code," and a good starting point in Ghidra for finding the intro
  loop and working outward from there.
- While in that region, saw `movem.l` block-copy code moving structured data
  (0x30/0x40-byte records) from a template around **`$69930`** to
  destinations around **`$7D830`/`$7D860`/`$7D870`**, and a byte-copy loop
  between **`$57D01`** (source, via `a5`) and **`$6D038`/`$6D039`**
  (destination, via `a3`). These addresses are all well outside where
  `RICK2.PRG`'s own ~140KB program image would sit if loaded contiguously —
  they're strong candidates for **where `.HNK` file contents (or data
  unpacked from them) end up at runtime**. Worth checking in the RAM dump
  directly (e.g. via Ghidra's string/byte search) for content that matches
  known `.HNK` file bytes, to confirm they're already loaded by this point.

These addresses/observations are now annotated directly in the Ghidra
program (see below) rather than only living in this doc.

### Ghidra state

- Ghidra was already running, connected to project `xrick2-prg`
  (`ghidra.xrick2/xrick2-prg.gpr`), containing `GXUT275-rw.PRG` and an
  earlier `full_ram_dump.bin` (imported in a prior session, already had 427
  functions from manual analysis — auto-analysis alone doesn't find
  functions in a raw dump with no code hints).
- Imported the corrected `prg2-ram.bin` as **`/prg2-ram.bin.0`** in that
  same project (same settings as `full_ram_dump.bin`: raw binary, language
  `68000:BE:32:default`, big-endian, base address 0). It's named `.0`
  because an earlier (stale, first-attempt) import of `prg2-ram.bin` was
  still open/in-use in the Ghidra GUI and couldn't be deleted via the MCP
  bridge — that stale one should be manually closed/deleted in the GUI and
  `/prg2-ram.bin.0` is the one to use.
- Annotated `/prg2-ram.bin.0` at `$191FA` with a bookmark (category
  "Analysis") and a label (`PC_at_dump_time_intro_wait_loop`) recording the
  full context above. Also created a function stub at `$18826`
  (`intro_data_unpack_maybe`) covering the `movem.l` copy code seen there —
  name is a guess, rename once actually analyzed.

### Gotcha: Hatari's `--cmd-fifo` and pausing don't mix well

Discovered while doing the above — worth remembering for future automation:

- Hatari only reads the cmd-fifo from inside its SDL event loop. When
  emulation is paused (`hatari-stop`), that loop switches to a **blocking**
  `SDL_WaitEvent`, so further fifo commands (including `hatari-cont` to
  resume!) may sit unread indefinitely — it isn't reliably driven by a
  timer, so this can deadlock the process. **Avoid `hatari-stop` when
  scripting the fifo; just issue commands while emulation keeps running.**
  State drifts by only a few instructions between commands, which is fine
  for sampling PC/registers/memory.
- Separately, killing a stuck Hatari process can apparently unlink the fifo
  special file from under a *different* still-running instance; a plain
  shell redirection (`echo ... > path`) into that now-missing path then
  silently creates a **regular file** at that path instead of erroring.
  Symptom: commands stop having any effect, with zero error output. Check
  `ls -la <fifo path>` — it must show `prw-------`; if it shows a regular
  file (`-rw-...`), the pipe is gone and the target process needs a fresh
  restart with a newly created fifo.

## Findings from analyzing the memory dump in Ghidra

Everything below refers to program `/prg2-ram.bin.0` in Ghidra project
`xrick2-prg` (the corrected, 20s-wait dump). All addresses are absolute ST
RAM addresses (the dump is loaded 1:1, base 0).

### (a) What's in memory: an LZ-style depacker at `$7400`–`$758E`

Disassembling the region right around the "RICK_02.HNK" string hit (see
below) turned up a small, self-contained decompression routine, now
labeled `lz_depack_backward` in Ghidra and bookmarked at `$7400`:

- Classic ST-cracker/demo-scene "bit reader" idiom: a byte is shifted with
  `lsl.b #1,D0`/`roxl.b #1,D0` to peek bits one at a time, refilling `D0`
  from `-(A0)` (i.e. reading the packed stream *backward* from its end)
  whenever it's exhausted.
- Several small escape/length tables embedded as inline data right after
  `lea (n,PC),A3`-style code, at `$7472`, `$74ca`, `$7516`, `$7558` — used
  to decode run lengths / back-reference distances (a small Huffman-ish or
  unary-coded length scheme).
- Output is written *backward too*, via `move.b -(A0),-(A1)` copy loops —
  the standard trick for in-place decompression when the compressed data
  and the decompressed output share the same buffer (decompress from the
  end towards the start so you never overwrite data you still need to
  read).
- The routine is entered at `$7400`, which first copies a small header/
  table to a fixed scratch address `(0x8000).l`, then does two block
  copies via a helper at `$7444`, before falling into the bit-stream
  decode loop and returning via `rts` at `$758E`.

This strongly looks like the runtime depacker for whatever asset format the
`.HNK` files (or resources baked into `RICK2.PRG` itself) use — `.HNK`
files are almost certainly *packed* ("chunk") resources, decompressed by
exactly this kind of routine before use.

**Caveat:** I could not find the *caller* of this routine. `get_xrefs_to`
on `$7400` and `$7590` both return no results, and a byte-pattern search
for the absolute-addressing encodings of `JSR $7400`/reference to `$7590`
found nothing. This is expected for a raw memory dump with no prior
disassembly: Ghidra only builds a reference database from code it has
actually disassembled, and nothing calling into this region has been
touched yet. The call is most likely a `bsr.w` with a small relative
displacement from somewhere in the intro's own code ($18xxx region), which
can't be found by searching for an absolute address — it would require
either walking all of the intro's code by hand, or getting Ghidra's
auto-analysis to run over the whole image (not attempted yet — see next
steps).

### (b) `RICK_02.HNK` is present in memory during the intro — but no other `.HNK` file is

- `search_byte_patterns` for the ASCII bytes of `"RICK_"` found exactly one
  hit in the whole 1MB dump: address `$7596`.
- `inspect_memory_content` around it shows a null-terminated string
  `"RICK_02.HNK\0"` starting at `$7590` (now labeled
  `str_RICK_02_HNK_reused_buffer`), immediately followed by many zero
  bytes — i.e. it sits in a reused/oversized fixed buffer, not a tightly
  packed string table.
- It sits **immediately after** the depacker's `rts` at `$758E` — so
  either it's inert leftover data at a fixed buffer address that happens to
  follow the depacker in the binary's layout, or (more interesting) it's
  the *name argument* that was passed to whatever routine opened
  `RICK_02.HNK`, sitting in a buffer that just happens to be adjacent to
  the depacker code in memory. Without a resolved caller (see caveat
  above) I can't yet tell which.
- A systematic follow-up search checked all 8 filenames
  (`RICK_01.HNK`…`RICK_08.HNK`) plus `RICK.PRG`/`RICK2.PRG` as ASCII
  strings across the entire dump:

  | String | Found? | Address | Notes |
  |---|---|---|---|
  | `RICK_01.HNK` | No | — | |
  | `RICK_02.HNK` | **Yes** | `$7590`/`$7596` | reused buffer, see above |
  | `RICK_03.HNK`…`RICK_08.HNK` | No | — | |
  | `RICK.PRG` | No | — | |
  | `RICK2.PRG` | **Yes** | `$f6ff`/`$f70f` | full string is `A:\RICK2.PRG`, sitting alone in a large zero-padded buffer — this is very plausibly the GEMDOS command-line/basepage argument buffer for the program that was actually launched (i.e. leftover from TOS's own `Pexec`/AUTO-boot machinery), not something the game wrote itself. |

**Conclusion on load timing:** by ~20s after the crack screen's keypress
(intro playing, music audible), **only `RICK_02.HNK`'s filename is
resident in memory**, and none of the other 7 `.HNK` files' names are
present anywhere in the 1MB dump. This is reasonably strong evidence that
the game loads `.HNK` files **one at a time, on demand**, rather than
loading the whole game/all levels up front during the crack intro. Since
`RICK_02.HNK` is the pairing partner of tiny `RICK_01.HNK` (68 bytes) —
see the size-pairing analysis at the top of this doc — this is consistent
with "small header/metadata chunk read first, triggers loading + depacking
of its paired large data chunk," which is exactly the depacker code found
in (a). It does **not** confirm whether loading happens *before* or
*during* the crack screen's wait loop itself (the dump was taken well
after the keypress) — only that it's not "everything loaded at once
up-front."

### (c) What happens when the user presses a key: a hand-rolled ACIA keyboard driver, not GEMDOS

The game does **not** use GEMDOS/XBIOS keyboard calls (`Bconin`, `Cnecin`,
etc.) or even the standard TOS IKBD packet protocol. It installs its own
raw interrupt handler directly on the 68000 keyboard vector:

- **`install_ikbd_vector_118` @ `$1a502`**: `move.l #$1a546,($118).l` —
  overwrites the CPU's keyboard interrupt vector at absolute address `$118`
  to point at the game's own handler (`custom_keyboard_isr`, see below).
  Immediately after, it calls a small helper at `$1a520`
  (`bset.b #6,($fffa09).l` / `bset.b #6,($fffa15).l` — enabling the
  relevant MFP interrupt-enable/mask bits), then sends two command bytes
  (`$12`, `$14`) to the keyboard ACIA one at a time via a busy-wait send
  routine at `$1a532` (`move.b ($fffc00).l,D1b` / `btst.l #1,D1` / loop
  until TX-ready, then `move.b D0b,($fffc02).l`) — this looks like it's
  reprogramming/resetting the IKBD with custom command bytes rather than
  using its default packet mode.
- **`custom_keyboard_isr` @ `$1a546`** (the actual interrupt handler,
  installed at `$118`, ends in `rte`): on every keyboard IRQ it reads the
  raw byte from the ACIA data register `$fffc02` directly (no IKBD packet
  parsing at all) and:
  - if the byte is the sentinel `$FE`, it sets a one-shot flag at
    `$1a5ca` and does **not** treat it as a scancode — the *next*
    interrupt's byte instead gets stored to `kbd_flag_or_byte_1` (`$1a4fa`)
    and the flag is cleared;
  - if the byte is the sentinel `$FF`, likewise via a flag at `$1a5cc`,
    redirecting the next byte to a second slot at `$1a4fb`;
  - otherwise (the common case — plain key up/down scancodes) it's stored
    straight to `kbd_last_scancode` (`$1a4fc`).
  - In all cases it clears MFP in-service bit 6 at `$fffa11` before
    `rte`-ing back.

So keypresses are captured as raw IKBD scancodes into three fixed low-memory
byte slots (`$1a4fa`, `$1a4fb`, `$1a4fc`), polled by the main game code —
this matches the wait-loop pattern already seen in the intro's stable
`$18400`–`$18780` code region, which repeatedly does
`btst.b #7,($1a4fb).l` / `cmpi.b #0x19,($1a4fc).l` style checks (i.e.
"is a key flagged, and is it *this specific* scancode") to gate animation/
advance-to-next-screen logic — this is very likely (not yet 100% confirmed)
the actual mechanism behind the crack screen's "press a key" prompt and the
intro's own key-driven transitions. The `$FE`/`$FF` sentinel handling
suggests the raw scancode stream also carries the ST's joystick/mouse
packet bytes (which the real IKBD normally prefixes that way in relative
mouse mode) and the driver is filtering those out from plain keyboard
scancodes.

### Follow-up: static evidence that RICK_01/RICK_02 (map 1) has already been consumed, and no other pair has

Prompted by the hypothesis that the 4 small/large `.HNK` pairs correspond to
the game's 4 maps, loaded one pair at a time rather than all up front: since
a single static RAM dump can't show *history*, the way to test "has this
file already been read/decompressed" without a new capture is to look for
physical leftovers — specifically, whether the file's own raw compressed
bytes still exist intact anywhere in RAM (if untouched) or have been
overwritten (if already consumed by the backward, in-place-style depacker
found above).

Using the actual on-disk files in `disks/chaos43/` as ground truth:

- Sampled `RICK_02.HNK` at 0%, 10%, 25%, 50%, 75%, 90%, 95%, 96%, 97%, 98%,
  99% of its length (24-byte windows) and searched each in
  `/prg2-ram.bin.0` — **none** of these matched anywhere in the 1MB dump.
  The file's head and body are gone.
- Binary-searched how much of the *tail* survives: last-96/128/130 bytes
  all matched (at `$8124`/`$8104`/`$8102` respectively — consistently
  ending at `$8184`); last-132/136/144/192/256 bytes did **not** match.
  So **exactly the final ~130 bytes** of `RICK_02.HNK` survive intact, at
  `$8100`–`$8184`.
- `inspect_memory_content` on `$8000`–`$818F` shows this precisely: the
  256 bytes from `$8000`–`$80FF` are **all zero**, then the data block
  starting exactly at `$8100` matches the file's tail byte-for-byte,
  followed by more zeros after `$8184`. This is a genuinely isolated,
  small remnant — not part of some larger still-intact buffer.
- Ran the identical last-130-bytes check against `RICK_04.HNK`,
  `RICK_06.HNK`, and `RICK_08.HNK` (the large partner of each of the other
  3 pairs) — **no matches for any of them**, anywhere in the dump.

**Reading:** `RICK_02.HNK` (part of the map-1 pair with `RICK_01.HNK`) has
left exactly the kind of trace you'd expect from a file that's already been
fully read and depacked: its bulk payload is gone (overwritten, consistent
with the backward in-place decompression scheme in `lz_depack_backward`),
while a small ~130-byte tail fragment — plausibly a footer/control block
read or parsed separately before/after the main decompression — survives
untouched in an otherwise-zeroed staging buffer at `$8100`. None of the
other 3 pairs show even that much of a trace, anywhere. This is solid
static-only support for "only map 1's pair has been loaded so far, by
~20s into the intro" — consistent with per-map, on-demand loading rather
than loading all 4 maps' data during the intro up front.

This does **not** tell us *who* called the depacker or *in what order/with
what arguments* — that information only exists transiently in registers/
stack at call time and is long gone from this static snapshot. That
requires a live trace (see below).

### Live trace: who calls the depacker, and with what — Hatari `--cmd-fifo` breakpoints

Following up on the previous section's open question, this used a live Hatari
session (per the boot procedure in `xrick2-ref.md`) with a **non-stopping**
conditional breakpoint sent over `--cmd-fifo`, avoiding the
stdin-blocking/DebugUI gotcha noted above:

```
hatari-debug history cpu 200000
hatari-debug breakpoint pc=$7400 :once :info registers
hatari-event keypress 57
```

Key mechanism: Hatari's breakpoint options `:trace`/`:lock`/`:info <name>`
print via `stderr` from inside `BreakCond_MatchBreakPoints()` **without**
ever calling `DebugUI()` — so `:info registers` (or `:info history`) dumps
state at the exact PC match and lets emulation keep running, instead of
dropping into the interactive console (which reads from stdin and would hang
a scripted/backgrounded session). `history cpu <N>` enables a per-instruction
ring buffer (`History_AddCpu()`, called every instruction once tracking is
on) that `:info history` can dump atomically at the moment of the hit — this
is what let us walk backward through actual executed code, not just a single
register snapshot.

**Registers at the `$7400` entry (`RICK_02.HNK`'s pair, first hit, fully
reproducible across repeated boots):**

```
D0 00000000   D1 000E0004   D2 0000FFFF   D3 00000014
D4 00000000   D5 0002F7FF   D6 00000005   D7 FFFFFF24
A0 0003EEC0   A1 0003EFC0   A2 0003EEC0   A3 0004AB2D
A4 00008020   A5 FFFF8604   A6 FFFF8606   A7 00011DBE
SR=2304  S=1 (supervisor)
00007400  2848        movea.l a0,a4     <- first instruction, confirms entry
```

A0/A1 (`$3EEC0`/`$3EFC0`) are a *different* pair of working buffers than the
`$8000`/`$8100` staging area identified in the static dump above — i.e. the
loader stages the packed bytes at a scratch address (here `$3EFC0`) before
whatever later step relocates/depacks into the game's fixed `$8000`-region
buffer used elsewhere. The two aren't in conflict; they're different points
in the same pipeline, caught at different moments.

**The actual call chain into the depacker (from `history`, at the instant of
the `$7400` hit), reproducible every run:**

```
00007052  225f        movea.l (a7)+,a1      ; == pops $00007058 into A1
00007054  6100 039a   bsr.w   $000073f0
000073f0  0c91 4c53 4421   cmp.l #$4c534421,(a1)   ; "LSD!" magic check
000073f6  6600 004a   bne.w  $00007442             ; -> error path if absent
000073fa  41e9 ff00   lea.l  (-$0100,a1),a0
000073fe  2448        movea.l a0,a2
   ... (setup continues, eventually reaches $7400)
```

This confirms **`$73f0` is the real header-validated entry point** of the
loader/depacker library, and `$7400` (found first, in the earlier static
session) is a sub-step reached a little further into the same routine after
the `"LSD!"` signature check passes.

**Correction (found during the map-switch investigation below):** the
`movea.l (a7)+,a1` at `$7052` is *not* a "return address as inline data
pointer" trick — that earlier theory was wrong. Fresh disassembly of
`$701c`-`$705c` (now the function `load_and_depack_hnk_file` @ `$7000`)
shows it's ordinary register preservation: `$7042: move.l A1,-(SP)` pushes
A1 as scratch storage before two intermediate `bsr` calls (`$7048` →
`$705e`, `$704a` → `$7136`, both raw disk-I/O related, not yet explored),
and `$7052: movea.l (SP)+,A1` simply restores it afterward so A1 still holds
the destination buffer pointer when `bsr.w $73f0` (the depacker) is called
at `$7054`.

**Also visible in the same instruction history: the busy-wait for the floppy
controller**, which explains why register dumps taken any time after the
hit (rather than atomically with it) show stale/already-progressed state:

```
00007322  0838 0005 fa01   btst.b  #5,$fffffa01.w   ; MFP GPIP bit 5 = FDC/DMA IRQ pending
00007328  66f8             bne.b   $00007322          ; spin until sector DMA completes
```

This is a **raw hand-rolled DMA-completion poll**, not an interrupt-driven
wait and not GEMDOS — consistent with `xrick2-ref.md`'s note that this loader
bypasses GEMDOS via direct sector reads. It also explains why a 200,000
instruction history ring buffer, read at the exact moment of the `$7400`
hit, is *still* saturated end-to-end by this one loop (interleaved with
periodic VBL-driven music-player calls into `$1a866`/`$1aedc`, which write
the YM2149 PSG registers at `$ffff8800`/`$ffff8802` once per frame while the
game is otherwise blocked on disk I/O) — the wait for one sector's worth of
real (emulated) floppy rotation is *much* longer than 200,000 instructions,
so the top-level caller that first decided "go load RICK_02.HNK now" sits
further back than this buffer could reach. That specific top-level call site
remains unidentified — reaching it would need either a vastly larger history
buffer, or a breakpoint placed earlier in the chain (e.g. on the FDC command
register write that starts the sector read, at `$ffff8604`/`$ffff8606`,
which already show up as A5/A6 in the register dump above and are worth
targeting directly next time).

Multiple other `bsr`/`bsr.w` targets clustered in `$7180`–$7442` were seen
repeating across every run (`$7296→$73d6`, `$72ba→$73bc`, `$72c6→$72d6`,
`$7306→$733a`, `$7320→$7386`, `$71b8→$7282`, `$7290→$738e`, `$7398→$73a0`,
`$71dc→$7282`, `$72ec→$7344`, `$734e→$733a`, `$7358→$7386`) — all internal to
the same `$7000`–`$7442` block, confirming it's a small self-contained
loader+depacker library with several helper subroutines (poll/read/verify/
copy), rather than a single monolithic function.

### Pinpointing exactly when RICK_01.HNK / RICK_02.HNK load

Building directly on the `$73f0` entry point found above, and its
`"LSD!"`-validated `A1` pointer being the start of the packed file's raw
bytes: since the loader is called exactly once per `.HNK` file, and the file
being loaded is fully identified by comparing the bytes at `A1` against the
known on-disk `.HNK` files, a multi-hit breakpoint plan lets us both time and
identify each load in one deterministic pass, without needing to reach back
to the (still-unidentified) top-level caller.

**Setup** (fresh boot per `xrick2-ref.md`, `--cmd-fifo` armed before the crack
screen's keypress):

```
hatari-debug history cpu 5000
hatari-debug breakpoint pc=$73f0 :once      :info registers :file /tmp/cmds_hit1.txt :trace
hatari-debug breakpoint pc=$73f0 :2 :once   :info registers :file /tmp/cmds_hit2.txt :trace
hatari-debug breakpoint pc=$73f0 :3 :once   :info registers :file /tmp/cmds_hit3.txt :trace
```

The `:N :once` skip-counter modifier (see `BreakCond_Options` in
`breakcond.c`) makes each breakpoint track *its own* hit count independently
and fire (then self-delete) only on its Nth match — so three breakpoints on
the *same* condition give three separate, independently-timed atomic capture
points for the 1st, 2nd, and 3rd occurrence of hitting `$73f0`, without
needing to know in advance how far apart they are. Each `cmds_hitN.txt` (run
synchronously via `:file`, see the gotcha section below) does:

```
memdump $19232                                              ; VBL frame counter snapshot
history 3000                                                ; short backward instruction trace
savebin kb2/dump_hnkload_hitN.bin $0 $100000                ; full 1MB RAM dump
```

**Result** (after sending `hatari-event keypress 57` and waiting ~45s):
only **two** hits ever fired — the `:3 :once` breakpoint never matched, so in
this run exactly two loader invocations happen, not three or more. Comparing
the 32 bytes at each hit's `A1` pointer inside its own dump against the
on-disk files in `disks/chaos43/` gives an exact, unambiguous identification:

| Hit | Dump file | Capture time (wall clock) | VBL counter @ `$19232` | `A1` (packed data ptr) | Matches |
|-----|-----------|----------------------------|-------------------------|-------------------------|---------|
| 1 | `dump_hnkload_hit1.bin` | 2026-09-11 15:45:59 CEST (~2.7s after keypress) | `$0066` (102) | `$0003EFC0` | `RICK_01.HNK` (byte-for-byte header match) |
| 2 | `dump_hnkload_hit2.bin` | 2026-09-11 15:46:01 CEST (~4.4s after keypress, ~1.7s after hit 1) | `$00CE` (206) | `$00065300` | `RICK_02.HNK` (byte-for-byte header match) |

(Keypress was sent at 2026-09-11 15:45:57 CEST.) The VBL delta between hits
(104 frames ≈ 2.08s at 50Hz PAL) roughly matches the ~1.7s wall-clock delta
(some slop expected from `--cmd-fifo` command latency and host scheduling).

**Answer to "when are RICK_01.HNK and RICK_02.HNK loaded":** both load
back-to-back within the first ~4.5 seconds after the crack screen's keypress
is registered — RICK_01.HNK first (at VBL frame ~102 after the keypress
advances the screen), then RICK_02.HNK about 2 seconds later (VBL frame
~206) — well before the intro's music/animation is actually playing (which
the earlier `prg2-ram.bin` dump, taken 20s post-keypress, was timed to
catch). No further calls to this loader were observed for at least ~45s
after that, so whatever uses `RICK_03.HNK`–`RICK_08.HNK` (if anything, this
early) either isn't reached yet at that point or uses a different code path.

### Ghidra annotations added this session

In `/prg2-ram.bin.0`:
- Function `lz_depack_backward` @ `$7400`, bookmark with full description.
- Label `str_RICK_02_HNK_reused_buffer` @ `$7590`.
- Labels `install_ikbd_vector_118` @ `$1a502`, `custom_keyboard_isr` @
  `$1a546`, `kbd_flag_or_byte_1` @ `$1a4fa`, `kbd_last_scancode` @ `$1a4fc`,
  with a bookmark on the ISR summarizing the sentinel-byte logic.
- (Carried over from the previous session: label
  `PC_at_dump_time_intro_wait_loop` @ `$191FA`, function stub
  `intro_data_unpack_maybe` @ `$18826`.)

## Next steps (when resuming)

1. In the Ghidra GUI: close/delete the stale `prg2-ram.bin` program, keep
   working in `/prg2-ram.bin.0`.
2. ~~Find the actual caller of `lz_depack_backward` (`$7400`)~~ — **done**
   via a live Hatari `--cmd-fifo` breakpoint/history trace (see "Live trace"
   section above): it's called internally from `$7054` (`bsr.w $73f0`, the
   `"LSD!"`-header-validating true entry point of the `$7000`–`$7442`
   loader library), not from the `$18xxx` region. What's still open is the
   *top-level* caller — whoever first decides to load `RICK_02.HNK` and
   kicks off the sector read — which sits further back than a 200,000
   instruction history window reaches (consumed by the FDC busy-wait loop
   at `$7322`/`$7328`). Next attempt: breakpoint on the FDC/ACSI command
   register write (around `$ffff8604`/`$ffff8606`, seen loaded into A5/A6 at
   the `$7400` hit) to catch the seek/read-initiation moment directly,
   rather than trying to out-size the history buffer.
3. Confirm the `btst.b #7,($1a4fb)` / `cmpi.b #0x19,($1a4fc)` reads in the
   `$18400`–`$18780` region really are the crack screen's/intro's
   keypress-detection logic (currently a strong inference, not confirmed
   by tracing a full call chain back to the "press a key" prompt itself).
4. ~~To pin down *when* `.HNK` loading starts relative to the keypress...~~
   — **done**, see "Pinpointing exactly when RICK_01.HNK / RICK_02.HNK load"
   above: both load back-to-back within ~4.5s of the keypress
   (`dump_hnkload_hit1.bin`/`hit2.bin`). Open follow-up: no third load
   was observed in the ~45s window after — worth extending the observation
   window (or adding a 4th/5th skip-count breakpoint) to see if/when
   `RICK_03.HNK` onward ever load via this same routine, and whether that
   happens on level transitions later in the actual game rather than during
   the intro.
5. Still open: what `RICK.PRG` (the other, non-crack-intro executable on
   the disk) is for — its name doesn't appear anywhere in this RAM dump,
   so nothing new learned about it this session.

## Map/submap structure and the map-1 → map-2 switch (2026-09-11, static analysis)

Investigated the user's hypothesis: "RICK_01/02.HNK = map 1, which has
submaps; when the last submap is reached the game loads the next map's HNK
pair (predicted RICK_03/04.HNK)." Done entirely via **static** analysis
against the already-captured dumps (`prg2-ram.bin`,
`dump_hnkload_hit1.bin`, `dump_hnkload_hit2.bin`) — no new Hatari session —
since this is all fixed code/data, not something that changes between
captures. Ghidra's auto-analysis of the raw dump import never disassembled
most of this code, so `get_xrefs_to` was useless here; the reliable
technique was writing small Python scripts that scan the raw `.bin` file
for `bsr`/`jsr`/`jmp` opcode+displacement patterns (for call sites) or for
a target's 4-byte absolute-address operand (for data read/write sites),
resolving targets by hand. All addresses below are in program
`/prg2-ram.bin.0`.

### The loader chain (bottom-up)

- **`load_and_depack_hnk_file` @ `$7000`** (renamed from `FUN_00007000`) —
  lowest-level loader. `D0` = ASCII digit (`'1'`-`'8'`) for the file number,
  `A0` = destination buffer. Patches the digit into the shared filename
  template at `$7590`/`$759c` (`"RICK_0?.HNK"`), stores the destination
  pointer to global `$8016`, does the raw sector read (via `$705e`/`$7136`,
  not yet explored), then `bsr.w $73f0` to depack (see corrected note
  above about `$7052`).
- **`resolve_hnk_id_by_checksum` @ `$11f86`** (renamed from
  `FUN_00011f86`) — takes two 16-bit "seed" values in `D1`/`D2`, sums them,
  and matches the sum against 8 magic constants mapped 1:1 to file digits
  1-8: `{0xd:'1', 0x59:'2', 0xf:'3', 0xa3:'4', 0x11:'5', 0xec:'6', 0x13:'7',
  0x13a:'8'}`. On a match, sets `D0` to that ASCII digit and calls
  `load_and_depack_hnk_file`. **No match → infinite loop** (anti-tamper
  trap — see below, this is reachable and matters).
- **`load_hnk_pair_by_seed` @ `$11e76`** (renamed from `FUN_00011e76`,
  Ghidra function body extended to its real size) — wrapper taking `A0` =
  pointer to a 2-word seed record (reads `D1`/`D2` from it via
  `(A0)+`), `D0` = destination buffer; saves/restores MFP registers and
  vectors `$68`/`$70`/`$118` (custom keyboard ISR)/`$134` around the call
  to `resolve_hnk_id_by_checksum`, then clears flag byte `$1a4fb`.
- **`load_map` @ `$123c4`** (newly created as a Ghidra function, 250
  bytes) — the general "load both HNK files for map N" routine: reads
  `g_current_map_number` (`$1239c`), stores it to `g_loaded_map_number`
  (`$1239e`), clamps `(map-1)` to `[0,4]`, indexes
  `g_level_descriptor_table` (`$12dd4`, see below), and calls
  `load_hnk_pair_by_seed` **twice** — once with the level's first seed
  pointer and `D0=$3EFC0` (fixed dest, confirmed exact match with
  `dump_hnkload_hit1.bin`'s `A1`), once with the second seed pointer and
  `D0=$65300` (confirmed exact match with `dump_hnkload_hit2.bin`'s `A1`).
  Finishes with `bsr $1795c` (`A0=$65300`, `A1=$53400`) — a post-load
  relocate/merge step, not yet explored.
- **`load_map_if_changed` @ `$12394`** (newly created) — lazy-reload
  guard: `cmp.w g_loaded_map_number,g_current_map_number`; if equal,
  returns immediately; if different, falls through into `load_map`. This is
  the function the main loop calls every frame — it only actually does I/O
  on the frame where `g_current_map_number` has just changed.

### `g_level_descriptor_table` @ `$12dd4`, fully dereferenced

The table holds one pointer per map (5 entries, 4 bytes each), each
pointing at an 8-byte descriptor of two seed-record pointers:

| Map # (table idx) | descriptor[0] → seed (D1,D2) → sum | descriptor[1] → seed (D1,D2) → sum | HNK pair |
|---|---|---|---|
| 1 (0) | `$11e4e` → `(0xb,2)` → `0xd` | `$11e62` → `(0x15,0x44)` → `0x59` | **RICK_01 + RICK_02** (confirmed match to live dumps) |
| 2 (1) | `$11e52` → `(0xd,2)` → `0xf` | `$11e66` → `(0x59,0x4a)` → `0xa3` | **RICK_03 + RICK_04** — confirms the user's prediction |
| 3 (2) | `$11e56` → `(0xf,2)` → `0x11` | `$11e6a` → `(0xa3,0x49)` → `0xec` | **RICK_05 + RICK_06** |
| 4 (3) | `$11e5a` → `(0x11,2)` → `0x13` | `$11e6e` → `(0xec,0x4e)` → `0x13a` | **RICK_07 + RICK_08** |
| 5 (4) | `$11e5e` → `(0x13,2)` → `0x15` (no magic match) | `$11e72` → `(0x13a,0x4b)` → `0x185` (no magic match) | **none — these are `resolve_hnk_id_by_checksum`'s chain *terminator* records** |

The two seed chains (`g_hnk_checksum_chain_table` @ `$11e4e`, 40 bytes: 5
records × 4 bytes for odd-file digits 1/3/5/7/terminator at `$11e4e`-`$11e5d`,
then 5 more for even-file digits 2/4/6/8/terminator at `$11e62`-`$11e75`)
are literally chained — each record's `D1` seed equals the previous
record's `D1+D2` sum, and each ends in a deliberate non-matching terminator.

**This means map index 4 ("map 5") is not a real 5th map with its own HNK
pair — it's wired directly to the anti-piracy trap.** If `g_current_map_number`
ever reached 5 and something tried to actually call `load_map` for it, both
`load_hnk_pair_by_seed` calls would resolve to the checksum-chain
terminator, fail to match any of the 8 magic sums in
`resolve_hnk_id_by_checksum`, and hang in the infinite loop. In practice
this is never hit in normal play — see the level-4/5 special-casing below,
which routes level 5 to an ending/finale branch instead of ever calling
`load_map` again. (The `(map-1)` clamp to `[0,4]` in `load_map` exists only
to keep the table index in bounds if `g_current_map_number` somehow
overshoots; it does not mean level 5 is a normal playable level reusing
level-4 assets.)

### The main loop and the map-advance trigger

**`main_loop_body` @ `$10a90`** (newly created, 204 bytes) is per-frame
game logic: a sequence of 8 `jsr` calls to still-unexplored subsystem
functions (`$16658`, `$18dac`, `$18782`, `$170b6`, `$177a8`, `$19216`,
`$191e6`, `$14362` — presumably input/physics/enemies/render/sound; not yet
characterized), followed immediately by the level-transition check:

```
$10acc  tst.w   g_submap_complete_flag   ; ($115e0)
$10ad2  beq.b   $10b2a                   ; flag==0 -> skip the whole block, continue next frame
```

**`g_submap_complete_flag` @ `$115e0`** is the best candidate for "last
submap of the current map has just been finished" — this is the flag the
user asked about, gating the entire map-transition block. Its own
setter(s) have not yet been traced back (would need the same
byte-pattern-scan technique applied to `000115e0` as an operand, then
following whichever of the unexplored subsystem functions above writes it
— left as an open follow-up, likely inside `$16658` or `$18782` given their
call order right before this check).

Once `g_submap_complete_flag` is non-zero, the branch logic is:

```
cmpi.w #4,g_current_map_number
  == 4:  cmpi.w #5,g_map4_end_state        ; ($17992)
           == 5: -> map_advance_instruction (normal advance)
         cmpi.w #1,g_map4_special_flag     ; ($17994)
           != 1: -> alternate handler (bsr $17bf4), jump elsewhere — NOT a normal advance
           == 1: force g_map4_end_state=5, -> map_advance_instruction anyway
  != 4:  cmpi.w #5,g_current_map_number
           == 5: cmpi.w #1,g_map4_special_flag -> special ending branch (beq.w $10bf2) or alternate handler
           != 5 (i.e. map is 1, 2, or 3): falls through unconditionally
                -> map_advance_instruction
```

**`map_advance_instruction` @ `$10b1a`**: `addi.w #1,g_current_map_number`
— the **only** instruction in the whole binary that increments the map
number (confirmed via the byte-pattern operand scan for `0001239c`; every
other reference is a plain read or a `cmpi.w #{1..5},...` comparison used
for per-level special-casing scattered across `$010ad8`-`$015646`).

**So, for maps 1-3** (which is what matters for the user's map-1 → map-2
question): the mechanism is exactly as hypothesized — once
`g_submap_complete_flag` (`$115e0`) goes non-zero, `main_loop_body`
unconditionally executes `addi.w #1,g_current_map_number` on that frame.
The very next frame, `load_map_if_changed` (`$12394`, called from
somewhere in the frame setup, not yet located) sees
`g_current_map_number != g_loaded_map_number`, falls into `load_map`
(`$123c4`), which indexes `g_level_descriptor_table` for the new map number
and loads its HNK pair. For map 1 → map 2 specifically, this loads
**RICK_03.HNK + RICK_04.HNK**, confirmed independently by dereferencing the
descriptor table above (not by observing it live).

Maps 4 and 5 are special-cased (map 4 has an extra `g_map4_end_state==5`
gate plus a `g_map4_special_flag` fork to an alternate handler at
`$17bf4`/`$10c00`; map 5 forks to what's likely the game-complete/ending
screen at `$10bf2` rather than ever calling `load_map` again) — consistent
with the real Rick Dangerous 2 having 4 real worlds and map 5 being an
ending pseudo-state, and consistent with the checksum-chain terminator trap
found in the descriptor table above.

### Ghidra annotations added this session (map-structure investigation)

In `/prg2-ram.bin.0`:
- Functions renamed: `FUN_00011e76` → `load_hnk_pair_by_seed`,
  `FUN_00011f86` → `resolve_hnk_id_by_checksum`, `FUN_00007000` →
  `load_and_depack_hnk_file`.
- Functions newly created: `load_map_if_changed` @ `$12394`, `load_map` @
  `$123c4`, `main_loop_body` @ `$10a90`.
- Labels created: `g_current_map_number` @ `$1239c`, `g_loaded_map_number`
  @ `$1239e`, `g_submap_complete_flag` @ `$115e0`,
  `g_level_descriptor_table` @ `$12dd4`, `g_hnk_checksum_chain_table` @
  `$11e4e`, `g_map4_end_state` @ `$17992`, `g_map4_special_flag` @
  `$17994`, `map_advance_instruction` @ `$10b1a`.

### Open follow-ups from this investigation

1. Trace what sets `g_submap_complete_flag` (`$115e0`) — the one remaining
   un-traced link ("what actually detects a submap is done"). Same
   byte-pattern-scan technique, targeting operand `000115e0`.
2. Characterize the 8 unexplored `jsr` targets called at the top of
   `main_loop_body` (`$16658`, `$18dac`, `$18782`, `$170b6`, `$177a8`,
   `$19216`, `$191e6`, `$14362`) to actually name the subsystems
   (input/physics/collision/render/sound/etc.) and find which one owns
   `g_submap_complete_flag`.
3. Find who calls `main_loop_body` (`$10a90`) itself and who calls
   `load_map_if_changed` (`$12394`) each frame — this is the true VBL-synced
   dispatcher / top of the main loop, not yet located.
4. Explore `$1795c` (`load_map`'s post-load step, `A0=$65300`,
   `A1=$53400`) — what happens to the two loaded HNK buffers afterward
   (likely a relocate/merge into the actual tile/sprite data the renderer
   uses).
5. Explore `$705e`/`$7136` (the two `bsr` targets called from inside
   `load_and_depack_hnk_file` before the depacker) — the actual raw
   sector-read implementation.
6. Confirm live (via a fresh Hatari trace) that finishing map 1 in-game
   really does trigger `load_and_depack_hnk_file` with digits `'3'`/`'4'` —
   this write-up predicts it from static data alone; an actual playthrough
   breakpoint trace would be the independent confirmation.

## Game engine architecture: main loop, input, player, entities (2026-09-11)

Follow-up to the map/submap investigation above, digging into
`main_loop_body` (`$10a90`)'s callees to answer: "what are the main
components of the game (input, loop, entities, data structures)?" Done via
static decompilation of `/prg2-ram.bin.0` (all these functions are code
that was never auto-analyzed by Ghidra's import, so each had to be
`create_function`'d by hand at the address before it would decompile —
same situation as the loader chain in the section above).

### The main loop, precisely

`main_loop_body` (`$10a90`) decompiles to a genuine `do { ... } while(true)`
wrapping a `do { ...16 subsystem calls... } while (sRam000115dc == 0)`.
Per iteration ("frame"):

1. **8 unconditional calls** (input/world housekeeping):
   `update_scroll_edge_trigger` (`$16658`), `animate_background_tiles`
   (`$18dac`), `advance_background_anim_counter` (`$18782`),
   `FUN_000170ce` (via thin wrapper `$170b6`, not yet explored),
   `update_hud_text_slots` (`$177a8`), `wait_for_vblank` (`$19216`),
   `FUN_000191e6` (pause/fire-button poll helper, not fully understood —
   Ghidra decompiles it as an unconditional infinite loop, which is
   probably a decompiler artifact around a self-modifying or
   interrupt-synchronized spin), `check_submap_exit_triggers` (`$14362`).
2. A big if/else on `g_submap_complete_flag` (`$115e0`): the "map just
   finished" branch (documented in the section above — increments
   `g_current_map_number`), or, on a normal frame, pause-key (`P`,
   scancode `0x19`) / sound-toggle (`S`, scancode `0x1f`) / quit (`Esc`,
   scancode `0x01`) handling, keyed off `kbd_last_scancode`, plus a
   "lives/game-over?" check (`sRam00012e2a`/`sRam00016960`) guarding calls
   to `$149c2`/`$142fc` (not yet explored).
3. **8 more unconditional calls** (the actual per-frame simulation):
   `update_countdown_timer_bcd`, `update_actor_slots`,
   `update_object_slots`, `scan_enemy_spawn_list`, `update_camera_scroll`,
   plus `update_player_rick` and `update_fall_state_slot` (exact call-site
   order captured in the decompile; see Ghidra if precise ordering
   matters).
4. `sRam000115dc` is reset to `0` right after step 2, then the inner loop
   repeats until something sets it non-zero — almost certainly
   `wait_for_vblank` (`$19216`, confirmed: busy-waits on the VBL counter
   `DAT_00019232` — the same global already identified in the "Live trace"
   section above — against a target `DAT_00018ed8`) is what ultimately
   paces this to 50Hz, though the exact write site of `sRam000115dc` itself
   hasn't been isolated yet (candidate: inside `$19234`, `wait_for_vblank`'s
   callee).

### Input handling

- **`custom_keyboard_isr`** (`$1a546`, confirmed via fresh disassembly)
  is installed on MFP vector `$118` and decodes the raw IKBD serial byte
  stream from the ACIA data register (`$fffc02`) directly — this is a
  from-scratch IKBD packet parser, not going through TOS/GEMDOS:
  - Byte `0xFE` → next byte is a **joystick port 0** state report, stored
    to `g_joystick0_state` (`$1a4fa`).
  - Byte `0xFF` → next byte is a **joystick port 1** state report, stored
    to `g_joystick1_state` (`$1a4fb`).
  - Any other byte → stored directly as a **keyboard scancode** to
    `kbd_last_scancode` (`$1a4fc`).
  - This matches real Atari ST IKBD auto-joystick-report packet format
    (header `0xFE`/`0xFF`, then a state byte with bit 7 = fire button,
    low nibble = up/down/left/right).
- `main_loop_body` checks `g_joystick1_state & 0x80` (fire button) in
  several places, and reads `kbd_last_scancode` directly for three
  hard-coded scancodes: `0x19` ('P', pause — spins calling `$191e6` until
  fire is pressed), `0x1f` ('S', toggles sound — calls `$1a5d0`, which
  writes the YM2149 PSG registers at `$ffff8800`/`$ffff8802`, and flips a
  "sound enabled" flag at `$1a5ce`), `0x01` (Esc — also mutes sound, then
  falls into the same reset path used for map transitions).
- **`attract_mode_handler`** (`$18400`, renamed from a guess at
  `input_and_player_action_handler` after decompiling it — it's *not* the
  general input reader) drives a 3-state (`DAT_00018180` = 0/1/2) sequence
  that also polls `g_joystick1_state`'s fire bit and animates a small
  table of position/velocity records at `$16d7c` (same 0x2c-word /
  88-byte stride as the main actor table, see below) — almost certainly
  the **title-screen attract-mode / demo playback** state machine, not
  in-game player input. Not yet confirmed by watching it run live.
- The actual translation of "joystick direction bits → Rick moves left/
  right/up/down" is read directly inside `update_player_rick` (`$13096`,
  see below) via `FUN_000141cc()` at its very top — that callee (not yet
  explored) is the real "read current input state" function and is the
  best next candidate to fully decode for reproduction purposes.

### The player entity — `update_player_rick` (`$13096`, 3.1KB, by far the
largest of the per-frame functions)

This is Rick's own physics/animation/collision state machine, running
once per frame regardless of map. Key globals (all newly labeled):

| Global | Address | Role |
|---|---|---|
| `g_player_x` | `$1695c` | Rick's world X position (fixed-point) |
| `g_player_y` | `$16960` | Rick's world Y position (fixed-point, 32-bit — high word likely sub-pixel) |
| `g_player_y_velocity` | `$16966` | Vertical velocity (gravity/jump), signed, accumulated into Y each frame, clamped to ±0x800 |
| `g_player_anim_frame` | `$16968` | Selected sprite/animation frame index for this frame |
| `g_player_run_cycle_counter` | `$1697c` | Run-cycle animation counter, indexes into per-direction frame tables at `$12e42`/`$12e4c`/`$12e56` |
| `g_player_facing_dir` | `$1697e` | **Correction (see "Correction: full decompile..." section below, 2026-09-14): not a boolean.** Holds a small signed step value (`0`, `±1`, `±2`) added into Rick's X position during stairs-transition code; also used to pick the ±8 horizontal-scroll step direction. Originally mis-described here as a simple 0/1 facing flag. |
| `g_player_dead_flag` | `$12e2a` | Non-zero disables normal update (checked by `update_player_rick` and `update_scroll_edge_trigger` alike) |
| `g_player_death_trigger` | `$12e2c` | Set to trigger the death sequence — plays a sound (`$1a6aa`), resets the actor table, re-seeds enemy slots from a template at `$15a2c` |

Behavior confirmed from the decompile:
- Movement/jump/crawl/climb are driven by a set of boolean sub-state flags
  at `$12e14`-`$12e28`. **Update (2026-09-14): all ten are now named** —
  see the "Stairs state machine decoded", "Effects-slot corrected, four
  player flags named", and "Last player stairs flags named" sections
  later in this document for the full naming work and evidence. Final
  names: `g_player_forced_push_flag` (`$12e14`), `g_player_ceiling_blocked_flag`
  (`$12e16`), *(crouch flag, `$12e18`, named in the actor-record section
  above as the gate for `check_box_vs_player`'s crouch-height branch)*,
  `g_player_wall_push_flag` (`$12e1a`), `g_player_airborne_flag` (`$12e1c`),
  `g_player_on_stairs_flag` (`$12e1e`), `g_player_stairs_variant_map4_flag`
  (`$12e20`), `g_player_stairs_variant_map2_flag` (`$12e22`),
  `g_player_wall_contact_flag` (`$12e24`), `g_player_scroll_pending_flag`
  (`$12e26`), `g_player_fallobj_trigger_flag` (`$12e28`). These do **not**
  all correspond one-to-one with distinct "poses" as originally guessed
  here — several are transition/edge-detection flags (wall-push vs.
  wall-contact, scroll-pending) rather than pose selectors; see the later
  sections for each flag's actual confirmed/plausible role and confidence
  level.
- Tile collision is queried via `FUN_00015fba`/`func_0x00015f1e`, writing
  a probe position into `DAT_00015f0e`/`DAT_00015f10` and reading back
  result flags in `DAT_00015f14` (bit meanings partially inferred: bit
  `0x20` = "died"/"trapdoor", bits `0x02`/`0x04` = blocked direction, bits
  `0x08`/`0x10` = ledge/step detection, bit `0x40` = "teleport to explicit
  position"). **SUPERSEDED 2026-09-22 — corrected in `kb2/xrick2-ref.md`,
  found by a documentation sweep**: the bits `0x08`/`0x10`/`0x40` guessed
  here are wrong, not just unconfirmed. Re-transcribed from the
  disassembly (`algo-player.md` §3, `algo-actors.md` §6) and live-
  validated (120 samples, `kb2/hatari_live_validate.py`): bit `0x08` =
  ladder tile present, bit `0x10` = ladder-top entry, bit `0x40` =
  standing on a platform actor. This function is the single most important remaining piece
  to fully decode for mechanical reproduction — it's effectively **the
  tile/level-collision query** the whole physics model is built on.
- **Per-map physics tuning is hard-coded by `g_current_map_number` value**
  (`==1`, `==2`, `==3`, `==4`, `==5` checked directly in multiple places)
  — e.g. different fall/bounce constants on map 3 and map 5, different
  run-cycle animation-frame counts on map 2 and map 4. This means the
  engine is not fully data-driven for physics; a faithful reproduction
  needs these per-map special cases carried over explicitly, not just
  derived from the level data files.
- Sound effects are triggered via `FUN_0001a6aa` (called with a value in
  `D0`/`D1` presumably selecting the effect — not yet decoded, but this is
  clearly **the general "play sound effect" entry point**, also called
  from `update_fall_state_slot`, `handle_screen_edge_and_respawn`, and the
  pause/sound-toggle key handling).
- On death (`g_player_dead_flag`/`g_player_death_trigger` path,
  `LAB_00013a62`), it: plays a sound, resets scroll velocity, resets the
  6-entry actor table (see below) back to a neutral template, and jumps
  back into the normal per-frame flow — i.e. death is handled entirely
  inside this one function; no separate "you died" screen function was
  found (that may be handled elsewhere, e.g. via the lives/game-over check
  gated in `main_loop_body` step 2 above).

### The actor/entity table

**`g_actor_table`** (`$16b6a`) is an array of fixed-size records, **0x58
(88) bytes per record**, iterated with a stride of `0x2c` *16-bit words*
(`0x2c * 2 = 0x58` bytes) by `update_actor_slots` (`$14d48`, 6 records) and
by `handle_screen_edge_and_respawn`/`update_player_rick` internals (5
records). The same 0x58-byte stride also appears at `$16d7c` (used by
`attract_mode_handler`) — strong evidence this is *the* general entity
struct size used throughout the engine, not something specific to enemies.

- `update_actor_slots` (`$14d48`) is a thin per-slot dispatcher: for each
  of 6 slots, if the first field is non-zero, call `FUN_00014d70` (the
  actual generic per-enemy update/AI/animation routine — not yet
  explored, next priority for understanding enemy behavior).
- `scan_enemy_spawn_list` (`$14594`) reads a **level-specific spawn table**
  via `g_enemy_spawn_table_ptr` (`$144c8` — **SUPERSEDED, see line ~3083: the
  real, disassembly-confirmed storage cell is `$144c4`** (`PTR_DAT_000144c4`);
  `$144c8` here was an early unconfirmed guess never corrected in place until
  now, a pointer — set per level/room,
  part of the loaded HNK data) — 4-byte records: byte0 = type/flags
  (bit `0x80` = a variant), byte1 = horizontal spawn position (×8, compared
  against the current scroll window `DAT_00016462` to decide when the
  entity scrolls into view), byte2 = more flags, byte3 low 2 bits = a
  skip-count for variable-length records. On a match it calls
  `FUN_00014a3c`/`FUN_00014636` (spawn variants — presumably "spawn enemy"
  vs. "spawn scenery/pickup" — not yet distinguished). **This table is the
  per-room enemy/object placement data** — the single most valuable
  structure to fully decode for level reproduction, since it's what
  actually defines where things appear.
- `update_object_slots` (`$150a2`) iterates a *separate*, smaller table at
  `$167a2` (`0x16`-word / 44-byte stride, only 4 records) calling
  `FUN_000150c0` per active slot — likely a lighter-weight table for
  projectiles or pickups, distinct from the main actor table.
- `update_fall_state_slot` (`$13e98`) manages a single extra "falling
  object" tracked via `g_fallobj_state`/`g_fallobj_x`/`g_fallobj_y`
  (`$16b12`/`$16b14`/`$16b18` — note these sit exactly 0x58 bytes before
  `g_actor_table`, i.e. **this is almost certainly actor-table slot -1, or
  equivalently Rick treated as "slot 0" of the same array**, with the
  6-entry loop in `update_actor_slots` covering slots 1-6). This function
  runs a tiny 3-state machine (`g_fallobj_state` 0/1/2) with its own tile-
  collision probe and its own map-specific physics constants (map 3/5
  again) — looks like it's specifically the trapdoor-fall / pit-fall
  physics for whichever entity (player or otherwise) has just triggered a
  fall, separate from normal walking/jumping in `update_player_rick`.

### Submap-exit triggers (the `$115e0` setter — resolved)

Follow-up from the previous section's open question: **found**.
`check_submap_exit_triggers` (`$14362`) is one of the 8 unconditional
per-frame calls. It scans a **level-specific trigger table** via
`g_submap_trigger_table_ptr` (`$1435c`, pointer — also set per level, like
the enemy spawn table) — 4-byte records: byte0 low 2 bits = a submap-index
tag (compared against `g_current_submap_index`, `$14360`), byte1 =
horizontal scroll-position threshold (×8, compared against
`sRam00016960 + (DAT_00016462 & 0xfff8)`, i.e. Rick's own scroll-relative
X position). When the current submap's trigger fires:
- If flag bits `0x90` (or, in the "else" arm, `0x80`) are set on the
  record → **`g_submap_complete_flag` (`$115e0`) is set to `0xffff`** —
  this is the actual "last submap of this map finished" detection the
  original map-switch investigation was missing.
- Otherwise → calls `FUN_00014434` with a direction flag (`uRam00012e14`)
  — likely a normal **submap-to-submap scroll transition within the same
  map** (i.e. "you've walked from submap 2 into submap 3, same map, no
  HNK reload needed"), as opposed to the map-ending exit.

This confirms the user's original mental model precisely: a **map** is
subdivided into **submaps** (rooms/screens), tracked by
`g_current_submap_index`; walking to specific scroll positions within a
submap triggers either an ordinary submap-to-submap transition (handled
by `FUN_00014434`, not yet explored) or — on the *last* submap of the
current map — sets `g_submap_complete_flag`, which `main_loop_body`
detects next frame and increments `g_current_map_number`, triggering the
next map's HNK pair to load (per the previous section's fully-verified
table).

### Ghidra annotations added this session (engine architecture)

In `/prg2-ram.bin.0`, functions renamed/created:
`update_player_rick` (`$13096`), `update_fall_state_slot` (`$13e98`),
`handle_screen_edge_and_respawn` (`$15bc0`), `scan_enemy_spawn_list`
(`$14594`), `update_actor_slots` (`$14d48`), `update_object_slots`
(`$150a2`), `update_countdown_timer_bcd` (`$15826`),
`update_camera_scroll` (`$13e14`), `check_submap_exit_triggers` (`$14362`),
`update_scroll_edge_trigger` (`$16658`), `animate_background_tiles`
(`$18dac`), `advance_background_anim_counter` (`$18782`),
`update_hud_text_slots` (`$177a8`), `wait_for_vblank` (`$19216`),
`attract_mode_handler` (`$18400`). Labels created: `g_player_x`
(`$1695c`), `g_player_y` (`$16960`), `g_player_anim_frame` (`$16968`),
`g_player_y_velocity` (`$16966`), `g_player_run_cycle_counter` (`$1697c`),
`g_player_facing_dir` (`$1697e`), `g_player_dead_flag` (`$12e2a`),
`g_player_death_trigger` (`$12e2c`), `g_fallobj_state`/`_x`/`_y`
(`$16b12`/`14`/`18`), `g_enemy_spawn_table_ptr` (`$144c8` — **SUPERSEDED, see
line ~3083: real address is `$144c4`**),
`g_submap_trigger_table_ptr` (`$1435c`), `g_current_submap_index`
(`$14360`), `g_actor_table` (`$16b6a`), `g_joystick0_state`/
`g_joystick1_state` (`$1a4fa`/`$1a4fb`).

### Open follow-ups (engine architecture)

1. **`FUN_000141cc`** (called at the very top of `update_player_rick`) —
   almost certainly "read current input direction/buttons into a bitmask"
   — decoding this fully gives the exact input→movement mapping needed
   for reproduction.
2. **`FUN_00015fba`/`func_0x00015f1e`** — the tile/level collision query
   used by both `update_player_rick` and `update_fall_state_slot`; decode
   the `DAT_00015f14` result-flag bit meanings precisely.
3. **`FUN_00014d70`** — the generic per-actor-slot update (enemy AI +
   animation); this is the key to documenting enemy behavior.
4. **`FUN_00014a3c`/`FUN_00014636`** — the two "spawn" variants called
   from `scan_enemy_spawn_list`; likely "spawn enemy" vs. "spawn
   scenery/pickup".
5. Fully decode the 4-byte record layout of `g_enemy_spawn_table_ptr` and
   `g_submap_trigger_table_ptr` tables by reading a live level's actual
   data (both are level-specific, loaded as part of the HNK pair) — this
   session only reverse-engineered the *code* that reads them, not a
   concrete data sample.
6. **`FUN_0001a6aa`** — general sound-effect trigger; decode the effect-ID
   parameter to build a full sound effects list.
7. Individually name the ten player sub-state flags at `$12e14`-`$12e28`
   (running/jumping/crouching/climbing/hanging/shooting/etc.) by observing
   which ones are set together during specific on-screen actions (best
   done with a live Hatari trace, watching these bytes while performing
   each action manually).
8. Confirm `attract_mode_handler` (`$18400`) really is the title-screen
   demo, not something else, by tracing when it's called (what calls it,
   and whether that caller is only reached from the title-screen code
   path).
9. Find the render/blit routines (not yet located among the traced
   per-frame calls — possibly inside one of the not-yet-explored
   `$149c2`/`$142fc`/`$170ce` functions, or elsewhere entirely) — needed
   to document how tile/sprite data becomes screen pixels.

## Input abstraction and tile/actor collision, decoded (2026-09-11)

Direct follow-up resolving open items 1 and 2 from the previous section.

### `read_player_input` (`$141cc`) — input is really a demo-playback abstraction

This is the function called at the very top of `update_player_rick`, and
it is **not** a simple "read the joystick" call — it's the single
input-abstraction point the whole game is built on, and it doubles as the
attract-mode demo player:

```c
undefined1 read_player_input(void) {
  if (g_demo_mode_active == 0)
      return g_joystick1_state;          // live play: raw joystick byte

  // demo playback: pull the next value out of an RLE-encoded byte stream
  if (g_demo_run_length_counter == 0) {
      run_len = *g_demo_input_stream_ptr;
      if (run_len == 0) { g_demo_stream_end_flag = 0xffff; return 0; }
      value = g_demo_input_stream_ptr[1];
      g_demo_input_stream_ptr += 2;
      g_demo_run_length_counter = run_len;
      g_demo_run_length_value  = value;
  }
  g_demo_run_length_counter--;
  return g_demo_run_length_value;
}
```

So the exact same byte format (`g_joystick1_state`: bit 7 = fire, low
nibble = direction — the real IKBD auto-report state byte) is used both
for live joystick input **and** for pre-recorded attract-mode demo input,
with the demo simply being an RLE stream of `(run_length, joystick_byte)`
pairs consumed one tick at a time. `g_demo_mode_active` (`$3efb6`) is the
same flag `main_loop_body` checks in several places (sound-toggle key is
disabled during a demo; map-advance-on-submap-complete takes a different,
demo-specific branch that resets `g_demo_mode_active` and jumps into the
title-screen-return code instead of the normal per-map reset). This means
**`attract_mode_handler` (`$18400`) is confirmed to be exactly what it was
guessed to be** (open item 8, previous section, now closed): the
title-screen demo driver, distinguished from real gameplay purely by
whether `read_player_input` is sourcing from `g_joystick1_state` or from
the recorded stream — `update_player_rick` itself doesn't know or care
which.

For reproduction purposes this means: model input as a single
"current-input-byte" abstraction (fire bit + 4 direction bits, IKBD
format) read once per frame, and treat "demo mode" as nothing more than
swapping the source of that byte for a scripted RLE stream — no separate
demo-specific player logic exists.

### `query_tile_and_actor_collision` (`$15fba`, renamed from
`FUN_00015fba`/`func_0x00015f1e`) — tile probing AND nearby-actor overlap
in one call

This resolves open item 2 precisely. The function is not purely a tile
query — it's a **combined terrain + actor collision probe**, called with
a world position pre-loaded into `g_collision_probe_x`/`g_collision_probe_y`
(`$15f0e`/`$15f10`):

1. **Tile probing** (via new helper `compute_tile_map_ptr`, `$1643e`):
   computes a pointer into `g_tile_attribute_map` (`$65300` — this is the
   buffer address flagged as unexplored in open item 4 of the map-switch
   section; it's now confirmed to be **the live tile-attribute grid the
   collision system reads**, addressed as
   `base + ((probe_y & ~7) * 4) + ((probe_x_offset) >> 3)`, i.e. one byte
   per 8×8 tile, row-major). It samples 2 or 3 tile-grid points (a
   1-tap or 2-tap probe depending on `g_collision_probe_y & 7 < 4`,
   presumably a "which half of the tile am I in" sub-check relevant to
   ledges) at three x-offsets each (`pbVar5[0]`, `[1]`, `[2]`, stepping
   `0x20` bytes/iteration through a small per-probe-direction offset
   table), OR-ing/masking the sampled tile-attribute bytes together with
   masks `0x7f`/`0x27`/`0x2a`/`0x22` into `g_collision_result_flags`
   (`$15f14`). If a secondary sign flag (`$15f12`) is negative, bit
   `0x04` is cleared from the result — consistent with "some flags only
   apply when probing to the right", i.e. per-direction bit suppression
   for a symmetric probe used for both left- and right-facing checks.
2. **Actor overlap** (only if `$15f16` is non-zero, i.e. this call site
   opted in to actor checking — `update_player_rick` does,
   `update_fall_state_slot` presumably doesn't need to): walks
   `g_actor_table` (terminated by a negative first field) and, for each
   *active* slot with flag bit `0x80` set, runs `aabb_overlap_test`
   (`$161ce`, renamed from `FUN_000161ce` — a textbook AABB rectangle-
   intersection test done entirely in registers D0-D7, returning its
   boolean via a condition-code trick rather than a real return value)
   between the probe and that actor's bounding box. Actor flag bit `0x40`
   distinguishes two behaviors: bit set → an unconditional/"hazard-style"
   overlap that also requires being within scroll range, sets result bits
   `0x42`, and zeroes some per-hit fields; bit clear → a "closest match"
   search that keeps the nearest qualifying actor (tracked via
   `$15f18`/`$15f1a`/`$15f1c`, an insertion-sort-by-distance style
   accumulator initialized to `0x7fff`) and sets bit `0x40` only for the
   overall winner.

**Practical takeaway for reproduction**: there is exactly one collision
primitive in the engine (`query_tile_and_actor_collision`), and it is
used identically by the player and by other systems — terrain collision
and actor-vs-actor collision are not separate subsystems, they're two
phases of the same probe call, driven by a shared position register pair
and a small set of per-call-site flags (`$15f12`, `$15f16`) that toggle
which phases run. A faithful reproduction should implement the game's
physics/hit-detection the same way: one "probe(x, y, flags) -> result
bits + nearest-actor info" function, not separate tile and entity
collision code paths.

### Ghidra annotations added this pass

Functions renamed: `read_player_input` (`$141cc`, from `FUN_000141cc`),
`compute_tile_map_ptr` (`$1643e`), `aabb_overlap_test` (`$161ce`),
`query_tile_and_actor_collision` (`$15fba`). Labels created:
`g_demo_mode_active` (`$3efb6`), `g_demo_stream_end_flag` (`$3efb8`),
`g_demo_input_stream_ptr` (`$3efba`), `g_demo_run_length_counter`
(`$3efbe`), `g_demo_run_length_value` (`$3efbf`), `g_tile_attribute_map`
(`$65300`), `g_collision_probe_x` (`$15f0e`), `g_collision_probe_y`
(`$15f10`), `g_collision_result_flags` (`$15f14`).

### Remaining open follow-ups (superseding items 1, 2, and 8 above, which are now resolved)

1. **`FUN_000161fe`** (a related function right after `aabb_overlap_test`,
   iterating a table at `$65200` — a second fixed base address close to
   `g_tile_attribute_map`'s `$65300`; possibly a sprite/object-placement
   table for the same tile grid) — not yet explored.
2. Decode the per-probe-direction offset table walked by
   `query_tile_and_actor_collision`'s `pbVar5` (stride `0x20`) to get the
   exact tap positions (currently only inferred as "3 x-offsets, 2 or 3
   y-taps").
3. Precisely map out the `g_collision_result_flags` bit meanings by
   correlating with in-game behavior (best done live: set a Hatari
   watchpoint on `$15f14` and observe values while manually walking off
   ledges, hitting hazards, and touching enemies).
4. `FUN_00014d70` — the generic per-actor-slot update (enemy AI +
   animation) — still unexplored; now that `query_tile_and_actor_collision`
   and `aabb_overlap_test` are understood, this is the natural next target
   since enemy AI almost certainly calls the same collision primitive.
5. `FUN_00014a3c`/`FUN_00014636` — the two "spawn" variants from
   `scan_enemy_spawn_list` — still unexplored.
6. Fully decode a concrete data sample of `g_enemy_spawn_table_ptr` and
   `g_submap_trigger_table_ptr` from live level data — still unexplored.
7. `FUN_0001a6aa` — general sound-effect trigger — still unexplored.
8. Individually name the ten player sub-state flags at `$12e14`-`$12e28`
   — still unexplored (best done live).
9. Find the render/blit routines — still unexplored.

## Enemy AI: a byte-code scripting VM per actor (2026-09-11)

Direct follow-up resolving open item 4 above (`FUN_00014d70`, called from
`update_actor_slots` for every active `g_actor_table` slot). Renamed to
`update_actor_ai` (`$14d70`). This turned out to be far more interesting
than a hand-written per-enemy-type behavior function — **each actor is
driven by two independent, data-driven byte-code scripts**, interpreted
generically by shared helper functions. This is the single biggest
structural finding yet for reproduction, since it means enemy *behavior*
is level/actor data, not code, much like the tile/spawn/trigger tables
already documented.

### The two scripts, and their interpreters

- **Movement script** — pointer at actor-record offset `0x16`, read by
  `advance_actor_move_script` (`$172fa`, renamed from `FUN_000172fa`).
  Each entry is a signed-byte `(dx, dy)` pair, applied once per call as a
  position delta. Two sentinel op-values in the low byte:
  - `0` → end-of-script: the pointer field is rewritten using a relative
    offset stored in the next word (`psVar4[1]`), i.e. **loop back to an
    earlier point in the script** — this is how a patrol/pace-back-and-
    forth movement cycles forever.
  - `-1` → **embedded sound-effect trigger**: if the actor's Y position
    (offset `0x6`) falls within the visible screen band (`0x23..0x148`),
    call the general sound entry point `FUN_0001a6aa` with no explicit
    id argument (worth revisiting once that function's parameter is
    decoded) — i.e. movement scripts can fire sound cues (footstep/flap/
    etc.) at specific points in the cycle, gated on visibility so
    offscreen actors stay silent.
  - Anything else → a literal `(dx, dy)` delta returned to the caller.
- **Animation/frame script** — pointer at offset `0x1e`, read by
  `advance_actor_anim_script` (`$171bc`, renamed from `FUN_000171bc`).
  Each entry is a signed 16-bit op-value followed by data:
  - `>= 0` → a literal animation-frame index, written to offset `0xe`
    (the actor's current sprite frame), and the script pointer advances
    by one word.
  - `-1` → loop: same relative-jump-via-next-word pattern as the movement
    script.
  - `-3` → embedded sound trigger (identical onscreen-band check as
    above, this time calling `FUN_0001a6aa(0xfffd)` — a specific,
    concrete sound-effect ID, unlike the movement-script trigger).
  - Any other negative value (specifically not `-1`/`-3`) → a
    **duration-frame pair**: next word = repeat/duration counter (stored
    at offset `0x22`, decremented once per subsequent call so the same
    frame holds for N frames), word after that = the frame index (offset
    `0xe`).
  - There's also a decrement-only fast path: if offset `0x22`
    (the duration counter) is already non-zero, the whole function just
    decrements it and returns immediately without touching the script
    pointer — the "hold this frame" mechanism.
- **`is_actor_onscreen`** (`$14998`, renamed from `FUN_00014998`) — a
  small guard used throughout `update_actor_ai`: checks the actor's Y
  (offset `0x6`, range `[0, 0x128)`) and X (offset `0x2`, range
  `[0, 0xe9)`) against the visible screen dimensions (`0xe9`×`0x128` =
  233×296 — plausibly the playfield's pixel size, close to but not
  exactly the ST's 320×200 mode, so likely a scroll-relative or
  tile-scaled coordinate space rather than raw screen pixels — worth
  reconciling against the camera-scroll globals from the earlier
  section). Its result is passed via the same "boolean through condition
  codes" idiom seen in `aabb_overlap_test`, which the decompiler can't
  show directly — confirmed logically from how call sites branch
  immediately afterward.

### `update_actor_ai`'s overall shape

Keyed off a per-actor **state byte** (bits `0x3c` of a flags word at
offset `0x0`/`0x1`), the function branches into two broad regimes:

1. **State values `0x20`, `0x28`, `0x2c`** — a **death/explosion
   sequence**: three sequential explosion-animation states. Each swaps in
   a fixed system explosion animation table pointer (`&DAT_00014696` for
   state `0x20`, `&DAT_00012ed6` for a related state) into the actor's
   own frame-script pointer field, plays specific sound effects (some via
   explicit ids like `6`, others by ID `0xfffd` again), and finally lets
   the shared `is_actor_onscreen`/collision helpers run the explosion
   animation to completion before presumably deactivating the slot.
   Reaching this state appears to always follow being killed, i.e. **this
   is the enemy-death effect**, reusing the exact same scripted-animation
   interpreter as normal behavior — dying enemies are literally "given a
   different animation script to play."
2. **All other state values** — **normal patrol/attack behavior**: pull
   the next movement delta from `advance_actor_move_script`, apply it to
   position (offsets `0x2`/`0x6`, matching the same x/y layout used
   elsewhere in the 0x58-byte struct), run the shared collision check
   (`is_actor_onscreen` + a wrapper the decompile calls via
   `FUN_000171bc`'s sibling, which itself reads the frame script), and —
   depending on flag bits at offset `0x1` (`0x40`, `0x80`, `0x20`,
   `0x10`, `0x1c` mask with several distinct values `0x0`/`0xc`/`0x14`/
   `0x1c`) — either continue normally, **swap a whole block of fields
   with a second copy living higher in the same record** (offsets
   `0x18`/`0x19-0x1a`/`0x1b-0x1c` swapped with `0x1`/`0xb-0xc`/`0xf-0x10`),
   or trigger `g_player_death_trigger` (`$12e2c`) directly — i.e. **this
   is the code path where an enemy actually kills Rick on contact**,
   confirming enemy-vs-player collision is resolved right here in the
   per-enemy update, not in `update_player_rick`.
   - The "swap a block of fields with a second copy" behavior (jump
     target `LAB_00014ed4` in the decompile) is very likely how an actor
     **flips between two complete behavior profiles** stored in the same
     record — e.g. a two-phase enemy (idle vs. chasing, or patrol vs.
     retaliate) that keeps both profiles' movement-script pointer,
     frame-script pointer, and flags pre-loaded and just swaps which
     "half" is active, rather than re-deriving state each transition.
     This needs a live trace to confirm which enemy types actually use
     it.

### Actor-record field map so far (word offsets from `g_actor_table` slot base, corroborated across this and the previous section)

| Offset | Field | Notes |
|---|---|---|
| `0x0`/`+1` | type/flags word | high-nibble-ish bits `0x3c` = death/explosion state; other bits (`0x40`,`0x80`,`0x20`,`0x10`,`0x08`,`0x1c`,`0x02`) = assorted per-type behavior flags, only partly decoded |
| `0x2` | X position | checked by `is_actor_onscreen` against `[0, 0xe9)` |
| `0x6` | Y position | checked by `is_actor_onscreen` against `[0, 0x128)`; also the "is visible" gate for movement/anim-script sound triggers |
| `0xe` | current animation/sprite frame index | written by `advance_actor_anim_script` |
| `0x16` | movement-script pointer | read/advanced by `advance_actor_move_script` |
| `0x1a` | movement-script repeat counter | (inferred from `advance_actor_move_script`'s structure, analogous to `0x22` below) |
| `0x1e` | animation/frame-script pointer | read/advanced by `advance_actor_anim_script` |
| `0x1d`/`0x1e` (as seen from `query_tile_and_actor_collision`'s caller-side view) | nearest-hit actor's recorded position fields | consistent with the same struct, different section of the earlier collision write-up — needs reconciling: this looks like the same word range interpreted two ways depending on caller, worth a follow-up |
| `0x22` | animation frame-hold/duration counter | decremented by `advance_actor_anim_script` |
| `0x27` | "explosion/death sequence active" flag | gates entry into the death-state branch of `update_actor_ai` |

(Note: the `0x1d/0x1e` row flags a real inconsistency between this
section's byte-offset reading of the struct and the earlier section's
word-offset reading from `query_tile_and_actor_collision` — the two were
decoded from different call sites/decompiles and haven't yet been
reconciled into one authoritative struct layout. Building an actual
Ghidra `struct` definition for the 0x58-byte actor record — rather than
tracking offsets in prose — is now clearly worthwhile and should be the
first step of any follow-up session touching actors.)

**SUPERSEDED — see line ~1379 ("Actor record struct, verified by
disassembly", 2026-09-11 later section).** The word-offset reading in
this row is superseded by that section's byte-accurate disassembly-based
struct: the field this row calls `0x1d/0x1e` is confirmed to actually be
byte offset `0x3a` (`move_delta_x`, later renamed from `prev_x`), reached
via `move.w (0x3a,A0),(0x15f1a).l`. The apparent "same word range
interpreted two ways" was a decompiler pointer-width artifact (treating
the base pointer as a `short*` in one decompile and a byte-addressed
pointer in another), not a real dual-purpose field. Every later section
in this document uses byte offsets exclusively and is consistent with
the `0x3a` reading — this row and its prose note are the only place the
older, superseded word-offset reading survives.

### Ghidra annotations added this pass

Functions renamed: `is_actor_onscreen` (`$14998`),
`advance_actor_anim_script` (`$171bc`), `advance_actor_move_script`
(`$172fa`), `update_actor_ai` (`$14d70`, from the placeholder
`FUN_00014d70`).

### Updated open follow-ups

1. **Define a real Ghidra `struct` for the 0x58-byte actor record**
   (see the reconciliation note above) — turn the prose field map into an
   authoritative structure definition, then re-decompile
   `update_actor_ai`/`update_actor_slots`/`query_tile_and_actor_collision`
   against it for much cleaner output.
2. Decode the exact flag-bit meanings at actor offset `0x1`/`+1` (the
   `0x02`/`0x08`/`0x10`/`0x1c`/`0x20`/`0x40`/`0x80` bits) — best done by
   dumping a live level's actual `g_actor_table` contents for several
   enemy types and correlating bit patterns with observed behavior.
3. `FUN_00014a3c`/`FUN_00014636` (spawn variants) and `FUN_00014a12`
   (the common tail-call every `update_actor_ai` path eventually reaches)
   — still unexplored.
4. Decode `FUN_0001a6aa`'s effect-ID parameter now that concrete call
   sites are known (`6`, `0xfffd`, and the movement-script's argument-less
   call) — should be tractable by reading the function itself directly.
5. Fully decode a concrete data sample of `g_enemy_spawn_table_ptr` and
   `g_submap_trigger_table_ptr`, and now also a concrete movement-script
   and frame-script byte stream for at least one real enemy — still
   unexplored, requires reading level HNK data or a live dump.
6. Individually name the ten player sub-state flags at `$12e14`-`$12e28`
   — still unexplored (best done live).
7. Find the render/blit routines — still unexplored.

## Actor record struct, verified by disassembly (2026-09-11)

The previous section flagged a real inconsistency between two different
decompiles' byte-offset readings of the 0x58-byte actor record (the
decompiler silently treats the same base pointer as a `short*` in some
functions and an `int`/byte-address in others, scaling offsets
differently each time). Resolved by reading the **raw 68000 disassembly**
directly (`(0xNN,A0)`/`(0xNN,A6)` addressing modes give unambiguous byte
displacements) for both `query_tile_and_actor_collision` (`$15fba`-
`$161c9`, the per-actor loop around `$160c0`-`$161bc`) and `update_actor_ai`
(`$14d70`-`$150a1`, disassembled in full from `$14d70` to `$14fc0`). Every
offset below is confirmed straight from opcode operands, not inferred
from decompiler output.

A Ghidra structure **`ActorRecord`** (88 = `0x58` bytes) has been created
and applied to `g_actor_table` as `ActorRecord[6]`:

| Offset | Field | Evidence |
|---|---|---|
| `0x00` | `state_flags` (byte) | `andi.b #0x3c,D7b` then compared to `0x20`/`0x28`/`0x2c` — selects the 3-stage death/explosion sequence; any other value is normal behavior |
| `0x01` | `behavior_flags` (byte) | bit `0x02` = "frozen" (skip movement script, reuse current x/y); bits `0x1c` = a 3-way sub-type switch (`0x00`/`0x0c`/`0x14`/`0x1c`, only `0x1c` and `0x0c` produce distinct branches, `0x14` triggers the profile swap); bit `0x40` = "can kill Rick on contact" gate; bit `0x80` = "play a sound before acting" gate; bit `0x20` set by the profile-swap logic itself (see below) |
| `0x02` | `x` (word) | world X position; read directly by `is_actor_onscreen`, `query_tile_and_actor_collision`, `check_box_vs_player` call sites |
| `0x04` | *(unknown, word)* | never referenced in either disassembled function — reserved/unused or sub-pixel X |
| `0x06` | `y` (word) | world Y position, same evidence pattern as `x` |
| `0x08`-`0x0d` | *(unknown, 6 bytes)* | not referenced in either function |
| `0x0e` | `anim_frame` (word) | current sprite/animation frame index; written by `advance_actor_anim_script`; compared against sentinel `0xfe` in the death-sequence tail (`$14e24`) to detect "explosion animation already finished" |
| `0x10`-`0x15` | *(unknown, 6 bytes)* | not referenced |
| `0x16` | `move_script_ptr` (4-byte pointer) | read/advanced by `advance_actor_move_script`; **swapped** with `move_script_ptr_alt` (`0x32`) during a profile flip |
| `0x1a` | `move_script_counter` (word) | run-length/repeat counter for the current movement-script entry; reset to 0 by the profile swap |
| `0x1c`-`0x1d` | *(unknown, 2 bytes)* | not referenced |
| `0x1e` | `anim_script_ptr` (4-byte pointer) | read/advanced by `advance_actor_anim_script`; **swapped** with `anim_script_ptr_alt` (`0x36`) |
| `0x22` | `anim_hold_counter` (word) | frame-hold/duration counter for `advance_actor_anim_script`; reset to 0 by the profile swap |
| `0x24`-`0x25` | *(unknown, 2 bytes)* | not referenced |
| `0x26` | `width` (word) | this actor's own AABB width — confirmed as `0x26,A0`/`0x26,A6` feeding both `aabb_overlap_test` (from `query_tile_and_actor_collision`) and `update_actor_ai`'s player-contact check |
| `0x28` | `height` (word) | AABB height, same evidence pattern |
| `0x2a` | `secondary_data_ptr` (4-byte pointer) | loaded into `A0` at `$14e72` right before calling `dispatch_spawn_record` (`$14a3c`, renamed from `FUN_00014a3c`) — this actor's own pointer *into* a spawn-style record table, i.e. an active enemy can itself own a nested spawn/drop table (see below) |
| `0x2c`-`0x2d` | *(unknown, 2 bytes)* | not referenced |
| `0x2e` | `substate_flags` (byte) | bits `0x08`/`0x10`/`0x20` set by the movement-script-retry loop (tracks "script exhausted, waiting to advance" sub-states); bits `0x03`/`0x04`/`0x05`/`0x06` set/tested around the profile-swap and death-sequence-entry logic |
| `0x2f` | *(unknown, byte)* | not referenced |
| `0x30` | `behavior_flags_alt` (byte) | the profile-swap partner of `0x01` — this actor carries **two complete behavior flag sets** |
| `0x31` | *(unknown, byte)* | not referenced (alignment padding before the pointer pair below) |
| `0x32` | `move_script_ptr_alt` (4-byte pointer) | swap partner of `0x16` |
| `0x36` | `anim_script_ptr_alt` (4-byte pointer) | swap partner of `0x1e` |
| `0x3a` | `prev_x` (word) | the actor's X position **immediately before** this frame's movement delta is applied — written every frame just before `x` is updated (`$14dec`); this is what `query_tile_and_actor_collision` reports back as the "nearest hit actor" position fields (previously mis-read as word-offset `0x1d` due to a decompiler pointer-width artifact — now confirmed byte-accurate via `move.w (0x3a,A0),(0x15f1a).l` in the raw disassembly) |
| `0x3c` | `prev_y` (word) | same pattern as `prev_x` |
| `0x3e`-`0x4d` | *(unknown, 16 bytes)* | not referenced in the disassembled ranges — candidate territory for the still-unnamed per-actor sound/VFX-trigger fields seen used elsewhere |
| `0x4e` | `explosion_done_flag` (word) | gates the death sequence: `tst.w (0x4e,A6)` at `$14f24` — if non-zero, skip straight to the sequence's tail state instead of re-running the first explosion-animation stage |
| `0x50`-`0x57` | *(unknown, 8 bytes)* | not referenced |

### The behavior-profile swap, fully resolved

The `LAB_00014ed4` swap block (open item from the previous section) is
now completely explained: when an actor's `behavior_flags & 0x1c == 0x14`
(and a couple of other gating conditions on `substate_flags`), the engine
performs a straight 3-field swap:

```
swap(behavior_flags,   behavior_flags_alt)    // 0x01 <-> 0x30
swap(move_script_ptr,  move_script_ptr_alt)   // 0x16 <-> 0x32
swap(anim_script_ptr,  anim_script_ptr_alt)   // 0x1e <-> 0x36
move_script_counter = 0                        // 0x1a
anim_hold_counter   = 0                        // 0x22
```

So **every actor slot can carry two complete, independent behavior
programs** (flags + movement script + animation script) simultaneously,
and this is a single atomic "flip to the other program" operation. This
is exactly the mechanism for two-phase enemies (e.g. idle-patrol vs.
alerted/chasing, or a left-moving vs. right-moving cycle for something
that reverses at a wall) — the game doesn't re-derive or recompute a new
script on the transition, it just has both baked in from spawn time and
swaps a pointer pair.

### Player hitbox size, confirmed with concrete numbers

`check_box_vs_player` (`$14b7a`, renamed from `FUN_00014b7a`) is a
dedicated "does this box overlap Rick" test (distinct from the generic
`aabb_overlap_test`, hardcoded against `g_player_x`/`g_player_y` rather
than taking a second box as parameters) — called from both
`dispatch_spawn_record` and (indirectly) the enemy-death "find a place to
drop an item" search. It reveals **Rick's actual hitbox dimensions**:

- Horizontal: probe box overlaps Rick's box if `probe.x < g_player_x + 0x14` **and** `g_player_x + 4 < probe.x + probe.width` — i.e. Rick's hittable X-span is `[g_player_x + 4, g_player_x + 0x14)`, a **16-pixel-wide** box inset 4 pixels from his drawn origin.
- Vertical (standing): `probe.y < g_player_y + 0x15` and `g_player_y < probe.y + probe.height` — a full **21-pixel-tall** box.
- Vertical (crouching, gated by `_DAT_00012e18` — one of the ten still-unnamed player sub-state flags from the earlier section, now identifiable as **the crouch/duck flag**): the same test but with the far edge check tightened to `g_player_y + 5 <= probe.y + probe.height`, i.e. Rick's **hittable height shrinks to about 5 pixels** while crouching — a big, concrete, exact number for reproducing his duck hitbox.
- Also returns "no hit" unconditionally while `g_player_dead_flag` is set — dead Rick can't be hit again.

### `dispatch_spawn_record` (`$14a3c`, renamed from `FUN_00014a3c`) — richer than previously described

Re-examined with full disassembly-informed context; this refines (not
replaces) the earlier "two spawn variants" description from the enemy-AI
section. It's actually a **single dispatcher over up to 6 independent
condition/action bits**, read from a control byte at the *next* table
record's offset (record stride is confirmed as 4 bytes, and the control
byte for record N is read as record-N-plus-one's leading byte — i.e. the
table is a tightly packed byte stream, not an array of self-contained
4-byte structs with a leading tag each):

- An X-visibility precheck (spawn X in tile units ×8, minus current
  scroll `DAT_00016462 & 0xfff8`; combined with a width-in-tiles nibble)
  decides whether this record's target is even within camera range yet;
  if not, its "done" bit (`0x80`) is left alone and it's skipped for now
  (record advances but nothing fires).
- If in range, and control bit `0x01` is set, first calls
  `check_box_vs_player` — i.e. **some spawn records only fire when Rick
  is standing on/near the trigger tile**, not just when it's scrolled
  into view.
- Then, independently, up to four more bits can each fire a distinct
  handler against the *same* record: bit `0x02` → `FUN_00014bee`, bit
  `0x04` → `FUN_00014c20`, bit `0x08` → `FUN_00014c5a` (none of these
  three decoded yet — next priority), bit `0x10` → scans the smaller
  object-slot table at `$167a2` (`update_object_slots`'s table, matching
  the earlier section) calling `FUN_00014cb4` per active slot, bit
  `0x20` → scans the main `g_actor_table` calling `FUN_00014d04` per
  active slot.
- Bit `0x80` marks the record as already resolved (skip permanently once
  set); bit `0x40` suppresses re-firing without fully disabling it; bit
  `0x08` combined with completion additionally fires a sound.

**Practical takeaway**: level trigger/spawn data is not just "spawn enemy
type X at position Y" — it's a small **condition/action bitmask per
record**, capable of gating on player proximity, cross-referencing both
entity tables, and re-triggering existing actors/objects rather than
only creating new ones. A faithful data format for reproduction needs
this full bitfield, not just a type+position pair.

### Ghidra annotations added this pass

Struct created: `ActorRecord` (88 bytes, full field layout above),
applied to `g_actor_table` as `ActorRecord[6]`. Functions renamed:
`check_box_vs_player` (`$14b7a`, from `FUN_00014b7a`),
`dispatch_spawn_record` (`$14a3c`, from `FUN_00014a3c`).

### Updated open follow-ups

1. Decode `FUN_00014bee`, `FUN_00014c20`, `FUN_00014c5a` (the three
   remaining undecoded spawn-dispatch handlers) and `FUN_00014cb4`/
   `FUN_00014d04` (the object-slot-table and actor-table cross-reference
   handlers) — this fully completes the spawn/trigger system.
2. Fill in the "unknown" byte ranges in `ActorRecord` (`0x04`, `0x08-0x0d`,
   `0x10-0x15`, `0x1c-0x1d`, `0x24-0x25`, `0x2c-0x2d`, `0x2f`, `0x31`,
   `0x3e-0x4d`, `0x50-0x57` — roughly 40 of the 88 bytes are still
   unaccounted for) by decoding the remaining actor-related functions
   (`FUN_00014bee`/`c20`/`c5a`/`cb4`/`d04` above, plus
   `update_camera_scroll`/`update_fall_state_slot` if they touch actor
   records).
3. Fully decode a concrete data sample of `g_enemy_spawn_table_ptr`
   against the now-much-more-precise record format above (control byte
   bit layout, 4-byte packed stride) — still needs live level data.
4. Individually name the remaining player sub-state flags at
   `$12e14`-`$12e28` (one, `_DAT_00012e18`, is now identified as the
   crouch flag — nine more to go).
5. Find the render/blit routines — still unexplored.

## Spawn-trigger handlers decoded; object-slot table shares ActorRecord's stride (2026-09-14)

Completed the "decode the remaining spawn-dispatch handlers" follow-up,
and made progress on the "fill in `ActorRecord` unknowns" follow-up as a
side effect of tracing the object-slot table (`$167a2`) that several of
these handlers touch.

### The three precondition-gated trigger variants (bits `0x02`/`0x04`/`0x08`)

All three turned out to be thin precondition gates that, if their
condition holds, call one shared action routine — they are variants of
"do X only if some global flag/counter says so", not three different
actions:

- **`spawn_trigger_variant_a`** (`$14bee`, bit `0x02`) — gated on
  `_DAT_00016902`. This is the same flag `update_camera_scroll` (`$13e14`)
  checks at its very top (`if (_DAT_00016902 == 0) return;`) and clears
  on scroll-bounds failure — so this trigger variant fires only **while
  a camera-scroll transition is active**. Role: not renamed with full
  confidence (still "variant_a" rather than a scroll-specific name) since
  the causal direction (does the trigger start the scroll, or gate on an
  already-running scroll?) isn't nailed down yet.
- **`spawn_trigger_if_falling`** (`$14c20`, bit `0x04`) — gated on
  `g_fallobj_state` (must be > 0, i.e. the single dedicated falling-object
  slot — see below — is active) **and** `_DAT_00012efe`. The latter is
  set to `1` inside `update_fall_state_slot` (`$13e98`) only in the branch
  that also sets `_g_player_death_trigger` via a `check_box_vs_player`
  call against the falling object — i.e. this flag means "the falling
  object just landed/impacted this frame." So this trigger fires only on
  the frame a falling hazard lands.
- **`spawn_trigger_variant_c`** (`$14c5a`, bit `0x08`) — gated on
  `DAT_00012ef4`. This global's producer wasn't traced this pass (role
  uncertain — do not treat as understood).
- Shared action: **`point_in_box_test`** (`$14c8c`) — a plain
  point-in-rectangle test (box position/size in D0-D3, probe point in
  D6/D7, boolean via condition codes as usual). All three variants funnel
  into this one primitive when their gate passes.

### The falling-object subsystem is a single dedicated slot, not part of `g_actor_table`

`update_fall_state_slot` (`$13e98`) manages exactly one falling-hazard
object via its own globals (`g_fallobj_state`, `g_fallobj_x`,
`g_fallobj_y`, plus a handful of `DAT_00016b1*` timing fields) — **not**
a slot in `g_actor_table` or the object-slot table. It reuses the shared
primitives freely: `advance_actor_anim_script` for its animation and
`check_box_vs_player` for the player-impact hitbox test (same fixed
12×10-ish probe box convention as the other `check_box_vs_*` callers).
`_DAT_00012efe` (see above) is its "impacted this frame" output flag,
and there's a short countdown (`DAT_00012f00`, counts to 7-8) after
impact during which it keeps re-testing the player-impact box each frame
before finally clearing `g_fallobj_state`.

### `check_box_vs_object_slot` / `check_box_vs_actor` (bits `0x10`/`0x20`) — confirmed cross-table AABB checks

Both scan their respective table (`update_object_slots`'s table at
`$167a2` for bit `0x10`, `g_actor_table` for bit `0x20`) and run an AABB
test per active slot. `check_box_vs_actor` independently re-confirms
`ActorRecord`'s `x`/`y`/`width`/`height` offsets (`0x02`/`0x06`/`0x26`/
`0x28`) from a third call site.

### The object-slot table shares `ActorRecord`'s 88-byte stride, and some — not all — field offsets

Disassembling `update_object_slots` (`$150a2`) directly (rather than
trusting the decompiler's pointer-width guess) shows its per-slot loop
step is `lea (0x58,A6),A6` — **0x58 = 88 bytes, exactly `sizeof(ActorRecord)`**.
This is a real structural fact, not a coincidence: `check_box_vs_object_slot`'s
offset-`0x4e` "active" gate (noted in the previous section as a lead)
lines up with `ActorRecord.explosion_done_flag` at the same offset.

Disassembling/decompiling the per-slot handler `FUN_000150c0` (called
once per active slot) against this confirmed stride shows the object-slot
struct **reuses `ActorRecord`'s early field conventions but diverges
significantly past offset `0x10`** — it is a separate struct of the same
size, not a literal `ActorRecord` instance:

- Offset `0x00` (word): an object **type** enum (1/2/3 seen: type 1 does
  a back-and-forth patrol via a phase counter, type 2/3 have distinct
  branches through a shared `FUN_0001570e` helper) — this reuses the byte
  pair Ghidra's `ActorRecord.state_flags`/`behavior_flags` occupy, but
  here it's read as one 16-bit type code, not two independent flag bytes.
- Offset `0x02` = x, offset `0x06` = y — **match `ActorRecord.x`/`.y`
  exactly**, same collision-probe usage pattern as the actor table.
- Offset `0x0e` = a frame/base value combined into an animation index —
  **matches `ActorRecord.anim_frame`'s offset**.
- Offset `0x3e` = a per-type animation base/offset added into the frame
  index each frame — this is the first byte of `ActorRecord`'s previously
  fully-unknown `0x3e-0x4d` range. Treat as **hypothesis for this table
  only**: "object records store a type-specific animation base here" —
  not yet confirmed for actual enemy `ActorRecord` slots.
- Offsets `0x40`/`0x42`/`0x44`/`0x46`/`0x48`/`0x4a`/`0x4c` (rest of the
  `0x3e-0x4d` unknown range): a cluster of per-frame state flags/deltas
  specific to this moving-object logic (collision-stuck flag, two
  map-specific behavior flags, a horizontal-delta accumulator, a
  "frozen/disabled" gate). Same caveat as above — object-slot-specific,
  not confirmed for `ActorRecord` proper.
- Offset `0x4e` = `explosion_done_flag` — **confirmed reused identically**
  (this is the offset `check_box_vs_object_slot` already keyed off).
- Offsets `0x50`/`0x52`/`0x54`/`0x56` (the fully-unknown `0x50-0x57`
  range): here used as an activation flag, a phase counter, a phase
  wrap-around threshold, and a post-hit countdown timer respectively.
  Same caveat: plausible hypothesis for `ActorRecord`'s tail, unconfirmed
  for enemy use.
- Offset `0x22` onward (where `ActorRecord` has `move_script_ptr`) is
  instead read here as a small 16-bit animation-phase counter with
  wraparound at 0x20 — i.e. **this table does not use the script-VM
  pointers at all**; it's hardcoded per-type motion, not driven by
  `advance_actor_move_script`/`advance_actor_anim_script`'s byte-code
  scripts. That's the key divergence from `ActorRecord`'s design.

**Practical takeaway**: there are (at least) two structurally-identical-
size-but-different-purpose record tables in this engine — the 6-slot
scripted `g_actor_table` (enemies, script-VM driven) and the smaller
object-slot table at `$167a2` (simpler hardcoded moving hazards/props,
type-switched, no script pointers). A reproduction needs both as
distinct struct definitions, not one shared type, despite the identical
88-byte size and several shared leading-field conventions (x, y,
anim_frame, explosion_done_flag).

`update_camera_scroll` (`$13e14`) was also inspected and confirmed to be
pure scroll-position bookkeeping (own globals `DAT_00016904`/`08`/`26`,
no `ActorRecord`/object-slot table access) — out of scope per the
game-logic-only focus, not explored further.

### Ghidra annotations added this pass

Functions renamed: `point_in_box_test` (`$14c8c`), `spawn_trigger_variant_a`
(`$14bee`), `spawn_trigger_if_falling` (`$14c20`), `spawn_trigger_variant_c`
(`$14c5a`), `check_box_vs_object_slot` (`$14cb4`), `check_box_vs_actor`
(`$14d04`).

### Updated open follow-ups

1. Determine `spawn_trigger_variant_a`'s causal relationship to
   `update_camera_scroll` (does the trigger start scrolling, or only fire
   while scrolling is already underway?) and name `_DAT_00016902`
   accordingly.
2. Trace the producer of `DAT_00012ef4` (gate for `spawn_trigger_variant_c`)
   — not yet found.
3. Confirm or refute the object-slot-derived hypotheses for `ActorRecord`'s
   `0x3e-0x4d` and `0x50-0x57` ranges against actual enemy-slot usage
   (candidates: re-examine `update_actor_ai`/`advance_actor_move_script`
   more closely, or find a function that writes those offsets on
   `g_actor_table` directly rather than the object-slot table).
4. `ActorRecord`'s remaining fully-unaccounted ranges after this pass:
   `0x04`, `0x08-0x0d`, `0x10-0x15`, `0x1c-0x1d`, `0x24-0x25`, `0x2c-0x2d`,
   `0x2f`, `0x31` (unchanged — no actor-table writes to these were found
   this pass; only the object-slot table's analogous-but-distinct bytes
   were decoded).
5. Fully decode a concrete data sample of `g_enemy_spawn_table_ptr`
   against the now-complete record/control-byte format — still needs
   live level data.
6. Individually name the remaining player sub-state flags at
   `$12e14`-`$12e28` (nine still to go).
7. Find the render/blit routines — still unexplored, deprioritized per
   the game-logic-only focus.

## Resolving the open follow-ups: fire cooldown, screen-exit trigger, and ActorRecord tail bytes (2026-09-14)

Chased down the three items flagged unresolved above by reading
`update_player_rick`'s full disassembly and `check_submap_exit_triggers`'
body, plus re-checking `update_actor_ai`'s own field accesses.

### `DAT_00012ef4` was Rick's weapon-fire cooldown all along

Renamed to **`g_player_fire_cooldown`** (word). `update_player_rick`
decrements it by 1 every frame while nonzero. When a new fire input edge
is detected (tile/input flag bits 2 or 3, compared against
`g_player_last_fire_input` — renamed from `DAT_00012ef2` — to ignore a
button being *held*, not just pressed), it's reloaded to `10` and the
current input byte is latched into `g_player_last_fire_input`. So
**`spawn_trigger_variant_c`'s gate (bit `0x08`) is "fires only while
Rick is within ~10 frames of having just fired his weapon"** — i.e. that
spawn-record variant is for targets that react to being shot (breakable
blocks, shootable switches), not a generic timer. `spawn_trigger_variant_c`
is not renamed further since "shootable target trigger" is still an
inference, not confirmed against a concrete data sample.

### The screen-exit/respawn trigger chain, now fully traced

- **`check_submap_exit_triggers`** (`$14362`) scans a 4-byte-stride
  submap-trigger table (`_g_submap_trigger_table_ptr`). For the record
  whose low 2 bits match the current submap index and whose row byte
  matches Rick's current (scroll-adjusted, tile-quantized) Y position, it
  writes bit `0x40` of that record's control byte into
  **`g_screen_exit_trigger_flag`** (renamed from `_DAT_000144c2`) — this
  is the actual "Rick has reached a room-exit row" detector. The same
  record's bit `0x20` also feeds `_DAT_00012e14` (one of the still-unnamed
  player sub-state flags) and, via a different bit combination, can set
  `g_submap_complete_flag` directly (already documented).
- **`handle_screen_edge_and_respawn`** (`$15bc0`, already named) gates its
  entire body on `g_screen_exit_trigger_flag` — confirming the causal
  link guessed at previously. Once triggered, it drives actor 0's
  transition movement, tests `spawn_trigger_variant_a`/`_if_falling`, and
  on completion fully re-initializes all 6 `ActorRecord` slots (clearing
  `state_flags`/`behavior_flags`/`substate_flags`, reloading
  `anim_script_ptr`/`move_script_ptr` from a fresh per-screen table
  `PTR_DAT_00015a2c`) plus resets object-slot 0 — i.e. **this is the
  per-screen actor respawn/reinitialization routine**, confirming its
  existing name.
- `_DAT_00016902` (still unrenamed — kept as a plain global, not
  confidently named) is cleared to `0` at the very top of every
  `main_loop_body` iteration, and consumed later the same frame by
  `update_camera_scroll` (must be nonzero to scroll at all) and
  `spawn_trigger_variant_a`. **Its setter (the `=1` write) was not found**
  this pass — searched `update_player_rick`, `handle_screen_edge_and_respawn`,
  and the actor-0 transition-mover `FUN_0001726e` directly; none of them
  write it to a nonzero value. It's either written through an addressing
  mode the address-literal xref search misses (e.g. an indexed/computed
  store), or by a function not yet examined. Left as a genuine open
  question rather than guessed.

### `ActorRecord`'s `0x3e-0x4d` and `0x50-0x57` ranges: confirmed unused by actual enemy-slot logic

Re-read `update_actor_ai`'s full body against the confirmed struct
offsets. It exercises `substate_flags` (`0x2e`), `behavior_flags_alt`
(`0x30`), `move_script_ptr_alt`/`anim_script_ptr_alt` (`0x32`/`0x36`,
swapped with the primary pointers at `0x16`/`0x1e`),
`move_script_counter` (`0x1a`) and `anim_hold_counter` (`0x22`, both
zeroed post-swap), and `explosion_done_flag` (`0x4e`) — but **never
touches offsets `0x3e-0x4d` or `0x50-0x57`**. Combined with the earlier
finding that the object-slot table's per-slot handler (`FUN_000150c0`)
*does* use that exact byte range heavily (type-specific animation base,
motion/collision flags, phase counters) for its own struct of the same
size: this is now a confident conclusion, not just a hypothesis — **that
byte range is object-slot-table-specific state that happens to occupy
the tail of the shared 88-byte record size, and is genuinely unused
padding when the same-sized slot is used as an enemy `ActorRecord`.**
No further work needed on this item; not just unnamed, but confirmed
inapplicable to enemies.

One correction from this re-read: the fields previously named `prev_x`/
`prev_y` (offsets `0x3a`/`0x3c`) actually store the **move-script's raw
per-frame delta** (`advance_actor_move_script`'s dx/dy return, stashed
here before being added into `x`/`y`), not a "previous position" —
renamed to **`move_delta_x`**/**`move_delta_y`** in the `ActorRecord`
struct to reflect that.

### Ghidra annotations added this pass

Struct field renames on `ActorRecord`: `prev_x`→`move_delta_x` (`0x3a`),
`prev_y`→`move_delta_y` (`0x3c`). Labels created: `g_player_fire_cooldown`
(`$12ef4`), `g_player_last_fire_input` (`$12ef2`),
`g_screen_exit_trigger_flag` (`$144c2`).

### Updated open follow-ups

1. Locate the write site that sets `_DAT_00016902` to a nonzero value
   (only its clear-to-0 sites were found this pass) — needed before it
   can be confidently named/renamed.
2. Trace the producer of `DAT_00012ef4`'s sibling gate for
   `spawn_trigger_if_falling`/`spawn_trigger_variant_a` more precisely if
   still needed, though both are now reasonably well understood.
3. `ActorRecord`'s remaining genuinely-unaccounted-for ranges (now
   narrowed): `0x04`, `0x08-0x0d`, `0x10-0x15`, `0x1c-0x1d`, `0x24-0x25`,
   `0x2c-0x2d`, `0x2f`, `0x31`. (`0x3e-0x4d`/`0x50-0x57` are resolved as
   "unused for enemies" per above — remove from the "to fill in" list.)
4. Fully decode a concrete data sample of `g_enemy_spawn_table_ptr` and
   `_g_submap_trigger_table_ptr` against their now-complete record
   formats — still needs live level data.
5. Individually name the remaining player sub-state flags at
   `$12e14`-`$12e28` (nine still to go, including `_DAT_00012e14`, now
   known to be set from the submap-trigger table's bit `0x20`).
6. Find the render/blit routines — still unexplored, deprioritized per
   the game-logic-only focus.

## `_DAT_00016902`'s setter found: horizontal screen-scroll trigger (2026-09-14)

Located via a raw byte-pattern search for `move.w #1,(0x16902).l`
(`33fc000100016902`) rather than an address xref, since the only
`get_xrefs_to` write hit besides the two known clears
(`main_loop_body`'s frame-top reset, `handle_screen_edge_and_respawn`'s
completion clear) was a call target (`FUN_00013d58`) whose own body
Ghidra hadn't attributed the literal-operand write to directly in the
earlier pass — the pattern search found it immediately.

**`FUN_00013d58`**, called from `update_player_rick` (and duplicated
inline inside a second helper, `FUN_00013d0a`, itself called from
`update_player_rick` when input/collision flag bit `0x80` is set — read
elsewhere in the same function as a "pushed against a wall/edge" signal)
is the **start-horizontal-scroll routine**:

- Guarded by `PTR_DAT_000176f4._0_2_ != 0` (some kind of "scroll budget"
  counter — decremented by 1 each time a transition starts; role beyond
  that not traced) and `_DAT_00016902 == 0` (don't restart an
  already-active scroll).
- Seeds the scroll: `DAT_00016908` = Rick's Y + 7 (scroll anchor),
  `DAT_00016904` = Rick's X (scroll origin, matches `update_camera_scroll`'s
  own use of this global as the position it advances), `DAT_00016926` =
  `+8` or `-8` depending on `g_player_facing_dir` (scroll step —
  `update_camera_scroll` adds this every call while active).
  `_DAT_00012e26` (a player sub-state flag) is set to `0xffff` alongside.
- Sets `_DAT_00016902 = 1`, which is exactly the flag `update_camera_scroll`
  requires nonzero to do anything, and that `spawn_trigger_variant_a`
  gates on — confirming the original hypothesis: **`spawn_trigger_variant_a`
  fires only while a horizontal screen-scroll transition is in progress.**

Renamed `_DAT_00016902` → **`g_camera_scroll_active`**. This closes the
last open item from the previous section — the full screen-transition
picture is now: `check_submap_exit_triggers` handles vertical
room-to-room moves (via the submap-trigger table and
`handle_screen_edge_and_respawn`'s full actor respawn), while
`FUN_00013d58`/`FUN_00013d0a` handle horizontal scroll-within-a-screen
triggered by walking into a screen-edge wall — two distinct mechanisms
that happen to share some of the same consuming code
(`spawn_trigger_variant_a`, actor-table respawn on completion).

### Ghidra annotations added this pass

Label created: `g_camera_scroll_active` (`$16902`, renamed from
`_DAT_00016902`).

### Updated open follow-ups

All three struct/global items from the prior section are now resolved.
Remaining open items (carried forward, unchanged in substance):

1. `ActorRecord`'s still-unaccounted-for ranges: `0x04`, `0x08-0x0d`,
   `0x10-0x15`, `0x1c-0x1d`, `0x24-0x25`, `0x2c-0x2d`, `0x2f`, `0x31`.
2. Name `PTR_DAT_000176f4` (the horizontal-scroll "budget" counter) and
   trace what replenishes it.
3. Fully decode a concrete data sample of `g_enemy_spawn_table_ptr` and
   `_g_submap_trigger_table_ptr` against their now-complete record
   formats — still needs live level data.
4. Individually name the remaining player sub-state flags at
   `$12e14`-`$12e28` (still nine to go, though several now have inferred
   roles from this pass's tracing: `_DAT_00012e14` from the submap
   trigger's bit `0x20`, `_DAT_00012e24`/`_DAT_00012e26` from the
   horizontal-scroll-trigger path).
5. Find the render/blit routines — still unexplored, deprioritized per
   the game-logic-only focus.

## `PTR_DAT_000176f4` is an effects-subsystem slot (out of scope); four more player flags named (2026-09-14)

### `PTR_DAT_000176f4`/`_DAT_000176f2` ruled out of the "scroll budget" theory

Traced this pair's other call sites to check the "horizontal-scroll
budget counter" theory from the previous section. `update_actor_ai`
writes the exact same pair (`PTR_DAT_000176f4._0_2_ = 6;
_DAT_000176f2 = 0xffff;`) when an enemy of type `0x28` dies, and a data
reference into the surrounding table exists at `$178ae` (not a function —
a data table entry, consistent with a small fixed-size resource pool).
This is a **shared visual/sound-effect slot** (word = effect id/duration,
second word = active flag), reused by both "enemy death effect" and "Rick
bumped a wall" to request the same kind of transient effect object — not
a level-progression resource. Per the standing game-logic-only scope
(no sound/render work), this is **not investigated further** — noted
here only to correct the earlier "budget counter" phrasing: it's an
effects-slot request/consumption counter, not a scroll-transition budget.

### Four more player sub-state flags named, from the `update_player_rick` disassembly already on hand

Re-read the `$130a0-$13460` disassembly captured while tracing the fire
cooldown/screen-exit chain, this time for the flags themselves rather
than the fire-cooldown/scroll logic:

- **`g_player_wall_push_flag`** (renamed from `_DAT_00012e1a`) — set to
  `1` in the branches that handle Rick pushing into a wall-type
  collision result (paired with the horizontal-scroll-trigger code from
  the previous section); while set, forces alternate velocity handling
  and is checked before starting a new horizontal scroll
  (`g_camera_scroll_active`). Confident: this is the "Rick is currently
  pressed against a wall" state.
- **`g_player_wall_contact_flag`** (renamed from `_DAT_00012e24`) — set
  to `1` in the same wall-collision handling region as
  `g_player_wall_push_flag` but from a slightly different branch
  (immediately before the `PTR_DAT_000176f4` effect-slot check at
  `$13922`) — likely "wall touched this frame" as distinct from
  "actively being pushed/stuck", but the exact distinction between the
  two wasn't fully pinned down; treat as **plausible, not fully
  confirmed**.
- **`g_player_scroll_pending_flag`** (renamed from `_DAT_00012e26`) — set
  to `0xffff` by `FUN_00013d58` when a horizontal scroll starts, and
  read by `FUN_00013d0a`'s guard (`if (_DAT_00012e26 == 0)`) to avoid
  re-entering the scroll-start logic while one is already pending/active.
  Confident.
- **`g_player_ceiling_blocked_flag`** (renamed from `_DAT_00012e16`) —
  read immediately alongside the crouch flag (`_DAT_00012e18`) at
  `$13390-$133ac`: the crouch flag is only auto-cleared when this flag
  is also clear. Inferred meaning: "something overhead prevents standing
  up" (low ceiling), gating whether Rick can un-crouch. **Plausible, not
  independently confirmed** — no second call site checked.

### Ghidra annotations added this pass

Labels created: `g_player_wall_push_flag` (`$12e1a`),
`g_player_wall_contact_flag` (`$12e24`), `g_player_scroll_pending_flag`
(`$12e26`), `g_player_ceiling_blocked_flag` (`$12e16`).

### Updated open follow-ups

1. `ActorRecord`'s still-unaccounted-for ranges: `0x04`, `0x08-0x0d`,
   `0x10-0x15`, `0x1c-0x1d`, `0x24-0x25`, `0x2c-0x2d`, `0x2f`, `0x31`.
2. Remaining unnamed player sub-state flags: `_DAT_00012e14` (has an
   inferred role — set from the submap-trigger table's bit `0x20`,
   forces an alternate branch in `update_player_rick` — but the branch
   target itself, around `$13b84`, hasn't been read), `_DAT_00012e1c`,
   `_DAT_00012e1e`, `_DAT_00012e20`, `_DAT_00012e22`, `_DAT_00012e28`,
   `_DAT_00012e2a`, `_DAT_00012e2c` (the last two are full-override
   states that skip most of `update_player_rick` — likely climbing/
   riding-platform or similar exclusive movement modes; their branch
   targets `$13ace`/`$13a62` haven't been read yet). This needs reading
   the `$13460-$13b84` region of `update_player_rick`, not yet
   disassembled.
3. Fully decode a concrete data sample of `g_enemy_spawn_table_ptr` and
   `_g_submap_trigger_table_ptr` against their now-complete record
   formats — still needs live level data.
4. Find the render/blit routines — still unexplored, deprioritized per
   the game-logic-only focus.

## Stairs/ladder movement decoded; four more flags named (2026-09-14)

Disassembled `update_player_rick`'s `$13460-$1370c` region (the block
right after the fire-input handling, previously unread) — this is
Rick's **vertical movement state machine**: stairs, ladders, and
jump/airborne gating, driven by tile-attribute bits in `D7` and the
up/down input bits in `D0`.

- **`g_player_forced_push_flag`** (renamed from `_DAT_00012e14`) —
  confirmed at `$13662`: when set, `update_player_rick` skips its normal
  vertical-movement branch entirely, selects animation code `0xc`, and
  calls `FUN_00013d0a` (the horizontal-scroll-trigger helper from two
  sections ago) directly. So this **is** the "scripted/forced walk into
  a screen-edge push" flag guessed at earlier — now confirmed, not just
  inferred from the submap-trigger table alone.
- **`g_player_on_stairs_flag`** (renamed from `_DAT_00012e1e`) — set to
  `1` specifically in the "stairs, moving down, map-type 2" branch
  (`$13584`). **Correction (2026-09-14, see below):** at the time this was
  written, `_DAT_0001697e` was mistakenly believed to be a companion
  "ladder flag" for the same vertical-movement block. That belief was
  disproven a few paragraphs later in this same section — `$1697e` is
  actually the pre-existing `g_player_facing_dir`, holding a signed step
  delta, not a ladder flag. **No distinct "ladder" sub-state flag has
  actually been identified**; ladder handling within this vertical-movement
  block, if distinct from the stairs case at all, remains unattributed to
  a specific flag.
- **`g_player_airborne_flag`** (renamed from `_DAT_00012e1c`) — read at
  `$136ec`: when clear, `update_player_rick` runs a ground/vertical-tile
  search (comparing a saved scroll delta against `_DAT_00012e30`'s low 2
  bits and possibly playing a footstep-adjacent effect); when set, that
  search is skipped outright. Reading this as "not currently in contact
  with a walkable surface" — i.e. airborne (jumping/falling) — fits the
  skip semantics, but this one is **less certain** than the previous
  three: only one call site examined, and the surrounding code cares
  more about horizontal scroll-delta bookkeeping than an obvious
  jump/fall test.
- `_DAT_00012e20`/`_DAT_00012e22` are set as **map-type-specific
  sub-variants of the stairs/ladder case** (map `== 4` sets `e20`, map
  `== 2` sets `e22`, both inside the up/down-input branches) — clearly
  real distinctions in the vertical-movement logic, but their exact
  gameplay meaning (which map each corresponds to, and why the
  distinction matters elsewhere) wasn't chased further. Left unnamed.
- `_DAT_00012e2a`/`_DAT_00012e2c` (the two full-override flags that skip
  most of `update_player_rick`, branching to `$13ace`/`$13a62`) were
  **not reached** by this disassembly window (their branch targets are
  further down, beyond `$1370c`) — still fully open.

### Ghidra annotations added this pass

Labels created: `g_player_forced_push_flag` (`$12e14`),
`g_player_on_stairs_flag` (`$12e1e`), `g_player_airborne_flag`
(`$12e1c`), `g_player_fallobj_trigger_flag` (`$12e28`).

### Correction: full decompile of `update_player_rick` obtained; two prior claims fixed (2026-09-14)

Pulling the full decompile of `update_player_rick` (`$13096`) rather
than reading disassembly windows piecemeal caught two mistakes from
earlier this session and the prior "pending items" note:

- **`_DAT_0001697e` is NOT a ladder flag.** It already carries an
  established name from an earlier session, `g_player_facing_dir`
  (confirmed via `audit_global`), and the decompile shows it holds a
  small signed step value (`0`, `±1`, `±2`) added into Rick's x-position
  during the stairs-transition code, not a boolean. The
  `g_player_on_ladder_flag` label I had created at this address was
  wrong and has been **deleted**. Apologies for the churn — the
  disassembly-only read of that one branch was misleading without the
  full decompiled context.
- **`_DAT_00012e2a`/`_DAT_00012e2c` are not unnamed "full-override
  movement flags"** as an earlier pass's open-items note assumed — they
  are already-named (pre-dating this session) `g_player_dead_flag` and
  `g_player_death_trigger` (confirmed via `audit_global`), gating the
  ballistic death-fall/particle-burst code at `$13ace`/`$13a62`. That
  block spawns 3 death-fragment records into an 88-byte-stride table at
  `$169b2` (`ActorRecord`-sized slots, likely a continuation of the
  object-slot table past its first 6 entries) — this is
  particle/death-effect content, ruled **out of scope** per the
  sound/render exclusion, and not investigated further.
- **`_DAT_00012e28`** (now `g_player_fallobj_trigger_flag`) — set to `1`
  whenever Rick's collision result triggers a falling-object tile; gates
  the same falling-object spawn logic documented earlier
  (`update_fall_state_slot`, `g_fallobj_state`). High confidence, single
  clear call site in the full decompile.
- `_DAT_00012e20`/`_DAT_00012e22` are confirmed **map-specific markers
  paired with the stairs-step logic**: `e20` sets alongside a
  single-unit step on map 4, `e22` alongside a two-unit step on map 2,
  in the same up/down-input branches as `g_player_on_stairs_flag`. Read
  elsewhere only to pick an animation-cycle length constant. Left
  unnamed — the map/step pairing is clear but the underlying "why" isn't.

### Updated open follow-ups

1. `ActorRecord`'s still-unaccounted-for ranges: `0x04`, `0x08-0x0d`,
   `0x10-0x15`, `0x1c-0x1d`, `0x24-0x25`, `0x2c-0x2d`, `0x2f`, `0x31`.
2. `_DAT_00012e20`/`_DAT_00012e22` — map-specific stairs-step markers,
   role understood but not confidently named.
3. Fully decode a concrete data sample of `g_enemy_spawn_table_ptr` and
   `_g_submap_trigger_table_ptr` against their now-complete record
   formats — still needs live level data.
4. Find the render/blit routines — still unexplored, deprioritized per
   the game-logic-only focus.

## `ActorRecord`'s dual behavior-profile swap confirmed field-by-field (2026-09-14)

Pulled the full decompile of `update_actor_ai` (`$14d70`) and cross-checked
it against the current `ActorRecord` layout (via `get_struct_layout`,
which already carries clean names from an earlier pass: `bState_flags`,
`bBehavior_flags`, `nX`, `nY`, `nAnim_frame`, `nMove_script_ptr`,
`nMove_script_counter`, `nAnim_script_ptr`, `nAnim_hold_counter`,
`nWidth`, `nHeight`, `nSecondary_data_ptr`, `bSubstate_flags`,
`bBehavior_flags_alt`, `nMove_script_ptr_alt`, `nAnim_script_ptr_alt`,
`nMove_delta_x`, `nMove_delta_y`, `nExplosion_done_flag`, plus unnamed
blobs `nUnk04`, `aUnk08`, `aUnk10`, `aUnk1c`, `aUnk24`, `bUnk2f`,
`bUnk31`, `aUnk3e`, `aUnk50`).

This resolves the "dual behavior profile, atomically swapped" claim from
much earlier in the session into an exact field list. When a spawn
record's dispatch result calls for a behavior change (the `(bVar3 & 8)
!= 0` case in `update_actor_ai`, reached via `dispatch_spawn_record`),
the actor swaps its **entire active profile** for its alternate in one
block:
- `bBehavior_flags` (offset 1) ↔ `bBehavior_flags_alt` (offset 0x30)
- `nMove_script_ptr` (offset 0x16) ↔ `nMove_script_ptr_alt` (offset 0x32)
- `nAnim_script_ptr` (offset 0x1e) ↔ `nAnim_script_ptr_alt` (offset 0x36)

`bSubstate_flags` (offset 0x2e) gates whether this swap has already
happened (bits `0x10`/`0x20`/`0x40`/`0x08` track swap state and a
"return to primary" condition) — confirms this field's role rather than
just its existence.

Also confirms `nMove_delta_x`/`nMove_delta_y` (offsets 0x3a/0x3c) are
written directly from the move-script's per-step output and added into
`nX`/`nY` every frame — matches the earlier delta-not-position
correction, now seen at the actual write site
(`unaff_A6[0x1d] = (short)uVar2; ...; unaff_A6[1] += uVar2`).

One narrow new observation: two bytes at offset `0x12` (inside the
6-byte `aUnk10` blob, i.e. just before `nMove_script_ptr` at 0x16) are
explicitly zeroed in two of `update_actor_ai`'s cleanup paths, alongside
`nAnim_hold_counter`, when an actor's script pointers are being reset to
a default script. Likely a counter/timer paired with the move script,
but this is a single write-only observation with no confirmed read
site — not confident enough to split out and name.

### Ghidra annotations added this pass

None — this pass was pure confirmation via decompile + struct-layout
cross-reference, no new renames.

### Updated open follow-ups

1. `ActorRecord`'s remaining unnamed blobs: `nUnk04`, `aUnk08` (offsets
   8-13), `aUnk1c` (28-29), `aUnk24` (36-37), `bUnk2f`, `bUnk31` — plus
   the confirmed-unused-by-enemies `aUnk3e`/`aUnk50`. The 2 bytes at
   offset `0x12` inside `aUnk10` have a narrow lead (see above) but
   aren't independently confirmed.
2. `_DAT_00012e20`/`_DAT_00012e22` — map-specific stairs-step markers,
   role understood but not confidently named.
3. Fully decode a concrete data sample of `g_enemy_spawn_table_ptr` and
   `_g_submap_trigger_table_ptr` against their now-complete record
   formats — still needs live level data.
4. Find the render/blit routines — still unexplored, deprioritized per
   the game-logic-only focus.

## Actor-spawn-init routines checked for the remaining unnamed `ActorRecord` bytes (2026-09-14)

Decompiled the move/anim script interpreters (`advance_actor_move_script`
`$172fa`, `advance_actor_anim_script` `$171bc`) and the two type-specific
actor-init helpers (`FUN_000146a0` `$146a0`, `FUN_00014862` `$14862`,
both called from `FUN_00014636` `$14636`, the per-spawn-type actor
constructor) looking for reads/writes into the still-unnamed blobs
(`nUnk04`, `aUnk08`, `aUnk1c`, `aUnk24`, `bUnk2f`, `bUnk31`).

- The two script interpreters touch **only already-named fields**
  (`nMove_script_ptr`/`nMove_script_counter`, `nAnim_script_ptr`/
  `nAnim_hold_counter`/`nAnim_frame`) — good confirmation of the existing
  names, no new fields found there.
- Both actor-init helpers **zero the entire `aUnk10` blob (offsets
  0x10/0x12/0x14) as a unit** at actor-spawn time (`unaff_A6[8]`,
  `unaff_A6[9]`, `unaff_A6[10]`) — so this blob is genuinely
  spawn-initialized state, not padding. One of the three words (offset
  `0x12`) is distinguished: both helpers set it to `-1` instead of `0`
  specifically when bit `0x80` of the spawn-record's 4th byte is set,
  and `update_actor_ai` separately clears it back to `0` on certain
  script-reset paths. This is a real, consistent behavior — probably a
  "spawn-record variant echoed onto the actor" flag or a one-shot/timer
  bit — but its exact meaning (what bit `0x80` of the spawn record
  represents) hasn't been traced back to the spawn-record format itself,
  so it's being left unnamed rather than guessed.
- `nUnk04`, `aUnk08`, `aUnk1c`, `aUnk24`, `bUnk2f`, `bUnk31` were **not
  touched by any of these four functions** — still no lead on them from
  the actor-side code explored so far. They may only be written by the
  type-specific move-script byte-code itself (interpreted data, not code)
  or by functions further from the core actor-update path
  (`FUN_00014962`/`FUN_00014970`/`FUN_000157be`/`FUN_000157f4`, not yet
  examined).

### Ghidra annotations added this pass

None — evidence gathered was consistent with existing names but not
strong enough to justify new renames.

### Updated open follow-ups

1. `ActorRecord`'s remaining unnamed blobs: `nUnk04`, `aUnk08` (offsets
   8-13), `aUnk1c` (28-29), `aUnk24` (36-37), `bUnk2f`, `bUnk31`. Next
   places to check: `FUN_00014962`, `FUN_00014970`, `FUN_000157be`,
   `FUN_000157f4` (the two spawn-subtype dispatch targets from
   `FUN_00014636`), and the move-script byte-code format itself.
2. `aUnk10` offset `0x12`'s spawn-flag-echo behavior (see above) — traced
   as far as "mirrors spawn-record byte 3 bit `0x80`" but not further;
   would need the spawn-record format decoded to name confidently.
3. `_DAT_00012e20`/`_DAT_00012e22` — map-specific stairs-step markers,
   role understood but not confidently named.
4. Fully decode a concrete data sample of `g_enemy_spawn_table_ptr` and
   `_g_submap_trigger_table_ptr` against their now-complete record
   formats — still needs live level data.
5. Find the render/blit routines — still unexplored, deprioritized per
   the game-logic-only focus.

## Last player stairs flags named; remaining `ActorRecord` bytes confirmed dead-end for now (2026-09-14)

Two threads closed out this pass:

- **`_DAT_00012e20`/`_DAT_00012e22` named.** `get_xrefs_to` on both
  addresses shows every access confined to `update_player_rick`, with
  exactly one read site each (`$13830`/`$1383a`), where they select an
  animation run-cycle-length constant for the stairs-walk animation
  (map 4 uses length `1`, map 2 uses length `4`, otherwise `2`). No
  other consumer exists anywhere in the binary. Renamed to
  `g_player_stairs_variant_map4_flag` (`$12e20`) and
  `g_player_stairs_variant_map2_flag` (`$12e22`) — the names describe
  the confirmed behavior (map-specific stairs-animation selector) without
  overclaiming a deeper game-logic reason for the per-map difference.
- **The remaining unnamed `ActorRecord` bytes are a dead end for static
  analysis without live data.** Checked every function directly
  reachable from the actor-update path that hadn't been checked yet:
  `FUN_00014962`/`FUN_00014970` (free-slot scanners — only read
  `bState_flags`/`bBehavior_flags`), `FUN_000157be`/`FUN_000157f4`
  (a single-instance sound/effect toggle pair on unrelated globals
  `$157ac`-`$157b0`, not `ActorRecord` fields at all — likely gates a
  specific spawn-type's one-shot sound cue, out of scope), and
  `update_actor_slots` (`$14d48`, the outer per-slot loop — only reads
  `bState_flags`/`bBehavior_flags` to skip empty slots).
  **SUPERSEDED — see line ~2290 ("Follow-up: live `g_actor_table` sample
  from the same dump", 2026-09-14 later pass): a live sample showed all 4
  active slots have `bState_flags == 0`, so `bState_flags` alone is *not*
  the occupancy test. The real, decompile-confirmed test is the combined
  16-bit word `bState_flags:bBehavior_flags != 0`. This phrasing (and the
  same phrasing a few lines below in this paragraph) was flagged by that
  later pass as "loose" and scheduled for cosmetic cleanup ("Updated open
  follow-ups" item 4 there) but was never actually corrected at this
  location until this annotation.** None of these
  touch `nUnk04`, `aUnk08`, `aUnk1c`, `aUnk24`, `bUnk2f`, or `bUnk31`.
  Combined with the earlier findings, every function on the
  spawn→init→update→script-interpret call path has now been checked at
  least once. These bytes are either genuinely dead/padding (like the
  confirmed-unused `aUnk3e`/`aUnk50`) or are written by per-enemy-type
  move/anim-script *data* (byte-code content, not code) that hasn't been
  captured in a live RAM sample yet — static disassembly alone can't
  resolve that without a concrete script blob to read.

### Ghidra annotations added this pass

Labels created: `g_player_stairs_variant_map4_flag` (`$12e20`),
`g_player_stairs_variant_map2_flag` (`$12e22`).

### Updated open follow-ups

1. `ActorRecord`'s remaining unnamed blobs (`nUnk04`, `aUnk08`,
   `aUnk1c`, `aUnk24`, `bUnk2f`, `bUnk31`) — static analysis of the
   actor-update call path is now exhausted; next step needs either a
   live RAM sample with active enemies (to read actual script byte-code
   and see which fields it writes) or accepting these as
   likely-unused/padding, matching `aUnk3e`/`aUnk50`.
2. Fully decode a concrete data sample of `g_enemy_spawn_table_ptr` and
   `_g_submap_trigger_table_ptr` against their now-complete record
   formats — still needs live level data (same blocker as above).
3. Find the render/blit routines — still unexplored, deprioritized per
   the game-logic-only focus.

This closes out the player-state-flag naming effort for this session —
every `_DAT_0001*e**` global touched by `update_player_rick`'s stairs/
ladder/scroll logic now has either a confirmed name or a documented
reason it can't be named yet. Remaining open work is either blocked on
live level/RAM data (items 1-2) or explicitly out of scope (item 3).

## Spawn/trigger table decoded against a real data sample (2026-09-14)

The "still needs live level data" blocker on `g_enemy_spawn_table_ptr`/
`_g_submap_trigger_table_ptr` turned out to be already resolved by data
we had on disk: **`prg2-ram.bin` already has both pointers
populated** (`g_enemy_spawn_table_ptr` = `$54e11`,
`_g_submap_trigger_table_ptr` = `$54d98`, i.e. the trigger table sits
directly before the spawn table in memory, 0x79 bytes apart). No new
Hatari capture was needed. This makes sense in hindsight: `prg2-ram.bin`
was captured ~20s into the post-crack-screen "intro," and the intro is
the title-screen **attract-mode demo** (`attract_mode_handler`, see the
input-abstraction section above) — i.e. it's real map-1 gameplay driven
by a recorded input stream, not a separate non-gameplay state, so
level-1's runtime tables are already live at that point.

**Worked decode of a real sample**, applying `dispatch_spawn_record`'s
confirmed field layout (X source = *next* record's byte 1, in tile
units ×8, tested against `DAT_00016462 & 0xfff8` as the current scroll;
width nibble = next record's byte 2 high nibble, `(nibble+1)*8` pixels;
control bug = next record's byte 3) to the first 22 packed 4-byte
records read from `$54e11` (with `DAT_00016462` = `$2d6` → scroll
`720`px at capture time):

| # | x (px) | width (px) | ctrl | bits set |
|---|--------|------------|------|----------|
| 0 | -32 | 24 | `0x01` | player-proximity gate |
| 1 | 80 | 8 | `0x41` | player-proximity gate + done |
| 2 | 80 | 32 | `0x01` | player-proximity gate |
| 3 | 88 | 72 | `0x98` | done + suppress-refire + object-slot scan |
| 4 | 88 | 104 | `0x55` | proximity + fall-trigger + object-slot + actor-scan |
| 5 | 96 | 16 | `0x04` | fall-trigger |
| 6 | 168 | 80 | `0x4d` | proximity + fall-trigger + suppress-refire + actor-scan... |
| ... | ... | ... | ... | (monotonically increasing x through record 21, x=408) |

This is a clean, internally-consistent result: x values increase
monotonically record-over-record across this whole span, all sitting
just ahead of or just behind the 720px scroll position — exactly what a
position-ordered per-level spawn table should look like when read near
the camera's current position during demo playback. This is the first
concrete confirmation that the record format documented earlier is
correct against real level data, not just against the dispatcher's own
code.

**Caveat — table length/end not yet determined.** Continuing to read
past record ~21 as more 4-byte records produces `x` values that jump to
large negative/erratic numbers with no positional coherence (e.g.
records 22-45 in the raw byte stream), strongly suggesting the actual
`g_enemy_spawn_table_ptr` table ends well before that point and what
follows in memory is a different structure (possibly movement/animation
script byte-code, or the next level asset in the HNK-loaded blob) that
just happens to still parse as syntactically-valid-looking 4-byte
records. One exception: records 46-53 of the raw stream show a tight,
regular repeating pattern (`ctrl` alternating `0x11`/`0x20` at fixed
alternating x positions -280/-248) — this is too regular to be
incidental, but whether it's a second real (sub)table or coincidental
structure in script byte-code is not established. **Do not treat bytes
beyond the confirmed monotonic run (records 0-21) as decoded spawn
data** without first determining the table's real length (e.g. via a
terminator byte/count field read from a table *header*, which hasn't
been identified — the `bVar3 & 3` count read at dispatch time is a
per-call batch size, not the table length, per the `dispatch_spawn_record`
decompile above).

The same exercise against `_g_submap_trigger_table_ptr` (`$54d98`,
using the identical field layout) did **not** produce a comparably clean
monotonic run — x values were erratic from the first few records. This
could mean the submap-trigger table uses a different record
convention than the enemy-spawn table (plausible — they're read by
different call sites even though both ultimately funnel into
`dispatch_spawn_record`-style handling), or simply that this table's
first entries aren't position-ordered the same way. Not resolved this
pass — noted as open rather than guessed at.

### Ghidra annotations added this pass

None — the table's live location (`$54e11`/`$54d98` in this specific
RAM snapshot) is level-instance data inside the HNK-loaded blob, not a
fixed program symbol, so it isn't a meaningful place to attach a
permanent Ghidra label. The pointer *variables* (`g_enemy_spawn_table_ptr`,
`_g_submap_trigger_table_ptr`) were already named in an earlier session.

### Updated open follow-ups

1. Determine the enemy-spawn table's actual length/terminator so the
   confirmed-monotonic record run (0-21) can be distinguished with
   certainty from unrelated trailing bytes — likely needs either finding
   a header/count field read once at level-load time, or bracketing the
   table by finding what function writes `g_enemy_spawn_table_ptr` itself
   (its source address should reveal the table's start, and possibly a
   sibling "length" field is loaded alongside the pointer at the same
   call site).
2. Resolve why `_g_submap_trigger_table_ptr`'s decode didn't produce a
   clean monotonic run like the spawn table did — check whether its call
   site into `dispatch_spawn_record`-family logic uses a different base
   offset or record convention.
3. `ActorRecord`'s remaining unnamed blobs (`nUnk04`, `aUnk08`,
   `aUnk1c`, `aUnk24`, `bUnk2f`, `bUnk31`) — still blocked on live
   script byte-code data; now that we know the "intro" *is* live map-1
   gameplay, the same `prg2-ram.bin` dump likely already has an active
   `g_actor_table` slot with a real movement/animation script pointer —
   worth checking directly before assuming a fresh capture is needed.
   (See immediate follow-up below — checked this pass.)
4. Find the render/blit routines — still unexplored, deprioritized per
   the game-logic-only focus.

### Follow-up: live `g_actor_table` sample from the same dump (2026-09-14)

Acting on open item 3 above — checked `g_actor_table` (`$16b6a`,
`ActorRecord[6]`) in the same `prg2-ram.bin` dump before assuming a
fresh capture was needed, since we'd just confirmed this "intro" dump
is live map-1 gameplay. It paid off: **4 of 6 slots are active**
(slot 5 is the all-zero empty pattern; slot list below is 0-indexed).

**Occupancy test corrected.** All 4 active slots have `bState_flags`
(offset 0) equal to `0` — so `bState_flags` alone is *not* the
occupancy flag, contradicting the loose earlier phrasing ("free-slot
scanners only read `bState_flags`/`bBehavior_flags` to skip empty
slots"). Reading `dispatch_spawn_record`'s decompile precisely: it
loads `bState_flags` and `bBehavior_flags` together as one 16-bit word
and tests `!= 0`. So the real test is **"`bState_flags:bBehavior_flags`
as a combined 16-bit value is nonzero"** — in this sample every active
slot has a nonzero `bBehavior_flags` (`0x41`, `0xd5`, `0x11`, `0x49`,
`0x4d` across the 4 slots) carrying the whole test by itself, with
`bState_flags` at 0. Worth remembering next time `bState_flags` is
assumed to be a simple presence flag — it isn't, on its own.

**`nSecondary_data_ptr` confirmed pointing into the just-decoded spawn
table.** All 4 active actors' `nSecondary_data_ptr` (offset `0x2a`)
values land inside (or exactly at the base of) the `$54e11` spawn-table
region decoded above:

| Slot | `nSecondary_data_ptr` | Offset from `$54e11` |
|------|------------------------|------------------------|
| 0 | `$54e35` | `+0x24` (record 9) |
| 1 | `$54e25` | `+0x14` (record 5) |
| 3 | `$54e11` | `+0x00` (record 0, table base) |
| 4 | `$54e2d` | `+0x1c` (record 7) |

All four offsets fall within the confirmed-monotonic record run
(records 0-21) from the spawn-table decode above, not past it — solid
independent cross-validation that both the table's real memory location
*and* the record-0-through-21 boundary are correctly identified. This
matches the earlier hypothesis that an active enemy's
`nSecondary_data_ptr` is "this actor's own pointer *into* a spawn-style
record table" (each actor points at its own position within the shared
table, likely so it can re-trigger or hand off to nearby records as it
moves).

**Remaining unnamed `ActorRecord` bytes still unresolved.** `nUnk04`,
`aUnk08`, `aUnk1c`, `aUnk24`, `bUnk2f`, and `bUnk31` are `0` in **all 4**
live active slots in this sample — consistent with, but not proof of,
them being padding/dead. This is one real level's worth of early-game
enemies (map 1, ~20s into demo playback); doesn't rule out a
later-level or later-in-level enemy type writing these fields. Not
claiming these are dead — just noting the live sample didn't produce a
counterexample either.

### Ghidra annotations added this pass

None — same reasoning as above (this is level-instance data, not a
fixed symbol location).

### Updated open follow-ups

1. Determine the enemy-spawn table's actual length/terminator (unchanged
   from above).
2. Resolve the `_g_submap_trigger_table_ptr` decode inconsistency
   (unchanged from above).
3. `ActorRecord`'s remaining unnamed blobs (`nUnk04`, `aUnk08`,
   `aUnk1c`, `aUnk24`, `bUnk2f`, `bUnk31`) — now checked against one
   real live sample (4 active enemies, all zero in these fields); still
   open, would need either a later-level sample or a decoded
   move/anim-script byte-code stream that's confirmed to write to one
   of these offsets.
4. Correct the loose "free-slot scanners skip empty slots via
   `bState_flags`/`bBehavior_flags`" phrasing wherever it recurs
   earlier in this document to the precise test (combined 16-bit
   `bState_flags:bBehavior_flags != 0`) — cosmetic, not urgent.
5. Find the render/blit routines — still unexplored, deprioritized per
   the game-logic-only focus.

### Move/animation script opcode formats decoded byte-exact (2026-09-14)

With real script pointers in hand from slot 0 above
(`nMove_script_ptr` = `$53a82`, `nAnim_script_ptr` = `$534fe`), full
decompiles of the two generic interpreters (`advance_actor_move_script`
`$172fa`, `advance_actor_anim_script` `$171bc`) plus the real bytes at
both pointers give a complete, concrete opcode encoding — this was
previously described only at the "supports looping and embedded sound
triggers" level; now it's byte-exact.

**Movement script** — a flat stream of 4-byte records (`int16 count,
int8 dx, int8 dy`), each read via a `short*` cursor stored at
`nMove_script_ptr` (offset `0x16`):
- `count == 0`: end/loop marker — jump to `cursor + *(int16*)(cursor+2)`
  (a byte-address-relative signed offset stored in the record's last
  two bytes) and keep interpreting from there.
- `count == -1` (`0xffff`): conditional sound-effect marker — if
  `0x22 < nY < 0x149` (an onscreen-range test on the actor's own Y,
  *not* a call to `is_actor_onscreen`, contrary to the earlier
  description), calls `FUN_0001a6aa`; either way, skip the record and
  continue immediately (doesn't consume a movement frame).
- Otherwise: a real movement command — hold `count` frames applying
  `(dx, dy)` as the per-frame delta into `nMove_delta_x`/`nMove_delta_y`;
  `count` is stored into `nMove_script_counter` (offset `0x1a`) and
  decremented once per frame; only on reaching 0 does the cursor
  advance to the next record.

**Confirmed against slot 0's real script** (`00 08 08 00 | 00 18 00 00
| 00 08 f8 00 | 00 18 00 00 | 00 00 ff f0 ...`): `(8, +8, 0)` → hold 24
frames at `(0,0)` → `(8, -8, 0)` → hold 24 frames at `(0,0)` → loop
marker jumping back `-16` bytes to record 0 — a clean 64-frame
left-right patrol cycle, matching `nMove_script_counter = 6` in the
live slot (mid-way through the first 8-frame block). This is the first
byte-exact, independently-reconstructed enemy behavior in the project.

**Animation script** — a variable-length stream of `int16` cells (not
a fixed stride), cursor at `nAnim_script_ptr` (offset `0x1e`), gated by
`nAnim_hold_counter` (offset `0x22`, decremented once per call; the
cursor only advances once it reaches 0):
- Cell `>= 0`: an immediate frame index — store into `nAnim_frame`
  (offset `0xe`), advance 1 cell (2 bytes), done for this call.
- Cell `== -1` (`0xffff`): loop marker — jump to `cursor_byte_address +
  next_cell` (again a raw signed byte-address delta, same convention
  as the move script), then keep interpreting without returning.
- Cell `== -3` (`0xfffd`): conditional sound marker — same `0x22 < nY <
  0x149` onscreen-range test, calls `FUN_0001a6aa(0xfffd)` (passing the
  opcode value itself as the sound parameter); skip 2 cells (4 bytes,
  one of them unused padding) and continue.
- Any other negative value: a 3-cell hold record — next cell is the
  hold count (stored into `nAnim_hold_counter`, decremented once
  immediately), the cell after that is the frame index (stored into
  `nAnim_frame`); advance 3 cells (6 bytes), done for this call.

**Confirmed against slot 0's real script**: the first 6 cells are a
plain frame-flip sequence `91,92,89,90,91,92` (one frame change per
call — a 6-frame idle/walk cycle), then a hold record `(-2, hold=24,
frame=254)`, then a loop marker jumping 26 bytes backward (to a point
*before* our 32-byte read window — the script's real start is earlier
in memory than the address captured here, unsurprising since
`nAnim_script_ptr` reflects the cursor's *current* position, not the
script's base), then (from a second read further along) a sound
marker (`-3`) followed by a hold record `(-2, hold=26, frame=86)`.
Every opcode value observed matches the decompile's branch conditions
exactly — no unexplained bytes in either script sample.

**Practical takeaway for the mechanical-port goal**: both script VMs
are now fully specified at the opcode level with a real confirmed
example each. This — combined with the `ActorRecord` layout, the
dual-behavior-profile swap, and the spawn-table record format — means
enemy behavior is very close to portable end-to-end; the main remaining
piece is bulk-decoding every level's actual script/table *data* (this
pass validated the format against one enemy in map 1, not the full
game's content).

### Ghidra annotations added this pass

None yet — `FUN_0001a6aa` (the sound-trigger call in both scripts)
remains unrenamed; out of scope per the sound-engine exclusion, but
worth a plain `trigger_sound_effect`-style rename purely for
readability of the two script interpreters, without decoding its
parameter meaning.

### Updated open follow-ups

1. Determine the enemy-spawn table's actual length/terminator (unchanged).
2. Resolve the `_g_submap_trigger_table_ptr` decode inconsistency (unchanged).
3. `ActorRecord`'s remaining unnamed blobs — unchanged; the two script
   formats just decoded don't reference any of `nUnk04`, `aUnk08`,
   `aUnk1c`, `aUnk24`, `bUnk2f`, `bUnk31`, reinforcing (not proving)
   that they're unrelated to movement/animation scripting specifically.
4. Bulk-decode more of each level's actual script/table byte streams
   now that the exact grammar is known, to build real confidence beyond
   the single confirmed enemy instance in this pass.
5. Find the render/blit routines — still unexplored, deprioritized per
   the game-logic-only focus.

## Spawn-table record grammar corrected — header + variable detail blocks (2026-09-14)

The earlier "flat 4-byte record" decode of the spawn table (previous
section, above) was wrong about *segmentation*, even though most of
the individual field reads happened to still be meaningful. Decompiling
the actual table-walking driver, `scan_enemy_spawn_list` (`$14594`,
called from the level-tick path, one read xref to
`g_enemy_spawn_table_ptr` at `$145ae`), gives the real grammar:

```c
byte *pbVar3 = g_enemy_spawn_table_ptr;
for (; *pbVar3 != 0; pbVar3 += 4) {
    x = pbVar3[1] * 8;
    if (DAT_00016462 + 0x128 <= x) break;      // too far right of scroll — stop scanning for this tick
    if ((*pbVar3 & 0x80) == 0) {               // header not yet "done"
        if ((pbVar3[2] & 0x80) == 0) {
            dispatch_spawn_record();            // in_A0 = pbVar3 (the header itself)
            if (x < DAT_00016462 + 0x128) goto call_spawn;
        } else if (_DAT_00014592 != 0 ||
                   (short)(x - DAT_00016462) < 0x28 ||
                   0x10f < (short)(x - DAT_00016462)) {
call_spawn:
            FUN_00014636();                     // likely the real "instantiate actor" routine
        }
    }
    if ((pbVar3[3] & 3) != 0) {
        pbVar3 += (pbVar3[3] & 3) << 2;          // skip the header's own trailing detail blocks
    }
}
```

**Corrected record grammar**: each logical spawn-table entry is a
4-byte **header** —

| byte | meaning |
|---|---|
| 0 | nonzero = valid header (loop terminator when `0`); bit `0x80` = "already done" |
| 1 | X position `/8` (tile coordinate, same units used throughout) |
| 2 | bit `0x80` gates an alternate scroll-window condition vs. the direct-dispatch path |
| 3 | bits 0-1 = number of trailing 4-byte **detail** blocks (0-3); remaining bits unresolved |

— followed by exactly that many 4-byte **detail** blocks, each holding
the same fields `dispatch_spawn_record` was already known to read
relative to `in_A0+4`: byte1 = X-recheck, byte2 high nibble = width,
byte3 = the condition/action bitmask (`0x01,0x02,0x04,0x08,...,0x80`)
documented in the earlier pass. This is exactly why the two functions
looked like they disagreed about "current vs. next record" — they
don't disagree; `dispatch_spawn_record`'s `in_A0` *is* the header
`scan_enemy_spawn_list` just passed it, and its internal `+4` steps
into that header's own detail blocks, not an unrelated "next record."

**This resolves follow-up item 1**: the table terminator is
unambiguous — a header byte0 of `0x00` ends the table. Re-walking the
same 256-byte sample from `$54e11` with the corrected header+detail
segmentation (not a flat 4-byte stride) finds a clean run of 13
headers (with 0 or 1 detail blocks each, detail counts observed: 0 or 1
only, never 2 or 3 in this sample) followed by a terminator header
(`byte0==0`) at table offset `0x5c` — i.e. **this sample's table is
only 92 bytes long / 13 entries**, not the ~22 "records" the earlier
flat decode reported (that count conflated some detail blocks with
independent headers). X values across the 13 headers are still
monotonically non-decreasing (744 → 1120), consistent with the table
being sorted by X for the scan's early-exit `break`.

### Updated open follow-ups

1. ~~Determine the enemy-spawn table's actual length/terminator~~ —
   **resolved**: terminator is a header with byte0==0; real entries are
   variable-length (4 + 4×detail_count bytes), not flat 4-byte records.
2. ~~Resolve the `_g_submap_trigger_table_ptr` decode inconsistency~~ —
   **resolved**, see below.
3. Investigate the new globals/functions this decompile surfaced:
   `_g_screen_exit_trigger_flag` (gates the whole function at entry,
   tied to `g_actor_table[0]` being empty, calling `FUN_00015b3c()`) —
   still open. `FUN_00014636` is now decoded (see below); its four
   callees (`FUN_000146a0`, `FUN_00014862`, `FUN_000157be`,
   `FUN_000157f4`) are not yet decompiled.
4. `ActorRecord`'s remaining unnamed blobs (unchanged).
5. Bulk-decode more of each level's actual script/table byte streams,
   now using the *corrected* header+detail segmentation.
6. `func_0x00014434` (called from `check_submap_exit_triggers`'s
   "forced push" path) has no defined function boundary at all in
   Ghidra's analysis — likely explains what submap-trigger-table bytes
   2-3 are for; needs `create_function` + decompile.
7. Find the render/blit routines — still deprioritized, out of scope.

## Submap-trigger table format decoded; the "0 xrefs" mystery explained (2026-09-14)

Follow-up item 2 is resolved. `search_functions` for `trigger` turned up
an already-named function sitting immediately next to the suspect
label: `check_submap_exit_triggers` (`$14362`), 6 bytes before
`g_submap_trigger_table_ptr` (`$1435c`). Its decompile:

```c
undefined8 check_submap_exit_triggers(void)
{
    byte *pbVar1 = _g_submap_trigger_table_ptr;
    if (_g_current_submap_index == 0) return;
    do {
        if (*pbVar1 == 0) return;                       // terminator, same convention as spawn table
        if ((*pbVar1 & 3) == _g_current_submap_index &&
            (byte)((g_player_y + (DAT_00016462 & 0xfff8) + 0x14) >> 3) == pbVar1[1]) {
            _g_screen_exit_trigger_flag = (*pbVar1 & 0x40) != 0;
            if (sRam00017990 == 0) {
                if ((*pbVar1 & 0x90) != 0x90) goto forced_push;
            } else if ((*pbVar1 & 0x80) == 0) {
forced_push:
                _g_player_forced_push_flag = (*pbVar1 & 0x20) ? 0xffff : 0;
                func_0x00014434();
                return;
            }
            _g_submap_complete_flag = 0xffff;
            return;
        }
        pbVar1 += 4;
    } while (true);
}
```

**Table format** (4-byte records, terminator `byte0==0`, same
convention as the spawn table):

| byte | meaning |
|---|---|
| 0 bits 0-1 | target submap index (matched against `_g_current_submap_index`) |
| 0 bit `0x40` | sets `_g_screen_exit_trigger_flag` when the record matches |
| 0 bits `0x80`/`0x10` (mask `0x90`) + `sRam00017990` | selects "submap complete" vs. "forced push" outcome |
| 0 bit `0x20` | forced-push direction/flag value |
| 1 | trigger line, as a screen-relative, scroll-adjusted Y tile: `(player_y + (scroll & 0xfff8) + 0x14) >> 3` |
| 2-3 | **not read by this function** — likely consumed by `func_0x00014434` (the forced-push handler), which has no defined function boundary in Ghidra yet |

Note this table triggers on **Y position**, unlike the spawn table's
**X position** — consistent with submap transitions being vertical
(e.g. entering/exiting an underground room) rather than horizontal
scroll-driven spawns.

**Why `audit_global`/`get_xrefs_to` showed 0 xrefs despite this
function clearly reading it**: confirmed via `get_function_pcode` —
the low P-code for this function contains an explicit `COPY` op whose
input is `ram` space, offset `1435c`, size 4, at p-code address
`$14368`. The read is real and at the expected address; Ghidra's
auto-analysis simply never converted that absolute-addressing
instruction into a recorded memory reference (a gap in this dump's
analysis pass, not a mislabeled or dead symbol). `disassemble_function`
and `get_function_by_address` also report a degenerate 1-byte body for
this function despite the decompiler successfully walking well past
it — another symptom of the same incomplete analysis, harmless for
reading but worth a `create_function`/`reanalyze` pass if we want the
static tools (xrefs, disassembly listing) to work normally on it.

**`FUN_00014636` decoded** (the function `scan_enemy_spawn_list` calls
to actually instantiate an enemy from a matched spawn record):

```c
undefined4 FUN_00014636(void)
{
    byte bVar1 = *in_A0;              // detail block's own byte0 = enemy-type ID
    if (bVar1 == 0x78) FUN_000157be();
    else if (bVar1 == 0x7c) FUN_000157f4();
    else if (bVar1 != 0) {
        if (bVar1 < 0x75) FUN_000146a0();
        else FUN_00014862();
    }
    return in_D0;
}
```

This is an enemy-type-ID dispatcher: the detail block's byte0 (not yet
named/decoded as a distinct field before this pass) is an enemy-type
ID, routed into one of four construction routines by range/special-case
(`<0x75` / `>=0x75` / `==0x78` / `==0x7c`). This is very likely the
real "spawn record → live `ActorRecord`" boundary for the mechanical
port.

## Actor construction routines decoded — monster-type descriptor table found (2026-09-15)

Decompiled all four of `FUN_00014636`'s callees. `unaff_A6` in each is
a `ushort*` aliasing the freshly-allocated `ActorRecord` — the index
math (`unaff_A6[N]` = byte offset `N*2`) lines up exactly with the
existing struct layout and fills in several previously-unnamed fields.

**Detail-block field meanings, refined** (the 4-byte block read via
`in_A0`/`extraout_A0`, previously only byte3's bitmask was decoded):

| byte | meaning |
|---|---|
| 0 | enemy-type ID (dispatch key for `FUN_00014636`); OR'd with `0x80` after construction to mark "already spawned" |
| 1 | **Y** tile position: `nY = byte1*8 - (scroll & 0xfff8) + 3` |
| 2 | **X** sub-position: bits 0-4 `*8`, `+4` more if bit `0x20` set (a half-tile-alignment flag) |
| 3 | bit `0x80` → initial facing/flip flag (see below); bits `0x3c` feed into `bBehavior_flags` composition (type<0x75 path only) |

(This clarifies the earlier note that the *header's* byte1 is a
different, coarser X used only for the table-scan visibility/sort
test — the header and its detail block(s) carry independent
position fields for different purposes.)

**New `ActorRecord` field names** (all confirmed via the `unaff_A6[N]`
index arithmetic matching the existing offset table):

- `aUnk10` bytes 2-3 (offset 18, one 16-bit field) → **`nFacing_flag`**:
  `0xffff` if detail-block byte3 bit `0x80` set at spawn time, else `0`
  (both construction routines set it this way; `FUN_00015b3c`'s static
  actor init sets the equivalent bytes to `1` instead — a third
  distinct value, meaning this is likely a tri-state facing/subtype
  flag, not a plain boolean).
- `aUnk08` bytes 4-5 (offset 12) → constant `0x100` on spawn (type≥0x75
  path); bytes 2-3 (offset 10) → constant `2`. Purpose still unnamed,
  but now known to be *type-independent* spawn-time constants rather
  than per-type data.
- `nExplosion_done_flag` (offset 78) confirmed zeroed on spawn by both
  construction paths (already named; behavior now doubly confirmed).

**Monster-type descriptor table — `DAT_00053400`** (type<0x75 path,
`FUN_000146a0`, non-special-case branch): the type ID (`detail.byte0 &
0x7f`, minus 1) indexes a table of `int16` **self-relative offsets**:

```c
entry_addr = &DAT_00053400 + (type_id & 0x7f - 1) * 2;
pbVar5 /* descriptor */ = entry_addr + *(int16*)entry_addr;
```

`pbVar5` (the resolved descriptor) supplies, for that monster type:

| descriptor offset | meaning |
|---|---|
| 0 | `nWidth` (copied to `ActorRecord+0x26`) |
| 1 | `nHeight` (copied to `ActorRecord+0x28`) |
| 2 | behavior-flag bits — feeds both `bBehavior_flags` (`&0xc0`) and `bBehavior_flags_alt` (`<<2`, combined with detail-block byte3 bits) |
| +4 (int16, self-relative) | **primary** move-script pointer → `nMove_script_ptr` |
| +6 (int16, self-relative) | **primary** anim-script pointer → primed once via `advance_actor_anim_script()`, result stored to `nAnim_script_ptr` |
| +8 (int16, self-relative, off a second reference `extraout_A1` — likely the same descriptor, unconfirmed) | **alt** move-script pointer → `nMove_script_ptr_alt` |
| +10 (same) | **alt** anim-script pointer → `nAnim_script_ptr_alt` |

This is a strong, near-complete "monster type definition" record:
width, height, behavior bits, and *both* script-pointer pairs (primary
+ alt) that the previously-documented dual-behavior-profile swap
mechanic switches between. This is one of the most directly portable
pieces of data found so far — it's the natural place to source a
per-monster-type table in a reimplementation. Not yet fully closed:
whether `extraout_A1` (offsets +8/+10) is really the same `pbVar5`
descriptor or a distinct lookup — the decompiler's register-tracking
across the `advance_actor_anim_script()` call makes this ambiguous
without manual register tracing.

Two extra sub-cases in `FUN_000146a0` (monster-descriptor byte2 `&
0x3c == 0x20`, `== 0x28`, `== 0x2c`) skip the descriptor-table lookup
entirely and hardcode `nAnim_script_ptr` to one of two fixed pointers
(`&DAT_0001466e`, or `&DAT_0001468a` when `g_current_map_number == 4`)
— a map-4-specific enemy behavior swap, not yet investigated further.

**`FUN_00014862`** (type≥0x75 path) is the simpler construction
routine — no descriptor-table lookup; `bBehavior_flags` is set
directly from `type_id & 3`, and `nAnim_frame` (+ a mirrored copy at
`ActorRecord+0x3e`) comes from a tiny 4-entry lookup `DAT_00014854`
indexed by `type_id` bits 2-3. A sub-case (`type_id&3==1`) additionally
sets one `aUnk50` field (offset 84) from detail-block byte3.

**`FUN_000157be` / `FUN_000157f4`** (special-case IDs `0x78`/`0x7c`)
are one-shot global toggles, not real actor spawns: they flip a shared
flag `_DAT_000157ac` and fire a sound (`FUN_0001a6aa`) — `0x78` turns
it on (if currently off), `0x7c` turns it off (if currently on, via
`FUN_00017810()` first). Likely a boss-intro/screen-event trigger
pair rather than an enemy type; out of scope for further decoding
(sound-adjacent).

**`FUN_00015b3c`** (called from `scan_enemy_spawn_list`'s entry gate
when `_g_screen_exit_trigger_flag` is set and slot 0 is empty) is a
**static actor-table initializer**: it fills `g_actor_table` slots 0-4
from a small fixed source table at `DAT_0001586e` (packed
`{int32 posXY (X in high 16 bits, Y in low 16 bits); int32
animScriptPtr}` per entry, plus a move-script pointer read
immediately after priming the anim script once), then explicitly
zeroes slot 5 to an inactive/default state. This looks like a
"reset to this submap's canned default actors" routine, distinct from
the data-driven spawn-table path — plausibly what repopulates a
submap's fixed enemies when re-entering it. `DAT_00015b38`/
`DAT_00015b3a` (set to `0x14` and `0` respectively) are unexplored
counters, possibly a countdown/cooldown pair for this reset.

### Updated open follow-ups

1-2. Resolved (see prior sections).
3. `_g_screen_exit_trigger_flag` — now understood as the gate for
   `FUN_00015b3c`'s static-actor reset; `_DAT_00014592` still unnamed.
4. `ActorRecord`'s remaining unnamed blobs — narrowed further (see
   `nFacing_flag`, `aUnk08` constants above), but `aUnk3e`/`aUnk50`
   (minus the one `FUN_00014862` field) and `bUnk2f`/`bUnk31` are
   still open.
5. Bulk-decode more of each level's actual script/table byte streams.
6. ~~`func_0x00014434` has no defined function boundary~~ — **resolved**,
   see below; submap-trigger-table bytes 2-3 are *still* unexplained
   though (this function doesn't read them either).
7. Resolve whether `FUN_000146a0`'s `extraout_A1` (alt script offsets
   +8/+10) is the same descriptor as `pbVar5` or a separate lookup —
   needs manual register tracing, the decompiler is ambiguous here.
8. ~~Decode the monster-type descriptor table contents for real live
   type IDs~~ — **partially resolved**, see below: all 4 live actors
   turned out to use the simpler self-as-header/`FUN_00014862` path,
   so `FUN_000146a0`'s descriptor-table format is still unvalidated
   against real data.
9. Investigate the map-4-specific fixed anim-script pointers
   (`DAT_0001466e` / `DAT_0001468a`) and monster-descriptor byte2 values
   `0x20`/`0x28`/`0x2c` that trigger them.
10. Find the render/blit routines — still deprioritized, out of scope.
11. (new) Find a live example that exercises `dispatch_spawn_record`'s
    detail-block path and/or `FUN_000146a0`'s descriptor-table path —
    none of this dump's 4 live actors did (see below), so that whole
    code path is still unvalidated against real data.
12. (new) submap-trigger-table bytes 2-3 remain unexplained —
    `check_submap_exit_triggers`'s only helper, `FUN_00014434`, doesn't
    read them either. No other candidate reader found yet.

## Live actors cross-checked against corrected spawn-table segmentation — all 4 use the "self-as-header" path (2026-09-15)

Re-checked the 4 live actors' `nSecondary_data_ptr` values (recorded
2026-09-14, offsets `+0x00/+0x14/+0x1c/+0x24` from `$54e11`) against
the *corrected* header+detail segmentation from the section above.
All 4 land exactly on a **header** address (`0x00`, `0x14`, `0x1c`,
`0x24` are all header offsets in the corrected walk, not detail-block
offsets) — and every one of those headers has **both** `byte0 & 0x80`
and `byte2 & 0x80` set:

| Offset | Header bytes | byte0 done? | byte2 `0x80`? | detail_count | self type ID |
|---|---|---|---|---|---|
| `0x00` | `a6 5d c8 89` | yes | yes | 1 | `0xa6` |
| `0x14` | `8f 65 c0 55` | yes | yes | 1 | `0x8f` |
| `0x1c` | `92 6f 9d 4d` | yes | yes | 1 | `0x92` |
| `0x24` | `93 70 8a 80` | yes | yes | 0 | `0x93` |

This is a clean, fully self-consistent finding: all 4 actors were
spawned via the **"self-as-header"** branch of `scan_enemy_spawn_list`
(header `byte2 & 0x80` set → `FUN_00014636` called directly on the
header, using the header's own byte0 as the type ID) rather than
through `dispatch_spawn_record`'s detail-block mechanism. All 4 type
IDs (`0xa6`, `0x8f`, `0x92`, `0x93`) are `>= 0x75` and not `0x78`/
`0x7c`, so all 4 constructed via the simpler `FUN_00014862` path — and
the header's own `byte0 & 0x80` being set in every case is exactly the
"already spawned" marker that construction OR's onto its source
record. This validates the self-as-header/`FUN_00014862` path
end-to-end against real live data.

**Left unvalidated by this sample**: three of these four headers
(`0x00`, `0x14`, `0x1c`) *do* have a trailing detail block
(`detail_count=1`), but since they took the `byte2&0x80` branch,
`dispatch_spawn_record` (which only runs when `byte2&0x80==0`) never
touched those detail blocks in this sample — leaving open whether
those detail blocks are simply unused padding for `byte2&0x80`
headers, or consumed by some other code path not yet traced. Also
still unvalidated: `FUN_000146a0`'s descriptor-table path (type
`<0x75`) — no live actor in this sample had a type ID below `0x75`.

## `FUN_00014434` decoded — this *is* the submap-transition teleport (2026-09-15)

Gave it a real function boundary (`create_function`) since Ghidra had
never defined one despite `check_submap_exit_triggers` calling it.
Decompile:

```c
void FUN_00014434(void)
{
    if (g_player_x == 0) { g_player_x = 0xe8; FUN_00018abe(); }
    else                 { g_player_x = 0;    FUN_00018bb2(); }
}
```

This is the actual "forced push" effect referenced in the submap-
trigger-table decode: teleporting the player's X position between `0`
and `0xe8` (232) — i.e. wrapping them to the opposite horizontal edge
of the screen on a submap transition (classic room-to-room "walk off
one side, appear on the other" screen change). `FUN_00018abe`/
`FUN_00018bb2` (called after each half of the toggle) are presumably
the actual submap-load/scroll-reset pair — not decompiled this pass.
Notably, this function reads none of the trigger-table's bytes 2-3,
so that part of the table's format is still unexplained; no other
caller of the table has surfaced yet.

## Register-level trace of `FUN_000146a0`'s `extraout_A1` (2026-09-15)

Partial progress on follow-up 7. Dumped `FUN_000146a0`'s raw P-code
(`get_function_pcode`) and confirmed `unaff_A6` = register offset `38`
and the `extraout_A1` used for the alt-script-pointer reads (`+8`,
`+10`) = register offset `24`. Traced every write to register `24`
within the function and its one callee, `FUN_00014962` (the initial
helper, which turned out to be a **free-`ActorRecord`-slot scanner**
over `g_actor_table`, stepping by `0x58` (88) bytes per slot — a nice
independent confirmation of `sizeof(ActorRecord) == 88`, matching the
existing struct layout exactly): **register 24 is never written in
either function.** It's a genuine live-in value, inherited unchanged
from whatever the caller (`FUN_00014636`, or further up,
`scan_enemy_spawn_list`/`dispatch_spawn_record`) last put there.
Resolving what it actually points at requires dumping *those*
callers' P-code and tracing register 24 further up the chain — not
done yet, still open. Best guess, unconfirmed: given the surrounding
code's conventions (A0 = "current record pointer" throughout this
whole subsystem), A1 may be a second, longer-lived "current monster
descriptor" register set once per dispatch and reused across the
primary/alt script-pointer reads — but this is speculation pending the
actual trace.

### Updated open follow-ups

7. `extraout_A1` provenance — traced two more call-chain levels
   (`FUN_00014636`, `scan_enemy_spawn_list`): register 24 is unwritten
   in either. Three consecutive functions with no assignment is a
   strong signal this is a **decompiler register-tracking artifact**
   (stale/misattributed register under Ghidra's non-standard-ABI
   model for this whole subsystem, same family of issue as the
   `unaff_A6` naming) rather than real intentional data flow.
   Deprioritized — further tracing has hit diminishing returns; the
   `FUN_000146a0` alt-script-pointer read (`+8`/`+10` off some pointer)
   is still believed correct, just its *source* register's provenance
   is unresolved and likely unresolvable without the real disassembly
   listing (which Ghidra can't produce for this function either, same
   "empty disassemble_function" symptom seen on
   `check_submap_exit_triggers`).

## `_DAT_00014592` resolved — submap-transition force-scan flag (2026-09-15)

Follow-up (part of item 3) resolved. `get_xrefs_to` on `$14592` shows
5 xrefs: one read (`scan_enemy_spawn_list`, the alternate-window gate
already documented) and 4 writes, all inside `FUN_00018abe` and
`FUN_00018bb2` — exactly the two functions `FUN_00014434` (the submap
"forced push" teleport) calls. Both are near-identical "load new
submap" sequences (mirror images for the two transition directions):

```c
void FUN_00018abe(void)   // and FUN_00018bb2, near-identical
{
    advance_background_anim_counter();
    _DAT_0001695a = 0;  _g_camera_scroll_active = 0;
    FUN_000170b6();
    _DAT_0001695a = 1;  g_fallobj_state = 0;
    FUN_00014458(); func_0x00016474(); FUN_000188d0();
    FUN_000157b4(); FUN_000149c2(); FUN_00014542();
    _DAT_00014592 = 0xffff;
    scan_enemy_spawn_list();     // <-- one-shot enemy seed for the new submap
    _DAT_00014592 = 0;
    FUN_0001709e();
    wait_for_vblank(); FUN_000191e6();
    DAT_00018ed8 = 1;
    do {
        FUN_00018b5c();           // (FUN_00018c50 in the other variant) — screen transition anim, presumably
        wait_for_vblank();
    } while (FUN_000191e6() != 0);
    DAT_00018ed8 = 2;
    FUN_00016630();
}
```

So `_DAT_00014592` is a **"submap transition in progress" flag**,
set for exactly the duration of one `scan_enemy_spawn_list()` call:
its only reader is the alternate-window branch in
`scan_enemy_spawn_list`, where it forces spawn processing regardless
of the normal narrow `0x28`-`0x10f` scroll-delta gate — i.e. during a
submap load, the game needs to seed *all* relevant enemies for the new
screen in one pass, rather than relying on the gradual frame-by-frame
scroll-driven trigger. Outside of a submap transition it's always `0`
(confirmed: `0000` in the live dump), so the narrow-window gate applies
normally during regular gameplay.

This also gives a first real picture of the overall submap-transition
sequence (background/scroll/fall-state resets, one spawn-list seed
call, then a `wait_for_vblank` loop driving a transition animation
until `FUN_000191e6` signals completion) — none of the other called
helpers (`FUN_000170b6`, `FUN_00014458`, `func_0x00016474`,
`FUN_000188d0`, `FUN_000157b4`, `FUN_00014542`, `FUN_0001709e`,
`FUN_00018b5c`/`FUN_00018c50`, `FUN_000191e6`, `FUN_00016630`) have
been decompiled — flagged as a group for a future pass if the
mechanical port needs the transition sequence in detail, but
individually lower-priority than the spawn/table work already done.

## `_g_screen_exit_trigger_flag` resolved — real address `$144c2`, and its full read-side picture (2026-09-15)

Follow-up item 3 fully resolved. My initial guess that this flag lived
at `$14590` (naming/proximity guess, next to `scan_enemy_spawn_list`'s
entry at `$14594`) was wrong — `get_xrefs_to(0x14590)` came back empty.
Re-derived the real address directly from `scan_enemy_spawn_list`'s own
already-saved P-code instead of guessing again:

```
00014594 INT_NOTEQUAL ['ram:144c2(sz2)', 'const:0(sz2)'] -> register:45(sz1)
0001459a CBRANCH ['ram:145aa(sz1)', 'register:45(sz1)'] -> None
```

`$144c2` is the real address. `audit_global(0x144c2)` confirms Ghidra
already privately knows this symbol as `g_screen_exit_trigger_flag`
(4 xrefs) even though `list_globals(name_substring="screen_exit_trigger")`
returned nothing — a **third** instance of the same `list_globals`/
`get_xrefs_to`-unreliable-for-this-symbol-class pattern already
documented for `g_submap_trigger_table_ptr` and (initially) for this
flag's own wrong-address guess. `get_xrefs_to` on the *correct* address
works fine and lists all 4 real references:

| Site | Access | Role |
|---|---|---|
| `scan_enemy_spawn_list` @`14594` | READ | entry gate |
| `update_actor_slots` @`14d48` | READ | entry gate |
| `handle_screen_edge_and_respawn` @`15bc0` | READ | entry gate |
| `handle_screen_edge_and_respawn` @`15cd2` | WRITE (`=0`) | clears flag at end of transition |

(The *setter*, `=0xffff`ish via trigger-table byte0 bit `0x40`, is in
`check_submap_exit_triggers` — already documented — but doesn't show up
in this xref list, presumably the same indexing-gap pattern; not
re-verified since the write side was already independently confirmed
via that function's own P-code.)

This flag is the **screen-exit-transition-in-progress gate**, and the
three readers form a clean, consistent picture:

- `update_actor_slots` — skips the *entire* per-actor AI-update loop
  (all 6 slots) while the flag is set:
  ```c
  void update_actor_slots(void) {
      if (_g_screen_exit_trigger_flag == 0) {
          // ... normal loop calling update_actor_ai() for each
          //     live slot (bState_flags:bBehavior_flags != 0) ...
      }
      // else: do nothing — game logic frozen during the transition
  }
  ```
- `scan_enemy_spawn_list` — same polarity: normal spawn-table scanning
  is presumably skipped/altered while set (entry gate at `14594`
  matches this function's already-documented behavior; consistent with
  freezing normal spawn logic during the transition).
- `handle_screen_edge_and_respawn` — the **inverse** gate: this whole
  function is a no-op *unless* the flag is set (`if (flag==0) return`).
  This is the dedicated handler that actually runs the transition:
  moves all 5 main actors by a delta from `FUN_0001726e()`, advances
  their anim scripts, runs two `check_box_vs_player` collision checks
  (setting `_g_player_death_trigger` on a hit), fires
  `spawn_trigger_variant_a()`/`spawn_trigger_if_falling()` checks, and
  once a completion condition is met (`LAB_00015cc8`): clears the flag
  (`=0`), **re-initializes all 5 main actor slots** to a fresh state
  (`bBehavior_flags=0x11`, `bSubstate_flags=0x60`, fresh anim/move
  script pointers from a table at `PTR_DAT_00015a2c`, mirroring but not
  identical to `FUN_00015b3c`'s own reset block), resets several
  scroll/camera globals (`DAT_000167e0`/`f0`/`b4`/`c4`/`aa`/`ae`/`ac`),
  and calls `FUN_0001a6aa()`.

So the overall mechanism: `check_submap_exit_triggers` sets the flag
when the player crosses a trigger line with byte0 bit `0x40` set →
normal AI/spawn processing freezes (`update_actor_slots`,
`scan_enemy_spawn_list`) → `handle_screen_edge_and_respawn` runs the
actual transition (actor repositioning, collision/death checks, new
enemy-trigger spawns) every frame until its completion condition fires
→ it clears the flag and resets the 5 main actors for the new screen →
normal processing resumes next frame. This is a distinct, narrower
mechanism from the `FUN_00014434`/`_DAT_00014592` submap-*load*
teleport already documented — that one is the abrupt room-to-room
"walk off one edge" case; this one looks like the softer in-screen
"boss/star exit sequence" case (collision/death checks + a fresh actor
reset strongly suggest an end-of-level or end-of-set-piece cutscene).
Not decompiled this pass (flagged for later, lower priority): `FUN_0001726e`,
`check_box_vs_player`, `spawn_trigger_variant_a`, `spawn_trigger_if_falling`,
`FUN_00015eca`, `FUN_00017810`, `FUN_0001a6aa`, `FUN_00015d84`, `FUN_00015e48`.

### Updated open follow-ups

3. ~~`_g_screen_exit_trigger_flag`~~ — **resolved**, see above: real
   address `$144c2`, full 3-reader/1-writer picture documented.
   `_DAT_00014592` (the separate submap-*load* flag) was already
   resolved in the prior section.

## Per-level table loader decoded (`FUN_00014458`) — real name `g_enemy_spawn_table_ptr` found, item 12 resolved (2026-09-15)

While re-checking follow-up 12 (trigger-table bytes 2-3), re-confirmed
via `decompile_function` that `check_submap_exit_triggers` genuinely
never touches `pbVar1[2]`/`pbVar1[3]` — only `*pbVar1` (byte0) and
`pbVar1[1]` (byte1). Then found `g_submap_trigger_table_ptr`'s only
*writer*, `FUN_00014458`, which turned out to be the **per-level/
per-submap table loader**, called only from `FUN_00018abe`/
`FUN_00018bb2` (the submap-load routines, confirmed via
`get_xrefs_to`):

```c
void FUN_00014458(void)      // in_D0w = level/submap index
{
    short sVar1 = in_D0w << 3;                 // 8-byte record per level
    _LAB_0001646a = *(ushort*)(&DAT_00054c00 + sVar1) + 0x56400;  // bg gfx ptr (rendering, out of scope)
    _LAB_00016464_2 = 0;
    _LAB_00016468 = *(short*)(&DAT_00054c02 + sVar1) << 3;        // Y offset
    g_submap_trigger_table_ptr = &DAT_00054c00 + *(ushort*)(&DAT_00054c04 + sVar1);
    PTR_DAT_000144c4       /* = g_enemy_spawn_table_ptr's storage cell */
                            = &DAT_00054c00 + *(ushort*)(&DAT_00054c06 + sVar1);
    DAT_00016462 = in_D1w;   // scroll/camera-X (see below)
    _LAB_00016464 = in_D0w;  // stash the level index itself
    FUN_0001300e();          // rendering-related, not decoded
    FUN_00018516();          // rendering-related, not decoded
}
```

So each level/submap has an **8-byte header record** at
`DAT_00054c00 + level_index*8`: `+0`=background-gfx pointer offset
(rendering, out of scope), `+2`=a Y offset (`*8`), `+4`=offset to that
level's **submap-trigger table**, `+6`=offset to that level's
**enemy-spawn table**. This is the real per-level table-selection
mechanism — confirms the trigger/spawn tables are genuinely per-level
data, addressed by a shared small per-level header block, not global
singletons.

The storage cell at `$144c4` (`PTR_DAT_000144c4`) turned out to have a
real Ghidra name after all: **`g_enemy_spawn_table_ptr`** — read by
`FUN_00014542`, which decompiles to:

```c
void FUN_00014542(void)
{
    g_enemy_spawn_table_ptr = PTR_DAT_000144c4;
    if (g_enemy_spawn_table_ptr != NULL) {
        while (*g_enemy_spawn_table_ptr != 0 &&
               (short)(g_enemy_spawn_table_ptr[1] * 8) < DAT_00016462) {
            if ((g_enemy_spawn_table_ptr[3] & 3) != 0)
                g_enemy_spawn_table_ptr += ((g_enemy_spawn_table_ptr[3] & 3) << 2);
            g_enemy_spawn_table_ptr += 4;
        }
    }
}
```

This is a clean **independent re-confirmation of the header+detail-
block grammar** already documented for `scan_enemy_spawn_list`: it
walks the same header stride (4 bytes + `(byte3&3)*4` extra for
trailing detail blocks) and uses the same byte1-as-X8/byte3-bits0-1-
as-detail-count fields. Its purpose: called during submap load (from
`FUN_00018abe`/`FUN_00018bb2`, alongside `FUN_00014458` and the
already-documented `scan_enemy_spawn_list` seed call) to **fast-
forward the spawn-table read cursor past every header whose position
is already behind the initial scroll threshold** (`DAT_00016462`) —
i.e. skip enemies that would already be off the left edge of the new
screen, rather than spawning-then-immediately-culling them.

Also confirms `DAT_00016462`'s identity: it's read by `scan_enemy_spawn_list`,
`FUN_000146a0`, `FUN_00014862`, `dispatch_spawn_record`, and others —
exactly the address behind the informally-named "`scroll`" value used
throughout this doc's earlier field-offset formulas (e.g.
`nY = byte1*8 - (scroll & 0xfff8) + 3`). `DAT_00016462` = **the real
address of the scroll/camera-X global**, set here from `FUN_00014458`'s
`in_D1w` parameter at level-load time.

**Follow-up item 12 resolved**: no reader for the trigger table's
bytes 2-3 exists anywhere in the game-logic call graph reachable from
`check_submap_exit_triggers`/`FUN_00014434`/`FUN_00014458`/
`FUN_00014542`. Concluding these two bytes are either unused padding
(kept for record-size alignment / editor convenience) or consumed only
by a rendering-side subsystem (e.g. an on-screen door/exit graphic) —
out of scope either way. Not investigating further.

**SUPERSEDED 2026-09-22 — corrected in `kb2/xrick2-ref.md`, found by a
documentation sweep**: this conclusion is wrong, not just unconfirmed.
Re-disassembling `check_submap_exit_triggers` (`$14362`) directly shows
byte 2 (`move.b (0x2,A0),D0b`) and byte 3 (`move.b (0x3,A0),D1b`, shifted
and combined with the scroll/Y term) both moved into D0/D1 and passed to
`bsr $14434`, which uses them as the target submap and target row
(`level-tables.md` §2, `algo-flow.md` §9). The call-graph search here
evidently didn't reach `$14434` itself — a tooling/coverage miss, not a
fact about the code.

### Updated open follow-ups

12. ~~submap-trigger-table bytes 2-3~~ — was marked "resolved (as
    'no game-logic reader exists')"; **that resolution was wrong**, see
    the SUPERSEDED note above — bytes 2/3 are the target submap/row,
    consumed by `$14434`.

## `FUN_000146a0` fully decoded — detail-block `byte3&0x3c` switch resolves items 7 and 9 (2026-09-15)

Full decompile of the descriptor-table construction path (previously
only partially transcribed). The dispatch on the detail block's byte3
(`extraout_A0[3] & 0x3c`) is a real 4-way switch, not just a bitfield
feeding `bBehavior_flags`:

```c
bVar2 = extraout_A0[3] & 0x3c;
if (bVar2 == 0x20) {
    actor->nMove_script_ptr = &DAT_0001466e;
    if (g_current_map_number == 4) actor->nMove_script_ptr = &DAT_0001468a;
    actor->fieldAt7 = 0x40;
    // ... common tail (nAnim_hold_counter etc. zeroed) ...
} else if (bVar2 == 0x28) {
    actor->nMove_script_ptr = 0; actor->nMove_script_ptr_hi = 0;
    actor->fieldAt7 = 0x27;
    // ... common tail ...
} else if (bVar2 == 0x2c) {
    actor->nMove_script_ptr = 0; actor->nMove_script_ptr_hi = 0;
    actor->fieldAt7 = 0x28;
    // ... common tail ...
} else {
    // the real descriptor-table lookup path (DAT_00053400, self-relative
    // offset by (type_id&0x7f)-1) — already documented; pbVar5 = descriptor addr
    pbVar5 = descriptor_addr;
    actor->nWidth  = pbVar5[0];
    actor->nHeight = pbVar5[1];
    if ((extraout_A0[3] & 0x3c) == 0x10) {
        actor->nFacing_flag = 0x60;
        if (extraout_A0[3] & 0x40) { actor->aUnk15[0]=0; actor->aUnk15[1]=0; }
    }
    // primary + alt move/anim script pointers from pbVar5+4/+6 and
    // extraout_A1+8/+10 (see below) ...
}
```

**Item 9 resolved**: `DAT_0001466e`/`DAT_0001468a` are **fixed, hard-
coded move-script pointers** substituted whenever a detail block's
byte3 masked with `0x3c` equals `0x20` — completely bypassing the
per-type descriptor-table lookup. The only condition selecting between
the two is `g_current_map_number == 4`: every level uses
`DAT_0001466e` except map 4, which uses `DAT_0001468a` instead. This
reads exactly like a shared "elevator/moving-platform" or similarly
map-generic actor behavior script, with map 4 alone needing a
different variant (e.g. a different platform travel distance/tile
geometry on that level). `0x28`/`0x2c` are two more special cases in
the same switch, both **nulling** the move-script pointer pair instead
(`fieldAt7` set to `0x27`/`0x28` respectively — likely distinct
"static/no-movement" sub-behavior IDs) — i.e. certain detail-block
byte3 values mean "this actor has no move script at all," probably for
purely-decorative or trigger-only spawn entries. None of these three
special cases touch the descriptor table, so they apply uniformly
regardless of the detail block's type-ID byte.

**Item 7 (partially re-opened, now resolved by inference)**: in the
default (descriptor-table) branch, the alt-script-pointer computation
```c
*(int *)(unaff_A6 + 0x19) = extraout_A1 + *(short *)(extraout_A1 + 8);
*(int *)(unaff_A6 + 0x1b) = extraout_A1 + *(short *)(extraout_A1 + 10);
```
is structurally identical to the primary-script computation done two
lines earlier using `pbVar5` (`pbVar5 + *(short*)(pbVar5+4)`,
`pbVar5 + *(short*)(pbVar5+6)`) — same self-relative-pointer idiom,
same base. There is no code between the `pbVar5` assignment and the
`extraout_A1` uses that could plausibly reload a *different* pointer
into that register (only field writes and one call to
`advance_actor_anim_script()`, which per the 68k calling convention
used throughout this binary does not clobber address registers other
than scratch ones already accounted for elsewhere). Concluding
`extraout_A1` **is** `pbVar5` — the decompiler simply lost track of
the register's continuity across the call and re-synthesized it as a
fresh `extraout` variable. So: primary scripts = descriptor+4/+6,
alt scripts = descriptor+8/+10, **both pairs read from the same single
descriptor pointer**, exactly as originally guessed before the register
trace, now confirmed by decompile structure rather than raw register
provenance (which remains formally untraceable in the P-code, as
previously found — but no longer needed to reach this conclusion).

### Updated open follow-ups

7. ~~`extraout_A1` provenance~~ — **resolved by decompile-structure
   inference**, see above: `extraout_A1 == pbVar5`, the single
   monster-descriptor pointer, reused for both primary (+4/+6) and alt
   (+8/+10) script-pointer pairs.
9. ~~Map-4-specific fixed anim pointers / descriptor byte2 special
   values~~ — **resolved**, see above: it's a detail-block `byte3&0x3c`
   4-way switch (`0x20`=fixed map-conditional move script,
   `0x28`/`0x2c`=null move script, default=descriptor-table lookup),
   not a byte2 special case.

## `FUN_00014862` fully decoded — resolves most of `ActorRecord`'s remaining unnamed fields (item 4) (2026-09-15)

Full decompile of the simpler ("self-as-header", type `>=0x75`)
construction routine, indexing `unaff_A6` as a `ushort*` so
`unaff_A6[N]` = byte offset `N*2` into the 88-byte record. Converting
every write to byte offsets against the existing struct table:

```c
unaff_A6[0x26] = 0;   // byte 0x4c  — zeroed at spawn
unaff_A6[0x27] = 0;   // byte 0x4e  — explosion_done_flag, already named; confirmed zeroed at spawn
unaff_A6[0]    = header.byte0 & 3;          // byte 0x00 — state_flags/type word, low 2 bits of type ID
unaff_A6[7]    = DAT_00014854[(header.byte0 & 0xc) - 4) >> 1];  // byte 0x0e — anim_frame, initial value from a small 4-entry LUT keyed by type bits 2-3
unaff_A6[0x1f] = <same LUT value>;          // byte 0x3e — mirrors anim_frame's spawn-time initial value
if ((header.byte0 & 3) == 1) {              // only for type-category 1
    unaff_A6[0x2a] = (detail.byte3 & 0x3c) * 2 + 8;  // byte 0x54 — derived per-type-1 value
    unaff_A6[0x29] = 0;                              // byte 0x52
}
unaff_A6[4]  = 0;      // byte 0x08
unaff_A6[6]  = 0x100;   // byte 0x0c  — non-zero init constant
unaff_A6[5]  = 2;       // byte 0x0a  — non-zero init constant
unaff_A6[0x21] = 0;     // byte 0x42
unaff_A6[0x22] = 0;     // byte 0x44
unaff_A6[0x23] = 0;     // byte 0x46
unaff_A6[0x24] = 0;     // byte 0x48
unaff_A6[0x28] = 0;     // byte 0x50
unaff_A6[0x25] = 0;     // byte 0x4a
unaff_A6[0x2b] = 0;     // byte 0x56
unaff_A6[1] = (detail.byte2 & 0x1f)*8 + ((detail.byte2 & 0x20) ? 4 : 0);       // byte 0x02 — x, already named
unaff_A6[3] = detail.byte1*8 - (scroll & 0xfff8) + 3;                          // byte 0x06 — y, already named
unaff_A6[8]  = 0;       // byte 0x10
unaff_A6[10] = 0;       // byte 0x14
unaff_A6[9]  = (detail.byte3 & 0x80) ? 0xffff : 0;   // byte 0x12 — nFacing_flag, already named
unaff_A6[0x15] = extraout_A0;   // byte 0x2a — secondary_data_ptr, already named: set to *its own* spawn-record pointer
*extraout_A0 |= 0x80;           // marks the source header/detail byte0 "already spawned"
```

This resolves a good chunk of the previously-"unreferenced" struct
ranges, all as **spawn-time initialization**, which is exactly why
`update_actor_ai`/`query_tile_and_actor_collision`'s disassembly never
touched them — they're written once at construction and apparently
never read again by the two functions disassembled so far:

- byte `0x08` = 0, byte `0x0a` = **2**, byte `0x0c` = **0x100** — three
  of the six "unknown `0x08`-`0x0d`" bytes, two with distinctive
  non-zero constants (worth checking against `update_actor_ai` for a
  read later — these look like real counters/thresholds, not padding).
- byte `0x10` and `0x14` (within the `0x10`-`0x15` range that also
  contains `nFacing_flag` at `0x12`) = always zeroed at spawn.
- byte `0x3e` (start of the "unknown `0x3e`-`0x4d`" range) = a spawn-
  time **copy of the initial `anim_frame` value** — tentatively
  `nSpawn_anim_frame` (candidate name, unconfirmed usage elsewhere).
- bytes `0x42`, `0x44`, `0x46`, `0x48`, `0x4a` = always zeroed at spawn
  (still unnamed — no distinguishing computed value, likely per-type
  runtime scratch state initialized to a neutral value).
- byte `0x4c` = always zeroed at spawn (adjacent to
  `explosion_done_flag` at `0x4e`).
- bytes `0x50`, `0x52`, `0x56` (within the "unknown `0x50`-`0x57`"
  range) = always zeroed at spawn.
- byte `0x54` = **the one genuinely interesting field**: only written
  for type-category `header.byte0 & 3 == 1`, computed as
  `(detail.byte3 & 0x3c) * 2 + 8` — a real derived per-type-1 value
  (candidate: a hit-point count, an attack-cooldown period, or a
  death-animation duration; needs a live type-1 sample or the
  `FUN_00014636`-family AI code that reads offset `0x54` to pin down
  which).

**Still genuinely unresolved** (not written at all by this
construction routine — either padding, or written by a different
construction path such as `FUN_000146a0`'s descriptor-table branch,
`dispatch_spawn_record`, or the fixed-actor resets): byte `0x2f`, byte
`0x31`, and the exact purpose of the always-zeroed bytes listed above
beyond "spawn-time init." `DAT_00014854`'s 4-entry LUT (keyed by type
bits `0x0c`) is itself new and undecoded — likely small per-type-
category initial-frame values, low priority.

### Updated open follow-ups

4. `ActorRecord`'s remaining unnamed fields — **substantially
   narrowed**, see above: most of the `0x3e`-`0x4d`/`0x50`-`0x57`
   ranges are now known to be spawn-time-zeroed scratch fields (not
   fully named, but no longer mysterious), byte `0x0c`/`0x0a` carry
   real non-zero init constants worth checking for readers, and byte
   `0x54` is a genuine derived per-type-1 value. Only `0x2f`/`0x31`
   remain completely untouched by every construction routine seen so
   far. (Also not touched by `update_actor_ai`/`FUN_00014a12` — see
   below — so still fully open; likely written only by
   `dispatch_spawn_record`-family or `FUN_000146a0`'s uncommon
   type-branches, still not checked line-by-line for those two bytes
   specifically.)

## `FUN_00014a12` and `dispatch_spawn_record` decoded — de-spawn tail call and the trigger-detail-block bitmask (2026-09-15)

Decompiled `update_actor_ai`'s common tail call, `FUN_00014a12`
(reached via `LAB_00015096` from several paths): it's the **actor
de-spawn/reset routine** —

```c
void FUN_00014a12(void) {
    if (actor->state_flags != 0) {           // word offset 0, i.e. bytes 0x00-0x01
        actor->state_flags = 0;                // deactivate this slot
        secondary = actor->secondary_data_ptr; // 0x2a
        if (secondary != NULL && (secondary_detail.byte3 & 0x40) == 0) {
            secondary_header.byte0 &= 0x7f;      // clear "already spawned" bit
        }
    }
}
```

So killing/deactivating an actor also **un-marks its source spawn
record** (clears header/detail `byte0 & 0x80`) so it can be
re-triggered later on a future scroll pass — *unless* the record's own
detail byte3 bit `0x40` is set, which now reads as a genuine **"one-
shot: never respawn after being killed"** flag (distinct from the
already-documented byte3 bits `0x80`/`0x3c`/`0x20` interpretations
used by the *other* construction path).

Also fully decompiled `dispatch_spawn_record` (previously only
partially transcribed, flagged as "richer than described"). It turns
out this is **not** a monster-construction routine at all in the sense
`FUN_00014636`'s family is — it's a **trigger/effect-box dispatcher**
operating on the header's *own* trailing detail blocks (the ones a
`byte2&0x80==0` header can own, per the corrected spawn-table grammar).
For each detail block (up to the header's `byte3&3` count):

- A visibility/position gate first (`detail.byte1*8 - scroll`,
  height-adjusted by `detail.byte2>>4`) — if the block is fully
  off-screen, its own `byte3 & 0x80` "already processed" bit is
  cleared (allowing re-arming once it scrolls back into range) and
  nothing else happens this pass.
- Otherwise, **the detail block's `byte3` is read as a bitmask of
  independent trigger conditions to test**, each guarding a call to a
  different check/spawn helper:
  - `0x01` → `check_box_vs_player()` — box-vs-Rick collision
  - `0x02` → `spawn_trigger_variant_a()`, and on success sets
    `_DAT_000115dc = 0xffff` (a new, unexplored global — a trigger
    flag of some kind)
  - `0x04` → `spawn_trigger_if_falling()`
  - `0x08` → `spawn_trigger_variant_c()`
  - `0x10` → `check_box_vs_object_slot()` against a **4-slot table at
    `PTR_LAB_000167a2`**, stride `0x58` — the exact `ActorRecord`
    layout/size. This table was already seen being *written* in
    `handle_screen_edge_and_respawn` (`PTR_LAB_000167a2._0_2_=1;
    ..._2_2_=g_actor_table[0].nX; ...`, i.e. slot 0's `state_flags=1`,
    `x`/`y` copied from the main actor 0) — strongly suggesting this is
    a **separate small "object/projectile" actor table**, distinct
    from the 6-slot `g_actor_table`, tentatively `g_object_table`
    (unconfirmed name/address beyond `$167a2`; not yet investigated as
    its own struct).
  - `0x20` → `check_box_vs_actor()` against the main `g_actor_table`
    (slots 0-5)
  - `0x40` → if the tested condition fired, **suppress** the
    `FUN_0001a6aa()` effect call (a "silent"/no-effect trigger variant)
  - `0x80` → "already processed" marker, same convention as the header/
    detail `byte0` bit throughout this whole subsystem

This is a completely different *use* of the same byte3 bit-position
than `FUN_000146a0`/`FUN_00014862`'s "spawn-type" detail blocks — makes
sense, since these are two different *kinds* of table entries walked
by two different header branches (`byte2&0x80==0` → trigger/effect
records via `dispatch_spawn_record`; `byte2&0x80!=0` → monster-spawn
records via `FUN_00014636`). The table's 4-byte record grammar (header
+ variable detail blocks) is shared, but each branch's detail-block
`byte3` is a *locally*-scoped bitfield with a completely different
meaning. Worth flagging explicitly in the struct/table docs so a
future port doesn't conflate the two.

**New unexplored global noted in passing**: `_DAT_000115dc` (set to
`0xffff` on a `spawn_trigger_variant_a()` hit) — not investigated.

### Updated open follow-ups

13. (new) `g_object_table` (tentative name, `$167a2`, 4×`0x58`-byte
    `ActorRecord`-shaped slots) — a probable secondary actor table for
    projectiles/objects, discovered via `dispatch_spawn_record`'s
    `byte3&0x10` collision check and `handle_screen_edge_and_respawn`'s
    slot-0 initialization. Not yet explored as its own subsystem —
    would need its own construction-routine search (who else writes to
    it?) and struct-field mapping.
14. (new) `_DAT_000115dc` — set on a `spawn_trigger_variant_a()` hit
    inside `dispatch_spawn_record`; purpose/readers not investigated.

## `g_object_table` confirmed — item 13 resolved (2026-09-15)

Followed up on `$167a2` immediately. `get_xrefs_to` lists 7 distinct
functions touching it, including two already carrying sensible names:
`update_object_slots` (`$150a2`) and — from the earlier `FUN_00014862`
decode — its free-slot scanner is `FUN_00014970` (already decompiled
there as the function called before any field writes). Both confirm
the table structure directly:

```c
void update_object_slots(void) {           // per-frame AI update, mirrors update_actor_slots
    ActorRecord *p = &g_object_table[0];
    for (short i = 3; i >= 0; i--) {         // 4 slots
        if (p->state_flags_word != 0) FUN_000150c0();   // per-slot AI tick, not decompiled
        p = (ActorRecord*)((char*)p + 0x58);              // confirmed 88-byte stride
    }
}

void FUN_00014970(void) {                  // free-slot scan, mirrors FUN_00014962
    ActorRecord *p = &g_object_table[0];
    for (short i = 3; i >= 0; i--) {
        if (p->state_flags_word < 0) return;   // (sign-check variant, unlike FUN_00014962's ==0 test)
        if (p->state_flags_word == 0) break;   // found a free slot
        p = (ActorRecord*)((char*)p + 0x58);
    }
}
```

So `g_object_table` is a real, independent **4-slot secondary actor
table**, same 88-byte `ActorRecord` layout and stride as the 6-slot
`g_actor_table`, with its own free-slot scanner and its own per-frame
update loop — a fully parallel subsystem, presumably for lighter-
weight objects (projectiles, thrown items, drop pickups) that don't
need all 6 main actor slots. Other touch points from the xref list,
not yet individually decompiled: `dispatch_spawn_record` (the
`byte3&0x10` collision check already documented),
`handle_screen_edge_and_respawn` (writes slot 0 at end of a screen
transition), `FUN_00015740` (called from `update_actor_ai`'s death-
sequence branch), `FUN_0001709e`/`FUN_000170b6` (part of the submap-
load helper group already flagged as undecoded), `FUN_000149c2`
(unexplored).

Also checked `_DAT_000115dc`'s readers: `get_xrefs_to` finds only its
two known writers (`dispatch_spawn_record`, `update_actor_ai`) and no
reader at all — either genuinely unread (a vestigial/leftover flag) or
another instance of this dump's xref-indexing gap. Not pursued
further; low priority.

### Updated open follow-ups

13. ~~`g_object_table`~~ — **resolved**, see above: confirmed real,
    independent 4-slot `ActorRecord`-shaped secondary actor table with
    its own free-slot scanner (`FUN_00014970`) and update loop
    (`update_object_slots`). Individual object-type construction/AI
    routines (`FUN_000150c0` and whatever constructs new objects into
    it) not yet explored — new candidate follow-up if object/projectile
    behavior matters for the port.
14. `_DAT_000115dc` — still open; no reader found (possibly vestigial,
    possibly another xref-indexing gap). Low priority.

## `FUN_000150c0` decoded (`g_object_table`'s per-slot AI tick); bytes `0x2f`/`0x31` remain genuinely unexplained (2026-09-15)

Decompiled `FUN_000150c0` (the per-slot routine `update_object_slots`
calls for every active `g_object_table` entry) and `FUN_00015740`
(the "silent trigger scan" briefly seen earlier). `FUN_000150c0` is a
large, self-contained **falling/thrown-object physics-and-collision
tick** — gravity acceleration with a capped ramp (`+0x80` per tick,
clamped to `0x800`), tile-collision probing via
`query_tile_and_actor_collision`/`g_collision_probe_x`/`g_collision_probe_y`/
`g_collision_result_flags`, three distinct per-object-type movement
patterns selected by the low byte of offset `0x00` (`1`=oscillate
between two X bounds using a counter pair at `0x29`/`0x2a` mirroring
`FUN_00014862`'s per-type-1 field, confirming that derived byte `0x54`
value from the earlier write-up is indeed this oscillation's *period*.
**SUPERSEDED 2026-09-22 — corrected in `kb2/xrick2-ref.md`, found by a
documentation sweep**: `0x29`/`0x2a` is a decompiler pointer-scaled index
(see the raw pseudocode at "`FUN_00014862` fully decoded" below, which
self-annotates `unaff_A6[0x29] // byte 0x52`), not a byte offset — the
period `0x54` was right, the counter is byte offset **`0x52`**, confirmed
directly from the `$150c0` disassembly (`move.w (0x52,A6),D5w`), matching
`algo-objects.md`.
`2`/`3`=directional movers with several `g_current_map_number`-specific
special cases), and a full despawn/reset path at the bottom (calls
`FUN_00014a12` when the object scrolls past `x >= 0x12a`). This
strongly reads as the game's dropped-item/thrown-projectile/falling-
hazard physics, distinct from the main `update_actor_ai` movement-
script-driven system. Not transcribing the full field-by-field
breakdown (large, and mostly reuses fields already named for
`ActorRecord`) — flagged as available for a deeper pass if the port
needs faithful physics-object behavior.

## Gap-resolution pass: main loop dispatch, loader internals, submap-reload, misc functions (2026-09-16)

Following the doc audit/reorganization (see `xrick2-gaps.md`), worked
through the gaps list starting with the easiest-to-resolve items — plain
`decompile_function`/`get_xrefs_to` calls against already-identified but
unexplored addresses in `/prg2-ram.bin.0`, no live Hatari session needed.
Order follows `xrick2-gaps.md` section C's numbering. Several turned out
to resolve in a single decompile; a few surfaced genuinely new mechanics
(a second depacker, a FAT12-style raw filesystem reader, a demo-mode
subsystem not previously documented at all).

### Gap #9 resolved: `_DAT_000115dc`'s write site — and its "vestigial" status (assumption #12 / gap #14) is wrong

Re-decompiling `main_loop_body` (`$10a90`) directly (rather than relying on
the older transcription) shows the outer/inner loop structure precisely:

```c
void main_loop_body(void)
{
  do {
    _g_camera_scroll_active = 0;
    do {
      update_scroll_edge_trigger(); animate_background_tiles();
      advance_background_anim_counter(); FUN_000170b6();
      update_hud_text_slots(); wait_for_vblank(); FUN_000191e6();
      check_submap_exit_triggers();
      if (_g_submap_complete_flag == 0) { /* ...pause/sound/quit/death-check... */ }
      else { /* ...map-advance branch, see below... */ }
      _DAT_000115dc = 0;
      scan_enemy_spawn_list(); handle_screen_edge_and_respawn();
      update_actor_slots(); update_object_slots();
      update_countdown_timer_bcd(); update_player_rick();
      update_camera_scroll(); update_fall_state_slot();
    } while (_DAT_000115dc == 0);
  } while (true);
}
```

**`_DAT_000115dc` is `main_loop_body`'s own inner-loop continuation flag**:
`main_loop_body` itself resets it to `0` every outer-loop pass (right
after the submap-complete branch), and reads it in its own `while`
condition at the bottom of the inner loop. It is written non-zero
elsewhere by `dispatch_spawn_record`/`update_actor_ai` (already known) to
signal "abort/restart this inner-loop pass" — most likely triggered by a
death or a map-changing event that needs the frame's remaining per-actor
updates skipped. **This closes gap #9 and reverses the earlier
"possibly vestigial" conclusion (assumption B12 / gap #14)**: it is
neither dead nor unread — `get_xrefs_to` simply missed both the write and
the read *inside* `main_loop_body` itself, because neither shows up in its
xref list (only the two external writers were found by that tool). This
is a **third confirmed instance of the documented Ghidra xref-indexing gap**
(see methodology caveat, item #29) — add `main_loop_body`'s self-read/
self-write of `$115dc` to that caveat's example list.

### Gap #7: callers of `main_loop_body`/`load_map_if_changed` — still open, and now a fourth confirmed tooling-gap instance

Both `get_xrefs_to` and `get_function_callers` return **zero results** for
`$10a90` (`main_loop_body`) and `$12394` (`load_map_if_changed`) — despite
both functions obviously being called by something (they're the top of the
whole per-frame engine). This is not evidence they're unreachable; it's the
same xref-indexing gap as above. Resolving this for real would need the
byte-pattern-scan technique used earlier in the doc (scanning the raw
`.bin` for `bsr`/`jsr` operand encodings of `$10a90`/`$12394`), not
attempted this pass — left open, but now explicitly tied to the tooling
caveat rather than looking like an unexplained mystery.

### Gap #4 resolved: `$705e`/`$7136` are the raw FAT12-style floppy filesystem reader

- **`FUN_0000705e`** (`$705e`) sets a command byte (`_DAT_00008000 = 0x10009`),
  calls `FUN_00007282` (the actual FDC/DMA sector-read primitive, still
  unexplored but now scoped precisely), then — if the read succeeded
  (`unaff_D4w == 0`) — decodes a small on-disk structure at `$8030`-`$8056`
  into six derived fields at `$8000`-`$800e` via straight arithmetic
  (sums/right-shifts). The shape (a handful of `CONCAT`-assembled fields
  derived from a fixed-offset sector buffer, including what look like
  sector-count/first-data-sector/track-layout style computations) is
  consistent with **decoding a floppy boot-sector-style BIOS Parameter
  Block (BPB)** into the geometry constants the rest of the loader needs
  (bytes/sector, sectors/cluster, reserved sectors, FAT size, root-dir
  size, first-data-sector offset) — the standard fields a FAT12 reader
  needs, in the standard derivation order.
- **`FUN_00007136`** (`$7136`) is unambiguously a **FAT12 directory search
  + cluster-chain follower**, hand-rolled (no GEMDOS/BIOS calls):
  1. Calls `func_0x000070dc`/`FUN_00007282` (more sector-read primitives),
     then linearly scans a `0xdf4`-byte root-directory-sized region at
     `$803c` for an 11-byte entry (`sVar5 = 10` downto `0`, i.e. an 8.3
     `name+ext` comparison) matching a template at `$8030` — this is the
     already-known `"RICK_0?.HNK"` filename template with the digit
     patched in by `load_and_depack_hnk_file`.
  2. On a match, extracts the directory entry's **starting cluster**
     (`uRam00008010`) and **file size − 1** (`uRam00008012`) using the
     classic FAT12 directory-entry byte layout, then follows the cluster
     chain: `(cluster*3)>>1` computes the FAT12 byte offset for a 12-bit
     entry, with the odd/even-cluster nibble-swap logic
     (`& 0xfff` vs. `>>4 | *0x10`) exactly matching the standard FAT12
     packed-12-bit-entries encoding, reading the FAT table at
     `$843c`-ish and copying `0x400`-byte clusters from `_DAT_00008016`
     forward until the remaining size drops under `0x400`, then a final
     byte-at-a-time tail copy.
  - **Conclusion**: the game's loader completely bypasses GEMDOS and
    implements its own minimal FAT12 reader directly against raw sectors
    already staged in a scratch buffer (consistent with the busy-wait DMA
    polling documented earlier at `$7322`/`$7328`) — it reads the boot
    sector's BPB, searches the root directory by filename, and walks the
    FAT12 cluster chain by hand. This fully resolves gap #4; `FUN_00007282`
    (the shared low-level sector-read primitive both functions call) is a
    reasonable next target if the exact disk geometry constants matter for
    a port, but the *mechanism* is now completely understood.

### Gap #5 resolved: `$1795c` is a second, distinct depacker — decompresses into the monster-descriptor table

`FUN_0001795c` (`load_map`'s post-load step, `A0=$65300`, `A1=$53400`)
decompiles to a **second bit-stream decoder**, structurally different from
`lz_depack_backward` (`$7400`, the backward/in-place LZ scheme documented
earlier): this one reads bits forward from a fixed-size bit-window
(`unaff_D2w`, refilled 16 bits at a time from the input stream at
`in_A0+0x100`), walks a signed-offset tree/table starting at `in_A0+4`
(negative values = literal byte output, positive/zero = tree-node jump by
that many bytes) to decode one byte per iteration, and writes output bytes
forward into `in_A1` until a counter at `*in_A0` reaches zero. This is a
**canonical Huffman-style bit-tree decompressor**, distinct from the
LZ77-with-backreferences scheme in `lz_depack_backward`.

**Since this is called from `load_map` with `A0=$65300`/`A1=$53400`, and
`$53400` is the already-documented monster-type descriptor table
(`DAT_00053400`)**, this resolves gap #5 with a genuinely new fact: **the
monster-descriptor table is not stored flat in the HNK data — it's
Huffman-decompressed at map-load time** from a packed form at `$65300`
into the flat table at `$53400` that `FUN_000146a0`'s default branch reads.
(`$65300` is also independently the address previously associated with
`g_tile_attribute_map` — worth a follow-up to confirm whether that's the
same buffer serving double duty across load stages, or two different
per-map staging buffers that happen to reuse the same fixed address at
different times, since HNK loading for a map is fully sequential.)

### Gap #8 resolved: `FUN_000170ce`'s wrapper chain, and `FUN_000191e6` is *not* actually an infinite loop

- `main_loop_body`'s per-frame call is `FUN_000170b6()`, which is simply
  `{ FUN_000170ce(); }`. `FUN_0001709e` (seen elsewhere in the
  `g_object_table` xref list) is *also* just `{ FUN_000170ce(); }` — the
  same shared code reached from two call sites, not two different helpers.
  `FUN_000170ce` itself is `{ FUN_000170d4(); FUN_000170f2(); }`, and both
  of those walk an `ActorRecord`-strided table (0x2c words = 0x58 bytes,
  terminated by a negative first field) checking a **word at offset
  `0x14`** (inside the previously-fully-unnamed `aUnk10`-range,
  `0x10`-`0x15`) — `FUN_000170d4` calls `FUN_00017116` when that word is
  zero, `FUN_000170f2` clears it to zero and calls `FUN_00017116` when it
  was *non-zero*. `FUN_00017116` itself checks a byte at `+0xe` against
  sentinel `0xfe` ("no sound"/no-op) and otherwise picks between
  `FUN_00019e96`/`FUN_0001952c` based on a flag at `+0x12` — this reads as
  a **per-actor "one-shot sound/effect trigger" pair**: offset `0x14` is
  an edge-detected "already fired" latch, offset `0xe`/`0x12` select which
  of two sound-adjacent routines to call. This is sound-adjacent (out of
  primary scope per project convention) but the *mechanism* — an edge-
  latched one-shot trigger scanned every frame across the actor table —
  is now understood and worth naming (`aUnk10+0x14` → candidate
  `bOneshot_trigger_fired_flag`) if the port needs to reproduce trigger
  timing exactly.
- **`FUN_000191e6` is not an infinite loop** — Ghidra's decompiler flags it
  as one because it can't see the interrupt-driven exit condition, but the
  raw disassembly is a straightforward bounded busy-wait:
  ```
  D0 = *$19232                    ; VBL counter now
  D1 = *$18ed8 - 1                ; target frame count - 1
  loop: if D1 > *$19232: goto loop
        if D0 == *$19232: goto loop   ; also re-loop if counter hasn't advanced at all yet
        clr.w *$19232                ; done: reset the VBL counter to 0
        rts
  ```
  i.e. **"busy-wait until the VBL counter has both changed from its
  entry value and reached the target in `$18ed8`, then zero the
  counter."** This is a bounded VBL-frame delay/pace function (the
  decompiler's "infinite loop" reading was purely an artifact of not being
  able to prove the ISR-driven `$19232` increment terminates the spin) —
  confirms the "probably a decompiler artifact around an interrupt-
  synchronized spin" guess in the original doc, now with the actual
  mechanism nailed down. Also notable: this routine resets the *same*
  `$19232` VBL counter that `wait_for_vblank` (`$19216`) paces the main
  loop against — worth keeping in mind if a port's timing diverges after
  a pause, since this is a second, independent writer of that counter.

### Gap #10 resolved: `$149c2`/`$142fc`

- **`FUN_000149c2`** (`$149c2`) is a small death-sequence step: calls
  `FUN_000149f0` 4 times then 6 times (10 total, fixed counts, no visible
  per-call state change from this function's own decompile — the callee
  must carry per-call state via a register `main_loop_body` doesn't thread
  through explicitly). `FUN_000149f0` itself: if a flag is set, clear it
  and clear bit `0x80` of a byte at struct-offset `0x2a` (word offset
  `0x15`) relative to an inherited base pointer — reads as "un-flag one
  slot's high bit," plausibly a per-life/per-icon 'used' bit being reset
  10 times (matching a plausible max-lives-ish count) as part of the
  death/game-over sequence.
- **`FUN_000142fc`** (created as a function this pass — it existed as
  reachable code but had no Ghidra function record) is the **submap
  reload/respawn routine**: resets Rick's position/facing (`g_player_x`/
  `g_player_y`/`g_player_facing_dir`) and three player flags
  (`g_player_forced_push_flag`, the crouch flag at `$12e18`,
  `g_player_wall_push_flag`) from register values passed in by its caller,
  then calls `FUN_00014458` (the per-level table-selector loader,
  previously documented), `func_0x00016474` (still undecoded — see below),
  `FUN_00016630`, `FUN_000157b4`, `FUN_00014542` (loads
  `g_enemy_spawn_table_ptr`), and finally re-populates the enemy spawn
  list by setting `_DAT_00014592 = 0xffff` as a guard, calling
  `scan_enemy_spawn_list()`, then clearing the guard back to `0`. **This
  is the "reset current submap to its just-loaded state" routine** — the
  respawn-after-death and submap-(re)entry code path, called from
  `main_loop_body`'s death-check branch (`$149c2`/`$142fc` back-to-back).

### Gap #11 partially resolved: three of the submap-helper functions

Three of the previously-undecoded submap-load helpers turned out to be
simple once reached via `FUN_000142fc`'s call list:
- **`FUN_00016630`**: resets a sub-pixel scroll accumulator
  (`_DAT_0001662c = 0`; `DAT_0001662e = DAT_00016462 & 7`, i.e. the low 3
  bits of the scroll/camera-X global) then calls `FUN_000175c6`/
  `FUN_0001856a` (both unexplored, likely rendering-adjacent scroll setup
  — out of primary scope).
- **`FUN_000157b4`**: trivially `{ _DAT_000157ac = 0; }` — a single flag
  reset, role not otherwise chased (likely a "silent trigger" or
  similar one-shot latch reset per submap entry, consistent with its
  neighboring `_DAT_00014592` guard-flag idiom seen right above).
- **`func_0x00016474`**: **could not be turned into a real function** —
  `create_function` fails at this address (`"Unable to create
  function"`), and the preceding function (`compute_tile_map_ptr`, ending
  at `$16461`) leaves a `$16462`-`$16473` gap Ghidra's raw-dump
  auto-analysis never disassembled cleanly. This is the same
  "auto-analysis leaves swaths of code un-disassembled" methodology
  caveat documented elsewhere (item #30) — still open, but now understood
  to be a tooling limitation rather than a dead end worth chasing with
  more decompiles.
- `FUN_000170b6`/`FUN_0001709e` (also on the original gap #11 list) are
  now known to both be trivial wrappers around `FUN_000170ce` — see gap #8
  above, not independent helpers.
- Remaining gap #11 items (`FUN_000188d0`, `FUN_00018b5c`/`FUN_00018c50`,
  `FUN_000191e6`'s *submap-load-context* caller if different from the
  main-loop one) not attempted this pass.

### Gap #12 resolved: `FUN_0001726e` characterized

`FUN_0001726e` (the actor-0 transition-mover called by
`handle_screen_edge_and_respawn`) decompiles as a **byte-stream stepper
matching the same shape as the documented per-actor movement-script VM**:
walks a byte-code stream via a base pointer + saved position at
struct-offsets `0x16`/`0x1a` (relative to an inherited `A6`), treats
negative op bytes as either "reload repeat-count from the byte itself"
(`>= 0`) or "call `FUN_0001a6aa` (the general sound-effect entry point) if
a companion value at offset `0x06` falls in `[0x23, 0x148]`" (i.e. an
embedded sound-effect-ID range check identical in shape to the main
movement-script VM's embedded-sound-trigger opcode), then returns two
decoded delta values packed into a 64-bit return. **This confirms
`FUN_0001726e` is the same movement-script interpreter machinery reused
against a different (non-`ActorRecord`, presumably a small dedicated
"screen transition" state block) base structure for animating Rick's
position during a screen-edge transition**, rather than a separate,
custom-built routine — consistent with the engine's general pattern of
one byte-code VM shared across multiple subsystems.

### Gap #13 resolved: `$17bf4` and `$10bf2`

- **`FUN_00017bf4`** (map-4 alternate handler) is trivial: `if
  (_g_demo_mode_active != 0) return; func_0x00018186();` — i.e. it's a
  demo-mode guard around a single call (`func_0x00018186`, not decoded
  further — presumably rendering/transition-effect given its context
  right before the ending-screen calls, out of primary scope).
  **`_g_demo_mode_active` is a previously-undocumented global** surfaced
  by this decompile (see "New globals surfaced" below).
- **`$10bf2` is not a separate function at all** — it's an inline label
  (`LAB_00010c00` in the current decompile) inside `main_loop_body`
  itself, part of the map-5 ending branch. No further decompilation target
  exists here; this item is closed simply by correcting the original
  "unexplored function" framing to "already-inline code, already visible
  in `main_loop_body`'s own decompile."

### Gap #15 resolved: `FUN_00015b3c`'s canned-actor-restore table and its counters

`FUN_00015b3c` fully decoded: initializes `g_actor_table` slots 0-3 from a
per-slot template at `DAT_0001586e` (X/Y position, anim-script pointer,
move-script pointer), sets `bState_flags=0`/`bBehavior_flags=1` on each,
zeroes/sets a few `aUnk10`/`aUnk1c` bytes to fixed constants (`aUnk10[2..3]
= 0,1`), calls `advance_actor_anim_script()` once per slot to prime the
animation, and separately clears slot 5 to an all-zero/inert state
(`bState_flags=0`, `bBehavior_flags=0`, `aUnk10 = 0,0,0,1`). Alongside this:
`DAT_00015b38 = 0x14` (20) and `DAT_00015b3a = 0`. Given the function's
name-adjacent role ("restore canned actors") and this being the *only*
place either counter is written to a nonzero-vs-reset pair, the most
likely reading is **`DAT_00015b38` = a fixed re-arm delay (20 frames/ticks)
and `DAT_00015b3a` = the live countdown against it** — consistent with
"canned actors reappear N ticks after being cleared," though no reader of
either counter was found this pass (would need `get_xrefs_to` on
`$15b38`/`$15b3a` specifically — not yet done, small follow-up).

### Gap #21 (partially) already resolved in an earlier session — cross-reference correction

Re-reading the existing `FUN_000150c0` write-up (this document, further
above) shows **`ActorRecord+0x54`'s meaning was already resolved in the
2026-09-15 session**, not still open as `xrick2-gaps.md` items B13/C21
currently claim: `FUN_000150c0` (the `g_object_table` per-slot AI tick)
reads a counter pair at offset `0x29`/`0x2a` for its type-1 "oscillate
between two X bounds" movement pattern, and the existing write-up
explicitly states this "confirm[s] that derived byte `0x54` value from the
earlier write-up is indeed this oscillation's *period*." `xrick2-gaps.md`
will be corrected to reflect this as resolved, not open. `DAT_00014854`'s
4-entry LUT remains genuinely unread outside `FUN_00014862` itself
(confirmed via `get_xrefs_to`: all 3 references are internal to that same
function) — its exact per-type-category semantic meaning is still an
open, low-priority guess, but "is there any other reader" is now a closed
question (answer: no).

### Gap #28 resolved: `FUN_000161fe`

`FUN_000161fe` decompiles as a **combined tile+hazard-actor collision
check**: calls `compute_tile_map_ptr`, sets
`g_collision_result_flags = <tile attribute byte>`, and — only if the
tile-attribute bit `0x02` isn't already set — additionally scans the live
`g_actor_table` for any occupied slot (combined-word occupancy test, per
the A1 correction) whose `bBehavior_flags & 0xc0 == 0xc0` (a "hazard
actor" bit combination) and does a `point_in_box_test` against it,
OR-ing bit `0x02` into `g_collision_result_flags` on a hit. **This
resolves gap #28 and clarifies `g_collision_result_flags` bit `0x02`**
(previously "blocked direction," per assumption B25) — it's actually a
combined "tile OR hazard-actor collision at this point" flag, at least for
whichever caller uses this specific probe function; worth reconciling
against the other bit-`0x02` call sites if a port needs the collision
semantics to be fully unambiguous (`g_tile_attribute_map`'s own bit `0x02`
may or may not mean exactly the same thing as this function's OR'd-in
actor-hazard case — not reconciled this pass).

### New globals surfaced this pass (not previously documented anywhere)

- **`_g_demo_mode_active`** and **`_g_demo_stream_end_flag`** — read/set in
  `main_loop_body` itself, gating an entire demo-playback branch (skip
  input handling, play back a recorded input stream, exit demo mode on
  a real fire-press or on stream exhaustion). This is a **previously
  entirely undocumented subsystem** — the attract-mode/demo-playback
  mechanism guessed at earlier (`attract_mode_handler` @ `$18400`) may be
  related to or reuse this flag; worth a follow-up to connect the two.
  Calls seen gated by these flags: `func_0x00017a46`, `func_0x0001771c`,
  `func_0x000123a0`, `func_0x00010c28`, `func_0x0001789a`,
  `func_0x00017bda`, `func_0x00017c06`, `func_0x00017f22`,
  `func_0x000178dc` — none decoded yet, all new candidate follow-ups if
  demo/attract-mode behavior needs porting.
- **`FUN_00017760`**, **`func_0x00019388`** (called twice),
  **`func_0x000123b0`**, **`func_0x000142a0`** — called as part of the
  map-advance branch's cleanup (after `g_current_map_number` is
  incremented, before falling into the next frame's normal update calls).
  Not decoded; likely candidates for "reset per-map render/HUD state,"
  given their position right after a map transition.

### Updated open follow-ups (2026-09-16 gap-resolution pass)

- Gap #7 (callers of `main_loop_body`/`load_map_if_changed`): still open,
  needs the byte-pattern-scan technique, not attempted this pass.
- Gap #11: `FUN_000188d0`, `FUN_00018b5c`/`FUN_00018c50` still undecoded;
  `func_0x00016474` blocked by a Ghidra auto-analysis gap (not a real
  code-complexity blocker).
- New: the demo-mode subsystem (`_g_demo_mode_active` and its ~9 gated
  callees) is a wholly new, undecoded area — not on the original gaps
  list at all since it wasn't known to exist before this pass.
- New: `DAT_00015b38`/`DAT_00015b3a` (canned-actor re-arm counters) —
  candidate reading given above, but no reader confirmed; small follow-up
  (`get_xrefs_to` on both addresses).
- New: `$65300`'s possible dual role (both `g_tile_attribute_map` and the
  packed-source buffer for `$1795c`'s Huffman decompression into the
  monster-descriptor table) — worth reconciling.
- `FUN_00007282` (shared low-level sector-read primitive under both
  `$705e` and `$7136`) — exact disk-geometry constants not extracted, low
  priority unless precise load timing/geometry matters for a port.

### Correction: the "demo-mode subsystem" is very likely not brand-new

Cross-checking `xrick2-ref.md`'s existing "Input handling" section
(written in an earlier session) shows `g_demo_mode_active` (`$3efb6`)
already documented there, gating `read_player_input`'s choice between
live joystick input and an RLE-encoded recorded stream, tied to
`attract_mode_handler`. `main_loop_body`'s `_g_demo_mode_active` (no
concrete address surfaced by this pass's decompile) is almost certainly
the *same* global, not a second independent one — the name match is too
exact to be coincidence, though this hasn't been confirmed by checking
the actual address. **Correcting the framing above**: this is not a
wholly new, previously-undocumented subsystem — it's `main_loop_body`
itself branching on an already-partially-known flag. What is genuinely
new is `main_loop_body`'s own branch structure and its ~9 gated callees,
plus `_g_demo_stream_end_flag` (not previously documented anywhere).
Confirming `_g_demo_mode_active`'s address equals `$3efb6` is a quick,
worthwhile follow-up, not yet done.

## Second gap-resolution batch (2026-09-16, continued)

Continuing "investigate each open gap, easiest first" after the write-up
above. This batch chased the loose ends left at the end of the first
batch: the demo-mode address confirmation, `DAT_00015b38`/`DAT_00015b3a`'s
readers, the `g_object_table`-construction lead from
`handle_screen_edge_and_respawn`'s WRITE at `$15d22`, the remaining
render-adjacent submap helpers, `FUN_00007282`, and one more serious push
on gap #7 (`main_loop_body`/`load_map_if_changed` callers) and the
`func_0x00016474` tooling block.

### Confirmed: `_g_demo_mode_active` IS `g_demo_mode_active` (`$3efb6`)

`get_xrefs_to(0x3efb6)` lists a read at `00010b2a in main_loop_body` —
exactly the address of the `if (_g_demo_mode_active != 0)` check in the
decompile from the previous section. **Confirmed, not just inferred**:
this is the same global already documented for `read_player_input`/
`attract_mode_handler`, not a second independent flag. The "new" part of
gap #33 really is just `main_loop_body`'s own branch structure, its ~9
gated callees, and `_g_demo_stream_end_flag` (still a genuinely new,
undecoded flag).

### Gap #24 RESOLVED: `g_object_table`'s construction site found

Re-decompiling `handle_screen_edge_and_respawn` (`$15d24`) in full (not
just the summary from the prior session) shows its `LAB_00015cc8` block —
reached after the screen-transition-mover (`FUN_0001726e`) and a chain of
box-vs-player checks/`spawn_trigger_variant_a` calls determine the
transition has fully completed — **directly constructs a live
`g_object_table` slot 0 entry**:

```c
LAB_00015cc8:
  uVar10 = FUN_00017810();               // returns a sound-ID (D0) + delta (D1)
  _g_screen_exit_trigger_flag = 0;       // transition officially over
  /* ...resets g_actor_table[0..3] to a fixed post-transition template... */
  PTR_LAB_000167a2._0_2_ = 1;             // g_object_table[0]: combined state:behavior word = 1
  PTR_LAB_000167a2._2_2_ = g_actor_table[0].nX;  // nX = Rick's transitioned X
  DAT_000167a8 = g_actor_table[0].nY;             // nY = Rick's transitioned Y
  DAT_000167e0 = 0x4b;                            // offset 0x3e (nSpawn_anim_frame) = 0x4b
  DAT_000167f0 = 0xffff;                          // offset 0x4e
  DAT_000167b4 = 0;                               // offset 0x12
  DAT_000167c4 = 0;                               // offset 0x22
  DAT_000167aa = 0;                               // offset 0x08
  DAT_000167ae = 0xfb00;                          // offset 0x0c
  DAT_000167ac = 0xfffe;                          // offset 0x0a
  FUN_0001a6aa(uVar10);                           // plays the sound-ID from FUN_00017810
  PTR_DAT_000167cc = (undefined *)0x0;            // offset 0x2a, a pointer field, zeroed
  g_actor_table[5].bState_flags = 0;              // also clears the "homing hazard" slot (see below)
  g_actor_table[5].bBehavior_flags = 0;
```

Every written address is `g_object_table`'s base (`$167a2`) plus a fixed
offset, at exactly the offsets already named in the `ActorRecord` struct
table — this is a **hand-inlined `g_object_table[0]` construction**,
positioned at Rick's post-transition location, not a generic "spawn
routine" shared with the enemy side. **This resolves gap #24**: the
"construction routine" isn't a separate function analogous to
`FUN_00014636` — it's inlined directly into
`handle_screen_edge_and_respawn`'s transition-complete path. Read as:
after a screen-edge transition finishes, the game plants a single
invisible/timed hazard-or-marker object at Rick's arrival point (sound-ID
from `FUN_00017810` suggests this fires an audible cue, e.g. a
"transition complete" chime) — consistent with `g_object_table`'s
documented role as a dropped-item/hazard table, applied here to a
transition-triggered rather than enemy-triggered spawn.

### New finding: `g_actor_table` slot 5 is a dedicated "homing hazard" special actor

Chasing `DAT_00015b38`/`DAT_00015b3a`'s readers (gap #15's loose end)
surfaced a previously undocumented mechanic. Three functions read/write
these counters, all operating on **`g_actor_table[5]`** specifically (the
same slot `FUN_00015b3c`, `handle_screen_edge_and_respawn`, and
`FUN_00014862`/`update_object_slots` all special-case as "not a normal
enemy slot" without previously explaining why):

- **`FUN_00015d84`**: if `DAT_00015b3a != 0`, decrements it and returns
  (cooldown). Otherwise: plays a sound (`FUN_0001a6aa`), resets the
  cooldown to `0x32` (50), and (re)spawns `g_actor_table[5]` as a homing
  actor: `bState_flags=0`, `bBehavior_flags=1`, `nAnim_frame=0x6c`,
  positioned near `g_actor_table[0]` (Rick's own transition-mover slot),
  then computes a coarse "aim at the player" step vector by repeatedly
  halving `(g_player_x - slot5.nX, g_player_y - slot5.nY)` until both
  components fit in `[-4, 4]`, storing the result into `aUnk08[2..5]` (a
  4-byte packed X/Y step-delta pair) — a **classic discrete "homing
  missile" direction-vector computation**.
- **`FUN_00015e48`**: applies that stored step delta to
  `g_actor_table[5].nX`/`nY` each frame, decrementing
  `DAT_00015b3a` toward 0 (floor-clamped) as it goes; if the new position
  is on-screen (`0 <= nX+4 < 0x104`), does a tile-collision probe
  (`FUN_000161fe`, gap #28's function) and a `check_box_vs_player` — a hit
  sets `_g_player_death_trigger = 0xffff`. Otherwise (off-screen or a
  successful hit either way falls through to) clears the slot
  (`bState_flags=bBehavior_flags=0`).
- **`FUN_00015eca`** (`g_object_table`-construction's own earlier
  gate-check callee): decrements `DAT_00015b38` (the counter reset to
  `0x14`=20 by `FUN_00015b3c`) as a straightforward screen-transition
  countdown; also unconditionally resets `aUnk10[0..1] = {0, 1}` across
  all 4 main actor slots every call — plausibly re-arming the per-actor
  one-shot sound-trigger latch from gap #8 for the new submap.

**Conclusion**: `g_actor_table[5]` is a **dedicated, single-instance
"homing hazard" actor slot**, spawned by `FUN_00015d84` on a 50-frame
cooldown timer, distinct in kind from both the normal enemy slots (0-4)
and `g_object_table`. `DAT_00015b38` = screen-transition countdown (20
frames, read by `FUN_00015eca`); `DAT_00015b3a` = this homing-actor's own
respawn cooldown (50 frames, read/written only by `FUN_00015d84`/
`FUN_00015e48`). This resolves the remaining open half of gap #15 with
confirmed readers for both counters (previously only a guess).

### Gap #4 extended: `FUN_00007282` decoded — low-level per-sector read loop

`FUN_00007282` (the shared primitive under both `$705e` and `$7136`) is a
straightforward sector-read loop: for a run of `in_D1w` sectors starting
at a track/sector index from `func_0x0000738e()`, it calls
`func_0x000073d6` (compute physical sector position, wrapping via a
sectors-per-track modulo derived from the BPB fields decoded earlier),
conditionally calls `func_0x000073bc` (likely a head/side-switch when
crossing a track boundary), then `func_0x000072d6` (the actual FDC
DMA-read-and-busy-wait, matching the earlier-documented polling loop),
checking an error flag (`unaff_D4w`) after each sector. This is pure
low-level floppy-controller driver detail (side/track/sector stepping) —
confirms the mechanism but the four callees themselves are hardware-
driver plumbing, not game logic; not chased further (very low priority).

### Gap #11 fully closed: remaining submap helpers are render/blit, out of scope

`FUN_000188d0`, `FUN_00018b5c`, `FUN_00018c50` all decompile as tight,
`0xbf`(191)-iteration-count byte/word-shuffling copy loops moving data
between fixed buffers in the `$57d00`-`$68510` range (tile/sprite-data
addresses) with scroll-offset-dependent addressing
(`DAT_00016462 & 7` selecting a sub-tile pixel shift) — i.e. **screen-
scroll column/row blit routines**, not game logic. Per the project's
standing scope rule (render/blit excluded), these are now confirmed
out-of-scope rather than merely undecoded. **This closes gap #11**: every
item on the original undecoded-helper list is now either decoded
(game-logic) or confirmed render-adjacent (out of scope).

### Gap #7: pursued further, remains genuinely blocked — now with a clean negative result

- `search_byte_patterns` for a `JSR` absolute-long encoding of either
  target (`4E B9 00 01 0A 90` for `main_loop_body`, `4E B9 00 01 23 94`
  for `load_map_if_changed`) found no matches.
- `search_instructions(mnemonic="bsr", operand_pattern="10a90"/"12394")`
  — searching **every currently-disassembled instruction in the entire
  program** (6459 total) — found zero matches for either address.
- `find_code_gaps` showed a large 38KB "gap" immediately before
  `main_loop_body` (`$7590`-`$10a8f`) flagged `has_orphaned_instructions:
  true`; investigated directly via `create_function`/`disassemble_bytes`
  — this region is **data** (Ghidra's own auto-suggested name at `$7590`
  is `str_RICK_02_HNK_reused_buffer`, a string/data label, not code), and
  the "orphaned instructions" flag is a false lead from stray incidental
  byte patterns, not a real undisassembled function. This rules out "the
  caller is hiding in this specific gap."
- **Conclusion**: the real caller of both functions is not merely
  hard-to-find with `get_xrefs_to` — it isn't disassembled as code
  *anywhere* in the current Ghidra project (0 of 6459 known instructions
  reference either target). It's either in one of this dump's many
  genuinely-still-undisassembled regions (see `find_code_gaps`'s other
  ~50 gaps, e.g. `$10b5c`-`$11e75`, `$124be`-`$1300d`, etc. — several
  are multi-KB and un-investigated), reached via an indirect call (`jsr
  (An)`/jump table) that wouldn't carry the address as a literal operand,
  or the call uses a `bsr` encoding this search should have caught but
  didn't for some other reason. **Genuinely unresolved**, but now backed
  by an exhaustive negative result rather than a single failed lookup.

### `func_0x00016474` root cause fully diagnosed (still blocked, but now precisely understood)

Manually inspecting the raw bytes around the call target with
`read_memory`/`disassemble_bytes` found the exact conflict that makes
`create_function(0x16474)` fail:

- Raw bytes at `$16474`-`$16477`: `48 E7 E0 E0`. `48 E7` is the opcode
  word for **`movem.l {reglist},-(SP)`** — a completely ordinary function
  prologue — with `E0 E0` as its register-list mask (decodes to a
  `D5-D7`/`A5-A7`-range register set, an unusual but valid combination).
  **`$16474` is almost certainly the function's real, correct entry
  point.**
- But asking Ghidra to disassemble starting exactly at `$16474` doesn't
  decode the `movem.l` at all — it silently jumps to `$16476` and decodes
  *only* the trailing mask bytes (`E0 E0`) as their own bogus instruction,
  `asr -(A0)`. This means Ghidra's project already has a **pre-existing,
  incorrect code-unit boundary asserted at `$16476`** (left over from an
  earlier stray auto-analysis pass that walked into this region from the
  wrong starting offset), and it won't let a new instruction/function
  start at `$16474` because that would overlap/conflict with the already
  -committed (wrong) unit two bytes later.
- **This is a fully diagnosed, fixable Ghidra data-model issue, not an
  unknowable gap**: clearing the code unit at `$16476` (e.g. via Ghidra's
  GUI "Clear Code Bytes" on that address, or an equivalent MCP call not
  available in this tool's current surface) and re-disassembling from
  `$16474` should recover the real function. Not done this pass (no
  "clear code unit" tool was available), but the exact fix is now known
  precisely, upgrading this from "blocked, cause unknown" to "blocked,
  cause and fix both identified."

### Updated open follow-ups (this batch)

- Gap #7: still open; next step is either scanning the other large
  `find_code_gaps` regions directly for `bsr`/`jsr` patterns, or accepting
  this as a permanent tooling limitation of this particular raw-RAM-dump
  import.
- `func_0x00016474`: still blocked, but the fix is now a mechanical
  Ghidra housekeeping step (clear the wrong code unit at `$16476`) rather
  than an open research question.
- New: `FUN_00017810` (called by `handle_screen_edge_and_respawn`'s
  transition-complete path, returns a sound-ID + delta) — not chased,
  sound-adjacent.
- New: the exact meaning of `g_object_table[0]`'s planted fields
  (`0x4b` init anim-frame, `0xfb00`/`0xfffe`/`0xffff` constants at offsets
  `0xc`/`0xa`/`0x4e`) — mechanism (a hand-inlined spawn) is now known, but
  the per-field game-meaning (e.g. what visual/hazard effect this
  represents) is not decoded further, low priority unless the port needs
  to reproduce this exact post-transition object.

Crucially: **neither `FUN_000150c0` nor `FUN_00015740` reference byte
offset `0x2f` or `0x31` either.** Combined with every other function
already checked this session (`update_actor_ai`, `FUN_00014a12`,
`dispatch_spawn_record`, `FUN_00014862`, `FUN_000146a0`,
`update_object_slots`, `FUN_00014970`), that's now **every function
reachable from the actor/object AI and construction call graph**
without a single access to these two bytes. Concluding this is a
real, final answer rather than an artifact of incomplete searching:
`ActorRecord+0x2f` and `+0x31` are most likely genuine **alignment
padding** (each sits directly before a 4-byte pointer field —
`+0x2f` before `substate_flags` at `0x2e`... actually immediately
*after* `substate_flags` at `0x2e`, and `+0x31` immediately before
`move_script_ptr_alt` at `0x32` — both classic single-byte gaps needed
to keep the following/preceding multi-byte fields on even boundaries,
consistent with 68000's alignment preferences). Downgrading this from
"unexplained field" to "confirmed padding, no action needed" for
porting purposes — a straight struct port can leave these as unused
filler bytes.

### Updated open follow-ups

Item 4 (originally: `ActorRecord`'s remaining unnamed fields) is now
**fully closed** for practical porting purposes: bytes `0x2f`/`0x31`
are padding, and every other previously-"unknown" range has a
spawn-time-init explanation (see the `FUN_00014862` write-up).
Remaining genuinely open items: item 5 (bulk-decode more level
content — broad, low-urgency), item 10 (render/blit, out of scope by
design), item 13's sub-item (individual `g_object_table` construction
routine — who spawns new objects into it? — not yet found), and item
14 (`_DAT_000115dc`, low priority).

## Gap #33 resolved: demo-mode branch's callees decoded, and the "POOKY" cheat found (2026-09-16)

Continuing "proceed with remaining gaps" — tackled gap #33, the 9
undecoded callees clustered in the `$10c00`-`$17f22`/`$17f22` region
reached from the demo-mode/map-4-ending branch logic documented earlier
(main loop's level-transition special-casing, "Maps 4 and 5 are
special-cased" section above). None of these 9 addresses had been
`create_function`'d yet. 8 of 9 created and decompiled cleanly; the 9th
(`$123a0`) hit the exact same Ghidra tooling bug already diagnosed for
`func_0x00016474` (see below).

### `FUN_00017f22` — the name-entry screen, and a genuine "POOKY" cheat code

Full decompile shows a classic 5-character name-entry UI: a 6-column ×
5-row character grid (`&DAT_00017ef7`), navigated with the joystick
(`sVar3`/`sVar4` step through columns/rows on left/right/up/down,
wrapping via the `!=5`/`!=0` clamps), fire-button-confirmed per
character. Character code `0x11` from the grid is "END entry", `0x10` is
"backspace" (writes filler byte `0x0e` and steps the cursor back). Typed
characters accumulate into a 5-byte buffer at `$17f16`/`$17f1a`.

After entry completes, there's an explicit check:

```c
if ((_DAT_00017f16 == 0x504f4f4b) && (DAT_00017f1a == 0x590e0e0e)) {
    _DAT_0001798e = 0xff;
}
```

`0x504f4f4b` = ASCII `"POOK"`, and `0x590e0e0e` = `'Y'` followed by three
`0x0e` filler bytes (the same filler byte backspacing writes, i.e. "blank
slot") — so this fires when the player types the 5-letter name **"POOKY"**
at what is presumably the high-score name-entry screen. It sets flag byte
`_DAT_0001798e` to `0xff`.

That flag is read in two other places in this same cluster:
- `FUN_00017a46` gates joystick left/right handling on
  `_DAT_0001798e != 0` before letting `g_joystick1_state` bits 2/3 adjust
  `_DAT_00017990` (a signed step value) — i.e. **"POOKY" unlocks an extra
  manual joystick control** in whatever screen `FUN_00017a46` drives.
- `FUN_00017c06` also branches on it (not fully deciphered — calls
  `update_hud_text_slots` either way, so likely just changes which text
  is shown).

`FUN_00017a46` itself (the function gated by this flag) is a
level-picker: when not in demo mode and `g_map4_end_state != 0`, it runs
a joystick-driven loop adjusting `sVar1`/`sVar2` up/down clamped to
`[1, g_map4_end_state]`, fire-button-confirms, and stores the chosen
value into `g_map4_special_flag`. Combined with the flag-gated extra
joystick handling above, **this is the classic "POOKY" cheat: entering
it as your name at the high-score/name-entry screen unlocks manual level
selection** on this level-picker screen (previously seen only from the
*consumer* side, in the "Maps 4 and 5 are special-cased" main-loop
branch logic documented earlier in this doc, where
`g_map4_special_flag != 1` routes to an "alternate handler" instead of a
normal map advance — this cluster of functions *is* that alternate
handler/level-picker subsystem). This confirms the mechanism; the exact
end-user framing (what "level 1-N" corresponds to, whether this is
literally the real game's known cheat code) is a nice-to-have, not
pursued further as it needs a live playthrough to observe the resulting
screen.

### The rest of the cluster

- **`FUN_0001771c`** — zeroes the shared state block at `$176e4`-`$1770e`
  (the same block `FUN_00017a46`/`FUN_0001789a` read/write) and sets one
  field (`PTR_DAT_00017710`) to `6`. A reset/init routine for this
  screen's shared scratch state, called before entering it.
- **`FUN_0001789a`** — three back-to-back `while` loops that just spin
  calling `FUN_00017810` (the sound-ID+delta getter already flagged as
  sound-adjacent in the previous batch) until flag words at `$176f4`/
  `$17702` clear. Reads as "wait for a sound/jingle sequence (or two) to
  finish playing" — sound-adjacent, not chased further.
- **`FUN_00017bda`** — early-outs if `_g_demo_mode_active != 0`;
  otherwise plays a sound (`FUN_0001a6aa`) and calls `func_0x00018186`
  (still unexplored — name suggests a render/flash effect given its
  `$181xx` neighborhood, consistent with the render-adjacent code found
  in that area during the second batch's gap #11 closure). Reads as "if
  this is a real (non-demo) playthrough, play a fanfare + trigger a
  visual flash," e.g. on reaching this screen for real vs. during
  attract-mode demo playback.
- **`FUN_00017c06`** — a "press fire to continue" wait loop: calls
  `update_hud_text_slots`, waits out the current fire-button hold, then
  loops calling `FUN_000191e6` (the per-frame pause/fire-poll helper from
  the main-loop writeup) until fire is pressed, finishing with a sound
  toggle call (`func_0x0001a5d0`). Standard "screen up, wait for the
  player to acknowledge" pattern.
- **`FUN_000178dc`** — the demo/attract-mode *entry* sequencer: latches
  the fire button state, then runs up to 4 rounds alternating
  `FUN_0001793a`/`FUN_00017e40` (both still unexplored — likely "record"
  vs. "play back" a canned demo-input frame, given the naming pattern
  elsewhere) each followed by an abort-check (`FUN_00017c86`, also
  unexplored); if all 4 rounds complete without an abort,
  `_g_demo_mode_active` is set to `0xffff`. This is almost certainly the
  title-screen idle-timeout logic that flips the game into attract-mode
  demo playback — confirms `_g_demo_mode_active`'s *setter*, complementing
  the second batch's confirmation of its *identity* with
  `g_demo_mode_active` (`$3efb6`).
- **`FUN_00010c28`** — unrelated to the rest of this cluster; a one-shot
  hardware/system routine that copies live MFP register values
  (`$fffffa07`/`09`/`13`/`15`/`17`/`19`/`1f`) and the original `$68`/`$70`/
  `$118`/`$134` exception-vector contents into a fixed save area at
  `$11606`-`$1161a`. This is a "back up the OS's original vectors/MFP
  state before installing custom handlers" routine, the same pattern as
  `install_ikbd_vector_118` documented earlier — system/hardware
  init, not game logic, out of scope for the port.

### `func_0x000123a0` — second confirmed instance of the code-unit-boundary bug

`create_function(0x123a0)` failed the same way `$16474` did in the
previous batch. `read_memory(0x12390, 32)` shows the real bytes at
`$123a0` are `33 f9 00 01 79 94` — a valid 6-byte `move.w D1,$17994`
instruction (note: `$17994` is `_DAT_00017990`'s immediate neighbor, the
signed-step field `FUN_00017a46` writes — so this function saves/
restores that value). Ghidra's existing (wrong) code-unit boundary starts
two bytes later at `$123a2`, decoding just the trailing `00 01 79 94` as
`ori.b #-0x6c,D1` — exactly the same class of error (and the same 2-byte
offset) as `func_0x00016474`. This is now a **confirmed pattern**, not a
one-off: this Ghidra project has at least two spots where a stray
earlier auto-analysis pass planted a wrong short instruction 2 bytes
into a real `movem`/`move`-family instruction's operand bytes, blocking
correct disassembly at the true entry point. Same fix needed (clear the
wrong code unit, redisassemble from 2 bytes earlier) and same tooling
limitation (no "clear code unit" MCP tool available this session).

### Gap #33 status: closed for practical purposes

All 9 callees are now identified: 6 are UI/sequencing logic for a
name-entry-screen "POOKY" cheat cluster (level-picker unlock), 1 is a
sound-wait helper, 1 is a one-shot hardware vector-backup routine (out of
scope), and 1 (`$123a0`) is blocked on the now-twice-confirmed Ghidra
code-unit bug. This is a menu/attract-mode subsystem, not core gameplay
AI/physics — genuinely useful context (especially the "POOKY" cheat and
the demo-mode entry sequencer) but adjacent to, not part of, the
project's core game-logic porting scope.

### Ghidra annotations added this pass

Functions created (not yet renamed — names above are descriptive, not
yet applied in Ghidra): `$17a46`, `$1771c`, `$10c28`, `$1789a`, `$17bda`,
`$17c06`, `$17f22`, `$178dc`.

### Updated open follow-ups (this batch)

- `func_0x000123a0` blocked, same fix as `func_0x00016474` (now 2
  confirmed instances of this Ghidra housekeeping bug).
- `func_0x00018186`, `FUN_0001793a`, `FUN_00017e40`, `FUN_00017c86` — new
  unexplored callees surfaced by this pass; the first is render-adjacent
  (likely out of scope), the latter three are demo-record/playback
  primitives, moderate priority if the port wants attract-mode demo
  playback, low priority otherwise.
- End-user confirmation of the "POOKY" cheat (what it actually looks
  like in play) needs a live Hatari session — not attempted, static
  evidence is strong enough to document as a confirmed finding.

## Gap #26 partially resolved: collision probe's exact tap geometry (2026-09-16)

Continuing "proceed with remaining gaps" — gap #26 asked for the exact
tap positions `query_tile_and_actor_collision` (`$15fba`) uses for tile
collision (previously only "3 x-offsets, 2 or 3 y-taps," not decoded
precisely). Went back to its raw disassembly (`disassemble_function`,
not just the decompile, since the decompile flattens the address math
into opaque `extraout_A1`/`extraout_A0`) plus its pointer-setup callee,
`compute_tile_map_ptr` (`$1643e`, decompiles to nothing useful — pure
address arithmetic, read from disassembly instead).

### Row count: confirmed 2 or 3, gated by sub-tile Y phase

```c
sVar6 = 3;
if ((g_collision_probe_y & 7) < 4) {
    sVar6 = 2;
}
```
Already known; re-confirmed directly from the decompile at the top of
`query_tile_and_actor_collision`. `g_collision_probe_y & 7` is the
probe's sub-tile (0-7 pixel) phase within its current 8px tile row;
when it's in the lower half of the tile (`<4`), only 2 rows are probed
instead of 3 — consistent with "don't bother probing a 3rd row's worth
of headroom/footroom you can't possibly be touching yet at this sub-tile
offset."

### `compute_tile_map_ptr` (`$1643e`): the base-pointer formula

```
A1 = $65300                                  ; tile-map base
D6 = (g_collision_probe_y & ~7) * 4          ; row term
A1 += D6
D7 = 4 + g_collision_probe_x                 ; caller sets D7=4 before the call
D6 = D7 >> 3                                  ; pixel-X -> tile column (÷8)
A1 += D6
```

The X half is unambiguous: `(g_collision_probe_x + 4) >> 3` converts the
probe's pixel X (offset by a fixed +4px, i.e. centering the probe on the
middle of an 8px-wide tile rather than its left edge) into a tile-column
byte index, and each tile column is exactly 1 byte in the map array — so
**consecutive bytes at `A1`, `A1+1`, `A1+2` are 3 horizontally-adjacent
tile columns**, matching the "3 x-offsets" already known, now pinned
down as literally *adjacent* columns (not e.g. `-1/0/+1` with a gap).

The Y half's `*4` multiplier is **not fully resolved** — it implies each
row-band spans 4 bytes of the map array per 8px of world Y, which is
smaller than a full tile row's width would need to be for a real map (a
typical Rick Dangerous submap is tens of tiles wide). The most likely
reading, not yet confirmed, is that `$65300` is not the raw per-tile map
array itself but a **compact per-row descriptor table** (4 bytes/row)
that `query_tile_and_actor_collision`'s row-stride jumps (`0x1e`/`0x1f`
bytes, see below) then walk through differently — i.e. the `*4` term
picks a *starting row descriptor*, and the actual tile bytes read via
`(A1)+` come from data reached indirectly through it, not from `$65300`
literally interpreted as tile IDs at a `*4`-per-row stride. This would
need either finding what's actually stored in the first few bytes at
`$65300` in a live/dump capture, or tracing one more level in — not done
this pass, flagged as the residual open piece of this gap.

### Row-to-row stride inside the collision loop: `0x1e`/`0x1f` bytes

From `query_tile_and_actor_collision`'s own disassembly (the two probe
loops at `$16004`-`$1601a` and `$16058`-`$16068`): after reading 2 or 3
adjacent tile bytes via `(A1)+`, `A1` is advanced by `lea (0x1e,A1),A1`
(30 bytes, 3-tap loop) or `lea (0x1f,A1),A1` (31 bytes, 2-tap loop)
before the next row's read — i.e. **each row advance is exactly "3 (or
2) bytes already consumed this row" + a fixed jump**, landing on a
consistent per-row byte pitch of `0x1e+3 = 0x21` (33) or `0x1f+2 = 0x21`
(33) either way — **both loop variants land on the identical 33-byte
row pitch**, which is the actual confirmed row width of the underlying
map/descriptor structure being walked, regardless of which of the two
`*4`-formula readings above turns out to be correct.

### Gap #26 status: mostly resolved

Confirmed and now precisely documented: 3 adjacent tile-map bytes probed
per row (x-tap positions are literally consecutive bytes, X computed as
`(probe_x+4)>>3`), across 2 or 3 rows (gated by `probe_y&7<4`), with a
uniform 33-byte row pitch. **Still open**: what `$65300`'s `*4`-per-row
addressing actually indexes semantically (raw per-column tile bytes at
an unexpectedly small row stride, vs. an indirect per-row descriptor) —
low priority for porting purposes since the *effective* 33-byte pitch
and 3-adjacent-column tap pattern are what a reimplementation actually
needs; the deeper "why 65300 specifically encodes rows this way" is
architecture trivia, not behavior-affecting.

### Ghidra annotations added this pass

None — this was pure disassembly reading, no new labels/functions
created (both `query_tile_and_actor_collision` and `compute_tile_map_ptr`
were already named from earlier sessions).

## `func_0x00014434` decoded: the submap forced-push teleport (2026-09-16)

**Duplicate-discovery note (added during the 2026-09-16 documentation
audit): this function was already fully decoded, with the identical
conclusion, in "[`FUN_00014434` decoded — this *is* the submap-transition
teleport (2026-09-15)](#fun_00014434-decoded--this-is-the-submap-transition-teleport-2026-09-15)"
above — that is almost certainly the earlier session whose function
boundary this entry found already in place but couldn't trace the origin
of. No fact conflict between the two write-ups; this entry is preserved
per the append-only convention but adds nothing new — see the earlier
entry for the first decode.**

Picked up an old open follow-up (item 6 from the "Spawn table record
grammar corrected" section, 2026-09-14): `func_0x00014434`, called from
`check_submap_exit_triggers`'s "forced push" path (see that function's
decompile earlier in this doc), had no defined function boundary. It
already had one this pass (`get_function_by_address` found body
`$14434`-`$14457`, presumably created in a session not captured in this
doc), so just needed decompiling:

```c
void FUN_00014434(void)
{
  if (g_player_x == 0) {
    g_player_x = 0xe8;
    FUN_00018abe();
  } else {
    g_player_x = 0;
    FUN_00018bb2();
  }
}
```

This is the **submap forced-push teleport**: if the player is at the
left screen edge (`g_player_x == 0`), snap them to `x=0xe8` (232) and
call `FUN_00018abe` (already known as one of the two submap-load
routines, per the earlier `func_0x00014458`/loader write-up); otherwise
snap to `x=0` and call `FUN_00018bb2` (the other submap-load routine).
This is exactly the mechanic implied by `check_submap_exit_triggers`'s
`forced_push:` label — a scripted trigger record can force the player
through a submap boundary in a specific direction without them having
to walk to the edge normally, teleporting them to the *opposite* edge of
the newly-loaded submap. Confirms the "forced push" bit (`0x20` in the
trigger record) does exactly what it looks like it does; does not
change anything about trigger-table bytes 2-3 (still confirmed unused by
every reader — see gap #14).

Suggested rename (not yet applied in Ghidra):
`teleport_to_adjacent_submap_edge`.

### Note on gaps.md items #22/#23: stale relative to later wk.md sections

While tracing this follow-up, noticed `xrick2-gaps.md`'s items #22/#23
("bulk-decoding more of each level's script/table byte streams" /
"records 22+ ... not established either way") describe a state that was
already substantially superseded by two later 2026-09-14 sections in
this doc — "Spawn table record grammar corrected" and "Submap-trigger
table format decoded" — which found the *real* terminator convention
(header `byte0==0`) and re-walked the same sample with correct
variable-length header+detail segmentation, resolving the "records
22+ look incoherent" confusion as an artifact of the earlier flat
4-byte-stride misread, not a real second table. Corrected in gaps.md.

## Gap #2 resolved: both Ghidra code-unit-boundary bugs fixed with scripting (2026-09-16)

Previously (see the `func_0x00016474` and `func_0x000123a0` diagnosis
entries above/earlier) both addresses were blocked from `create_function`
by a pre-existing, wrong code unit sitting 2 bytes into what is actually a
longer real instruction — `$16476` had a stray `asr -(A0)` (bytes `E0 E0`,
which are just the tail of the real 4-byte `movem.l {D5-D7,A5-A7},-(SP)`
at `$16474`), and `$123a2` had a stray `ori.b #-0x6c,D1`, 2 bytes into the
real 6-byte `move.w D1,$17994` at `$123a0`. Confirmed via a
`disassemble_bytes` dry-run at `$16474` (length 8): it silently skipped
`$16474`-`$16475` and resumed decoding at the pre-existing stray unit
`$16476`, proving this is a code-unit lock, not a decoding ambiguity —
`disassemble_bytes` alone cannot force an overwrite.

The user enabled `GHIDRA_MCP_ALLOW_SCRIPTS=1` and restarted the Ghidra MCP
server mid-session, unblocking `run_script_inline`. Fixed both with:

```java
import ghidra.program.model.listing.Function;

clearListing(toAddr(0x16474), toAddr(0x1647f));
disassemble(toAddr(0x16474));
Function f = createFunction(toAddr(0x16474), "func_0x00016474_fixed");

clearListing(toAddr(0x123a0), toAddr(0x123af));
disassemble(toAddr(0x123a0));
Function f2 = createFunction(toAddr(0x123a0), "func_0x000123a0_fixed");
```

Both succeeded (verified dry-run first, then applied for real, then
`save_program`'d). Decompiled results:

- **`func_0x00016474_fixed`**:
  ```c
  undefined8 func_0x00016474_fixed(void)
  {
    undefined4 in_D0;
    undefined4 in_D1;
    short sVar1;

    sVar1 = 9;
    _LAB_0001646e = (short)((DAT_00016462 >> 5) << 3) + _LAB_0001646a;
    DAT_00016472 = DAT_00016462 >> 3 & 3;
    if (DAT_00016472 == 0) goto LAB_000164bc;
    FUN_000165a6();
    while (sVar1 = sVar1 + -1, sVar1 != -1) {
  LAB_000164bc:
      FUN_000165fc();
    }
    if (DAT_00016472 != 0) {
      FUN_000165a6();
    }
    return CONCAT44(in_D0,in_D1);
  }
  ```
  Reads a packed field out of `DAT_00016462` (low 3 bits after `>>3`,
  masked to `0-3`), computes an offset (`(hi5bits<<3) + base`), and loops
  calling `FUN_000165fc` up to 9 times with `FUN_000165a6` bracketing the
  loop when the packed field is non-zero. Not yet decoded further — callees
  `FUN_000165a6`/`FUN_000165fc` are new leads, not previously in scope.
  Gap note: naming/purpose still open (not itself a blocker anymore, just
  unexplored); candidate name once decoded: something in the render/blit
  neighborhood given the address range, but **out of scope by the standing
  render/blit exclusion** unless it turns out to touch game-logic state.
- **`func_0x000123a0_fixed`**:
  ```c
  void func_0x000123a0_fixed(void)
  {
    g_current_map_number = g_map4_special_flag._0_2_;
    FUN_00017760();
  }
  ```
  Confirms the earlier static read (`move.w D1,$17994`, i.e. writing into
  `g_current_map_number`) and gives it real content for the first time:
  it's copying the low 16 bits of `g_map4_special_flag` into
  `g_current_map_number`, then calling `FUN_00017760`. This is squarely
  in the map-transition/level-select cluster already covered by gap #33's
  writeup; `FUN_00017760` is a new callee not yet decoded.

Both fixes are mechanical/tooling only — no new gap opened beyond the two
new callees noted above (`FUN_000165a6`, `FUN_000165fc`, `FUN_00017760`),
which are minor/optional follow-ups, not required for the porting goal.
gaps.md item #2 marked resolved.
