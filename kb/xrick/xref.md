# Cross-reference — the port ↔ our reverse-engineering

**This is a state document.** It records how the two reversals correspond: which names
map onto which, where they agree, and where they differ. It holds no tasks and no
progress log.

Nothing here is a conclusion about the original game. Where the two sides differ, the
three candidate causes from `provenance.md` — a genuine PC-vs-ST difference, a port
error, or our error — are distinguished only where evidence allows.

Our side is `../`; addresses are ST physical addresses in `atari_ram.bin`.

## Name correspondence

### Structures

| Port (`ents.h`, `maps.h`) | Ours (`kb/data-structures.md`) |
|---|---|
| `ent_t` | `SpriteEntity` |
| `ent_t.n` | `SpriteEntity` type byte + DEAD/LETHAL bit |
| `ent_t.flags` | `bTriggerFlags` (0x46) |
| `ent_t.offsy` | `nVelY` (0x08) |
| `ent_t.ylow` | `nPosYFrac` |
| `ent_t.latency` | `bAiCooldown` (0x4A) |
| `ent_t.trig_x` (patrol use) | `nAiTimerReload` (0x30) |
| `entdata_t` / `ent_entdata[74]` | `ObjectTypeDef` / `object_type_defs[75]` @ `0x47D34` |
| `mark_t` / `map_marks[523]` | `PlacementRecord` / `placement_table[523]` @ `0x481E4` |
| `mvstep_t` / `ent_mvstep[784]` | the scripted-trap path steps |
| `map_submaps[47]` | the 47 rooms |
| `map_connect[153]` | `TransitionWaypoint` lists |
| `map_eflg[]` bits | `player_collision_flags` bits (`0x4D00A`) |

### Functions

| Port | Ours |
|---|---|
| `u_envtest` (ASM 0FBC/103E) | `probe_player_tile_collision` |
| — (enemy path, same function in the port) | `probe_entity_tile_collision` |
| `e_rick_action` / `_action2` (12CA/13BE) | `player_controller` |
| `e_rick_gozombie` (1851) | `kill_player` |
| `e_them_gozombie` (237B) | `kill_enemy` |
| `e_them_t1a/t1b/t2_action` | the three enemy AI modes |
| `e_them_t3_action` (2546) | the shared scripted-trap engine |
| `ent_actvis` (1F40) | `spawn_level_entity` / `init_entity_from_placement` |
| `map_chain` (0c08) | `process_level_transition_point` |
| `map_expand` | the tilemap block decoder |
| `map_resetMarks` (0025) | `revive_all_placements` (`0x495E0`) |
| `sprites_paint2` | the sprite blitter |
| `ents_paintAll` | the entity draw pass |

### Entity type dispatch

The port writes type numbers in **hex** and we write them in **decimal**; they are the
same numbers, and the partition is identical. The port's "24 `ent_actf` entries plus a
`>= 0x18` catch-all" is exactly our types 0-23 dispatched individually with 24-73
sharing one handler.

| Port `n` | Port handler | Our type | Our handler |
|---|---|---|---|
| `0x00` | `NULL` - free slot | 0 | free slot (`ObjectTypeDef[0]` all-zero) |
| `0x01` | `e_rick_action` | 1 | `player_controller` |
| `0x02` | `e_bullet_action` | 2 | `player_bullet_update` |
| `0x03` | `e_bomb_action` | 3 | `player_dynamite_update` |
| `0x04`-`0x0F` | `e_them_t1a` / `_t1b` / `_t2`, 4 banks x 3 modes | 4-15 | `enemy_update_4..15` -> `enemy_ai_update`, 4 banks x 3 AI modes |
| `0x10`-`0x11` | `e_box_action` | 16-17 | `destructible_pickup_16` / `_17` |
| `0x12`-`0x15` | `e_bonus_action` | 18-21 | `treasure_pickup_18..21` |
| `0x16`-`0x17` | `e_sbonus_start` / `_stop` | 22-23 | `trigger_zone_22` / `_23` |
| `>= 0x18` | `e_them_t3_action` | 24-73 | `scripted_trap_update` |
| `0x47` | `e_them_z_action` (zombie) | *(none)* | dying is a **flag**, not a type - see below |
| *(none)* | | 74 | `decorative_sprite_update` (intro screens) |

