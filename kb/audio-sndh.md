# Replacing the port's WAV audio with the real SNDH engine — architecture & plan

**Status: implemented, P1-P9 all done (2026-09-10).** Registered as T19 in `PLAN.md`.
Full progress log in §12; task table in §10. The one thing left is not an engineering
task: `xrick` is running interactively for the user's own by-ear confirmation — see
§12's P8 entry and §11 for exactly what engineering verification could and could not
check on its own.

## 0. The ask

The port (`xrick/`) currently plays 29 pre-rendered WAV files, made by ear, with no
PSG data anywhere (`MEMORY.md` §9: "the port has no sound engine"). We now have
`kb/assets/audio/rick_dangerous.sndh` — the game's **actual** ST sound engine, lifted
byte-for-byte from `atari_ram.bin`/`atari_ram_1M.bin` and packaged by
`kb/build_sndh.py`, verified by listening. The task: make the port call *that* engine
instead of `SDL_LoadWAV`, via Arnaud Carré's
[AtariAudio](https://github.com/arnaud-carkb/AtariAudio) library (MIT-licensed, header
`AtariAudio/README.md` fetched and read in full 2026-09-09), embedded in the binary and
streamed to SDL's audio callback.

This is a fidelity upgrade, not just a rewrite: the port's WAVs are guesses at what the
effects sounded like; the SNDH engine is the original 68000 replay code running under
emulation, so every envelope, every PSG mix trick and both digidrums play exactly as on
real hardware.

## 1. What AtariAudio actually gives us (verified by reading `src/*.h`/`.cpp` directly)

Two usable layers, not one:

| Class | What it does | Fits us? |
|---|---|---|
| `SndhRenderer` | The documented public API: `Create`/`InitSubSong(id)`/`AudioRender(buf,n)`. Generic SNDH-archive-browser use case. | **No** — see §2 |
| `AtariMachine` | The actual 68000 + YM2149 + MFP68901 + STE-DAC emulator `SndhRenderer` drives internally. Public methods: `Startup(rate)`, `Upload(src,addr,size)`, `Jsr(addr,d0)`, `ComputeNextSample()`. | **Yes** — this is the layer we drive directly |

`AtariMachine::Jsr()` resets only the 68000 *CPU* (registers/PC), not RAM, and runs
real 68000 instructions (Musashi core, vendored as `.cpp`, no code-gen step needed —
`m68kops.cpp` ships pre-generated) until the callee's `rts` is caught by a trampoline.
`ComputeNextSample()` advances the YM2149 by one output sample **and** ticks the four
MFP timers, jumping to a timer's ISR vector if it fired that sample — this is how
`timer_a_music_isr` (the digidrum player) runs, with zero special-case code on our side.
`memRead8/16`/`memWrite8/16` are also public, for poking scratch RAM.

License: MIT (`AtariAudio/LICENSE`, fetched and read in full). No encumbrance beyond
attribution, unlike xrick's own "all rights reserved" ambiguity (`MEMORY.md` §9) — this
vendored library is a separate, cleanly-licensed dependency.

## 2. The one hard design problem: `SndhRenderer.InitSubSong` resets everything

