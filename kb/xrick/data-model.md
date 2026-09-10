# Data model — structs, tables, flags, coordinates

Everything here is **verified** by reading `xrick/include/*.h` and the `dat_*.c` tables.
Counts marked "measured" were obtained by counting records in the initialiser, not by
trusting the `#define`.

## Coordinate systems

Three systems, defined in `draw.c:33-115` and `maps.h:891-904`.

| Name | Unit | Range | Used by |
|---|---|---|---|
| **map/px** | pixel | x `0x0000`–`0x00FF`, y `0x0000`–`0x013F` | entity positions, all game logic |
| **map/tl** | tile (8×8 px) | x `0x00`–`0x1F`, y `0x00`–`0x27` | `map_map`, tile painting |
| **fb/px** | pixel | x `0`–`319`, y `0`–`199` | the frame buffer |

The map column is 0x100 px (0x20 tiles) wide and the frame buffer is 0x140 px wide, so
the map is horizontally centred with 0x20 px of margin each side. Conversion:

```
x_fb = x_map - MAPS_FB_X      MAPS_FB_X = -0x20   maps.h:903
y_fb = y_map - MAPS_FB_Y      MAPS_FB_Y =  0x40   maps.h:904
```

A submap is taller than the screen. `map_map` holds a sliding window of 0x2C rows
(0x28 used) split into three bands (`maps.h:919-924`):

| Band | Rows | px height | Constant |
|---|---|---|---|
| hidden top | 0x00–0x07 | 0x40 | `MAPS_TOPHEIGHT_TL` = 8 |
| visible screen | 0x08–0x1F | 0xC0 | `MAPS_VISHEIGHT_TL` = 0x20 |
| hidden bottom | 0x20–0x27 | 0x40 | `MAPS_BOTHEIGHT_TL` = 8 |

`map_frow` (`maps.c:51`) is the absolute submap row of `map_map` row 0. Entity y
coordinates are relative to that window, so scrolling shifts every entity by 8 px
(`scroller.c:60-62`).

**`GFXST` paints 8 px lower than `GFXPC`.** Every ST paint path adds `+8` to the
y coordinate (`maps.c:254`, `maps.c:299`, `sprites.c:216`, `sprites.c:301`,
`ents.c:317`) with the comment "FIXME +8?". This is a status-bar offset: `GFXST` puts the
HUD at `DRAW_STATUS_Y = 0` and the play area below, `GFXPC` at `0x08`
(`env.c:44-55`).

## `ent_t` — the entity record (`ents.h:578-607`)

The C struct is not the original layout; the comments give the original byte offsets and
the port explicitly drops two fields it found unused.

| C field | Type | Original offset (per comment) | Meaning |
|---|---|---|---|
| `n` | U8 | b00 | entity type; **bit 7 = `ENT_LETHAL`**; `0` = free slot; `0xFF` = end-of-array sentinel |
| — | — | b01 | "in ASM code but never used" — omitted |
| `x` | U16 | b02 | position, map/px |
| `y` | U16 | w04 | position, map/px |
| `sprite` | U8 | b08 | sprite number; `0` = invisible |
| — | — | w0C | "in ASM code but never used" — omitted |
| `w` | U8 | b0E | box width |
| `h` | U8 | b10 | box height |
| `mark` | U16 | w12 | index of the mark that created this entity |
| `flags` | U8 | b14 | copy of `mark.flags` (see below) |
| `trig_x` | U16 | b16 | trigger-box x — **also reused as the type-1a patrol limit** |
| `trig_y` | U16 | w18 | trigger-box y |
| `xsave` | U16 | b1C | spawn x, restored when a type-3 path loops |
| `ysave` | U16 | w1E | spawn y, same |
| `sprbase` | U16 | w20 | base sprite number / index into `ent_sprseq` |
| `step_no_i` | U16 | w22 | initial index into `ent_mvstep` |
| `step_no` | U16 | w24 | current index into `ent_mvstep` |
| `c1` | S16 | b26 | **overloaded**: `offsx` (t1/zombie), `flgclmb` (t2), `sproffs` (t3), `cnt` (box), `seq` (bonus) |
| `c2` | S16 | b28 | **overloaded**: `step_count` (t1, t3), `offsx` (t2) |
| `ylow` | U8 | b2A | fractional y, low byte of the 8.8 fixed-point accumulator |
| `offsy` | S16 | w2C | y velocity, 8.8 fixed point |
| `latency` | U8 | b2E | countdown before the entity may act |
| `prev_n`, `prev_x`, `prev_y`, `prev_s` | | **new** | previous-frame state, for dirty-rectangle erasure |
| `front` | U8 | **new** | draw in front of foreground tiles |
| `trigsnd` | U8 | **new** | sound index, from `entdata.snd` |

