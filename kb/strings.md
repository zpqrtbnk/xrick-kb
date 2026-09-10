# Rick Dangerous — Text and String Data

Extracted 2026-08-28. Every in-game string in the snapshot, with its address, raw
bytes, and decoded form.

> **Background:** earlier passes recorded "the game's text is not ASCII, don't run
> string search". **That was wrong.** The text *is* plain ASCII; it is simply
> **`0xFF`-terminated instead of NUL-terminated**, and Ghidra's ASCII Strings analyzer
> had *Require Null Termination* enabled, so it reported zero strings. The advice has
> been retracted in `README.md` and `rick.md`.

---

## Character encoding

The font at `0x1B01E` is indexed by the **raw character byte** (32 bytes per glyph:
8 rows × 4 bitplanes). Letters sit at their normal ASCII codes, but four punctuation
marks are remapped. **These mappings are confirmed by rendering the actual glyphs**,
not inferred from context:

| Byte | ASCII | Renders as | Evidence |
|---|---|---|---|
| `0x5E` | `^` | **space** (entirely blank glyph) | all 32 bytes zero; also the fill byte `draw_hud_count` uses for blanks |
| `0x5C` | `\` | **.** (full stop) | 3×2 block on rows 5–6 |
| `0x5B` | `[` | **,** (comma) | 2×2 block on rows 5–6 with a descender on row 7 |
| `0x5D` | `]` | **?** (question mark) | question-mark shape |
| `0x3C` | `<` | **·** (dot leader) | small dot, used as `<<<<` leader in the score table |

⚠️ **Digits are not ASCII.** Glyph `0x30` (`'0'`) renders as unrelated graphics. Score
digits are stored as **unpacked decimal values 0–9**, which index font glyphs 0–9
directly. Any reimplementation must not treat score bytes as ASCII characters.

✅ **Resolved 2026-08-29 by rendering the glyphs** (`hatari/glyphs_30_41.png`):

| Byte | Renders as | Role |
|---|---|---|
| `0x36` | **left arrow ◄** | RUBOUT / DELETE |
| `0x37` | **`E`** | first glyph of `END` — the code the grid returns |
| `0x3A` | **`N`** | second glyph of `END`, display only |
| `0x3B` | **`D`** | third glyph of `END`, display only |

The earlier claim that all four "appear only in the name-entry grid" was imprecise.
The **selection grid** at `0x48FA1` is 30 entries — `A`–`Z`, `0x5C` (`.`), `0x5E`
(space), `0x36`, `0x37` — so only `0x36` and `0x37` are selectable codes. `0x3A` and
`0x3B` live in the **display row** at `0x48F98`
(`5C 5E 5E 5E 36 37 3A 3B FF` = `.` ␣ ␣ ␣ ◄ E N D), which spells "END" across three
glyphs because the font has no multi-character cell.

---

## Level intro / story texts

Reached via `LevelStartInfo[i].pIntroText` (table at `0x4B522`, stride 20). Rendered by
`show_level_intro_screen` (`0x4B5F4`). Format: lines separated by **`0xFF`**, whole
text terminated by **`0xFE`**. An empty line (`0xFF` immediately) is a blank spacer row.

These occupy `0x4B8FE`–`0x4BE1F`, the region `find_code_gaps` had reported as an
unexplained gap. **That gap is fully explained now.**

### Level 0 — South America (`0x4B8FE`, 280 bytes)
The first line embeds four non-printable bytes (`01 09 04 05`) after the title —
banner glyph indices, consistent with `wIntroParam`.
```
     SOUTH AMERICA
RICK DANGEROUS CRASH LANDS HIS
 PLANE OVER THE AMAZON WHILE
 SEARCHING FOR THE LOST GOOLU
            TRIBE.

 BUT, BY A TERRIBLE TWIST OF
FATE HE LANDS IN THE MIDDLE OF
   A BUNCH OF WILD GOOLUS.

  CAN RICK ESCAPE THESE ANGRY
   AMAZONIAN ANTAGONISTS?
```

### Level 1 — Egypt (`0x4BA16`, 270 bytes)
```
    EGYPT, SOMETIME LATER
RICK HEADS FOR THE PYRAMIDS AT
    THE REQUEST OF LONDON.

HE IS TO RECOVER THE JEWEL OF
ANKHEL THAT HAS BEEN STOLEN BY
FANATICS WHO THREATEN TO SMASH
 IT, IF A RANSOM IS NOT PAID.

CAN RICK SAVE THE GEM, OR WILL
HE JUST GET A BROKEN ANKHEL ?
```

### Level 2 — Schwarzendumpf Castle (`0x4BB24`, 260 bytes)
```
    EUROPE, LATER THAT WEEK
  RICK RECEIVES A COMMUNIQUE
  FROM BRITISH INTELLIGENCE
  ASKING HIM TO RESCUE ALLIED
 PRISONERS FROM THE NOTORIOUS
    SCHWARZENDUMPF CASTLE.

  RICK ACCEPTS THE MISSION.

   BUT CAN HE LIBERATE THE
 CRUELLY CAPTURED COMMANDOS ?
