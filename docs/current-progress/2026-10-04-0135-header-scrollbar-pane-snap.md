# Header nav scrollbar + module pane snap

## What I did

Two fixes on the `headerTabs` header strip (web only).

- **Scrollbar inside the header nav.** The header slot was `overflow-x-auto`, which per the CSS
  overflow rule forces `overflow-y` to `auto` too; a button's `active:translate-y-px` then created
  a 1px scrollable overflow and a scrollbar appeared on click. The slot now carries `no-scrollbar`
  (the repo's existing utility) and a little vertical padding, so no scrollbar chrome shows while
  genuine horizontal overflow can still be scrolled.
- **Scroll snap on tab switch (the part I missed).** `scrollIntoView` was not happening. The right
  pane now has a ref and, when `headerTabs` is on, switching a module calls
  `scrollIntoView({ block: "start" })` on it. That honours the pane's existing
  `lg:snap-start lg:scroll-mt-20` snap stop, so the pane's first block lands just under the sticky
  header instead of the page jumping to the very top.

## Structural changes

- `app-shell.tsx` (header slot classes), `video-studio.tsx` (pane ref + scroll effect). No backend,
  contract, or infra changes.

## Verification

- `bunx tsc --noEmit` clean; `bun run lint` clean; `bun run lint:eslint` 1 pre-existing `<img>`
  warning; `bun run build` succeeds.

## Not done / next step

- None for these two fixes.
