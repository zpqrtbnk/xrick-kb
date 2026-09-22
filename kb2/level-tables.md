# Rick Dangerous 2 — per-submap trigger and spawn tables, monster types

Extracted by `kb2/extract_tables.py` into `kb2/assets/levels/tables.json`. Everything here was checked on
2026-09-19 against the disassembly (Ghidra, `prg2-ram.bin`) and the four level images; "unverified" marks the rest.
Locations are level-image offsets (`address − $53400`). Layout of the images: `graphics.md` §3a.

## 1. Where the tables are

The **submap header table** (image `0x1800`, 8 bytes per submap) gives, per submap: block-map offset, max scroll ÷ 8,
**trigger table offset** and **spawn table offset** (both relative to `0x1800`). Header count per map = first trigger
offset ÷ 8: **17, 14, 14, 13** for maps 1–4.

**Chaining check (all 58 submaps, 4 maps, 0 exceptions):** `trigger_i` ends exactly where `spawn_i` starts, and
`spawn_i` ends exactly where `trigger_{i+1}` starts; the last spawn table ends at `0x1c9a`, `0x1e70`, `0x1f38`,
`0x1f42`. This is what confirms the two grammars below.

## 2. Trigger table (`check_submap_exit_triggers` `$14362`, pointer `[$1435c]`)

Records of **4 bytes, ended by a single `00` byte** (`move.b (A0),D2 / beq`). Per record (from the code):

