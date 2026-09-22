# Rick Dangerous 2 — the `.HNK` files: format, loader, contents

Rebuilt on 2026-09-20 from the sources of truth — the eight archives `disks/chaos43/RICK_01..08.HNK` (copies in `kb2/assets/hnk/`) and the game program inside
`RICK2.PRG` (Ghidra program `prg2-ram.bin`, RAM numbering) — not from the earlier `RICK_0N.bin` files, which are replaced by the outputs described here.
Every claim below names the address or the check that proves it; `kb2/verify_hnk.py` re-runs the checks. Extraction: `py -3 kb2/extract_all.py`.

## 0. Summary

* **What a `.HNK` is.** A *disk file holding one contiguous range of sectors of the original, protected game disk, packed with the "LSD!" packer*. The names come from the loader
  block embedded in the game program (string `RICK_0?.HNK` at `$7596`): the game asks for file **digit 1…8**, the loader builds `RICK_0<digit>.HNK`.
  The originals were read as raw sectors; the game's descriptor tables still carry the original `(start sector, sector count)` pairs (`$11e4e…`), but the file loader uses only the *end sector*
  to pick the file digit (§3). The four maps of this disk use 8 files = **4 pairs**.
* **Why two files per map.** The game's per-map descriptor (`$12dd4`) holds two descriptors:
  the **small file** (2 sectors = 1024 bytes) is the map's **attract-mode demo recording** — a list of `(frame count, input byte)` pairs replayed as joystick input (§5); the **large file** is the map's **level data** — a
  73 472-byte image (tiles, blocks, block maps, sprites, spawn/trigger tables, enemy scripts, cut scenes) stored twice-packed: LSD! transport layer + the game's own tree coder (§2).
* **What the `RICK_0N.bin` files were.** Depacked payloads produced by `kb2/hnk.py` (a transcription of the game's depackers). They are correct — re-checked here against the raw sectors of the original disk and live RAM (§9) — except that
  **`RICK_05` (map 3's small file) is not a demo**: the crack packed 512 wrong bytes (§6). They are superseded by `kb2/assets/maps/map<N>_{demo,level_stage1,level}.bin` (map numbers, not file numbers).
* **The port does not need any of the loader machinery**: it needs the per-map data set of §10, which `extract_all.py` produces at build time.

## 1. The files

| file | bytes | LSD! header: unpacked size | role | unpacked output |
|---|---|---|---|---|
| `RICK_01.HNK` | 68 | `$400` = 1024 | map 1 demo | `map1_demo.bin` (1024) |
| `RICK_02.HNK` | 27 976 | `$8800` = 34 816 | map 1 level | `map1_level_stage1.bin` (34 816) → `map1_level.bin` (73 472) |
| `RICK_03.HNK` | 166 | `$400` | map 2 demo | `map2_demo.bin` (1024) |
| `RICK_04.HNK` | 32 450 | `$9400` = 37 888 | map 2 level | stage 1 37 888 → 73 472 |
| `RICK_05.HNK` | 76 | **`$200` = 512** | map 3 "demo" — **wrong payload, §6** | `map3_demo.bin` (512, not a valid stream) |
| `RICK_06.HNK` | 31 982 | `$9200` = 37 376 | map 3 level | stage 1 37 376 → 73 472 |
| `RICK_07.HNK` | 118 | `$400` | map 4 demo | `map4_demo.bin` (1024) |
| `RICK_08.HNK` | 34 178 | `$9c00` = 39 936 | map 4 level | stage 1 39 936 → 73 472 |

Pairing: file `2N−1` = map N's demo, file `2N` = map N's level. Proof: (a) the loader's end-sector→digit table (`$11f86`) lists, in this order, the end sectors 13, 89, 15, 163, 17, 236, 19, 314 →
digits `'1'…'8'`, and those are exactly (demo end, level end) of maps 1–4 in the descriptor table (`kb2/verify_hnk.py` §2, §4); (b) each level file's unpacked size equals `sector count × 512` of the map's level descriptor
(68·512 = 34 816 …) and each demo's 1024 = 2 sectors.

## 2. The container formats

### 2.1 Layer 1: "LSD!" (every file) — the transport packer

```
+0   'LSD!'                      checked by the depacker entry $73f0; any other file is left untouched
+4   u32 BE unpacked size
+8   u32 BE stream length        = file size − 4 in all 8 files
+12  packed stream               read BACKWARDS from the end of the file down to +12
```

Backward LZ77 with a marker-bit bit reader; literal-run lengths, match lengths and offsets use escalating classes. `kb2/hnk.py depack()` is the transcription of the game's routine (`$73f0` entry, `$7444`–`$758e`
with three parameter tables at `$74ac`, `$7506`, `$754a`); its output equals the raw sectors of the original disk in 7 of 8 cases (§9), which validates it independently of the transcription.
Runtime behaviour of the entry `$73f0` (read): if the destination does not start with `LSD!` it just returns; otherwise it saves the 256 bytes below the destination (to `$8000`), copies the file 256 bytes *down* (to `dest − $100`), depacks in
place to `dest … dest + unpacked`, and restores the 256 bytes. (It also flashes the border colour `$ffff8240` while running.)

### 2.2 Layer 2: the game's tree coder (level files only) — `FUN_0001795c` (`$1795c`)

Applied to the stage-1 output of each **large** file. It is the game's own compression (the title picture at `$31eb0` in the program is stored the same way; `$1795c` has exactly two callers, the map loader `$1241c`
and the title routine `$1793a`).

