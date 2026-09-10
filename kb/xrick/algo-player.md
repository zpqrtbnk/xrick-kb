# Rick — `e_rick.c`, `util.c`

All line references are `xrick/src/e_rick.c` unless noted. Original-routine
cross-references in `ASM ...` are the port author's PC-side annotations.

## State

Module-private (`e_rick.c:41-52`): `scrawl` (last frame's crawl flag), `trigger` (fire
edge-detect), `offsx` (S8, zombie x drift), `ylow` (U8, fractional y), `offsy` (S16, y
velocity in 8.8 fixed point), `seq` (animation/step counter), `save_crawl`/`save_x`/
`save_y` (checkpoint).

Public: `e_rick_state` (bitfield, see `data-model.md`), `e_rick_atExit`,
`e_rick_stop_x`, `e_rick_stop_y`.

Rick's position lives in `ent_ents[1]`. `offsy` and `ylow` form a 24-bit accumulator:

```c
i = (y << 8) + offsy + ylow;   /* U32 */
y_new = i >> 8;
ylow  = (U8)i;
```

Gravity is `offsy += 0x0080` per frame, clamped to `0x0800`. Terminal velocity is
therefore 8 px/frame; one gravity step is 0.5 px/frame².

## `e_rick_action` (ASM 12CA) — `e_rick.c:448`

Wrapper. Calls `e_rick_action2()` to move, then picks the sprite:

```
scrawl = STCRAWL                      /* remembered for next frame's stand-up test */
if ZOMBIE            -> return (sprite already set by e_rick_z_action)
if STOP              -> sprite = dir ? 0x17 : 0x0B ; play WAV_STICK once per stop
if SHOOT             -> sprite = dir ? 0x16 : 0x0A
if CLIMB             -> sprite = ((x ^ y) & 4) ? 0x18 : 0x0C ; WAV_WALK every 4th frame
if CRAWL             -> sprite = (dir ? 0x13 : 0x07) + ((x & 4) ? 1 : 0)
                        WAV_WALK... (WAV_CRAWL) every 4th frame
if JUMP              -> sprite = dir ? 0x15 : 0x06
else                 -> seq++; if (seq >= 0x14) { WAV_WALK; seq = 4 }
                        else if (seq == 0x0C) WAV_WALK
                        sprite = (seq >> 2) + 1 + (dir ? 0x0C : 0)
```

`game_dir` is `LEFT = 1`, `RIGHT = 0` (`game.h:780-781`). The walk cycle is four frames
per sprite (`seq >> 2`), sprites 1–4 facing right and 0x0D–0x10 facing left, with the
footstep sound at `seq` 0x0C and on wrap.

## `e_rick_action2` (ASM 13BE) — `e_rick.c:143`

The mover. Structure, in source order:

```
STRST(STSTOP | STSHOOT)
if ZOMBIE     -> e_rick_z_action(); return
if CLIMB      -> goto climbing

/* NOT CLIMBING */
STRST(STJUMP)
i = (y << 8) + offsy + ylow ;  y = i >> 8
u_envtest(x, y, STCRAWL, &env0, &env1)
if (STCRAWL && !env0) STRST(STCRAWL)                 /* stand up when there is room */

blocked = offsy < 0 ? (VERT|SOLID|SPAD)              /* going up: WAYUP passes */
                    : (VERT|SOLID|SPAD|WAYUP)        /* going down: WAYUP blocks */
if (env1 & blocked) goto vert_not

/* VERTICAL MOVE */
STSET(STJUMP)
if (env1 & LETHAL) { gozombie(); return }
y, ylow = saved
if ((env1 & CLIMB) && (UP|DOWN)) { offsy = 0x0100; STSET(STCLIMB); return }
offsy += 0x0080 ; clamp to 0x0800 (and ylow = 0 when clamping)
/* falls through to horiz */
```

**`horiz:`** (`e_rick.c:208`)

```
if !(LEFT|RIGHT) { seq = 2; return }
LEFT :  x = ex - 2 ; game_dir = LEFT  ; if (x < 0)     { atExit = TRUE; ex = 0xE2; return }
RIGHT:  x = ex + 2 ; game_dir = RIGHT ; if (x >= 0xE8) { atExit = TRUE; ex = 0x04; return }
u_envtest(x, y, STCRAWL, ...)
if !(env1 & (SOLID|SPAD|WAYUP)) { ex = x; if (env1 & LETHAL) gozombie() }
return
```

Horizontal speed is 2 px/frame. Note `x` is `U16`, so `x < 0` after `- 2` is never true
in C — see `divergences.md`.

**`vert_not:`** (`e_rick.c:247`)