| byte | use |
|---|---|
| 0 | bits 0–1 must equal `[$14360]` for the record to be considered; bit 5 → `[$12e14] = -1`; bit 6 → `[$144c2] = 1` (arms the 5-actor group, `algo-flow.md` §10); **map complete** (`[$115e0] = -1`, `game_main` `$10ad2`) when `(b0 & $90) == $90` while `[$17990] == 0`, or when `b0 & $80` while `[$17990] ≠ 0` (`[$17990]` = the cheat-only "16 BIT LONG GAME" / "08 BIT SHORT GAME" switch, `algo-flow.md` §4) |
| 1 | **Y tile** compared with `((scroll & ~7) + [$16960] + $14) >> 3` (`[$16960]` = Rick's Y) |
| 2 | **target submap** — **all 106 records have a value below the map's header count** (checked) |
| 3 | target row: loaded into D1 as `(b3·8 − ((Y+$14) & ~7)) | (scroll & 7)` before the submap loader runs |

Totals: **18 / 27 / 30 / 31** trigger records in maps 1–4 (106). Verified 2026-09-20 (`algo-flow.md` §9): D0 = byte 2 and D1 flow unchanged through `$18abe`/`$18bb2` into `FUN_00014458` (the routines on the way preserve D0/D1); `[$14360]` = 1 / 2 when Rick's x was clamped at the left / right limit (`algo-player.md`), 0 otherwise; `[$17990]` as above.

## 3. Spawn table (`scan_enemy_spawn_list` `$14594`, working pointer `[$144c8]`)

Header **4 bytes + `4·(byte3 & 3)` detail bytes**, repeated, **ended by a single `00` byte**. Checked over
**769 records** (131 / 197 / 216 / 225): every table is **sorted by Y ascending**, every Y is inside its submap's
height, and **no record has the spawned bit set in the file**.

| field | meaning (source) |
|---|---|
| `b0 & 0x7f` | type id. `$14636` dispatches: `$78` → `FUN_000157be`, `$7c` → `FUN_000157f4`, `1..$74` → monster path `FUN_000146a0`, otherwise → `FUN_00014862` |
| `b0 & 0x80` | **already-spawned** flag: set at runtime (`bset #7,(A0)`), skipped by the scan; clear in the files |
| `b1` | **Y tile**; world y = `b1·8`. The scan stops at the first record with `b1·8 ≥ scroll + $128`; an actor record is spawned only when its screen y (`b1·8 − scroll`) is outside `$28..$110`, unless the transition flag `[$14592]` is set |
| `b2 & 0x80` | 1 = spawn an actor (482 records), 0 = trigger/effect record via `dispatch_spawn_record` `$14a3c` (287 records) |
| `b2 & 0x1f` | **X tile**: x = `(b2 & $1f)·8`, `+4` if bit 5 |
| `b2 & 0x40` | monster path: `+3` on the screen Y (see below) |
| `b3 & 3` | number of 4-byte detail blocks that follow |
| `b3 & 0x80` | actor `+0x12 = -1` (selects the **masked** sprite blitter `$1952c`: the sprite is hidden where the tile mask bitmap is 0 — `graphics.md` §4) |
| `b3 & 0x3c` | mode. Monster path: `0x20` = fixed animation script (`$1466e`, `$1468a` on map 4), frame `$40` — a **500-point pickup** (`algo-actors.md` §3); `0x28` / `0x2c` = no script, frames `$27` / `$28` — pickups that set HUD counter A / B to 6; `0x10` sets a 0x60 counter, and with `b3 & 0x40` clears the respawn pointer. Type ≥ `$75` path: for kind 1, `((b3 & $3c) << 1) + 8` → actor `+0x54` |

Screen position written into the actor: `+2` = X as above, `+6` = `b1·8 − (scroll & ~7)`, plus 3 always for types ≥ `$75` (`$1492e`) but only when `b2` bit 6 is set on the monster path (`$147c6`).
For types ≥ `$75` (`FUN_00014862`): actor `+0` = `b0 & 3`, and the sprite id (`+0xe`, `+0x3e`) =
`word[$14854 + (((b0 & $c) − 4) >> 1)]`. **Detail blocks are trigger boxes** (x, y tile, size, condition mask) — decoded in `algo-actors.md` §4; a trigger-path
record (`b2` bit 7 clear) **spawns its type (`b0`) when one of its boxes fires**; a monster-path record's boxes are its
own hit/trigger regions checked every frame. Actor-table vs object-table split: `algo-actors.md` header.

**kb2 gap #4 CLOSED 2026-09-22 — the trigger-path branch (`b2` bit 7 clear) fires live, exactly as decoded.** Live capture (`kb2/hatari_live_validate.py`, `kb2/assets/live_validation_2026-09-22.json`)
found genuine trigger-path records (confirmed `b2` bit 7 clear from the pristine image) with their own header byte0 flipping to "consumed" live: map 2 type 122 (submap 1) and map 4 types 26 and 3 (submap 0),
the last with its own detail-box latch bit also flipping — both the record-level dispatch and the box-level latch behave exactly as `dispatch_spawn_record` (`$14a3c`) was transcribed.

## 4. Monster type table (image `0x0000`)

Word *i* is a **self-relative** offset: descriptor address = `2·i + word` (`FUN_000146a0`: `A1 = $53400 + 2·(type−1)`,
then `A1 += (A1)`). Number of types per map = highest type id used by its spawn records, and the offsets ascend
over exactly that range (checked): **49 / 43 / 50 / 68** (maps 1–4). Descriptor (`$146a0`):
`b0` → actor `+0x26`, `b1` → `+0x28` (sizes, kb2), `b2 & 0xc0` → flag bits into actor `+1`, `b2` → actor `+0x30`,
four signed words at `+4/+6/+8/+10` = **offsets from the descriptor's own address** to the movement script
(`+0x16`), animation script (`+0x1e`) and the alternate pair (`+0x32`, `+0x36`). Consecutive descriptors are **8 or 12 bytes apart** (map 4 also has 3 pairs sharing one descriptor);
the code reads all four words regardless, so an 8-byte descriptor's last two words are its neighbour's first bytes.
Raw values and resolved offsets are in `tables.json` (`monster_types`).
**Image layout of `0x0000`–`0x1800` (checked on all four maps):** the type table is `2·n` bytes; the
**movement (`+4`) and animation (`+6`) script offsets of every used type land inside `[2·n, first descriptor)`**
(all of them, maps 1–4), so the byte-code scripts fill that gap; the descriptors follow; the rest up to `0x1800`
is zero padding. The alternate pair (`+8`, `+10`) of 8-byte descriptors points into the neighbour and is meaningless.
The scripts are decoded in `decode_scripts.py` → `assets/levels/scripts.json` (all 420, every jump lands on a record boundary).

## 5. What changed versus kb2

- The 8-byte header word 1 is **max scroll ÷ 8**, not a "Y offset" (`FUN_00016718` clamps the scroll to `w1·8`).
- `g_submap_trigger_table_ptr` is at `$1435c`.
- The old "in-screen horizontal camera scroll (`FUN_00013d58`/`FUN_00013d0a`)" was a misreading, corrected 2026-09-22 by
  a direct re-disassembly of `$13d58`: it is the **laser-shot creation** call inside `update_player_rick` (`algo-player.md` §4) — plays sound `$10`, sets the shot record active (`[$16902] := 1`), decrements ammo
  (`[$176f4]`, dirty `[$176f2]`), and writes the shot's position/velocity fields (`[$16908]` = Rick's y + 7, `[$16904]` = Rick's x, `[$16926]` = ±8 depending on facing `[$1697e]`) — not Rick's own position, and not
  a camera scroll at all. It also sets `[$12e26] := -1`, the latch `$13d0a` and `UPFIRE` read (`algo-player.md` §4, §10 — `$13d0a` was fully read there too, not "not read" as this line used to claim).
  There is no horizontal camera scroll in this game: scrolling is vertical only (`$16658` → `$16718`/`$166ae`, `graphics.md` §3a).
