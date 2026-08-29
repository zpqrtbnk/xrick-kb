# Rick Dangerous — Algorithms: Entities, Traps, Enemy AI

Exact transcriptions of every function in **`0x4B856`–`0x4C046`** and
**`0x4D00C`–`0x4DA40`**, taken from disassembly (not decompiler output). Together
these implement entity types 4–23 and 24–69, the shared trap/AI engine, the
collision helper suite, and the checkpoint/timer state.

**Bar:** reimplementable from this document alone. Constants are literal; branch
order is preserved. Field names follow `re/data-structures.md`.

## Calling conventions used throughout

| Convention | Meaning |
|---|---|
| `A0` | pointer to the current `SpriteEntity` — passed by `render_sprites` via the dispatch table |
| `A2` | per-type **effect callback**, loaded by `lea` in the type wrapper before delegating. The decompiler hides these loads entirely |
| `D0.b` (enemies) | **AI mode selector** (0/1/2), set by each `enemy_update_N` wrapper |
| **carry flag** | Every predicate helper returns its result in C: `ori #1,CCR` = true, `andi #~1,CCR` = false. Call sites branch with `bcs`/`bcc`. **None of them return a value in a register.** |

`play_music(D0.w = track, D1 = 0)` at `0x44CCE`; `add_score(D0.l = BCD delta)` at
`0x4B3E4`; `despawn_offscreen_entity(A0)` at `0x4AC3E`.

## Globals referenced

| Address | Name | Notes |
|---|---|---|
| `0x4A702` | `sprite_list[0]` | solid block; `+4/+6` pos, `+0x10/+0x12` hitbox |
| `0x4A74E` | `sprite_list[1].wType` | **the player-spawned flag** (see corrections) |
| `0x4A750`…`0x4A758` | player `nDirection`,`nPosX`,`nPosY`,`nVelY`,`nPosYFrac` | slot 1 fields |
| `0x4A79A` | `sprite_list[2].wType` | bullet alive flag |
| `0x4A7B0` / `0x4A7B6` | `sprite_list[2].bRender_flags_a/_b` | |
| `0x4BE18` | `timer_enable` (word) | |
| `0x4BE1A` | `timer_tick_divider` (word) | reload `0x19` = 25 |
| `0x4BE1C` | `timer_bcd_value` (2 BCD bytes) | |
| `0x4BE1E` | `timer_bcd_decrement` (2 BCD bytes) | static data |
| `0x4BF12`…`0x4BF15` | player state bytes | `0x4BF14` = crouching |
| `0x4BF18` | `player_dying` | |
| `0x4BF1A`,`0x4BF1C` | dynamite-exploding, unnamed | |
| `0x4BF1E` | `stick_attack_active` | with point `0x4BF20`/`0x4BF22` |
| `0x4BF24`/`0x4BF26` | **bullet X / Y** | see corrections |
| `0x4BF28`/`0x4BF2A`/`0x4BF2C` | `explosion_active` / `explosion_x` / `explosion_y` | |
| `0x4BF2E` | `player_touched_hazard` | |
| `0x4BFB8`…`0x4BFC1` | `CheckpointState` | |
| `0x4DC28`/`0x4DC29` | `tile_probe_mask` / `tile_probe_result` | |
| `0x495C7` | PRNG byte | low byte of the second PRNG word |
| `0x495CA` | `world_row_base` | |
| `0x4B32A`/`0x4B32C` | `bBullets` / `bDynamite` | dirty flags `0x4B352`/`0x4B354` |

---

# 1. `bTriggerFlags` — complete bit table

Derived entirely from `scripted_trap_update`. **Bits 2 and 3 are not the same
thing** (the previous docs conflated them as "always lethal"):

| Bit | Mask | Meaning |
|---|---|---|
| 7 | `0x80` | Triggered by **player touch** (player centre inside the trigger box) |
| 6 | `0x40` | Triggered by **stick jab** (`stick_attack_active` point in box) |
| 5 | `0x20` | Triggered by **bullet** (bullet alive and its point in box) |
| 4 | `0x10` | Triggered by **explosion** (`explosion_active` point in box) |
| 3 | `0x08` | Lethal **while triggered** (animation running) |
| 2 | `0x04` | Lethal **while idle** (before triggering) |
| 1 | `0x02` | On a bullet hit, remove the bullet via `despawn_offscreen_entity`; otherwise just set its erase-pending render bits |
| 0 | `0x01` | **One-shot**: at path end/off-screen, despawn permanently instead of resetting to spawn. Also makes `kill_enemy` call `mark_placement_dead` |

---

# 2. `scripted_trap_update` — `0x4D15C` (entity types 24–69)

`void scripted_trap_update(A0 = entity)`

