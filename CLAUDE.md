# CLAUDE.md

This file provides guidance to Claude.

## Key Rules

- be consise, do not be verbose
- keep thing short but complete
- **NEVER ASSUME ANYTHING — ALWAYS CHECK.** Before writing any claim, run the check
  that proves it. This applies to every claim, including ones that "obviously" follow:
  - never write "verified" / "confirmed" / "checked" unless the check actually ran
  - never state a count, address, size or constant without reading it from the binary,
    from Ghidra, or from the file — not from memory and not from another document
  - never conclude a thing is unused, absent, stale or safe to delete without an xref,
    a `git ls-files`, or an equivalent lookup
  - when two sources disagree, go to the disassembly; do not pick the more plausible one
  - if a check is impractical, say so explicitly and mark the claim as unverified
- do not guess, when in doubt ask me
- do not modify `CLAUDE.md` nor `README.md` — *(exception: the "never assume" rule above
  was added on 2026-08-29 at the user's explicit instruction; this file is otherwise
  still off limits)*
- maintain project high-level memory and key knowledge in `MEMORY.md`
- keep track of what we want to achieve and steps and progress in `PLAN.md`