```
if (offsy < 0) {                 /* hit the ceiling */
    STSET(STJUMP); y &= 0xF8; offsy = 0; ylow = 0; goto horiz
}
/* landing */
y = (y & 0xF8) | 0x03 ; ylow = 0            /* align: ground rows are y = 8k+3 */

if ((env1 & SPAD) && offsy >= 0x0200) {     /* super pad */
    offsy = (UP) ? 0xF800 : 0x00FE - offsy  /* held UP: fixed big bounce            */
    WAV_PAD                                 /* else: rebound proportional to impact */
    goto horiz
}
offsy = 0x0100                              /* standing */

if (scrawl || !FIRE) goto firing_not
```

The super-pad rebound `0x00FE - offsy` is a negated impact speed: land at `offsy` and
leave at roughly `-offsy`. With UP held it is a constant `-0x0800`.

**`FIRING`** (`e_rick.c:280`)

```
if (LEFT|RIGHT):                 /* stick out */
    RIGHT -> dir = RIGHT, stop_x = x + 0x17
    LEFT  -> dir = LEFT , stop_x = x
    stop_y = y + 0x0E ; STSET(STSTOP) ; return

if (control_status == FIRE|UP):  /* bullet */
    STSET(STSHOOT)
    if (trigger) return          /* single shot per press */
    trigger = TRUE
    if (bullet already live) return
    if (!env_bullets) return
    if (!env_trainer) env_bullets--
    e_bullet_init(x, y) ; return

trigger = FALSE ; seq = 0

if (control_status == FIRE|DOWN): /* bomb */
    if (bomb already ticking) return
    if (!env_bombs) return
    if (!env_trainer) env_bombs--
    e_bomb_init(x, y) ; return
return
```

Note the equality tests `control_status == (FIRE|UP)` — pressing any other direction at
the same time suppresses the shot.

**`firing_not:`** (`e_rick.c:338`)

```
if (UP):
    if (env1 & CLIMB) { STSET(STCLIMB); return }
    offsy = -0x0580 ; ylow = 0 ; WAV_JUMP ; goto horiz     /* jump */
if (DOWN):
    if ((env1 & VERT) && !(LEFT|RIGHT) && (x & 0x1f) < 0x0a) {
        x = (x & 0xF0) | 0x04 ; STSET(STCLIMB)             /* climb down a ladder  */
    } else {
        STSET(STCRAWL) ; goto horiz                        /* crawl                */
    }
goto horiz
```

Jump impulse is `-0x0580` = 5.5 px/frame upward.

**`climbing:`** (`e_rick.c:370`)

```
if !(UP|DOWN|LEFT|RIGHT) { seq = 0; return }

if (UP|DOWN):
    y = ey + (UP ? -2 : +2)
    u_envtest(x, y, STCRAWL, ...)
    if ((env1 & (SOLID|SPAD|WAYUP)) && !UP) { STRST(STCLIMB); return }
    if (!(env1 & (SOLID|SPAD|WAYUP)) || (env1 & WAYUP)) {
        ey = y
        if (env1 & LETHAL) { gozombie(); return }
        if (!(env1 & (VERT|CLIMB))) {            /* left the ladder */
            offsy = UP ? -0x0300 : 0x0100
            if (UP) WAV_JUMP
            STRST(STCLIMB) ; return
        }
    }

if (LEFT|RIGHT):
    x = ex -/+ 2, with the same submap-exit tests as horiz
    u_envtest(x, ey, STCRAWL, ...)
    if (env1 & (SOLID|SPAD)) return
    ex = x
    if (env1 & LETHAL) { gozombie(); return }
    if (env1 & (VERT|CLIMB)) return
    STRST(STCLIMB)
    if (UP) offsy = -0x0300
```

Climb speed is 2 px/frame in both axes. Leaving the top of a ladder while holding UP
gives a small hop (`-0x0300`).

## Death — `e_rick_gozombie` (ASM 1851) and `e_rick_z_action` (ASM 17DC)

```
gozombie:   if (env_invicible) return
            if (already ZOMBIE) return
            WAV_DIE ; STSET(STZOMBIE)
            offsy = -0x0400 ; offsx = (x > 0x80 ? -3 : +3) ; ylow = 0 ; front = TRUE

z_action:   sprite = (x & 4) ? 0x1A : 0x19
            x += offsx
            i = (y << 8) + offsy + ylow ; y = i >> 8 ; offsy += 0x80 ; ylow = i
            if (y < 0 || y > 0x0140) STSET(STDEAD)
```

The corpse is launched up and away from the nearer screen edge, falls under gravity, and
the *frame after* it leaves the map, `STDEAD` is set — which `game_cycle` picks up in
`CTRL_RICK` and turns into `RESTART` or game over.

## Checkpoint — `e_rick_save` / `e_rick_restore` (ASM parts of 0x0BBB / 0x0BDC)

Saves and restores `x`, `y` and the crawl flag only; `front` is forced to `FALSE` on
restore. Both carry a `FIXME` noting that `b0C` and "some 6DBC stuff" are not saved.
`game_save()` (`game.c:838`) pairs this with `save_map_row = map_frow`.