```

### Level 3 — Missile Base (`0x4BC28`, 235 bytes)
```
      EUROPE, EVEN LATER
RICK LEARNS FROM THE PRISONERS
 THAT THE ENEMY ARE TO LAUNCH
AN ATTACK ON LONDON FROM THEIR
     SECRET MISSILE BASE.

WITHOUT HESITATION, HE DECIDES
   TO INFILTRATE THE BASE.

CAN RICK SAVE LONDON IN TIME ?
```

### Ending (`0x4BD14`, 259 bytes) — **new finding**
A **fifth** intro-text pointer follows the four level entries at `0x4B572`. It is not a
fifth level: it is the **game-completion text**, ending on a sequel tease.
```
   LONDON, MUCH, MUCH LATER
 RICK RETURNS TO A TRIUMPHANT
  WELCOME HOME HAVING HELPED
    SECURE ALLIED VICTORY.

BUT, MEANWHILE, IN SPACE, THE
   MASSED STARSHIPS OF THE
   BARFIAN EMPIRE ARE POISED
     TO INVADE THE EARTH.

 WHAT WILL RICK DO NEXT ... ?
```
This means the `LevelStartInfo`-adjacent pointer array has **5** entries even though
only 4 are levels — worth accounting for in any reimplementation of the level flow.

---

## Level names (`0x49859`, stride `0x1A` = 26 bytes)

Fixed-width, space-padded to 24 characters, `0xFF`-terminated.

| # | Address | Text |
|---|---|---|
| 0 | `0x49859` | `   SOUTH AMERICA        ` |
| 1 | `0x49873` | `   EGYPT                ` |
| 2 | `0x4988D` | `   SCHWARZENDUMPF CASTLE` |
| 3 | `0x498A7` | `   MISSILE BASE         ` |

---

## Default high-score table (`0x48E26`, 8 × 30 bytes)

Record layout confirmed: score digits are **unpacked decimal, one digit per byte** —
a word of 2 digits at `+2` and a long of 4 digits at `+4` (6 digits total), 10 bytes of
dot-leader decoration at `+8`, and the 10-byte name at `+0x12`.

| # | Address | Score | Name |
|---|---|---|---|
| 0 | `0x48E26` | 008000 | `SIMES` |
| 1 | `0x48E44` | 007000 | `JAYNE` |
| 2 | `0x48E62` | 006000 | `DANGERSTU` |
| 3 | `0x48E80` | 005000 | `KEN` |
| 4 | `0x48E9E` | 004000 | `ROB N BOB` |
| 5 | `0x48EBC` | 003000 | `TELLY` |
| 6 | `0x48EDA` | 002000 | `NOBBY` |
| 7 | `0x48EF8` | 001000 | `JEZEBEL` |

The decoration field is `   ····   ` in every record (`^^^<<<<^^^`), i.e. a dot leader
between the score and the name.

---

## Name-entry screen (`0x48F4C`+)

Prompt at `0x48F4C`: `PLEASE ENTER YOUR NAME`

The selectable character grid is five rows of 6 cells (letters separated by blanks),
drawn by `draw_name_entry_cursor` (`0x491E8`):

| Address | Raw | Decoded |
|---|---|---|
| `0x48F64` | `A^B^C^D^E^F` | `A B C D E F` |
| `0x48F70` | `G^H^I^J^K^L` | `G H I J K L` |
| `0x48F7C` | `M^N^O^P^Q^R` | `M N O P Q R` |
| `0x48F88` | `S^T^U^V^W^X` | `S T U V W X` |
| `0x48F94` | `Y^Z^\^^^67:;` | `Y Z .` + 4 special glyphs |

✅ The trailing `0x36 0x37 0x3A 0x3B` are **confirmed** (2026-08-29): `0x36` is a
left arrow (RUBOUT/DELETE) and `0x37`/`0x3A`/`0x3B` are `E`,`N`,`D` spelling "END".
This is the **display row** at `0x48F98`; the *selection* grid at `0x48FA1` holds only
`0x36` and `0x37` as returnable codes.

---

## Miscellaneous

| Address | Text | Notes |
|---|---|---|
| `0x4DE22` | `GAME` | game-over banner, drawn by `main_init_and_loop`'s game-over path |
| `0x4DE27` | `OVER` | second line |
| `0x00FD2` | `\AUTO\` | TOS boot-path remnant, **not game data** (outside the program image) |
| `0x1E1EA` | `Z$~~` | 4-byte coincidence inside the graphics blob — **not a string** |

---

## Reproducing this extraction

`0xFF`-terminated printable runs of ≥4 characters, over `kb/atari_ram.bin`:

```python
import re
D = open("atari_ram.bin", "rb").read()
for m in re.finditer(rb"[ -~]{4,}\xff", D):
    print(f"0x{m.start():05X}  {m.group()[:-1].decode('ascii')}")
```

66 runs total; the two noted above are false positives, leaving **64 genuine strings**.
Decode with `^`→space, `\`→`.`, `[`→`,`, `]`→`?`.
