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
| `sprites.png` | **212** × 32×21 | frame grid sweep | The complete frame grid, `0x2BFEE`–`0x3D62E`, stride `0x150`. **Cell index = sprite number** |
| `scenery_tiles.png` | 161 × 8×8 | `0x1BBFE` | Unreferenced scenery artwork (see below) |
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

### Sprite coverage — the complete grid (revised 2026-08-29)
Frames sit on **one regular grid**: stride `0x150`, every frame aligned to
**110 mod 0x150** — verified across all 124 table-referenced frames without exception.
Sweeping that grid from `0x2BFEE` to `0x3D62E` yields **212 slots**, of which exactly
one (slot **127**) is blank. The extractor renders every slot in grid order, blank
included, so **sheet cell N is sprite number N** — which is what makes the sheet usable
for cross-referencing `gfx_data` addresses.

> **Corrected 2026-08-29 — the previous "185 frames" figure was wrong twice over,**
> found while cross-checking against the xrick port (see `xrick/re/xref.md` -> *Where
> the two agree*, sprite frame count).
>
> 1. **The grid was cut short.** The sweep ended at `0x3BA9E` (slot 190). Slots
>    **191–211 are all non-empty** and hold genuine artwork; the first all-zero slot
>    is 212, and every slot from there to the banners at `0x40FEE` is blank. The true
>    end is `0x3D62E`. **21 frames were missing.**
> 2. **A density filter silently discarded real frames.** The extractor kept only
>    slots with `> 10%` non-zero bytes. Small sprites — the bullet and similar — carry
>    only ~17–30 non-zero bytes out of `0x150` and were thrown away. Seven were lost
>    inside the old range and twelve more would have been lost in the recovered range.
>    "185 non-empty" was therefore a filter artifact, not a count of real frames. The
>    filter is gone; emptiness is now tested as "no non-zero byte at all".
>
> The termination rule matters: **trim trailing blanks, do not stop at the first
> blank.** Slot 127 is a genuine interior gap, and stopping there truncates the sheet
> to 127 frames (observed while making this fix).
>
> Independent corroboration: the port declares `SPRITES_NBR_SPRITES = 0xD5 = 213`
> for its ST sprite array, against our 212 occupied slots — agreement to within the
> one trailing blank entry.

The earlier table-walk found only 124. The gap is not orphaned content: treasures
(`type*0x150 + 0x2F70E`) and the eight enemy sprite banks (`frame + bank`) are reached
by **computed** addresses that never exist as stored pointers, so neither a table walk
nor a program-wide pointer scan can see them — a pointer scan finds just 118. The grid
sweep sidesteps the question entirely and is the right method here.

All 212 were inspected and every one is genuine artwork: Rick in many poses, guards,
bats, boulders, barrels, dynamite, explosions, spikes, statues, the "SCORE GATE"
signs and a "500" score popup. Nothing is noise.

### The 5 KB after the font is scenery artwork — with no consumer
`0x1BBFE`–`0x1D01D` (5,152 bytes, immediately after the 95-glyph font and immediately
before tile bank 0) holds **161 cells in the standard 8×8 four-plane format**
depicting sky, clouds, pyramids/mountains, sand dunes, buildings and greenery. It is
plainly real artwork, rendered to `scenery_tiles.png`.

**Nothing in the program references it.** A scan for longwords pointing into the range
returns 10 hits, all round numbers (`0x1C000`, `0x1D000`) occurring inside sprite pixel
data — coincidence, not pointers. No code and no table addresses it. So it is either
cut content, or artwork consumed by the loader/intro stage that ran before the
snapshot was taken. Identified, but its use is unresolved.

---

## Not extracted

- ~~Music and sound~~ — ✅ **packaged as SNDH**, see below.
- ~~Per-room level maps~~ — ✅ **DONE**, see below.
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


---

## Room maps (`assets/rooms/`, produced by `render_rooms.py`)

All **47 rooms** rendered, named `roomNN_L<level>_<name>.png`. Pass `--overlay` for a
second set with entity spawn points marked (`_ents.png`, 462 placements).