The `c1`/`c2` overloading is done with `#define offsx c1` inside each `e_*.c`, undefined
at the end of the function. Six different meanings across five files.

Array: `ent_ents[ENT_ENTSNUM + 1]` = `ent_ents[13]` (`ents.c:41`).

### Slot allocation (`ents.c:170-198`, `ent_creat1`, `ent_creat2`)

| Slot | Contents |
|---|---|
| 0 | the single "stops Rick" entity — solid, blocks movement, and can kill other enemies |
| 1 | Rick (`E_RICK_NO`, `ENT_XRICK`) |
| 2 | bullet (`E_BULLET_NO`) |
| 3 | bomb (`E_BOMB_NO`) |
| 4–8 | `ent_creat1` — enemies of type ≥ 0x10, boxes, bonuses; `c1 = 0`. **Lethal to other enemies.** |
| 9–B | `ent_creat2` — enemies of type < 0x10; `c1 = 2`. Lethal to Rick only. Deduplicated by `mark`, so one mark cannot spawn twice. |
| C (=12) | **not an entity** — a scratch record used by `u_envtest` to box-test a candidate position against slot 0 (`util.c:97-98`, `util.c:176`) |

`ent_ents[ENT_ENTSNUM].n = 0xFF` is set once at `game.c:776`; every loop over entities
runs `for (i = 0; ent_ents[i].n != 0xff; i++)`, so slot 12 doubles as the terminator.

### Entity-type → behaviour (`ents.c:186-198`, `ents.c:448-473`)

```
n & 0x7f == 0x47          -> e_them_z_action        (zombie: dying enemy)
n & 0x7f >= 0x18          -> e_them_t3_action       (scripted trap)
otherwise                 -> ent_actf[n & 0x7f]
```

`ent_actf[]` has 24 entries:

| `n` | Handler |
|---|---|
| 00 | NULL (free slot) |
| 01 | `e_rick_action` (ASM 12CA) |
| 02 | `e_bullet_action` (1883) |
| 03 | `e_bomb_action` (18CA) |
| 04,07,0A,0D | `e_them_t1a_action` (2452) — patrol within a range |
| 05,08,0B,0E | `e_them_t1b_action` (21CA) — walk toward Rick |
| 06,09,0C,0F | `e_them_t2_action` (2718) — chase, can climb |
| 10,11 | `e_box_action` (245A) — bomb box / bullet box |
| 12–15 | `e_bonus_action` (242C) |
| 16 | `e_sbonus_start` (2182) |
| 17 | `e_sbonus_stop` (2143) |

The four-fold repetition of 04–0F is a sprite-set selector: same behaviour, different
`entdata` row and therefore different artwork.

## `entdata_t` — per-type template (`ents.h:609-614`, `dat_ents.c:16`)

`entdata_t ent_entdata[ENT_NBR_ENTDATA]` — `ENT_NBR_ENTDATA = 0x4a` = **74 entries**.

| Field | Type | Meaning |
|---|---|---|
| `w`, `h` | U8, U8 | collision box, almost always `0x18` × `0x15` |
| `spr` | U16 | base sprite number → `ent.sprbase` and `ent.sprite` |
| `sni` | U16 | **Dual-purpose, resolved 2026-09-04 (T9).** For scripted entities: initial `ent_mvstep` index → `ent.step_no_i`. For the **type-1a/1b walking enemies** (`mark.ent < 0x10`, i.e. slots 9-C, with all four trigger bits set) it is instead a **second sprite number** used as `sprbase`, the walk-cycle base of `sprite = sprbase + ent_sprseq[...]` — those enemies move under AI, never along `ent_mvstep`, so the field is free. Values `0x7E`/`0x86`/`0x8E` by enemy bank. See `xref.md` |
| `trig_w`, `trig_h` | U8, U8 | trigger box size in **tiles** (`<<3` at use, `util.c:196-197`) |
| `snd` | U8 | trigger sound; index used as `WAV_ENTITY[(snd & 0x1F) - 0x14]` (`e_them.c:696`) |

