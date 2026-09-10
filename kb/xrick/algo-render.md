# Rendering — `fb.c`, `tiles.c`, `sprites.c`, `img.c`, `draw.c`, `rects.c`, `env.c`

The port renders into a plain 8-bit indexed 320×200 array and then blits dirty
rectangles. Nothing here corresponds structurally to the original's bitplane blitter;
what *is* comparable is the **pixel-level semantics**: transparency, clipping, depth,
and the exact sprite/tile encodings.

## Frame buffer — `fb.c`

`U8 fb[200][320]` (`fb.c:25`), one palette index per pixel. `fb_at(x, y)` returns
`&fb[0][0] + x + y*320`.

Palette (`GFXST`, `fb.c:40-69`): **32 entries** — 16 game colours followed by 16
lightened "highlight" variants. RGB is stored as three parallel `U8[32]` arrays and
pushed with `sysvid_setPaletteFromRGB`. Highlighting a sprite is done by ORing `0x10`
into the pixel index (`sprites.c:242`), i.e. selecting the parallel colour.

Fades are palette ramps, not pixel work (`fb.c:101-140`):

```c
fb_fadeIn():  8 steps, sysvid_setGamma(56 + 255*(1 - 2/(fade+2)))   -> 255
fb_fadeOut(): 8 steps, sysvid_setGamma(255 * 3/(fade+3))            -> 0
```

`sysvid_setGamma` scales the whole display palette (`sysvid.c:139-141`). Both functions
are written as `while (fade < 8) { ...; return FALSE; }` — a loop that always returns on
its first iteration, i.e. a state machine dressed as a loop.

## Tiles — `tiles.c`

An 8×8 tile. `GFXST`: `U32 tile_t[8]`, one `U32` per row, 4 bits per pixel.

```c
U8 *tiles_paint(U8 tileNumber, U8 *fb) {
    for (i = 0; i < 8; i++) {
        x = tiles_bank[tileNumber][i];
        for (k = 8; k--; x >>= 4) f[k] = x & 0x0f;     /* leftmost pixel = high nibble */
        f += FB_WIDTH;
    }
    return fb + 8;
}
```

Tiles are **opaque** — every pixel is written, colour 0 included. `GFXPC` instead
applies `tiles_filter` (`x & tiles_filter`) to select CGA colour pairs; `GFXST` ignores
the filter entirely.

`tiles_paintList` walks a `TILES_NULL`-terminated byte string, handling `TILES_CRLF` by
advancing the base pointer 8 rows. This is the port's entire text engine: strings are
tile-number sequences, and the tile bank is the font.

## Sprites — `sprites.c`

`GFXST` sprite: `U32 sprite_t[0x54]` = 0x15 rows × 4 groups of 8 pixels at 4 bpp,
stored row-major (`sprites.h:1298`). **Transparency is derived, not stored**: colour
index 0 is transparent.

`sprites_paint` (`sprites.c:60`) — the simple path, used only by the map-intro
animation; no clipping, no depth:

```c
for (i = 0; i < 0x15; i++) {
    for (j = 0; j < 4; j++) {
        d = sprites_data[spriteNumber][g++];
        for (k = 8; k--; d >>= 4)
            if (d & 0x0f) f[k] = (f[k] & 0xf0) | (d & 0x0f);
        f += 8;
    }
    fb += FB_WIDTH;
}
```

Note `(f[k] & 0xf0) | (d & 0x0f)` — the high nibble of the destination is preserved, so
a highlighted background stays highlighted under a sprite.

`sprites_paint2` (`sprites.c:184`) — the gameplay path. Clips with `maps_clip`, converts
to fb coordinates (with the `GFXST` `+8`), then draws right-to-left in four unrolled
groups of 8 pixels via a `LOOP(N, C0, C1)` macro. Per pixel:

