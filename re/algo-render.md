# Rick Dangerous — Rendering & HUD Algorithms (0x4ABF8–0x4B855)

Exact transcription of the sprite blitter, background restore, and HUD subsystem,
to a level sufficient to reimplement pixel-identically without consulting Ghidra.

Source of truth: raw 68000 disassembly. Struct field names follow
`re/data-structures.md`. Entity records are `SpriteEntity` (0x4C bytes) in
`sprite_list` at `0x4A702`, terminated by a `wType == 0xFFFF` sentinel.

**Calling convention:** hand-written assembler — arguments are in registers, there is
no stack frame. Each function below states its own convention. `A0` is by far the
most common "current entity" register.

---

## Screen model (constants used throughout)

| Constant | Value | Meaning |
|---|---|---|
| Screen size | 320 × 200, 4 bitplanes | ST low-resolution |
| Bytes per scanline | **160** (`0xA0`) | 4 planes × 1 word per 16 px × 20 groups |
| Bytes per 16-px group | **8** | words `p0,p1,p2,p3` consecutive |
| Buffer size | **32000** (`0x7D00`) | one full screen |
| Screen buffer A | `0x70000` | |
| Screen buffer B | `0x78000` | differs from A only in **bit 15** |
| `g_screen_page` | `0x492EA` (long) | holds *one* of the two buffer addresses |
| **Draw target** | `g_screen_page ^ 0x8000` | the *other* buffer — what everything draws into |
| Background cache | `0x65B00` | 32000-byte clean background, same geometry as a screen |
| `g_scroll_active` | `0x4A6FE` (byte) | non-zero while a room scroll is animating |
| `g_scroll_delta_y` | `0x4A700` (word) | per-frame scroll delta, applied to Y fields |

**Buffer/flag pairing.** Every entity carries two independent render-state blocks,
one per screen buffer:

| Offset | Buffer-A block | Buffer-B block |
|---|---|---|
| flags byte | `0x16` `bRender_flags_a` | `0x1C` `bRender_flags_b` |
| pad | `0x17` | `0x1D` |
| rows−1 | `0x18` `nAnim_tick_a` | `0x1E` `nAnim_tick_b` |
| screen offset | `0x1A` `wScreen_offset_a` | `0x20` `wScreen_offset_b` |

Flag bits: **bit 0** = drawn/draw-enable, **bit 1** = wide (3 groups, shifted blit),
**bit 2** = erase-pending (entity vanished, background still needs restoring).

Selecting the block for the *current* draw target, as computed by both
`render_sprites` and `blit_backgrounds`:

```c
uint32_t d = g_screen_page;
uint32_t target = d ^ 0x8000;          /* draw here */
RenderBlock *rb = (d & 0x8000) ? &e->block_a   /* offset 0x16 */
                               : &e->block_b;  /* offset 0x1C */
```

`despawn_offscreen_entity` deliberately uses the **opposite** selection, so that the
erase-pending flag lands on the buffer holding the *stale* image (see below).

---

## hide_entity — 0x4AC08

> ⚠️ **The Ghidra function starts at 0x4ABF8, which is wrong.** Bytes
> `0x4ABF8`–`0x4AC07` are four more entries of `sprite_type_dispatch` (see
> Corrections). The real entry point is **`0x4AC08`**. The function has **no
> callers** (`get_xrefs_to` → none) and appears to be dead code.

`void hide_entity(SpriteEntity *A0)`

```c
e->bRender_flags_a &= ~0x01;   /* bclr #0 */
e->bRender_flags_b &= ~0x01;
```

---

## clear_sprite_flags — 0x4AC16

`void clear_sprite_flags(void)` — clobbers A0 (saved/restored).

```c
for (SpriteEntity *e = sprite_list; e->wType != 0xFFFF; e++) {
    e->wType = 0;
    *(uint16_t*)&e->bRender_flags_a = 0;   /* WORD write: clears flags + pad 0x17 */
    *(uint16_t*)&e->bRender_flags_b = 0;   /* WORD write: clears flags + pad 0x1D */
}
```

