# Rick Dangerous 2 — game flow (`game_main` `$10992` and everything it calls), transcribed

Read from the 68000 disassembly in Ghidra on 2026-09-20 (`game_main` `$10992`–`$10c22`, `$178dc`, `$17a46`, `$1771c`, `$17760`, `$123a0`,
`$123b0`, `$142a0`, `$14300`, `$14458`, `$12f08`, `$1300e`, `$13060`, `$14362`, `$14434`, `$18abe`, `$18bb2`, `$149c2`, `$15826`,
`$157b4`/`$157be`/`$157f4`, `$17782`, `$17810`, `$1789a`, `$17bda`, `$17bf4`, `$17c06`, `$17c86`, `$17e40`, `$17f22`, `$15bc0` and its
helpers, `$18782`, `$170b6`–`$17116`, `$191e6`, `$19216`, ISR `$1902e`). Only what those routines do is written here; addresses are RAM
addresses. No decompilation to C; names of things are descriptive labels, not names from the code.
Companion documents: `algo-player.md` (Rick), `algo-actors.md` (6-slot actor table + trigger boxes), `algo-objects.md` (4-slot object table),
`level-tables.md` (image tables), `graphics.md`, `sound-ref.md`.

## 1. Variables

| address | value |
|---|---|
| `[$1239c]` | map being played, 1–5 (word) |
| `[$1239e]` | map whose data is currently loaded (`$123b0` reloads only when `[$1239c] ≠ [$1239e]`) |
| `[$17994]` | map chosen on the picker (1 = start of a normal game); `[$17992]` = number of unlocked picker rows (initial 4); `[$1798e]` = cheat flag (initial 0); `[$17990]` = "long/short game" (initial 0) |
| `[$3efb6]` | attract-mode ("demo") flag, −1 while a demo recording is played; `[$3efb8]` = demo stream finished (`read_player_input` `$141cc`, `$14222` re-arms it: `[$3efb8]=0`, read pointer `[$3efba]=$3efc0`, bytes `$3efbe/$3efbf = 0`) |
| `[$1a4fb]` | input byte (bit 7 fire, 0 up, 1 down, 2 left, 3 right — `algo-player.md`); `[$1a4fc]` = last key scancode (`1` = ESC, `$19` = P, `$1f` = S, all as tested by `game_main`) |
| `[$115e0]` | map-complete flag (set by the trigger scan `$14362`, `-1`); `[$115dc]` = "laser shot hit something this frame" flag (`algo-actors.md`); `[$12e2a]` = Rick dead flag (set `-1` by the death routine `$13a62`); `[$144c2]` = actor-group flag (§10) |
| `[$17710]` | lives; `[$1770e]` = lives HUD dirty; `[$176f4]` = laser ammo, `[$176f2]` dirty; `[$17702]` = bomb count, `[$17700]` dirty; `[$176f0]` = score dirty |
| `$176e4..$176e6` | score, 3 bytes packed BCD (6 digits); `$176e8..$176ed` = the 6 digits as separate bytes (for drawing) |
| `[$10b5c]` | word inside the code segment used as the "S key already handled" latch |
| `[$18ed8]` | vblanks per game frame (2 in the image; 1 during the 16-step screen slide) |
| `[$19232]` | vblank counter, incremented by the vblank ISR `$1902e` (which then calls the music player `$1a866`) |
| `[$1a5ce]` | id-remap flag toggled by the S key (`sound-ref.md` §3: when set, `play_sound` maps ids > 9 to id + `$29`) |
| `[$1aa08]` | music-playing flag (0 = no music running; `$178dc`, `$17c06`, `$17c86` test it) |

## 2. `game_main` skeleton