```c
if (e->bAnimActive != 0) goto TRIGGERED;

/* ---------- IDLE ---------- */
e->wHazardActive = 0;
if (e->bTriggerFlags & 0x04) {              /* lethal while idle */
    *(u8*)&e->wHazardActive = 0xFF;         /* byte store -> word reads 0xFF00 */
    if (entity_overlaps_player(e))          /* carry set */
        player_touched_hazard = 0xFF;
}
if (player_dying != 0) return;              /* no triggering while dying */

/* trigger scan, in this exact order; first match wins */
if (e->bTriggerFlags & 0x80) {
    if (trigger_box_contains_point(e, player.nPosX + 11, player.nPosY + 10))
        goto FIRE;
}
if ((e->bTriggerFlags & 0x40) && stick_attack_active != 0) {
    if (trigger_box_contains_point(e, stick_x, stick_y)) goto FIRE;
}
if ((e->bTriggerFlags & 0x20) && sprite_list[2].wType != 0) {
    if (trigger_box_contains_point(e, bullet_x, bullet_y)) {
        sprite_list[2].wType = 0;                    /* consume the bullet */
        if (e->bTriggerFlags & 0x02) {
            despawn_offscreen_entity(&sprite_list[2]);
        } else {
            sprite_list[2].bRender_flags_a |= 0x04;  /* erase pending */
            sprite_list[2].bRender_flags_b |= 0x04;
        }
        goto FIRE;
    }
}
if ((e->bTriggerFlags & 0x10) && explosion_active != 0) {
    if (trigger_box_contains_point(e, explosion_x, explosion_y)) goto FIRE;
}
return;

FIRE:
e->bAnimActive = 0xFF;
if (e->wTriggerSound != 0)
    play_music(e->wTriggerSound & ~0x80, 0);         /* bit 7 stripped */
return;

/* ---------- TRIGGERED ---------- */
TRIGGERED:
e->wHazardActive = 0;
if (e->bTriggerFlags & 0x08) {              /* lethal while triggered */
    *(u8*)&e->wHazardActive = 0xFF;
    if (entity_overlaps_player(e)) player_touched_hazard = 0xFF;
}

/* --- animation step --- */
u16 idx   = e->nAnimFrameIdx + 1;
u32 frame = e->anim_frame_table[idx];       /* 4-byte entries */
if (frame == 0xFFFFFFFF) {                  /* end sentinel */
    u16 s = e->wTriggerSound;
    bool replay = (s & 0x80) != 0;          /* bclr sets Z from the ORIGINAL bit */
    s &= ~0x80;
    if (replay && s != 0) play_music(s, 0);
    idx = 1; frame = e->anim_frame_table[1];
    if (frame == 0xFFFFFFFF) { idx = 0; frame = e->anim_frame_table[0]; }
}
e->nAnimFrameIdx = idx;
e->gfx_data      = frame;

/* --- movement path step: 6-byte records {duration.w, dX.w, dY.w} --- */
u16 off = e->nPathStepIdx * 6;
if (e->movement_path_table[off].duration == -1) goto PATH_END;
e->nPosX += movement_path_table[off].dX;    /* +2 */
e->nPosY += movement_path_table[off].dY;    /* +4 */
e->nPathStepTick++;
if (e->nPathStepTick >= movement_path_table[off].duration) {
    e->nPathStepTick = 0;
    e->nPathStepIdx++;
}
/* on-screen bounds check */
if (e->nPosX < -8 || e->nPosX > 0xF0) goto PATH_END;
if (e->nPosY <  0 || e->nPosY > 0x142) goto PATH_END;
return;

PATH_END:
if (e->bTriggerFlags & 0x01) { despawn_offscreen_entity(e); return; }
e->bAnimActive   = 0;                       /* reset to idle at spawn point */
e->nAnimFrameIdx = 0;
e->nPathStepTick = 0;
e->nPathStepIdx  = 0;
e->nPosX = e->nSpawnX;
e->nPosY = e->nSpawnY;
e->gfx_data = e->anim_frame_table[0];
```

**Notes.** The animation loop restarts at index **1**, not 0 — frame 0 is a
one-time "intro" frame, replayed only if the table has a single entry. The
`0x4D170`/`0x4D284` hazard stores are `move.b #-1,(0x3a,A0)`, i.e. byte writes into
the *high* half of the `wHazardActive` word; readers use `tst.w`, so the effective
value is `0xFF00`. Reimplement as a byte store or the word test still succeeds.

---

# 3. `enemy_ai_update` — `0x4D4F4` (shared by types 4–15)

`void enemy_ai_update(A0 = entity, D0.b = aiMode)`

`aiMode` comes from the calling wrapper and selects the turn policy:

| aiMode | Turn policy |
|---|---|
| 0 | **Step-counted patrol** — `nPathStepIdx` counts down by 2 each step; on reaching ≤0 turn and reload from `nAiTimerReload` |
| 1 | **Player-seeking** — every 8 animation steps, face the player |
| 2 | **Random** — every 8 steps, turn if `prng & 3 == 0`. Also the only mode that can enter chase |