```c
if (c >= width || x + c < x0) continue;                     /* clipped column      */
if (!front && !env_highlight && (flg & MAP_EFLG_FGND)) continue;  /* behind fgnd   */
if (d & 0x0f) fb[i] = (fb[i] & 0xf0) | (d & 0x0f);          /* transparent = 0     */
if (env_highlight) fb[i] |= 0x10;
```

`flg` is refreshed from `map_eflg[map_map[...]]` every time the column crosses a tile
boundary (`im` counts down from the sub-tile offset and resets to 8). This is the
**depth test**: a sprite pixel is dropped where the map tile behind it is marked
foreground. `env_depth` (default TRUE, `env.c:29`) globally disables it.

The four `LOOP` invocations cover columns 0x1F..0x18, 0x17..0x10, 0x0F..0x08, 0x07..0x00
using sprite words `g+3`, `g+2`, `g+1`, `g+0` — so the sprite data is stored
left-to-right but consumed right-to-left, because the `d >>= 4` shift-out order runs from
the low nibble.

`sprites_clear` (`sprites.c:267`) repaints the map behind a sprite box: 4 or 5 tile
columns (depending on sub-tile x offset) and 3 or 4 tile rows (on `y & 0x04`).
**It is dead code** — nothing calls it; `ents_paintAll` uses `maps_paintRect` instead.

## Images — `img.c`

`img_paintPic(x, y, w, h, U32 *pic)` unpacks the same 4-bpp-in-`U32` format used by
tiles, for full-screen `GFXST` pictures (`pic_haf`, `pic_congrats`, `pic_splash`).
`img_paintImg(img_t*)` copies an 8-bit indexed image with its own palette straight into
the frame buffer — used only for the xrick splash (`img_splash.e`).

## Rectangles — `rects.c`, `draw.c`

`rect_t { U16 x, y, width, height; struct rect_s *next; }` — a singly linked list
allocated with `malloc`. Two static rectangles (`draw.c:137-142`):

```c
draw_STATUSRECT = { 0x20, 0, 0xF0 + 48 - 0x20, 8 }   /* GFXST HUD strip */
draw_SCREENRECT = { 0, 0, 320, 200 }
```

`game_rects` is what `sysvid_update` consumes at the top of the next frame.
`game_paintEntities` (`game.c:788`) chains the status rect in front of the entity list
and leaves a note that `draw_STATUSRECT.next` must be cleared afterwards — which
`game_loop` does at `game.c:239`, flagged "FIXME freerects should handle this".

## HUD — `env.c`

`env_paintGame` (`env.c:63`) draws, all from tile bank 0 at `DRAW_STATUS_Y = 0`
(`GFXST`):

| Item | x | Tiles |
|---|---|---|
| score, 6 digits | 0x20 | `'0' + digit`, i.e. tiles 0x30.. |
| bullets | 0x68 | `TILES_BULLET` (1) × `env_bullets` |
| bombs | 0xA8 | `TILES_BOMB` (2) × `env_bombs` |
| lives | 0xF0 | `TILES_RICK` (3) × `env_lives` |

`env_paintXtra` (`env.c:95`) draws the cheat indicators `T`/`I`/`H` at x 0, 8, 16 and a
two-line `Mnn` / `Snn` map/submap readout at y 16. **This is debug UI that the original
does not have** — it is on unconditionally in this build.

`env_clearGame` (`env.c:134`) erases the HUD strip by painting `'@'` (the blank tile)
across it under `GFXST`; under `GFXPC` it repaints the map row instead. Since `GFXST`
puts the HUD above the play area, blanking is correct there.

## What is *not* here

- No double buffering in the original's sense: there is one `fb`, and SDL owns the
  presentation.
- No shifted sprite pre-shift tables. `sprites.h:1258-1263` describes the PC version's
  four pre-shifted sprite planes, but the `GFXST` build shifts nothing — the ST sprite
  format is 8 pixels per `U32` at 4 bpp and sprites are drawn at tile-column granularity
  with the sub-column offset handled by `im`/`i` indexing.
- No palette-per-scanline, no raster effects, no VBlank sync.
