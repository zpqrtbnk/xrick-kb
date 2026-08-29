# Rick Dangerous — Player Subsystem: Exact Algorithms

Transcription of every function in `0x4C046`–`0x4D058` to re-codable pseudocode.
Source of truth is the **disassembly** (`disassemble_function`), not the decompiler.
Ghidra plate comments at each address hold the raw evidence trail.

**Scope:** the player controller, death handling, sprite/animation selection, the two
player projectiles, and the player-side collision probes.

---

## 0. Shared state

### The player *is* `sprite_list[1]`, addressed absolutely

All player code uses hard-coded absolute addresses rather than an `A0` base pointer.
`sprite_list` = `0x4A702`, stride `0x4C`, so `sprite_list[1]` = `0x4A74E`:

| Address | Field | Player meaning |
|---|---|---|
| `0x4A74E` | `wType` | 1 |
| `0x4A750` | `nDirection` | facing: **0 = right, 0xFF = left**. During death: X drift `±3` |
| `0x4A752` | `nPosX` | X (byte `0x4A753` = low) |
| `0x4A754` | `nPosY` | Y (byte `0x4A755` = low — used for tile snapping) |
| `0x4A756` | `nVelY` | vertical velocity, 8.8 fixed |
| `0x4A758` | `nPosYFrac` | fractional Y |
| `0x4A75A` | `nSpawnX` | **reused as "X before this frame's move"** (undo scratch) |
| `0x4A770` | `gfx_data` | current sprite frame pointer |
| `0x4A778` | `nAnimFrameIdx` | animation counter |

Other slots used by this subsystem:

| Slot | Base | Fields referenced |
|---|---|---|
| `[0]` block | `0x4A702` | `wType` `0x4A702`, `nPosX` `0x4A706`, `nPosY` `0x4A708`, `nHitboxW` `0x4A712`, `nHitboxH` `0x4A714` |
| `[2]` bullet | `0x4A79A` | `wType` `0x4A79A`, `nDirection` `0x4A79C`, `nPosX` `0x4A79E`, `nPosY` `0x4A7A0`, `bRender_flags_a` `0x4A7B0`, `bRender_flags_b` `0x4A7B6`, `gfx_data` `0x4A7BC` |
| `[3]` dynamite | `0x4A7E6` | `wType` `0x4A7E6`, `nPosX` `0x4A7EA`, `nPosY` `0x4A7EC`, `nRow_count` `0x4A7FA`, `bRender_flags_a` `0x4A7FC`, `bRender_flags_b` `0x4A802`, `gfx_data` `0x4A808`, `nAnimFrameIdx` `0x4A810` |

### Player state globals

| Address | Name | Meaning |
|---|---|---|
| `0x4922B` | `joystick` | **Atari IKBD joystick-1 state byte** (see §0.1) |
| `0x4BF12` | `climbing` | 0xFF while on a ladder |
| `0x4BF13` | `on_ground` | 0xFF if standing on a floor this frame |
| `0x4BF14` | `crouching` | 0xFF while crouched/crawling |
| `0x4BF15` | `shoot_debounce` | 0xFF once a bullet has been fired; cleared when UP+FIRE released |
| `0x4BF16` | `collision_mask` | AND-mask applied to tile attributes; reset to 0xFF each frame |
| `0x4BF17` | `moved_flags` | bit0 = X moved, bit1 = Y moved (climb mode); 0xFF = walking (normal mode) |
| `0x4BF18` | `player_dying` | 0xFF during the death sequence |
| `0x4BF1A` | `dynamite_exploding` | 0 = fuse phase, 0xFF = explosion phase |
| `0x4BF1C` | `stick_debounce` | one-shot latch for the stick jab sound |
| `0x4BF1E` | `stick_attack_active` | 0xFF while the jab hitbox is live |
| `0x4BF20` / `0x4BF22` | `stick_point_x/y` | the jab's single test point |
| `0x4BF24` / `0x4BF26` | `bullet_point_x/y` | the bullet's leading-edge test point |
| `0x4BF28` | `explosion_active` | 0xFF while the blast is lethal |
| `0x4BF2A` / `0x4BF2C` | `explosion_x/y` | blast centre |
| `0x4BF2E` | `player_touched_hazard` | set by anything lethal; polled at the top of `player_controller` |
| `0x4D00A` | `player_collision_flags` | masked tile attributes from the last probe |
| `0x4D00B` | `ceiling_flag` | head-level solid bit, captured separately while crouching |

### 0.1 Input bit mapping — **CONFIRMED**

`0x4922B` is written by `keyboard_isr` from the byte following an **`0xFF` IKBD
joystick report header** (`0x4922A` holds the `0xFE` / joystick-0 equivalent). It is
therefore the standard Atari ST joystick encoding, and every use in
`player_controller` agrees:

| Bit | Mask | Meaning | Evidence |
|---|---|---|---|
| 0 | `0x01` | **UP** | jump (`nVelY = -0x580`), climb up, shoot with FIRE |
| 1 | `0x02` | **DOWN** | crouch, climb down, dynamite with FIRE |
| 2 | `0x04` | **LEFT** | `nPosX -= 2`, `nDirection = 0xFF` |
| 3 | `0x08` | **RIGHT** | `nPosX += 2`, `nDirection = 0` |
| 7 | `0x80` | **FIRE** | modifier: FIRE+dir selects an attack instead of moving |