```
+0      u32 BE output length      = 0x11f00 = 73 472 for every map
+4      tree, 0x3fc bytes         node = pair of int16: a bit selects the slot; negative value = leaf (symbol = low byte), positive = relative byte offset to the child pair
+0x400  bit stream                u16 big-endian words, MSB first, one symbol per root-to-leaf walk
```

`kb2/hnk.py depack_tree()` implements it. Check: its output for map 1 equals the live game's level image except for 10 run-time bits (§9).

## 3. How the game loads a map (all read from the disassembly)

**Descriptor table** `$12dd4`: 5 words-pairs of pointers; entry `i` → 8 bytes = two pointers, the *demo descriptor* (`$11e4e + 4i`) and the *level descriptor* (`$11e62 + 4i`); each descriptor = `(u16 start sector, u16 sector count)`.
Values read from the program: demo `(11,2) (13,2) (15,2) (17,2) (19,2)`, level `(21,68) (89,74) (163,73) (236,78) (314,75)` — contiguous ranges (11…20 the five demos, 21…388 the five level blobs).

**Map loader** `load_map_if_changed` `$123b0`, called at every level start (`game_main` `$10a36`):

```
if [$1239c] == [$1239e]: return          # same map as the one already loaded: NOTHING is reloaded (see §8, run-time mutation)
$194ce(3) ; $1a5d0                        # screen prep / stop sound
[$1239e] := [$1239c]
i := min([$1239c] − 1, 4) ; A1 := $12dd4[i]
$11e76( A0 = demo descriptor , D0 = $3efc0 )      # small file  -> the 1024-byte demo buffer
$11e76( A0 = level descriptor, D0 = $65300 )      # large file  -> LSD! output (stage 1) at $65300
$1795c( A0 = $65300 , A1 = $53400 )               # tree layer  -> the level image at $53400 .. $65300
(then the anti-tamper return-address trampoline, same pattern as $10c28)
```

`$65300` is later reused as the tile-ID window (`graphics.md` §3), so stage 1 is transient; the image at `$53400` ends exactly at `$65300`.

**File request** `$11e76` (called only from `$123b0`, twice): saves/restores the MFP registers and vectors (`$fffa07…`, vectors `$68,$70,$118,$134`), reads `(start, count)` into D1/D2, moves the destination into A0 and calls `$11f86`,
which computes `end = start + count`, compares it with 8 constants and loads the ASCII digit into D0:

| end sector | 13 | 89 | 15 | 163 | 17 | 236 | 19 | 314 | anything else |
|---|---|---|---|---|---|---|---|---|---|
| D0 | `'1'` | `'2'` | `'3'` | `'4'` | `'5'` | `'6'` | `'7'` | `'8'` | **red border, infinite loop** (`$11fb8`: `move.w #$700,$ffff8240 / bra`) |

then `jsr $7000` (D0 = digit, A0 = destination) and returns. The sector numbers are otherwise unused. A block of code after it (from `$11fe6`, containing an FDC sector reader at `$120b0`; its end was not delimited) has **no callers** (`get_xrefs_to` on `$120b0` = none, `$12074` only from inside the same block):
leftovers of the original raw-sector loader.