```
$10992  install: word $4e73 (rte) at $19044; load the MFP registers $fffa07/09/13/15/17/19/1f and the vectors $68,$70,$118,$134 from the table at $11606..$1161a (interrupts masked meanwhile);  clr.b [$1a4fb]
TITLE   $10a18  jsr $178dc                      # title / attract sequence (§3)
PICK    $10a1e  jsr $17a46                      # level picker (§4)
        $10a24  jsr $1771c                      # score := 0, lives := 6 (§7)
        $10a2a  jsr $123a0                      # [$1239c] := [$17994]; jsr $17760 (ammo/bombs := 6)
LOAD    $10a30  jsr $19388                      # clear both screen buffers ($19388 -> $1939e on [$18ede] and [$18eda])
        $10a36  jsr $123b0                      # load_map_if_changed (loader; kb2/xrick2-ref.md)
        $10a3c  jsr $17760                      # ammo := 6, bombs := 6 (dirty flags set)
        $10a42  [$115e0] := 0 ; jsr $19388 ; jsr $142a0     # level_start (§5)
FRAME   $10a54  [$115dc] := 0
        calls   $14594 spawn scan · $15bc0 actor-group handler · $14d48 actors · $150a2 objects · $15826 bonus timer · $13096 Rick ·
                $13e14 laser shot · $13e98 (bomb) ;  if [$115dc] ≠ 0: [$16902] := 0        # the shot is consumed
                $16658 scroll · $18dac · $18782 (background to screen) · $170b6 (sprites to screen) · $177a8 (HUD) ·
                $19216 (wait + page flip) · $191e6 (wait) · $14362 (exit-trigger scan)
        then the checks of §6.
```

Frame pacing: `$19216` waits until `[$19232] ≥ [$18ed8] − 1`, then `$19234` toggles bit 7 of the middle byte of both screen base pointers
(`[$18edc]`, `[$18ee0]`, i.e. double buffering; the new base is written to the video-base registers); `$191e6` then waits until the counter has
changed at least once and is ≥ `[$18ed8] − 1`, and clears it. With `[$18ed8] = 2`: the counter must reach 1 in `$19216`, then change again in
`$191e6` → **2 vblanks per game frame** (half the display refresh rate). The slide of §8 sets `[$18ed8] = 1` (1 vblank per step) and restores 2.

## 3. Title / attract sequence `$178dc`

```
[$17938] := (fire held on entry) ? -1 : 0
if [$1aa08] == 0: play_sound(3, 0)                 # $1a6aa, D0 = 3
draw title ($1793a)                                # $1919e (fade out), $1795c depacks the image stored at $31eb0 to [$18eda], $19134 (fade in)
if wait($17c86): return                            # carry set = fire pressed
hall of fame ($17e40) ; wait ; title ; wait ; hall of fame ; wait   # each wait returning early (carry) leaves the routine
[$3efb6] := -1                                     # nothing pressed -> start a demo
```

`wait` = `$17c86`: up to `$b0` (176) iterations of { `$17cd8`; `$191e6`; if `[$1aa08] == 0`: play_sound(0, 1); if fire is down: return carry **only if fire was not already
held at entry** (`[$17938]`), else clear `[$17938]` when fire is released }. Returns carry clear when the 176 frames elapse.
`$17cd8`: if the last key is scancode `$39` (space bar): fade out (`$1919e`), toggle the palette pointer `[$18ee2]` between `$18ee6` (the game palette, `graphics.md` §2) and
`$18f06`, fade in (`$19134`). The second palette, read from RAM: `0000 0000 0222 0222 0222 0333 0444 0555 0111 0222 0333 0444 0222 0333 0444 0666` (greys).
`$17e40` (hall of fame view): fade out, clear, `$194ce(1)`, temporarily subtract 1 from the first 10 bytes of every table entry's name field
(`$17d20 + 30·k`, 8 entries) to convert stored codes to glyph ids, draw the table at `$17dfe` via `$1925a`, fade in, restore the bytes (+1).

## 4. Level picker `$17a46`

```
[$17994] := 1 ; [$17990] := 0
if [$3efb6] (demo): [$17994] := [$1239e] ; return                  # the demo replays the already loaded map
if [$17992] == 0: return
$1a5d0 (stop sound) ; [$17b84] := (fire held ? -1 : 0) ; fade out ; clear ; $194ce(2)
draw the row records from $17996 + 8·(5 − [$17992]) ($1925a, D0 = 5, D1 = 6) ; $17b86 ; fade in
D2 := 1 (selected row), D1 := 7 (its screen row)
loop: draw the cursor string $17e9e (the single glyph $0f) at (col 5 (D0), row D1) ; 4× $191e6 ; if fire: (if [$17b84] == 0 → [$17994] := D2 ; return ; else repeat)
      if [$1798e] (cheat): left  → [$17990] := 0 ; right → [$17990] := -1 ; redraw $17b86
      [$17b84] := 0 ; erase the cursor with the string $17ea0 (a single space) ;
      up: D2 −= 1, D1 −= 3 (clamped to 1 / 7) ; down: D2 += 1, D1 += 3 (clamped to [$17992])
```

