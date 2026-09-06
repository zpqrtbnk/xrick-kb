# Algorithms — System, Init, Interrupts, Screens, Text

Exact transcription of the 26 functions in `0x48F16`–`0x495E0` and `0x4DC2A`–`0x4DF86`.
Source of truth: Ghidra disassembly (not decompiler output). Ghidra plate comments hold
the per-address evidence; this file is the re-codable form.

**Scope:** main loop and init, the IKBD input path, VBlank/timing, palette, text/glyph
rendering, PRNG, attract mode, high-score table and name entry.

**Calling convention:** hand-written 68K. Arguments arrive in registers, results often
in the **condition codes**. Each function below states its own convention. Unless
stated, a function preserves the registers it lists in its `movem` prologue.

---

## 0x48F16 `show_highscore_table`

`show_highscore_table(void) -> void` — clobbers D0/D1/D2/A0

```c
clear_both_screen_buffers();              // 0x4B7DA
blit_image_5120(A0 = 0x423EE);            // 0x44BEE — high-score background bitmap
D1 = 6;                                   // starting text row
A0 = 0x48E26 + 2;                         // = 0x48E28, first record's display string
for (D2 = 7; D2 >= 0; D2--) {             // dbf: 8 iterations
    draw_string_xy(A0, x = 7, y = D1);
    A0 += 0x1E;                           // next high-score record (30 bytes)
    D1 += 2;                              // every other text row
}
```

**Notes.** The drawn string starts at record+2, i.e. the six score-digit bytes are
themselves part of the rendered string (see the record layout under
`enter_highscore_name`). Eight rows at y = 6, 8, 10 … 20.

---

## 0x48FCC `enter_highscore_name`

`enter_highscore_name(void) -> void` — reads the final score from `HudCounters`,
inserts it if it qualifies, then runs the joystick-driven name-entry grid.

### High-score record — 0x1E (30) bytes, 8 records at `0x48E26`

| Offset | Size | Field |
|---|---|---|
| +0x00 | word | unused (0) |
| +0x02 | word | `score_digits_hi` — **2 unpacked decimal digits, one per byte** |
| +0x04 | long | `score_digits_lo` — 4 unpacked decimal digits |
| +0x08 | 10 B | fixed decoration, identical in every record: `5E 5E 5E 3C 3C 3C 3C 5E 5E 5E` |
| +0x12 | 10 B | name, blank-padded with `0x5E` |
| +0x1C | byte | `0xFF` string terminator |
| +0x1D | byte | pad |

Scores are **unpacked decimal digits (one digit per byte)**, not packed BCD — which is
why a plain `cmp.w` / `cmp.l` on the digit bytes compares numerically.

