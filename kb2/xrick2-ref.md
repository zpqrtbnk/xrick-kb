> **File role: TOPIC-ORGANIZED REFERENCE / KNOWLEDGE BASE.** This file is a
> derived index, not a log — it states the **current best-known facts** for
> each subsystem, organized by topic rather than by date. It was
> restructured on 2026-09-16 from an earlier chronological/dated-entries
> version (which mirrored [xrick2-wk.md](xrick2-wk.md) section-by-section)
> because that structure made it hard to see, at a glance, what's currently
> true about e.g. `ActorRecord` without reading a dozen dated updates that
> supersede each other. No fact from the old version was dropped — anything
> not restated in full here is still recoverable from `xrick2-wk.md` via the
> line-number pointers below.
>
> Each section below ends with **Evidence** (a pointer into `xrick2-wk.md`
> for full reasoning/addresses/decompiles) and, where relevant, **Open
> items** (a pointer into [xrick2-gaps.md](xrick2-gaps.md) for exactly what's
> still unconfirmed or unexplored on that topic — gaps.md is also where all
> contradictions found during the 2026-09-16 audit are documented, along
> with two `SUPERSEDED` annotations now present in `xrick2-wk.md` at the
> exact points they apply). Do not treat `xrick2-wk.md`'s dated, append-only
> narrative as superseded by this file — it remains the authoritative
> evidence log; this file is just a faster way to find the current answer.

## Getting oriented

For an agent picking this project up cold:

