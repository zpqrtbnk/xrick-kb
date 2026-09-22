# Rick Dangerous 2 — graphics and screen composition

Scope (user, 2026-09-19): what an SDL port needs — the asset formats and how a frame is put together.
Not Atari hardware behaviour. Every statement below was checked against the disassembly (Ghidra, `prg2-ram.bin`),
the live game (Hatari, `kb2/hatari_rd2.py`) or the extracted files. **§7 is a closed checklist as of 2026-09-22** —
every static rendering question `PLAN.md` **T26** raised has been answered; §7 keeps the history for provenance.
Extraction tools: `kb2/extract_gfx.py` (tiles, sprites, palettes, banners) and `kb2/extract_levels.py` (level layouts);
outputs in `kb2/assets/gfx/`.

## 1. Screen

- **320 × 200, 16 colours, 4 bitplanes interleaved by word** (ST low-res: per 16 pixels, 4 words =
  plane 0..3, MSB = leftmost pixel; 160 bytes per line). Decoding the live screen buffer this way
  reproduces Hatari's own screenshot (`kb2/assets/gfx/ref_screen_map1..4.png`, viewed).
- **Two buffers, `$70000` and `$78000`** (pointers at `$18eda` = `$70000`, `$18ede` = `$78000`, read live);
  Hatari `info video` reported base `0x70000` at capture time; both buffers held the same picture in every
  capture. **Swap/draw-target logic**: `$19234` toggles bit 7 of the middle byte of both pointers and writes the
  new base to the video-base registers, once per frame after `$19216` (`algo-flow.md` §2) — a plain double buffer flip.