```c
D0 = (word) HudCounters.wScore_display_hi;   // 0x4B330
D1 = (long) HudCounters.dwScore_display_lo;  // 0x4B332
A1 = 0x48E26;
for (D2 = 7; D2 >= 0; D2--) {                // find insertion slot
    if (D0 >  *(word*)(A1+2)) goto INSERT;
    if (D0 == *(word*)(A1+2) && D1 >= *(long*)(A1+4)) goto INSERT;
    A1 += 0x1E;
}
return;                                       // score did not qualify

INSERT:
if (D2 != 0) {                                // shift lower entries down one slot
    A2 = 0x48EF8;                             // last record (0x48E26 + 7*0x1E)
    for (D3 = D2 - 1; D3 >= 0; D3--) {
        *(long*)(A2+0x00) = *(long*)(A2-0x1E+0x00);   // score hi word + pad
        *(long*)(A2+0x04) = *(long*)(A2-0x1E+0x04);   // score lo
        *(long*)(A2+0x12) = *(long*)(A2-0x1E+0x12);   // name bytes 0..3
        *(long*)(A2+0x16) = *(long*)(A2-0x1E+0x16);   // name bytes 4..7
        *(word*)(A2+0x1A) = *(word*)(A2-0x1E+0x1A);   // name bytes 8..9
        A2 -= 0x1E;
    }
}
*(word*)(A1+2) = D0;
*(long*)(A1+4) = D1;

palette_fade_out();
clear_both_screen_buffers();
blit_image_5120(A0 = 0x40FEE);                       // name-entry background
draw_string_xy(0x48F4C, x=9,  y=5);                  // "PLEASE ENTER YOUR NAME"
A0 = 0x48F64;                                        // 5 grid rows, 12 bytes each
D1 = 8;
for (D2 = 4; D2 >= 0; D2--) { draw_string_xy(A0, x=0x0E, y=D1); D1 += 2; A0 += 0x0C; }

// name buffer 0x48FC0[10] = ten '9' (0x39) placeholders
*(long*)0x48FC0 = 0x39393939;
*(long*)0x48FC4 = 0x39393939;
*(word*)0x48FC8 = 0x3939;

D2 = 5;  D3 = 4;  D7 = 0;      // grid col, grid row, name cursor position
palette_fade_in();

LOOP:                                                 // 0x490AC
draw_name_entry_cursor();
vsync_wait(); vsync_wait(); vsync_wait(); vsync_wait();   // 4-frame input debounce
D4 = joystick1_state;                                 // 0x4922B
if (D4 & 0x80) {                                      // FIRE
    D5   = D3 * 6 + D2;                               // grid index (6 cols x 5 rows)
    char = *(byte*)(0x48FA1 + D5);
    if (char == 0x37) goto COMMIT;                    // '7' cell = END
    draw_string_xy(0x48F4A, x = 0x0E + D7, y = 0x15); // erase name cursor
    A2 = 0x48FC0 + D7;
    if (char == 0x36) {                               // '6' cell = BACKSPACE
        *A2 = 0x39;                                   // blank the slot
        if (D7 != 0) D7--;
    } else {
        *A2 = char;
        if (D7 != 9) D7++;
    }
    do { draw_name_entry_cursor(); } while (joystick1_state & 0x80);  // wait release
    goto LOOP;
}
// no fire: move the grid cursor
D5 = D2; D6 = D3;                                     // remember old cell
if      (D4 & 0x04) { if (D2 != 0) D2--; }            // LEFT
else if (D4 & 0x08) { if (D2 != 5) D2++; }            // RIGHT
if      (D4 & 0x01) { if (D3 != 0) D3--; }            // UP
else if (D4 & 0x02) { if (D3 != 4) D3++; }            // DOWN
draw_string_xy(0x48F4A, x = D5*2 + 0x0E, y = D6*2 + 9);   // erase old cursor
goto LOOP;

COMMIT:                                               // 0x491A6
A1 += 0x12;                                           // name field of the chosen record
A2  = 0x48FC0;
if (*(long*)0x48FC0 == 0x504F4F4B &&                  // "POOK"
    *(long*)0x48FC4 == 0x59393939)                    // "Y999"
        *(word*)0x498C4 = 0x00FF;                     // POOKY easter-egg flag
D2 = 9;
do {
    D3 = *A2++;                                       // byte -> D3.b
    if (D3 == 0x39) D3 = 0x5E;                        // placeholder -> blank
    *A1++ = D3;
} while (--D3.w != -1);        // dbf D3w -- see the note below
```

**Notes / uncertainties.**
- **`0x491E2` — the commit loop ends with `dbf D3w`.** `D3` holds the *character just
  copied*, not the counter `D2` that was set to 9 immediately before. Reproduce
  `dbf D3w` literally; the object code is the specification.

  ✅ **Fully characterised 2026-09-02 (T7) — the loop is benign, and the "over-run" is
  exactly two bytes that land on their correct destinations.**

  `move.b (A2)+,D3` writes only the **low byte**, while `dbf` tests the **full word**.
  The high byte is therefore the whole question — and it is provably **always zero**:

  - `D3` reaches `COMMIT` holding the **grid row**, which the menu clamps to `0..4`
    (`D3 = 4` initially; UP/DOWN keep it in range). So `D3.w = 0x000r` on entry.
  - `move.b` never touches bits 8-15, so the high byte stays `0x00`.
  - `dbf` decrements `0x00XX`; for `XX > 0` the result is `0x00(XX-1)`, high byte still
    `0x00`. It can only reach `0xFFFF` from `0x0000`.

  So the high byte never becomes non-zero, and the loop is exactly equivalent to
  **"copy bytes until the byte just copied is `0x00`"**. The typed characters can never
  be `0x00` (letters, or `0x39` placeholders rewritten to `0x5E`), so termination comes
  from the source data:

  ```
  0x48FC0  10 bytes  name buffer
  0x48FCA  FF        static sentinel  <- copied, terminates nothing (non-zero)
  0x48FCB  00        static sentinel  <- copied, terminates the loop
  ```

  `0x48FCA`/`0x48FCB` are **static** — a program-wide search for absolute references to
  either returns **zero** writers, while the buffer's three initialisers (`0x48FC0`,
  `0x48FC4`, `0x48FC8`) account for exactly the 10 buffer bytes.

  The loop therefore always copies **exactly 12 bytes**, whatever is typed and whatever
  row `D3` held. Modelled in Python over the plausible inputs, all give 12 bytes — e.g.
  typing `POOKY` yields `50 4F 4F 4B 59 5E 5E 5E 5E 5E FF 00`.

  And the destination absorbs all 12 correctly, because the source layout mirrors the
  record tail:

  | Source | Bytes | Destination | Record field |
  |---|---|---|---|
  | `0x48FC0`+0..9 | name | `A1+0x12`..`+0x1B` | name (10 bytes) |
  | `0x48FCA` | `FF` | `A1+0x1C` | string terminator — **correct value** |
  | `0x48FCB` | `00` | `A1+0x1D` | pad |

  12 bytes span `+0x12`..`+0x1D`, which is the last byte of the `0x1E`-byte record — it
  **does not touch the next record**. Nothing is corrupted and the player sees nothing
  wrong.

  **`move.w #0x0009,D2` at `0x491D0` is dead** — `D2` is never read by the loop, almost
  certainly a leftover from an intended `dbf D2`.

  **For a reimplementation:** emitting `dbf D3w` literally is correct, but so is "copy 12
  bytes" or "copy until a copied byte is zero" — they are equivalent given this source
  layout. What must be preserved is that the `FF` and `00` reach `+0x1C`/`+0x1D`.