## `mvstep_t` — one path step (`ents.h:616-619`, `dat_ents.c:119`)

`mvstep_t ent_mvstep[ENT_NBR_MVSTEP]`, `ENT_NBR_MVSTEP = 0x310` = **784 entries**.

```c
typedef struct { U8 count; S8 dx, dy; } mvstep_t;
```

`count == 0xff` terminates a path. Type-3 entities walk this list, applying `dx`/`dy`
`count` times per step. `ent_sprseq[ENT_NBR_SPRSEQ]`, `ENT_NBR_SPRSEQ = 0x88` = **136
bytes**, is the parallel sprite-frame list, `0xff`-terminated per sequence.

## Map data (`maps.h`, `dat_maps.c`)

| Table | Declared size | Measured records | Record |
|---|---|---|---|
| `map_maps` | `MAP_NBR_MAPS` = 5 | 5 | `{x, y, row, submap, tune}` — Rick's start position, start row, start submap, WAV filename |
| `map_submaps` | `MAP_NBR_SUBMAPS` = 0x2F = 47 | 47 | `{page, bnum, connect, mark}` — tile page, first block, first connector, first mark |
| `map_connect` | `MAP_NBR_CONNECT` = 0x99 = 153 | 153 (+ terminator) | `{dir, rowout, submap, rowin}` |
| `map_blocks` | `MAP_NBR_BLOCKS` = 0x100 = 256 | 256 | `block_t` = `U8[0x10]` — a 4×4 tile block |
| `map_bnums` | `MAP_NBR_BNUMS` = 0x1FD8 = 8152 | 8152 bytes | block numbers, 8 per block-row |
| `map_marks` | `MAP_NBR_MARKS` = 0x20B = **523** | **523** | `mark_t` — the entity placement table |
| `map_eflg_c` | `MAP_NBR_EFLGC` = 0x20 = 32 | 32 bytes | run-length-compressed tile attributes, two 16-byte halves |
| `maps_intros` | (unsized) | 5 | `{title, body}` tile-string pairs |

`map_map[0x2c][0x20]` (`maps.c:49`) is the expanded window; `map_eflg[0x100]`
(`maps.c:50`) is the expanded per-tile attribute table for the current page.

### `mark_t` — one entity placement (`maps.h:981-987`)

```c
typedef struct {
  U8 row;    /* absolute submap row */
  U8 ent;    /* entity type; bit 7 = MAP_MARK_NACT (not active any more) */
  U8 flags;  /* ENT_FLG_* */
  U8 xy;     /* XXXXX YYY  (from b03) : X -> x, Y -> y within the row band */
  U8 lt;     /* XXXXX NNN  (from b04) : X -> trig_x, NNN -> latency and trig_y */
} mark_t;
```

Decoding, from `ent_actvis` (`ents.c:234-276`):

```
x        = xy & 0xf8
y        = ((xy & 0x07) + (row & 0xf8) - map_frow) << 3
           + 3, unless flags & ENT_FLG_STOPRICK
trig_x   = lt & 0xf8
latency  = (lt & 0x07) << 5                              /* = x32 */
trig_y   = 3 + 8 * ((row & 0xf8) - map_frow + (lt & 0x07))
```

Marks are stored **sorted by row**, which `ent_actvis` relies on to find the visible
range by linear scan and stop early (`ents.c:150-164`); `row == 0xff` terminates a
submap's list.

## Flag bits

### Tile attributes — `map_eflg[]` (`maps.h:1008-1015`)

| Bit | Name | Meaning |
|---|---|---|
| 0x80 | `MAP_EFLG_VERT` | vertical move only (usually above `_CLIMB`) — ladder top |
| 0x40 | `MAP_EFLG_SOLID` | solid |
| 0x20 | `MAP_EFLG_SPAD` | super pad: solid, but launches entities upward |
| 0x10 | `MAP_EFLG_WAYUP` | solid except when moving up (one-way platform) |
| 0x08 | `MAP_EFLG_FGND` | foreground: hides entities behind it |
| 0x04 | `MAP_EFLG_LETHAL` | kills entities |
| 0x02 | `MAP_EFLG_CLIMB` | climbable |
| 0x01 | `MAP_EFLG_01` | unnamed; collected by the probe but never tested |

