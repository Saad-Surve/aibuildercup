# 2026-10-12 01:50 — Divider for coming-soon, Post button placement, single-account default

Small follow-ups, uncommitted. Continues `0135`.

## Changes (web only, `oxlint` + `tsc` clean)

1. **Divider for the rest** (`account-connections.tsx`): added a second
   `<Separator />` before the coming-soon placeholder grid, so all three blocks
   (YouTube / Writing platforms / coming soon) are divider-separated inside the
   kept outer card.
2. **Post button placement** (`draft-workspace.tsx`, `crosspost-card.tsx`): the
   "Post this draft" trigger moved into the draft header's right-side button row,
   immediately right of "Edit brief" on the same line. The closed state no longer
   renders its own wrapper div (it returns `DisabledReason`, a fragment outside
   read-only mode, so `span` nesting stays valid); trigger resized to `xs outline`
   to match the row. The dialog itself portals, so placement only affects the
   trigger.
3. **Single-account default** (`crosspost-card.tsx`): when the chosen platform has
   exactly one connected account, it is preselected instead of an empty dropdown.

## Tree

6 modified files (prior 5 + `draft-workspace.tsx`); no backend change this round.