**Dying enemies are marked differently, and this is the only structural divergence in
the dispatch.** The port *rewrites the type*: `e_them_gozombie` sets `n = 0x47`, so the
dispatcher routes the corpse to `e_them_z_action`. We set a **flag**: `kill_enemy`
(`0x4D87C`) does `move.b #-0x1,(0x49,A0)` — `bDying = 0xFF` — and **never touches
`wType`**; `enemy_ai_update` branches on it at entry (`tst.b (0x49,A0)` @ `0x4D4F4`).
The constant `0x47` appears **nowhere in the program** as an immediate (program-wide
search, validated against a control). So on the ST, type 71 (= `0x47`) is an ordinary
`scripted_trap_update` entry with no special meaning.

## Where the two agree

Each row is **two independent reversals of two different builds arriving at the same
value** — strong evidence about the game's design rather than about either reading.

| Fact | Port | Ours |
|---|---|---|
| Placement table size | `map_marks[523]`, measured | `PlacementRecord[523]` @ `0x481E4`, reconciled to 476 records + 47 terminators |
| Room count | 47 submaps | 47 rooms |
| Tile attribute bits | `VERT 0x80, SOLID 0x40, SPAD 0x20, WAYUP 0x10, FGND 0x08, LETHAL 0x04, CLIMB 0x02, ? 0x01` | ladder-top 0x80, solid 0x40, bounce 0x20, one-way 0x10, bg-B 0x08, lethal 0x04, ladder 0x02, bg-A 0x01 — **all eight identical** |
| Bit 0x01 and 0x08 collected but never tested | `MAP_EFLG_01` unnamed; `FGND` used only by the blitter | "`0x01`/`0x08` are never tested" |
| Blocked mask | `SOLID\|SPAD\|WAYUP` (+`VERT` when falling) | `& 0xD0` |
| Trigger source bits | RICK 0x80, STOP 0x40, BULLET 0x20, BOMB 0x10, ONCE 0x01 | player-touch 0x80, stick jab 0x40, bullet 0x20, explosion 0x10, one-shot 0x01 — **identical** |
| Enemy spawn pools | type < 0x10 → slots 9,10,11; type ≥ 0x10 → slots 4..8 | identical, including the exclusive upper bound at slot 12 |
| Spawn dedup | `ent_creat2` refuses if the same `mark` is already live in 9..B | dedup by `placement_record_ptr` |
| Placement X/Y packing | `x = xy & 0xF8`; `y = ((xy & 7) + band) << 3` | `X = value & 0xF8`; `Y = (band + (value & 7)) × 8` |
| Trigger-box byte split | `trig_x = lt & 0xF8`, latency from `lt & 7` | `&0xF8` → patrol range at +0x30, `&7` → `bAiCooldown` |
| Jump impulse | `offsy = -0x0580` | `nVelY = -0x580` |
| Player gravity / terminal | `+0x0080`, clamp `0x0800` | `+0x80`, clamp `0x800` |
| Resting velocity | `offsy = 0x0100` | `nVelY = 0x100` |
| Super-pad rebound | `offsy = 0x00FE - offsy` | `nVelY = 0xFE - nVelY` — **the odd `0xFE` matches exactly** |
| Super-pad with UP held | `offsy = 0xF800` | `nVelY = -0x800` |
| Ground alignment | `y = (y & 0xF8) \| 0x03` | the `\|3` alignment nudge |
| Walk / climb speed | 2 px/frame | 2 px/frame |
| Bullet speed | ±8 px/frame | ±8 px/frame (`kb/algo-player.md` §6) |
| Bullet probe Y | `yc = y + 6 + 5` | `bullet_point_y = nPosY + 11` |
| Bullet leading edge, facing right | `bullet.x + 0x18` | `bullet_point_x = nPosX + 1 + 0x17` |
| Marks sorted by row, `0xFF` terminator | `ent_actvis` scan | per-room lists with an `0x00FF` sentinel |
| **Dynamite spawn offset** | `GFXST`: `x += 4; y += 5` | `nPosX = x + 4` (clamped 0xE8), `nPosY = y + 5` |
| **Dynamite detonate offset** | `x -= 4; y -= 5` | `nPosX -= 4; nPosY -= 5` |
| **Explosion centre** | `xc = x + 0x0C`, `yc = y + 0x0A` | `explosion_x = nPosX + 0x0C`, `explosion_y = nPosY + 0x0A` |
| Kill score | `env_score += 50` | `add_score(0x50)` BCD = 50 |
| Treasure score | `env_score += 500` | `add_score(0x500)` BCD = 500 |
| Super-bonus initial value | `e_sbonus_bonus = 2000` | `timer_bcd_value = 0x2000` BCD = 2000 |
| Player corpse X drift | `±3`, away from the nearer edge | `nDirection = 3`, negated when `nPosX >= 0x80` |
| Room-transition row window | `t = (y>>3) + frow - rowout; t < 3` | `D1 = worldrow - waypoint.wRow; 0 <= D1 <= 2` |
| Scroll trigger, downward view | `y >= 0xCC` | `player.nPosY >= 0xCC` (`main_init_and_loop`, `0x4DD0E`) |
| Submap exit, right | `x >= 0xE8` | `player.nPosX >= 0xE8` (`main_init_and_loop`) |
| Player hitbox, vertical | `y+[8 if crawling] .. y+0x14`, crouch offset cancelled on the low edge | identical, including the cancel (`entity_overlaps_player`) |
| Gameplay tile banks | `bank = (page==1) ? 2 : 1`, bank 0 = font/HUD; attributes selected by the same `page` | two gameplay banks; "the two tile banks switch graphics **and** attributes together" |