```c
/* ---------- DYING ---------- */
if (e->bDying != 0) {
    if (e->nDirection == 0) e->nPosX -= 1;   /* subi.w #1,(0x4,A0) */
    else                    e->nPosY += 1;   /* addi.w #1,(0x6,A0) */
    i32 fixed = (e->nPosY << 16) | e->nPosYFrac;
    fixed += (i32)(i16)e->nVelY << 8;
    e->nPosY     = fixed >> 16;
    e->nPosYFrac = fixed & 0xFFFF;
    e->nVelY    += 0xC4;                     /* no terminal clamp while dying */
    e->nAnimFrameIdx++;
    goto FINISH;
}

/* ---------- damage checks ---------- */
if (explosion_overlaps_entity(e)) { add_score(0x50); goto KILL; }
if (bullet_hits_entity(e))        { goto KILL; }

if (e->bAiCooldown != 0) e->bAiCooldown--;
if (stick_attack_hits_entity(e)) e->bAiCooldown = 0x19;   /* 25 frames stunned */
tile_probe_result = 0;

if (e->bChasing != 0) goto CHASE;

/* ---------- WALK ---------- */
D6 = e->nPosX;
i32 fixed = (e->nPosY << 16) | e->nPosYFrac;
fixed += (i32)(i16)e->nVelY << 8;
D7 = fixed >> 16;                            /* candidate Y */
tile_probe_mask = 0xFF;
if (!probe_entity_tile_collision(D6, D7)) {  /* carry clear = free -> falling */
    e->nPosY     = D7;
    e->nPosYFrac = fixed & 0xFFFF;
    e->nVelY    += 0x80;
    if (e->nVelY > 0x800) e->nVelY = 0x800;  /* terminal velocity */
    goto FINISH;
}
/* landed */
if (aiMode == 2 && (tile_probe_result & 0x80) && D7 <= player.nPosY) {
    if (!(D6 & 8) || (D6 & 7) == 0) {        /* aligned to a half-cell */
        e->nPosX = (D6 & ~0x0F) | 0x04;
        *((u8*)e + 7) = (*((u8*)e + 7) & ~7) | 5;   /* low byte of nPosY */
        e->nPosYFrac = 0; e->bChasing = 0xFF; e->nAnimFrameIdx = 0;
        goto FINISH;
    }
}
*((u8*)e + 7) = (*((u8*)e + 7) & ~7) | 3;    /* snap Y onto the floor */
D7 = e->nPosY; e->nPosYFrac = 0; e->nVelY = 0x100;

if (aiMode == 2) {
    probe_entity_tile_collision(D6, D7);
    if ((tile_probe_result & 0x02) && D7 > player.nPosY) {
        if (!(D6 & 8) || (D6 & 7) == 0) {
            e->nPosX = (e->nPosX & ~0x0F) | 0x04;
            e->nPosYFrac = 0; e->bChasing = 0xFF; e->nAnimFrameIdx = 0;
            goto FINISH;
        }
    }
}
if (e->bAiCooldown != 0) goto FINISH;        /* stunned: no movement */

D6 += (e->nDirection != 0) ? -2 : +2;        /* 2 px/frame */
if (probe_entity_tile_collision(D6, D7)) goto TURN_RELOAD;   /* wall */
e->nPosX = D6; e->nPosY = D7; e->nAnimFrameIdx++;

if (aiMode == 0) {
    e->nPathStepIdx -= 2;
    if (e->nPathStepIdx > 0) goto FINISH;
    goto TURN_RELOAD;
}
if (e->nAnimFrameIdx != 8) goto FINISH;      /* decide only every 8th step */
if (aiMode == 1) {
    if (D6 > player.nPosX) { if (e->nDirection != 0) goto FINISH; else goto TURN; }
    else                   { if (e->nDirection != 0) goto TURN;   else goto FINISH; }
} else {                                     /* aiMode 2 */
    update_prng();
    if ((prng_byte & 3) != 0) goto FINISH;
    goto TURN;
}

TURN_RELOAD:
e->nPathStepIdx = e->nAiTimerReload;
TURN:
e->nAnimFrameIdx = 0;
e->nDirection = (e->nDirection != 0) ? 0 : 0xFF;
goto FINISH;

/* ---------- CHASE (flying / homing) ---------- */
CHASE:
if (e->bAiCooldown != 0) goto FINISH;
D6 = e->nPosX; D7 = e->nPosY;
e->nVelY = 0x100;
tile_probe_mask = 0x7F;
if ((D7 & ~1) == (player.nPosY & ~1)) goto CHASE_X;   /* Y-aligned */
if (D7 >= player.nPosY) {
    D7 -= 2;
    if (probe_entity_tile_collision(D6, D7)) goto CHASE_X;
    e->nVelY = -0x200;
} else {
    D7 += 2;
    if (probe_entity_tile_collision(D6, D7)) goto EXIT_CHASE;
}
e->nPosY = D7; e->nAnimFrameIdx++;
goto CHASE_CHECK;

CHASE_X:
D7 = e->nPosY;
if (D6 == player.nPosX) goto FINISH;
if (D6 >= player.nPosX) { e->nDirection = 0xFF; D6 -= 2; }
else                    { e->nDirection = 0;    D6 += 2; }
if (probe_entity_tile_collision(D6, D7)) goto FINISH;
e->nPosX = D6; e->nAnimFrameIdx++;

CHASE_CHECK:
if (tile_probe_result & 0x02) goto FINISH;
EXIT_CHASE:
e->bChasing = 0; e->nAnimFrameIdx = 2; e->nPosYFrac = 0;

/* ---------- shared tail ---------- */
FINISH:
if (e->bDying == 0) {
    if (entity_overlaps_player(e)) player_touched_hazard = 0xFF;
    if ((tile_probe_result & 0x04) || entity_touches_hazard_or_block(e))
        kill_enemy(e);
}
KILL_JOIN:
u16 f = e->nAnimFrameIdx;
if (f > 7) { e->nAnimFrameIdx = 0; f = 0; }
else       { f = (f & ~1) * 2; }             /* frame pairs -> byte offset */
if      (e->bDying)   e->gfx_data += *(u32*)(0x46C92 + f);
else if (e->bChasing) e->gfx_data += *(u32*)(0x46C7E + f);
else {
    u32 d = *(u32*)(0x46C6A + f);
    if (e->nDirection != 0) d += 0x3F0;      /* mirrored bank */
    e->gfx_data += d;
}
```