- **Playfield 256 × 192 at screen (32, 8)**; the top 8 lines (row 0) are the HUD, drawn separately by
  `update_hud_text_slots` `$177a8` (score at column 4, then 3 icon-strip counters — §4a, fully traced, not "seen
  in screenshots but unread" as this section used to say).
- Vertical fine scroll: the tile-data pointer is advanced by `(scroll & 7) × 5` bytes (`$16462` & 7, in
  `$188d0`), i.e. whole pixel rows of a tile → the playfield scrolls **vertically** in pixel steps.

## 2. Palette

**One palette for the whole game: 16 words at `$18ee6` in the program**, installed into `$ff8240` by
`FUN_00019116` (`$19116`, `A0` = palette pointer, remembered in `[$18ee2]`) through the thin wrapper `$19106`
(pushes A0, sets `A0 = $18ee6`, calls `$19116`, restores A0):
`0000 0000 0620 0320 0522 0630 0743 0763 0032 0151 0127 0147 0223 0334 0445 0667` (checked in `prg2-ram.bin` and in all four
map captures: identical). All values are ≤ `0x777` (ST 3-bit colours; `kb2/extract_gfx.py` uses `v·255/7`).

**Who rewrites colour 1 — closed 2026-09-22, nobody does.** Exhaustive `get_xrefs_to` on both the table word (`$18ee8`) and
the hardware register (`$ff8242`) find only the two generic whole-palette fade routines (`$1919e` fade-out, `$19134`
fade-in — every colour, not just 1) as writers; no code targets colour 1 specially. The old observation "the live
`$ff8240` differs from the table only in colour 1" (`0008`/`0088`/`0080`/`0080`) is the **STE-only 4th colour bit**
(this program only ever writes 3-bit `$777`-masked values; the 4th bit an STE would use is simply whatever was in that
memory before, invisible on the real ST hardware this game targets) — not a runtime effect, and not colour-1-specific
either (any colour's spare bit could show the same noise).

**Other screens' palettes — closed 2026-09-22, there is only the one palette (plus the grey one).** Title, hall of fame,
level picker and the level-load banner (§4b) are all drawn as 2-bitplane images layered over an already-cleared screen
using colours 0–3 of this *same* table — none of `$17e40`/`$17a46`/`$17c06`/`$17f22`/`$123b0` (their call chains, fully
read) calls any palette-install routine other than the fade in/out, which always uses whatever the *current* pointer
(`[$18ee2]`) is. The only other palette that exists at all is the grey one at `$18f06`, toggled by the SPACE key
(`algo-flow.md` §3) — unrelated to which screen is showing. `$19106`/`$19116`'s own caller was not found (no xref, same
known gap as the boot entry itself, `PLAN.md` T24), but the effect — this exact table, installed once, never swapped
per screen — is directly confirmed by every live capture and by every consumer read above.
`kb2/assets/gfx/pal_map1..4.bin` keep the old live readings for the record; they are not evidence of a second mechanism.

## 3. Tiles

- **8 × 8, 40 bytes each, 256 tiles per map**, at level-image offset **`0x4900`** (`$57d00` once loaded) — so
  every map has its own tileset inside its `RICK_0(2N).HNK`. Tile *n* is at `$57d00 + 40·n` (`$185c8`–`$185d0`:
  `n·8 + n·32`).
- Per pixel row: **5 bytes** = plane 0, 1, 2, 3 (1 byte each) **+ 1 extra byte**. The renderer writes the four
  plane bytes into the 160-byte-per-line background bitmap and the extra byte into a separate 1-bit-per-pixel
  bitmap at `$65804…` (40 bytes per line). The extra byte is a per-pixel **mask**
  (`kb2/assets/gfx/tilemask_map*.png`: solid tiles all-1, ladders/decor partial); its reader is the masked sprite blitter `$1952c` (§4: a sprite pixel is drawn only where the mask bit is 1).
- Sheet layout in `tiles_mapN.png`: 16 × 16 cells of 8 × 8, **cell (row, col) = tile `row·16 + col`**.
- The tile IDs on screen come from a **32-column, row-major window of 40 rows** at `$65300`–`$657ff`
  (`compute_tile_map_ptr` `$1643e`: `$65300 + ((Y & ~7)·4) + (X >> 3)`); the renderer's copy of the visible
  24 rows is at `$65400`. **IDs `$f8`–`$ff` are animated tiles** (§3b).
- **The window is generated from block maps** (§3a). Right after `load_map` the bytes at `$65300` are still the
  packed stage-1 file (measured equal to `map2_level_stage1.bin`, 37,888 B); they are overwritten by the generator.

## 3b. Animated background tiles (ids `$f8`–`$ff`)

- When the renderer (`FUN_000185a6`, `cmp #$f8 … bsr $175f2`) meets an id ≥ `$f8` it registers an **animation slot**
  (`FUN_000175f2`, at most `$28` = 40 slots of 14 bytes at `$17394`): flag byte, **frame index = `((id + 8) << 2) + phase`** with a
  random `phase` 0..3 (`[$18568] & 3`, a small shift/xor generator at `$18538`), then the tile-map, bitmap and mask pointers.
- `animate_background_tiles` (`$18dac`) runs every frame over **8 slots** per call (round-robin cursor `[$18da8]`), and
  each active slot advances the **low 2 bits of its frame index by 1 (mod 4)**, then copies the 8×8 tile at
  **`$5a500 + 40·index`** (same 40-byte format as §3, mask byte to the mask bitmap) into the background bitmaps.
- `$5a500` = **image offset `0x7100`**: 32 tiles = 8 tile types × 4 frames, ending exactly where the level sprite bank
  starts (`$5aa00`). Extracted as `kb2/assets/gfx/tiles_anim_mapN.png` (4 columns = frames, 8 rows = ids `$f8`..`$ff`; viewed:
  lamps, waterfalls/snow, leaves, torches, lanterns — coherent 4-frame loops).
- Two background bitmaps are written from the same tile data: `$185a6` uses a **128-byte line pitch** (bitmap at `$68000`),
  `$188d0` a 160-byte pitch (the 256-px playfield inside a 320-px line, `$68510`). Per frame the `$68000` bitmap reaches the screen through `$18782`
  (192 lines from line `[$1662e]` of the 256-line circular bitmap, 128 bytes per line copied to 160-byte screen lines at screen (32, 8); §5).
- **`$188d0`, read 2026-09-22**: builds the 160-byte-pitch bitmap at `$68510` *and*, in the same pass, the 1-bit tile-mask bitmap at `$65800`/`$65804`
  used by the masked sprite blitter (§4) — for each tile it copies the same 4 plane bytes + 1 mask byte (§3's 40-byte tile format) that `$185a6` uses,
  confirming the two background paths and the mask builder all read the identical per-tile data. Its own callers are the scroll-boundary handlers
  `$16718`/`$166ae` (`graphics.md` §3a), which call it once whenever the tile window shifts by a whole tile row — not every frame.
- **The slide blits `$18b5c`/`$18c50`, read 2026-09-22**: each loops 192 times (exactly the playfield height) copying one scanline per iteration
  into the current draw buffer at the playfield origin (`+0x510`, matching `$18782`'s own destination); `$18b5c` writes new columns first then the
  shifted old picture (matching the "−8 per step" direction `$18abe` uses it for), `$18c50` writes the shifted old picture first then new columns
  (matching `$18bb2`'s "+8 per step") — confirms `algo-flow.md` §9's already-documented ±8-per-step slide is exactly these two routines, mirror images
  of each other. The exact byte-level column shuffle (Atari bitplane-interleave arithmetic) was read but is **not modelled further by design** — the
  user's rendering scope is "extract assets, understand screen composition," not Atari hardware tricks; a port reimplements this 16-step slide as an
  ordinary horizontal-scroll animation between the two already-decoded tile-map images (§3a), which is visually identical and needs none of this.

## 3a. Level tile map (found 2026-09-19)

Three levels of indirection, all inside the level image (`RICK_0(2N).bin`, image offset = address − `$53400`):

| image offset | address | what |
|---|---|---|
| `0x1800` | `$54c00` | **submap header table**, 8 bytes = 4 big-endian words per submap (below) |
| `0x3000` | `$56400` | **block maps**: rows of **8 block ids** (8 bytes); one row = 32 px tall, 256 px wide |
| `0x3900` | `$56d00` | **block table**: 16 bytes per block id = **4 × 4 tile ids**, row-major (4 rows of 4) |
| `0x4900` | `$57d00` | tiles (§3) |

- Header word 0 = block-map offset (`$56400 + w0`); word 1 × 8 = **maximum scroll in pixels**, so a submap is
  **256 px wide and `w1·8 + 192` px tall** (192 = playfield height); word 2 / word 3 = offsets from `$54c00`
  of the submap's **trigger table** (`[$1435c]`, read by `check_submap_exit_triggers`) and **spawn table**
  (`[$144c4]`). Set by `FUN_00014458` (`$14458`, called as `D0 = submap index`, `D1 = initial scroll`).
- Number of headers per map = first trigger-table offset / 8: **map 1 = 17, map 2 = 14, map 3 = 14, map 4 = 13**
  (some are stubs that repeat an earlier layout; `kb2/assets/gfx/levelmaps.json` marks them `same_layout_as`).
- **Window generation** (`func_0x00016474` `$16474`): source pointer `[$1646a]` (= block map base) advanced by
  `((scroll & ~7) >> 5) · 8` bytes; each block-row is expanded by `FUN_000165fc` (`$165fc`) into 4 tile rows
  of 32 tiles (8 block ids × 4 tiles); `FUN_000165a6` handles the partial first block-row when
  `(scroll >> 3) & 3 ≠ 0`. Scrolling past an 8-px boundary is handled by `FUN_00016718` (down) / `FUN_000166ae` (up), which call
  `FUN_000164de` (down) / `FUN_0001653e` (up), read 2026-09-20: each shifts the 40-row × 32-byte tile window at `$65300` by one row (39 rows of 32 bytes copied) and expands the one new row
  (bottom row at `$657e0` for down, top row at `$65300` for up) from the block map with `$165a6`, using the row-in-block counter `[$16472]` (0–3) and the block-map pointer `[$1646e]` (±8 per 4 rows).
  The callers `$16718` / `$166ae` first clamp the new scroll `[$16462] + [$1662c]` to `[$16466]` (= 0, minimum) / `[$16468]` (= w1·8, maximum); when the 8-px boundary is crossed
  they call `$17694` / `$17644` (shift the animated-tile slots' window pointers, §3b), the window shift, `$1884c` / `$1888e` — read 2026-09-22, both trivial wrappers that pick a row of the tile window (`$65400`
  for `$1884c`, `$65400+0x320` for `$1888e` — the "new" row after a down/up shift) and a destination row of the **128-byte-pitch** bitmap/mask (`$68000`/`$65800`) computed from the current pixel scroll
  `[$1662e]`, then call the same row-renderer `$185a6` used everywhere else — i.e. only the one freshly-scrolled-in row is re-rendered into the screen-facing bitmap per shift, not the whole 24-row view,
  `$16786` (`[$1662e] := ([$1662e] + [$1662c]) & $ff`, the pixel scroll row of the 256-line circular bitmap), `$171a4` with D0 = −8 / +8 (adds it to the y word `+6` of **every record of the 17-record chain**)
  and `$14542` (re-seek the spawn table); otherwise only `$16786` runs. Record y coordinates are therefore relative to the window, not absolute.
- **Verified**: for all four maps the live window at `$65300` (40 rows × 32) equals the rows generated from this
  scheme, 40/40 rows (captured 120 frames after each load; map 3 with scroll 1152 and base `$564a0`).
  Rendering every submap this way gives coherent rooms (`kb2/assets/gfx/levelmap_map<N>_sub<I>.png`, viewed for
  maps 1, 2). Tool: `kb2/extract_levels.py`.
- **Does the window ever read past a submap's own block-map extent? Closed 2026-09-22, no.** The shift functions advance the block-row pointer `[$1646e]` by one block-row (8 bytes) every 4th call; scrolling
  the *entire* range `[0, w1·8]` takes exactly `w1` calls (one per 8-px step), so the pointer advances `w1÷4` block-rows in total — always **exactly 6 block-rows short of** the submap's own declared `rows = w1÷4+6`
  (checked by computing this for all 58 submaps of all 4 maps: margin is 6 everywhere, never less). The `+6` in the header-derived row count *is* this safety margin, and it is never exhausted — confirmed from the
  arithmetic, not just the one live capture above. (Whatever bytes remain in `$3000`–`$3900` past the *last* submap's total range are simply unused space in that fixed-size storage block, read by nothing.)
- No horizontal scrolling code was seen; the player x limit check in `$13e14` is 0–255.

## 4. Sprites

- **32 × 21 pixels, 336 bytes (`0x150`) per frame**: per pixel row **4 longwords = plane 0..3**, each holding
  32 pixels (MSB = leftmost). **No mask is stored**: the blitter ORs the four planes and treats colour 0 as
  transparent (`or.l` chains in `$19e96`; `and`/`or` with the inverted OR to overwrite pixels).
- **Frame id → bank** (`FUN_00017116`, disassembled; id = word at actor record `+0x0e`; `$fe` = draw nothing):

  | id | bank base | in |
  |---|---|---|
  | 0–63 | `$37274` | shared, RAM only. **Only 41 valid** (0–40): the next bank starts 41 frames later |
  | 64–127 | `$5aa00` | level image offset `0x7600` (per map) |
  | 128–191 | `$3a844` | shared, RAM only. **Only 29 valid** (128–156): the text glyph set starts at `$3ce54` = `$3a844 + 29·336` |
  | 192–255 | `$5fe00` | level image, directly after the 64–127 bank |

  Frame address = `bank + 336·(id mod 64)`. The level bank is exactly 128 frames (`0x7600` + 128·336 =
  `0x11e00`, where the tile-attribute table starts).
- The **shared banks are not in any `.HNK`**: they are in RAM after `RICK2.PRG` has unpacked itself.
  `kb2/prg2-ram.bin` matches four fresh captures byte for byte over `$37274`–`$3efb6`.
- Draw loop: actor/object records are **88 bytes** (`lea $58,A6`); `$170d4` draws those with `+0x14 == 0` and
  `$170f2` the ones with `+0x14 != 0` (clearing it). Screen position = **(x + 32, y − $38)** with x = word `+2`,
  y = word `+6`, then y minus the scroll fine offset; sprites are clipped to x ∈ [0, `$120`), y ∈ (−13, `$c8`)
  (`$17116`, `$19eb4`–`$19edc`). Frame id 254 (`$fe`) is not drawn; ids ≥ `$c0` / ≥ `$80` / ≥ `$40` / < `$40` select the banks `$5fe00` / `$3a844` / `$5aa00` / `$37274` (id mod 64 inside the bank, 336 B per frame).
  A word at `+0x12 ≠ 0` selects the **masked** blitter `$1952c`, else the plain blitter `$19e96` (read 2026-09-20; both have separate code paths for `x & 15 = 0` / `≠ 0` and for the left and right screen edges; per pixel row they read
  4 longwords = 4 planes of 32 px). Plain: `screen := (screen & ~opaque) | sprite`, where *opaque* = OR of the four planes (colour 0 is transparent). Masked: the same with `sprite & mask` and
  `opaque & mask`, where *mask* is a word of the 1-bit bitmap at `$65800` (40 bytes per line, 256 lines, wrapping with the scroll row `[$1662e]`; the game playfield starts at byte 4 = x 32) — the sprite disappears
  where the mask bit is 0. Mirroring is **not** done by the blitters: mirrored frames are separate frames in the banks (the update code adds 3 to the frame id when moving left, `algo-objects.md`, `algo-player.md`).
  `+0x10` (word): if negative it is cleared and the sprite is skipped when bit 7 of the byte at `$18edc` is set (else drawn normally); if positive it is cleared and the sprite is drawn as a **silhouette**
  (every pixel with a non-zero colour gets all four planes set = palette colour 15) — this is the hit flash (`$15eca` sets `+$10 := 1`).
- `kb2/assets/gfx/sprites_shared_A_0-40.png`, `sprites_shared_C_128-156.png`,
  `sprites_mapN_level_64-127_192-255.png`: 16 frames per row, cell *k* = the *k*-th frame of that bank.
  Viewed: Rick's poses, bombs and explosions, pickups and the `500` score sprite (shared);
  penguins, guards, ice objects (map 2). 

## 4a. Text and HUD glyphs

- **Text blitter `FUN_00019272` (`$19272`)**: `A0` = string of glyph ids ended by `$ff`, `D0` = column (8-px units;
  bit 0 selects the odd byte column), `D1` = text row (8 lines each). It writes **into both screen buffers**
  (`$70000` and `$70000 + $8000`) with `movep.l` — glyphs are **opaque** (all four planes are written).
  **Fully derived from the instructions, 2026-09-22 (T30, was a hedge before):** `D7 := 4·(D0 & ~1) + (D0 & 1)`, `D7 += D1·`(256+1024) `= D1·0x500`, dest = `$70000 + D7`; each glyph's 8 rows go to that address
  and `+0xa0`, `+0x140`, … `+0x460` (i.e. 8 rows × 160-byte scanline pitch, confirming the 8×8 glyph size and the screen's 160-byte pitch independently of the sprite/tile evidence); after a glyph, the column
  address's bit 0 is toggled (byte-for-byte, `bchg #0,addr`) and, when that completes a 16-px hardware pair, +8 more is added — exactly the "half of a 16-px word-pair per column unit" model the bit-0 hedge already guessed, now proven.
  **`FUN_0001925a` (`$1925a`, "record-list draw"):** loops `(word col_or_terminator, word row, long string_ptr)` records, calling `$19272(col, row, *ptr)` for each; stops when a record's first word is negative
  (the picker's terminator is the literal `$ffff`, `algo-flow.md` §4).
- **Glyph set at `$3ce54`: 256 glyphs of 8 × 8, 32 bytes each = per pixel row 4 plane bytes** (no mask), glyph *n* at
  `$3ce54 + 32·n` (`$192aa`: `lsl #5`). `kb2/assets/gfx/font_glyphs.png` (16 × 16 cells, cell = glyph id, viewed):
  **ids 0–9 = digits**, then icons (lightning bolt = 10, a bullet/bomb-like icon = 11, Rick's head = 12 — by
  appearance), `END`, `OUT OF ORDER` pieces, `?`/`!`; **letters at their ASCII codes** (`A` = `$41`); from about
  `$60` on, 8 × 8 decorative pieces (metal, ice, cave, green) — **their use is as pieces of the cut-scene background images** (T35, answered 2026-09-20: `$18d00` copies any glyph id when drawing a scene's
  background, `decode_scenes.py`/`scenes.json` images use ids up to 240; the animated *tiles* are unrelated — those come from `$5aa00`, §3b).
- **HUD**: the score is 3 bytes of packed BCD at `$176e4`–`$176e6` (added with `abcd` in `FUN_00017810` `$17810`, split
  into six digit bytes at `$176e8`–`$176ed`) and drawn by `update_hud_text_slots` `$177a8` with `D0 = 4, D1 = 0`, i.e.
  column 4 = **x 32**, row 0 (matches the screenshots). Three further slots of 14 bytes each, chained from `$176f2` (`+0` pending flag, `+2` icon count, `+4` column, `+5` icon glyph id, `+6..+$b` a 6-byte
  text/icon buffer, `+$c` = `$ff` terminator) are drained the same way by `update_hud_text_slots`' 3-iteration loop.
  **Which slot draws which icon — closed 2026-09-22 (T26 item 4), from both the code and a live-RAM record dump:** all three slots draw on **row 0**, same as the score — this is *not* a separate icon row per
  stat, it's three more columns of the one HUD strip. Each slot's fill loop writes its **icon count** (not a number) copies of its **icon glyph** into the buffer, i.e. the HUD shows *N* repeated icons for a
  stat of value *N*, not "icon + digits". The three slots, in loop order, matching the counters named in `algo-player.md`/`algo-actors.md`:

  | slot base | stat | column (px) | icon glyph |
  |---|---|---|---|
  | `$176f2` | laser ammo (`[$176f4]`) | 13 (104) | `$0a` = lightning bolt |
  | `$17700` | bombs (`[$17702]`) | 21 (168) | `$0b` = bullet/bomb icon |
  | `$1770e` | lives (`[$17710]`) | 30 (240) | `$0c` = Rick's head |

  (columns/glyphs read directly from a live record dump; no writer of these two fields was ever found by `get_xrefs_to`, consistent with them being fixed layout constants baked in once, never rewritten —
  only the pending flag and icon count change at runtime.)
- `FUN_0001939e` (`$1939e`) zeroes a whole 32,000-byte screen at `A0` (25 × 32 `movem` blocks of 40 bytes); `FUN_00019388` calls it for both buffers (`$18ede`, `$18eda`).

## 4b. UI banners (`FUN_000194ce`, `$194ce`) — closed 2026-09-22 (T30/T38, and the "title image" item of §7)

Four fixed 256×24-pixel banners, one per `D0` argument, each a `$600`-byte slice at `$35a74 + D0·0x600`, copied into **both** screen buffers at screen (32, `D0==3 ? 80 : 0`) — the top-left of the playfield
area, occupying its first 3 character-rows (24 px = rows 0–2 of 8 px each); `D0==3`'s extra 80-scanline drop is used only by the level-load banner, clear of wherever else the loading screen draws. None of
these 4 screens draws the in-game HUD (`$177a8` is only called from the main gameplay frame loop), so there is no overlap to resolve — the banner is simply the heading, and each caller's own further content
(hall-of-fame table, picker rows, …) starts several character-rows further down. Format: only **bitplanes 0 and 1** are written (2 bits/pixel, colours 0–3 of the one palette); this is safe because every caller clears the screen first (`algo-flow.md`), so bitplanes 2–3 are
already 0. Source layout: 16 groups of 4 bytes per scanline (one `(plane0 word, plane1 word)` pair per 16-px group), 24 scanlines — decoded and extracted (`extract_gfx.py`, `banner()`) to
`kb2/assets/gfx/banner_{congratulations,hall_of_fame,select_level,loading}.png`, all four fully legible:

| `D0` | text | caller |
|---|---|---|
| 0 | "CONGRATULATIONS!" | `FUN_00017f22` (hall-of-fame name-entry screen, §11 of `algo-flow.md`) |
| 1 | "HALL OF FAME" | `FUN_00017e40` (hall-of-fame view) |
| 2 | "SELECT LEVEL" | `FUN_00017a46` (level picker) |
| 3 | "LOADING..." | `load_map_if_changed` (level start) |

## 5. Order of a frame (`game_main` `frame_loop`, `$10a54`)

Read from the disassembly (`kb2/algo-flow.md` §2 has the full call list). Render-relevant part, in call order:
`$16658` scroll-edge trigger (returns at once while Rick is dead, `[$12e2a]`) → `$18dac` background-tile animation (§3b) →
`$18782` **background to screen**: copies 192 lines (`$c0`) of the 256-line circular background bitmap at `$68000` (128 bytes per line = 256 px × 4 planes), starting at line `[$1662e]`
and wrapping at 256 (two `$18818` copies when it wraps), to the current draw screen `[$18ede]` + `$510` (= 8 lines · 160 B + 16 B, i.e. the playfield at screen (32, 8)) →
`$170b6` draws **all 17 records** of the chain `$167a2 … $16d79` in array order — objects ×4, laser shot, Rick, debris ×4, bomb, actors ×6 — first those with `+$14 == 0`, then those with `+$14 ≠ 0` (which it clears)
(`$170d4` / `$170f2`, sprite entry `$17116`, §4; the sentinel is the word `$16d7a = -1`) → `$177a8` HUD text slots →
`$19216` waits for vblank (`[$19232] ≥ [$18ed8] − 1`) and **flips the double buffer** (`$19234`: toggles bit 7 of the middle byte of `[$18edc]`/`[$18ee0]`, writes the new base to the video-base registers) → `$191e6`
(second wait). So the order on screen is: background, objects, laser, Rick, debris, bomb, actors, then HUD text; sprites with `+$14 ≠ 0` last of the sprites.

## 6. Screens of the four maps

`ref_screen_map1..4.png` (captured 120 frames after each map loaded, attract demo running): map 1 metal
hull/starfield, map 2 ice cave, map 3 jungle rock, map 4 orange cave. Palette shared, tilesets per map.

## 7. Closed checklist (→ `PLAN.md` T26)

**Every item below is now closed.** (History kept for provenance; nothing here is still open as of 2026-09-22.)

1. ~~Use of the tile extra byte~~ read 2026-09-20: mask of the masked sprite blitter (§3, §4).
2. ~~Palette source~~ found (§2). ~~What changes colour 1 at run time~~ nothing does, closed 2026-09-22 (§2). ~~Palettes of the title / hall-of-fame screens~~ same one palette, closed 2026-09-22 (§2).
3. ~~Tile ids ≥ `$f8`~~ done (§3b). ~~The 160-byte-pitch bitmap (`$188d0`) and the slide blits `$18b5c`/`$18c50`~~ read 2026-09-22 (§3b).
4. ~~The level tile map~~ found, §3a. ~~Window rows beyond a submap's last row~~ closed 2026-09-22: proven to always leave 6 block-rows of margin, never exhausted (§3a). ~~Submap transitions~~ the 16-step slide, `algo-flow.md` §9 and §3b.
5. ~~Which HUD slot draws which icon row~~ closed 2026-09-22 (§4a: ammo=bolt, bombs=bullet, lives=Rick's-head, all on HUD row 0). ~~The hall-of-fame/title/picker/loading banners (`FUN_000194ce`, `$35a74`)~~ decoded and extracted 2026-09-22 (§4b). ~~The animated-background glyph mapping~~ answered — the glyphs ≥ `$60` are the cut-scene background images' pieces, not the animated tiles (T35, `PLAN.md`).
6. ~~Sprite mirror variant~~ `+0x12` = masked blitter, not a mirror (§4); actor-table draw call site = `$170b6` walks all 17 records (§5).
7. Where `RICK2.PRG` keeps the shared banks before unpacking — genuinely still open, but low priority and not needed (`PLAN.md` T39): the banks are fully and correctly extracted directly from live RAM
   regardless of where the packed source sits inside the program image (§4).