Control scheme: FIRE+LEFT/RIGHT = stick jab, FIRE+UP = shoot, FIRE+DOWN = dynamite.

### 0.2 Tile-attribute bits (via `tile_attr_table_ptr`, `*0x495D4`)

| Bit | Mask | Meaning | Confidence |
|---|---|---|---|
| 1 | `0x02` | ladder / climbable | confirmed (gates climb entry & exit) |
| 2 | `0x04` | **lethal** — `player_sprite_update` kills on this | confirmed |
| 4 | `0x10` | one-way; cleared from `collision_mask` while moving up | confirmed |
| 5 | `0x20` | landable floor | confirmed (gates the landing branch) |
| 6 | `0x40` | solid wall | confirmed |
| 7 | `0x80` | ladder top / one-way; also cleared while moving up | confirmed |

"Blocked" is `(flags & 0xD0) != 0` — bits 7, 6, 4.

### 0.3 Sound track IDs used here

`0x08` bullet fire · `0x09` empty-click *and* dynamite fuse tick · `0x0A` explosion ·
`0x0B` stick jab · `0x0C` footstep/climb · `0x0D` crawl · `0x0E` jump / ladder-exit ·
`0x0F` landing · `0x13` player death.

### 0.4 Control-flow shape (important for reimplementation)

`player_controller` pushes `{D0–D7, A0}` on entry. It **never returns directly** —
every path ends in a `bra` to `player_sprite_update` (`0x4C8B2`) or
`player_select_anim_frame` (`0x4C8C2`), and the single `movem.l (SP)+` + `rts` lives
at `0x4CA54` inside `player_select_anim_frame`. `player_death_physics` also falls
through into it.

**So `player_sprite_update` and `player_select_anim_frame` are continuations sharing
`player_controller`'s stack frame, not free-standing subroutines.** In C, make them
plain functions called at the end of the controller.

---

## 1. `player_controller` — `0x4C046`

`player_controller(void) -> void` — dispatch type 1. Ignores `A0`.

```c
push {D0-D7, A0};

// --- 1. dynamite/explosion state follows the dynamite entity -----------
if (sprite_list[3].wType == 0) {          // 0x4A7E6
    dynamite_exploding = 0;               // word clear 0x4BF1A
    explosion_active   = 0;               // word clear 0x4BF28
}

// --- 2. already dead? -> physics only ---------------------------------
if (player_dying != 0) goto player_death_physics;          // 0x4C846

// --- 3. something lethal touched us last frame ------------------------
if (player_touched_hazard != 0) {         // word test 0x4BF2E
    kill_player();
    goto death_anim_frame;                // 0x4C8CA
}

// --- 4. per-frame reset ------------------------------------------------
on_ground           = 0;
collision_mask      = 0xFF;
moved_flags         = 0;
stick_attack_active = 0;                  // word

D0 = joystick;                            // byte @0x4922B

// shoot debounce clears unless BOTH up(0x01) and fire(0x80) are still held
if ((D0 & 0x81) != 0x81) shoot_debounce = 0;

if (climbing != 0) goto CLIMB_MODE;       // 0x4C67C
```

### 1a. Normal (walk / fall) model — `0x4C0B6`

