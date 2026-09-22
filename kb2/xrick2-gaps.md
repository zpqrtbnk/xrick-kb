# RD2 — gaps and open questions

**Rewritten 2026-09-22 — superseded content removed.** This file was a snapshot of the 2026-09-15/16 audit of the
*decompiler-era* pass (`xrick2-wk.md`'s first ~3500 lines). Almost everything it listed — the loader, the main loop,
every table format, every script, the actor/object/player logic, the map-count/"level 5" question — was independently
re-derived from raw 68000 disassembly during the 2026-09-19→22 pass and now lives in `kb2/algo-actors.md`,
`kb2/algo-objects.md`, `kb2/algo-player.md`, `kb2/algo-flow.md`, `kb2/level-tables.md`, `kb2/graphics.md`,
`kb2/hnk-system.md`, and `PLAN.md` (T24, T26–T28, T30–T33, T35–T39). Those are current; this file's old row-by-row
detail is not, and the full historical reasoning for each (if wanted) is preserved in `xrick2-wk.md` (append-only)
rather than repeated here. Below: the current, accurate list of what is genuinely still open, then a compact map from
each of this file's old sections to where its content now lives.

## Current open items (2026-09-22, after the final static pass *and* live validation)

**All static items, and all four remaining live-run items (kb2 gaps #3/#4/#5/#7), are closed.** T30–T33/T37/T38 and every `graphics.md` §7 item were answered on 2026-09-22 (string/list-draw formats, the
demo-input path, the slide blits and `$188d0`, `$1a5d0` and the per-map music ids, the block-map margin proof, palette colour 1, the title/UI banners now extracted to PNG, the HUD icon-row mapping).
The user then lifted "no live run for now" specifically to close the last four; `kb2/hatari_live_validate.py` captured maps 2/3/4 in real attract-mode play (evidence: `kb2/assets/live_validation_2026-09-22.json`)
and confirmed, live: the type-`<0x75` monster-descriptor path firing (`algo-actors.md` §3), `dispatch_spawn_record`'s trigger-path branch firing (`level-tables.md` §3), every collision-probe result byte
decomposing into the documented bits (`algo-actors.md` §6), and 20/21 live actor script pointers landing exactly on a decoded script boundary. **What's left, both low priority and parked, neither blocking:**

| Item | Kind | Doc |
|---|---|---|
| Where `RICK2.PRG` stores the shared sprite banks before unpacking (extraction already works regardless) | Static, low priority | `PLAN.md` T39 |
| How `RICK_05.HNK` came to hold the wrong 512 bytes — a Copylock-weak-sector hypothesis is evidence-consistent but not provable without the physical disk (correct bytes already recovered from elsewhere) | Static, parked | `hnk-system.md` §6, `PLAN.md` T36 |
| One live actor sample (map 2, kind 89, frame 99) whose script pointer didn't match any decoded boundary | Curiosity | `algo-actors.md` §3 |

**Static and live reverse-engineering of Rick Dangerous 2 are both complete.** Nothing here blocks starting the port.

## Where the old sections went

### Consolidated table (28 rows, 2026-09-16) and its "2026-09-18 correction"

All loader/HNK questions (top-level load caller, whether maps 3–8 load through the same routine, `RICK.PRG`'s purpose,
the FAT12 reader, the two depackers, live confirmation of map transitions) — answered in full, `kb2/hnk-system.md`.
Main-loop dispatch, `main_loop_body`'s true entry (renamed `game_main`) and its callers — answered, `PLAN.md` T24
"second pass" (the boot-code return-address trick at `$10000`/`$1010c`). `ActorRecord` remaining fields, the
monster-descriptor table, spawn/trigger grammars, the object table, tile-attribute bit meanings — all re-derived from
disassembly with real addresses in `algo-actors.md`/`algo-objects.md`/`level-tables.md`. The "2026-09-18 correction"
that Hatari doesn't need MCP integration and can be driven from Bash is still true and is exactly what
`kb2/hatari_rd2.py` does now.

### A. Contradictions found (3 items)

All three were about decompiler-derived claims (`ActorRecord` occupancy test, a word- vs byte-offset field, an
address off-by-one) in the pre-2026-09-19 write-up. That whole write-up was replaced, not patched, so these
contradictions no longer have anything to be contradictions *about* — the current field tables in `algo-actors.md`/
`algo-objects.md` were built directly from disassembly, not decompiler output, per the user's standing "no
decompiling to C" rule.

### B. Unverified / hedged assumptions (14 items)

| Old item | Now |
|---|---|
| Crack-screen keypress detection | `algo-flow.md` §3 (`$178dc`, `$17c86`) — fully traced |
| `g_player_wall_contact_flag`/`ceiling_blocked`/`airborne` (old names) | `algo-player.md` — every flag named from its real address and every consumer read |
| `extraout_A1` / monster-descriptor pointer reuse | Moot — `algo-actors.md` §4 built from real disassembly, not decompiler register tracking |
| Monster-descriptor table format, type IDs `< 0x75` | Decoded in full, `level-tables.md` §4 — **still not live-validated**, carried forward above |
| `dispatch_spawn_record`'s trigger path | Decoded in full, `algo-actors.md` §4 — **still not live-validated**, carried forward above |
| `nSpawn_anim_frame` / `ActorRecord+0x3e` | Named and its reader confirmed, `algo-objects.md`/`algo-actors.md` |
| "Shootable target trigger" naming | Superseded — `algo-actors.md` §4 names trigger-box condition bits directly from the code, no game-level name invented |
| `ActorRecord+0x2f`/`+0x31` padding; submap-trigger bytes 2–3 | Re-derived; `level-tables.md` §2 states exactly what each trigger byte does |
| `_DAT_000115dc`, `ActorRecord+0x54`, `DAT_00014854` | Resolved in the 2026-09-16 pass itself (already marked done there); carried into the current docs under new addresses/names |

### C. Genuine knowledge gaps (33 items across 8 subsystems)

| Subsystem | Now |
|---|---|
| Loader / HNK pipeline (6) | `hnk-system.md`, all sections — format, loader, both depackers, file pairing, map count |
| Main loop dispatch (4) | `algo-flow.md` §1–§2 — full `game_main` skeleton and its entry from the boot code |
| Map/submap transition (5) | `algo-flow.md` §9 (submap transition), §10 (the 5-actor group, née "slot 5 homing hazard" — same mechanic, now fully transcribed) |
| `ActorRecord`/actor system (6) | `algo-actors.md`, complete field table and `update_actor_ai` transcription |
| Spawn/trigger-table grammar (2) | `level-tables.md` §2–§3, chain-verified over all 58 submaps |
| `g_object_table` subsystem (1) | `algo-objects.md`, complete |
| Player physics (3) | `algo-player.md`, complete |
| Input (1) | `algo-player.md` §1, `algo-flow.md` §5 (demo streams) |
| Demo/attract-mode subsystem (incl. the "POOKY" cheat) | `algo-flow.md` §3–§4, §11 — the cheat, the picker, the name-entry screen, all with current addresses |

### Tooling / methodology caveats — still valid, kept

- `list_globals`/`get_xrefs_to` can silently miss real symbols or references; cross-check with `get_function_pcode` or a byte-pattern search before concluding something is unread. Confirmed repeatedly across this and later sessions.
- Ghidra's raw-dump auto-analysis can leave code un-disassembled with no recorded xrefs, or report a degenerate function body; prefer re-disassembling a suspicious range over trusting "0 xrefs" as proof of dead code.
- Hatari's `--cmd-fifo` automation has real gotchas (don't pause while issuing fifo commands; a killed Hatari can leave a stale fifo path). `kb2/hatari_rd2.py` uses the simpler `--parse`/`--run-vbls` batch style instead and has not hit these.

### Out of scope by design → later brought into scope and finished

Render/blit and the sound-effect dispatch were explicitly out of scope in 2026-09-16. Both were later brought into
scope by the user and finished: sound in an earlier session (`sound-ref.md`, `rick2_sfx.sndh`), rendering in the
2026-09-19→22 pass (`graphics.md`). Nothing here is still "deliberately deferred."
