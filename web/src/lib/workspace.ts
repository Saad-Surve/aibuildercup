/**
 * Shared height for the project workspace panes.
 *
 * At `lg` the video card and every card in the right-hand pane use an exact
 * fixed height so they line up, and each card scrolls internally instead of
 * stretching the page. Below `lg` the same cap applies as a `max-height`
 * instead: the pane grows with its content and only scrolls once it is tall,
 * which stops a phone from showing four nested scroll views. `min()` keeps it
 * usable on short viewports without ever letting a card collapse.
 */
export const WORKSPACE_PANE_HEIGHT =
  "max-h-[min(72vh,40rem)] lg:h-[min(72vh,40rem)] lg:max-h-none";

/** Flex column whose body scrolls once the pane is taller than its cap. */
export const WORKSPACE_PANE_CARD = `${WORKSPACE_PANE_HEIGHT} flex min-h-0 flex-col`;

/**
 * A right-hand pane that snaps its top to the video card's top while scrolling
 * normally (the page-level `scroll-snap-type: y proximity` lives in
 * `globals.css`). Panes do not overlap: each one scrolls up and out as the next
 * arrives.
 */
export const WORKSPACE_PANE_SNAP = `${WORKSPACE_PANE_CARD} lg:snap-start lg:snap-always lg:scroll-mt-20`;

/**
 * Snap target for a card that scrolls with its own height (placeholder modules):
 * its top snaps level with the video card without forcing a fixed pane height.
 */
export const WORKSPACE_SNAP_TARGET =
  "lg:snap-start lg:snap-always lg:scroll-mt-20";

/** Extra room after the last pane so it can snap level with the video card. */
export const WORKSPACE_PANE_STACK_SPACER = "hidden h-[55vh] shrink-0 lg:block";