```c
// 16.16 Y accumulator = posY:posYFrac ; velocity is 8.8 so shift left 8
D1 = (nPosY << 16) | nPosYFrac;
D3 = (int32)(int16)nVelY;
if ((int16)nVelY < 0) {                   // moving up: pass through one-way tiles
    collision_mask &= ~0x10;              // bclr #4
    collision_mask &= ~0x80;              // bclr #7
}
D3 = (D3 << 8) + D1;                      // integrate
D2 = nPosX;
nSpawnX = D2;                             // remember pre-move X (undo scratch)
D3 = swap(D3);                            // low word = new integer Y

// horizontal input
if (D0 & 0x04) { D2 -= 2; moved_flags = 0xFF; nDirection = 0xFF; }   // LEFT
else if (D0 & 0x08) { D2 += 2; moved_flags = 0xFF; nDirection = 0; } // RIGHT

// try the full move
D6 = D2; D7 = (int16)D3;
if (!probe_player_tile_collision()) {     // carry clear = free
    nPosX     = D2;
    nPosY     = (int16)D3;
    nPosYFrac = (int16)(swap(D3));
    nVelY += 0x80;                        // gravity
    if ((int16)nVelY > 0x800) nVelY = 0x800;   // terminal velocity
    goto LADDER_CHECK;                    // 0x4C2FE
}

// --- blocked: try vertical-only ---------------------------------------  0x4C168
D6 = nPosX;                               // old X
if (D2 != D6) {
    // D7 still holds the new Y
    if (!probe_player_tile_collision()) {
        nPosY     = (int16)D3;
        nPosYFrac = (int16)(swap(D3));
        moved_flags = 0;                  // horizontal rejected -> not "walking"
        nVelY += 0x80;
        if ((int16)nVelY > 0x800) nVelY = 0x800;
        goto LADDER_CHECK;
    }
}

// --- vertical blocked too ---------------------------------------------  0x4C1AC
if ((int16)nVelY < 0) {                   // was moving up -> bonk head    0x4C238
    nPosYFrac = 0;
    nVelY     = 0x80;                     // start falling
    goto POST_MOVE;                       // 0x4C2EA
}

if (player_collision_flags & 0x20) {      // bit5: landable floor          0x4C1B8
    if (nVelY == 0x100) {                 // already at rest
        on_ground = 0xFF;
        goto POST_MOVE;
    }
    nVelY = 0xFE - nVelY;                 // landing rebound (see notes)
    nPosY = (nPosY & ~7) | 3;             // snap Y to tile grid + 3  [byte @0x4A755]
    nPosYFrac = 0;
    play_music(D0=0x0F, D1=1);            // landing thud
    if (D0 & 0x80) goto POST_MOVE;        // FIRE held -> no super-bounce
    if (!(D0 & 0x01)) goto POST_MOVE;     // UP not held -> no super-bounce
    nVelY = -0x800;
    goto POST_MOVE;
}

// --- not a floor: maybe a ladder we can grab downward ------------------  0x4C24A
if ((player_collision_flags & 0x80) &&    // bit7: ladder top
    (D0 & 0x02) &&                        // DOWN
    !(D0 & 0x80) &&                       // FIRE not held
    !(D0 & 0x0C))                         // no LEFT/RIGHT
{
    D4 = nPosX;
    if (D4 & 0x08) {
        if ((D4 & 0x07) != 0) goto NO_LADDER;
        D4 = nPosX;
    }
    nPosX     = (D4 & ~0x0F) | 4;         // centre on the ladder  [byte-wise: &0xF0|4]
    nPosY     = (nPosY & ~7) | 5;
    nPosYFrac = 0;
    climbing  = 0xFF;
    crouching = 0;
    nAnimFrameIdx = 0;
    goto player_sprite_update;
}

NO_LADDER:                                //                                0x4C2C0
    nPosY     = (nPosY & ~7) | 3;
    nPosYFrac = 0;
    on_ground = 0xFF;
    nVelY     = 0x100;

POST_MOVE:                                //                                0x4C2EA
    D6 = D2; D7 = nPosY;
    if (!probe_player_tile_collision()) nPosX = D2;   // retry X at snapped Y
```

### 1b. Ladder / action dispatch — `0x4C2FE`

```c
LADDER_CHECK:
if (player_collision_flags & 0x02) {          // bit1: ladder here
    if ((D0 & 0x80) && on_ground) goto ACTION;          // 0x4C38C
    if (crouching) goto NO_CLIMB;                       // 0x4C370
    if (D0 & 0x01) goto START_CLIMB;                    // UP
    if (D0 & 0x02) {                                    // DOWN
        if (on_ground) {                                // 0x4C35E
            crouching = 0xFF; nAnimFrameIdx = 0;
            goto player_sprite_update;
        }
        goto START_CLIMB;
    }
    climbing = 0;
    goto player_sprite_update;

START_CLIMB:                                            // 0x4C33E
    climbing  = 0xFF;
    nVelY     = 0x100;
    nPosYFrac = 0;
    nAnimFrameIdx = 0;
    goto player_sprite_update;
}

NO_CLIMB:                                               // 0x4C370
if (on_ground) goto ACTION;
if (ceiling_flag != 0) goto player_sprite_update;       // still stuck under something
crouching = 0;
goto player_sprite_update;
```

### 1c. Action branch — `0x4C38C`