**Notes / uncertainties.**
- The frame offset is **added** to `gfx_data`, which the wrapper preset to a bank
  base — so `gfx_data` is `bank + frame_offset`, not a plain pointer.
- ✅ **Dying-drift branch verified against disassembly 2026-08-29.** The two arms
  really do act on different axes, and the transcription is byte-faithful:

  ```
  4D4F4  tst.b  (0x49,A0)        ; bDying
  4D4F8  beq.w  4D542            ; not dying -> damage checks
  4D4FC  tst.w  (0x2,A0)         ; nDirection
  4D500  bne.b  4D50A
  4D502  subi.w #0x1,(0x4,A0)    ; nPosX -= 1   (nDirection == 0)
  4D508  bra.b  4D510
  4D50A  addi.w #0x1,(0x6,A0)    ; nPosY += 1   (nDirection != 0)
  ```

  `+0x04` is `nPosX` and `+0x06` is `nPosY` (both *confirmed* in
  `data-structures.md`), so `subi.w` on one axis and `addi.w` on the other is exactly
  what the program does. Reproduce it literally. No claim is made about authorial
  intent — the object code is the specification.

  The rest of the dying block is likewise byte-faithful: the 8.8 integration builds
  `D1 = (nPosY << 16) | nPosYFrac` via `moveq #0 / move.w / swap / move.w`, adds
  `ext.l`-sign-extended `nVelY << 8`, and splits the result back across `+0x06`/`+0x0A`;
  gravity is `addi.w #0xc4,(0x8,A0)` with **no terminal clamp**, and the frame index is
  `addi.w #0x1,(0x2a,A0)`.
- `tile_probe_result` bit meanings used here: `0x02` = ledge/edge, `0x04` = lethal
  tile, `0x80` = chase-enabling tile. ✅ **Remaining bits resolved 2026-08-29**:
  `0x01` and `0x08` are inert background classes tested by no reader, `0x20` is the
  rare bounce surface (4 tiles game-wide), `0x40` solid, `0x10` one-way. See
  `data-structures.md` → *Tile attribute bits*.

## `enemy_update_4`…`15` — `0x4D39C`–`0x4D4E2` (12 wrappers)

Each is: set `D0.b` = aiMode, set `gfx_data` = bank base, optionally swap to the
alternate bank when `bTriggerFlags` bit 7 is set, then `bsr enemy_ai_update`.

| Type | Addr | aiMode | Bank | Alt bank (if bit 7) |
|---|---|---|---|---|
| 4 | `0x4D39C` | 0 | `0x0000` | `0x8B20` |
| 5 | `0x4D3BE` | 1 | `0x0000` | `0x8B20` |
| 6 | `0x4D3E0` | 2 | `0x0000` | *(none)* |
| 7 | `0x4D3F2` | 0 | `0x0D20` | `0x95A0` |
| 8 | `0x4D414` | 1 | `0x0D20` | `0x95A0` |
| 9 | `0x4D436` | 2 | `0x0D20` | *(none)* |
| 10 | `0x4D448` | 0 | `0x1A40` | `0xA020` |
| 11 | `0x4D46A` | 1 | `0x1A40` | `0xA020` |
| 12 | `0x4D48C` | 2 | `0x1A40` | *(none)* |
| 13 | `0x4D49E` | 0 | `0x2760` | `0xAAA0` |
| 14 | `0x4D4C0` | 1 | `0x2760` | `0xAAA0` |
| 15 | `0x4D4E2` | 2 | `0x2760` | *(none)* |

