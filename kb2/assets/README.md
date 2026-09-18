# Extracted game data

Produced by `../hnk.py` from the original disk. Nothing here is hand-edited.

```
disks/chaos43_noauto.st  --mcopy-->  hnk/RICK_0N.HNK   (8 files, as shipped)
        RICK_0N.HNK  --depack()-->      LSD! layer
        large ones   --depack_tree()--> levels/RICK_0N.bin
```

## Files

| Path | What |
|---|---|
| `RICK2.PRG` | The game executable as shipped (140202 bytes). |
| `hnk/RICK_0N.HNK` | The 8 original archives, byte-for-byte off the disk. |
| `levels/RICK_0N.bin` | Fully unpacked payload. |
| `levels/RICK_0N.stage1.bin` | Intermediate, for the double-packed files only. |

## Map → archive pair

Map 1 = `RICK_01`/`RICK_02`, map 2 = `03`/`04`, map 3 = `05`/`06`,
map 4 = `07`/`08` (from `g_level_descriptor_table` @ `$12dd4`). The odd file of
each pair is small and single-packed; the even one is large and double-packed.

| file | packed | stage 1 | stage 2 |
|---|---|---|---|
| RICK_01 | 68 | 1024 | — |
| RICK_02 | 27976 | 34816 | 73472 |
| RICK_03 | 166 | 1024 | — |
| RICK_04 | 32450 | 37888 | 73472 |
| RICK_05 | 76 | 512 | — |
| RICK_06 | 31982 | 37376 | 73472 |
| RICK_07 | 118 | 1024 | — |
| RICK_08 | 34178 | 39936 | 73472 |

**Every map's level image is exactly 73472 bytes (`0x11F00`)**, loaded at
`$53400` and therefore ending exactly at `$65300`, where the stage-1 buffer
begins. The two depackers are transcriptions of the game's own
(`$73f0`/`$7444` and `$1795c`); see the docstrings in `../hnk.py`.

## Level image layout (`levels/RICK_0N.bin`, loads at `$53400`)

| Image offset | Address | Contents |
|---|---|---|
| `0x00000` | `$53400` | Monster-descriptor table — ascending self-relative `u16` offsets, then per-type records (width, height, behaviour bits, both script-pointer pairs). |
| … | … | Spawn tables, submap-trigger tables, move/anim byte-code scripts, tile-ID data — **not yet individually located within the image.** |
| `0x11E00` | `$65200` | Tile-**attribute** table, 256 bytes, indexed by tile ID. Only 9 distinct values. |
| `0x11F00` | `$65300` | (end) — the tile-**ID** map array lives here, i.e. in the *next* buffer, not in the image. |

## Verification

The pipeline is verified four independent ways, all byte-exact:

1. `hnk/RICK_02.HNK` as extracted is **identical** to the bytes the game had
   loaded at `$65300` in `dump_hnkload_hit2.bin` (captured at the load
   breakpoint) — so the disk extraction is right.
2. `depack(RICK_01.HNK)` is **byte-identical** to live RAM at `$3EFC0` in
   `prg2-ram.bin` (1024 bytes).
3. `depack_tree(depack(RICK_02.HNK))` matches live RAM at `$53400` in
   `prg2-ram.bin` for **73462 of 73472 bytes**. All 10 differences are exactly
   bit `0x80`, spaced 4–9 bytes apart — the game setting the documented
   "already spawned" bit in spawn records during 20 s of attract-mode play.
   Live state, not decoder error; and it independently corroborates both the
   spawned-bit semantics and the 4-byte record grid.
4. The tile-attribute table at image offset `0x11E00` is **byte-identical** to
   live `$65200`.

Additionally every archive's stage-1 depack terminates with the output buffer
exactly filled and the input exactly consumed (`hnk.py` raises otherwise), and
all four level images come out at exactly the same size.