## Collision helpers — `util.c`

### `e_rick_boxtest(e)` (ASM 113E, specialised) — `e_rick.c:65`

Rick's box is `x+0x05 .. x+0x11` horizontally and `y+[0x08 if crawling] .. y+0x14`
vertically; the other entity's is `x .. x+w`, `y .. y+h-1`.

```c
if (rx + 0x11 < ex || rx + 0x05 > ex + ew ||
    ry + 0x14 < ey || ry + (crawl ? 0x08 : 0x00) > ey + eh - 1) return FALSE;
return TRUE;
```

### `u_boxtest(e1, e2)` (ASM 113E) — `util.c:61`

Same shape, with `e1` in Rick's role; delegates to `e_rick_boxtest` when `e1 == 1`. Note
the lower edge differs slightly: `ent_ents[e1].y > ey + eh - 1` (no crawl offset).

### `u_fboxtest(e, x, y)` (ASM 1199) — `util.c:37`

Point-in-box, **strict on the low edge**: true iff `ex < x <= ex + ew` and
`ey < y <= ey + eh`.

### `u_trigbox(e, x, y)` (ASM 126F) — `util.c:192`

Point in the entity's trigger box, sized from `entdata[n & 0x7F].trig_w/h` in tiles:

```c
xmax = trig_x + (trig_w << 3);  if (xmax > 0xFF) xmax = 0xFF;
ymax = trig_y + (trig_h << 3);
return !(x <= trig_x || x > xmax || y <= trig_y || y > ymax);
```

### `u_envtest(x, y, crawl, *rc0, *rc1)` (ASM 0FBC / 103E) — `util.c:92`

**The single most important routine in the port** — the tile probe that every mover
consults. It ORs the attribute bytes of a small set of tiles around the candidate
position, returning two masks: `rc1` (the movement/hazard flags, PC address `6DAD`) and
`rc0` (the crawl-clearance flags, `6DBA`).

```
ent_ents[12].x = x ; ent_ents[12].y = y        /* scratch entity for the slot-0 test */

i = 1 ; if (!crawl) i++ ; if (y & 0x0004) i++  /* 1..3 middle row-pairs */
x += 4 ; xx = (U8)x
x >>= 3 ; y >>= 3                              /* to tiles */
rc0 = rc1 = 0
```

Two branches, on whether the position straddles a tile column (`xx & 0x07`):

**Straddling — three columns per row** (`util.c:112-142`)

```
if crawl:  rc0 |= eflg[map[y][x+0..2]] & (VERT|SOLID|SPAD|WAYUP) ; y++
repeat i times:
    rc1 |= eflg[map[y][x  ]] & (SOLID|SPAD|FGND|LETHAL|01)
    rc1 |= eflg[map[y][x+1]] & (SOLID|SPAD|FGND|LETHAL|CLIMB|01)   /* CLIMB centre only */
    rc1 |= eflg[map[y][x+2]] & (SOLID|SPAD|FGND|LETHAL|01)
    y++
/* final (foot) row: WAYUP joins the mask, and the centre column is taken whole */
rc1 |= eflg[map[y][x  ]] & (SOLID|SPAD|WAYUP|FGND|LETHAL|01)
rc1 |= eflg[map[y][x+1]]                                            /* everything */
rc1 |= eflg[map[y][x+2]] & (SOLID|SPAD|WAYUP|FGND|LETHAL|01)
```

**Aligned — two columns per row** (`util.c:143-163`)

```
if crawl:  rc0 |= eflg[map[y][x+0..1]] & (VERT|SOLID|SPAD|WAYUP) ; y++
repeat i times:
    rc1 |= eflg[map[y][x  ]] & (SOLID|SPAD|FGND|LETHAL|CLIMB|01)
    rc1 |= eflg[map[y][x+1]] & (SOLID|SPAD|FGND|LETHAL|CLIMB|01)
    y++
rc1 |= eflg[map[y][x  ]]                                            /* everything */
rc1 |= eflg[map[y][x+1]]                                            /* everything */
```

The asymmetry is deliberate and behaviourally significant: **`VERT` (ladder top) and
`WAYUP` are only picked up from the foot row**, and in the straddling case `CLIMB` is
only seen in the centre column above the feet. This is the mechanism that lets Rick walk
over a ladder top but grab it when standing on it.

Two post-conditions (`util.c:174-181`):

```c
if (!(rc1 & LETHAL) && ent_ents[0].n && u_boxtest(12, 0)) rc1 |= SOLID;
if (env_invicible) rc1 &= ~LETHAL;
```

The first is how the slot-0 entity becomes an impassable moving obstacle; the comment
warns that with invincibility on, a block can move over Rick and trap him.