```c
ACTION:
if (!(D0 & 0x80)) {                        // ---- FIRE NOT held: move/jump
    stick_debounce = 0;
    D4 = ((D0 & 0x02) | ceiling_flag) ? 0xFF : 0;       // sne
    if (D4 != crouching) { crouching = D4; nAnimFrameIdx = 0; }
    if (crouching) { on_ground = 0; goto player_sprite_update; }
    if (!(D0 & 0x01)) goto player_sprite_update;
    nVelY = -0x580;                        // JUMP
    play_music(D0=0x0E, D1=1);
    goto player_sprite_update;
}

// ---- FIRE held ------------------------------------------------------- 0x4C3F4
if (crouching && ceiling_flag) goto player_sprite_update;

if (D0 & 0x04) {                           // FIRE+LEFT: stick jab left    0x4C406
    stick_attack_active = 0xFF;
    nDirection = 0xFF;
    nPosX = nSpawnX;                       // cancel this frame's walk
    crouching = 0;
    stick_point_y = nPosY + 0x0E;
    stick_point_x = nPosX + 0x00;
    if (stick_debounce != 0) goto player_sprite_update;
    stick_debounce = 0xFF;
    play_music(D0=0x0B, D1=1);
    goto player_sprite_update;
}
if (D0 & 0x08) {                           // FIRE+RIGHT: stick jab right  0x4C460
    stick_attack_active = 0xFF;
    nDirection = 0;
    nPosX = nSpawnX;
    crouching = 0;
    stick_point_y = nPosY + 0x0E;
    stick_point_x = nPosX + 0x17;
    if (stick_debounce != 0) goto player_sprite_update;
    stick_debounce = 0xFF;
    play_music(D0=0x0B, D1=1);
    goto player_sprite_update;
}

stick_debounce = 0;                        //                              0x4C4CE

if (D0 & 0x01) {                           // FIRE+UP: shoot               0x4C4D4
    if (shoot_debounce) goto player_sprite_update;
    shoot_debounce = 0xFF;
    D4 = nSpawnX;  nPosX = D4;             // cancel walk
    crouching = 0;
    if (nDirection != 0) { if (D4 <= 0x08) goto player_sprite_update; }  // too near left edge
    else                 { if (D4 >= 0xE0) goto player_sprite_update; }  // too near right edge
    if (sprite_list[2].wType != 0) goto player_sprite_update;            // bullet already live
    if (HudCounters.bBullets == 0) {
        play_music(D0=0x09, D1=1);          // empty click
        goto player_sprite_update;
    }
    HudCounters.bBullets -= 1;
    HudDirtyFlags.bBullets_dirty = 0xFF;
    sprite_list[2].wType = 2;
    play_music(D0=0x08, D1=1);
    play_music(D0=0x08, D1=0);
    sprite_list[2].bRender_flags_a &= ~0x01;
    sprite_list[2].bRender_flags_b &= ~0x01;
    sprite_list[2].nDirection = nDirection;
    D4 = nPosY + 7;   sprite_list[2].nPosY = D4;
    D4 += 4;          bullet_point_y = D4;              // = nPosY + 11
    D4 = nPosX;
    if (sprite_list[2].nDirection != 0) {               // facing left
        D4 -= 1;
        sprite_list[2].nPosX = D4;
        bullet_point_x = D4;
        sprite_list[2].gfx_data = 0x0002E9EE;
    } else {                                            // facing right
        D4 += 1;
        sprite_list[2].nPosX = D4;
        D4 += 0x17;
        bullet_point_x = D4;                            // = nPosX + 0x18
        sprite_list[2].gfx_data = 0x0002E89E;
    }
    goto player_sprite_update;
}

if (D0 & 0x02) {                           // FIRE+DOWN: dynamite          0x4C5FC
    if (sprite_list[3].wType != 0) goto player_sprite_update;
    if (HudCounters.bDynamite == 0) goto player_sprite_update;
    HudCounters.bDynamite -= 1;
    HudDirtyFlags.bDynamite_dirty = 0xFF;
    sprite_list[3].wType = 3;
    sprite_list[3].bRender_flags_a &= ~0x01;
    sprite_list[3].bRender_flags_b &= ~0x01;
    sprite_list[3].nRow_count = 0x10;
    D4 = nPosX + 4;  if (D4 > 0xE8) D4 = 0xE8;
    sprite_list[3].nPosX = D4;
    D4 = nPosY + 5;  sprite_list[3].nPosY = D4;
    sprite_list[3].nAnimFrameIdx = 0;
}
goto player_sprite_update;
```

### 1d. Climb mode — `0x4C67C`

```c
CLIMB_MODE:
D2 = nPosX; D3 = nPosY;
D6 = D2;    D7 = D3;
nVelY = 0x100;
collision_mask &= ~0x80;                   // bclr #7

if (D0 & 0x04) { D2 -= 2; nDirection = 0xFF; moved_flags |= 0x01; }  // LEFT
else if (D0 & 0x08) { D2 += 2; nDirection = 0; moved_flags |= 0x01; }// RIGHT

if (D0 & 0x01) {                           // UP
    D3 -= 2;
    nVelY = -0x200;
    collision_mask &= ~0x10;
    moved_flags |= 0x02;
} else if (D0 & 0x02) {                    // DOWN
    D3 += 2;
    moved_flags |= 0x02;
}

if (moved_flags & 0x01) {                  //                              0x4C706
    D6 = D2;                               // D7 still = old Y
    if (probe_player_tile_collision()) {   // blocked
        if (player_collision_flags & 0x40) moved_flags &= ~0x01;  // solid: cancel
        else nPosX = D2;
    } else nPosX = D2;
}

if (moved_flags & 0x02) {                  //                              0x4C732
    D6 = nPosX; D7 = D3;
    if (!probe_player_tile_collision()) goto COMMIT_Y;
}

if (D0 & 0x02) {                           // DOWN and blocked             0x4C74A
    if (player_collision_flags & 0x80) goto COMMIT_Y;   // ladder continues
    // stepping off the bottom of the ladder
    nVelY = 0x100;
    climbing = 0;
    moved_flags = 0;
    nAnimFrameIdx = 0;
    nPosYFrac = 0;
    goto player_sprite_update;
}

nVelY = 0x100;                             //                              0x4C77E
moved_flags &= ~0x02;
if (!(moved_flags & 0x01)) goto player_sprite_update;
goto LEAVE_LADDER_CHECK;

COMMIT_Y:                                  //                              0x4C79C
nPosY = D3;

LEAVE_LADDER_CHECK:                        //                              0x4C7A2
if (player_collision_flags & 0x02) goto player_sprite_update;  // still on ladder
climbing = 0;
nAnimFrameIdx = 0;
nPosYFrac = 0;
if (nVelY != 0x100) play_music(D0=0x0E, D1=1);
goto player_sprite_update;
```