The dynamite `+4/+5` at spawn and `-4/-5` at detonation is the third
nobody-guesses-it-twice constant, and it settles something the port could only guess at:
its author wrote the offset as a `GFXST` fudge to "fix" ST sprite centring
(`e_bomb.c:74-79`). It is not a fudge — **the ST original does exactly this**, in both
directions, and the port reproduced the original's behaviour while believing it was
compensating for it.

The super-pad `0xFE` and the `-0x580` jump are the two strongest single data points: both
are arbitrary constants that no one would arrive at independently by guessing.

## Where the two differ

Every entry is a specific, measured difference. Our side is read directly from
instruction encodings unless noted; the port's from its C source.

### Settled — checked against the PC code segment

`kb/ibmpc_cs.bin` makes the port's side directly checkable. Where a row says *PC*, the
value was located in that binary; where it says the ST value is absent, the **same
encoding pattern** that found the PC value failed to find ours, which makes the negative
meaningful rather than a failed query.

#### Data-model differences already settled without the PC binary

| Quantity | Port | Ours | Resolution |
|---|---|---|---|
| Object-type table size | `ent_entdata[74]` = types 0-73 | `object_type_defs[75]` = types 0-74 | **Agree.** The extra entry is type 74, the intro-screen decorative sprite, which the port has no equivalent for |
| Kill score | `+50` | `add_score(0x50)` = 50 | **Agree** |
| Gameplay tile banks | `(page==1) ? 2 : 1` of 3 | two gameplay banks, graphics and attributes on one selector | **Agree** |
| Sprite frame count | 213 | 212 occupied slots | **Agree to within one trailing blank.** Ours previously read 185 - our defect, fixed |
| Room/submap connector count | **106** + 47 terminators = **153 records**, matching its own `MAP_NBR_CONNECT` `0x99` | **106** + 47 = **153** | **Agree — exactly.** All 47 lists match, list 17 included. *(Recorded as a port defect 2026-08-30; **retracted 2026-09-04** — the apparent 154th record was a commented-out line the author had already removed, miscounted by a regex that matched braces inside comments. See `../../PLAN.md` T10.)* |
| Entity trigger-sound table | 10 slots declared, 9 loaded, indexed `- 0x14` | ten consecutive values `0x13`-`0x1C` | **Port right on the count, wrong on the base** - `- 0x14` yields `-1` for the `0x13` entity |

#### Genuine PC-vs-ST differences — the port read its build correctly

In every row below the PC binary carries the port's value and **not** ours.