Banks step by `0x0D20`; alt banks by `0x0A80`. The third type of each triple
(aiMode 2) has **no** alt-bank check — consistent with mode 2 being the
chase-capable variant that uses a different frame set.

---

# 4. Pickups and trigger zones

## `destructible_pickup_update` — `0x4D058` (types 16/17)

`void destructible_pickup_update(A0 = entity, A2 = effect callback)`

```c
if (e->wHazardActive != 0) goto DESTROYING;
if (stick_attack_hits_entity(e)) goto DESTROY;
if (bullet_hits_entity(e))       goto DESTROY;
if (explosion_overlaps_entity(e)) {
DESTROY:
    mark_placement_dead(e);
    play_music(0x0A, 0);
    e->wHazardActive = 0xFF;                /* full word here, not a byte store */
    goto DESTROYING;
}
if (entity_overlaps_player(e)) {            /* collected */
    (*A2)();                                /* refill effect */
    mark_placement_dead(e);
    despawn_offscreen_entity(e);
    play_music(0x10, 0);
}
return;

DESTROYING:                                  /* destruction animation */
u16 f = (e->nAnimFrameIdx & ~1) * 2;
u32 frame = *(u32*)(0x46C3E + f);
if (frame == 0xFFFFFFFF) { despawn_offscreen_entity(e); return; }
e->nAnimFrameIdx++;
e->gfx_data = frame;
if (entity_overlaps_player(e)) player_touched_hazard = 0xFF;  /* debris kills */
```

Wrappers: `destructible_pickup_16` (`0x4D00C`) sets `gfx_data = 0x2F46E`,
`A2 = effect_refill_dynamite`; `destructible_pickup_17` (`0x4D020`) sets
`gfx_data = 0x2F5BE`, `A2 = effect_refill_bullets`.

- `effect_refill_dynamite` `0x4D034`: `bDynamite = 6; bDynamite_dirty = 0xFF;`
- `effect_refill_bullets` `0x4D046`: `bBullets = 6; bBullets_dirty = 0xFF;`

## `treasure_pickup_update` — `0x4D102` (types 18–21)

`void treasure_pickup_update(A0 = entity, D0.w = type index)`

```c
if (e->nPathStepIdx != 0) {                  /* sparkle phase */
    if (--e->nPathStepIdx == 0) { despawn_offscreen_entity(e); return; }
    e->gfx_data = 0x3822E;
    e->nPosY -= 2;                           /* drifts upward */
    return;
}
e->gfx_data = D0 * 0x150 + 0x2F70E;          /* one 0x150 frame per type */
if (entity_overlaps_player(e)) {
    add_score(0x500);
    mark_placement_dead(e);
    e->nPathStepIdx = 0x0C;                  /* 12-frame sparkle */
    play_music(0x11, 0);
}
```

## `trigger_zone_update` — `0x4BEDC` (types 22/23)

`void trigger_zone_update(A0 = entity, A2 = event callback)`

```c
if (player_dying != 0) return;
if (!trigger_box_contains_point(e, player.nPosX + 11, player.nPosY + 10)) return;
despawn_offscreen_entity(e);
(*A2)();
if (e->bTriggerFlags & 0x01) mark_placement_dead(e);
```

Wrappers `trigger_zone_22` (`0x4BE68`) / `trigger_zone_23` (`0x4BEA2`) both clear
`gfx_data` (invisible) and set `A2`:

- `effect_start_escape_timer` `0x4BE7C`:
  `timer_enable = 0xFF; timer_tick_divider = 0x19; timer_bcd_value = 0x2000;
   play_music(0x12, 0);`
- `effect_stop_timer_award_bonus` `0x4BEB6`:
  `if (timer_enable) { play_music(7,0); timer_enable = 0;
   add_score(timer_bcd_value); }` — the remaining time is banked as score.

---

# 5. Collision / interaction helpers

All return their result in the **carry flag**.

## `trigger_box_contains_point` — `0x4D986`
`carry trigger_box_contains_point(A0 = entity, D0.w = x, D1.w = y)`
```c
return (x >= e->nTrigBoxXMin) && (y >= e->nTrigBoxYMin)
    && (x <= e->nTrigBoxXMax) && (y <= e->nTrigBoxYMax);
```