- Character grid `0x48FA1`, 6 cols × 5 rows: `ABCDEF` / `GHIJKL` / `MNOPQR` / `STUVWX`
  / `Y Z \ (blank) DEL END`, where `0x36`=DEL and `0x37`=END.
- The easter egg requires the buffer to read `POOKY` followed by five untouched `9`
  placeholders — i.e. the player types exactly "POOKY" and selects END.

---

## 0x491E8 `draw_name_entry_cursor`

`draw_name_entry_cursor(D2 = grid col, D3 = grid row, D7 = name pos) -> void`

```c
draw_string_xy(0x48F48, x = D2*2 + 0x0E, y = D3*2 + 9);   // "8" = cursor glyph
draw_string_xy(0x48FC0, x = 0x0E,        y = 0x14);       // the name buffer so far
draw_string_xy(0x48F48, x = D7  + 0x0E,  y = 0x15);       // cursor under name slot
```

**Strings.** `0x48F48` = `38 FF` (glyph `'8'` used as the cursor mark);
`0x48F4A` = `5E FF` (a single blank, used to erase a cursor);
`0x48F4C` = `"PLEASE^ENTER^YOUR^NAME"` + `0xFF` (`0x5E` renders as space).

---

## 0x4922E `init_keyboard`

`init_keyboard(void) -> void` — configures the IKBD and installs the ACIA interrupt.

```c
acia_write(0x12);                       // IKBD command: disable mouse
acia_write(0x14);                       // IKBD command: set joystick event reporting
*(long*)0x00000118 = 0x49262;           // MFP ACIA interrupt vector -> keyboard_isr
```

**Note.** Vector `0x118` is MFP channel 6 (ACIA / IKBD-MIDI) on the ST.

---

## 0x4924E `acia_write`

`acia_write(D0.b = byte) -> void` — clobbers D1

```c
do { D1 = *(byte*)0x00FFFC00; } while ((D1 & 0x02) == 0);   // wait TX-ready
*(byte*)0x00FFFC02 = D0;                                    // ACIA data
```

---

## 0x49262 `keyboard_isr` — **the input path**

Installed at vector `0x118`. This is a **joystick reader**, not a keyboard reader: it
decodes the standard Atari IKBD joystick report, which is a two-byte packet
(`0xFE`/`0xFF` header, then one state byte). Two static flag bytes carry the
"next byte belongs to joystick N" state across interrupts.

```c
if (*(byte*)0x492E6 != 0) {                    // previous byte was the 0xFE header
    joystick0_state = *(byte*)0x00FFFC02;      // -> 0x4922A
    *(byte*)0x492E6 = 0;
    goto done;
}
if (*(byte*)0x492E8 != 0) {                    // previous byte was the 0xFF header
    joystick1_state = *(byte*)0x00FFFC02;      // -> 0x4922B
    *(byte*)0x492E8 = 0;
    goto done;
}
push D0;
D0 = *(byte*)0x00FFFC02;
if      (D0 == 0xFE) *(byte*)0x492E6 = 1;      // joystick 0 report follows
else if (D0 == 0xFF) *(byte*)0x492E8 = 1;      // joystick 1 report follows
else                 kbd_scancode = D0;        // -> 0x4922C, plain key scancode
pop D0;
done:
*(byte*)0x00FFFA11 &= ~0x40;                   // clear MFP ISRB bit 6
rte;
```