**Notes / uncertainties**
- ✅ **Resolved 2026-08-29.** `nVelY = 0xFE - nVelY` is **not the normal landing
  path**. It is gated on `player_collision_flags & 0x20`, and bit `0x20` is carried by
  only 4 tiles in the entire game (bank 0: 190/191/192; bank 1: 216 — always `0x60`,
  solid+bounce), used in just 5 rooms (13, 19, 23, 36, 37). Ordinary solid ground is
  plain `0x40` and leaves at `4C1C0` for `0x4C24A`.
  So the "surprising" large rebound is exactly right: these are **bounce surfaces**,
  and the rebound scales with impact speed. Gravity is `+0x80`/frame clamped to a
  terminal `0x800`, so the strongest bounce is `0xFE - 0x800 = -0x702`. The
  `nVelY == 0x100` early-out is the only way to come to rest on such a tile.
  Confirmed dynamically: with `0x4C1DE` breakpointed, repeated falls reaching `nVelY`
  of `0x08xx`–`0x0Cxx` never once reached the site. *(Visual confirmation of what the
  tiles look like in play is still open — see rooms 13/19.)*
- The ladder-grab X test (`btst #3` then `& 7`) accepts X values where
  `(X & 8) == 0`, or `(X & 0x0F) == 8`. Effectively "close enough to a 16px column".
- `nSpawnX` (`0x4A75A`) is *not* used as a spawn position for the player; it is a
  one-frame scratch holding pre-move X, so attacks can cancel the walk step.
- Dynamite has **no** debounce latch — re-fire is gated purely on
  `sprite_list[3].wType != 0`.

---

## 2. `kill_player` — `0x4C7E4`

`kill_player(void) -> void`

```c
player_dying = 0xFF;                       // 0x4BF18
HudCounters.bLives -= 1;                   // byte @0x4B32E
HudDirtyFlags.bLives_dirty = 0xFF;         // byte @0x4B356
bcd_timer_enable = 0;                      // word clear 0x4BE18
play_music(D0=0x13, D1=1);                 // death jingle
nPosYFrac     = 0;
nAnimFrameIdx = 0;
nVelY         = -0x300;                    // upward launch
nDirection    = 3;                         // X drift +3
if (nPosX >= 0x80) nDirection = -nDirection;   // drift away from the near wall
```

---

## 3. `player_death_physics` — `0x4C846`

`player_death_physics(void) -> void` — falls through into
`player_select_anim_frame`. Reached by tail-jump from `player_controller`.

```c
D1 = (nPosY << 16) | nPosYFrac;
D3 = ((int32)(int16)nVelY) << 8;
D3 += D1;

D2 = nPosX + nDirection;
if (nDirection <= 0) {
    if (D2 > 0)     nPosX = D2;
    else            nDirection = -nDirection;   // bounce off left edge
} else {
    if (D2 < 0xE8)  nPosX = D2;
    else            nDirection = -nDirection;   // bounce off right edge
}

nPosYFrac = (int16)D3;
nPosY     = (int16)(swap(D3));
nVelY    += 0x80;                          // gravity
goto player_select_anim_frame;             // 0x4C8C2
```

Note the asymmetry: on a bounce the X move is **discarded** (no `nPosX` write).

---

## 4. `player_sprite_update` — `0x4C8B2`

`player_sprite_update(void) -> void` — continuation, shares the controller's frame.

```c
if (player_collision_flags & 0x04) {       // bit2 = lethal tile
    kill_player();
    goto death_anim_frame;                 // 0x4C8CA
}
goto player_select_anim_frame;             // falls through to 0x4C8C2
```

---

## 5. `player_select_anim_frame` — `0x4C8C2`

`player_select_anim_frame(void) -> void` — **owns the `movem.l (SP)+ / rts`** that
returns from `player_controller`.

All frame tables are arrays of `uint32` sprite pointers. The index arithmetic is
`bclr #0,D4; D4 += D4` → byte offset `(idx & ~1) * 2` = longword index `idx >> 1`,
i.e. **every frame is held for 2 ticks**.

```c
if (player_dying) {
death_anim_frame:                          //                              0x4C8CA
    D4 = nAnimFrameIdx + 1;
    if (D4 >= 4) D4 = 0;
    nAnimFrameIdx = D4;
    gfx_data = ((uint32*)0x46BE6)[D4 >> 1];    // death, 2 frames x 2 ticks
    goto done_no_mirror;                        // 0x4CA54 - skips the mirror step
}

if (shoot_debounce) {                      // jump/shoot pose              0x4C8FA
    gfx_data = *(uint32*)0x46BB2;
    goto mirror;
}
if (stick_attack_active) {                 //                              0x4C910
    gfx_data = *(uint32*)0x46BBA;
    goto mirror;
}
if (crouching) {                           // crawl, 4 ticks               0x4C926
    D4 = nAnimFrameIdx;
    if (moved_flags) {
        D4 += 1;
        if (D4 >= 4) { D4 = 0; play_music(D0=0x0D, D1=1); }   // crawl sound
    }
    nAnimFrameIdx = D4;
    gfx_data = ((uint32*)0x46BDA)[D4 >> 1];
    goto mirror;
}
if (climbing) {                            // climb, 4 ticks               0x4C97A
    D4 = nAnimFrameIdx;
    if (moved_flags) {
        D4 += 1;
        if (D4 >= 4) { D4 = 0; play_music(D0=0x0C, D1=1); }   // climb sound
    }
    nAnimFrameIdx = D4;
    gfx_data = ((uint32*)0x46B9E)[D4 >> 1];
    goto done_no_mirror;                   // climb frames are NOT mirrored
}
if (on_ground) {                           //                              0x4C9CE
    if (moved_flags) {                     // walking, 10 ticks = 5 frames
        D4 = nAnimFrameIdx + 1;
        if (D4 >= 0x0A) D4 = 0;
        nAnimFrameIdx = D4;
        if (D4 == 0 || D4 == 5) play_music(D0=0x0C, D1=1);    // footsteps
        gfx_data = ((uint32*)0x46BC2)[D4 >> 1];
        goto mirror;
    }
    gfx_data = *(uint32*)0x46B96;          // standing still
    goto mirror;
}
gfx_data = *(uint32*)0x46BAA;              // airborne / idle              0x4CA38

mirror:                                    //                              0x4CA42
if (nDirection != 0) gfx_data += 0xFC0;    // left-facing sprite bank

done_no_mirror:                            //                              0x4CA54
pop {D0-D7, A0};
return;
```

