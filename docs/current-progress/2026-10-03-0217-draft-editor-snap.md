# Draft editor: restore page snap

## What I did

The Obsidian-style editor rewrite dropped the pane's snap classes, so the draft page scrolled
freely and the editor never snapped level with the chat. Added
`lg:snap-start lg:snap-always lg:scroll-mt-20` back to the editor card (it keeps its
`min(78vh,44rem)` height) and added the `WORKSPACE_PANE_STACK_SPACER` after the two-column grid
so the editor can actually reach the top.

## Verification

- Web: `tsc` clean, `oxlint` clean, `eslint` 0 errors (one pre-existing `<img>` warning),
  `next build` succeeds.

## Not done / next step

- Committed and pushed.