Every room is **8 blocks = 256 px wide**. Height is the room's own block-index stream
(distance to the next room's `pTileMap`; the last runs to `block_defs`) **plus a
6-block-row / 192 px margin**.

That margin is not padding. `world_row_base` can reach the room's last transition row
— empirically `(own_rows − 1) × 4` — and the decoder then fills one more screenful,
which physically lives in the *following* stream but is visible to the player.
Rendering only a room's own stream cut a few tile rows off the bottom of every image.
Room 46 gets a reduced margin because its data ends at the block table.
Heights now range from 15 to 79 block-rows (480–2528 px); room 8 is the tallest.

**This validated the tilemap decode end-to-end** — the one major format that had never
been checked by rendering its output. Every room comes out as coherent level geometry,
and room 0 opens with five block-rows of solid rock exactly as `algo-level.md`
predicted from the raw byte stream. Both tile banks were checked in context (cave and
castle). The entity overlay is a further cross-check: markers land in open passages
rather than inside solid rock, and the type 22/23 escape-timer triggers sit at a
passage entrance and exit, which is where a timed challenge belongs.


---

## Audio — `assets/audio/rick_dangerous.sndh`

Built by [`build_sndh.py`](build_sndh.py). **29 subtunes — every entry in
`music_track_table`**, which covers music, sound effects and PCM samples alike, since
all three go through `play_music` with a track index.

This is not a re-synthesis. SNDH players (sc68, sndh-player, ZXTune) contain a 68000
emulator, so the file carries the game's **original replay code** and runs it verbatim
— including the digidrums, because `timer_a_music_isr` executes exactly as it does in
the game. No emulator was written and no audio was rendered.

### How it is built

| Step | Detail |
|---|---|
| Lift | Bytes `0x44C10`–`0x5324F` (58,944) — the whole sound subsystem in one window |
| Relocate | The replay code is position-dependent, so a hand-assembled stub copies the image back to `0x44C10` before calling anything |
| Init | interrupts off → copy → `reset_sound_chip` → **`silence_all_channels`** → **`setup_timer_a`** → `play_music(d0 = subtune − 1, d1 = 0)` |
| Play | `music_tick`, called at 50 Hz (`TC50`) |
| Exit | `reset_sound_chip` |

**`setup_timer_a` in `init` is what makes PCM work.** Samples are driven by the MFP
Timer-A interrupt, not the 50 Hz tick; omit that call and the tracked music still
plays while every digidrum is silent.

### Why the sound window is self-contained

An audit of every global the engine touches: code `0x44C10`–`0x45720`, state and
tables `0x44F08`–`0x46B66`, song data in `0x45720`–`0x48F15`, samples at `0x4DF86` /
`0x4FCF2` / `0x50DA8`. Nothing below `0x44C10`, nothing in the graphics blob, no calls
into game code. That containment is what makes the lift possible at all.

### Track map

Recovered by scanning every `jsr play_music` call site for the literal track number
loaded into `D0` beforehand, then attributing it to the enclosing function. Subtune =
track + 1 (SNDH subtunes are 1-based).

| Subtune | Track | Type | Triggered by | Sound |
|---|---|---|---|---|
| 9 | 8 | **PCM** `0x4DF86` | `player_controller` (fire path, after decrementing `bBullets`) | **gunshot** — *intact* |
| 10 | 9 | 1 | `player_controller` (fire path when `bBullets == 0`); `player_dynamite_update` fuse | out-of-ammo click / fuse tick |
| 11 | 10 | **PCM** `0x4FCF2` | `player_dynamite_update`; `destructible_pickup_update` | **explosion** — *runs past the capture* |
| 12 | 11 | 1 | `player_controller` | — |
| 13, 14 | 12, 13 | 1 | `player_select_anim_frame` | footstep / climb cues |
| 15, 16 | 14, 15 | 1 | `player_controller` | jump / land cues |
| 17 | 16 | 1 | `destructible_pickup_update` | crate collected (refill) |
| 18 | 17 | 1 | `treasure_pickup_update` | treasure pickup |
| 19 | 18 | 1 | `effect_start_escape_timer` | escape-timer music |
| **20** | **19** | **PCM** `0x50DA8` | **`kill_player`** and `kill_enemy` | **the death "waaaaa"** — *entirely uncaptured* |

❌ **Corrected 2026-09-07.** The line that stood here — *"Remaining subtunes (1–8, 21–29)
have no literal call site"* — is **wrong for subtunes 6, 7 and 8**. The original scan
matched only `move.w #N,D0` (`30 3c 00 NN`) and so missed the sites that load a small
track number with **`moveq`** (`70 NN`). Re-scanned across both encodings, the 25
`jsr play_music` sites are:

- **19** via `move.w #N,D0` → tracks 8–19, the table above;
- **4** via `moveq #N,D0` → **track 7** @ `0x4BEC2` (D1=0), **track 5** @ `0x4DC62` and
  `0x4DC94` (D1=1), **track 6** @ `0x4DDC6` (D1=0);
- **2** with `D0` loaded indirectly — `0x4D26C` and `0x4D2CC`, the entity trigger-sound
  path over the `0x13`–`0x1C` range.

Track 5's two sites are the ones already described further down (before `NEW_GAME` and
before the per-frame main loop). Subtunes 1–5 and 21–29 do remain without a literal call
site. This is the same encoding-blindness that hid the ST's `cmp.w` from a `cmpi.w`
scan — see `review-plan.md` standing checks.

