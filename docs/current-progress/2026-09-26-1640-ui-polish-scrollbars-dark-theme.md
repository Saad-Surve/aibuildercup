# Progress — 2026-09-26 16:40 UTC — UI polish: scrollbars, avatar wrap, project cards, dark theme

## What changed

### Scrollbars hidden in app pages
- `AppShell` now adds `no-scrollbar` to `document.documentElement` on mount, removing it on unmount. This hides the browser scrollbar in all authenticated app pages (Project workspace, Profile, Dashboard, etc.) while preserving scroll behaviour. The presence of stacked workspace panes on the right already signals that the page scrolls.

### Avatar customizer — no horizontal scroll
- Replaced `overflow-x-auto` with `flex-wrap` on the part-group picker row in `AvatarCustomizer`. The individual part buttons now wrap to multiple lines instead of scrolling horizontally inside the dialog.

### Projects sorted newest-first
- `ProjectsPage` now sorts the project list by `createdAt` descending using `Array#toSorted()` before rendering.

### Project card metadata
- `ProjectCard` now queries the project's assets (deduped by React Query with the same key `ProjectThumb` uses) and displays a 3-column metadata grid:
  - **Duration** — from `source_video.durationMs` via `formatTimestamp`
  - **Size** — from `source_video.sizeBytes` via `formatBytes`
  - **Uploaded** — from `source_video.createdAt` (falls back to `project.createdAt`) formatted as `d MMM yyyy`
- `ProjectCardSkeleton` updated to mirror the new layout: two description skeleton lines + a 3-column grid of `h-8` skeleton blocks.

### Dark theme softened
- Raised dark-mode background lightness from near-pure-black (`oklch(0.16 0 0)`) to a dark charcoal (`oklch(0.22 0 0)`).
- Card, popover, sidebar, secondary, muted, and accent surfaces lifted proportionally (`0.24` → `0.26`, `0.18` → `0.24`, `0.24` → `0.30`). Much easier on the eyes.

## Verified
- `bun run lint` (oxlint) clean
- `bunx tsc --noEmit` clean
- `NODE_OPTIONS=--max-old-space-size=6144 bun run build` passes

## Next
- Nothing outstanding for this request.
