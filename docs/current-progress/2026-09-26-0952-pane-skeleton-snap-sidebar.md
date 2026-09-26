# Progress — 2026-09-26 09:52 UTC — pane skeleton, snap fix, sidebar flash, blue timestamps

## Workspace loading skeleton
- `project-workspace.tsx` loading state now mirrors the real 2-pane layout: back-link + title
  skeletons, then a grid with a video-card skeleton on the left and two fixed-height card
  skeletons (transcript, review) on the right, using `WORKSPACE_PANE_CARD`.

## Snap
- Restored `scroll-snap-stop: always` on the panes and the top stop. Without it a fling could
  skip the transcript and land on Review when scrolling back to the top.
- Top stop still wraps the back link + header, so "< Projects" stays reachable.

## Sidebar hard-refresh flash
- Root layout injects a blocking script that sets `data-sidebar="collapsed"` before first paint.
- `globals.css` applies `width: 64px !important` to `.app-sidebar-rail` under that attribute, so
  the first paint is already collapsed.
- `AppShell` removes the attribute on the next frame (after React has applied the stored width),
  handing control back to framer-motion.

## Colour
- New `--time` token = the original project blue (`oklch(0.54 0.17 258)`, lighter in dark mode);
  transcript, findings and heatmap readout timestamps use `text-time`.
- Video.js big-play button back to the default grey (`rgb(82 82 82)` / hover `rgb(107 107 107)`).

## Avatar size
- Header 38 → 44 (button h-12), profile preview 96 → 128, customizer preview 128 → 160.

## Scroll fade
- Added `py-2` inside the transcript, review and findings scroll bodies so the fade mask no
  longer clips the first/last row.
- Removed `scroll-fade-y` from the Review card (requested).

## Verified
- Web: `tsc --noEmit` clean, `oxlint` clean, `next build` passes.