`SndhRenderer::InitSubSong(id)` calls `AtariMachine::Startup()` (zeroes all 4MB of
emulated RAM) and re-uploads the whole image, then jumps to the subtune's `init`. That
is exactly right for a jukebox that plays one subtune to completion — and exactly wrong
for us: the real game calls `play_music()` for **level music, every sound effect, and
both digidrums, all through the same live engine state**, while three PSG voices are
shared between tracked music and SFX with a priority bit
(`kb/algo-music.md` §3, §12: `trigger_channel_note` sets `A6[0x18] |= 0x80`, "SFX voice
priority"). A jump sound effect must not stop the level music. `SndhRenderer`'s
one-subtune-at-a-time model cannot express that; `build_sndh.py`'s own SNDH (§4 below)
is deliberately built with **one subtune per `music_track_table` entry** precisely so a
generic *player* can audition each track in isolation — the opposite of what the game
itself does at runtime.

**Resolution: don't use `SndhRenderer` for gameplay at all. Drive one persistent
`AtariMachine` instance for the whole game session**, exactly mirroring what the real
ST hardware does:

1. `Startup(hostReplayRate)` once, at `sounds_load()` time.
2. `Upload(engine_blob, addr, size)` once — at the address that matches wherever the
   *source dump's own* internal absolute references actually point (see the P8
   correction below — this is **not** simply the literal `0x44C10` in every case).
   `AtariMachine` lets the caller choose the load address, so the whole relocating
   stub `build_sndh.py` had to hand-assemble (because generic SNDH players pick their
   own load address) becomes unnecessary here — we choose it once, in Python, at
   extraction time, instead of copying at runtime.

   ⚠️ **Correction, found the hard way in P8's smoke test.** The design as first
   written here said "at 0x44C10, the original ST address" and treated that as always
   correct. It is only correct if the blob's bytes were captured from a dump with load
   delta 0. `extract_sound_engine.py` (P1) prefers `atari_ram_1M.bin` for complete PCM
   data, same as `build_sndh.py` — and that dump's own internal absolute references
   (table lookups, the timer-A ISR vector `setup_timer_a` installs, everything) are
   **relocated by that dump's own `-0x2054` delta**, confirmed by diffing the raw bytes
   of `setup_timer_a` between `atari_ram.bin` and `atari_ram_1M.bin` directly: one
   installs ISR address `0x45022`, the other `0x0042FCE` — off by exactly the delta.
   Uploading `atari_ram_1M.bin`-sourced content at the canonical `0x44C10` (as this
   section originally specified) silently breaks every internal reference by that
   delta — the engine still runs (no crash), dispatches correctly on the surface, but
   every table lookup and hardware-vector install lands `0x2054` bytes off from where
   it should. `build_sndh.py` never hits this because it uploads at its own
   `rel(REF_RESET)`, not the canonical address — P1's extractor now does the same
   (§10, P1's log entry). The lesson generalizes: **any address into a
   position-dependent blob sourced from a non-canonical dump needs the same
   adjustment as the blob's own load address, not just the entry points** — this bit
   both the extractor and, initially, the standalone verification harness written to
   check it.
3. `Jsr(0x44C10, 0)` once — `reset_sound_chip`.
4. `Jsr(0x45006, 0)` once — `setup_timer_a` (required for both digidrums; omitting it is
   the exact mistake `build_sndh.py`'s own header warns about).
5. Every gameplay sound trigger (jump, bullet, entity death, level-music start, …)
   becomes `Jsr(0x44CCE, D0=track)` — i.e. a direct call to `play_music`, with D1 handled
   by a two-line trampoline (§5).
6. The SDL audio callback ticks Timer-independent 50 Hz music by calling
   `Jsr(0x44E0C, 0)` (`music_tick`) once every `sampleRate/50` samples, then calls
   `ComputeNextSample()` once per output sample — precisely the pacing
   `SndhRenderer::AudioRenderInternal` uses internally (confirmed by reading it), just
   reimplemented so gameplay `Jsr` calls can interleave between ticks.

This reproduces the original ST's actual behaviour (one continuously-running replay
engine, all triggers going through the same `play_music` entry point) rather than
forcing the game through a "load a track, play it to completion" abstraction that never
existed on the real machine.

## 3. Component architecture

```
xrick/xrick/src/
  syssnd.c          <-- rewritten: owns the AtariMachine instance + SDL callback
  sounds.c          <-- rewritten: WAV_* become { track, voiceSlot } descriptors
  dat_sndh_engine.c  <-- NEW, generated: the 58,944-byte engine+table blob as a
                          const U8[] (same pattern as dat_tilesST.c, dat_maps.c —
                          this port already embeds big binary tables as C arrays)
  audio_engine/      <-- NEW, vendored verbatim from arnaud-carkb/AtariAudio (MIT),
                          unmodified except for build-system glue:
    AtariMachine.{h,cpp}
    Mk68901.{h,cpp}
    SteDac.{h,cpp}         (unused STE features; cheap, keep for parity/future)
    ym2149c.{h,cpp}, ym2149_tables.h
    Musashi/*.{h,cpp}      (m68k core, pre-generated opcode tables, no codegen step)

xrick/xrick/include/
  syssnd.h          <-- same public function names/signatures where possible (§6)
  sounds.h          <-- same WAV_* extern names (§6)

kb/                  <-- unchanged; still the RE source of truth
  build_sndh.py       <-- unchanged; still produces the standalone .sndh artifact
                          (useful for archival / sc68 / SndhArchivePlayer playback)
tools/ (new, top-level or under xrick/)
  extract_sound_engine.py  <-- NEW, adapted from build_sndh.py: same delta-finding
                          logic, but emits a flat 0x44C10-0x5324F image with NO
                          relocating stub and NO SNDH header (we upload at the
                          original address ourselves, so neither is needed), as a
                          generated dat_sndh_engine.c
```

`SndhRenderer` itself, `ice_24` (ICE depacker) and `timedb` are **not vendored** — they
exist only to make `SndhRenderer::Load()` parse an arbitrary third-party SNDH file's
header and duration tags, none of which we need since we drive `AtariMachine` directly
against a blob we generated ourselves.

Why not reuse `rick_dangerous.sndh` itself as the embedded resource? Because its stub
and header exist to satisfy §2's *wrong* per-subtune-reset model; embedding it and then
never calling its `init` trampolines would just carry dead weight. `extract_sound_engine.py`
shares `build_sndh.py`'s dump-loading and `find_delta()` logic (the delta is not fixed —
`MEMORY.md` §6 — so this must stay dynamic) but drops everything past "lift the blob".

## 4. Why the engine can be lifted at all (inherited invariant, not re-derived)

`kb/assets-manifest.md`'s audio section already establishes the containment audit this
depends on: engine code `0x44C10`–`0x45720`, tables `0x44F08`–`0x46B66`, song data
`0x45720`–`0x48F15`, three PCM samples at `0x4DF86`/`0x4FCF2`/`0x50DA8`, window
`0x44C10`–`0x5324F` (58,944 bytes), nothing below it, nothing in the graphics blob, no
calls into game code. This design reuses that audit rather than re-running it; if it
is ever found wrong, both `build_sndh.py` and this design need revisiting together.

## 5. The `play_music(D0, D1)` calling convention, and why it maps cleanly

`kb/algo-music.md` §3 documents that `D1`'s meaning depends on the track's *type*:

| Track type | D1 meaning |
|---|---|
| 0 — tracked song | Loop flag: `0` = one-shot, nonzero = loop forever (`music_tick` restarts it) |
| 1 — SFX | Voice-slot pick: `0` = alternate voices 0/1, nonzero = dedicated priority voice (slot 2) |
| 2 — digi sample | **Ignored entirely** (`assets-manifest.md`: confirmed by reading `play_music`'s type-2 branch) |

The port's existing `syssnd_play(sound, loop)` / `sounds_setMusic(name, loop)` calls
already only ever pass **`1` or `-1`** for `loop` (checked — every call site in
`e_*.c`/`scr_*.c`/`sounds.c` was grepped; no other value appears), and that binary
already matches the ST's own binary D1 for the *music* tracks: `-1` at the sites that
mean "loop" (attract-mode `tune5`, per `algo-system.md` `play_music(D0=5,D1=1)`), `1` at
the sites that mean "play once" (level tunes, game-over `play_music(D0=6,D1=0)`). So:

- **Track type 0 (music):** `D1 = (port_loop < 0) ? nonzero : 0`. No new research
  needed — this is the same translation the port author already did by ear.
- **Track type 1 (SFX):** the port's `loop` parameter has no ST counterpart (voice-slot
  choice is a hardware-mixing nuance, not a gameplay-visible loop). Default to `D1 = 1`
  (dedicated voice) since that's what most cited `algo-player.md` SFX call sites use
  (`0x0F`,`0x0E`,`0x0B` all `D1=1`); a handful use `D1=0` (`0x08`/`0x0A` have both a
  `D1=1` and a `D1=0` site — different contexts for the same track). **Open item:** a
  full per-callsite D1 census (mirror of the T16/assets-manifest.md census method) is
  cheap but not yet done — see task P3. Getting this wrong only affects which of two
  overlapping SFX wins the shared voice, never correctness of pitch/timbkb/track choice.