| Quantity | PC (verified in `ibmpc_cs.bin`) | ST (ours) |
|---|---|---|
| Stick-jab stun | `MOV byte[SI+0x2E],0x14` = **20** @ `0x237E`, `0x28D6` | `0x19` = **25** @ `0x4D574` |
| Spawn latency seed | `AND DL,7` then **five** `ADD AL,AL` = **x32**, `MOV [SI+0x2E],AL` @ `0x21A5`-`0x21B4` | **x25**, `mulu.w #0x19` @ `0x497FE` |
| Dying-entity gravity | `ADD AX,0x0080` = **+0x80** @ `0x23DF`, `0x2547`, `0x2A49`; **`+0xC4` occurs nowhere** | **+0xC4**, no clamp @ `0x4D532` |
| Death launch velocity | `MOV word[SI+0x2C],0xFC00` = **-0x400** @ `0x24C8` | **-0x300** |
| Enemy corpse drift | clamp to `0` / `0xE8` @ `0x2563`/`0x2570` *(⚠️ the `ADD AL,2` / `CMP AL,0xE8` @ `0x1912` originally cited here was **misattributed** — corrected 2026-09-02, that site is Rick's own right-edge submap test inside `e_rick`'s movement code, which calls `u_envtest` at `0x191E`)* | `dir==0 -> nPosX-1`, else **`nPosY+1`** @ `0x4D4FC`-`0x4D50A` |
| Ladder-exit upward velocity | `MOV [0x7D70],0xFD00` = **-0x300** @ `0x1953`; **`-0x200` occurs nowhere** | **-0x200** |
| Super-bonus tick divider | `MOV byte[0x7D95],0x1E` = **30** @ `0x22EE` | `0x19` = **25** @ `0x4BE3C`, `0x4BE84` |
| Dynamite fuse | `MOV byte[0x7D81],0x2D` = **45-frame counter** @ `0x17F6` | **table-driven**: 17 fuse frames + 10 explosion frames |
| Player hitbox, horizontal | `ADD AL,0x11` @ `0x12BF` | `x+5 .. x+0x12` - one pixel further right |
| Scroll trigger, low threshold | `CMP AL,0x60` @ `0x018B`; **no `0x5F` compare exists** | `<= 0x5F` |
| Player trigger-box probe X | `ADD AL,0x0C` @ `0x1536`, `0x1A16`, `0x1A9C`; **no `ADD AL,0x0B`** | `nPosX + 0x0B` @ `0x4D19A` |
| Bomb blast box | x `[-4, +0x20]` with the high edge **clamped to `0xFF`**, y `[-4, +0x1D]` — `e_bomb_hit` @ **`0x134B`**: `MOV AL,[0x7EE0]` / `MOV AH,AL` / `SUB AL,4` (clamp 0) / `ADD AH,0x20` (clamp `0xFF`), then `MOV AX,[0x7EE2]` / `SUB AX,4` (clamp 0) / `ADD BX,0x1D` | x `[-4, +0x1B]`, y `[-4, +0x18]`, **no clamp** |
| Submap re-entry X | `0xE2` prev / `0x04` next — `MOV word[SI+2],0x00E2` @ `0x19B9`, `MOV word[SI+2],0x0004` @ `0x19C9` | `0x02` enter-left / `0xE6` enter-right @ `algo-level.md` reposition |
| Bullet vs. moving block | **passes through** — the terrain test @ `0x1115` is tile-only (`AND AL,0x40 / RET`) | **blocked** — `0x4CCFC` also tests `sprite_list[0]` (`tst.w (0x4A702)`, then `0x4A706`/`0x4A712`, `0x4A708`/`0x4A714`) |
| Bullet out-of-range test | explicit: `x < 0` (byte underflow @ `0x1A0E`) or `x >= 0xE8` (@ `0x1A3A`) | **none** — `0x4CA5A` relies on the map border being `SOLID` |
| Point-in-entity box, X lower | **exclusive** — `CMP AL,BL`/`JNC` @ `0x131C` | **inclusive** — `cmp.w D1w,D0w`/`bgt` @ `0x4CC5C` |
| Point-in-entity box, extents | `ent.x + w` / `ent.y + h` | **`ent.x + w - 1` / `ent.y + h - 1`** — `subi.w #0x1` @ `0x4CC60`, `0x4CC78` |
| Trigger box, lower edge | **exclusive** — `CMP AL,BL` / `JNC` @ `0x13F2` requires `x > trig_x` | **inclusive** — `cmp.w (0x3c,A0),D0w` / `blt` @ `0x4D98A` requires `x >= XMin` |
| Trigger box, right-edge clamp | **clamped to `0xFF`** — `JNC` / `MOV AH,0xFF` @ `0x141C` | **no clamp** — `XMax` is a precomputed word at `0x40`, unsaturated, and can exceed `0xFF` |
| Player hitbox, left edge | `e.x+e.w < x+5` — strict `<` (`ADD AH,[SI+0x0E]` / `CMP AH,AL` / `JC` @ `0x12D0`) | `x+5 >= e.x+e.w` — `bge` @ `0x4D9D4`, one pixel tighter |
| Vertical despawn bound | **`0x140`** — `CMP AX,0x140` @ `0x10E3`, `0x2742`; no `0x142` compare exists in the segment | **`0x142`** — `cmp.w #0x142,D2w` @ `0x4B0C8` (`render_sprites`) and `0x4D352` (`scripted_trap_update`) |
| Dynamite kill score | **50** — one `CALL 0x0292` in `e_them_gozombie` @ `0x24D6`; all four score-add sites in the segment accounted for and none is a second add on the explosion path | **100** — `add_score(0x50)` @ `0x4D54E` on the `explosion_overlaps_entity` path *plus* `kill_enemy`'s own `0x50` @ `0x4D892` |
| Placement bit that suppresses the spawn Y `+3` nudge | `TEST byte[DI+2],0x2` / `JNZ` skips `ADD DX,0x3` @ `0x212D`-`0x2136` in `ent_actvis` - bit **`0x02`** | bit **`0x04`** - `btst.b #0x2,(0x3,A0)` @ `0x497B8` |
| Bullet probe points | **two**: a stored **centre** `x + 0x0C` at `[0x7D7E]` (written `0x1A17`, read by trigger code at `0x2602`, `0x27FF`) *and* an inline **leading edge** `+0x18` in the enemy-hit path (`ADD BL,0x18` @ `0x233B`, `0x2899`) | **one**: leading edge only, read unmodified by both consumers |
| Type-2 ladder-grab masks | **both** masks present - `AND AL,7` @ `0x2A27` *and* `AND AL,0x0E` @ `0x2A81`, `0x2AAF` | **one rule** at both sites, byte-identical instructions @ `0x4D6B4`/`0x4D72C` |