Two details worth noting. `kill_player` passes `D1 = 1` and `kill_enemy` passes
`D1 = 0`, but `play_music`'s type-2 branch ignores `D1` entirely, so **Rick's death and
an enemy's death play the same digitised sample**. And all three PCM samples turn out
to be the game's three "punchy" effects — gunshot, explosion, death — which is exactly
what a 1989 ST title would spend its sample budget on.

✅ **All three samples are complete and confirmed audible** (rebuilt from
`atari_ram_1M.bin`, 2026-08-28). The death "waaaaa" — track 19, the one asset the
original 320 KB capture was missing entirely — is subtune 20, 5,150 bytes.

### Verification status

✅ **Fully verified by listening (2026-08-28).** Confirmed in a real SNDH player:
the relocating stub, the Timer-A/PCM path, the subtune mapping and **all three PCM
samples** work as designed. Two defects were found and fixed along the way — the
superimposed 'ding' (see below) and the incomplete samples (fixed by rebuilding from
the 1 MB capture). **The audio extraction is complete; nothing about it is outstanding.**

Structural checks, all still passing after the fix: every opcode encoding in the stub
matches an identical instruction found elsewhere in the same binary; the three branch
targets resolve correctly; the PC-relative `lea` lands exactly on the blob; the `dbf`
loop returns to the copy instruction; the copy count covers the blob exactly; the blob
is longword-aligned and its first bytes match the dump at `0x44C10`.

### Known limitations

1. ~~Two samples are incomplete~~ — ✅ **fixed 2026-08-28** by rebuilding from
   `atari_ram_1M.bin`. All three PCM samples are now complete: gunshot 7,530 bytes,
   explosion 4,277, **death 5,150**. Nothing is zero-filled.
2. ~~Copy-target collision~~ — did not occur in practice; the player loaded the file
   clear of `0x44C10`–`0x5324F`. Still a theoretical risk with a player that loads
   high.
3. ~~Header tag conventions~~ — the header as written is accepted.


### Playback bug found and fixed: the superimposed 'ding'

The first build had a stale note ringing under every subtune from **9 onward**
(reported from real playback; **fix confirmed working**).

⚠️ **Correction 2026-08-31 — the type-0 census here was wrong.** This previously read
"subtunes 1–8 are the only type-0 tracks". Reading `nTrack_type` out of all 29
`MusicTrackDescriptor` records at `0x44F08` gives **nine** type-0 tracks, not eight:
tracks `0`–`7` **and track `27` (0x1B)**, i.e. subtunes 1–8 *and 28*. Track 27 carries
`nParam_index = 8`, the ninth entry of the 9×6 song table at `0x46932` — which
independently confirms the nine-song count. Track 27 is not a literal at any call site;
it is reached through the entity trigger-sound range (`0x13`–`0x1C`). So the 9-onward
boundary is **not** a clean type-0/type-1 split, and subtune 28 should not have rung.