Note both writes are **word**-sized, so they also clear the pad bytes at 0x17/0x1D.
Frees every slot and drops all render state, for both buffers.

---

## despawn_offscreen_entity — 0x4AC3E

`void despawn_offscreen_entity(SpriteEntity *A0)` — preserves D0.

```c
e->wType = 0;                       /* free the slot immediately */
if (g_screen_page & 0x8000)
    e->bRender_flags_b |= 0x04;     /* bset #2 on block B */
else
    e->bRender_flags_a |= 0x04;     /* bset #2 on block A */
```

**Why the inverted selection matters.** `render_sprites` draws into
`g_screen_page ^ 0x8000` using the block chosen by `(g_screen_page & 0x8000)`.
Here the *other* block is marked. That block describes the position the sprite
occupied in the buffer that is **not** being drawn this frame — i.e. the buffer that
still shows the sprite. Setting bit 2 there makes the next `blit_backgrounds` pass
over that buffer restore the stale footprint even though `wType` is now 0.
Without this, freeing the slot would leave a permanent ghost.

---

## blit_backgrounds — 0x4AC8C

`void blit_backgrounds(void)` — saves/restores D0,D1,A0,A1,A2,A3.

Restores clean background over every entity's previous footprint, from the cache at
`0x65B00` into the draw target. Runs **before** `render_sprites` each frame.

```c
for (SpriteEntity *e = sprite_list; e->wType != 0xFFFF; e++) {
    uint32_t d = g_screen_page;
    uint32_t target = d ^ 0x8000;
    RenderBlock *rb = (d & 0x8000) ? &e->block_a : &e->block_b;

    if (e->wType == 0) {                 /* freed slot */
        if (!(rb->flags & 0x04)) continue;   /* nothing pending */
        rb->flags &= ~0x04;                  /* consume the erase request */
    }
    /* NOTE: when wType != 0 the bit-2 test is skipped entirely */

    if (!(rb->flags & 0x01)) continue;   /* was never drawn here */
    if (g_scroll_active)     continue;   /* whole screen is being redrawn anyway */

    uint8_t *src = (uint8_t*)0x65B00 + rb->screen_offset;
    uint8_t *dst = (uint8_t*)target   + rb->screen_offset;
    int rows = rb->rows_minus_1;         /* dbf semantics: rows+1 iterations */

    if (rb->flags & 0x02) {              /* WIDE: 3 groups = 24 bytes/row */
        for (int i = 0; i <= rows; i++) {
            memcpy(dst, src, 24);
            src += 160; dst += 160;
        }
    } else {                             /* NARROW: 2 groups = 16 bytes/row */
        for (int i = 0; i <= rows; i++) {
            memcpy(dst, src, 16);
            src += 160; dst += 160;
        }
    }
}
```

**Exact pointer arithmetic in the original.** Each row is copied as
`move.l (A2)+,(A3)+` repeated, with the *last* longword using non-incrementing
`(A2),(A3)`, then a `lea` supplies the remainder of the 160-byte stride:

- narrow: 3 × post-increment (+12) + 1 non-incrementing, then `lea 0x94` (+148) → **160**
- wide: 5 × post-increment (+20) + 1 non-incrementing, then `lea 0x8C` (+140) → **160**

Both row counts have a fully unrolled fast path for `rows_minus_1 == 0x14` (21 rows,
the default sprite height) consisting of 21 inline row blocks; otherwise a `dbf`
loop of identical body. The unrolled and looped versions are semantically identical —
a reimplementation needs only the loop.

---

## render_sprites — 0x4B032

`void render_sprites(void)` — saves/restores D0–D7, A0–A6.

The main entity pass: runs each entity's behaviour handler, clips, computes the
screen address, and composites the sprite. Called after `blit_backgrounds`.

### Outer loop

