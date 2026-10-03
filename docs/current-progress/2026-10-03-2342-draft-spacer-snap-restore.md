# Draft workspace: restore a smaller bottom spacer + snap targets

## What I did

Follow-up to the previous note. Removing the bottom spacer entirely fixed the "scrolls too far
below the cards" complaint but also killed the page scroll, so the snap stopped engaging. Restored
a *smaller* spacer and the snap targets.

- Added `DRAFT_PANE_STACK_SPACER = "hidden h-[20vh] shrink-0 lg:block"` in `lib/workspace.ts`.
  The video-studio spacer stays at `55vh` (untouched); the draft grid only needs enough page
  scroll to bring the editor card up to its snap point.
- Restored `lg:snap-start lg:snap-always lg:scroll-mt-20` on the editor card (via `EDITOR_HEIGHT`)
  and used the existing `WORKSPACE_SNAP_TARGET` on the generating / empty-state cards.
- Re-added the spacer element at the bottom of the draft workspace.

## Files

- `web/src/lib/workspace.ts`
- `web/src/components/projects/draft/free-flow-editor.tsx`
- `web/src/components/projects/draft/draft-workspace.tsx`

## Decisions / gotchas

- 20vh is a heuristic: enough to reach the snap point on common viewports without the old ~55vh of
  empty page. If it still feels short/long, this one constant is the knob.
- Only the editor card snaps; the chat card is `lg:sticky lg:top-20` and rides along.

## Verification

- `tsc` clean, `oxlint` clean, `next build` succeeds.
- Backend untouched.

## Not done / next step

- Not click-tested in a browser; the spacer height may want a visual tweak.
- Uncommitted.
