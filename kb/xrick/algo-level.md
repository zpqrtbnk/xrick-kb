# Level data and scrolling — `maps.c`, `scroller.c`

## The data model

A **map** (5 of them; South America, Egypt, Castle, Missile Base, plus the "much later"
epilogue text) is a chain of **submaps** (47). A submap is stored as an array of
**blocks**; a block is 4×4 tiles. Blocks are referenced by `map_bnums`, 8 per block-row.
Only a sliding window of a submap exists in expanded form at any time, in
`map_map[0x2C][0x20]`.

```
map_maps[env_map]      -> {x, y, row, submap, tune}
map_submaps[env_submap] -> {page, bnum, connect, mark}
       page    : which tile page (0 or 1) -> which tile bank
       bnum    : index into map_bnums of this submap's first block-row
       connect : index into map_connect of this submap's first connector
       mark    : index into map_marks of this submap's first entity placement
```

## `map_expand` — `maps.c:70`

Fills `map_map` from blocks, starting at the block-row containing `map_frow`:

```c
pbnum = map_submaps[env_submap].bnum + ((2 * map_frow) & 0xfff8);
```

The comment explains the arithmetic: `map_frow` is a tile row; `/4` converts to block
rows and `*8` to block numbers (8 blocks per row), and `*2` then `&0xfff8` does both at
once. **Note this truncates `map_frow` to a multiple of 4** — the window is always
block-aligned, which is why scrolling only calls `map_expand` every 8th step.

The loop writes 0x0B block-rows × 8 blocks, expanding each block column-major into four
consecutive `map_map` rows (`maps.c:79-92`). 0x0B × 4 = 44 = 0x2C rows, exactly the
array height.

## `map_init` (ASM 0cc3) — `maps.c:102`

```c
map_tilesBank = (map_submaps[env_submap].page == 1) ? 2 : 1;   /* GFXST */
map_eflg_expand((page == 1) ? 0x10 : 0x00);
map_expand();
ent_reset();
ent_actvis(frow + 8,  frow + 8 + 0x20 - 1);   /* visible band  */
ent_actvis(frow + 0,  frow + 8 - 1);          /* hidden top    */
ent_actvis(frow + 0x28, frow + 0x28 + 8 - 1); /* hidden bottom */
```

The order matters: the **visible band is populated first**, so when slots are scarce the
on-screen entities win. Under `GFXPC` the banks are 3 and 2 instead of 2 and 1, and
`tiles_setFilter(0xffff)` is set.

## `map_eflg_expand(offs)` (ASM 1117) — `maps.c:139`

Run-length decode of the 32-byte `map_eflg_c` into the 256-byte `map_eflg`, using the
16-byte half selected by `offs` (0 or 0x10):

```c
for (i = 0, k = 0; i < 0x10; i++) {
    j = map_eflg_c[offs + i++];        /* count  */
    while (j--) map_eflg[k++] = map_eflg_c[offs + i];   /* value */
}
```

Note the double increment: `i++` in the loop header and `i++` inside the body, so the
16 bytes are consumed as 8 (count, value) pairs. Tile attributes are therefore assigned
in **8 contiguous runs over the 256 tile numbers**, per page.

## `map_chain` (ASM 0c08) — `maps.c:158`

Called when Rick walks off the left or right edge. Finds the connector for the current
submap whose `rowout` is within 3 rows of Rick's current absolute row:

```c
e_sbonus_counting = FALSE;
for (c = map_submaps[env_submap].connect; ; c++) {
    if (map_connect[c].dir == 0xff) sys_panic("can not find connector");
    if (map_connect[c].dir != game_dir) continue;
    t = (ent_ents[1].y >> 3) + map_frow - map_connect[c].rowout;
    if (t < 3) break;
}
if (map_connect[c].submap == 0xff) return FALSE;      /* end of map */
map_frow = map_frow - map_connect[c].rowout + map_connect[c].rowin;
env_submap = map_connect[c].submap;
return TRUE;
```

