# Assets — what data the port ships, in what form

The port carries the game's data as **C source**, not as ripped binary files. Every
table was transcribed into an array initialiser at some point in 1998–2005 and is
compiled into the executable. The only loose data files are the sounds.

## Data compiled into the executable

| File | Bytes | Contents | Built in `GFXST`? |
|---|---|---|---|
| `dat_maps.c` | 109 123 | `map_maps[5]`, `map_submaps[47]`, `map_connect[153]`, `map_bnums[8152]`, `map_blocks[256]`, `map_marks[523]`, `map_eflg_c[32]`, `maps_intros[5]` | yes (graphics-independent) |
| `dat_ents.c` | 22 389 | `ent_entdata[74]`, `ent_sprseq[136]`, `ent_mvstep[784]` | yes (graphics-independent) |
| `dat_screens.c` | 4 627 | `screen_imapsl`, `screen_imapsteps`, `screen_imapsofs`, `screen_imaptext`, HoF/title/gameover/paused/congrats tile strings | yes |
| `dat_tilesST.c` | 109 988 | `tiles_banks[3][256]` of `U32[8]`, 4 bpp | **yes** |
| `dat_spritesST.c` | 245 795 | `sprites_data[213]` of `U32[0x54]`, 4 bpp | **yes** |
| `dat_picsST.c` | 161 939 | `pic_haf`, `pic_congrats`, `pic_splash` — full-screen 4 bpp pictures | **yes** |
| `dat_tilesPC.c` | 107 201 | `tiles_banks[4][256]` of `U16[8]`, CGA 2 bpp | no |
| `dat_spritesPC.c` | 338 685 | `sprites_data[155]` of `{U16 mask, U16 pict}[4][0x15]` | no |
| `dat_picsPC.c` | 572 | stubs | no |
| `dat_snd.c` | 770 | legacy `sound_t*` declarations — see below | (compiled, unused) |
| `src/img_splash.e` | 352 696 | the xrick splash image, 8-bit indexed + palette | yes |
| `src/img_icon.e` | 6 337 | window icon | yes |
| `src/sdlcodes.e` | 7 660 | SDL keycode name table | yes |

The ST tile data carries a comment on each tile giving its original number
(`dat_tilesST.c:19` — `{ /* 0x11 */ ... }`), so bank contents are not in original tile
order; the comment is the mapping.

## Sound

⚠️ **Superseded 2026-09-10 (T19, `audio-sndh.md`).** `data/sounds/*.wav` is no longer
loaded by anything — `syssnd.c` now runs the real ST sound engine under 68000
emulation (`src/audio_engine/`, `src/dat_sndh_engine.c`). The 29 loose WAV files below
are unused legacy data, left in place (not deleted — no instruction to remove game
data assets, only the dead C/`.e` duplicates were). `sound_t` no longer wraps a WAV
buffer; see `algo-system.md`'s Sound section for the current design.

**Loose WAV files** in `data/sounds/` — 29 files, ~3.4 MB total, 8-bit unsigned mono at
22050 Hz. **Unused since T19** (below is what the pre-T19 port loaded).

| Group | Files |
|---|---|
| Music | `tune0`–`tune4` (one per map, from `map_maps[].tune`), `tune5` (title screen) |
| Effects | `bombshht, bonus, box, bullet, crawl, die, explode, gameover, jump, pad, sbonus1, sbonus2, stick, walk` |
| Entity triggers | `ent0`–`ent8` (nine; `WAV_ENTITY[]` was declared with ten slots, index 9 unfilled) |

**Legacy embedded PCM — deleted 2026-09-10 (T19).** Eleven `src/wav_*.e` files
(~430 KB of C initialisers: `wav_bomb, wav_bombshht, wav_bonus, wav_box, wav_bullet,
wav_ddding, wav_ding, wav_jump, wav_shht, wav_waa, wav_walk`) and `dat_snd.c` (which
re-declared six of `sounds.c`'s names under a different scheme — `WAV_WAA`, `WAV_TING`,
`WAV_DDDING`, `WAV_SHHT`, `WAV_BOMB` — only ever linking because they were C tentative
definitions) were confirmed unreferenced by grep and removed, along with their two
stale entries in the MSVC project files. **They no longer exist in the tree** — this
entry is a record of what was there, not a live description.

## Where the assets came from

The port's own README says the game was reverse-engineered from "the PC and Atari
versions". The ST graphics tables must therefore have been ripped from an Atari ST
build, and the sound WAVs were recorded or synthesised rather than extracted as
instrument data — there is no PSG register data, no note tables, and no sequencer
anywhere in the tree. The author's comment about the entity-trigger sounds ("I dont have
the table yet, must rip the data off the game", `e_them.c:691-696`) confirms that the
sound side was reconstructed by ear, not decoded.

**Consequence:** on the audio side the port has *nothing* to compare against our
`kb/algo-music.md` and the extracted SNDH. Our RE is strictly ahead there. The
comparison value of the port is in geometry, logic and level data — not sound.

## What we can compare directly, byte for byte

These four tables are graphics-independent and should correspond to regions we have
already located in `atari_ram.bin`:

| Port table | Records | Our counterpart (`../`) |
|---|---|---|
| `map_marks[523]` | 523 × 5 bytes | `placement_table` = `PlacementRecord[523]` at `0x481E4` (6 bytes each) |
| `ent_entdata[74]` | 74 × 7 fields | `object_type_defs` = `ObjectTypeDef[75]` at `0x47D34` (16 bytes each) |
| `map_submaps[47]` | 47 × 4 words | the 47 rooms |
| `map_eflg_c[32]` | 2 × 16 bytes RLE | the tile-attribute table, two banks |

The record *layouts* differ (the port normalised everything into C structs), so the
comparison must be **field-by-field after decode**, not a memcmp. See `xref.md`.