`[$17992]` is written only by `game_main` (`$10af2`, value 5). Picker records at `$17996` (read from RAM): five `(word 5, word row, long string pointer)` = rows 18, 15, 12, 9, 6 with
strings `$17a28`, `$17a10`, `$179f2`, `$179d4`, `$179c0`, then a `ffff` terminator. Strings are font glyph ids ending in `$ff`: `$179c0` = `01 20 20` "HYDE PARK, EARTH",
`$179d4` = `02 20 20` "THE ICE CAVERNS OF FREEZIA", `$179f2` = `03 20 20` "THE FORESTS OF VEGETALIA", `$17a10` = `04 20 20` "THE ATOMIC MUD MINES", `$17a28` = `05 20 20` "THE FAT GUY'S HEADQUARTERS"
(the leading id is a digit glyph 1–5, i.e. the map number). Drawing starts at record `5 − [$17992]`, so with `[$17992] = 4` rows 15, 12, 9, 6 = maps 4, 3, 2, 1
are shown, map 1 at the top; `D2` = selected entry counted from the top = the map number `[$17994]`.
`$17b86` shows a text only when `[$1798e] ≠ 0`, at column `$c`, row `$15`: `[$17990] = 0` → the string at `$17bb6` (`01 06 20 42 49 54 20 4c 4f 4e 47 20 47 41 4d 45 ff` = glyph ids 1, 6, space, "BIT LONG GAME"
→ "16 BIT LONG GAME"), `[$17990] ≠ 0` → `$17bc8` (`00 08 20 …SHORT GAME` → "08 BIT SHORT GAME"). **Effect of `[$17990]`:** it is read only by the trigger scan (`$143c0`): `[$17990] = 0` → a trigger record completes the map only when
`(byte0 & $90) == $90`; `[$17990] ≠ 0` → when `byte0 & $80`. `[$1798e]` is set by entering the name "POOKY" in the hall of fame (§10).

## 5. Level start `$142a0` / `$14300` / `$14458`

```
$142a0: [$144c2] := 0
        if !demo: play_sound([$1239c] + 3, 0)                    # music id per map: 4..8
        run_scene(0)                                             # $18186 with D0 = 0: the map's opening scene (decode_scenes.py)
        rec := word[$14250 + 4·([$1239c] − 1)] → 6 words  D0, D1, D2, D3, D4, D7
        $14300 ; $14222                                          # $14222 re-arms the demo reader when demo
$14300: $1704c: for every record of the 17-record chain $167a2 … (objects ×4, laser shot, Rick, debris ×4, bomb, actors ×6; the word at $16d7a is the -1
        sentinel, read from the RAM dump) clear kind, +$16 long, +$1a, +$1c, +$1e long, +$22, +$10
        $12f08 (player reset, below)
        [$1695c] := D2 (Rick x) ; [$16960] := D3 (Rick y) ; [$1697e] := D4 ; [$12e18] := D5 (= 0) ; [$12e1a] := D6 (= 0) ; [$12e14] := D7
        $14458 (submap loader) ; $16474 (draw the map into the $68000 window) ; $16630 ; $157b4 (bonus timer off) ; $14542 (skip spawn records above the window)
        [$14592] := -1 ; $14594 (first spawn scan, forced) ; [$14592] := 0
$14458: [$16464] := D0 (submap index) ; hdr := $54c00 + 8·D0 ; [$1646a] := $56400 + w0 ; [$16466] := 0 ; [$16468] := w1·8 ;
        [$1435c] := $54c00 + w2 (trigger table) ; [$144c4] := $54c00 + w3 (spawn table) ; [$16462] := D1 (scroll y)
        then $1300e (checkpoint save) and $18516
```

**Start records** `$14250` = pointers to `$14264, $14270, $1427c, $14288, $14294`, 12 bytes = 6 words `(D0 submap, D1 scroll y, D2 Rick x, D3 Rick y, D4, D7)`:

| map | submap | scroll y | Rick x | Rick y | D4 | D7 |
|---|---|---|---|---|---|---|
| 1 | 0 | 0 | 0 | `$e3` | 0 | 0 |
| 2 | 0 | 0 | 0 | `$cb` | 0 | 0 |
| 3 | 1 | `$480` | 0 | `$ab` | 0 | 0 |
| 4 | 0 | 0 | 0 | `$cb` | 0 | 0 |
| 5 | 0 | `$300` | 0 | `$ab` | 0 | 0 |

(bytes read from RAM `$14264..$1429f`; the map-3/5 rows' submap/scroll come from words 0 and 1 of each record.)

**Player reset `$12f08`** (called by `$14300`): clears words `[$12e14 … $12e2e]` (14 words), `[$14360] := 0`, `[$1695a] := 1` (Rick record active),
`[$1696c] := 1`, `[$1696a]`, `[$1696e]`, `[$16962]`, `[$1697c]`, `[$1697e] := 0`, `[$12ef4] := 0` (melee flag), byte `[$12ef2] := 0`, bomb `[$16b12]`, `[$16b5e]`,
laser shot `[$16902]`, `[$12e30] := 0`, `[$16966] := $100`, and the four debris records `$169b2 + 88·k` (kind := 0).
**Checkpoint** `$1300e` copies `[$1697e]→[$12e32]`, `[$12e18]→[$12e34]`, `[$12e1a]→[$12e36]`, `[$12e14]→[$12e38]`, Rick x `[$1695c]→[$12e3a]`, Rick y `[$16960]→[$12e3c]`,
submap `[$16464]→[$12e3e]`, scroll `[$16462]→[$12e40]`; `$13060` restores them into D0..D7 (after `$17760`: ammo and bombs := 6) — that is the respawn state.
`$1300e` is called at the end of every `$14458`, i.e. **the checkpoint is the last submap entry**.

## 6. Checks at the end of every frame (`$10acc…`)

```
if [$115e0] != 0: goto MAPDONE                                                   # §8
if !demo:  if key == $1f (S): if [$10b5c] == 0: [$10b5c] := -1 ; $1a5d0 ; [$1a5ce] ^= -1       # once per press
           else [$10b5c] := 0
           (demo: [$10b5c] := 0)
if demo:   if [$3efb8] != 0: goto END_OF_RUN ($10c00)                              # the recording ended
           if fire: [$3efb6] := 0 ; jump to PICK ($10a1e)                          # fire ends the demo and starts a game
else:      if key == 1 (ESC): $1a5d0 ; jump to TITLE ($10a18)
           if key == $19 (P): repeat $191e6 until fire is down ; one more $191e6      # pause
if [$12e2a] != 0 and [$16960] ≥ $100:                                              # Rick dead and fallen out of the playfield (y >= $100)
      if [$17710] == 0: goto END_OF_RUN
      $149c2 (kill all 4 objects and 6 actors: $149f0 each) ; $142fc (= $13060 restore, then §5 from $14300 on)
goto FRAME
END_OF_RUN ($10c00):  if demo: [$3efb6] := 0 ; jump to TITLE ;  else $17c06 (game over) ; $17f22 (hall of fame) ; jump to TITLE
```

`$1a5d0` stops all sound: it writes directly to the YM2149 PSG (`$ffff8800`/`8802`), muting mixer register 7 (`|= $3f`, disabling all 3 tone channels and the noise generator) then zeroing registers 0–6
(volume/period of channels A/B/C and the noise period) — a hardware-level silence, not a request the music/SFX engine could override (read 2026-09-22, `PLAN.md` T33, closed). Note that in the demo branch the fire test is on `[$1a4fb]` bit 7, which during the demo is the *recorded* input byte or the
real one — `read_player_input` (`$141cc`, `algo-player.md`) decides. `$141cc` was itself confirmed to return the recorded byte unmodified into the same consumers as live input (`PLAN.md` T31, closed).

## 7. Score, lives, ammo, bombs, bonus timer

* `$1771c` (new game): score bytes `$176e4..6 := 0`, `[$176e8]` long and `[$176ec]` word := 0, `[$176f0] := -1`, lives `[$17710] := 6`, `[$1770e] := -1`.
  `$17760`: `[$176f4] := 6` (laser ammo), `[$176f2] := -1`, `[$17702] := 6` (bombs), `[$17700] := -1`.
* `$17810` add score, **D0 = BCD long**: does nothing when demo; stores D0 at `$17896`; `abcd` ×3 adds the low three bytes of D0 (`$17897..$17899`) into
  `$176e4..$176e6` (carry out of the top byte is dropped — max 999 999); then splits the 6 digits into `$176e8..$176ed` (one digit per byte); `[$176f0] := -1`.
  E.g. `D0 = $500` adds 500, `$5000` adds 5000, `$100000` adds 100 000, `$10000` adds 10 000 (used by the callers listed in `algo-*.md`).
* `$17782` (extra life): `[$17710] := min([$17710] + 1, 6)`, `[$1770e] := -1`. Called once per map completion (`$10b22`).
* Death branch `$13a62` (inside `update_player_rick`, `algo-player.md` §8): play_sound(10), `[$12e2c] := 0`, `[$12e2a] := -1`, **`[$17710] −= 1`**, `[$1770e] := -1`, `[$1696c] := 0`. The game-over
  test (`[$17710] == 0`, §6) therefore happens after the decrement, once Rick has fallen to y ≥ `$100`: from the initial 6 lives, deaths 1–5 respawn and the 6th death ends the run.
* **Bonus timer** (`$15826`, per frame): `if [$157ac] == 0: return`; `[$157ae] −= 1`; when it reaches 0: `[$157ae] := $19` (25) and `sbcd` subtracts the two
  bytes at `$1586c/$1586d` (`00 10`) from the BCD long `[$157b0]` (i.e. −10 per tick, one tick per 25 frames); if `[$157b0] == 0` after the tick, `[$157ac] := 0` (stops).
  Start `$157be` (spawn record type `$78`; only if not running): `[$157ac] := -1`, `[$157b0] := $2000` (BCD 2000), `[$157ae] := $19`, play_sound(`$11`).
  Stop with award `$157f4` (record type `$7c`; only if running): `[$157ac] := 0`, score += `[$157b0]` (via `$17810`), play_sound(1), and `bset #7` on the spawn record
  (latched). Silent stop `$157b4`: `[$157ac] := 0`; called by `$14300` and by both submap transitions. (Dispatch of the record types: `level-tables.md` §3.)
* Map completion `$1789a` (only at the very end, §8): `(lives + 1) × 100 000` (loop body-first: `[$17710] + 1` iterations of `$100000`), `[$176f4]` × 5 000 (`$5000`),
  `[$17702]` × 10 000 (`$10000`) — the last two loops test first, so exactly `[$176f4]` / `[$17702]` iterations.

## 8. Map completion, endings, game over

```
MAPDONE ($10ad2, [$115e0] != 0):
   if [$1239c] == 4:
        if [$17992] == 5: → NEXT
        if [$17994] == 1: [$17992] := 5 ; → NEXT              # finishing map 4 in a game started from map 1 unlocks the fifth picker row
        else: $17bf4 (scene 1, not in demo) ; → END_OF_RUN
   elif [$1239c] == 5:
        if [$17994] == 1: → ENDING
        else: $17bf4 (scene 1) ; → END_OF_RUN
   else: → NEXT
NEXT ($10b1a):   [$1239c] += 1 ; $17782 (extra life) ; goto LOAD ($10a30)
ENDING ($10bf2): bsr $10c28 ; $1789a (tally, §7) ; $17bda ; then END_OF_RUN
```

* `$17bf4` = `run_scene(1)` (`$18186`, D0 = 1), nothing when demo. `$17bda`: nothing when demo, else play_sound(9, 0) and `run_scene(2)`.
  Scene grammar and content: `decode_scenes.py` → `assets/levels/scenes.json` (maps 1–3: 1 scene, map 4: 2 scenes, the second being the "level 5" tease itself; there is no map 5 to have images for — `hnk-system.md` §7).
* `$10c28` is an obfuscated trampoline: it saves the MFP registers and vectors to `$11606..` and pushes two computed return addresses; the returns land at `$10cce`
  → `$11554` (restores the same registers/vectors from `$11606..`, `clr.b [$1a4fb]`) → `$1153e` (arithmetic on A0/D0 only) → `$11554` again → `rts` to `$10bf4`.
  Traced statically (all steps read): net effect = no game-visible change except `[$1a4fb] := 0` and the `$4e71` written at `$1164a`. Not needed for a port.
* **Game over `$17c06`**: fade out, clear, `$194ce(2)`, play_sound(2, 0), set all four HUD dirty flags, `$177a8` (HUD), draw the string at `$17c7c` at column `$f`, row `$c`,
  fade in, wait until `[$1aa08] == 0` (music ended), then up to `$3c` (60) frames or fire, `$1a5d0`.
* Extra life per map: `$17782` at NEXT. Ammo/bombs are refilled to 6 by `$17760` at every map load (`$10a3c`) and at every respawn (`$13060`).

## 9. Submap transition (`$14362` → `$14434` → `$18abe` / `$18bb2`)

`$14362` (every frame; runs only when `[$14360] ≠ 0`, i.e. when the last horizontal move clamped Rick against the left (1) or right (2) limit —
`algo-player.md`): walks the trigger table `[$1435c]` (4-byte records `b0 b1 b2 b3`, ended by `b0 == 0`); a record matches when `b0 & 3 == [$14360]` and
`b1 == ((([$16462] & ~7) + [$16960] + $14) >> 3)` (Rick's tile row). For the matching record:
`[$144c2] := (b0 bit 6) ? 1 : 0` (§10); then if `[$17990] == 0` the record completes the map when `(b0 & $90) == $90`, if `[$17990] ≠ 0` when `b0 & $80` — completing means
`[$115e0] := -1` and leaving the scan; otherwise `[$12e14] := (b0 bit 5) ? -1 : 0`, `D0 := b2`, `D1 := (((b3 << 3) − (([$16960] + $14) & ~7)) & ~7) | ([$16462] & 7)`, and call `$14434`.
`$14434`: if Rick's x `[$1695c] == 0`: `[$1695c] := $e8`, `$18abe`; else `[$1695c] := 0`, `$18bb2`.
Both transitions (`$18abe`: source `$68588`, address −8 per step, uses `$18b5c`; `$18bb2`: source `$68510`, +8 per step, uses `$18c50`) do, in order:
`$18782` (draw the background), `[$1695a] := 0`, `[$16902] := 0`, `$170b6`, `[$1695a] := 1`, `[$16b12] := 0`, **`$14458` with the D0/D1 passed in** (`$18782` saves D0/D1;
`$170b6` and `$170ce/$170d4/$170f2` save only A registers, and `$17116` (the sprite draw) saves D0–D7 — all read — so D0/D1 arrive intact), `$16474`, `$188d0`, `$157b4`,
`$149c2` (all objects and actors killed), `$14542`, spawn scan forced (`[$14592] := -1 … 0`), `$1709e` (draws the objects into the `$68000` window),
`$19216`, `$191e6`, then `[$18ed8] := 1` and **16 steps** of {slide blit, `$19216`, `$191e6`}, `[$18ed8] := 2`, `$16630`.

## 10. Actor group (`$15bc0`, called every frame; gated by `[$144c2]`)

Armed by a trigger-table record with bit 6 (§9); cleared at level start (`$142a0`), by `$143aa` when a record without bit 6 matches, and when defeated (`$15cd2`).
While `[$144c2] ≠ 0`: `$14d48` (actor table update) returns immediately; the spawn scan `$14594` only builds the group (`$15b3c`) if actor 0 is free and then returns; `$15bc0`
returns unless actor 0 (`$16b6a`) is active. Descriptive label used here: **the group** (5 actors); the code gives no name.

* **Setup `$15b3c`**: `[$15b38] := $14` (20 hits), `[$15b3a] := 0`; for actors 0–4 (`$16b6a + 88·k`): kind 1, x/y := the words of the template table `$1586e` (5 × 12 B: x, y, anim ptr (long),
  move ptr (long); rows `(176,144,$159f6)`, `(156,165,$159fc)`, `(180,165,$15a02)`, `(156,186,$15a1e)`, `(180,186,$15a24)`; all five use move script `$158aa`), `+$12 := 1`, `+$10 := 0`, one `$171bc`
  (animation step), counters cleared; `[$16d22] := 0`, `[$16d32] := 0`, `[$16d34] := 1`.
* **Per frame `$15bc0`**: `$1726e` on actor 0 gives (dx, dy) from its movement script `$158aa`; **all five** actors get `x += dx, y += dy` and one animation step `$171bc`.
  Hit tests, with actor 0's (x, y): box `(x, y, $1c, $3e)` and box `(x−$14, y+$18, $14, $20)` against Rick via `$14b7a` → `[$12e2c] := -1` (Rick is hurt);
  the laser point (`$14bee`, point 1) in either of those boxes → `[$16902] := 0` and a **hit** (below); otherwise each of the two boxes enlarged by `(−$10, −$e, +$20, +$1d)` against the bomb point (`$14c20`, point 2), same **hit**.
  **Hit `$15eca`**: play_sound(`$18`), set `+$10 := 1` in all five actors (flag read by the animation/draw code), `[$15b38] −= 1`; when it reaches 0 the group is **defeated**.
  Not hit: if `[$16d22] == 0` → `$15d84` (fire a shot) else `$15e48` (move the shot).
* **Shot** (uses actor slot 5, record `$16d22`: `+0 [$16d22]` active, `+2 [$16d24]` x, `+6 [$16d28]` y, `+$a [$16d2c]` dx, `+$c [$16d2e]` dy, `+$e [$16d30]` frame): `$15d84`: while `[$15b3a] ≠ 0` it counts down (`$15e48` also counts it down, floor 0, while a shot flies);
  at 0: play_sound(`$22`), `[$15b3a] := $32` (50 frames), `[$16d22] := 1`, frame `[$16d30] := $6c`, start `(actor0.x − $1c, actor0.y + $2c)`; velocity: `(Rick.x + $c − x, Rick.y + $a − y)` halved
  repeatedly until both |components| ≤ 4 (if both reach 0 → `(±4, ±4)` with the signs of the differences). `$15e48`: `x += dx`, `y += dy`; deactivate if `x + 4 < 0` or `x + 4 ≥ $104`, or the tile attribute at
  `(x+4, y+4)` (`$161fe`, byte `[$15f14]`) has bit 1 set, or the box `(x+2, y+2, 4, 4)` hits Rick (then `[$12e2c] := -1` as well).
* **Defeat `$15cc8`**: score += `$5000`; `[$144c2] := 0`; actors 0–4 are re-initialised from the table `$15a2c` (5 × 8 B: anim ptr, move ptr — anims `$15a54/$15a5a/$15a5c/$15a5e/$15a6e`, moves
  `$15a74/$15a98/$15ac4/$15af0/$15b1c`; scripts decoded in `assets/levels/scripts.json` → `in_program_group`): kind `$11`, `+$2e := $60`, animation/move pointers, counters cleared; object 0 (`$167a2`) is
  created at actor 0's position: kind 1, frame base `+$3e := $4b`, `+$4e := -1` (dying), `+$12 := 0`, vy `−$500`, dx `−2`, play_sound(`$b`); `[$16d22] := 0`.

## 11. Game over / hall of fame `$17f22`

Entry point: `END_OF_RUN` (§6) after `$17c06`. Score compare: D0 := word `[$176e8]`, D1 := long `[$176ea]` (the digit bytes, i.e. the digits 10⁵10⁴ and 10³…10⁰); entries `k = 0…7` at `$17d0e + 30·k`
(`+2` word = same high digits, `+4` long = low digits). First entry with `D0 > word` or (`D0 == word` and `D1 ≥ long`) is the insertion point (ties go above). If none: return.
Entries `k … 6` are shifted down one place (copy of `+0` long, `+4` long, `+$12` long, long, word = the name; bytes `+8..+$11` are not copied), then `+2`/`+4` := the score.
Name entry screen: title string `$17ea2` (col 9, row 5), five grid-row strings at `$17eba` (col 14, rows 8, 10, …; 12 bytes apart), cursor cell `(D2 col 0–5, D3 row 0–4)` starting at (5, 4), `D7` = index of the
next name character (0–9), starting at 0. On fire: `grid[D3·6 + D2]` from `$17ef7` is fetched; `$11` = finish (goto the POOKY check below); else the OLD "next-char" marker is erased first (draws the space string
`$17ea0` at column `D7+14`, row `21`, i.e. right under the name buffer — **before** `D7` can change), then `$10` = delete (writes `$0e` at buffer `$17f16+D7`, then `D7 −= 1` unless already 0) or any other value is
written at `$17f16+D7` (then `D7 += 1` unless it is 9, so the 10th slot is overwritten in place, never grown past). On up/down/left/right (no fire): the *grid* cursor's old cell is erased first (`$17ea0` at the
*old* `(D2,D3)`, saved before moving) then `D2`/`D3` move, clamped, no wrap. Either way the redraw `$1813e` runs next: draws the cursor glyph `$17e9e` (a single `$0f`) at the grid cell `(2·D2+14, 2·D3+9)`, the
10-byte name buffer `$17f16` at the fixed position (col 14, row 20), then the *same* cursor glyph again at `(D7+14, 21)` — the "next letter goes here" marker under the buffer. So there are two simultaneously
visible cursors, sharing one glyph and one erase string. The name buffer `$17f16` (10 bytes) starts as ten `$0e`; fire must be released before the next key is read (the `$18080` loop calls `$1813e` and waits for release).
At finish the buffer is compared with the long `$504f4f4b` ("POOK") at `$17f16` and the long `$590e0e0e` ("Y", 3 blanks) at `$17f1a` — the last two characters are **not** compared — and if both match `[$1798e] := $ff` (cheat).
The name is stored at entry `+$12` as `char + 1`, with `$0e` first replaced by `$20` (so a blank is stored as `$21`). `$17e40` subtracts 1 again for display.
Grid at `$17ef7` (read from RAM, 6 × 5, row-major): `ABCDEF / GHIJKL / MNOPQR / STUVWX / YZ.␠ then $10 $11` (ASCII codes; `$10` delete, `$11` end). The row strings drawn on screen (`$17eba…`) are the letters
separated by spaces; the last one ends with the glyph ids `$10 $11 $12 $13`. Title string `$17ea2` = "PLEASE ENTER YOUR NAME". `$17c7c` = "GAME OVER".

## 12. What this document does not cover

**T30–T33/T38 closed 2026-09-22** (`PLAN.md`): `$19272` (glyph blitter — `D0` = column in 8-px units, bit 0 selects which half of the 16-px hardware word-pair; `D1` = row in 8-scanline units;
writes both screen buffers), `$1925a` (record-list draw — repeats `(word col-or-terminator, word row, long string-ptr)`, terminator = a negative first word, e.g. the picker's `$ffff`), `$194ce` (arg 0–3 picks one
of four `$600`-byte banners at `$35a74` — "CONGRATULATIONS!", "HALL OF FAME", "SELECT LEVEL", "LOADING..." — decoded and rendered, `graphics.md` §4b; arg 3 additionally shifts the destination down 80 scanlines,
used only by `load_map_if_changed`'s "LOADING..." banner), the demo-mode input path (`$141cc` returns the recorded byte completely unmodified into the same bit tests as live input — no separate mapping exists),
the slide blits and `$188d0` (`graphics.md` §3b), `$1a5d0` (direct YM2149 silence-everything: mixer register 7 muted, registers 0–6 zeroed). `$1a866` (music tick) is in `sound-ref.md`.
**T37 (block-map tail bytes) closed 2026-09-22** — see `graphics.md` §3a: the row-shift arithmetic (`$164de`/`$1653e`/`$165a6`, plus the `rows = w1//4+6` header formula) proves the window generator leaves exactly
6 block-rows of margin unused at maximum scroll, for every submap of all 4 maps (checked by computing `w1//4` — the block-rows the shift mechanism will have consumed after scrolling the full range — against the
declared `rows`, for all 58 submaps: margin is 6 everywhere). The tail bytes past the *last* submap's total range are simply unused space in the fixed `$3000`–`$3900` region — never read by anything.
**Map 5's data** (level image, demo stream, scenes 0–2) was never a real level — the finale scripts (`$17bf4`/`$17bda`) exist for a "level 5" that is a sequel tease, never playable, per the user; `hnk-system.md` §7, `PLAN.md` T28 (closed).

_Ghidra names (program `prg2-ram.bin`, renamed 2026-09-20): `$15bc0` = `update_actor_group` (it was `handle_screen_edge_and_respawn` — that name was wrong: nothing in it handles screen edges or respawns), `$15b3c` = `init_actor_group`._