| Table | Address | Frames | Used when |
|---|---|---|---|
| death | `0x46BE6` | 4 ticks / 2 frames | `player_dying` |
| jump / shoot pose | `0x46BB2` | single | `shoot_debounce` |
| stick jab | `0x46BBA` | single | `stick_attack_active` |
| crawl | `0x46BDA` | 4 ticks / 2 frames | `crouching` |
| climb | `0x46B9E` | 4 ticks / 2 frames | `climbing` (never mirrored) |
| walk | `0x46BC2` | 10 ticks / 5 frames | `on_ground && moved_flags` |
| stand | `0x46B96` | single | `on_ground` |
| airborne | `0x46BAA` | single | otherwise |

**Note:** the death and climb paths jump to `0x4CA54`, *bypassing* the `+0xFC0`
mirror step — those animations have no left-facing variant.

---

## 6. `player_bullet_update` — `0x4CA5A`

`player_bullet_update(void) -> void` — dispatch type 2. Ignores `A0`; operates on
`sprite_list[2]` absolutely.

```c
push {D6, D7};
D6 = bullet_point_x;                       // 0x4BF24
D7 = bullet_point_y;                       // 0x4BF26

if (sprite_list[2].nDirection == 0) {      // facing right
    sprite_list[2].nPosX += 8;
    D6 += 8;
} else {                                   // facing left
    sprite_list[2].nPosX -= 8;
    D6 -= 8;
}

if (bullet_hit_solid_test()) {             // carry SET = blocked
    despawn_offscreen_entity();            // 0x4AC3E
    pop {D6, D7};
    return;
}
bullet_point_x = D6;                       // advance the probe point
pop {D6, D7};
return;
```

**Correction:** `0x4BF24` is the bullet's **probe X coordinate**, not a
"range remaining" counter — it is seeded from the muzzle position and stepped by ±8
alongside `nPosX`. The bullet despawns purely on hitting something solid (or via
`bullet_hits_entity` when it strikes an entity); there is no travel budget.

---

## 7. `player_dynamite_update` — `0x4CAA8`

`player_dynamite_update(void) -> void` — dispatch type 3, operates on
`sprite_list[3]` absolutely.

```c
push {D0, D1, A0};

if (dynamite_exploding == 0) {             // ---- FUSE PHASE
    explosion_active = 0;
    D0 = sprite_list[3].nAnimFrameIdx;
    D1 = ((uint32*)0x46BF2)[D0 >> 1];      // fuse frame table
    if (D1 != 0xFFFFFFFF) {
        sprite_list[3].nAnimFrameIdx += 1;
        sprite_list[3].gfx_data = D1;
        if ((sprite_list[3].nAnimFrameIdx & 3) == 0)
            play_music(D0=0x09, D1=1);     // fuse tick every 4 ticks
        pop; return;
    }
    // fuse ran out -> detonate                                            0x4CB06
    dynamite_exploding = 0xFF;
    sprite_list[3].nPosX -= 4;
    sprite_list[3].nPosY -= 5;
    sprite_list[3].nRow_count     = 0;
    sprite_list[3].nAnimFrameIdx  = 0;
    play_music(D0=0x0A, D1=1);
    play_music(D0=0x0A, D1=0);
}

// ---- EXPLOSION PHASE ------------------------------------------------- 0x4CB5A
explosion_x = sprite_list[3].nPosX + 0x0C;
explosion_y = sprite_list[3].nPosY + 0x0A;
explosion_active = 0xFF;
if (sprite_list[3].nAnimFrameIdx >= 7) explosion_active = 0;   // lethal only frames 0..6

D0 = sprite_list[3].nAnimFrameIdx;
D1 = ((uint32*)0x46C3E)[D0 >> 1];          // explosion frame table
if (D1 != 0xFFFFFFFF) {
    sprite_list[3].nAnimFrameIdx += 1;
    sprite_list[3].gfx_data = D1;
    A0 = &sprite_list[1];                  // 0x4A74E — test the PLAYER
    if (explosion_overlaps_entity()) player_touched_hazard = 0xFF;
    pop; return;
}

sprite_list[3].wType = 0;                  //                              0x4CBD4
dynamite_exploding = 0;
explosion_active   = 0;
pop;
despawn_offscreen_entity();
return;
```

Your own dynamite is lethal to you — the explosion is explicitly tested against
`sprite_list[1]`.