```c
for (SpriteEntity *e = sprite_list; e->wType != 0xFFFF; e++) {
    if (e->wType == 0) continue;                  /* free slot */

    if (g_scroll_active) {
        /* During a scroll, behaviour handlers are NOT run; instead every
           Y-ish field is displaced by the scroll delta.                     */
        int16_t d = g_scroll_delta_y;
        e->nPosY        += d;   /* 0x06 */
        e->nSpawnY      += d;   /* 0x0E */
        e->nTrigBoxYMin += d;   /* 0x3E */
        e->nTrigBoxYMax += d;   /* 0x42 */
        /* falls straight through to clipping */
    } else {
        /* dispatch: NOTE index is wType-1, and there is NO bounds check */
        void (*h)(SpriteEntity*) = sprite_type_dispatch[e->wType - 1];
        h(e);                                     /* A0 = e, preserved via stack */
        if (e->wType == 0) continue;              /* handler despawned it */
    }
    ... clipping and blit, below ...
}
```

Confirms the scroll axis is **Y** (offset 0x06), matching the axis note in
`re/data-structures.md`.

### Stage 1 — despawn clipping (frees the slot)

Operating on `D1 = e->nPosX` (0x04) and `D2 = e->nPosY` (0x06):

```c
if (e->nPosX <  -8   ) { despawn_offscreen_entity(e); continue; }
if (e->nPosX >  0xF0 ) { despawn_offscreen_entity(e); continue; }
if (e->nPosY <   0   ) { despawn_offscreen_entity(e); continue; }
if (e->nPosY >  0x142) { despawn_offscreen_entity(e); continue; }
```

### Stage 2 — select block, reset it, resolve row count and graphics

```c
uint32_t d = g_screen_page;
uint32_t target = d ^ 0x8000;
RenderBlock *rb = (d & 0x8000) ? &e->block_a : &e->block_b;

*(uint16_t*)rb = 0;        /* word write: clears flags byte AND pad     */
rb->flags |= 0x01;         /* provisionally mark "drawn"                */

int rows = e->nRow_count;              /* 0x14 */
if (rows == 0) rows = 0x15;            /* default 21 */
uint8_t *gfx = e->gfx_data;            /* 0x22 */
if (gfx == NULL) { rb->flags &= ~0x01; continue; }
```

### Stage 3 — visibility clipping (does *not* free the slot)

Horizontal — the drawable X window is narrower than the despawn window:

```c
if (e->nPosX < 0)      { rb->flags &= ~0x01; continue; }
if (e->nPosX > 0xE8)   { rb->flags &= ~0x01; continue; }
```

Vertical — the visible world-Y window is **[0x40, 0x100)**, i.e. 192 rows, and
partial sprites are clipped by advancing the source pointer:

```c
if (e->nPosY < 0x40) {                       /* overlaps the top edge */
    if (e->nPosY <= 0x40 - rows) { rb->flags &= ~0x01; continue; }  /* fully above */
    int clipped = 0x40 - e->nPosY;
    rows -= clipped;
    gfx  += clipped * 16;                    /* 16 bytes per sprite row */
    y     = 0x40;                            /* clamp to window top */
} else {
    if (e->nPosY > 0xFF - rows) {            /* overlaps the bottom edge */
        if (e->nPosY >= 0xFF) { rb->flags &= ~0x01; continue; }     /* fully below */
        rows = 0x100 - e->nPosY;             /* clip at bottom; gfx unchanged */
    }
    y = e->nPosY;
}
rows -= 1;
rb->rows_minus_1 = rows;                     /* stored for blit_backgrounds */
```

The `clipped * 16` advance is independent confirmation that a sprite row is
**16 bytes**.

### Stage 4 — screen address and shift