## `entity_overlaps_player` — `0x4D9AA`
`carry entity_overlaps_player(A0 = entity)`
```c
if (player_dying != 0) return false;         /* corpses cannot be hit */
i16 w = e->nHitboxW, h = e->nHitboxH;
i16 x = player.nPosX + 5 - w;
if (x >= e->nPosX)          return false;
if (x + w + 0x0D < e->nPosX) return false;
i16 y = player.nPosY;
if (player_crouching) y += 8;
y -= h;
if (y >= e->nPosY)          return false;
i16 yy = y + h + 0x14;
if (player_crouching) yy -= 8;
if (yy < e->nPosY)          return false;
return true;
```
The player box is 13 px wide (offset +5) and 20 px tall, shrinking to 12 px and
shifting down 8 px while crouching.

## `entity_touches_hazard_or_block` — `0x4D8B0`
`carry entity_touches_hazard_or_block(A0 = entity)`
```c
/* (a) the solid block in slot 0 */
if (sprite_list[0].wType != 0) {
    i16 w = sprite_list[0].nHitboxW, h = sprite_list[0].nHitboxH;
    i16 x = e->nPosX + 4 - w;
    if (x < block.nPosX && x + w + 0x0F >= block.nPosX) {
        i16 y = e->nPosY - h;
        if (y < block.nPosY && y + h + 0x14 >= block.nPosY) return true;
    }
}
/* (b) any hazard-active entity in slots 4..8 */
for (SpriteEntity *o = &sprite_list[4]; o != &sprite_list[9]; o++) {
    if (o->wType == 0 || o->wHazardActive == 0) continue;
    i16 w = o->nHitboxW, h = o->nHitboxH;
    i16 x = e->nPosX + 4 - w;
    if (x >= o->nPosX || x + w + 0x0F < o->nPosX) continue;
    i16 y = e->nPosY - h;
    if (y >= o->nPosY || y + h + 0x14 < o->nPosY) continue;
    return true;
}
return false;
```
Loop bounds are the literals `0x4A832` (slot 4) to `0x4A9AE` (slot 9), stride
`0x4C`.

## `kill_enemy` — `0x4D87C`
```c
e->bDying = 0xFF;
e->nPosYFrac = 0;
e->nVelY = -0x300;                            /* upward launch */
add_score(0x50);
play_music(0x13, 0);
if (e->bTriggerFlags & 0x01) mark_placement_dead(e);
```

## `mark_placement_dead` — `0x4DA30`
```c
((u8*)e->placement_record_ptr)[2] |= 0x80;    /* DEAD bit */
```

## `probe_entity_tile_collision` — `0x4DA40`
`carry probe_entity_tile_collision(D6.w = x, D7.w = y)`

**Returns the carry flag only** — it restores D0–D7/A0/A1 from the stack on exit,
so it produces *no* register result. Its output is the global `tile_probe_result`.

```c
A0 = tile_attr_table_ptr;                     /* 0x495D4 */
x += 4;                                       /* addi.w #4,D6 -- BEFORE the index */
A1 = &room_tile_map[(x >> 3) + ((y & ~7) * 4)];   /* 0x4A17E, 0x20 bytes per ROW */
D0 = D1 = D4 = 0;

/* ---- LITERAL four-variant transcription, 0x4DA7E-0x4DBB2 (2026-08-29) ----
   Identical in shape to probe_player_tile_collision (see algo-player.md) except
   that this one has NO crouch block and NO ceiling_flag. Same row counts, same
   strides, and the same tail asymmetry.

     D5 = x & 7 (after the +=4) ;  bit2 of D7 = y & 4
     A' 0x4DA7E : D5!=0, y&4!=0 -> 3 tiles, stride 0x1E, 4 rows, mask after row 3, tail YES
     B' 0x4DAE8 : D5!=0, y&4==0 -> 3 tiles, stride 0x1E, 3 rows, mask after row 2, tail YES
     C' 0x4DB42 : D5==0, y&4!=0 -> 2 tiles, stride 0x1F, 4 rows, mask after row 3, tail NO
     D' 0x4DB84 : D5==0, y&4==0 -> 2 tiles, stride 0x1F, 3 rows, mask after row 2, tail NO   */

#define TRIPLE  D4=*A1++; D0|=A0[D4];  D4=*A1++; D1|=A0[D4];  D4=*A1; D0|=A0[D4];
#define PAIR    D4=*A1++; D0|=A0[D4];                         D4=*A1; D0|=A0[D4];

if ((x & 7) != 0) {                    /* 3 tiles wide, stride 0x1E */
    if (y & 4) { TRIPLE A1+=0x1E; TRIPLE A1+=0x1E; TRIPLE A1+=0x1E;
                 D0 &= 0x6F; D1 &= 0x6F;  TRIPLE }          /* A' -- 4 rows */
    else       { TRIPLE A1+=0x1E; TRIPLE A1+=0x1E;
                 D0 &= 0x6F; D1 &= 0x6F;  TRIPLE }          /* B' -- 3 rows */
    D0 &= ~0x80;  D0 &= ~0x02;  D0 |= D1;      /* 3-wide ONLY */
} else {                               /* 2 tiles wide, stride 0x1F */
    if (y & 4) { PAIR A1+=0x1F; PAIR A1+=0x1F; PAIR A1+=0x1F;
                 D0 &= 0x6F;  PAIR }                        /* C' -- 4 rows */
    else       { PAIR A1+=0x1F; PAIR A1+=0x1F;
                 D0 &= 0x6F;  PAIR }                        /* D' -- 3 rows */
    /* NO bclr #7, NO bclr #1, NO "D0 |= D1". D1 stays 0 throughout. */
}
/* slot-0 block counts as solid */
if (sprite_list[0].wType != 0
    && x - block.nHitboxW < block.nPosX && x - block.nHitboxW + block.nHitboxW + 0x0F >= block.nPosX
    && y - block.nHitboxH < block.nPosY && y - block.nHitboxH + block.nHitboxH + 0x14 >= block.nPosY)
    D0 |= 0x40;
D0 &= tile_probe_mask;                        /* 0xFF walking, 0x7F chasing */
tile_probe_result = D0;
return (D0 & 0xD0) != 0;                      /* carry = blocked */
```
✅ **The four sampling shapes are now transcribed literally** (above, 2026-08-29),
not in outline. They are structurally identical to `probe_player_tile_collision`'s,
including the fact that the **2-wide variants have no `D1` accumulator and no
`bclr #7`/`bclr #1`/`or D1,D0` tail** — see `byte-identity.md` Audit 6. The bounds
checks in the block test use **signed** `bge`/`blt`. Superseded note:
LUT walk is **deferred to `algo-level.md`**, which owns the tile map.