**Cause.** Only the type-0 path in `play_music` calls `init_music_playback`, which
zeroes the per-channel work area. Type-1 and type-2 tracks skip it — they rely on the
engine already being in a clean state.

✅ **That reliance is safe in the shipped game — verified 2026-08-31 (T16).** The
**first** `play_music` executed after boot is `play_music(5, 1)` at `0x4DC62`, inside
`main_init_and_loop`'s init sequence (`0x4DC2A`–`0x4DCCD`) — before `attract_mode_loop`,
before `NEW_GAME` (`0x4DC9E`) and before the per-frame main loop (`0x4DCCE`). Track 5 is
**type 0**, so `init_music_playback` runs and clears the channel work area before
anything else can play. All 22 type-1/type-2 call sites lie in gameplay code
(`0x4BE9A`–`0x4D89C`), reachable only from the main loop; `RESTART` (`0x4DC90`) re-plays
track 5 before re-entering attract mode. No type-1/2 track can start on a dirty engine.

The blob bug is therefore specific to the blob, which restores the snapshot's **live**
engine state: it was captured with track 5 (the title music) mid-play, `song_active =
0xFF00`, `play_state = 1`. `reset_sound_chip` clears the top-level flags but **not**
the three channel-active flags at `0x45454`/`0x4546E`/`0x45488`, so a leftover voice
kept sounding under the selected track.

**Fix.** `init` now calls **`silence_all_channels` (`0x45528`)** after
`reset_sound_chip` — the engine's own routine, which clears exactly those three flags
and zeroes the PSG volume registers.

**Also hardened.** The copy now runs with interrupts masked (`move.w #$2700,sr`,
restored afterwards). Once any sample track has played, Timer A is armed and its ISR
streams from `0x457C8` — an address *inside the blob being overwritten*. That race
would corrupt playback on every subtune switch even after the ding was fixed.

This is a good illustration of a general hazard when lifting code out of a RAM
snapshot: **the captured state is whatever the program happened to be doing**, not a
clean boot state, and any routine that assumes prior initialisation will misbehave.

---

## Rebuilt from the 1 MB dump — and a warning about that dump

`re/atari_ram_1M.bin` is a complete 1 MB capture, and the SNDH is now built from it,
so **all three PCM samples are complete** — including the death "waaaaa" (subtune 20,
5,150 bytes), which was entirely absent before.

> ⚠️ **`atari_ram_1M.bin` is NOT a drop-in replacement for `atari_ram.bin`.**
> The game is loaded at a **different base address** in that capture — everything is
> shifted by **−0x2054**. `reset_sound_chip` is at `0x42BBC` there, not `0x44C10`.
> Every address in `re/` and in the Ghidra project refers to **`atari_ram.bin`
> numbering**; do not mix them. To convert: `1M_address = doc_address − 0x2054`.

The two captures were verified to be the same program, not merely similar: with the
delta applied, the sound engine's code matches ~95% and its data ~88% byte-for-byte —
the residual differences being exactly the embedded absolute addresses, which is what
relocation looks like — and the overlapping sample bytes match **100%**.

`build_sndh.py` now handles this automatically. It locates `reset_sound_chip` by a
**position-independent anchor** (the routine opens by poking the PSG through absolute
hardware addresses, which do not relocate), derives the delta, and resolves every
function and table from it. It then self-checks by verifying all 29 track-table
entries have a valid type before proceeding, and prefers the 1 MB dump when present.
So the same script produces a correct SNDH from either capture.

### Sample extents (1 MB dump, contiguous block `0x4BF32`–`0x50172`)

| Subtune | Sound | Address | Length |
|---|---|---|---|
| 9 | gunshot | `0x4BF32` | 7,530 |
| 11 | explosion | `0x4DC9E` | 4,277 |
| 20 | **death "waaaaa"** | `0x4ED54` | 5,150 |
