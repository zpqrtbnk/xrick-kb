# Entities — `ents.c`, `e_them.c`, `e_box.c`, `e_bonus.c`, `e_sbonus.c`, `e_bomb.c`, `e_bullet.c`

Slot layout, the `ent_t` record and the dispatch table are in `data-model.md`. This file
covers behaviour.

## Lifecycle

```
map_init()  -> ent_reset()      clear slots, then
            -> ent_actvis() x3  spawn everything in the top / visible / bottom bands
scroll      -> ent_actvis() x1  spawn the band that just scrolled in
each frame  -> ent_action()     dispatch every live slot
            -> ents_paintAll()  erase, draw, and compute dirty rectangles
```

### `ent_reset` (ASM 2520) — `ents.c:59`

```c
E_RICK_STRST(E_RICK_STSTOP);
e_bomb_lethal = FALSE;
ent_ents[0].n = 0;
for (i = 2; ent_ents[i].n != 0xff; i++) ent_ents[i].n = 0;
```

Slot 1 (Rick) is deliberately skipped; slot 0 is cleared explicitly.

### `ent_actvis(frow, lrow)` (ASM 1F40) — `ents.c:139`

Scans `map_marks` from `map_submaps[env_submap].mark`, skipping marks with
`row < frow`, then processing every mark with `row < lrow`, stopping at `row == 0xff`.
Marks with `MAP_MARK_NACT` (0x80 in `.ent`) are skipped.

Slot choice:

```
if (!(flags & ENT_FLG_STOPRICK)):
    ent >= 0x10  -> ent_creat1  (slots 4..8, c1 = 0)      boxes, bonuses, type-3
    ent <  0x10  -> ent_creat2  (slots 9..B, c1 = 2)      type-1 and type-2 enemies
else:
    slot 0, only if free ; c1 = 0
```

`ent_creat2` first refuses if any of slots 9..B already holds this same `mark`
(`ents.c:111-113`) — a mark cannot spawn a second copy of itself while the first is
alive. `ent_creat1` has no such check.

Initialisation (`ents.c:222-282`) — see `data-model.md` for the `xy`/`lt` bit decode.
Two subtleties:

- `if (flags & ENT_FLG_LETHALR) n |= ENT_LETHAL` — an entity that is "lethal on restart"
  is lethal from the very first frame too.