- **Track type 2 (sample):** D1 irrelevant, pass `0`.

Two static trampolines solve the "Jsr only sets D0" problem (`Jsr(addr,d0)` has no `d1`
parameter) — write D1 into a fixed scratch RAM cell via `memWrite16`, then jump into two
1-instruction stubs assembled into the blob at build time (same hand-assembly technique
`build_sndh.py` already uses and documents its `ENCODINGS` block for):

```
trampoline_d1_from_scratch:
    move.w  (SCRATCH_D1).w, d1
    jmp     play_music        ; 0x44CCE
```
One instance is enough (D1 is written right before each `Jsr`); no need for two
separate loop/no-loop trampolines.

## 6. Public API — keep call sites unchanged where the semantics allow it

The whole point of doing this at the `syssnd.c`/`sounds.c` layer is that ~25 call sites
across `e_*.c`, `scr_*.c`, `game.c`, `sysevt.c` never need to change. Mapping:

| Old | New behaviour |
|---|---|
| `sound_t` | No longer a PCM buffer. Becomes `{ U8 track; U8 sfxVoiceD1; }` — 2 bytes, still heap-free, still usable as `static const` (see below) |
| `syssnd_load(char* name)` | **Removed.** There is no file to load; every `WAV_*` becomes a compile-time constant. Mirrors the port's own pre-#021212 `wav_*.e` files (`wav_bullet.e` etc., still in the tree, dead since the WAV-file switch) — this design is closer to that original embedded-data approach than to the file-loading one it replaces |
| `sounds_load()` / `sounds_free()` | Rewritten: `sounds_load()` = `AtariMachine::Startup` + `Upload` + the two init `Jsr`s (§2 steps 1-4) + `SDL_OpenAudioDevice`; `sounds_free()` = stop device, nothing to free (no per-sound heap allocs survive) |
| `syssnd_play(sound_t*, S8 loop)` | Locks the same mutex the callback uses, writes D1 per §5, `Jsr(0x44CCE, sound->track)` |
| `sounds_setMusic(char* name, U8 loop)` | **Signature changes**: `name` was always a WAV path; becomes `sounds_setMusic(U8 track, S8 loop)`. This is the one real call-site edit — `dat_maps.c`'s `map_t.tune` field (`char*`) becomes a `U8` track number, and its 5 literal `"sounds/tuneN.wav"` strings become literal track numbers (§7) |
| `syssnd_stopsound()` / `syssnd_stopchan()` / `syssnd_isplaying()` | No ST hardware equivalent — the original engine has no "stop this one sound", only whole-engine `reset_sound_chip`/`silence_all_channels`. Grep confirms these three are **only called from within `syssnd.c`/`sounds.c` themselves**, never from game logic — so they collapse to calling `Jsr(0x45528,0)` (`silence_all_channels`) or become dead code. Needs a git-tracked removal, not silent deletion — task P5 |
| `syssnd_pause(pause, clear)` | `SDL_PauseAudioDevice`; `clear=TRUE` → also `Jsr(reset_sound_chip)` |
| `syssnd_vol(S8)` / `syssnd_toggleMute()` | Unchanged in spirit: scale/zero the `int16_t` sample in the callback after `ComputeNextSample()`. (`AtariMachine::MuteVoices()` exists but mutes individual YM/DAC voices, not overall volume — not the right tool for a user volume slider) |

`dat_snd.c` and the five `wav_*.e` files (`WAV_WAA`, `WAV_BOMB`, `WAV_TING`, `WAV_SHHT`,
`WAV_DDDING`) are confirmed dead — grepped, zero references outside their own
declarations. Candidates for deletion in the same pass (task P6), not before — per house
rule, "unused" is asserted here only because the xref was actually run, not assumed.

## 7. The track-number census ✅ **DONE 2026-09-10 (task P3)**

`kb/assets-manifest.md`'s "Track map" section did the first pass; `kb/algo-player.md`
§0.3 ("Sound track IDs used here") turned out to already hold a complete literal census
for the player's own tracks that the original scan hadn't been cross-referenced against.
Combined with `kb/algo-entities.md`'s pickup/trigger-zone transcriptions and the port's
*own* source comments (several call sites already cite the exact ST instruction, written
during T1), every `WAV_*`/tune symbol now resolves to a track number on real evidence —
no name-based guessing.

