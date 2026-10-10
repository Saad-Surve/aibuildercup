# Calendar: Teams-style week time-grid

## What I did (web only, no contract/backend change)

Rebuilt the week view as a real time grid instead of stacked day columns:

- **Time gutter left**: 12am–11pm hour labels, 48px per hour, same 7-column track
  (`3.5rem repeat(7, minmax(0, 1fr))`) for the header and the body so they align.
- **Posts pinned to their times**: each slot is absolutely positioned at its
  `scheduledAt` with a 30-minute assumed height; overlapping slots pack into
  side-by-side lanes (`layoutDaySlots`: overlap clustering + greedy lane packing).
  Chips show time + platform logo + title, with the deep-link highlight ring.
- **Click-to-schedule at a time**: every hour cell is a real `<button>` —
  pointer clicks snap to the nearest quarter hour, keyboard Enter takes the hour
  start — and opens the create dialog prefilled with that exact datetime.
- **Now-line**: a red current-time rule on today's column when this week is shown.
- **Smart initial scroll**: the grid opens scrolled to an hour before the week's
  earliest slot (7am default); scroll position only, no state, no lint conflict.
- The old padded week grid is gone; month and day views are unchanged (month block
  simplified back to month-only).

## Verification

- `bun run lint` clean; `bun run lint:eslint` 0 errors (pre-existing `<img>`
  warning only); `bun run build` clean; dev `/calendar` serves 200.

## Not done / next step

- Same as before: authenticated end-to-end pass with a signed-in session.