#### Newly discovered, from the PC binary

| Quantity | PC | ST |
|---|---|---|
| Ceiling-bonk velocity | `MOV [0x7D70],0` - velocity **zeroed** @ `0x16AC` | `nVelY = 0x80` - starts falling immediately |

This one was never in the comparison: the port's `offsy = 0` on hitting the roof matches
the PC binary exactly, and differs from our ST reading. Rick therefore hangs a frame
longer under a ceiling on the PC than on the ST.

#### Newly confirmed agreements — all three sources concur

Found while adjudicating the above. Each is now attested by the PC binary, the port's C,
and our ST disassembly:

| Quantity | Value | PC site |
|---|---|---|
| Jump impulse | `-0x580` | `MOV [0x7D70],0xFA80` @ `0x181E` |
| Resting velocity | `0x100` | `0x15F1`, `0x16FC` |
| Living-player gravity | `+0x80` | `MOV DX,[0x7D70]; ADD DX,0x0080` @ `0x15FD` |
| Living-enemy gravity | `+0x80` | `0x23DF`, `0x2547`, `0x2A49` |
| Super-pad, UP held | `-0x800` | imm `0xF800` @ `0x16EB` |
| Super-pad rebound | `0xFE - offsy` | imm `0x00FE` @ `0x16F1`, `SUB` @ `0x16F5` |
| Mark/placement count | **523** | `MOV CX,0x20B` @ `0x0022` |
| Dead-mark bit | `0x80`, cleared with `AND ...,0x7F` | `0x0025` |

The super-pad pair is worth singling out: the arbitrary `0xFE` and the `-0x800`
UP-bounce now appear in **all three** independent sources.

### Still unadjudicated — **none**

All 17 measured differences are adjudicated. Every one was a **genuine PC-vs-ST
divergence**; not a single value turned out to be an error by the port.

The last two were closed on 2026-09-02 once the **`0x17E` address delta** was noticed
(below), which turns the port's `ASM nnnn` comments into usable addresses.

### Structural differences that are understood

**Placement flag bit `0x02` has two readers on the ST.** `spawn_level_entity`
(`btst.b #0x1,(0x3,A0)` @ `0x496B8`) routes the placement into `sprite_list[0]` - the
port's `ENT_FLG_STOPRICK`. `scripted_trap_update` (`0x4D204`) separately uses the same
bit, in the bullet-trigger branch only, to choose the spent bullet's disposal route
(`despawn_offscreen_entity` vs setting the erase-pending render bits). The bullet is
consumed either way - `clr.w (0x4A79A).l` @ `0x4D1FE` runs first. The port has no
equivalent of the render bits, so it models only the first reader.

