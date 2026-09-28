# Widen the caption popover/menu

## What I did

The "Burn captions onto video" entry was crammed because its containers were too narrow.

- `web/src/components/projects/transcript-panel.tsx` — the Export `DropdownMenuContent` had no
  explicit width, so it collapsed to the narrow Export trigger (base-ui `w-(--anchor-width)`).
  Set `className="w-64"` so the "Burn captions onto video" row fits on one line.
- `web/src/components/projects/caption-burn-dialog.tsx` — the render dialog was capped at
  `sm:max-w-3xl`; raised the cap to `sm:max-w-5xl`.

## Structural changes

- UI only. No contract, schema, or backend changes.

## Not done / next step

- Confirm which surface the user meant (Export dropdown vs the render dialog) and drop the other
  change if it was unwanted. Verify visually at desktop and narrow widths.