`t` is `U16` and the subtraction is unsigned, so `t < 3` also matches the three rows
*above* only by wrapping — in practice the connector list is ordered so the first match
in `dir` with a non-huge `t` wins. The new `map_frow` preserves Rick's vertical position
across the seam by re-basing on `rowin`.

Returning `FALSE` sends `game_cycle` to `NEXT_MAP`: bullets and bombs are refilled to 6
and `env_map++`.

## `map_resetMarks` (ASM 0025) — `maps.c:226`

Clears `MAP_MARK_NACT` on all 523 marks. Called once, from `init()` at new game
(`game.c:778`) — **not** on death or on re-entering a submap, so a collected bonus or a
one-shot trap stays consumed for the whole game.

## Painting the map

```
maps_paint()      maps.c:241  0x18 rows x 0x20 tiles from map_map[i+8][j]
                              at fb (0x20, (i+1)*8)  -- GFXST; (i*8) for GFXPC
maps_paintRect()  maps.c:269  align, clip, convert, then tile-by-tile
maps_alignRect()  maps.c:317  expand to whole tiles
maps_clip()       maps.c:347  clip to x in [0, 0x100), y in [0x40, 0x100)
```

`maps_paint` draws rows 8..0x1F of `map_map` — exactly the visible band. `maps_clip`
returns `TRUE` when a rectangle is entirely outside the visible band.

## Scrolling — `scroller.c`

Triggered by `game_cycle`'s `CTRL_SCROLL` state: `ent_ents[1].y >= 0xCC` scrolls up,
`<= 0x60` scrolls down. Each is an 8-step sequence, one step per frame, at
`SCROLL_PERIOD` = 24 ms instead of the normal 75. *(Port since master `89d0e1a`: 12
and 40, with the frame timer fixed — same scroll pace as before.)*

`scroll_up` (`scroller.c:34`), one step:

```
n == 8 -> restore game_period, n = 0, return SCROLL_DONE
n == 0 -> save game_period, set to SCROLL_PERIOD
shift map_map rows 0x08..0x26 up by one (from row+1)
for each live entity: ysave -= 8; trig_y -= 8; y -= 8
                      if (y & 0x8000) n = 0            /* scrolled off the top */
maps_paint(); ents_paintAll(); env_paintGame()
map_frow++
if (n++ == 7):  ent_actvis(map_frow + 0x20, map_frow + 0x27)   /* new bottom band */
                map_expand()
                maps_paint(); ents_paintAll(); env_paintGame()
game_rects = &draw_SCREENRECT
return SCROLL_RUNNING
```

`scroll_down` is the mirror image: rows shift down from `MAP_ROW_SCRBOT` (0x1F) toward
`MAP_ROW_HTTOP`, entities move `+8`, the off-map test is `y > 0x0140`, `map_frow--`, and
the newly-exposed band is the hidden **top** (`MAP_ROW_HTTOP`..`MAP_ROW_HTBOT`).

Three things to note for comparison:

1. The map is scrolled by **copying `map_map` rows**, and only re-expanded from blocks
   once per 8 steps — the block window is 4-row aligned so a full 8-row shift crosses
   exactly two block rows.
2. Each step **repaints the entire visible map and all entities**, and requests a
   full-screen refresh. There is no hardware scroll.
3. `scroll_up` shifts rows `0x08..0x26` but `scroll_down` shifts `0x1F..0x01`; the
   ranges are not symmetric (`MAP_ROW_HBBOT` = 0x27 vs `MAP_ROW_SCRBOT` = 0x1F). The
   downward case therefore does not shift the hidden bottom band at all.

## Level texts

`maps_intros[]` (`dat_maps.c:2360`) — five `{title, body}` pairs of tile strings using
`@` for space, `TILES_CRLFCHAR` (`\377`) for newline and `TILES_NULLCHAR` (`\376`) to
terminate. Painted by `screen_introMap` at (32, 0) and (32, 96). The fifth entry is the
epilogue ("LONDON, MUCH, MUCH LATER" / the Barfian Empire teaser).
