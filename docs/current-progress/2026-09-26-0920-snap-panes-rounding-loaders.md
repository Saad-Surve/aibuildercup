# Progress — 2026-09-26 09:20 UTC — snap (not stack), less rounding, faster loaders

## Panes: snap instead of stack
- `lib/workspace.ts`: `WORKSPACE_PANE_SNAP` replaces the sticky card class
  (`lg:snap-start lg:scroll-mt-20`). Transcript / Review / Findings now scroll in normal flow
  and snap their top level with the video card — no more overlap.
- `globals.css`: `html { scroll-snap-type: y proximity }` at `lg`. `proximity` only pulls when a
  stop lands near a boundary, so other pages (no snap-align elements) are unaffected.
- The trailing `WORKSPACE_PANE_STACK_SPACER` (`h-[28vh]`) stays so the last pane has room to
  reach the snap position.

## Less rounded
- `--radius` 0.625rem → 0.5rem; `Card` `rounded-xl` → `rounded-lg` (and its image corners).
- All non-landing `rounded-xl` → `rounded-lg` (dialogs, alert dialog, empty state, onboarding
  card, avatar part preview, video player, dropzone, project card). Landing page left alone.

## Faster loading affordances
- `@theme`: `--animate-pulse` 2s → 1.1s, `--animate-spin` 1s → 0.6s. Every skeleton and spinner
  uses these utilities, so they all speed up together.

## Transcript affordance
- Timestamp gets `group-hover:underline` (row is `group`), so it reads as clickable.

## Heatmap ruler alignment
- `TimeRuler` was spanning the full card width including the 8.5rem label column, so `0:00` sat
  far left of the actual track. It now mirrors the `TrackRow` layout (inset + label spacer +
  gap + track + score spacer) and pins the first/last tick to the track edges.

## Verified
- Web: `tsc --noEmit` clean, `oxlint` clean, `next build` passes.
