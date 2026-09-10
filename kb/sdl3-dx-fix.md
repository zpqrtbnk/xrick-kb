# SDL3 Direct3D11 streaming-texture corruption (Windows-only rendering bug)

## Symptom

Windows build only (WSL build is fine): sprites moving vertically leave
"traces" (torn/ghosted duplicates) behind them; scrolling breaks the display
entirely. Easiest repro: on submap 1, do nothing but press `P` (pause), wait,
press `P` again to unpause. The `PAUSED` overlay does not cleanly disappear —
the screen flickers, alternating between what looks like the freshly
rendered frame and a stale/old frame, even though the new frame *was*
rendered.

## Root cause

`sysvid_update()` (`xrick/xrick/src/sysvid.c`) locked the **entire** texture
every call, then only painted the pixels belonging to the game's dirty-rect
list into the locked buffer:

```c
SDL_LockTexture(texture, NULL, (void **)&pixelx, &pitch);   /* NULL = whole texture */
/* ...loop over `rects`, writing only those sub-regions into pixelx... */
SDL_UnlockTexture(texture);
```

Passing `NULL` expands to `{0, 0, texture->w, texture->h}`
(`SDL_render.c:2639-2644` in the vendored SDL3 source,
`vcpkg_installed/vcpkg/blds/sdl3/src/.../src/render/SDL_render.c`). During
normal gameplay the dirty-rect list is *not* the full screen — it's a
handful of small per-entity boxes plus the status bar, built in
`game_paintEntities()` (`xrick/xrick/src/game.c:849-861`, `game_rects = r`
where `r` is `draw_STATUSRECT` chained to `ent_rects`).

So every frame: lock the whole texture, but only fill in a few small
rectangles of it.

Whether that's safe depends entirely on how the active SDL3 renderer backend
implements `LockTexture`/`UnlockTexture` for a streaming texture — and here
the two backends differ substantially.

### Direct3D11 backend (Windows default)

`SDL_render_d3d11.c` is first in SDL3's renderer probe order
(`SDL_render.c:110-112`, `render_drivers[]` lists `D3D11_RenderDriver`
before D3D12/D3D/OpenGL), so it's what `SDL_CreateRenderer(screen, NULL)`
picks on Windows.

- `D3D11_LockTexture` (`SDL_render_d3d11.c:1754`) creates a **brand-new
  `D3D11_USAGE_STAGING` texture sized to the locked rect on every single
  call**, maps it **write-only** (`D3D11_MAP_WRITE`, no read-back of
  existing contents), and hands back a pointer into that fresh allocation.
  Its initial contents are whatever memory the driver returned — not the
  previous frame's pixels, and not zeroed.
- `D3D11_UnlockTexture` (`SDL_render_d3d11.c:1835`) then does
  `ID3D11DeviceContext_CopySubresourceRegion` of the **entire staging
  texture** back onto the corresponding region of the main texture.

Consequence: locking the whole texture but only writing a few small rects
into it means the rest of that staging buffer — uninitialized/leftover GPU
memory — gets unconditionally stamped over the real texture on unlock. The
staging texture is created and destroyed every frame, so the driver is very
likely recycling the same one or two freed allocations; that's why the
result looks like *flicker between an old and a new frame* rather than
random static — the "garbage" is actually a recently-freed, slightly-stale
frame capture.

### OpenGL / software backends (what WSL uses)

D3D11/D3D12/D3D aren't compiled in on Linux, so SDL3 falls back to
`SDL_render_gl.c`. There, a streaming texture keeps **one persistent CPU
buffer for the lifetime of the texture** (`GL_TextureData`), and unlock
issues `glTexSubImage2D` scoped to exactly the locked rect
(`SDL_render_gl.c:~805`). The software renderer (`SDL_render_sw.c`) is
similar: the texture is backed by a single persistent `SDL_Surface`
(`texture->internal`) for its whole life, and `SW_LockTexture` just returns
a pointer into it — nothing is ever reallocated. In both cases, pixels
outside the locked rect are simply never touched, frame after frame, so
stale-but-valid data from previous frames survives untouched. This is why
WSL never showed the bug.

### Why the pause repro is such a clean reproducer

`screen_pause()` (`xrick/xrick/src/scr_pause.c:54`) sets
`game_rects = &draw_SCREENRECT` (the full 320x200 screen, a single rect)
unconditionally on both pause-in and pause-out — so that one transition
frame is a full-screen lock that gets fully painted and is correct. But the
very next frame, gameplay resumes normal per-sprite dirty-rect updates via
`game_paintEntities()`, which immediately hits the bug described above —
most of the screen gets stamped with stale/garbage data from a recycled
D3D11 staging allocation. The alternation between "one good full-screen
frame" and "next frame mostly stomped" is the flicker.

This also explains the movement/tearing symptom directly: moving sprites
produce small per-entity dirty rects (not full-screen), so every such frame
partially corrupts the display outside those rects, leaving "traces".
Scrolling multiplies the number and pattern of dirty rects, so it "breaks
everything".

## Fix

Lock and paint **per dirty rect** instead of locking the whole texture once
and only partially filling it. For each rect in the game's dirty list, call
`SDL_LockTexture(texture, &that_rect, ...)`, paint exactly that rect's
pixels, then `SDL_UnlockTexture`. This way the D3D11 staging texture is
allocated at exactly the size of the rect being painted and gets **fully**
written before it's copied back — nothing in it is ever left uninitialized.
This is also how `SDL_UpdateTexture` documents itself to behave and how the
OpenGL/software backends already work.

Note: when locking a sub-rect (rather than the whole texture with `NULL`),
the pointer SDL returns is the **top-left of that rect**, not an offset into
a full-texture buffer — this is the documented and cross-backend-consistent
`SDL_LockTexture` contract (confirmed in both `D3D11_LockTexture` and
`SW_LockTexture`). The previous code's manual `rect->y * pitch + rect->x *
sizeof(U32)` offset was only correct because it always locked the whole
texture (`NULL`) and needed to seek into it. Locking per-rect means that
offset must be dropped — the destination write starts at pixel `(0,0)` of
the returned buffer.

Implemented in `xrick/xrick/src/sysvid.c` (`sysvid_update`).

## Resolution

Confirmed fixed: user rebuilt the native Windows (`vcxproj`) build with this
change and re-ran the pause repro (submap 1, `P`, wait, `P`) — no more
flicker, and sprite movement/scrolling no longer tear or leave traces. WSL
build was also rebuilt and run (`make` + `./xrick -submap 1`) with no
regressions before the Windows test.

This closes the "open, unexplained Windows-specific rendering defect" noted
in `kb/build.md` §2 (scrolling glitches / sprite misalignment, WSL-clean but
Windows-broken) — that entry is now stale and should be updated to point
here.