- `if ((flags & all four TRIG bits) == all four && slot >= 0x09)` then
  `sprbase = (U8)(entdata.sni & 0x00FF)` (`ents.c:266-268`). The port could not explain
  this: *"FIXME what is this? ... What is the point?"* ✅ **Explained 2026-09-04 — see
  `xref.md` and `../../PLAN.md` T9.** The condition selects exactly the type-1a/1b
  walking enemies (`e >= 9` **is** `mark.ent < 0x10`, via the `ent_creat1`/`ent_creat2`
  split; all four trigger bits is the shipped encoding for "killable by touch, jab,
  bullet and bomb"). For those entries `sni` is not a movement index at all but a
  **second sprite number** — the walk-cycle base — because type-1 enemies move under AI
  rather than along `ent_mvstep` paths, leaving the field free. The visible effect the
  author noted ("the falling guy on the right on submap 3 ... changes when hitting the
  ground") follows: `ent.sprite` keeps its `spr`-derived value until the handler
  recomputes it from the new `sprbase`.

## Enemies — `e_them.c`

Four behaviours plus the shared dying state.

### Shared death — `e_them_gozombie(e)` (ASM 237B) — `e_them.c:72`

```c
n = 0x47; front = TRUE; offsy = -0x0400; WAV_DIE; env_score += 50;
if (flags & ENT_FLG_ONCE) map_marks[mark].ent |= MAP_MARK_NACT;
c1 /*offsx*/ = (x >= 0x80 ? -0x02 : 0x02);
```

Note the score is a flat **50** per kill, and that the corpse drifts at ±2 px/frame,
where Rick's corpse drifts at ±3.

### `e_them_z_action` (ASM 23B8) — `e_them.c:285`

```c
sprite = sprbase + ((x & 0x04) ? 0x07 : 0x06);
i = (y << 8) + offsy + ylow;
if (y < 0 || y > 0x0140) { n = 0; return; }     /* tests the OLD y */
offsy += 0x0080; ylow = i; y = i >> 8;
x += offsx;  clamp x to [0, 0xE8]
```

### `u_themtest(e)` (ASM 122E) — `e_them.c:51`

An enemy is killed by anything lethal in **slot 0 or slots 4..8**:

```c
if ((ent_ents[0].n & ENT_LETHAL) && u_boxtest(e, 0)) return TRUE;
for (i = 4; i < 9; i++) if ((ent_ents[i].n & ENT_LETHAL) && u_boxtest(e, i)) return TRUE;
```

This is exactly why the slot ranges matter: entities in 9..B are never lethal to other
entities, only to Rick.

### Types 1a / 1b — `e_them_t1_action2` (ASM 2242) — `e_them.c:102`

Ground walkers. `c1 = offsx`, `c2 = step_count`.

```
i = (y << 8) + offsy + ylow ; y = i >> 8
if (y > 0x140) { n = 0; return }                  /* fell off the bottom */
u_envtest(x, y, FALSE, ...)

if !(env1 & (VERT|SOLID|SPAD|WAYUP)):             /* falling */
    if (env1 & LETHAL) { gozombie; return }
    save y, ylow ; offsy += 0x0080 clamp 0x0800 ; return

/* on the ground */
sprite = sprbase + ent_sprseq[(x & 0x1c) >> 3] + (offsx < 0 ? 3 : 0)
offsy = 0x0080
y = (y & 0xFFF8) | 0x0003
if (latency) { latency--; return }
if (offsx == 0) return                            /* a stationary variant */

x_new = x + offsx
if (x < 0 || x > 0xE8) { step_count = 0; offsx = -offsx; return }
u_envtest(x_new, y, FALSE, ...)
if (env1 & (VERT|SOLID|SPAD|WAYUP)) { step_count = 0; offsx = -offsx; return }
if (env1 & LETHAL) { gozombie; return }
x = x_new

TYPE_1B: if ((x & 0x1e) != 0x10) return
         offsx = (x < rick.x) ? 0x02 : -0x02      /* re-aim, at most every 16 px */
         return
TYPE_1A: step_count++
         if ((trig_x >> 1) > step_count) return
         step_count = 0 ; offsx = -offsx          /* patrol turn-around */
```

`TYPE_1A = 0x00`, `TYPE_1B = 0xff` (`e_them.c:28-29`). The patrol range comes from
`trig_x`, the field otherwise used as a trigger-box origin — the port flags this with
"FIXME why trig_x (b16)??" (`e_them.c:202`). The sprite index uses `ent_sprseq` as a
4-entry walk cycle keyed on `(x & 0x1c) >> 3`, with `+3` for the left-facing set.

**Wrapper** `e_them_t1_action` (ASM 21CF, `e_them.c:219`) runs the mover, then, in order:

```
u_themtest(e)                              -> gozombie
bullet live && u_fboxtest(e, bullet.x + (offsx < 0 ? 0 : 0x18), bullet.y)
                                           -> bullet.n = 0, gozombie
e_bomb_lethal && e_bomb_hit(e)             -> gozombie
Rick STOP && u_fboxtest(e, stop_x, stop_y) -> latency = 0x14      (stunned by the stick)
e_rick_boxtest(e)                          -> e_rick_gozombie()
```

The bullet's test point is its **leading edge**: the tail when moving left, `+0x18` when
moving right.

### Type 2 — `e_them_t2_action2` (ASM 2792) — `e_them.c:328`

The chaser: walks, falls, and climbs ladders to reach Rick. `c1 = flgclmb`,
`c2 = offsx`.

```
if (latency) latency--

if (flgclmb == TRUE):                                 /* CLIMBING */
    if (latency) return
    sprite = sprbase + 0x08 + (((x ^ y) & 4) ? 1 : 0)
    if ((y & 0xfe) != (rick.y & 0xfe)) goto ymove
  xmove:
    offsx = (x < rick.x) ? 2 : -2 ; x_new = x + offsx
    u_envtest -> (SOLID|SPAD|WAYUP) ? return : LETHAL ? gozombie : x = x_new
    if (env1 & (VERT|CLIMB)) return                    /* still on the ladder */
    goto climbing_not
  ymove:
    yd = (y < rick.y) ? 2 : -2 ; y_new = y + yd
    if (y_new < 0 || y_new > 0x140) { n = 0; return }
    u_envtest -> if (SOLID|SPAD|WAYUP) { yd < 0 ? goto xmove : goto climbing_not }
    y = y_new
    if (env1 & (VERT|CLIMB)) return

climbing_not:
    flgclmb = FALSE
    i = (y << 8) + offsy + ylow ; y_new = i >> 8 ; u_envtest(x, y_new)
    if !(env1 & (SOLID|SPAD|WAYUP)):
        if (LETHAL) gozombie
        if (y_new > 0x140) { n = 0; return }
        if (!(env1 & VERT)) { save y, ylow; offsy += 0x80 clamp 0x800; return }   /* fall */
        if ((x & 0x07) == 0x04 && y_new < rick.y) { flgclmb = TRUE; return }      /* grab */
    /* blocked, or standing on a ladder top */
    y = (y & 0xf8) | 0x03 ; offsy = 0x0100
    if (latency) return
    if ((env1 & CLIMB) && ((x & 0x0e) == 0x04) && (y > rick.y)) { flgclmb = TRUE; return }
    sprite = sprbase + ent_sprseq[(offsx < 0 ? 4 : 0) + ((x & 0x0e) >> 3)]
    if (offsx == 0) offsx = 2
    x_new = x + offsx
    if (x_new < 0xe8):
        u_envtest(x_new, y)
        if !(env1 & (VERT|SOLID|SPAD|WAYUP)):
            x = x_new
            if ((x & 0x1e) != 0x08) return
            <<random direction>>                                          /* see below */
            offsx = (bl & 1) ? -2 : 2 ; return
    if (offsx == 0) offsx = 2 else offsx = -offsx                         /* U-turn */
```

Two ladder-grab conditions with **different x-alignment masks** — `(x & 0x07) == 0x04`
when climbing up out of a fall, `(x & 0x0e) == 0x04` when starting from the ground. Both
appear in the source as written; whether that asymmetry is in the original is a question
for the comparison.

#### The randomiser ("Black Magic (tm)") — `e_them.c:480-494`

```c
static U16 bx; U8 *bl = &bx, *bh = &bx + 1;
static U16 cx; U8 *cl = &cx, *ch = &cx + 1;
static U16 *sl = (U16*)&e_them_rndseed, *sh = (U16*)&e_them_rndseed + 2;

bx = e_them_rndnbr + *sh + *sl + 0x0d;
cx = *sh;
*bl ^= *ch; *bl ^= *cl; *bl ^= *bh;
e_them_rndnbr = bx;
offsx = (*bl & 0x01) ? -0x02 : 0x02;
```

The author states this is "an exact copy of what the assembler code does but I can't
explain". `e_them_rndseed` is a `U32` incremented once per frame in `game_cycle`
(`game.c:484`, annotated `(0270)`); `e_them_rndnbr` is the module-private running value.

**This code is not portable and is very likely wrong as written.** `sh` is
`(U16*)&e_them_rndseed + 2`, which points **two `U16`s past** the start of a 4-byte
object — i.e. past the end of `e_them_rndseed` entirely — rather than to its high half.
✅ **Settled 2026-08-31 against the PC binary (T17): the intended expression is `+ 1`,
and the `+ 2` is a real bug.** The randomiser is a small subroutine at `0x024A` in
`kb/ibmpc_cs.bin`, immediately followed by the seed increment at `0x0270` — which is
exactly the address the port annotates as `(0270)` at `game.c:484`, confirming the
correspondence:

```
024A  53              PUSH BX
024B  51              PUSH CX
024C  8B 1E 48 7E     MOV  BX,[0x7E48]      ; e_them_rndnbr
0250  03 1E 4A 7E     ADD  BX,[0x7E4A]      ; + seed LOW word
0254  83 C3 0D        ADD  BX,0x0D          ; + 13
0257  8B 0E 4C 7E     MOV  CX,[0x7E4C]      ; seed HIGH word
025B  03 D9           ADD  BX,CX
025D  2A C0           SUB  AL,AL            ; al = 0
025F  32 C3           XOR  AL,BL
0261  32 C5           XOR  AL,CH
0263  32 C1           XOR  AL,CL
0265  32 C7           XOR  AL,BH
0267  8A D8           MOV  BL,AL
0269  89 1E 48 7E     MOV  [0x7E48],BX      ; e_them_rndnbr = bx
026F  C3              RET

0270  83 06 4A 7E 01  ADD  word [0x7E4A],1  ; 32-bit seed increment
0275  83 16 4C 7E 00  ADC  word [0x7E4C],0
```

The `ADD`/`ADC` pair proves `e_them_rndseed` is a **32-bit value held as two words**:
low at `0x7E4A`, high at `0x7E4C`. The randomiser reads **both** halves, so the high half
is one `U16` past the start — `(U16*)&e_them_rndseed + 1`. The port's `+ 2` lands four
bytes past a four-byte object and reads whatever follows it in memory. **Confirmed bug.**

**The XOR chain, by contrast, is transcribed correctly.** The PC folds through an `AL`
temporary — `al = 0; al ^= bl; al ^= ch; al ^= cl; al ^= bh; bl = al` — which is exactly
the port's three `*bl ^=` statements.

**And the "Black Magic" is no longer mysterious.** It is a plain mixing step: take the
running value, add both halves of the free-running frame-counter seed and the constant
13, then fold all four bytes of `BX`/`CX` down into the low byte by XOR. The caller tests
bit 0 to pick a direction. Nothing in it is unexplainable — the port author simply never
had the seed's layout, which is what makes the `sh` pointer wrong. It also assumes little-endian byte
order for `bl`/`bh`. Recorded in `divergences.md`; it means the port's enemy randomness
is *not* evidence about the original's.

### Type 3 — `e_them_t3_action2` (ASM 255A) — `e_them.c:568`

The scripted trap: sleeps until triggered, then plays a path from `ent_mvstep` with
frames from `ent_sprseq`. `c1 = sproffs`, `c2 = step_count`. Wrapped in `while (1)` so a
step boundary can be resolved without waiting a frame.

```
i = ent_sprseq[sprbase + sproffs] ; if (i == 0xff) i = ent_sprseq[sprbase]
sprite = i

if (sproffs != 0):                                      /* AWAKE */
    advance sproffs; wrap to 1 at the 0xff terminator
    if (step_count < ent_mvstep[step_no].count):
        step_count++
        x_new = x + mvstep[step_no].dx
        if (0 < x_new < 0xE8):
            x = x_new
            y_new = y + mvstep[step_no].dy
            if (0 < y_new < 0x140) { y = y_new; return }
    step_no++
    if (mvstep[step_no].count != 0xff): step_count = 0    /* next step, loop */
    else:
        if (!Rick ZOMBIE && !(flags & ENT_FLG_ONCE)):     /* restart the path */
            sproffs = 0 ; n &= ~ENT_LETHAL
            if (flags & ENT_FLG_LETHALR) n |= ENT_LETHAL
            x = xsave ; y = ysave
            if (y < 0 || y > 0x140) { n = 0; return }
        else: n = 0; return                               /* one-shot: gone */
else:                                                     /* ASLEEP */
    TRIGRICK   && u_trigbox(e, rick.x + 0x0C, rick.y + 0x0A)      -> wakeup
    TRIGSTOP   && Rick STOP && u_trigbox(e, stop_x, stop_y)       -> wakeup
    TRIGBULLET && bullet live && u_trigbox(e, bullet_xc, bullet_yc)
                                       -> bullet.n = 0,           -> wakeup
    TRIGBOMB   && e_bomb_lethal && u_trigbox(e, bomb_xc, bomb_yc) -> wakeup
    return                                                /* still asleep */
  wakeup:
    if (Rick ZOMBIE) return
    play WAV_ENTITY[(trigsnd & 0x1F) - 0x14]
    n &= ~ENT_LETHAL ; if (flags & ENT_FLG_LETHALI) n |= ENT_LETHAL
    sproffs = 1 ; step_count = 0 ; step_no = step_no_i
    return
```

Rick's trigger probe point is his centre-ish `(x + 0x0C, y + 0x0A)`.

**Wrapper** `e_them_t3_action` (ASM 2546, `e_them.c:718`): after the mover, if the entity
is lethal and Rick is not already a zombie and `e_rick_boxtest` hits, Rick dies. Note a
type-3 trap is **not** killable by bullets or bombs and does not participate in
`u_themtest` — it only ever kills.

## Bullet — `e_bullet.c`

```
e_bullet_init(x, y)        n = 0x02; ex = x; ey = y + 6
                           dir LEFT  -> offsx = -8, sprite = 0x21
                           dir RIGHT -> offsx = +8, sprite = 0x20 ; WAV_BULLET

e_bullet_action (1883/0F97)
                           ex += offsx
                           if (ex <= -0x10 || ex > 0xE8) n = 0
                           else:
                             xc = ex + 0x0C ; yc = ey + 0x05
                             if (eflg[map[yc>>3][xc>>3]] & SOLID) n = 0
```

8 px/frame. The wall test is a **single tile lookup at the bullet centre**, not the full
`u_envtest`. Only one bullet may exist at a time (checked in `e_rick_action2`).

## Bomb — `e_bomb.c`

`E_BOMB_TICKER = 0x2D` = 45 frames.

```
e_bomb_init(x, y)   n = 3; pos = Rick's; ticker = 0x2D; lethal = FALSE
                    GFXST: x += 4, y += 5   (ST sprite centring fixup)

e_bomb_action (18CA)
  ticker--
  ticker == 0     -> n = 0 ; lethal = FALSE
  ticker >= 0x0A  -> fuse:  every 4th frame ((ticker & 3) == 2) play WAV_BOMBSHHT
                     GFXST and ticker < 40 : sprite = 0x99 + 19 - (ticker >> 1)
                     else                  : sprite = (ticker & 1) ? 0x23 : 0x22
  ticker == 0x09  -> explode: WAV_EXPLODE
                     GFXST: undo the +4/+5 fixup ; sprite = 0xA8 + 4 - (ticker >> 1)
                     xc = x + 0x0C ; yc = y + 0x0A ; lethal = TRUE
                     if (e_bomb_hit(RICK)) e_rick_gozombie()
  else            -> exploding: sprite = 0xA8 + 4 - (ticker >> 1)
                     if (e_bomb_hit(RICK)) e_rick_gozombie()
```

The `ticker >= 0x0A` and `ticker == 0x09` branches are mutually exclusive in that order,
so the explosion frame is exactly `ticker == 9` and frames 8..1 are the blast.

`e_bomb_hit(e)` (ASM 11CD, `e_bomb.c:48`) — an asymmetric box around the bomb:

```c
if (ex        >  (bx >= 0xE0 ? 0xFF : bx + 0x20)) return FALSE;
if (ex + ew   <  (bx > 0x04  ? bx - 0x04 : 0))    return FALSE;
if (ey        >  by + 0x1D)                       return FALSE;
if (ey + eh   <  (by > 4 ? by - 4 : 0))           return FALSE;
return TRUE;
```

Blast extent: 0x20 right, 4 left, 0x1D down, 4 up — heavily biased right and down,
consistent with a sprite whose origin is its top-left.

## Boxes — `e_box.c` (ASM 245A)

Types `0x10` (bombs) and `0x11` (bullets).

```
if (n & ENT_LETHAL):                  /* exploding */
    sprite = sp[cnt >> 1]             /* sp[] = {0x24,0x25,0x26,0x27,0x28} */
    if (--cnt == 0) { n = 0; map_marks[mark].ent |= MAP_MARK_NACT }
else:
    e_rick_boxtest(e)                    -> WAV_BOX; refill (bombs or bullets) to 6;
                                            n = 0; mark inactive
    Rick STOP && u_fboxtest(stop)        -> explode()
    bullet live && u_fboxtest(bullet_xc,yc) -> bullet.n = 0; explode()
    e_bomb_lethal && e_bomb_hit(e)       -> explode()

explode(e): cnt = SEQ_INIT (0x0A); n |= ENT_LETHAL; WAV_EXPLODE
```

An exploding box is lethal, and being in slots 4..8 it is picked up by `u_themtest`, so
it kills nearby enemies. Collecting refills to `GAME_BOMBS_INIT`/`GAME_BULLETS_INIT` = 6.

## Bonus — `e_bonus.c` (ASM 242C)

Types `0x12`–`0x15`. `c1 = seq`.

```
seq == 0 && e_rick_boxtest(e):  env_score += 500 ; WAV_BONUS ; mark inactive
                                seq = 1 ; sprite = 0xAD ; front = TRUE ; y -= 8
0 < seq < 10:                   seq++ ; y -= 2        /* the "500" floats up */
else:                           n = 0
```

## Super bonus — `e_sbonus.c`

A pair of trigger volumes, types `0x16` (start) and `0x17` (stop), both invisible
(`sprite = 0`).

```
e_sbonus_start (2182): if (u_trigbox(e, rick.x + 0x0C, rick.y + 0x0A)):
                           n = 0 ; counting = TRUE ; counter = 0x1E ; bonus = 2000
                           WAV_SBONUS1
e_sbonus_stop  (2143): if (!counting) return
                       if (u_trigbox(e, rick.x + 0x0C, rick.y + 0x0A)):
                           counting = FALSE ; n = 0 ; env_score += bonus
                           WAV_SBONUS2 ; mark inactive
                       else if (--counter == 0) { counter = 0x1E; if (bonus) bonus-- }
```

The timer decrements the bonus by 1 every 30 frames. `e_sbonus_counting` is also cleared
by `map_chain` (`maps.c:163`, flagged "FIXME what? move this out of here!!").

## Painting — `ents_paintAll` — `ents.c:341`

Three passes over the slot array, then dirty-rectangle bookkeeping:

1. **erase**: for every slot whose `prev_n` was set and which was visible last frame,
   `maps_paintRect(prev_x, prev_y, 0x20, 0x15)` — repaint the map behind it.
2. **draw**: for every live slot with a non-zero sprite (or `env_highlight`),
   `sprites_paint2(sprite, x, y, front)`.
3. **rects**: for each slot, add one rectangle covering both old and new positions if
   they overlap (`dx < 0x20 && dy < 0x16`), otherwise two; then save
   `prev_x/y/n/s`.

`ent_addrect` (`ents.c:293`) aligns to the tile grid, clips to the visible map with
`maps_clip`, adds the `GFXST` `+8`, converts to fb coordinates, and prepends to
`ent_rects`.