---

## 8. `stick_attack_hits_entity` — `0x4CBF0`

`stick_attack_hits_entity(A0 = entity) -> carry set if hit`

```c
push.w {D0, D1, D2};
D0 = stick_attack_active;                  // 0x4BF1E (0 = inactive)
D1 = stick_point_x;                        // 0x4BF20
D2 = stick_point_y;                        // 0x4BF22
entity_contains_point();                   // sets carry
pop.w {D0, D1, D2};                        // movem.w does NOT disturb CCR
return;                                    // carry propagates to caller
```

---

## 9. `bullet_hits_entity` — `0x4CC10`

`bullet_hits_entity(A0 = entity) -> carry set if hit` (and consumes the bullet)

```c
push {D0, D1, D2, A0};
D0 = sprite_list[2].wType;                 // 0 = no bullet in flight
D1 = bullet_point_x;
D2 = bullet_point_y;
if (entity_contains_point()) {             // carry set
    sprite_list[2].wType = 0;              // consume the bullet
    sprite_list[2].bRender_flags_a |= 0x04;   // schedule erase blit
    sprite_list[2].bRender_flags_b |= 0x04;
    set_carry();                           // ori #1,CCR
}
pop {D0, D1, D2, A0};
return;
```

---

## 10. `entity_contains_point` — `0x4CC4C`

`entity_contains_point(A0 = entity, D0 = active?, D1 = X, D2 = Y) -> carry`

```c
if (D0 == 0) { clear_carry(); return; }    // source inactive
D0 = entity->nPosX;
if (D0 >  D1) goto miss;
D0 = D0 - 1 + entity->nHitboxW;
if (D0 <  D1) goto miss;
D0 = entity->nPosY;
if (D0 >  D2) goto miss;
D0 = D0 - 1 + entity->nHitboxH;
if (D0 <  D2) goto miss;
set_carry(); return;
miss:
clear_carry(); return;
```

Inclusive box: `nPosX <= X <= nPosX + nHitboxW - 1`, likewise for Y.

---

## 11. `explosion_overlaps_entity` — `0x4CC92`

`explosion_overlaps_entity(A0 = entity) -> carry set if overlapping`

```c
if (explosion_active == 0) { clear_carry(); return; }
push {D0, D1, D2, D3};
D0 = explosion_x - 0x10;
D1 = explosion_y - 0x0E;
D2 = entity->nHitboxW;
D3 = entity->nHitboxH;

D0 -= D2;              if (D0 >= entity->nPosX) goto miss;
D0 += 0x1F;  D0 += D2; if (D0 <  entity->nPosX) goto miss;
D1 -= D3;              if (D1 >= entity->nPosY) goto miss;
D1 += 0x1C;  D1 += D3; if (D1 <  entity->nPosY) goto miss;

pop; set_carry();  return;
miss:
pop; clear_carry(); return;
```

Effective blast box: 32 px wide (`0x1F + 1`) and 29 px tall (`0x1C + 1`), anchored at
`(explosion_x - 0x10, explosion_y - 0x0E)` and inflated by the target's own hitbox.

---

## 12. `bullet_hit_solid_test` — `0x4CCFC`

`bullet_hit_solid_test(D6 = X, D7 = Y) -> carry set if blocked`

```c
push {D4, D5, D6, D7, A0};
A0 = room_tile_map;                        // 0x4A17E
D4 = D6;  D5 = D7;                         // keep pixel coords
D6 >>= 3;                                  // tile column = X / 8
D7 &= 0xF8;  D7 *= 4;                      // tile row offset = (Y/8) * 0x20
A0 += D6 + D7;
D7 = *(uint8*)A0;                          // tile index
A0 = tile_attr_table_ptr;                  // *0x495D4
if (A0[D7] & 0x40) goto blocked;           // bit6 = solid

if (sprite_list[0].wType != 0) {           // the pushable block entity
    D6 = sprite_list[0].nPosX;
    if (D4 <  D6) goto clear;
    D6 += sprite_list[0].nHitboxW;
    if (D4 >= D6) goto clear;
    D6 = sprite_list[0].nPosY;
    if (D5 <  D6) goto clear;
    D6 += sprite_list[0].nHitboxH;
    if (D5 >= D6) goto clear;
    goto blocked;
}
clear:   pop; clear_carry(); return;
blocked: pop; set_carry();   return;
```

**Tile map addressing (confirmed):** `room_tile_map[(Y/8) * 0x20 + (X/8)]` — row-major
by Y, **0x20 (32) bytes per 8-pixel row**, covering X `0..255`.

---

## 13. `probe_player_tile_collision` — `0x4CD70`

`probe_player_tile_collision(D6 = X, D7 = Y) -> carry set if blocked`
Side effects: writes `player_collision_flags` (`0x4D00A`) and `ceiling_flag`
(`0x4D00B`).

The player is wider than one tile, so this ORs the attributes of a **block of tiles**
covering his body. There are four sampling variants chosen by `X & 7` (straddling a
column boundary or not) and `Y & 4` (which vertical band).