| Port symbol | ST track | Type | Evidence |
|---|---|---|---|
| `WAV_ENTITY[0..9]` | `19`-`28` (`0x13`-`0x1C`) | 1 (mostly) | `wTriggerSound` **is** the track number directly (`data-structures.md:66`; `kb/pm-baty.md`'s G8) |
| `WAV_BULLET` | 8 | **PCM** | `algo-player.md:94` §0.3 "`0x08` bullet fire"; `assets-manifest.md` track 8 = gunshot, `player_controller` fire path |
| `WAV_BOMBSHHT` | 9 | 1 | `algo-player.md:94` "`0x09` empty-click *and* dynamite fuse tick". **Confirmed at instruction level in the port's own source**: `e_rick.c:463-468`'s comment cites `4C530 move.w #0x9,D0 / moveq #1,D1 / jsr play_music` verbatim for the empty-gun click, and names this same track for `e_bomb.c:156`'s fuse tick |
| `WAV_EXPLODE` | 10 | **PCM** | §0.3 "`0x0A` explosion"; `algo-entities.md:402` `destructible_pickup_update`'s `DESTROY:` path, `play_music(0x0A,0)` — matches `e_box.c`'s/`e_bomb.c`'s `explode()` |
| `WAV_STICK` | 11 | 1 | §0.3 "`0x0B` stick jab"; `e_rick.c:657`, the stick-attack action |
| `WAV_WALK` | 12 | 1 | §0.3 "`0x0C` footstep/climb"; `algo-player.md:566,577` — `player_select_anim_frame` uses the **same** track for both the climbing and walking cadence, matching the port having no separate climb sound |
| `WAV_CRAWL` | 13 | 1 | §0.3 "`0x0D` crawl"; `algo-player.md:556` |
| `WAV_JUMP` | 14 | 1 | §0.3 "`0x0E` jump / ladder-exit"; `algo-player.md:289` (jump button) and `:437` (ladder-exit) — matches the port's two `WAV_JUMP` call sites in `e_rick.c` |
| `WAV_PAD` | 15 | 1 | §0.3 "`0x0F` landing"; `algo-player.md:207` "landing thud" — matches `e_rick.c:411`'s name (landing **pad**) |
| `WAV_BOX` | 16 | 1 | `algo-entities.md:410`, `destructible_pickup_update`'s "collected" path, `play_music(0x10,0)` — byte-exact match against `e_box.c`'s "collect bombs or bullets" branch (same two `n==0x10`/`0x11` type numbers) |
| `WAV_BONUS` | 17 | 1 | `algo-entities.md:446`, `treasure_pickup_update`, `play_music(0x11,0)` — **byte-exact match** against `e_bonus.c`'s `PLATFORM_ST` path: `add_score(500)` = ST's `add_score(0x500)`, sparkle counter `12` = ST's `0xC`, both literal, both cited in the port's own R3.11 comment |
| `WAV_SBONUS1` | 18 | 1 | `algo-entities.md:465-467`, `effect_start_escape_timer` (type 22), `play_music(0x12,0)` — **byte-exact match** against `e_sbonus_start`: tick divider `0x19` and bonus `2000`/`0x2000` BCD both literal and already cross-cited in the port's own comment (`xref.md` 'Super-bonus tick divider') |
| `WAV_SBONUS2` | 7 | 1 | `algo-entities.md:468-470`, `effect_stop_timer_award_bonus` (type 23), `play_music(7,0)` — matches `e_sbonus_stop`'s "add bonus to score" exactly. **This also resolves `assets-manifest.md`'s previously-unattributed track 7** |
| `WAV_DIE` | 19 | **PCM** | §0.3 "`0x13` player death"; `algo-player.md:472`, `kill_player`/`kill_enemy` — port's two `WAV_DIE` sites match "same digitised sample for player and enemy death" exactly. **Same track number as `WAV_ENTITY[0]`** (`trigsnd == 0x13` is a legal `ent_entdata` value) — not a conflict, the original genuinely reuses this sample as an entity trigger sound too |
| `gameover.wav` | 6 | 0 (song) | `algo-system.md:672`: `play_music(D0=6,D1=0)`, "game-over jingle" — the port's `loop=1` (one-shot) at `scr_gameover.c:51` already matches D1=0 |
| `tune5.wav` (attract) | 5 | 0 (song) | `algo-system.md:591/603`: `play_music(D0=5,D1=1)`, title music — the port's `loop=-1` (forever) at `scr_imain.c:61` already matches D1=1 |
| `tune0`-`tune4.wav` (level themes) | 0-4 | 0 (song) | `algo-render.md:606`: `play_music(D0=level_index,D1=0)` — **D0 is a runtime variable**, which is why the original literal-D0 scan in `assets-manifest.md` missed this site entirely. The `tuneN → track N` assignment is not separately instruction-verified per level; it rests on the naming being self-consistent with the one point that *is* independently verified (`tune5.wav` = track 5, exactly as its name implies) |

**One byproduct worth recording:** §5's D1 guess ("default to 1, the dedicated SFX
voice") is now checked against real evidence rather than assumed — every literal
`play_music` site found above for a type-1 track happens to pass `D1=1` **except** the
four `algo-entities.md` pickup/trigger-zone sites (box/bonus/sbonus, `D1=0`) and the two
`scripted_trap_update` entity-trigger sites (also `D1=0`). So the split is not
"SFX vs music" but "player-action SFX (`D1=1`) vs. world-event SFX (`D1=0`)" — recorded
here so P4 wires the real value per call site instead of a blanket default.

## 8. Threading & the SDL callback

Same shape as today's `syssnd_callback`, same mutex discipline
(`SDL_mutexP`/`SDL_mutexV` already bracket every shared-state touch in the current
`syssnd.c` — reuse the pattern, not the code):

```c
void syssnd_callback(void *userdata, U8 *stream, int len) {
    S16 *out = (S16*)stream;
    U32 n = len / sizeof(S16);
    SDL_mutexP(sndlock);
    for (U32 i = 0; i < n; i++) {
        if (--tickCountdown == 0) {
            AtariMachine_Jsr(&machine, FN_TICK, 0);
            tickCountdown = obtainedFreq / 50;
        }
        S16 s = AtariMachine_ComputeNextSample(&machine);
        out[i] = sndMute ? 0 : (S16)(s * volumeScale);
    }
    SDL_mutexV(sndlock);
}
```

`syssnd_play()`/`sounds_setMusic()` take the same `sndlock` before calling `Jsr` from
the game thread. `AtariMachine` is C++; `syssnd.c` stays C and talks to it through a thin
`extern "C"` wrapper (`audio_engine/AtariMachineC.{h,cpp}`, new, a few functions:
`Create`/`Destroy`/`Startup`/`Upload`/`Jsr`/`ComputeNextSample`/`MemWrite16`) — the only
new glue code that isn't vendored-verbatim library or generated data.

Output format changes from `AUDIO_U8` mono `22050`Hz to `AUDIO_S16SYS` mono — pass
whatever `SDL_OpenAudioDevice` actually negotiates (`obtained.freq`) into
`AtariMachine::Startup()`, don't hardcode a rate.

## 9. Build system

`xrick/xrick/Makefile` is pure `gcc`/C today (`CC := gcc`, `$(CC)` does the link too).
AtariAudio's vendored sources are `.cpp` (Musashi is C rewritten to compile as C++ per
the vendored headers). Needed changes, all confined to the Makefile:

- Add a `CXX := g++` + a C++ rule (`%.o: %.cpp`) alongside the existing `%.o: %.c` rule.
- Link with `$(CXX)` instead of `$(CC)` once any `.cpp` object exists (pulls in
  `libstdc++` automatically; no other C++ runtime dependency — the library doesn't use
  STL, exceptions or RTTI per a read of its headers).
- New source directories (`audio_engine/`, generated `dat_sndh_engine.c`) added to the
  existing `$(wildcard src/*.c)`-style globs.
- Per `MEMORY.md` — **build and smoke-test in WSL**, same as every prior port change
  (T18, G2, G8(a)).

## 10. Phased task plan

| # | Task | Depends on | Status |
|---|---|---|---|
| P1 | Write `extract_sound_engine.py` (adapt `build_sndh.py`'s delta-finder; drop the stub/header code) → `dat_sndh_engine.c` | — | ✅ 2026-09-10 |
| P2 | Vendor `AtariAudio/src/{AtariMachine,Mk68901,SteDac,ym2149c}.{h,cpp}`, `ym2149_tables.h`, `external/Musashi/*` verbatim (MIT notice preserved); write the thin `extern "C"` wrapper | — | ✅ 2026-09-10 |
| P3 | Run the extended track-number census (§7) — same method as `assets-manifest.md`'s, closes the remaining port-symbol gaps. **Do this before P4**, not after — call sites need the real numbers, not placeholders | — | ✅ 2026-09-10 |
| P4 | Rewrite `syssnd.c`/`syssnd.h` (§6, §8) and `sounds.c`/`sounds.h` (§6); update the ~4 call sites whose signature changes (`sounds_setMusic`, `dat_maps.c`'s `tune` field) | P1, P2, P3 | ✅ 2026-09-10 |
| P5 | Remove or collapse `syssnd_stopsound`/`stopchan`/`isplaying` per the xref already run in §6 | P4 | ✅ 2026-09-10 (resolved by omission — P4's rewrite never declares them) |
| P6 | Delete `dat_snd.c`/`.o` and the five dead `wav_*.e` files (confirmed unreferenced, §6) | P4 | ✅ 2026-09-10 |
| P7 | Makefile: C++ rule, `audio_engine/` + generated sources on the build list, link with `g++` (§9) | P1, P2 | ✅ 2026-09-10 |
| P8 | Build in WSL both `PLATFORM=ST` and `PLATFORM=PC`; headless smoke run; visible-window run for by-ear verification of music + every SFX + both digidrums, mirroring how `rick_dangerous.sndh` itself was verified | P4-P7 | ✅ engineering-verified 2026-09-10; **by-ear confirmation is the user's, not done by me** |
| P9 | Update `kb/xrick/` (the port knowledge base) — `sounds.c`/`syssnd.c` move from "no counterpart" to documented, closing part of T1's remaining item 3 | P8 | ✅ 2026-09-10 |

## 12. Progress log

- **2026-09-10 — P1 done.** `xrick/xrick/tools/extract_sound_engine.py` written (adapted
  from `kb/build_sndh.py`'s delta-finder, stub/header assembly dropped). Run against
  `kb/atari_ram_1M.bin`: delta measured at `-0x2054` (matches `MEMORY.md` §6's documented
  value — self-consistent, not re-asserted from memory), blob `0x44C10`-`0x5324F`
  (58,944 bytes, nothing zero-filled). Wrote `xrick/xrick/include/dat_sndh_engine.h`
  (the `SNDH_*` address constants + extern declarations) and
  `xrick/xrick/src/dat_sndh_engine.c` (the generated byte array).
- **2026-09-10 — P2 done.** Vendored verbatim from `arnaud-carkb/AtariAudio` (commit at
  fetch time; MIT `LICENSE` copied alongside) into `xrick/xrick/src/audio_engine/`:
  `AtariMachine.{h,cpp}`, `Mk68901.{h,cpp}`, `SteDac.{h,cpp}`, `ym2149c.{h,cpp}`,
  `ym2149_tables.h`, and `external/Musashi/*` (the pre-generated `m68kops.cpp`, no
  code-gen step needed — confirmed by reading it, 787,279 bytes as fetched). Byte counts
  of every fetched file checked against the GitHub API's own reported sizes before use.
  Wrote the hand-written glue this integration needs, `AtariMachineC.{h,cpp}` — an
  `extern "C"` wrapper (`create`/`destroy`/`upload`/`jsr`/`next_sample`/`mem_write16`)
  so `syssnd.c` (plain C) can drive the vendored `AtariMachine` C++ class.
  **Not yet compiled** — that happens with the rest of the build in P7/P8.
- **2026-09-10 — P3 done.** Full track census, §7 rewritten with a resolved table for
  every `WAV_*`/tune symbol. The player-action tracks came from `kb/algo-player.md`
  §0.3, a literal census that already existed but hadn't been cross-referenced against
  the port's WAV names. The pickup/trigger-zone tracks (`WAV_BOX`/`WAV_BONUS`/
  `WAV_SBONUS1`/`WAV_SBONUS2`) came from byte-exact matches against
  `kb/algo-entities.md` (same literal constants — `0x19` tick divider, `2000`/`0x2000`
  bonus, `500`/`0x500` score, `12`/`0xC` sparkle counter — appearing on both sides).
  `WAV_BOMBSHHT`'s track 9 was independently confirmed already cited at instruction
  level inside the port's own `e_rick.c:463-468` comment. One genuine three-way reuse
  found and recorded: `WAV_DIE` and `WAV_ENTITY[0]` are the **same** ST track (19) —
  not a bug, the original reuses the death sample as an entity trigger sound. Only the
  `tune0`-`tune4` (level-theme) assignment rests on naming-consistency rather than a
  separate instruction citation per level, and is flagged as such in §7.
- **2026-09-10 — P4-P7 done**, all in one pass since they touch the same files.
  - **`syssnd.h`/`syssnd.c` rewritten.** `sound_t` is now `{U8 track; S8 d1;}`.
    `syssnd_init()` opens `AUDIO_S16SYS` mono (was `AUDIO_U8`), creates one persistent
    `AtariMachine` via the `AtariMachineC` wrapper, uploads the engine blob at its
    original address plus two 8-byte hand-assembled trampolines (see below), then
    `Jsr`s `reset_sound_chip` and `setup_timer_a` once. The callback ticks
    `music_tick` every `rate/50` samples and pulls one `ComputeNextSample()` per
    output sample, under the same `SDL_mutexP`/`V` pattern the WAV mixer used.
    `syssnd_stopsound`/`stopchan`/`isplaying`/`stopall` and `channel_t` are gone
    (P5) — confirmed by grep to have no callers outside the file being rewritten.
  - **The D1 trampoline problem (design doc §5) turned out to need real 68000 bytes,
    not just a plan.** `AtariMachine::Jsr(addr, d0)` only ever sets D0, and every real
    call site uses D1 ∈ {0, 1} (P3's census), so `syssnd.c` carries two 8-byte stubs
    (`moveq #0/1,d1 ; jmp play_music`) uploaded right after the engine blob. Both
    opcodes trace to encodings `kb/build_sndh.py` already verified against real
    instructions in `atari_ram.bin` (`0x7200`/`0x7201`, and `JMP` derived from its
    verified `JSR (xxx).l = 0x4EB9` by the standard one-bit 68000 encoding
    difference) — written up in the code comment, **still owed a live
    disassembly re-check in P8**, not yet done.
  - **`sounds.h`/`sounds.c` rewritten.** Every `WAV_*` is now a `static const sound_t`
    object plus a pointer to it — the same shape the port's own dead `wav_*.e` files
    used. `WAV_ENTITY` grew from 9 to **10** populated slots: the engine already
    contains track 28 like every other track, so there is no longer a reason to leave
    slot 9 `NULL` — **this closes `kb/pm-baty.md` G8 (c)** as a side effect, noted in both
    `sounds.c` and the stale comment in `e_them.c` (now corrected).
  - **Call sites updated**, all mechanical given P3's numbers: `dat_maps.c`'s
    `map_t.tune` field is now `U8` (`maps.h` changed to match) holding the level
    index directly, since `play_music(D0=level_index,...)` makes the assignment
    trivial; the 21 `syssnd_play(WAV_X, 1)` sites lost their now-meaningless second
    argument (mechanical `sed`, verified by re-grepping after); the 4
    `sounds_setMusic` sites now pass a track number and the real `D1` from P3 instead
    of a filename and a loop count. `scr_xrick.c`'s splash-screen cue was switched
    from `sounds_setMusic` to `syssnd_play(WAV_BULLET)` — it was always the one-shot
    gunshot SFX under a misleading "set music" call, not a type-0 track.
  - **P6**: deleted `dat_snd.c`/`.o` and the ten `wav_*.e` files (grepped clean of
    references first, including the MSVC project files — `xrick.vcxproj` and
    `.vcxproj.filters` had one stale `dat_snd.c` entry each, removed to match).
  - **P7**: `Makefile` gained a `CXX`/`CXXFLAGS` pair (C++17, deliberately *not* the
    `-Wconversion`/`-Wsign-conversion` set held over the tree's own code — vendored
    library), a `%.o: %.cpp` rule, `audio_engine/**.cpp` added to the object list, and
    the final link switched from `$(CC)` to `$(CXX)`. No new `-I` flags were needed —
    every vendored include resolves same-directory.
  - **Not yet built or run** — that's P8, next.
- **2026-09-10 — P8 done (engineering side; by-ear pass is the user's).** Built clean
  in WSL, both `PLATFORM=ST` and `PLATFORM=PC` (268 warnings, same order of magnitude
  as the tree's existing baseline, none new). The first build attempt failed at link
  time (`dat_sndh_engine.c` never included `system.h`, so its whole `#ifdef
  ENABLE_SOUND` body compiled away silently — fixed by adding the include).

  **A standalone verification harness (throwaway, not committed) then found a real
  bug the headless smoke run's crash-free exit could not have caught**: uploading
  `atari_ram_1M.bin`-sourced content at the canonical `0x44C10` breaks every internal
  absolute reference by that dump's `-0x2054` delta (§2's correction, written up
  there in full — `setup_timer_a` installing `0x0042FCE` instead of `0x45022` was the
  smoking gun, confirmed by diffing raw dump bytes directly). Fixed in
  `extract_sound_engine.py`; re-verified with the same harness, byte-exact this time
  — D1 trampolines correct for both values, `play_music` dispatch confirmed reaching
  its body (track IDs, loop flags, PCM sample pointers, voice state all read back
  matching expectations), the busy-guard behaviour (type-1/2 refused while a type-0
  track is active) directly observed and matched against the documented engine
  design rather than assumed. Also found and fixed: a missing
  `silence_all_channels` call, and a first-Jsr-call reliability quirk needing a
  throwaway warm-up call (§11 has the full detail on both).

  Headless smoke run (`SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy`, `-demo`, 30s):
  no crash, clean exit on timeout. `xrick` is now running **interactively** (real
  video, real audio routed through WSLg's PulseAudio — confirmed opening without
  error) for the user's own listening pass; I cannot hear it myself, so this is
  reported as engineering-verified, not as "sounds right."
- **2026-09-10 — P9 done.** Swept `kb/xrick/` for every reference to the retired WAV
  mixer and updated each in place (marked `⚠️ Superseded`, pre-T19 content kept as a
  labelled historical record rather than deleted, matching this knowledge base's own
  convention): `algo-system.md`'s Sound section rewritten to describe the engine-based
  design; `divergences.md`'s three sound-related entries (the top-level "WAV audio in
  place of the PSG" divergence, the `channel[-1]` bug, the `dat_snd.c` duplicate-symbol
  note) marked resolved/moot; `assets.md`'s WAV/`.e`-file inventory marked unused/
  deleted; `data-model.md`'s `sound_t` layout updated; `xref.md`'s "what the port
  cannot help with" sound bullet inverted (with the caveat that the port now *imports*
  `kb/`'s extraction rather than independently corroborating it); `architecture.md`'s
  layering table's "nothing corresponds to the platform layer" claim carved out an
  exception for `syssnd.c`. `MEMORY.md` §9's "the port has no sound engine" fact
  updated at the source. T19 is now fully implemented (P1-P9); remaining work is the
  user's own by-ear pass on the running build.

## 11. Risks / things not yet verified

Resolved by P8's standalone verification harness (a throwaway program linking the
vendored library directly, driving it exactly like `syssnd.c` and reading engine RAM
back to check — not committed, not part of the port):

- ✅ **D1 trampoline correctness** — confirmed byte-exact: `track_id`/loop-flag read
  back from engine RAM after each trampoline call matched the requested `(track, d1)`
  pair exactly, for both trampolines, including the `d1=1` (loop) and `d1=0` (one-shot)
  cases.
- ✅ **The upload-address bug** (§2's correction) — found *by* this harness, not just
  checked by it: the first version silently mis-set every internal reference by the
  dump's delta. Fixed in P1's extractor; re-verified clean afterward (`setup_timer_a`
  installs the correct, dump-relative ISR address; a PCM track's `dwData_ptr` lands
  correctly in the sample-start pointer once the engine is idle).
- ✅ **D1 for type-1 SFX** — turned out not to matter functionally. Every SFX call
  site's `D1` picks *which voice* (dedicated vs. alternating), never *whether* the
  sound plays; sounds.c bakes in the real value per §7's census regardless.
- ✅ **Busy-guard behaviour understood, not assumed.** `play_music`'s type-1/2 dispatch
  refuses to interrupt an *active* type-0 (tracked-music) track (`state == 1`) —
  confirmed directly (an SFX call made while a looping track was active left the voice
  state untouched; the identical call succeeded, provably reaching
  `trigger_channel_note`, once a one-shot level track had run to completion and the
  engine returned to idle). This is why level themes being one-shot (§7) matters
  mechanically, not just as a loop-flag curiosity: gameplay SFX are silently swallowed
  for as long as any type-0 track stays active, exactly matching the original engine,
  not a bug in this port.
- ✅ **Two real bugs found and fixed, both in `syssnd_init()`:**
  1. Missing `Jsr(SNDH_FN_SILENCE, 0)` — the design doc's own §2/§9 always intended
     this (mirroring `build_sndh.py`'s RESET→SILENCE→TIMERA sequence, required
     because the blob is a *live, mid-play* snapshot, not a clean boot) but the first
     `syssnd.c` implementation omitted it. Added.
  2. **A freshly-`Startup()`'d `AtariMachine`'s very first `Jsr()` call is unreliable** —
     measured directly: calling `reset_sound_chip` first returns `false` (harmlessly);
     calling `setup_timer_a` first **segfaults**. Calling *any* function twice in a row
     is reliable from the second call onward, and stays reliable for the rest of the
     instance's life (proven over a simulated 1-second tick loop plus several further
     `Jsr` calls, no further failures). Root cause not fully chased into the vendored
     library (plausible candidate: `m68ki_cpu.pref_addr`'s "arbitrary" post-`Startup`
     sentinel interacting with the very first instruction fetch) — the fix is a
     one-line throwaway warm-up `Jsr(SNDH_FN_RESET, 0)` before the real init sequence,
     empirically validated rather than root-caused. **Worth a closer look if it
     recurs elsewhere**, but with one persistent machine for the whole game session
     (this design's whole point, §2), it only has to be dodged once.

Still open:

- **§7's open mappings are real gaps, not filled in here.** All fourteen `WAV_*`/tune
  symbols now have cited evidence (§7 is closed as of P3), but the level-theme
  `tune0`-`tune4` assignment still rests on naming-consistency rather than a separate
  instruction citation per level.
- **`Jsr`'s 1-second timeout (`JmpBinary(addr, 50*10)`)** — not hit in any P8 test
  (single-frame `music_tick`/`play_music` calls complete in a handful of instructions),
  but not stress-tested against pathological input either.
- **Sample-rate assumption**: `ym2149c`/`Mk68901`/`SteDac` all take `hostReplayRate` at
  `Startup()`; only ever exercised at 44100 Hz here (`syssnd_init` requests it but
  doesn't hardcode it — whatever SDL negotiates is what the engine gets). Fine as
  designed (`Startup` is called exactly once, in `syssnd_init`), just not tested at a
  second rate.
- **Audible correctness is not something P8's harness or the headless smoke run can
  check** — both prove the *engine* dispatches and transitions correctly by reading
  its RAM back, not that the *rendered waveform* sounds right. `xrick` is running
  interactively (real video + real audio via WSLg PulseAudio, confirmed to open
  without error) for the user's own by-ear pass, mirroring how `rick_dangerous.sndh`
  itself was verified (`assets-manifest.md`: "Fully verified by listening").
- **License attribution**: MIT requires the notice to ship with the binary/docs; add it
  to whatever the port's own README/about screen does for its existing SDL/zlib credits.

## 13. Sound mixing regressed from the WAV era — measured, not yet fixed

**Report (2026-09-10, post-ship): "if music is playing and I fire a bullet, I don't
hear the bullet."** True, and worth stating plainly against what came before: the
pre-T19 WAV-based `syssnd.c` mixed sounds in software (multiple independent PCM
buffers additively summed in the SDL callback), so any number of WAVs — music
sting, gunshot, footstep, pickup jingle — could and did play back simultaneously
without a second thought. That capability is gone. **This single `AtariMachine`
instance can only ever be "doing" one thing** from the small set `{idle, playing a
tracked song, playing a queued/active PCM sample}`, because that is a real
constraint of the one Atari ST YM2149 chip the instance emulates, enforced by the
*original, unmodified* `play_music` dispatch code running under 68000 emulation —
not something this port added. §2 already knew tracked music and SFX would share
voices; what wasn't measured until now is how *large* the resulting gap is in
practice.

**Measured with a throwaway harness** (same method as P8 — links the vendored
engine directly, drives it exactly like `syssnd.c`, reads engine RAM back; not
committed):

1. `sounds_setMusic(SND_TRACK_LEVEL0, 0)` (a level's one-shot theme, D1=0) holds
   `*(byte*)0x45002` (`kb/algo-music.md` §2's engine-state byte) at `1` for **815
   ticks at the engine's 50 Hz tick rate — 16.30 seconds** — before it drops back to
   `0` (idle) on its own.
2. Firing the bullet sound (`WAV_BULLET` = `{ track 8, type 2 — digi sample }`,
   `sounds.c`) *while* state is `1`: refused, silently, state unchanged. This is
   `play_music`'s own guard (`kb/algo-music.md` §3, both the type-1 and type-2
   branches): `if (*(byte*)0x45002 == 1) return;`.
3. Firing the identical call once state is back at `0`: succeeds immediately —
   state advances `0` → `2` (sample queued) → `0xFF` (sample playing) exactly as
   §3 documents.

So every level currently opens with a genuine **~16 second window in which no
gameplay sound effect can be heard at all** — not a rare edge case, but the common
case, since players routinely start moving and firing within the first few seconds
of a level. `screen_introMap` (`scr_imap.c`) starts this tune once, at the map-intro
screen that precedes gameplay; whether that screen's own on-screen duration is
long enough to fully absorb the 16.3 s window was not checked here — plausibly not,
since the report describes it happening during ordinary play, not during the intro
animation.

**Why this is not a bug to fix by correcting the engine.** The busy-guard is the
*actual original ST 68000 code*, byte-identical, already independently verified
faithful by P8 (§11: "exactly matching the original engine, not a bug in this
port"). Removing or loosening it would mean patching or bypassing genuine game
code, which is exactly the kind of change T1's ground rules (`PLAN.md`) exist to
require a deliberate, labeled decision about — not something to slip in as a "fix."

**Options for real mixing, not yet implemented (user decision pending):**

1. **A second, independent `AtariMachine` instance dedicated to SFX/samples,
   summed with the music instance's output in the audio callback.** Both instances
   run the same unmodified engine blob, so pitch/timbre stay period-accurate; this
   only removes the *"can't play while music plays"* restriction, not the
   synthesis itself. Clean call-site split already exists: `sounds_setMusic`
   (type-0 only) is the sole entry point for tracked music; every other call goes
   through `syssnd_play`/`syssnd_play_track` — route the former to engine A, the
   latter to engine B.

   **Important limit, easy to miss:** this buys music-plus-*one*-effect, not
   music-plus-*several*-effects. A single engine instance is still the same
   one-thing-at-a-time state machine among its *own* callers — a type-2 (PCM
   sample) call holds that instance's state busy at `2`/`0xFF` for the sample's
   whole duration (measured above: this is exactly what a gunshot is), refusing
   any other type-1/2 call on the *same* instance meanwhile. `WAV_BULLET`,
   `WAV_EXPLODE` and `WAV_DIE` (tracks 8/10/19) are all type-2 for this reason. So
   two SFX engine instances gives "music + one sample-type effect, and that effect
   blocks a second overlapping one until it finishes" — not true polyphony among
   effects. **Getting N simultaneously-audible one-shot effects needs N dedicated
   engine instances**, one per concurrently-playable slot, each ticked and mixed
   into the callback the same way. Non-sample SFX (type 1, e.g. `WAV_STICK`,
   `WAV_JUMP`) are cheaper to overlap *within* one instance — `play_music`'s type-1
   branch clears state back to `0` immediately after triggering (§3: `*(byte*)
   0x45002 = 0;` at the end of the type-1 case) and arbitrates via per-voice bits
   (`A6[0x18] |= 0x80`) across the alternating/dedicated voice slots instead — but
   that arbitration is still bounded by 3 real PSG voices per instance, and a
   type-2 call on the same instance still locks the whole instance out regardless
   of type-1's own accounting.
2. **Reserve one of the 3 PSG voices exclusively for SFX**, never letting tracked
   music's channel-arbitration touch it, closer to "one authentic chip used
   differently." Requires patching the disassembled channel-arbitration logic
   (`advance_music_channels` / the 3-entry channel-state table in `kb/algo-music.md`
   §2), i.e. deviating from bit-exact engine code, with the attendant risk of new,
   subtler bugs — the same class of risk this project has spent considerable effort
   avoiding elsewhere (`MEMORY.md` §8's method lessons).
3. **Leave it as-is**, since it is faithful to the original hardwakb/engine, and
   just make sure the ~16 s window is documented (this section) rather than
   silently discovered by playing.

No option has been implemented. This section exists to record the measurement and
the trade-offs so a decision can be made deliberately, per the project's standing
practice for anything that would touch verified-faithful original code.