### Mark / entity flags — `ent.flags` (`ents.h:569-576`)

| Bit | Name | Meaning |
|---|---|---|
| 0x80 | `ENT_FLG_TRIGRICK` | triggered by Rick entering the trigger box |
| 0x40 | `ENT_FLG_TRIGSTOP` | triggered by Rick's stick jab |
| 0x20 | `ENT_FLG_TRIGBULLET` | triggered by a bullet |
| 0x10 | `ENT_FLG_TRIGBOMB` | triggered by a bomb blast |
| 0x08 | `ENT_FLG_LETHALI` | lethal once triggered ("initially") |
| 0x04 | `ENT_FLG_LETHALR` | lethal when the path restarts, and at spawn |
| 0x02 | `ENT_FLG_STOPRICK` | goes to slot 0 and blocks Rick; also suppresses the `+3` y nudge |
| 0x01 | `ENT_FLG_ONCE` | run once, then mark the placement inactive |

### Entity `n` flag

`ENT_LETHAL = 0x80` (`ents.h:555`) — set in `n`, tested as `n & ENT_LETHAL`, and stripped
with `n & 0x7f` before dispatch.

### Rick state — `e_rick_state` (`e_rick.h:437-447`)

| Bit | Name |
|---|---|
| 0x01 | `E_RICK_STSTOP` — stick out |
| 0x02 | `E_RICK_STSHOOT` |
| 0x04 | `E_RICK_STCLIMB` |
| 0x08 | `E_RICK_STJUMP` — airborne |
| 0x10 | `E_RICK_STZOMBIE` — dying |
| 0x20 | `E_RICK_STDEAD` |
| 0x40 | `E_RICK_STCRAWL` |

### Controls — `control_status` (`control.h:77-84`)

`RIGHT 0x01, DOWN 0x04, LEFT 0x02, UP 0x08, FIRE 0x10, EXIT 0x20, END 0x40, PAUSE 0x80`.
Three globals: `control_status` (held bits), `control_last` (last key event, used for the
"quit" test), `control_active` (window focus).

## Sprites and tiles

| | `GFXST` (built) | `GFXPC` |
|---|---|---|
| Sprite count | `0xD5` = **213** | `0x9b` = 155 |
| Sprite format | `U32 sprite_t[0x54]` — 0x15 rows × 4 columns of 8 pixels at 4 bpp; colour 0 = transparent | `spriteX_t[4][0x15]` of `{U16 mask, U16 pict}` — CGA 2 bpp with an explicit mask |
| Tile format | `U32 tile_t[8]` — 8 rows, 4 bpp | `U16 tile_t[8]` — 8 rows, 2 bpp |
| Tile banks | `TILES_BANKS_COUNT` = **3** × 256 tiles | 4 × 256 |
| Filter | not used | `tiles_setFilter()` ANDs the tile row — CGA colour selection |

Special tile numbers (`tiles.h:1682-1689`): `TILES_BULLET 0x01`, `TILES_BOMB 0x02`,
`TILES_RICK 0x03`, `TILES_NULL 0xFE` (string terminator), `TILES_CRLF 0xFF`.

Tile bank usage is documented with a "FIXME is this true?" (`tiles.h:1660-1668`); what
the code actually does is: bank 0 for all text/HUD/intro (`env.c:69`, `scr_*.c`), and
`map_tilesBank = (submap.page == 1) ? 2 : 1` for gameplay under `GFXST`
(`maps.c:110`) — i.e. **two gameplay banks**, banks 1 and 2.

## Sound tables

⚠️ **Superseded 2026-09-10 (T19, `audio-sndh.md`).** `sound_t` is now
`{U8 track; S8 d1;}` — an ST `music_track_table` index and a `play_music()` D1 value,
not a WAV buffer. Audio is the real engine running under 68000 emulation
(`src/audio_engine/`), output `AUDIO_S16SYS`. See `algo-system.md`'s Sound section.

Pre-T19, for the record: `sound_t { char* name (DEBUG only); U8* buf; U32 len; U8
dispose; }`. Audio was 8-bit unsigned mono at 22050 Hz, 8 mix channels, mixed by hand
in the SDL callback. 23 cached effects plus streamed music.