---

# 6. Timer, player state, checkpoint

## `stop_bcd_timer` — `0x4BE20`
```c
timer_enable = 0;
```

## `bcd_countdown_timer` — `0x4BE28`
```c
if (timer_enable == 0) return;
if (--timer_tick_divider != 0) return;
timer_tick_divider = 0x19;                    /* 25 frames per BCD tick */
clear_X_and_C();
/* two-byte BCD subtract, high-to-low via predecrement */
timer_bcd_value[1] = sbcd(timer_bcd_value[1], timer_bcd_decrement[1]);
timer_bcd_value[0] = sbcd(timer_bcd_value[0], timer_bcd_decrement[0]);
if (timer_bcd_value == 0) timer_enable = 0;
```

## `reset_player_state` — `0x4BF30`
```c
player_touched_hazard = 0;      player_dying = 0;
*(u8*)0x4BF12 = 0;  *(u8*)0x4BF13 = 0;
player_crouching = 0;  *(u8*)0x4BF15 = 0;
*(u8*)0x4D00B = 0;                            /* ceiling-above flag */
player.nVelY = 0x100;   *(u8*)0x4A758 = 0;    /* nPosYFrac high byte */
player.nDirection = 0;
player.nAnimFrameIdx = 0;                     /* 0x4A778 */
stick_attack_active = 0;  dynamite_exploding = 0;
explosion_active = 0;     *(u16*)0x4BF1C = 0;
bBullets = 6;  bDynamite = 6;
bBullets_dirty = 0xFF;  bDynamite_dirty = 0xFF;
```
Note it does **not** touch `bLives` — lives persist across respawns.

## `spawn_player_entity` — `0x4BFAE`
```c
sprite_list[1].wType = 1;                     /* 0x4A74E */
```

## `save_checkpoint_state` — `0x4BFC2`
```c
cp.saved_a752 = player.nPosX;      /* 0x4BFB8 */
cp.saved_a754 = player.nPosY;      /* 0x4BFBA */
cp.saved_a750 = player.nDirection; /* 0x4BFBC */
cp.saved_95ca = world_row_base;    /* 0x4BFBE */
cp.saved_d00b = *(u8*)0x4D00B;     /* 0x4BFC0 */
cp.saved_bf14 = player_crouching;  /* 0x4BFC1 */
```

## `restore_checkpoint_state` — `0x4C000`
```c
reset_player_state();
player.nPosX = cp.saved_a752;   player.nPosY   = cp.saved_a754;
player.nDirection = cp.saved_a750;  world_row_base = cp.saved_95ca;
*(u8*)0x4D00B = cp.saved_d00b;  player_crouching = cp.saved_bf14;
spawn_player_entity();
```

---

# 7. `decorative_sprite_update` — `0x4B856` (type 70)

Operates on **`sprite_list[12]` by absolute address**, ignoring `A0` for state
(it only writes `gfx_data` through `A0`). Uses a **10-byte** path record format,
distinct from the traps' 6-byte one.