**The resident loader `$7000`** (a ≈1.4 KB block; the program's start-up code copies `$5b1` bytes to `$7000`; in the depacked program the block starts at file offset `0x114` with the bytes `601a 0000 0586`, i.e. it is itself a tiny PRG image):
`$701c` builds the name by patching the digit into `RICK_0?.HNK` (`$7596 + 6`), converts it to an 11-character 8.3 name (`$70dc`, lower case → upper), then works as a **minimal FAT12 file reader that drives the WD1772 floppy controller directly**
(sector read `$7282`: logical sector → track/side/sector, DMA at `$ffff8609…`): boot-sector BPB → root directory search (`$7136`, 11-byte compare) → first cluster/size → FAT chain → clusters copied to the destination → `bsr $73f0` (§2.1). So a `.HNK`
is looked up **by name on the boot floppy**; nothing but the digit matters.

## 4. Why two files per map

They are the two descriptors of one map (§3). The game needs both at map load: the small one goes to the fixed **demo buffer `$3efc0`** (next to its control variables `$3efb6 … $3efbf`), the large one becomes the level image. The demo is *map-specific*
because it is a recording of somebody playing that map with the joystick: it only makes sense on the map it was recorded on.

## 5. The small files: demo input streams

Reader `read_player_input` `$141cc` (single caller: `update_player_rick`, `$130ba`, once per game frame):

```
if [$3efb6] == 0 (no demo): D0 := [$1a4fb]                 # real input byte
else if [$3efbe] == 0: b := next byte at [$3efba]++ ; if b == 0: [$3efb8] := -1 (stream finished), return
                       [$3efbe] := b ; [$3efbf] := next byte ; 
     [$3efbe] −= 1 ; D0 := [$3efbf]                        # the state is delivered for `count` consecutive calls
```

`$14222` re-arms it at every level start in demo mode: `[$3efb8] := 0`, `[$3efba] := $3efc0`, `[$3efbe] := [$3efbf] := 0`. So a stream is `(count, state)` pairs, `count` = frames the state is held, terminated by a zero count byte; the rest of the 1024 bytes is padding.
The state byte uses the live input layout (`algo-player.md` §1): bit 0 up, 1 down, 2 left, 3 right, 7 fire; in `game_main` fire (the real one, `[$1a4fb]` bit 7) aborts a demo (`algo-flow.md` §6).

| map | pairs | frames | terminator at byte |
|---|---|---|---|
| 1 | 14 | 383 | 28 |
| 2 | 70 | 850 | 140 |
| 3 | — | (the file is not a stream) | none within 512 B |
| 4 | 31 | 378 | 62 |

All states in the three valid streams use only the bits above (`kb2/assets/maps/demos.json`, generated by `extract_hnk.py`, holds the pairs). Frames are game frames (2 vblanks each, `algo-flow.md` §2).

## 6. `RICK_05.HNK` and the original map-3 demo

`RICK_05.HNK` has the header size `$200` (512) and unpacks to 512 bytes starting `Rob Northen Comp…` (the copy-protection signature of the original disk); it is not a `(count, state)` stream (256 pairs, no terminator, states outside the five input bits).
The game loads exactly that into `$3efc0` for map 3 (live check in an earlier session, `PLAN.md` T25). The original disk image `disks/RICKDA2/RD2` (raw sectors) holds the real map-3 demo at sectors 15–16 (`RD2[7680:8704]`): 52 pairs, 663 frames, terminator at byte 104,
and the other three demos are byte-identical to the crack's (§9).

**T36, advanced 2026-09-22 (still not fully closable statically):** re-searched `RD2` byte-for-byte for the payload's content. The first 16 bytes ("Rob Northen Comp") occur at **two** places in `RD2` — offset 215
(very early on the disk) and offset 2560 (= sector 5) — so the signature is genuinely duplicated on the original disk, not something the crack invented. From byte 32 onward, though, the payload is **just a
9-byte cycle repeating to the end** (`9e 41 3c 82 79 04 f2 09 e4…`) — it does not match any other sector of `RD2`, or any sliding window within it, anywhere. A short repeating cycle standing in for real sector
content, right after a genuine "Rob Northen Computing" signature, is the classic symptom of a disk-imaging tool reading a **deliberately non-standard-formatted ("weak") sector** — exactly what Rob Northen's own
"Copylock" protection (well documented in the ST demoscene/preservation community, external to this session's disassembly) is built to make ordinary sector copiers choke on. **This is a plausible, evidence-consistent
explanation, not a proven one**: it would need the real, physical original disk read at the hardware level to confirm, which is not available here. What is proven: it is not a copy-paste of any other single sector,
and the signature bytes are genuinely duplicated elsewhere on the disk.

For a port: use `RD2[7680:8704]` as map 3's demo (documented as taken from the original disk, not from an HNK), or omit demos.

## 7. "Level 5" — a sequel tease, not a level (settled by the user, who has direct knowledge of the original boxed release)

**The game has 4 maps. It has never had a fifth, playable level — not in this disk, not in the original boxed retail release.** `[$17994]`/`[$17992]`/the "COMPLETE ALL 5 LEVELS" message are a **tease for a future game**, not an unlock mechanic: the text dangles a "level 5" the player can never actually reach, presumably as a hook for a sequel. This is settled fact per the user, not an inference from the disassembly, and it resolves cleanly against everything checked below.

**What is in the code and data, and how it now reads correctly:**

* Every earlier level's cut-scene name-drops "THE FAT GUY'S HEADQUARTERS" as Rick's ultimate, still-unreached destination (map 2: "HEADING FOR ... THE FAT GUY'S HEADQUARTERS"; map 3: "RICK ATTEMPTS TO TELEPORT DIRECTLY TO THE FAT GUY'S HEADQUARTERS ... BUT HE FAILS"; map 4: "RICK HEADS FOR THE ATOMIC MUD MINES BENEATH THE FAT GUY'S HEADQUARTERS") — narrative colour, not a promise of a 5th playable map.
* Map 4's second scene spells the tease out directly (`scenes.json`, `kb2/decode_scenes.py`):

  > CONGRATULATIONS! YOU HAVE COMPLETED LEVEL 4. HOWEVER, TO PLAY LEVEL 5 YOU MUST COMPLETE LEVELS 1 TO 4 IN ONE GAME, STARTING FROM LEVEL 1. THIS WILL ALLOW YOU TO SELECT LEVEL 5, BUT TO COMPLETE THE GAME PROPERLY YOU MUST COMPLETE ALL 5 LEVELS IN ONE GAME, STARTING FROM LEVEL 1.

  — read now for what it is: a joke/tease ending screen. It was never wired to real content.
* `game_main`'s map-complete branch (`algo-flow.md` §8) does contain code that reacts to this: finishing map 4 with `[$17994] == 1` sets `[$17992] := 5` (a 5th, cosmetic picker row becomes selectable) and advances `[$1239c]` to 5, which the frame loop feeds into `load_map_if_changed` (§3). **This is the tease's payoff, and it goes nowhere on purpose** — see below.
* The picker's 5th name string (`$17a28`, `"THE FAT GUY'S HEADQUARTERS"`), the 5-entry pointer table at `$12dd4`/`$11e4e`/`$11e62`, and the 5-row level-start table at `$14250` exist only to **make the tease look real** (a selectable-looking row, a name, a start-position placeholder) — cosmetic scaffolding for a joke ending, not evidence of unfinished game content.

**Why `[$1239c] = 5` can never load anything, checked at the byte level (this is *why* the tease is safe to leave in — it cannot accidentally become playable):**

* The filename template lives at `$7596`: the literal ASCII bytes `RICK_02.HNK`. The patch code (`$701e`: `lea (var,PC),A0`; `addq.l #6,A0`; `move.b D0b,(A0)`) writes the computed digit **6 bytes in — the *second* digit, `'2'`**. The *first* digit, `'0'`, is a compile-time constant, never touched: this loader can only ever ask for `RICK_0<d>.HNK`, one variable digit, never a two-digit `RICK_10.HNK`.
* The end-sector → digit table (`$11f86`–`$11fdc`, disassembled in full, exactly 8 `cmp.w`/`beq.b` pairs, no more) recognises end sectors `13, 89, 15, 163, 17, 236, 19, 314` → digits `'1'`…`'8'` and nothing else. Any other end sector — including the 5th table entry's own (21, 389) — falls through to `$11fb8`: `move.w #$700,$ffff8240 / bra $11fb8`, an unconditional infinite loop that paints the border red. There is no digit-9 case, no error message, no timeout.
* `[$1239c]`'s two writers (`set_current_map_from_choice` and `game_main`'s `NEXT`, `$10b1a`) never clamp it below 5, so the tease *is* reachable in principle by a player who completes 1→4 from level 1 — and hits the hang above. Whether the finished retail game actually let a player get that far, or gated the tease differently (e.g. only shown, never actually loaded), is not something this static reading resolves; either way there is no level behind it.

**The disk-level data that looked like it might be "level 5"** (this project's earlier, now-retracted hypothesis): the raw sectors 19–20 and 314–388 of `disks/RICKDA2/RD2`, and the `FILE.8`/`FILE.9` pair of `disks/rd2.st`, sit at exactly the positions the 5th table entry names, and decode without erroring (`hnk.depack_tree` produces a 73 472-byte buffer with plausible-looking submap headers). Given the game never had a level 5, this is **not evidence of a real, finished level** — most likely coincidental bytes (whatever else happens to occupy those disk sectors) that the tree decoder, which imposes very little structural validity, does not reject. **Not used by the port; kept, if at all, purely as a curiosity** (`kb2/extract_hnk.py --rd2` → `extra_rd2/map5_*`).

**Practical conclusion for the port: 4 maps, no more, no unlock code, no 5th picker row that goes anywhere.**

**Unrelated, worth flagging explicitly: `RICK_05.HNK` is not "map 5" / "level 5".** File-number 5 is the *third* map's *demo* recording (pair 5–6 = map 3, §1) — an unrelated, already-diagnosed corruption (§6). The sequel tease above is a different, higher-numbered concept (files 9–10, which this naming scheme cannot even produce). They share nothing but the digit "5".

## 8. The level image (`map<N>_level.bin`, 73 472 bytes, loaded at `$53400`; image offset = address − `$53400`)

| offset | size | content | doc |
|---|---|---|---|
| `0x0000` | up to `0x1800` | monster type table (n self-relative words, n = 49/43/50/68), then move/animation byte-code scripts and the 8/12-byte type descriptors; zero padding to `0x1800` (last non-zero byte `0xa49/0x9af/0xd2d/0x147d`) | `level-tables.md` §4, `algo-actors.md` §2, `scripts.json` |
| `0x1800` | to `0x1c86/0x1e6c/0x1f2e/0x1f40` | submap header table (8 bytes × 17/14/14/13), then per submap a trigger table and a spawn table (chain verified exactly); zero to `0x2000` | `level-tables.md`, `tables.json` |
| `0x2000` | to `0x2821/0x2baf/0x2b87/0x260d` | cut-scene zone: word 0 = offset of the image list, then the scene table, scene scripts (opcodes 1–14), texts and animation/movement scripts; the **image records are at the end** (each `cols`=32, `rows`, 0, 32 + rows·32 glyph ids of the 256-glyph font at `$3ce54`; they tile the rest of the zone exactly — asserted by `decode_scenes.py`; 1/3/2/1 images) | `decode_scenes.py`, `scenes.json`, `gfx/scene_map*_image*.png` |
| `0x3000` | ≈ `0x3530…0x38c0` | block maps of the submaps (rows of 8 block ids) | `graphics.md` §3a |
| `0x3900` | `0x1000` | block table: 256 blocks × 16 bytes = 4 × 4 tile ids | `graphics.md` §3a |
| `0x4900` | `0x2800` | 256 background tiles, 8 × 8, 40 bytes each (4 plane bytes + 1 mask byte per row) | `graphics.md` §3 |
| `0x7100` | `0x500` | 32 animated-tile frames (8 tile ids × 4 frames) | `graphics.md` §3b |
| `0x7600` | `0xa800` | level sprite bank, 128 frames × 336 bytes (used as frame ids 64–127 and 192–255) | `graphics.md` §4 |
| `0x11e00` | `0x100` | tile attribute byte per tile id | `algo-actors.md` §6, `tile_attributes.json` |

Coverage (checked by a scan of all four images on 2026-09-20: last non-zero byte per zone, image records tiling the scene zone, block/tile/sprite/attribute banks filling `0x3900…0x11f00` exactly): every byte outside the zero padding belongs to a row above, with one open item — bytes of `0x3000…0x38ff` beyond the block-map extent computed from the headers (map 1 to `0x35fe`, map 2 `0x387f`, map 3 `0x3827`, map 4 `0x38fb`) are
non-zero and not explained (T37; they are inside `map<N>_level.bin` regardless).

**Run-time mutation and reload rule.** The image is edited in place while playing (the "already spawned" bit `0x80` of spawn-record byte 0, `algo-actors.md` §4; live check: exactly 10 bytes differ from the pristine image in map 1, each only in that bit) and it is reloaded **only** when the map number
changes (`$123b0`, first instruction). Consequences for a faithful port: restarting the same map (respawn, or a new game on the map that is still loaded) keeps the latched records; a port that reloads each time must decide whether to reproduce that.

## 9. Verification (`py -3 kb2/verify_hnk.py`)

1. The eight archives in `kb2/assets/hnk/` equal `disks/chaos43/` and the FAT12 image `disks/chaos43_noauto.st`.
2. The descriptor table is read from the RAM dump and is contiguous.
3. **`hnk.depack(HNK)` equals the raw sectors of the original disk image `disks/RICKDA2/RD2` at the descriptor's sectors for 7 of 8 files** (all except `RICK_05`, §6). This does not use `hnk.py`'s claim of being a transcription: the reference is the disk itself.
4. The 8 end-sector constants and digits read from `$11f86…$11fdc` equal the 4 maps' (demo, level) end sectors; the "level 5" tease's own descriptor's end sectors (21, 389) are absent from the table.
5. Live RAM (`prg2-ram.bin`, map 1 playing): `$3efc0` = `map1_demo.bin`; `$53400…$65300` = `map1_level.bin` except 10 bytes differing only in bit `0x80`; `$65200` = image `0x11e00`. Earlier sessions also forced maps 2–4 in a live Hatari run: level images identical (`PLAN.md` T24), and map 3's `$3efc0` held the 512 junk bytes.
6. `dump_hnkload_hit1/2.bin`: `RICK_01.HNK` sits at `$3efc0` and `RICK_02.HNK` at `$65300` at the moment `$73f0` runs.
7. `RICK2.PRG` = a 794-byte crack stub (text) + an LSD! archive (data) of the whole game program; depacked (194 332 bytes) it equals `FILE.DRS` of the second disk image `disks/rd2.st`. Program assets checked equal between the depacked program and the RAM dump
   (RAM = file offset + `$f8b8`): font `$3ce54` (8192 B), the shared sprite banks `$37274…$3efb6`, the title region `$31eb0…`, the palettes `$18ee6…`.

Not a check but a note: `disks/rd2.st` carries the same 5 pairs as `FILE.0…FILE.9` in a *different* packing (magic `LZH!`, unpacked sizes equal to the stage-1 sizes). It is irrelevant here: the raw sectors of `RD2` give the same data without needing that packer.

## 10. What the port loads at start (no loader, no packing)

Per map 1–4, all produced by `extract_all.py`:

* **Level image `map<N>_level.bin`** (or its already split forms): tiles + mask, block table, block maps, animated tiles, level sprite bank, attributes (`levelmap_*.png`, `tiles_*.png`, `tilemask_*.png`, `sprites_map*`), submap headers + trigger + spawn tables (`tables.json`), enemy scripts (`scripts.json`), cut scenes and their images (`scenes.json`, `scene_map*_image*.png`).
* **Demo stream `map<N>_demo.bin`** (`demos.json`) — optional (attract mode); map 3's from the original disk (§6).
* **Program-resident assets (not in any HNK; all inside the game program, already extracted from the RAM dump — byte-identical to the depacked program, §9):** the palette(s) `$18ee6`/`$18f06`, the shared sprite banks (`$37274` frames 0–40, `$3a844` frames 128–156), the 256-glyph font `$3ce54`, the title picture (tree-packed at `$31eb0`, unpacked with the same coder to a 32 000-byte screen; **not yet extracted**), strings, sound (`sound-ref.md`, `rick2_sfx.sndh`).

## 11. Open items (`PLAN.md`)

T36 how `RICK_05.HNK` got its payload; T37 the unexplained block-map tail bytes; T38 the argument `3` of `$194ce` in `$123b0`. (T28, "level 5", is CLOSED: settled by the user as a sequel tease, never a real level.)