### Input state — resolved

| Address | Name | Meaning |
|---|---|---|
| `0x4922A` | `joystick0_state` | port 0 (mouse port) — read but unused by gameplay |
| `0x4922B` | `joystick1_state` | **the player's joystick** |
| `0x4922C` | `kbd_scancode` | last raw key scancode |
| `0x492E6` | `pending_joy0` | one-shot: next ACIA byte is joystick 0 |
| `0x492E8` | `pending_joy1` | one-shot: next ACIA byte is joystick 1 |

**Joystick bit layout** (standard Atari encoding, confirmed by usage in
`enter_highscore_name`'s cursor movement and the `btst #7` fire tests throughout):

| Bit | Mask | Direction |
|---|---|---|
| 0 | 0x01 | UP |
| 1 | 0x02 | DOWN |
| 2 | 0x04 | LEFT |
| 3 | 0x08 | RIGHT |
| 7 | 0x80 | FIRE |

**Keyboard scancodes actually used:** `0x01` = ESC (abandon game → attract mode),
`0x19` = P (pause), `0x39` = SPACE (palette toggle). All standard ST scancodes.

**Note.** `find_code_gaps` reports "orphaned instructions" at `0x492E6` — that is these
two flag **bytes** being mis-disassembled as code. They are data.

---

## 0x492EE `install_vblank_handler`

```c
*(long*)0x00000070 = 0x492FA;      // level-4 autovector = VBlank on the ST
```

---

## 0x492FA `vblank_isr`

```c
movem.l D0-D7/A0-A6, -(SP);
*(byte*)0x49334 += 1;              // vblank_counter
music_tick();                      // 0x44E0C  <-- music is driven at 50 Hz VBlank
movem.l (SP)+, D0-D7/A0-A6;
rte;
```

**Note.** The music engine ticks from **VBlank**, not from Timer A, even though
`setup_timer_a` exists. Any reimplementation must call the music tick once per frame
from the vertical-blank path to keep tempo identical.

---

## 0x49310 `vsync_wait`

`vsync_wait(void) -> void` — preserves D0 (and therefore any caller `dbf` counter in D1)

```c
push D0;
D0 = vblank_counter;                                  // 0x49334
do {
    while ((int8)vblank_counter < 1) { /* spin */ }   // at least one tick pending
} while (vblank_counter == D0);                       // and it must have changed
vblank_counter = 0;
pop D0;
```

**Note.** Callers rely on D1 surviving (`main_init_and_loop` and `attract_mode_loop`
both run `dbf D1w` loops around this call).

---

## 0x49336 `flip_screen_buffer`

```c
while ((int8)vblank_counter < 1) { /* spin */ }
*(byte*)0x492EC ^= 0x80;                       // toggle bit 7 of the mid byte
*(byte*)0x00FF8201 = *(byte*)0x492EB;          // video base, bits 16-23
*(byte*)0x00FF8203 = *(byte*)0x492EC;          // video base, bits 8-15
```

**Screen base model.** `0x492EA` is a longword holding the current screen address;
`0x492EB`/`0x492EC` are its high and mid bytes, written straight into the ST video base
registers. Toggling bit 7 of the mid byte moves the base by `0x8000`, giving the two
buffers **`0x70000`** and **`0x78000`**. Elsewhere the *back* buffer is obtained as
`*(long*)0x492EA ^ 0x8000` (see `render_sprites`, `draw_title_picture`).

Note this function does **not** clear `vblank_counter` — only `vsync_wait` does.

---

## 0x4935E `xbios_setscreen`

```c
push word 0;            // rez = 0 (320x200, 16 colours)
push long -1;           // physbase unchanged
push long -1;           // logbase unchanged
push word 5;            // XBIOS 5 = Setscreen
trap #14;
SP += 12;
```

---

## 0x4937C `set_palette`

`set_palette(A0 = ptr to 16 words) -> void`

```c
A1 = 0x00FF8240;
for (D0 = 15; D0 >= 0; D0--) *A1++ = *A0++;    // 16 hardware colour registers
```

---

## 0x49394 `palette_fade_in`

Ramps the hardware palette up to the target at `0x4DEE2` over **8 frames**.

✅ **Precondition verified 2026-08-31 (T12) — the palette does read black at entry.**
The routine ramps *up to* a target and never reads or zeroes the current palette, so the
"starts from black" contract is real and had to be proven at the call sites. It is:
the hardware palette base `0x00FF8240` is referenced by exactly **three** instructions in
the image — in `set_palette` (`0x49382`), here (`0x493AE`) and in `palette_fade_out`
(`0x4940A`) — and `set_palette` has a single caller (`0x4DE4A`). Of the nine callers of
this routine, eight have a `palette_fade_out` in the same function; the ninth
(`0x499BC`, in `enter_screen_with_fade`) is reached only via `show_selection_menu` ->
`start_level` -> `show_level_intro_screen`, which ends with `palette_fade_out` at
`0x4B794` and cannot restore the palette before returning. See `../PLAN.md` T12.

```c
D2 = 0x700; D3 = 0x70;                       // per-component thresholds
for (D4 = 7; D4 >= 0; D4--) {
    vsync_wait();
    A1 = 0x4DEE2;                            // target palette
    A2 = 0x00FF8240;                         // hardware palette
    for (D0 = 15; D0 >= 0; D0--) {
        if ((*A1 & 0x700) > D2) *A2 += 0x100;    // red   +1
        if ((*A1 & 0x070) > D3) *A2 += 0x010;    // green +1
        if ((*A1 & 0x007) > D4) *A2 += 0x001;    // blue  +1
        A1 += 2; A2 += 2;
    }
    D2 -= 0x100; D3 -= 0x10;                 // D4 decremented by the dbf
}
```

A component with target value `T` is incremented on exactly `T` of the 8 steps, so it
arrives at `T`. ST colour words are `0x0RGB`, 3 bits per component.

---

## 0x493FE `palette_fade_out`

Ramps the hardware palette down to black over 8 frames.

```c
for (D2 = 7; D2 >= 0; D2--) {
    vsync_wait();
    A0 = 0x00FF8240;
    for (D0 = 15; D0 >= 0; D0--) {
        if (*A0 & 0x700) *A0 -= 0x100;
        if (*A0 & 0x070) *A0 -= 0x010;
        if (*A0 & 0x007) *A0 -= 0x001;
        A0 += 2;
    }
}
```

---

## The text system

### Font

`0x1B01E`, **32 bytes per glyph, indexed by the raw character byte** (so a 256-glyph
table spanning `0x1B01E`–`0x1D01E`). Each glyph is **8×8 pixels in 4 bitplanes**:
8 rows × 4 bytes, one byte per plane per row.

**Strings are ASCII terminated by `0xFF`** (not NUL) — e.g. `0x4DE22` = `"GAME\xFF"`,
`0x4DE27` = `"OVER\xFF"`. Verified by decoding glyph `0x47` at `0x1B01E + 0x47*32 =
0x1B8FE`, whose plane-3 bitmap is a legible `G`. Indices `0x00`–`0x09` are the digit
glyphs (used for score display), `0x5E` renders as blank, and letters sit at their
ASCII codes.

### 0x494E2 `draw_glyph`

`draw_glyph(A4 = glyph data, A1 = screen ptr) -> void` — preserves A4, advances nothing

```c
push A4;
for (row = 0; row < 8; row++) {
    *(byte*)(A1 + 0) = *A4++;     // plane 0
    *(byte*)(A1 + 2) = *A4++;     // plane 1
    *(byte*)(A1 + 4) = *A4++;     // plane 2
    *(byte*)(A1 + 6) = *A4++;     // plane 3
    A1 += 0xA0;                   // 160 bytes = one low-res scanline
}
pop A4;
```

Writing single bytes at +0/+2/+4/+6 targets the *high* byte of each plane word, i.e.
the left 8 pixels of a 16-pixel group. The odd/even stepping in the callers selects the
left or right half.

> **Fidelity note (2026-08-30).** The real routine is **fully unrolled**, not a loop,
> and differs from the rolled form above in two unobservable ways: it performs **seven**
> `lea (0xa0,A1),A1` advances for eight rows (the eighth row needs none), and the
> **32nd byte is read as `move.b (A4),(0x6,A1)` with no post-increment**. So on return
> the real A1 is `7 × 0xA0` further on, not `8 × 0xA0`, and A4 has advanced 31 times,
> not 32. Neither is observable: A4 is restored from the stack, and both callers reload
> A1 (`draw_string` recomputes it per glyph; `draw_glyph_string` saves it in A2 and
> restores it after the call). Reproduce either form — but if you emit the rolled loop,
> do not also rely on A1's final value.

### 0x49466 `draw_string`

`draw_string(A0 = 0xFF-terminated string, D0 = screen byte offset) -> void`

```c
for (;;) {
    D1 = *A0++;
    if (D1 == 0xFF) return;
    A4 = 0x1B01E + (D1 << 5);            // glyph = index * 32
    A2 = 0x70000 + D0;
    A3 = 0x78000 + D0;
    draw_glyph(A4, A1 = A2);             // both screen buffers
    draw_glyph(A4, A1 = A3);
    // advance one 8-pixel cell:
    old_bit0 = D0 & 1;  D0 ^= 1;
    if (old_bit0) D0 += 8;               // 2 cells per 16-px group, group = 8 bytes
}
```

### 0x494AC `draw_glyph_string`

`draw_glyph_string(A0 = string, A1 = raw screen ptr) -> void` — same stepping, but
writes **one** buffer at a caller-supplied address.

```c
for (;;) {
    D0 = *A0++;
    if (D0 == 0xFF) return;
    A4 = 0x1B01E + (D0 << 5);
    A2 = A1;
    draw_glyph(A4, A1);
    A1 = A2;
    old_bit0 = (long)A1 & 1;  A1 = (void*)((long)A1 ^ 1);
    if (old_bit0) A1 += 8;
}
```

### 0x49446 `draw_string_xy`

`draw_string_xy(A0 = string, D0 = x in cells, D1 = y in text rows) -> void`

```c
D1 = D1 * 1280;                 // lsl#8 then (x4 + x1): 8 scanlines * 160 bytes
old_bit0 = D0 & 1;  D0 &= ~1;
if (old_bit0) D1 += 1;          // odd column -> +1 byte (right half of the group)
D0 = D0 * 4;                    // (x & ~1) * 4  ==  (x/2) * 8
D0 += D1;
draw_string(A0, D0);
```

Screen offset = `(x >> 1) * 8 + (x & 1) + y * 1280`. Text cells are 8×8 px, so 40
columns × 25 rows.

---

## 0x49574 `seed_prng_state`

```c
D7 = 0x16051966;
D6 = 0x09121967;
D6 <<= 8;                       // 0x12196700
D6.w -> D7.w;                   // D7 = 0x16056700
D7.w -= 7;                      // D7 = 0x160566F9
D6.w ^= D7.w;                   // D6 = 0x121901F9
prng_a = D6;                    // 0x495C0 = 0x121901F9
prng_b = D7;                    // 0x495C4 = 0x160566F9
```

A **fixed** seed — the game's randomness is deterministic from power-on, so a
reimplementation reproduces identical sequences by using these exact values.

## 0x49596 `update_prng`

```c
D6 = prng_a;  D7 = prng_b;      // 0x495C0, 0x495C4
swap(D6, D7);
D7 = rol32(D7, 3);
D7.w -= 7;
D7.w ^= D6.w;
prng_a = D6;                    // = old prng_b
prng_b = D7;
```

Only the low word is mixed by the subtract/xor; the high word is merely rotated.
Consumers use the low byte (e.g. `enemy_ai_update` tests `prng_b & 3`).

---

## 0x4DC2A `main_init_and_loop` — the spine

### Init sequence (0x4DC2A – 0x4DCCD), in order

```c
Super(0x5324C);                     // GEMDOS #0x20, trap #1  -- see CORRECTION below
clear_screen_buffers();             // 0x4DE2E
furthest_level = 0;                 // 0x498C2
seed_prng_state();
init_screen_and_palette();
install_vblank_handler();
init_keyboard();
setup_timer_a();                    // 0x45006
flip_screen_buffer(); vsync_wait();
play_music(D0 = 5, D1 = 1);         // title music, one-shot
draw_title_picture();
flip_screen_buffer(); vsync_wait();

for (D1 = 0xAF; D1 >= 0; D1--) {    // dbf D1: 0xAF -> **176** frames, not 175
    vsync_wait();
    toggle_palette_on_space();
    if (joystick1_state & 0x80) goto NEW_GAME;
}
attract_mode_loop();                // returns only when FIRE pressed

RESTART:                            // 0x4DC90 — re-entry after game over / ESC
play_music(5, 1);
attract_mode_loop();

NEW_GAME:                           // 0x4DC9E
reset_sound_chip();                 // 0x44C10
init_hud_state();
revive_all_placements();
stop_bcd_timer();
*(word*)0x4DE2C = 0;                // "return to attract" flag
clear_sprite_flags();
reset_player_state();
spawn_player_entity();
show_selection_menu();              // 0x499A0
flip_screen_buffer(); vsync_wait();
```

### Per-frame dispatch (main loop at 0x4DCCE)

```c
MAIN_LOOP:
hud_update_score();
hud_update_bullets();
hud_update_dynamite();
hud_update_lives();

if (player_dying == 0) goto ALIVE;                    // 0x4BF18

    // --- dying ---
    if (player.wType != 0) goto RENDER;               // 0x4A74E: player entity still
                                                      // spawned -> death tumble running
    if (HudCounters.bLives == 0) goto GAME_OVER;      // 0x4B32E
    clear_sprite_flags();
    restore_checkpoint_state();
    spawn_scan_flags = 7;                             // 0x495C8: repopulate all pools
    render_new_screen();
    goto MAIN_LOOP;

ALIVE:                                                // 0x4DD0E
    if (player.nPosY <= 0x5F) { scroll_view_up();  goto MAIN_LOOP; }   // 0x4A754
    if (player.nPosY >= 0xCC) { scroll_view_down(); goto MAIN_LOOP; }

RENDER:                                               // 0x4DD2E
    blit_backgrounds();
    render_sprites();
    bcd_countdown_timer();
    update_prng();
    flip_screen_buffer();
    vsync_wait();

    if (player_dying != 0) goto MAIN_LOOP;
    if (player.nPosX <= 0 || player.nPosX >= 0xE8) {   // 0x4A752, out of bounds
        clear_sprite_flags();
        spawn_player_entity();
        process_level_transition_point();
        if (*(word*)0x4DE2C != 0) goto AFTER_FADE;    // level/game finished
        goto MAIN_LOOP;
    }
    if (kbd_scancode == 0x01) goto RESTART;           // ESC -> abandon to attract
    if (kbd_scancode != 0x19) goto MAIN_LOOP;         // not P -> continue
        kbd_scancode = 0;                             // P = PAUSE
        while (kbd_scancode != 0x19) { /* spin */ }   // wait for P again
        kbd_scancode = 0;
        vsync_wait();
        goto MAIN_LOOP;

GAME_OVER:                                            // 0x4DDBA
    palette_fade_out();
AFTER_FADE:                                           // 0x4DDBE
    reset_hud_dirty_and_redraw();
    play_music(D0 = 6, D1 = 0);                       // game-over jingle, looping arg 0
    draw_string_xy(0x4DE22, x = 0x0F, y = 0x0C);      // "GAME"
    draw_string_xy(0x4DE27, x = 0x15, y = 0x0C);      // "OVER"
    palette_fade_in();
    do { vsync_wait(); } while (*(word*)0x45096 != 0);    // wait for jingle to finish
    for (D0 = 0x3C; D0 >= 0; D0--) {                     // dbf D0: 0x3C -> up to **61** frames
        vsync_wait();
        if (joystick1_state & 0x80) break;
    }
    reset_sound_chip();
    enter_highscore_name();
    goto RESTART;
```

**Constants:** room-scroll thresholds `0x5F` / `0xCC` on `player.nPosY`;
out-of-bounds bounds `0` / `0xE8` on `player.nPosX`; title wait **176** frames
(`dbf` with `0xAF`); game-over wait **61** frames (`dbf` with `0x3C`).

⚠️ **`dbf Dn` with `Dn = N` executes the body `N+1` times.** The `for (D = N; D >= 0; D--)`
form above is correct; the earlier prose counts of "175" and "60" were off by one and
are corrected. Audit 7 in `byte-identity.md` enumerates every `dbcc` site.

---

## 0x4DE2E `clear_screen_buffers`

```c
A0 = 0x63800;
for (D0 = 0x71FF; D0 >= 0; D0--) *(long*)A0++ = 0;   // 0x7200 longwords = 0x1C800 bytes
```

Clears `0x63800`–`0x7FFFF`: the tile/sprite cache at `0x65B00` and both screen buffers.

## 0x4DE40 `init_screen_and_palette`

```c
xbios_setscreen();
set_palette(A0 = 0x4DEE2);
*(word*)0x4DE56 = 0;               // palette-variant flag
```

## 0x4DE58 `toggle_palette_on_space`

```c
if (kbd_scancode != 0x39) return;               // SPACE
palette_fade_out();
A1 = 0x4DEE2;                                   // live target palette
A0 = (*(word*)0x4DE56 != 0) ? 0x4DEA2 : 0x4DEC2;   // alternate / default palette
for (D0 = 15; D0 >= 0; D0--) *A1++ = *A0++;
*(word*)0x4DE56 ^= 0x00FF;
palette_fade_in();
```

A cosmetic colour-scheme toggle between the palettes at `0x4DEA2` and `0x4DEC2`.

## 0x4DF02 `attract_mode_loop`

```c
for (;;) {
    palette_fade_out();
    show_highscore_table();
    palette_fade_in();
    for (D1 = 0xAF; D1 >= 0; D1--) {
        vsync_wait();
        toggle_palette_on_space();
        if (joystick1_state & 0x80) return;
    }
    palette_fade_out();
    draw_title_picture();
    flip_screen_buffer();
    vsync_wait();
    palette_fade_in();
    for (D1 = 0xAF; D1 >= 0; D1--) {
        vsync_wait();
        toggle_palette_on_space();
        if (joystick1_state & 0x80) return;
    }
}
```

Alternates high-score table and title picture, **176** frames each (`dbf` with `0xAF`), until FIRE.

## 0x4DF5A `draw_title_picture`

```c
A0 = 0x23FEE;                                   // title bitmap
A1 = (*(long*)0x492EA) ^ 0x8000;                // back buffer
for (D0 = 0x3FF; D0 >= 0; D0--) {
    // 8 unrolled long moves = 32 bytes per iteration
    for (i = 0; i < 8; i++) *(long*)A1++ = *(long*)A0++;
}
```

0x400 × 32 = **32768 bytes** = one full low-res screen.

---

## Corrections — all applied (closed 2026-08-29)

Six items this pass raised against the then-current docs. All are folded in; nothing
here is outstanding. (See the rule in `MEMORY.md` §8.)

| # | Correction | Status |
|---|---|---|
| 1 | **`Mshrink` is wrong — it is `Super()`.** `main_init_and_loop` pushes long `0x5324C`, word `0x20`, then `trap #1`; GEMDOS `0x20` is `Super()` (Mshrink is `0x4A`). The game enters supervisor mode with SSP = `0x5324C`, which is why it touches MFP/ACIA/video registers directly. **Consequence:** the supervisor stack grows *downward from `0x5324C`* into the uncaptured `0x50000`–`0x5324F` region, so that region is stack as well as sample data. | ✅ applied — `functions.md`; `MEMORY.md` §7 records "two traps total (`Super`, `Setscreen`)", and the missing-memory question is closed |
| 2 | **Input is a JOYSTICK, not the keyboard.** `keyboard_isr` decodes IKBD joystick packets; `0x4922B` is the player input byte with Atari bits UP/DOWN/LEFT/RIGHT/FIRE = `0x01`/`0x02`/`0x04`/`0x08`/`0x80`. Keyboard scancodes are used only for ESC (`0x01`), P (`0x19`) and SPACE (`0x39`). Closes the "keyboard-scancode-to-action mapping" item once flagged as needing dynamic verification. | ✅ applied — global settled as **`joystick1_state`** throughout `re/` (the last four `player_input_bitmask` uses were retired 2026-08-29) |
| 3 | **Game text IS ASCII**, merely `0xFF`-terminated rather than NUL-terminated, and the font is indexed by the raw character byte. Ghidra found nothing only because its ASCII analyzer had *Require Null Termination* enabled. | ✅ applied — the old "text isn't ASCII" advice is **retracted**; `re/strings.md` holds all 64 strings, and `MEMORY.md` §7 records both the retraction and the analyzer-option lesson |
| 4 | **Music ticks from VBlank**, not Timer A — `vblank_isr` calls `music_tick` (`0x44E0C`) every frame. Both ISRs exist, but the 50 Hz driver is the VBlank path; Timer A drives sample playback. | ✅ applied — `functions.md` `music_tick` / `vblank_isr` / `timer_a_music_isr` rows |
| 5 | **High-score record layout** is more specific than recorded: 30-byte records at `0x48E26`, score as **unpacked decimal digit bytes** (word of 2 digits at +2, long of 4 at +4), 10 bytes of fixed decoration at +8, and the 10-byte **name at +0x12** — not "name text follows" at +8. | ✅ applied — the full table is in this file under `enter_highscore_name` |
| 6 | **`0x498C4`** is the POOKY easter-egg flag (set to `0x00FF`); **`0x498C2`** is `furthest_level`, cleared during init. | ✅ applied — `data-structures.md` globals; `functions.md` notes the level-select menu is gated by it |

## Unresolved

- ~~The effect of the POOKY flag `0x498C4`~~ ✅ **resolved, and verified on hardware
  2026-08-29** — it gates `run_selection_menu` (`0x498C6`), the level-select screen,
  which is therefore unreachable in normal play. See `algo-level.md`.
- The `dbf D3w` name-commit loop (item above) — behaviour is deterministic but odd;
  **needs dynamic verification** to describe the visible result. Tracked as `../PLAN.md` T7.
- ~~`0x4DE2C`, the "return to attract mode" flag~~ ✅ **resolved** — set to `0xFF` by
  `process_level_transition_point` on the game-complete path (`algo-level.md`), cleared
  and read here. The cross-range gap is closed.
