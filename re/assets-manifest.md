# Rick Dangerous — Asset Manifest

Everything in `re/assets/` was produced by [`extract_assets.py`](extract_assets.py)
from `atari_ram.bin`. Re-run it with `python re/extract_assets.py`.

**Every format below was validated by looking at the rendered output**, not by
inference — the title screen, the sprite sheet and the tile blocks all come out as
recognisable artwork, which simultaneously confirms the palette, the plane decoding
and the base addresses.

---

## Palette (`0x4DEE2`, 16 words)

ST format `0x0RGB`, 3 bits per channel, scaled ×255/7:

| # | RGB | | # | RGB | | # | RGB | | # | RGB |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | `#000000` | | 4 | `#242424` | | 8 | `#486D24` | | 12 | `#484848` |
| 1 | `#DA0000` | | 5 | `#0048B6` | | 9 | `#482400` | | 13 | `#6D6D6D` |
| 2 | `#B66D6D` | | 6 | `#006DDA` | | 10 | `#914800` | | 14 | `#919191` |
| 3 | `#FF916D` | | 7 | `#244800` | | 11 | `#DA6D00` | | 15 | `#B6B6B6` |

**Index 0 is transparent** for sprites — `render_sprites` derives its mask as
`NOT(p0|p1|p2|p3)`, so there is no stored mask plane.

---

## Pixel formats — note the two are different

### 8×8 cells (font, tiles): 32 bytes, **one byte per plane per row**
Row `r`, plane `p` = byte at `base + r*4 + p`; pixel `x` = bit `7-x`.

### Sprite frames: `0x150` bytes = 21 rows × 16 bytes, **plane-major longwords**
Row `r`, plane `p` = longword at `base + r*16 + p*4`; pixel `x` = bit `31-x`.
Each frame is **32 px wide × 21 rows** (sprites are nominally 24 px, leaving the
right 8 px blank).

> ⚠️ **This is not ST screen format.** Screen memory interleaves planes by *word*;
> sprite source data stores a whole longword per plane so `render_sprites` can rotate
> each plane independently for sub-word horizontal shifts. Decoding sprite data as if
> it were screen data produces noise. Confirmed by rendering Rick's idle frame
> (`0x2CA6E`) both ways — only the plane-major reading yields a figure.

### Full-screen images: standard ST low-res
320×200, 32000 bytes, word-interleaved planes, 160 bytes per scanline.

---

## Extracted files

| File | Size | Source | Contents |
|---|---|---|---|
| `palette.png` | 256×16 | `0x4DEE2` | The 16 colours as swatches |
| `font.png` | 95 glyphs | `0x1B01E` | See "Font" below |
| `tiles_bank0.png` | 256 × 8×8 | `0x1D01E` | Tile bank 0 — **levels 0–1** (South America, Egypt) |
| `tiles_bank1.png` | 256 × 8×8 | `0x1F01E` | Tile bank 1 — **levels 2–3** (Castle, Missile Base) |
| `blocks_bank0.png` | 256 × 32×32 | `0x22FEE` + bank 0 | Blocks assembled from 4×4 tile grids — stone/temple |
| `blocks_bank1.png` | 256 × 32×32 | `0x22FEE` + bank 1 | Same definitions, bank-1 tiles — castle/industrial |
| `sprites.png` | 124 × 32×21 | animation tables | All frames reachable from `ObjectTypeDef` + the hard-coded player/enemy/projectile tables |
| `title.png` | 320×200 | `0x23FEE` | The title screen |
| `banner_congratulations.png` | 320×32 | `0x40FEE` | "CONGRATULATIONS!" |
| `banner_hall_of_fame.png` | 320×32 | `0x423EE` | "HALL OF FAME" |
| `banner_select_level.png` | 320×32 | `0x437EE` | "SELECT LEVEL" |

---

## Findings from the extraction

### The font's extent is now settled — 95 glyphs, `0x00`–`0x5E`
Previously recorded as "true glyph count unconfirmed". Rendering the sheet shows the
layout plainly:

| Range | Contents |
|---|---|
| `0x00`–`0x09` | **digits 0–9** — which is why score digits are stored as *unpacked decimal*, indexing glyphs directly rather than as ASCII |
| `0x0A`–`0x0C` | the three HUD icons (bullets, dynamite, lives) |
| `0x0D`–`0x40` | assorted small graphics |
| `0x41`–`0x5A` | `A`–`Z` at their ASCII positions |
| `0x5B`–`0x5E` | `,` `.` `?` and space (`0x5E`, a blank glyph) |
| `0x5F`+ | **not font** — unrelated graphics data |

That matches the `byte[95][32]` typing an earlier pass applied in Ghidra.

### `0x40FEE` is three banners, not a full-screen image
Decoding it as 320×200 gives clean text for the first ~96 rows and noise below.
It is in fact **three 320×32 strips of 5120 bytes each** — and 5120 bytes is exactly
what `blit_image_5120` copies, which explains that function's otherwise odd size.
Earlier notes calling `0x40FEE` "a title/menu bitmap" were half right: it is banner
artwork, not a screen.

### Sprite coverage
124 unique frames were reached by walking every animation table in
`ObjectTypeDef[75]` plus the hard-coded player, dynamite and enemy tables, and adding
the computed treasure frames (`type*0x150 + 0x2F70E`) and the eight enemy sprite
banks. The sheet shows Rick in several poses, guards, bats, boulders, barrels,
dynamite, explosions and the "SCORE GATE" signs — i.e. the reachable set looks
complete for the entity types in use. There may be further frames in the graphics
blob that no table references; those would need a linear sweep to find.

---

## Not extracted

- **Music and sound.** The PSG sequence data and the three PCM samples are *located*
  and their formats decoded (`algo-music.md`), but nothing has been rendered to audio.
  Two of the three samples are also partly outside the RAM capture (see
  `memory_map.md`).
- **Per-room level maps.** The tilemap *encoding* is decoded (`algo-level.md`) and the
  blocks are extracted here, so rendering whole rooms is now straightforward — it just
  hasn't been done.
- **Any frames not referenced by an animation table**, as noted above.


---

## The whole game is resident — nothing is loaded from disk during play

A natural question on seeing the tile sheets is whether only level 1's graphics are in
the snapshot, with the rest streamed from disk as the player progresses. **They are
not.** Everything for all four levels is already in memory:

| Data | Extent | Covers |
|---|---|---|
| `room_headers` | 47 entries, `0x47620`–`0x478B1` | all 4 levels (entry rooms 0, 9, 20, 38) |
| Tilemaps | `0x2101E`–`0x22F76`, contiguous | all 47 rooms |
| `placement_table` | 523 records | all 4 levels |
| Tile graphics | **only 2 banks** | shared pairwise across the 4 levels |
| Intro texts | 5 (4 levels + ending) | all |
| Level names | 4 | all |

**There are only two tilesets in the entire game**, selected by
`RoomHeader.wTileBankVariant`:

| Bank | Address | Levels | Character |
|---|---|---|---|
| 0 | `0x1D01E` | 0 South America, 1 Egypt | ancient stone: temple blocks, ladders, carved faces, torches |
| 1 | `0x1F01E` | 2 Schwarzendumpf Castle, 3 Missile Base | castle stone and barred windows, then pipes, rockets, hazard stripes, grating |

Pairing the levels this way is what makes two banks sufficient — the two "ancient"
levels share an art style, as do the two "modern" ones.

**The decisive evidence that no disk access occurs**: the entire 133-function program
contains exactly **two** trap instructions — one `TRAP #1` (`Super`) and one
`TRAP #14` (`Setscreen`). There is no GEMDOS `Fopen`/`Fread`, no BIOS `Rwabs`, no
XBIOS `Floprd` anywhere. The code physically cannot touch the disk.

So completing a level is pure pointer arithmetic:
`process_level_transition_point` sees a `TransitionWaypoint` with
`pNextRoomHeader == -1`, increments `level_index`, and calls `start_level`, which reads
`level_start_info[level_index]` for the next entry room and hands off to
`init_screen_pointers` → `render_new_screen`. No I/O, no decompression, no waiting.

All loading happened **once**, before this snapshot's entry point, during the outer
loader/HPack decompression stage described in `rick.md`.