- **Ghidra project**: `xrick2-prg` (`ghidra.xrick2/xrick2-prg.gpr`).
- **Program to analyze**: `/prg2-ram.bin.0` — a full 1MB ST RAM snapshot
  imported into that project (see [RAM dump inventory](#ram-dump-inventory)
  for exactly what it captures and how it was made; the `.0` suffix is a
  historical artifact of the import, not meaningful).
- **RAM dumps on disk**: under `` in this repo (`prg2-ram.bin` plus
  two loader-moment snapshots) — these are the source `.bin` files the
  Ghidra program was imported from, kept for reference/re-import.
- **Standing scope constraint**: this effort exists to mechanically
  reproduce the game's **core logic** for a port — struct definitions,
  spawn/trigger tables, AI, physics, input. Render/blit and sound routines
  are explicitly **out of scope** and not gaps (see [Out of scope by
  design](#out-of-scope-by-design)).
- **Read next**: this file for current best-known facts by topic; drop to
  `xrick2-wk.md` for the evidence behind any claim; check `xrick2-gaps.md`
  for what's still open before doing new work on a topic.

## Table of contents

0. [Getting oriented](#getting-oriented)
1. [Booting RICK2.PRG in Hatari](#booting-rick2prg-in-hatari)
2. [RAM dump inventory](#ram-dump-inventory)
3. [Loader / `.HNK` pipeline](#loader-hnk-pipeline)
4. [Memory map & key globals](#memory-map--key-globals)
5. [Map / submap transition mechanics](#map--submap-transition-mechanics)
6. [Main loop dispatch](#main-loop-dispatch)
7. [`ActorRecord` struct](#actorrecord-struct)
8. [Spawn / trigger-table grammar](#spawn--trigger-table-grammar)
9. [`g_object_table` subsystem](#g_object_table-subsystem)
10. [Enemy AI: byte-code scripting VM](#enemy-ai-byte-code-scripting-vm)
11. [Player physics](#player-physics)
12. [Input handling](#input-handling)
13. [Tooling / methodology notes](#tooling--methodology-notes)
14. [Out of scope by design](#out-of-scope-by-design)

---

## Booting RICK2.PRG in Hatari

```sh
hatari --disk-a disks/chaos43_noauto.st --auto "A:\RICK2.PRG"
```

The cracked `RICK2.PRG` does raw floppy sector/track reads for its loader,
bypassing GEMDOS — so GEMDOS harddrive emulation (`--harddrive` + `--auto`)
boots but hangs on a black screen after the crack-screen keypress. Real
floppy emulation (`--disk-a` with an `.st`/`.msa` image) fixes that, but the
stock disk's `AUTO/MENU44.PRG` boot menu never returns control to TOS, so
`--auto` never fires. The fix used here: keep real floppy emulation, but
neutralize the AUTO-folder menu program so TOS falls through to `--auto`.

**How `disks/chaos43_noauto.st` was made** (already committed under
`disks/`, no need to redo): converted `disks/chaos43.msa` to a raw `.st`
sector image with `disks/tools/msa_convert.py` (a repo also has a full Rust
converter at `msa-to-st-converter/`), then used `mtools`' `mren` to rename
`AUTO/MENU44.PRG` → `AUTO/MENU44.DIS` directly on the raw image (TOS only
auto-executes `*.PRG`/`*.APP`/`*.TOS` in `\AUTO`, so the extension rename is
enough). `AUTO/DAT.PRG` (163 bytes, possibly a menu companion patch) was
left untouched.

**Automating the crack screen's "press a key" prompt**: boot with
`--cmd-fifo /tmp/hatari.fifo`, then after a few seconds' delay write
`echo "hatari-event keypress 57" > /tmp/hatari.fifo` (57 = Space scancode;
28 = Return, 0x1 = Escape, 15 = Tab, per Hatari's `tools/hconsole/hconsole.py`).
Confirmed to advance straight into the game intro.

**Files**: `disks/chaos43.msa` (original), `disks/chaos43_backup.msa`
(redundant backup), `disks/chaos43_noauto.st` (use this one to boot),
`disks/tools/msa_convert.py` (converter).

**Evidence**: `xrick2-wk.md` intro/boot sections, ~line 1-170 (includes the
`--cmd-fifo`-and-pausing gotcha — see [Tooling / methodology
notes](#tooling--methodology-notes)).

---

## RAM dump inventory

Full 1MB ST RAM snapshots (`hatari-debug savebin <file> $0 $100000` over
`--cmd-fifo`), all under ``:

| File | Captured | Trigger / condition | What it shows |
|------|----------|----------------------|----------------|
| `prg2-ram.bin` | ~20s after crack-screen keypress, free-running | Manual delay to let intro music/animation start | Turned out to be a live capture of the title-screen **attract-mode demo** (real map-1 gameplay, not just an intro) — this is the sample used for essentially all spawn-table/enemy-script/`ActorRecord` live validation described below |
| `dump_hnkload_hit1.bin` | 2026-09-11 15:45:59 CEST (~2.7s post-keypress) | `pc=$73f0 :once` (1st hit of `"LSD!"`-validated depacker entry) | `RICK_01.HNK` load moment; `A1=$0003EFC0`; VBL counter `$19232`=`0x0066` |
| `dump_hnkload_hit2.bin` | 2026-09-11 15:46:01 CEST (~4.4s post-keypress) | `pc=$73f0 :2 :once` (2nd hit) | `RICK_02.HNK` load moment; `A1=$00065300`; VBL counter=`0x00CE` |

A third armed breakpoint (`pc=$73f0 :3 :once`) never fired in ~45s —
only two loader invocations were observed in that window (see [Loader
gaps](#loader-hnk-pipeline) for whether later HNK pairs ever load the same
way). The two `hnkload` dumps are pre-gameplay loader snapshots with no
live actor table — `prg2-ram.bin` is the only dump with a live actor table.

Naming note (checked during the 2026-09-16 audit, **not** an
inconsistency): every dated section of `xrick2-wk.md` names the imported
Ghidra program for the primary dump `/prg2-ram.bin.0` consistently
end-to-end (the `.0` suffix comes from a stale duplicate import that was
still open in the Ghidra GUI at first-import time) — there is no later
silent drop of the suffix.

**Evidence**: `xrick2-wk.md` "RAM dumps captured" / "Pinpointing exactly
when RICK_01.HNK / RICK_02.HNK load" sections.

---

## Loader / `.HNK` pipeline

- **Depack entry**: `load_and_depack_hnk_file` @ `$7000`; validated entry
  point `$73f0` gated on a `"LSD!"` magic check; actual depacker
  `lz_depack_backward` @ `$7400` (backward, in-place LZ-style).
- **HNK resolution**: `resolve_hnk_id_by_checksum` @ `$11f86`,
  `load_hnk_pair_by_seed` @ `$11e76`.
- **Map loading**: `load_map` / `load_map_if_changed` @ `$123c4` / `$12394`.
- **Confirmed live loads**: `RICK_01.HNK` → `A1=$0003EFC0`, `RICK_02.HNK` →
  `A1=$00065300` (see [RAM dump inventory](#ram-dump-inventory) for exact
  capture conditions). Map 1 = `RICK_01`/`RICK_02`, map 2 = `RICK_03`/
  `RICK_04`, map 3 = `RICK_05`/`RICK_06`, map 4 = `RICK_07`/`RICK_08`
  (from `g_level_descriptor_table` @ `$12dd4`, static analysis).
- **Post-load decompress step**: `load_map`'s tail jumps to `$1795c`
  (`A0=$65300`, `A1=$53400`) — **not a relocate/merge step**; it's a
  **second, distinct depacker** (a Huffman-style bit-tree decoder,
  structurally unrelated to `lz_depack_backward`) that decompresses the
  monster-descriptor table (`DAT_00053400`) from a packed form staged at
  `$65300`. Resolved 2026-09-16 — see gaps.md gap #5.
- **Raw sector-read implementation**: the loader bypasses GEMDOS
  entirely with a hand-rolled FAT12 reader. `FUN_0000705e` (`$705e`)
  decodes a boot-sector/BPB-style disk-geometry structure into working
  globals; `FUN_00007136` (`$7136`) does an 8.3-filename directory search
  against a template buffer, then follows the FAT12 cluster chain
  (odd/even 12-bit nibble decode) copying `0x400`-byte clusters. Resolved
  2026-09-16 — see gaps.md gap #4. The shared low-level sector-read
  primitive both call, `FUN_00007282`, remains unexplored (low priority).
- **Input driver**: a from-scratch IKBD packet parser in
  `custom_keyboard_isr` @ `$1a546`, bypassing GEMDOS entirely, feeding
  `kbd_last_scancode` and two joystick state bytes.

**Evidence**: `xrick2-wk.md` "Live trace: who calls the depacker" (~line
357-461), "Open follow-ups from this investigation" (~line 741-754),
"Gap-resolution pass…" (2026-09-16) gaps #4/#5 subsections.

**Open items**: top-level `.HNK`-load-decision caller never found; whether
`RICK_03`-`RICK_08.HNK` load via the same routine unconfirmed; `RICK.PRG`'s
purpose (a second, 93KB executable on the disk) unexplored; whether
`$65300` double-serves as both the tile-ID map array (`g_tile_attribute_map`
was earlier misidentified as living here — see [Memory map & key
globals](#memory-map--key-globals) and [Player physics](#player-physics)
"Correction 2026-09-16" — it's actually at `$65200`) and the `$1795c`
depacker's packed-source buffer at different load stages is unreconciled;
the map-1→map-2 HNK load is inferred from static tables only, never
confirmed live. Full detail: **gaps.md section C, "Loader / HNK
pipeline"**.

---

## Memory map & key globals

| Global | Address | Role | Confidence |
|---|---|---|---|
| `g_current_map_number` | `$1239c` | current map index | confirmed |
| `g_loaded_map_number` | — | last-loaded map index, compared against current | confirmed |
| `g_level_descriptor_table` | `$12dd4` | map number → HNK file pair + level table offsets | confirmed |
| `g_submap_complete_flag` | `$115e0` | gates the map-advance instruction | confirmed (setter: `check_submap_exit_triggers`) |
| `g_actor_table` | `$16b6a` | 6-slot enemy table, `ActorRecord`-shaped | confirmed |
| `g_object_table` | `$167a2` | 4-slot secondary actor table, same struct | confirmed (see [g_object_table subsystem](#g_object_table-subsystem)) |
| `g_tile_attribute_map` | `$65200` | tile-collision attribute grid (was misidentified as `$65300` earlier in this project; `$65300` is actually the tile-ID map array — see [Player physics](#player-physics) "Correction 2026-09-16") | confirmed, rename/re-point pending |
| `g_enemy_spawn_table_ptr` | `$144c4` | current level's spawn table pointer | confirmed |
| `g_submap_trigger_table_ptr` | — | current level's Y-trigger table pointer | confirmed (name unreliable in `list_globals` — see [Tooling notes](#tooling--methodology-notes)) |
| `g_screen_exit_trigger_flag` | `$144c2` | screen-exit-transition-in-progress gate | confirmed; real address only found after `list_globals`/`get_xrefs_to` reported the wrong one (`$14590`) |
| `_DAT_00014592` | `$14592` | "submap transition in progress" flag, live only during one `scan_enemy_spawn_list()` call | confirmed |
| `DAT_00016462` | `$16462` | real scroll/camera-X global | confirmed |
| `kbd_last_scancode` | — | last IKBD scancode | confirmed |
| `_DAT_000115dc` | `$115dc` | `main_loop_body`'s own inner-loop continuation flag: reset to `0` inline in `main_loop_body` each outer pass, read in its own inner `while` condition, set non-zero by `dispatch_spawn_record`/`update_actor_ai` to abort/restart the current inner-loop pass | confirmed 2026-09-16 (was previously miscategorized as vestigial/dead — see gaps.md former-B12) |
| `PTR_DAT_000176f4` | `$176f4` | shared visual/sound-effect request slot (enemy death, wall-bump) | confirmed, out of scope (render/sound) |
| `_g_demo_mode_active` / `_g_demo_stream_end_flag` | `$3efb6` / — | gate an attract-mode/demo-playback branch in `main_loop_body` (skip live input, play back a recorded input stream); `_g_demo_mode_active` confirmed same global as `g_demo_mode_active` used by `attract_mode_handler` | fully resolved 2026-09-16, see [Input handling](#input-handling), gaps.md gap #33 |

Player sub-state flags (all in the `$12e14`-`$12e28` range) — see
[Player physics](#player-physics) for the full table with confidence
levels.

**Evidence**: scattered across `xrick2-wk.md`; the clearest single
consolidations are the "Game engine architecture" section (~line
179-197 equivalent narrative) and the various "Update (same day)" passes
in the 2026-09-14/15 sections.

---

## Map / submap transition mechanics

Two **distinct** screen-transition mechanisms exist — do not conflate them:

1. **Room-to-room (submap) transition**, driven by the submap-trigger
   table: `check_submap_exit_triggers` @ `$14362` decodes 4-byte records
   (byte0==0 terminates), triggering on a scroll-adjusted **Y** tile
   position (vs. the spawn table's **X** — see [Spawn/trigger-table
   grammar](#spawn--trigger-table-grammar)). Trigger-record byte0 bits
   select: submap index, screen-exit flag, submap-complete-vs-forced-push
   outcome. Bytes 2-3 of each trigger record have no game-logic reader
   found anywhere in the reachable call graph — tentatively "unused or
   rendering-only" (an absence-of-evidence conclusion, not a positive
   confirmation — see gaps.md B11/C14).
   - The "forced push" outcome is `FUN_00014434`: teleports the player's
     X position between `0` and `0xe8` (wrap to the opposite screen
     edge). It's called from the two submap-load routines
     (`FUN_00018abe`/`FUN_00018bb2`), which also drive
     `_DAT_00014592` (see [globals table](#memory-map--key-globals)) and
     the overall submap-transition sequence (background/scroll reset →
     one spawn-list seed → vblank-driven transition animation loop) —
     most of that sequence's individual helper calls remain undecoded
     (gaps.md C11).
   - The "softer" in-screen transition case (looks like a boss/star exit
     cutscene, distinct from full room teleport) is gated by
     `g_screen_exit_trigger_flag` @ `$144c2`: set by
     `check_submap_exit_triggers` (trigger byte0 bit `0x40`), read by
     `update_actor_slots` and `scan_enemy_spawn_list` (both alter/skip
     normal processing while set), and read+cleared by
     `handle_screen_edge_and_respawn` — the dedicated per-frame handler
     that runs the transition (actor repositioning, player-collision/
     death checks, trigger spawns) until complete, then resets the 5
     main actors for the new screen.
2. **In-screen horizontal camera scroll**: `FUN_00013d58`/`FUN_00013d0a`,
   called from `update_player_rick` when Rick walks into a screen-edge
   wall; sets `g_camera_scroll_active`.

**Per-level table format**: each level has an 8-byte header record
(bg-gfx offset, Y offset, trigger-table offset, spawn-table offset),
decoded in `FUN_00014458` (called only from the submap-load routines).
`FUN_00014542` is the level-init "seek past off-screen headers" routine.

Map 5 has no real HNK pair — it's wired to the loader's anti-piracy
checksum-chain trap, consistent with being an ending/finale pseudo-state.
Map 4's alternate handler (`$17bf4`) and map 5's special branch in
`main_loop_body` (`$10bf2`) are both special-cased but undecoded.

**Evidence**: `xrick2-wk.md` "Map/submap structure and the map-1→map-2
switch," "`_DAT_00014592` resolved," "`_g_screen_exit_trigger_flag`
resolved," "Per-level table loader decoded" sections (~line 2870-3100).

**Resolved 2026-09-16**: `FUN_0001726e` (actor-0 transition mover) is the
same byte-code movement-script VM reused against a dedicated
screen-transition state block, not a custom routine. Map-4/map-5 special
handlers resolved (`$17bf4` trivial demo-mode guard; `$10bf2` is just an
inline label, not a function). `FUN_00015b3c`'s canned-actor-restore
fully decoded; its paired counters `DAT_00015b38 = 0x14`/`DAT_00015b3a = 0`
are a plausible re-arm delay/countdown pair, though no reader was found.
Of the 8 undecoded submap-load helpers: `FUN_000170b6`/`FUN_0001709e`
(trivial `FUN_000170ce` wrappers), `FUN_00016630` (scroll sub-pixel
reset), and `FUN_000157b4` (trivial flag reset) are now decoded;
`func_0x00016474` is confirmed **blocked by a real Ghidra
auto-analysis gap** (a genuine tooling limitation, not unattempted);
`FUN_000188d0`/`FUN_00018b5c`/`FUN_00018c50` remain fully undecoded.

**Fully closed 2026-09-16**: `FUN_000188d0`/`FUN_00018b5c`/`FUN_00018c50`
confirmed as screen-scroll blit loops (render-adjacent, out of scope).
`func_0x00016474` root cause diagnosed precisely — raw bytes at `$16474`
(`48 E7 E0 E0`) are a valid `movem.l` prologue, but a pre-existing wrong
code-unit boundary at `$16476` in the Ghidra project blocks placing the
function there; a mechanical Ghidra fix (clear the code unit, re-
disassemble), not attempted with the tools available this pass.

**Open items**: trigger-table bytes 2-3 (needs a rendering-consumer
check); `func_0x00016474`'s actual behavior once the Ghidra housekeeping
fix is applied. Full detail: **gaps.md section C, "Map/submap
transition"**.

---

## Main loop dispatch

`main_loop_body` @ `$10a90` — a 50Hz VBL-paced frame loop with an
outer/inner loop structure: an **outer loop** (resets
`_g_camera_scroll_active`, runs forever) wrapping an **inner loop** that
runs the per-frame subsystem calls and continues `while
(_DAT_000115dc == 0)`. `_DAT_000115dc` is reset to `0` inline in
`main_loop_body` itself right after the submap-complete/normal-frame
branch, each outer pass — it's `main_loop_body`'s own inner-loop
continuation flag, set non-zero elsewhere (`dispatch_spawn_record`/
`update_actor_ai`) to abort/restart the current inner-loop pass. Resolved
2026-09-16 (previously miscategorized as vestigial — see gaps.md
former-B12).

Confirmed pieces: lives/game-over check gating `FUN_000149c2` (death
sequence, calls `FUN_000149f0` 10 times to clear per-slot "used" flags)
and `FUN_000142fc` (submap reload/respawn routine — resets Rick's
position/facing/flags, re-runs the per-level loader chain, re-scans the
enemy spawn list); the map-advance trigger logic (with the map-4/map-5
special cases above — `$17bf4` is a trivial demo-mode guard, `$10bf2` is
just the inline label `LAB_00010c00`, not a separate function); calls
into `load_map_if_changed`, `update_player_rick`, `update_actor_slots`,
`update_object_slots`, `scan_enemy_spawn_list`, `check_submap_exit_triggers`,
and others documented per-topic elsewhere in this file.

`FUN_000170b6`/`FUN_0001709e` are trivial wrappers around `FUN_000170ce`
→ `FUN_000170d4`/`FUN_000170f2`, together an edge-latched per-actor
one-shot sound/effect trigger scan (sound-adjacent, mechanism understood,
not renamed). `FUN_000191e6` is **not** an infinite loop — real
disassembly shows a bounded, VBL-interrupt-synced delay-wait: busy-waits
on the `$19232` VBL counter against a target derived from `$18ed8`, then
resets the counter to `0`. Both resolved 2026-09-16.

**Newly discovered (2026-09-16), previously undocumented**: a
demo/attract-mode playback subsystem — `_g_demo_mode_active` and
`_g_demo_stream_end_flag` gate an entire alternate branch (skip live
input, play back a recorded input stream, exit on a real fire-press or
stream exhaustion) with ~9 undecoded gated callees. See gaps.md gap #33.

**Not yet found**: the true top-level caller of `main_loop_body` itself
(the actual VBL-synced dispatcher), and of `load_map_if_changed` each
frame — `get_function_callers`/`get_xrefs_to` both return zero results
for both, consistent with the documented xref-indexing-gap tooling
caveat rather than proof of "no callers."

**Evidence**: `xrick2-wk.md` "The main loop, precisely" section (~line
654-801); "Gap-resolution pass…" (2026-09-16) section.

**Open items**: full detail in **gaps.md section C, "Main loop dispatch"
and gap #33**.

---

## `ActorRecord` struct

88 (`0x58`) bytes, applied as a Ghidra struct to both `g_actor_table` (6
slots) and `g_object_table` (4 slots — see [g_object_table
subsystem](#g_object_table-subsystem) for how that table's struct usage
diverges past offset `0x10`). All offsets below are **byte offsets**,
established via raw 68000 disassembly (not decompiler pointer arithmetic —
an earlier word-offset reading of one field was a decompiler artifact; see
gaps.md A2 for the full contradiction writeup and its `SUPERSEDED`
annotation in `xrick2-wk.md`).

**Confirmed / named fields** (partial — see `xrick2-wk.md` for the
complete table with all ~48+ named offsets):

| Offset | Field | Notes |
|---|---|---|
| `0x00` | `state_flags` (byte) | occupancy/death-state; see combined-word occupancy test below |
| `0x01` | `behavior_flags` (byte) | per-type behavior bitmask |
| `0x02` | `x` (word) | world X position |
| `0x06` | `y` (word) | world Y position |
| — | `anim_frame` | current animation frame |
| — | `explosion_done_flag` | shared with object-table layout |
| `0x3a` | `move_delta_x` (was `prev_x`) | per-frame movement **delta**, not a position — renamed for accuracy |
| — | `move_delta_y` (was `prev_y`) | same correction |
| — | `bState_flags`, `bBehavior_flags` | occupancy + behavior; **occupancy test is the combined 16-bit word `bState_flags:bBehavior_flags != 0`**, not either byte alone (an earlier note implying single-byte occupancy is now marked `SUPERSEDED` in wk.md — see gaps.md A1) |
| — | `bBehavior_flags_alt`, `nMove_script_ptr_alt`, `nAnim_script_ptr_alt` | the "alt" half of the dual behavior-profile |
| — | `nMove_script_ptr`, `nAnim_script_ptr` | primary move/anim byte-code script pointers |
| — | `nSecondary_data_ptr` | points back into the spawn table |
| — | `nFacing_flag` | from detail-block byte3 bit `0x80` |
| `0x3e` | `nSpawn_anim_frame` (candidate name) | spawn-time copy of initial `anim_frame`; usage elsewhere unconfirmed |
| `0x54` | (unnamed) | derived only for type-category-1 monsters, `(detail.byte3&0x3c)*2+8` — candidate hit-points/cooldown/death-duration field |
| `0x2f`, `0x31` | (unnamed) | concluded **alignment padding** — zero accesses found anywhere in the reachable actor/object AI + construction call graph (each sits next to a 4-byte pointer field) |
| `0x3e-0x4d`, `0x50-0x57` | mostly spawn-time-zeroed scratch | confirmed unused by actual enemy logic; object-table-only state that happens to share the record's tail |
| `0x08`, `0x0a`, `0x0c` | constants at spawn (`0`, `2`, `0x100`) | purpose of the non-zero constants not identified |
| `nUnk04`, `aUnk1c` (28-29), `aUnk24` (36-37) | still fully unnamed | no reader found anywhere reachable; static-analysis dead end absent a live sample with active enemy scripts touching them |

**Key mechanism — dual behavior-profile swap**: every actor slot carries
two complete behavior profiles (behavior flags + move-script pointer +
anim-script pointer); one atomic operation in `update_actor_ai` swaps
which is active (`bBehavior_flags`↔`bBehavior_flags_alt`,
`nMove_script_ptr`↔`nMove_script_ptr_alt`, `nAnim_script_ptr`↔
`nAnim_script_ptr_alt`) — this is the mechanism behind two-phase enemies
(patrol↔chase, reverse-at-wall, etc.), with no runtime recomputation.

**Rick's hitbox** (via `check_box_vs_player` @ `$14b7a`): 16px wide (inset
4px from origin), 21px tall standing, ~5px tall crouching.

**Evidence**: `xrick2-wk.md` "Actor record struct, verified by
disassembly" (~line 1336-1408), "Dual behavior-profile swap confirmed
field-by-field," "Actor-init helpers checked," "Last two player flags
named," "`FUN_00014862` fully decoded" (~line 3197-3271), "`FUN_000150c0`
decoded" (~line 3438-3491) sections.

**Open items**: remaining unnamed blobs, live validation of the
type-`<0x75` descriptor path, live validation of
`dispatch_spawn_record`'s detail-block path, whether unused trailing
detail blocks are read by anything, `extraout_A1` register provenance,
byte `0x54`/LUT semantics. Full detail: **gaps.md section C,
"ActorRecord/actor system" (6 items)**, plus assumptions **B5-B6, B8,
B10, B13-B14**.

---

## Spawn / trigger-table grammar

**Record format** (both spawn table and submap-trigger table share this
base grammar): a 4-byte **header**, terminated by `byte0==0`, optionally
followed by 0-3 trailing 4-byte **detail blocks** — the count is encoded
in the header's own byte3. (An earlier "flat 4-byte record" reading was
mis-segmented; re-walked with this corrected grammar, a 256-byte live
sample yields a clean 13-entry spawn table terminated at offset `0x5c`.)

**Dispatch branches on the same 4-byte grammar — two genuinely different
record kinds, kept deliberately separate here to avoid the conflation the
project explicitly flagged as a risk:**

### Monster-spawn path (`byte2&0x80 != 0` → `FUN_00014636` → `FUN_000146a0` / `FUN_00014862`)

- Header: byte1=Y, byte2=X-subposition (top bit is the path selector),
  byte3 used as **`byte3&0x3c`, a 4-way move-script-source switch**:
  `0x20` → fixed hard-coded move script `DAT_0001466e` (or
  `DAT_0001468a` on map 4 only — shared "elevator"-style behavior);
  `0x28`/`0x2c` → null move-script pointer (no-movement actor); default →
  real per-type monster-descriptor-table lookup.
- `FUN_00014636` dispatches on a detail block's byte0 as an enemy-type ID
  into one of four construction routines — the real "spawn record → live
  `ActorRecord`" boundary.
- **Monster-type descriptor table** `DAT_00053400` (indexed by type ID,
  self-relative `int16` offsets): gives each type's width, height,
  behavior-flag bits, and both script-pointer pairs (primary + alt).
  Near-ready "monster type definition" record for a port — **but only
  exercised via `FUN_00014862`'s simpler path in every live sample so
  far; the `FUN_000146a0` branch for type IDs `<0x75` has never fired
  against real data** (gaps.md B6/C17).
- De-spawn: `FUN_00014a12` deactivates the slot and clears the source
  record's "already spawned" bit, unless detail byte3 bit `0x40` says
  "one-shot, never respawn."

### Trigger/effect path (`byte2&0x80 == 0` → `dispatch_spawn_record`)

- **Not** a monster constructor. Walks a header's own trailing detail
  blocks and reads **each detail block's byte3 as an independent 8-bit
  bitmask of trigger/collision conditions** — vs.-player, vs.-falling,
  vs. the 4-slot `g_object_table`, vs. the main actor table — each
  optionally firing a visual/sound effect via `FUN_0001a6aa`.
- **This byte3 is unrelated in meaning to the monster-spawn path's
  `byte3&0x3c` switch above**, despite both living in the same bit
  position of the same 4-byte grammar. The document itself flags this
  explicitly; this section exists specifically to keep the two from ever
  being merged into one "byte3 means X" statement. Never fired against
  live data either (gaps.md B7/C18).
- Rick's weapon-fire cooldown timer (`g_player_fire_cooldown`) is the
  gate for the "shootable target" spawn trigger — resolved, though the
  function itself is left un-renamed (`spawn_trigger_variant_c`) pending
  positive confirmation against real table data (gaps.md B9).

**Submap-trigger table** (distinct table, same base 4-byte grammar,
triggers on **Y** not **X**) is documented separately under [Map/submap
transition mechanics](#map--submap-transition-mechanics) — do not confuse
its byte0 bit meanings with either spawn-table branch above.

**Evidence**: `xrick2-wk.md` "Spawn table record grammar corrected"
(~line 2358-2539), "`FUN_00014a12`/`dispatch_spawn_record`" section
(~line 3287-3361), "`FUN_000146a0` fully decoded" (~line 3106-3196).

**Open items**: live validation of both unvalidated branches; records
22+ of the sampled spawn-table stream parse ambiguously (including a
repeating sub-pattern at records 46-53 of uncertain significance); no
bulk validation beyond one map-1 sample. Full detail: **gaps.md section
C, "Spawn/trigger-table grammar" (2 items)** plus **B6-B7, B9**.

---

## `g_object_table` subsystem

A real, independent 4-slot secondary actor table at `$167a2`, sharing
`g_actor_table`'s exact 88-byte `ActorRecord` stride and several leading
field offsets (x, y, anim_frame, explosion_done_flag) — but a genuinely
different struct usage past offset `0x10`: hardcoded per-type motion
instead of the script-VM pointers enemies use. Has its own free-slot
scanner (`FUN_00014970`) and per-frame update loop
(`update_object_slots`/`FUN_000150c0`) — the latter handles gravity, tile
collision, three per-object-type movement patterns, and the despawn path;
confirmed to be a dropped-item/projectile/falling-hazard subsystem
distinct from the main actor AI.

**Construction site resolved 2026-09-16**: there is no generic
object-spawn constructor analogous to `FUN_00014636`. The *only* place
anything writes a fresh `g_object_table` entry is hand-inlined directly
into `handle_screen_edge_and_respawn`'s `LAB_00015cc8` block, reached
when a screen-edge transition finishes: it plants a `g_object_table[0]`
entry at Rick's post-transition position, field-by-field at fixed
offsets, paired with a sound-effect call (`FUN_0001a6aa`, sound-ID from
`FUN_00017810`). Per-field game meaning of the planted constants
(`0x4b` init anim-frame, etc.) not decoded further — mechanism, not
semantics, is confirmed.

`ActorRecord+0x54` is confirmed (already resolved before the 2026-09-16
pass, but only cross-referenced back into gaps.md during it): the
oscillation *period* for this table's type-1 "oscillate between two X
bounds" movers, read by `FUN_000150c0` from a counter pair at offset
`0x29`/`0x2a`.

**Evidence**: `xrick2-wk.md` "`g_object_table` confirmed," "`FUN_000150c0`
decoded" sections (~line 3420-3491); "Gap-resolution pass…" and "Second
gap-resolution batch…" (2026-09-16).

**Open items**: none remaining in gaps.md section C for this subsystem —
the low-priority per-field semantic meaning of the planted object noted
above is the only loose end.

---

## Enemy AI: byte-code scripting VM

`update_actor_ai` @ `$14d70` — the per-enemy-slot update — is not
hand-written per-enemy-type logic. Each actor carries two small
**data-driven byte-code scripts** (movement-delta script, animation-frame
script), interpreted generically by `advance_actor_move_script` @ `$172fa`
and `advance_actor_anim_script` @ `$171bc`. Both formats support looping
(patrol cycles) and embedded sound-effect triggers gated on
`is_actor_onscreen` @ `$14998`. Enemy death is a switch to a different
(explosion) animation script; enemy-vs-player kill contact is resolved
here, not inside the player's own update.

Both script formats were decoded to the exact opcode level and confirmed
byte-for-byte against one real enemy's live script data, including a full
patrol-loop cycle, from the `prg2-ram.bin` sample.

**Evidence**: `xrick2-wk.md` "Enemy AI: a byte-code scripting VM per
actor" (~line 1280-1408), "Move/animation script opcode formats decoded"
(~line 2358-2539 area).

**Open items**: none beyond the general "only one map-1 sample validated"
caveat in [Spawn/trigger-table grammar](#spawn--trigger-table-grammar).

---

## Player physics

Driven by `update_player_rick` @ `$13096`: position/velocity/animation
globals, tile-collision query, per-map hard-coded physics constants.
`read_player_input` @ `$141cc` (called at the top) is the whole input
abstraction — see [Input handling](#input-handling).

**Confirmed flags/fields**: `g_player_forced_push_flag` (scripted
screen-edge push), `g_player_on_stairs_flag`, `g_player_fallobj_trigger_flag`,
`g_player_dead_flag`/`g_player_death_trigger` (gate Rick's death-fall/
particle-burst code — an earlier note calling these an unnamed "movement
override" was simply wrong and is self-corrected in wk.md),
`g_player_facing_dir` (holds a step delta, not a boolean — an earlier
guess that this was a ladder flag was also self-corrected in wk.md),
`g_player_wall_push_flag`, `g_player_scroll_pending_flag`,
`g_player_stairs_variant_map4_flag`/`g_player_stairs_variant_map2_flag`
(confirmed via xrefs to be stairs-animation-speed selectors — why maps 2
and 4 specifically need a different cycle length was never chased),
`g_camera_scroll_active` (set by the horizontal-scroll trigger pair, see
[Map/submap transition](#map--submap-transition-mechanics)).

**Lower-confidence flags** (hedged in the original analysis, not yet
independently re-confirmed):

| Flag | Address | Confidence |
|---|---|---|
| `g_player_wall_contact_flag` | `$12e24` | plausible, not fully confirmed |
| `g_player_ceiling_blocked_flag` | `$12e16` | plausible, single call site only |
| `g_player_airborne_flag` | `$12e1c` | less certain — single call site, surrounding code more about scroll-delta bookkeeping than an obvious jump/fall test |

**Collision**: `query_tile_and_actor_collision` @ `$15fba` — a single
unified primitive for both terrain and nearby-actor overlap (via
reusable `aabb_overlap_test` @ `$161ce`); there's no separate "hit an
enemy" vs. "hit a wall" code path. **Correction 2026-09-16**: the two
fixed base addresses are the other way around from how they were
previously labeled here — `$65200` is the **tile-attribute lookup table**
(indexed by tile-ID byte, via `or.b (0,A0,D4w*1),D0` where `A0=$65200`
and `D4`=the tile ID), and `$65300` (`compute_tile_map_ptr` @ `$1643e`'s
base) is the **tile-ID map array itself** that gets indexed by world
position to find which tile ID to look up. `g_tile_attribute_map` should
refer to `$65200`, not `$65300` — rename pending.
`g_collision_result_flags` bit meanings are only partially inferred (bit
`0x20`=died/trapdoor, `0x02`/`0x04`=blocked direction, `0x08`/`0x10`=
ledge/step detection, `0x40`=teleport-to-explicit-position) — never
confirmed with a live watchpoint.

**Probe geometry, mostly resolved 2026-09-16**: the per-probe-direction
offset table is 3 *literally adjacent* tile-map bytes per row (X tap
position = `(g_collision_probe_x+4)>>3`, i.e. tile-column granularity),
across 2 or 3 rows gated by `g_collision_probe_y&7<4`, all rows sharing
a uniform 33-byte pitch. Still open: the exact semantics of
`compute_tile_map_ptr`'s Y-term (`(probe_y&~7)*4`) — whether `$65300` is
a flat per-column array at an unexpectedly narrow row stride or an
indirect per-row descriptor table; low priority since the effective
33-byte pitch is already confirmed and is what a port actually needs.

Death-fragment spawn (into an 88-byte-slot table) is effects content,
ruled out of scope.

**Evidence**: `xrick2-wk.md` "Input abstraction and tile/actor collision,
decoded" (~line 1026-1161), "Stairs state machine decoded" (~line
1925-1988), "Effects-slot corrected, four player flags named" (~line
1852-1870), "Last two player flags named" (~line 2119-2132), "Gap #26
partially resolved: collision probe's exact tap geometry" (2026-09-16)
sections.

**Open items**: `g_collision_result_flags` bit meanings need a live
watchpoint to confirm; `$65300`'s exact row-addressing semantics;
`g_tile_attribute_map`'s address needs correcting to `$65200`. Full
detail in **gaps.md section C, "Player physics" (3 items)**, plus
assumptions **B2-B4**.

---

## Input handling

`read_player_input` @ `$141cc`: in normal play returns the live joystick
state byte directly; in attract-mode demo playback it instead decodes the
same byte from an RLE-encoded recorded stream (selected by
`g_demo_mode_active` @ `$3efb6`) — confirming `attract_mode_handler`
really is the title-screen demo driver, sharing all the same player logic
as real gameplay (this is exactly the mechanism that made the
`prg2-ram.bin` "intro" dump usable as a real live-gameplay sample —
see [RAM dump inventory](#ram-dump-inventory)).

Raw hardware input: `custom_keyboard_isr` @ `$1a546` (from-scratch IKBD
parser, no GEMDOS) feeding `kbd_last_scancode` and two joystick state
bytes.

**Evidence**: `xrick2-wk.md` "Input abstraction and tile/actor collision,
decoded" section (~line 1026-1161).

**Resolved 2026-09-16**: `FUN_000161fe` is a combined tile+hazard-actor
collision probe (tile-attribute lookup via `compute_tile_map_ptr`, plus —
if tile bit `0x02` isn't already set — a scan of `g_actor_table` for
occupied "hazard" actors via `point_in_box_test`, OR-ing bit `0x02` into
`g_collision_result_flags` on a hit). Not a sprite/placement table as
guessed.

**Cross-reference note, confirmed 2026-09-16**: `main_loop_body`'s
demo-playback branch (`_g_demo_mode_active`/`_g_demo_stream_end_flag`)
uses the **same** `g_demo_mode_active` global documented here for
`read_player_input`/`attract_mode_handler` — confirmed by address via
`get_xrefs_to(0x3efb6)`, not just name-matched. Not a second, unrelated
flag; extends the known mechanism into the main loop.

**Gap #33 fully resolved 2026-09-16**: all 9 gated callees decoded.
8 are a menu/attract-mode UI cluster: `func_0x00017a46` is a
joystick-driven level-picker screen (writes `g_map4_special_flag`);
`func_0x0001771c` resets its shared scratch state; `func_0x0001789a`
is a sound-sequence-wait helper; `func_0x00017bda` plays a fanfare +
render-adjacent effect on non-demo completion; `func_0x00017c06` is a
generic "press fire to continue" prompt; `func_0x00017f22` is a
5-character name-entry screen containing a genuine **"POOKY" cheat
code** — typing that name sets a flag (`$1798e`) that unlocks the
manual level-picker in `func_0x00017a46`; `func_0x000178dc` is the
demo/attract-mode *entry* sequencer (confirms `_g_demo_mode_active`'s
setter). `func_0x00010c28` is unrelated — a one-shot hardware-vector-
backup routine, out of scope. The 9th, `func_0x000123a0`, is blocked
by a **second confirmed instance** of the `func_0x00016474` Ghidra
code-unit-boundary bug (see "Map/submap transition mechanics" section)
— known fix, not yet applied.

**Open items**: keypress-detection mechanism for the crack screen itself
only pattern-matched, never traced end-to-end; `func_0x00018186`,
`FUN_0001793a`, `FUN_00017e40`, `FUN_00017c86` (new callees surfaced by
the gap #33 decode, still unexplored — demo record/playback primitives
and a render-adjacent effect, low-to-moderate priority); live
confirmation of the "POOKY" cheat's on-screen behavior. Full detail:
**gaps.md section C, "Input"** and **"Demo/attract-mode subsystem"**.

---

## Tooling / methodology notes

- **`list_globals`/`get_xrefs_to` unreliability.** Documented at least 3
  times against real, already-named symbols
  (`g_submap_trigger_table_ptr`, `g_screen_exit_trigger_flag`'s real
  address `$144c2` vs. the wrongly-reported `$14590`) — these tools can
  silently miss real references. Always cross-check with `audit_global`
  or `get_function_pcode` before concluding a symbol is unread/unnamed.
- **Ghidra raw-dump auto-analysis gaps.** Large swaths of code can be left
  un-disassembled with no recorded xrefs even when the decompiler walks
  the function correctly; `disassemble_function`/`get_function_by_address`
  can report a degenerate 1-byte body for such a function (seen on
  `check_submap_exit_triggers` and `FUN_000146a0`). Prefer
  `get_function_pcode`/`decompile_function` over raw disassembly-listing
  tools when a function looks like it has "0 xrefs" or "empty"
  disassembly.
- **Decompiler pointer-width artifacts.** The decompiler can silently
  scale struct-field offsets differently depending on inferred pointer
  width across different call sites for the same struct — this produced
  a real, now-`SUPERSEDED`-annotated contradiction in the `ActorRecord`
  field table (gaps.md A2). Prefer raw 68000 disassembly to settle
  byte-vs-word offset questions.
- **Hatari `--cmd-fifo` gotchas**: `hatari-stop` can deadlock a scripted
  fifo session (emulation must be left running, not paused, while
  issuing fifo commands); killing a stuck Hatari process can unlink its
  fifo special file out from under a *different* still-running instance,
  after which a shell redirect into the now-missing path silently creates
  a regular file instead of erroring (symptom: fifo commands stop working
  with zero error output — check `ls -la` shows `prw-------` for a real
  fifo).
- All RE work in this project uses **Ghidra MCP tools exclusively** for
  disassembly/decompilation — never raw byte inspection or other
  disassemblers.

**Evidence**: `xrick2-wk.md` "Gotcha: Hatari's `--cmd-fifo` and pausing
don't mix well" (~line 151-170), and the two `list_globals`/xref-gap
sections cited above (~line 2540-2602, 2925-2958).

**Open items**: none — these are process notes, not gaps. Full context in
**gaps.md section C, "Tooling / methodology caveats" (3 items)**.

---

## Out of scope by design

Explicitly excluded from this reverse-engineering effort's scope
(game-logic-only focus) — **not gaps**, do not treat as unfinished work:

- Render/blit routines — never located among traced per-frame calls, not
  pursued.
- `FUN_0001a6aa`'s sound-effect-ID parameter meaning.
- `PTR_DAT_000176f4` (shared visual/sound-effect request slot).
- Death-fragment/particle-burst spawn content.

See **gaps.md section C item 32** for the full callout (this exists so
none of these look like accidentally-missed work when scanning for open
items).

---

## See also

- [xrick2-wk.md](xrick2-wk.md) — full chronological evidence log; append-only,
  never edited except for `SUPERSEDED` annotations at the two contradiction
  points documented in gaps.md section A.
- [xrick2-gaps.md](xrick2-gaps.md) — consolidated contradictions (A),
  unverified assumptions (B), and genuine knowledge gaps by subsystem (C),
  produced by the 2026-09-16 documentation audit.