**Slot 12 differs structurally.** On the ST it is a real entity slot holding the type-74
decorative sprite; the list terminator is a *separate* 14th `wType` word at `0x4AADE`
holding `FF FF`, and all three `sprite_list` walkers stop on that word alone. The port
collapses both roles into `ent_ents[ENT_ENTSNUM]`: scratch record for `u_envtest` and
terminator at once, with no type-74 sprite at all.

**The type-2 randomisers are unrelated.** Ours is `update_prng` (`0x49596`) - two
longwords, `exg / rol.l #3 / subq.w #7 / eor.w`, seeded to fixed constants - with two
callers (`main_init_and_loop` per frame, `enemy_ai_update` per decision) and one
consumer, `(0x495C7) & 3`: a mode-2 enemy turns on a **1-in-4** chance. The port's
ad-hoc byte mixer picks a *direction* 1-in-2. One design point agrees: both step a
global generator once per frame and consult it per decision.

**The tile-probe asymmetry is identical — now confirmed in the PC binary itself.**
`u_envtest` is `FUN_0000_11bc` in `ibmpc_cs.bin`, and it is startlingly close to ours:

| | PC (`0x11BC`) | ST (`probe_player_tile_collision`) |
|---|---|---|
| pre-index nudge | `ADD BL,0x4` | `x += 4` |
| row count | `MOV CX,2`, `TEST DX,4`, `INC CX` | `i = 1; if (!crawl) i++; if (y & 4) i++` |
| straddle test | `AND AL,0x7` / `JZ` | `(x & 7) != 0` |
| 3-wide stride | `ADD DI,0x1E` | `A1 += 0x1E` |
| 2-wide stride | `ADD DI,0x1F` | `A1 += 0x1F` |
| upper-row masks | outer `0x6D`, centre `0x6F` | `0x6F`, with `0x02`/`0x80` later cleared from the outer accumulator |
| foot-row masks | outer `0x7D`, centre **unmasked** | foot row unmasked, `D0 |= D1` |
| blocked test | `TEST byte[0x7D67],0x40` | `(D0 & 0xD0) != 0` |

Working out which of the eight attribute bits can reach the result across
{upper, foot} x {outer, centre} gives **agreement in all 32 cells** between PC, port and
ST: ladder-top only from the centre column of the foot row, one-way only from the foot
row, ladder only from the centre column. The two builds reach it by different masking
arithmetic — the PC bakes the exclusions into per-cell masks (`0x6D`/`0x6F`/`0x7D`), the
ST applies `0x6F` and then clears `0x80`/`0x02` from the outer accumulator — and land on
the identical result.

**The `sni` -> `sprbase` substitution is explained — and it is not a divergence.**
✅ **Solved 2026-09-04 (T9).** The port's `ents.c:266` does

```c
if ((flags & (TRIGBOMB|TRIGBULLET|TRIGSTOP|TRIGRICK)) == all four && e >= 0x09)
    ent.sprbase = (U8)(entdata.sni & 0x00ff);
```

and its author wrote "FIXME what is this? ... Why? What is the point?". The condition
**selects exactly one class of entity**, and both halves are deterministic:

- **`e >= 9` is not allocation luck.** `ent_actvis`'s allocator routes on the entity
  number: `mark.ent >= 0x10` -> `ent_creat1` -> slots **4-8**; `mark.ent < 0x10` ->
  `ent_creat2` -> slots **9-C**. So `e >= 9` **is** `mark.ent < 0x10`, i.e. an `e_them`
  walking enemy.
- **All four trigger bits is the natural encoding for a live enemy** — killable by touch,
  stick jab, bullet *and* explosion. It is not an arbitrary sentinel.

**Shipped data confirms it.** Of the **78** `PlacementRecord`s whose `bTriggerFlags`
satisfy `& 0xF0 == 0xF0`, **75** have type `< 0x10` and their types are exactly
`4, 5, 7, 8, 10, 11, 13, 14` — precisely the port's own `e_them` **type 1a** (`4,7,a,d`)
and **type 1b** (`5,8,b,e`). The remaining 3 are types 40/43, which are `>= 0x10` and so
route to slots 4-8 where the substitution is correctly skipped. *(The port's FIXME guesses
"type 1 and 2 e_them"; the data says **1a and 1b only** — no type-2 entry, `6/9/c/f`,
carries all four bits.)*

