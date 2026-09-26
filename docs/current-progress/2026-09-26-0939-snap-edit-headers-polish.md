# Progress — 2026-09-26 09:39 UTC — snap fix, edit project, headers, polish batch

## Snap
- The top snap stop now wraps the back link **and** the header, so mandatory snapping rests
  showing "< Projects" instead of skipping it.
- Softer spring: dropped `scroll-snap-stop: always` and added `scroll-behavior: smooth`.
  Mandatory snap is kept, but a fling can now glide across panes.

## Rounding
- `--radius` 0.5rem → 0.375rem (cards/dialogs/inputs all follow).

## Status pills (no pink everywhere)
- `ProjectStatusBadge` now uses semantic colours: ready green, processing/uploading amber,
  partial orange, failed red, draft/archived grey. Height already matched buttons.
- `ProcessingStatusCard` in-progress pill + spinner moved from signal (pink) to amber.

## Project title/description editing
- Wired the existing `EditProjectDialog` into the workspace header actions (status · Edit ·
  Delete). Uses the already-added `PATCH /projects/{id}` `updateProject`.

## Sidebar collapse icon
- Now `SidebarRight01Icon` when collapsed and `SidebarLeft01Icon` when expanded (was the same
  icon both ways).

## Removed tile entrance animation
- Dashboard and Projects dropped the `motion.div` fade/slide-up wrapper around `ProjectCard`.

## Review card
- Removed the `ReviewerStrip` dimension list (dimensions already appear in the heatmap table).
- Status moved next to the "Review" title behind a divider; the "6 dimensions · 1 transcript
  window" line is gone.
- "Run analysis" gained a `SparklesIcon`; once any run exists the label is "Run analysis again".

## Transcript card
- Segment count · duration · language moved onto the "Transcript" title line behind a divider.

## Findings card
- "N of M observations, worst first." moved onto the "Findings" title line behind a divider.
- Evidence toggle icons switched to `ViewIcon` / `ViewOffIcon`.

## Scroll fade
- New `.scroll-fade-y` mask (0.6rem) on the transcript, review and findings scroll panes.

## Verified
- Web: `tsc --noEmit` clean, `oxlint` clean, `next build` passes.
