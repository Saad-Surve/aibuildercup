# Progress — 2026-09-20 23:54 IST

Status: **flow animation fixed and verified headless; work committed on a new
branch. Not pushed.**

## Git (as requested)

- `git stash -u` backup → new branch `feature/landing-flow` → stash popped →
  local commit `e9e8606` with the full landing state (page, backgrounds,
  brand SVGs, consolidated progress note; `fixtures/cassettes/llm/` excluded
  as runtime debris).
- The animation fix then landed as a second local commit `a2418a8`.

## Why the stage was blank

- The hook ran its effect once on mount with `[stageRef]` deps. At mount,
  auth is still "loading", so `LandingPage` renders the loading screen
  WITHOUT the stage → `stageRef.current === null` → effect bailed and never
  re-ran when the stage later mounted. Dead on arrival, no errors.
- Secondary fragility: an IntersectionObserver visibility gate froze the
  timeline whenever the stage wasn't intersecting at fire time.

## Fix

- `useFlowStage()` now uses a **callback ref**: the stage node lands in
  state, effect deps `[stage]` re-run the moment the stage mounts. Cleanup
  resets dot/center inline styles.
- Removed the IO gate entirely (rAF already pauses in background tabs).
- Timeline unchanged, per the orchestration spec: inputs 0/0.7/1.4s,
  processing pulse (scale 1.00→1.02→1.00 + glow) 2.1s, outputs 2.6–5.6s,
  settle to 6.5s, seamless loop; easeInOutCubic packets follow real path
  geometry container-relatively.

## Verification (headless Edge via puppeteer-core, since removed)

- Instrumented run against localhost:3000: 449 frames, **all 8 packets
  visibly active during the cycle** (`activeCounts` ≥33 frames each),
  `centerPulsed: true`, reduced-motion false, loop continuous.
- `bun run build`, `oxlint`, `oxfmt` all clean; test script + dev dep
  removed before committing.

## Not done / next

- Branch `feature/landing-flow` pushed to origin (f6df1b8; amend folded in:
  locale hover-cycle 2200→1400ms, chat bubbles + typing indicator get a
  smooth fade/slide entry — the input already clears via `setDraft("")` on
  every send).
- Merged/pushed the flow animation fix and verified headless; user confirmed
  it works.
