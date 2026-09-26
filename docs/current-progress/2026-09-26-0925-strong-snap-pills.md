# Progress — 2026-09-26 09:25 UTC — stronger snap, bigger pane gap, evidence icons, pill sizes

## Stronger snapping
- `globals.css`: `scroll-snap-type: y proximity` → `y mandatory`.
- Added a snap stop at the top of the page (the `PageHeader` wrapper, `lg:snap-start lg:snap-always
  lg:scroll-mt-20`) so mandatory snapping can rest on the header instead of jumping straight to
  the first pane.
- `WORKSPACE_PANE_SNAP` now also sets `scroll-snap-stop: always` (`lg:snap-always`), so a fast
  gesture still stops at each pane.

## Right-pane gap
- Right column `space-y-6` → `space-y-10`.

## Findings evidence icons
- "Show evidence" / "Hide evidence" now carry `EyeIcon` / `EyeOffIcon` (swapped by the `open`
  state).

## Leftover pill/skeleton polish (from the earlier prompts)
- Review severity filter chips `h-6` → `h-7` (matches `size="sm"` buttons).
- `ProjectStatusBadge` (`h-5`) → `h-7 px-2.5`, so the status pill in the project header matches
  the action buttons.
- Review loading skeleton `h-32` → `h-full min-h-40`, so it fills the fixed-height review card
  instead of leaving a large empty area.

## Verified
- Web: `tsc --noEmit` clean, `oxlint` clean, `next build` passes.