```c
A1 = slot12.movement_path_table;              /* 0x4AAC8 */
u16 off = slot12.nPathStepIdx * 10;           /* 0x4AABE */
if (slot12.anim_frame_table == NULL) return;  /* 0x4AAC4 */

/* animation: nAnimFrameIdx is a BYTE offset, stepped by 4 */
A2 = slot12.anim_frame_table;
u16 ai = slot12.nAnimFrameIdx;                /* 0x4AABC */
u32 frame = *(u32*)(A2 + ai);
if (frame == 0xFFFFFFFF) { ai = 0; frame = *(u32*)A2; }
slot12.nAnimFrameIdx = ai;
e->gfx_data = frame;
slot12.nAnimFrameIdx += 4;

if (*(i16*)(A1 + off) == 0) return;           /* duration 0 = path finished */
slot12.nPosX += *(i16*)(A1 + off + 2);        /* 0x4AA96 */
slot12.nPosY += *(i16*)(A1 + off + 4);        /* 0x4AA98 */
slot12.nPathStepTick++;                       /* 0x4AAC0 */
if (slot12.nPathStepTick <= *(i16*)(A1 + off)) return;
slot12.nPathStepTick = 0;
slot12.nPathStepIdx++;
slot12.nAnimFrameIdx = 0;
off += 10;                                    /* peek the next record */
if (*(i16*)(A1 + off) == 0) return;
slot12.anim_frame_table = *(u32*)(A1 + off + 6);   /* per-step anim swap */
```

Record layout: `{ duration.w, dX.w, dY.w, anim_frame_table.l }` = 10 bytes;
`duration == 0` terminates.

---

# Corrections for the parent to apply

These contradict current `re/` docs. I did **not** edit those files.

1. **`bTriggerFlags` bits 2 and 3 are distinct.** `0x04` = lethal **while idle**;
   `0x08` = lethal **while triggered**. `data-structures.md` lists them jointly as
   "0x08/0x04 always-lethal".
2. **`bTriggerFlags` bit 1 (`0x02`) is not "bullet passes through".** The bullet is
   consumed either way (`sprite_list[2].wType = 0` happens first); the bit only
   selects *how* it is cleaned up — `despawn_offscreen_entity` vs. setting the
   erase-pending render bits.
3. **The three enemy sub-types per visual are NOT identical.** Each wrapper passes a
   distinct `D0.b` AI mode (0 = step-counted patrol, 1 = player-seeking, 2 = random
   + chase-capable). `entities.md` says they "decompile identically — differences
   come from placement data"; that is wrong.
4. **`0x4A74E` is `sprite_list[1].wType`, not a generic "state_flag".**
   `spawn_player_entity` writes `1` there. The main loop's "state_flag" dispatch is
   really testing whether the player entity is spawned. Affects `functions.md`'s
   main-loop description.
5. **`0x4A752`/`0x4A754` are not "copies".** They are `sprite_list[1].nPosX` /
   `.nPosY` directly (slot 1 base `0x4A74E`). The labels `player_pos_x_copy` /
   `player_pos_y_copy` are misleading.
6. **`0x4BF24` is the bullet's X coordinate, not `bullet_range_remaining`.**
   `scripted_trap_update` passes `0x4BF24`/`0x4BF26` as the (x, y) point for the
   bullet trigger test. New: `0x4BF20`/`0x4BF22` are the stick-attack point.
7. **`probe_entity_tile_collision` returns no register value** — it restores all of
   D0–D7 before `rts`. `enemy_ai_update`'s `cmp.b #2,D0b` is testing the *caller's*
   `aiMode`, not a floor-type return code. `entities.md`'s "returns floor-type code"
   is wrong, and so is the plate comment at `0x4DA40`.
8. `kill_enemy` awards `add_score(0x50)` and plays track `0x13`; the explosion path
   in `enemy_ai_update` awards a *second* `0x50` before calling it.

# Unresolved

- Exact per-shape offset sequences inside `probe_entity_tile_collision` (outlined
  only; belongs with the tile map in `algo-level.md`).
- ~~`tile_probe_result` bits and the `0x6F` mask~~ ✅ **resolved 2026-08-29.**
  `0x6F` = `~(0x10|0x80)`, a **row filter**: applied after the upper rows so one-way
  and ladder-top can only be contributed by the bottom row (feet). Bits `0x01`/`0x08`
  are inert. See `data-structures.md` → *Tile attribute bits*.
- ~~The dying-enemy `nPosY += 1` asymmetry~~ ✅ **verified against disassembly
  2026-08-29** — `subi.w #1,(0x4,A0)` / `addi.w #1,(0x6,A0)`, transcription is
  byte-faithful. Reproduce literally.
- `0x4BF12`, `0x4BF13`, `0x4BF15`, `0x4BF1C` are cleared by `reset_player_state`
  but not read anywhere in my ranges; they belong to `algo-player.md`.