```c
push {D0-D7, A0, A1};
A0 = tile_attr_table_ptr;                  // *0x495D4
A1 = room_tile_map;                        // 0x4A17E
ceiling_flag = 0;
D0 = 0; D1 = 0; D4 = 0;

D6 += 4;                                   // probe uses X + 4 (body centre)
D2 = D6 >> 3;                              // tile column
D3 = (D7 & 0xF8) * 4;                      // tile row offset
A1 += D2 + D3;
D5 = D6 & 7;

// ---- Variant selection ------------------------------------------------
//  D5 != 0  -> 3 tiles wide, advance A1 by 0x1E after each triple
//  D5 == 0  -> 2 tiles wide, advance A1 by 0x1F after each pair
//  (D7 & 4) -> selects the 4-row sampling; otherwise 3 rows (+ an extra
//              masked row).  All four variants share the shape below.

// Row 1: OR attributes into D0 (outer tiles) and D1 (middle tile)
D4 = *A1++;  D0 |= A0[D4];
D4 = *A1++;  D1 |= A0[D4];                 // (3-wide variants only)
D4 = *A1;    D0 |= A0[D4];
A1 += 0x1E;                                // (or 0x1F in the 2-wide variants)

// ---- crouch: head-level solid is recorded, not enforced ---------------
if (crouching) {
    D5 = (D0 | D1) & 0x40;
    ceiling_flag = D5;                     // remember "something solid overhead"
    D0 &= ~0x40;  D1 &= ~0x40;             // bclr #6
    D0 &= ~0x04;  D1 &= ~0x04;             // bclr #2  (also drop lethal)
}

// Row 2: same shape
// Row 3: same shape, then
D0 &= 0x6F;  D1 &= 0x6F;                   // keep bits 0,1,2,3,5,6
// Row 4: same shape, then
D0 &= ~0x80;                               // bclr #7
D0 &= ~0x02;                               // bclr #1
D0 |= D1;

// ---- the pushable block counts as solid ------------------------------- 0x4CF72
if (sprite_list[0].wType != 0) {
    D2 = sprite_list[0].nHitboxW;
    D3 = sprite_list[0].nHitboxH;
    D1 = D6 - D2;          if (D1 >= sprite_list[0].nPosX) goto no_block;
    D1 += D2 + 0x0F;       if (D1 <  sprite_list[0].nPosX) goto no_block;
    D1 = D7 - D3;          if (D1 >= sprite_list[0].nPosY) goto no_block;
    D1 += D3 + 0x14;       if (D1 <  sprite_list[0].nPosY) goto no_block;

    if (crouching) {
        D1 = sprite_list[0].nPosY + D3 - 8;
        if (D7 > D1) { ceiling_flag |= 0x40; goto no_block; }   // block is overhead
    }
    D0 |= 0x40;                            // treat as solid
}
no_block:

D0 &= collision_mask;                      // 0x4BF16
player_collision_flags = D0;               // 0x4D00A

if ((D0 & 0xD0) != 0) { pop; set_carry();   return; }   // bits 7,6,4 = blocked
                        pop; clear_carry(); return;
```

**Notes / uncertainties**
- The four variants differ only in tile count per row (2 vs 3) and stride
  (`0x1F` vs `0x1E`) — the two must sum to `0x20`, the row stride. The `Y & 4` split
  selects how many rows are sampled before the `0x6F` mask is applied.
- The exact row count per variant is faithfully reproduced in the disassembly at
  `0x4CDB4`–`0x4CF70`; a reimplementation can equivalently OR the attributes of every
  tile intersecting the player's 24×21 box, applying the crouch and mask steps in the
  same order. **This equivalence has not been proven** — if bit-exactness matters,
  follow the four literal variants.
- `collision_mask` is the mechanism behind one-way platforms: `player_controller`
  clears bits 4 and 7 while `nVelY < 0`, so upward motion passes through them.

---

## Corrections to existing docs (for the orchestrator to apply)

1. **`0x4BF24` is not `bullet_range_remaining`.** It is `bullet_point_x`, the bullet's
   leading-edge probe X; `0x4BF26` is `bullet_point_y`. Seeded at fire time from the
   muzzle, stepped ±8 per frame. There is no range budget. (`re/data-structures.md`
   "Related globals" and any `functions.md` mention.)
2. **`SpriteEntity.nSpawnX` is overloaded for the player**: `0x4A75A` holds
   *pre-move X* for one frame so attacks can cancel a walk step. It is not a spawn
   position in slot 1.
3. **Tile map geometry confirmed**: `room_tile_map[(Y/8)*0x20 + (X/8)]`, 32 bytes per
   8-pixel row, X range 0..255.
4. **Input mapping resolved** (was "needs dynamic verification"): standard Atari
   joystick bits — 0=UP, 1=DOWN, 2=LEFT, 3=RIGHT, 7=FIRE, read from the IKBD
   joystick-1 report byte at `0x4922B`.
5. **Tile attribute bits resolved**: 0x02 ladder, 0x04 lethal, 0x10 one-way,
   0x20 landable floor, 0x40 solid, 0x80 ladder-top/one-way; blocked = `& 0xD0`.
6. **`player_sprite_update` / `player_select_anim_frame` are continuations**, not
   independent subroutines — they pop the 9 registers `player_controller` pushed.
7. The **slot-0 block** is read as a solid obstacle by both player and bullet probes,
   with a crouch special-case, but **nothing in this address range writes its
   position** — the pushing logic is still unlocated.