**Why the field is free, and what it really holds.** Reading `ent_entdata` for the
indices the substitution can reach (`< 0x10`) settles it — `sni` there is **not** a
movement-step index at all, it is a **second sprite number**:

| entdata idx | `spr` | `sni` | enemy bank |
|---|---|---|---|
| 4, 5, 6 | `0x2F` | `0x8E` | bank 0 |
| 7, 8, 9 | `0x37` | `0x7E` | bank 1 |
| 10, 11, 12 | `0x41` | `0x86` | bank 2 |
| 13, 14, 15 | `0x4B` | `0x86` | bank 3 |

`spr` (`0x2F`-`0x4B`) seeds `ent.sprite`, the frame shown immediately; `sni`
(`0x7E`-`0x8E`) becomes `sprbase`, the base of the walk-cycle formula
`sprite = sprbase + ent_sprseq[...]`. Two different sprite numbers are needed, and for
type-1 enemies — which move under AI, not along `ent_mvstep` scripted paths — the `sni`
field is dead, so the engine reuses it. Entries 0-3 (block/Rick/bullet/bomb) have
`spr = sni = 0`.

That also accounts for the artifact the port's author noticed: `ent.sprite` keeps its
`spr`-derived value until the handler recomputes it from the new `sprbase`, so a
spawned-falling enemy visibly changes sprite on landing.

**Why our ST build has none of it.** Verified by disassembly: `init_entity_from_placement`
(`0x49742`) contains **no** all-four-bits test and **no** slot test, and the only three
`andi.b #0xF0` sites in the whole ST code region (`0x4C280`, `0x4D6C2`, `0x4D73E`) are the
X-snap `(x & 0xF0) | 0x04`, not flag tests. ST entity offset `0x20` is `wScreen_offset_b`,
not a sprite base. The reason is structural: the ST `ObjectTypeDef` is **16 bytes carrying
real pointers** (`anim_frame_table` at `+6`, `movement_path_table` at `+0xA`) and the
spawn seeds `anim_frame_table` (`0x32`) and `gfx_data` (`0x22`) directly, whereas the PC's
`entdata_t` is **8 packed bytes** of sprite *numbers*. With no "base + offset" sprite
formula there is no second base to store and nothing to overload.

**So this was never a behavioural divergence** — it is one consequence of two different
sprite-referencing models, and both builds are internally consistent.

**One latent difference, unreachable in shipped data.** The PC stores only the **low
byte** (`MOV [SI+0x20],CL` @ `0x2198`), leaving `sprbase`'s high byte as `spr`'s; the port
assigns the whole `U16`, zeroing it. They differ only if some `spr` exceeds `0xFF` — and
across all 74 `ent_entdata` entries the maximum `spr` is `0x0080`. Behaviourally
identical.

## What the port cannot help with

- **Sound — true until 2026-09-10, now inverted.** The port used to have no PSG
  emulation, no note tables, no sequencer; the WAVs were made by ear (`assets.md`,
  pre-T19 state). **T19 (`audio-sndh.md`) changed this**: `syssnd.c` now runs the
  actual sound-engine bytes lifted into `kb/algo-music.md`/`kb/assets/audio/
  rick_dangerous.sndh`, under real 68000 emulation. This is not independent
  corroboration, though — the port now *imports* `kb/`'s own extraction rather than
  offering a second, separately-derived reading of the original, so it still cannot
  cross-validate `algo-music.md`'s transcription the way the numeric/semantic
  comparisons elsewhere in this document do for gameplay logic.
- **Timing.** No VBlank, no interrupts, no 50 Hz tick (`divergences.md` §2).
- **Widths and signedness.** The port normalises everything into C types chosen for
  convenience; our `kb/byte-identity.md` exists because those properties matter.
- **The 68000 side of anything** — supervisor entry, double buffering, the blitter,
  relocation, the packed executable.

---

*This document records **state**: how the two reversals correspond, where they agree, and
where they differ. It contains no tasks and no progress log. Actions arising from it are
tracked as **T-items in `../../PLAN.md`**; the history of what each comparison pass found
is in `../byte-identity.md`.*
