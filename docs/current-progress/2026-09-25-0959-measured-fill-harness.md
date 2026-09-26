# Progress — 2026-09-25 09:59 UTC — Measured fill, repro harness

Uncommitted (not requested — commit only on ask). No backend changes.

## The gap, settled with measurements (not guesses)

- Built a headless-Chrome repro harness (temp dir, outside the repo) using
  the project's own video.js build, the compiled Tailwind utilities, and
  the exact Card class strings: across 16:9 and 4:3 videos the card is
  pixel-tight (`cardH = headerH + playerH`, `gapBelowVideo = 0`). The card
  structure cannot produce the whitespace — it was page void below the
  panes, and the player already hugs content via the aspectRatio fix.
- Screenshots + DOM metrics verified each step (4:3 frame fills edge to
  edge, red-border test frame intact).

## Transcript uses the full available height

- `SplitPanes` now measures video height AND the document-relative pane top
  (viewport-relative math would feedback-loop on scroll) and fills the pane
  to `max(videoH, viewportRemainder - 48, 360)` — but only when content is
  actually longer (short content stays natural, no stretched empty card).
- Guards: `xl`-only, MutationObserver for local edits (typing/add/delete
  don't re-render the parent), ResizeObserver + resize listener, every set
  change-guarded. Verified in the harness: 64-row pane ends exactly at
  `viewport - 48` while the video keeps its natural height.

## Verification

- Web: `oxlint`/`oxfmt` clean, `eslint` 0 errors (1 pre-existing `<img>`
  advisory), `bun run build` passes.
- Harness numbers: `paneH=772, cardBottom=1052=1100-48` with video at 520.

## Gotchas

- A bad edit left duplicated JSX closers in project-workspace (caught by
  lint, fixed). When replacing whole blocks, double-check the tail.
- Repro lives in the OS temp dir (`opencode/repro`), not the repo — keep
  it out of git. Puppeteer-core + downloaded video.js copies live there.

## Next

- Caption `<track>` from transcription; backend-generated `thumbnail` assets;
  per-card delete menus; Audience/Connections/Settings pages (unchanged).