```c
int32_t xa = e->nPosX + 0x20;                /* X biased by 32 px */
int32_t ya = y - 0x38;                       /* Y biased: window top -> row 8 */

uint16_t offset = (uint16_t)(ya * 160)       /* computed as (ya<<5) + ((ya<<5)<<2) */
                + (uint16_t)((xa & 0xFFF0) >> 1);   /* (x/16)*8 bytes */
rb->screen_offset = offset;

uint8_t *dst = (uint8_t*)target + offset;
int shift = xa & 0x0F;                       /* 0..15 pixels */
```

Playfield geometry that falls out of these constants: world-Y `0x40..0xFF` maps to
screen rows `8..199`, so **the top 8 scanlines are reserved** (the HUD strip).
World-X `0..0xE8` maps to screen pixels `32..264`.

### Stage 5a — ALIGNED blit (`shift == 0`), 32 px wide

Two 16-px groups. `rb->flags` bit 1 stays **clear**, which is what tells
`blit_backgrounds` to use its 16-byte narrow path.

Source layout, confirmed here: each row is **4 longwords, plane-major** —
`D0` = plane 0 across 32 px, `D1` = plane 1, `D2` = plane 2, `D3` = plane 3.
(This is *not* the screen's interleaved order; the blitter converts.)

```c
for (int r = 0; r <= rows; r++) {
    uint32_t p0 = *(uint32_t*)(gfx +  0), p1 = *(uint32_t*)(gfx +  4);
    uint32_t p2 = *(uint32_t*)(gfx +  8), p3 = *(uint32_t*)(gfx + 12);
    gfx += 16;

    uint32_t m = ~(p0 | p1 | p2 | p3);       /* 1 = transparent (colour 0)  */
    uint16_t m_hi = m >> 16;                 /* mask for pixels  0..15      */
    uint16_t m_lo = m & 0xFFFF;              /* mask for pixels 16..31      */

    uint16_t *g0 = (uint16_t*)(dst);         /* pixels  0..15: p0,p1,p2,p3  */
    uint16_t *g1 = (uint16_t*)(dst + 8);     /* pixels 16..31               */

    /* group 1 first (low words), then group 0 (high words) */
    g1[0] = (g1[0] & m_lo) | (uint16_t)(p0);        g1[1] = (g1[1] & m_lo) | (uint16_t)(p1);
    g1[2] = (g1[2] & m_lo) | (uint16_t)(p2);        g1[3] = (g1[3] & m_lo) | (uint16_t)(p3);
    g0[0] = (g0[0] & m_hi) | (uint16_t)(p0 >> 16);  g0[1] = (g0[1] & m_hi) | (uint16_t)(p1 >> 16);
    g0[2] = (g0[2] & m_hi) | (uint16_t)(p2 >> 16);  g0[3] = (g0[3] & m_hi) | (uint16_t)(p3 >> 16);

    dst += 160;
}
```

The original writes plane pairs as longwords (`and.l D5,D6` with `D5` holding the
mask duplicated into both halves, then `or.w` twice with a `swap` between), and
advances `A2` by one `(A2)+` (+4) plus `lea 0x9C` (+156) = **160**.

### Stage 5b — SHIFTED blit (`shift != 0`), spans 3 groups

`rb->flags |= 0x02` is set here (`bset #1`), which is exactly what makes
`blit_backgrounds` restore 24 bytes per row instead of 16.

Three destination groups: `A2 = dst`, `A3 = dst+8`, `A4 = dst+16`.

The mask and each plane are rotated right by `shift` using the 68000 idiom
"place the 16-bit value in the low half of a longword, `ror.l` by n" — after which
the **low word is the part that stays in this group** and the **high word is the
part that spills into the next group**.

```c
for (int r = 0; r <= rows; r++) {
    uint32_t p[4] = { ld32(gfx+0), ld32(gfx+4), ld32(gfx+8), ld32(gfx+12) };
    gfx += 16;
    uint32_t m = ~(p[0]|p[1]|p[2]|p[3]);

    /* --- masks: bits not covered by the sprite must read as 1 (transparent) --- */
    uint32_t A = ror32((0xFFFF0000u | (m >> 16)),    shift);
    uint32_t B = ror32((0xFFFF0000u | (m & 0xFFFF)), shift);
    uint16_t mask0 = (uint16_t)(A);                    /* group 0 */
    uint16_t mask1 = (uint16_t)(A >> 16) & (uint16_t)(B);  /* group 1 */
    uint16_t mask2 = (uint16_t)(B >> 16);              /* group 2 */

    uint16_t *g0 = (uint16_t*)(dst), *g1 = (uint16_t*)(dst+8), *g2 = (uint16_t*)(dst+16);

    for (int pl = 0; pl < 4; pl++) {
        uint32_t hi = ror32((uint32_t)(p[pl] >> 16),    shift); /* pixels 0..15  */
        uint32_t lo = ror32((uint32_t)(p[pl] & 0xFFFF), shift); /* pixels 16..31 */
        uint16_t s0 =  (uint16_t)(hi);                       /* stays in group 0 */
        uint16_t s1 =  (uint16_t)(lo) | (uint16_t)(hi >> 16);/* group 1          */
        uint16_t s2 =  (uint16_t)(lo >> 16);                 /* group 2          */

        g0[pl] = (g0[pl] & mask0) | s0;
        g1[pl] = (g1[pl] & mask1) | s1;
        g2[pl] = (g2[pl] & mask2) | s2;
    }
    dst += 160;
}
```

In the original, `A3`/`A4` are recomputed as `A2+8` / `A2+0x10` at the top of every
row iteration; only `A2` is advanced (3 × `(A2)+` = +6, then `lea 0x9A` = +154,
total **160**). The row counter lives in `A5` across the body because `D7` is used
as scratch (`move.w A5w,D7w` then `dbf D7w` then `movea.w D7w,A5` on re-entry).

### The transparency rule — confirmed

There is **no stored mask**. For every row the blitter derives
`mask = NOT(plane0 | plane1 | plane2 | plane3)`, so a pixel is transparent exactly
when its colour index is 0. The composite is the classic
`dst = (dst & mask) | src`. This matches the note already in
`re/data-structures.md` and is confirmed at both `0x4B1C8` (shifted) and
`0x4B2BA` (aligned).

---

## init_hud_state — 0x4B358

`void init_hud_state(void)`

```c
score_bcd[0] = score_bcd[1] = score_bcd[2] = 0;  /* 0x4B326,27,28 */
bBullets = bDynamite = bLives = 6;               /* 0x4B32A,2C,2E */
*(uint32_t*)0x4B330 = 0;   /* score glyph buffer, first 4 bytes  */
*(uint16_t*)0x4B334 = 0;   /* score glyph buffer, last 2 bytes   */
dirty_bullets = dirty_dynamite = dirty_lives = dirty_score = 0xFF;
```

### The four HUD glyph buffers

Each is 6 glyph bytes followed by a **0xFF terminator** (verified in memory):

| Buffer | Terminator | Drawn by | Screen pos (D0) | Icon (D2) |
|---|---|---|---|---|
| `0x4B330` score | `0x4B336` | `hud_update_score` | `0x10` | — (digits) |
| `0x4B338` bullets | `0x4B33E` | `hud_update_bullets` | `0x31` | `0x0A` |
| `0x4B340` dynamite | `0x4B346` | `hud_update_dynamite` | `0x51` | `0x0B` |
| `0x4B348` lives | `0x4B34E` | `hud_update_lives` | `0x78` | `0x0C` |

Dirty flags: score `0x4B350`, bullets `0x4B352`, dynamite `0x4B354`, lives `0x4B356`.

Note the score buffer overlaps what `re/data-structures.md` types as
`wScore_display_hi` (+0xA) and `dwScore_display_lo` (+0xC); functionally it is a
single `char[6]` glyph string.

---

## hud_update_score — 0x4B3BC

```c
if (dirty_score) {                       /* 0x4B350 */
    draw_string(A0 = 0x4B330, D0 = 0x10);   /* 0x49466 */
    dirty_score = 0;
}
```

## hud_update_bullets / dynamite / lives — 0x4B460 / 0x4B494 / 0x4B4C8

Identical shape; only the four constants differ (table above):

```c
if (dirty_X) {
    draw_hud_count(A0 = buffer, D0 = screen_pos, D1 = counter_value, D2 = icon_char);
    dirty_X = 0;
}
```

## draw_hud_count — 0x4B4FC

`void draw_hud_count(char *A0, uint16_t D0 pos, uint16_t D1 count, uint8_t D2 icon)`

```c
*(uint32_t*)(A0 + 0) = 0x5E5E5E5E;      /* 0x5E = blank glyph */
*(uint16_t*)(A0 + 4) = 0x5E5E;          /* 6 blanks total */
if (D1 != 0)
    for (int i = D1 - 1; i >= 0; i--)   /* dbf loop, descending */
        A0[i] = D2;
draw_string(A0, D0);                    /* relies on the 0xFF at A0[6] */
```

## add_score — 0x4B3E4

`void add_score(uint32_t D0)` — D0's low 3 bytes are a packed BCD delta.

```c
*(uint32_t*)0x4B51E = D0;               /* scratch; low 3 bytes are the addend */

/* 3-byte BCD add, least-significant first, via predecrement ABCD */
CCR &= ~(X | C);  CCR |= Z;             /* andi #0xEE,CCR — required ABCD prologue */
score_bcd[2] = abcd(score_bcd[2], *(uint8_t*)0x4B521);   /* 0x4B328 */
score_bcd[1] = abcd(score_bcd[1], *(uint8_t*)0x4B520);   /* 0x4B327 */
score_bcd[0] = abcd(score_bcd[0], *(uint8_t*)0x4B51F);   /* 0x4B326 */

/* unpack 3 BCD bytes -> 6 glyph digits, most-significant first */
*(uint8_t*)0x4B335 = score_bcd[2] & 0x0F;   *(uint8_t*)0x4B334 = score_bcd[2] >> 4;
*(uint8_t*)0x4B333 = score_bcd[1] & 0x0F;   *(uint8_t*)0x4B332 = score_bcd[1] >> 4;
*(uint8_t*)0x4B331 = score_bcd[0] & 0x0F;   *(uint8_t*)0x4B330 = score_bcd[0] >> 4;

dirty_score = 0xFF;
```

Font glyph indices **0–9 are the digits**, since raw nibbles are written as glyphs.
The `andi #0xEE,CCR` clears X and C while leaving Z set — the standard multi-precision
BCD idiom (ABCD only ever *clears* Z).

---

## start_level — 0x4B588

`void start_level(void)`

> ⚠️ **Corrects `re/data-structures.md`:** the `LevelStartInfo` table base is
> **`0x4B522`**, not `0x4B526`, and there is a leading pointer field at +0 that the
> existing doc omits (its fields are all listed 4 bytes early).

```c
LevelStartInfo *L = (LevelStartInfo*)0x4B522 + level_index;   /* stride 20 */

player.nPosX  = L->wStartX;         /* +0x04 -> 0x4A752 */
player.nPosY  = L->wStartY;         /* +0x06 -> 0x4A754 */
world_row_base     = L->wStartWorldRow;  /* +0x08 -> 0x495CA */
cur_room_header_ptr= L->pRoomHeader;     /* +0x0A -> 0x495D8 */

bBullets = 6;  bDynamite = 6;            /* bLives deliberately untouched */
dirty_bullets = dirty_dynamite = 0xFF;

show_level_intro_screen(A0 = L->pIntroText,   /* +0x00 */
                        A1 = L->pIntroSprite, /* +0x10 */
                        D0 = L->wIntroParam); /* +0x0E */
```

### Corrected LevelStartInfo (20 bytes, base 0x4B522)

| Off | Field | L0 | L1 | L2 | L3 |
|---|---|---|---|---|---|
| +0x00 | `pIntroText` | `0x4B8FE` | `0x4BA16` | `0x4BB24` | `0x4BC28` |
| +0x04 | `wStartX` | 8 | 8 | 8 | 8 |
| +0x06 | `wStartY` | 0x8B | 0x8B | 0x8B | 0x8B |
| +0x08 | `wStartWorldRow` | 0x08 | 0x68 | 0x10 | 0x10 |
| +0x0A | `pRoomHeader` | `0x47620` | `0x4769E` | `0x47738` | `0x47834` |
| +0x0E | `wIntroParam` | 0x12 | 0x60 | 0x84 | 0xA8 |
| +0x10 | `pIntroSprite` | `0x46CE2` | `0x46CFC` | `0x46D20` | `0x46D3A` |

`pIntroText` points into `0x4B8FE`–`0x4BE1F` — the region `find_code_gaps` reports as
an unresolved gap. **That gap is the level intro/story text data.** A 5th pointer
`0x4BD14` follows the 4th entry at `0x4B572`, so a 5th table entry may exist.

---

## show_level_intro_screen — 0x4B5F4

`void show_level_intro_screen(uint8_t *A0 text, void *A1 sprite_def, uint16_t D0 param)`

```c
palette_fade_out();                       /* 0x493FE */
D2 = param;  A2 = text;  A4 = sprite_def;
vsync_wait();                             /* 0x49310 */
reset_hud_dirty_and_redraw();             /* 0x4B7FE */

/* 1. Six rows of a 6-glyph banner at 0x4B7BA, glyph codes running param, param+1, ... */
D0 = 0x1941;
for (int row = 5; row >= 0; row--) {
    for (int i = 0; i < 6; i++) *(uint8_t*)(0x4B7BA + i) = D2++;
    draw_string(A0 = 0x4B7BA, D0);
    D0 += 0x500;                          /* next banner row */
}

/* 2. Story text: byte stream at A2, one glyph per cell via draw_string_xy */
D1 = 2; D0 = 5;
for (;;) {
    uint8_t c = *A2++;
    if (c == 0xFF) {                      /* end of line */
        D1 += 1;
        if (D1 == 3) D1 = 0x0D;           /* skip a band of rows */
        D0 = 5; continue;
    }
    if (c == 0xFE) break;                 /* end of text */
    *(uint8_t*)0x4B7B8 = c;
    draw_string_xy(A0 = 0x4B7B8, D0, D1); /* 0x49446 */
    D0 += 1;
}

/* 3. Snapshot the finished screen into the background cache (32000 bytes) */
memcpy((void*)0x65B00, (void*)0x78000, 32000);   /* 1024 × 8 longwords */

/* 4. Activate the decorative sprite in slot 12 */
clear_sprite_flags();
sprite_list[12].wType               = 0x4A;   /* == 74 */
sprite_list[12].nPosX               = ((uint16_t*)A4)[0];
sprite_list[12].nPosY               = ((uint16_t*)A4)[1];
A4 += 4;
sprite_list[12].movement_path_table = A4;            /* 0x4AAC8 */
sprite_list[12].anim_frame_table    = *(void**)(A4+6);/* 0x4AAC4 */
sprite_list[12].nAnimFrameIdx = 0;                   /* 0x4AABC */
sprite_list[12].nPathStepIdx  = 0;                   /* 0x4AABE */
sprite_list[12].nPathStepTick = 0;                   /* 0x4AAC0 */

play_music(D0 = level_index, D1 = 0);
palette_fade_in();                                   /* 0x49394 */

/* 5. Animate until a key is pressed (bit 7 of the input bitmask at 0x4922B) */
do {
    blit_backgrounds();
    draw_glyph_string(A0 = 0x4B7C2, A1 = 0x79440);   /* 0x494AC */
    A1 += 0x500;
    for (int i = 6; i >= 0; i--) {                   /* prompt block, buffer B */
        draw_glyph_string(A0 = 0x4B7D6, A1);  A1 += 0x19;
        draw_glyph_string(A0 = 0x4B7D6, A1);  A1 += 0x4E7;
    }
    A1 = 0x71440;                                    /* same, buffer A */
    for (int i = 6; i >= 0; i--) {
        draw_glyph_string(A0 = 0x4B7D8, A1);  A1 += 0x19;
        draw_glyph_string(A0 = 0x4B7D8, A1);  A1 += 0x4E7;
    }
    draw_glyph_string(A0 = 0x4B7CC, A1);
    render_sprites();
    flip_screen_buffer();                            /* 0x49336 */
    vsync_wait();
} while (!(*(uint8_t*)0x4922B & 0x80));

/* 6. On level 4, wait for the music to finish */
if (level_index == 4)
    while (*(uint16_t*)0x45096 != 0) { }
    vsync_wait();

palette_fade_out();
reset_hud_dirty_and_redraw();
sprite_list[12].wType            = 0;   /* 0x4AA92 */
sprite_list[12].bRender_flags_a  = 0;   /* 0x4AAA8 */
sprite_list[12].bRender_flags_b  = 0;   /* 0x4AAAE */
spawn_player_entity();                  /* 0x4BFAE */
```

`sprite_list[12]` is at `0x4AA92` (= `0x4A702 + 12 × 0x4C`), confirming the slot
index and that `wType = 0x4A` is decimal **74**.

**Uncertainty:** the exact glyph/cell semantics of `draw_glyph_string` and the
meaning of the `0x19` / `0x4E7` / `0x500` screen strides belong to that function
(0x494AC, another fork's range) — **needs cross-checking** against its transcription.

---

## clear_both_screen_buffers — 0x4B7DA

```c
clear_screen_buffer_32000(A0 = g_screen_page);
clear_screen_buffer_32000(A0 = g_screen_page ^ 0x8000);
```

## reset_hud_dirty_and_redraw — 0x4B7FE

```c
clear_both_screen_buffers();
dirty_score = dirty_bullets = dirty_dynamite = dirty_lives = 0xFF;
hud_update_score(); hud_update_bullets(); hud_update_dynamite(); hud_update_lives();
```

## clear_screen_buffer_32000 — 0x4B83A

`void clear_screen_buffer_32000(uint32_t *A0)` — clobbers D0, advances A0.

```c
for (int i = 0; i <= 0x3E7; i++) {   /* 1000 iterations */
    /* 8 × clr.l (A0)+ = 32 bytes */
}
/* 1000 × 32 = 32000 bytes exactly */
```

---

## Frame order (as used by `show_level_intro_screen` and the main loop)

```
blit_backgrounds();   /* restore background over last frame's sprites */
... draw HUD / text ...
render_sprites();     /* run handlers, clip, composite sprites       */
flip_screen_buffer(); /* toggles g_screen_page                        */
vsync_wait();
```

Because `g_screen_page` toggles every flip, the per-entity A/B blocks alternate,
so each buffer's restore always uses the geometry that was actually drawn into it.

---

## Notes / uncertainties

- `hide_entity` (`0x4AC08`) has no callers — dead code. *(Its entry point was once
  recorded as `0x4ABF8`, which is really dispatch index 70; corrected 2026-08-29.)*
- The unrolled 21-row fast paths in `blit_backgrounds` are pure optimisation.
- The `0x1941` / `0x500` banner offsets and the intro-screen glyph strides are
  reproduced literally; their *pixel* meaning depends on `draw_string` /
  `draw_glyph_string`, both now transcribed in `algo-system.md` (`0x49466` / `0x494AC`).
  ✅ No longer open — resolved 2026-08-29 by the system write-up, not by a live run.
- `0x45096` (music-busy word) and `0x4922B` (input bitmask) are read here but owned
  by other subsystems.
