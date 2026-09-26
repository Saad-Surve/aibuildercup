/**
 * Shared fixed height for the project workspace panes.
 *
 * The source video card and every card in the right-hand pane use this exact
 * class so they line up regardless of their content, and each card scrolls
 * internally instead of stretching the page. `min()` keeps it usable on short
 * viewports without ever letting a card collapse.
 */
export const WORKSPACE_PANE_HEIGHT = "h-[min(72vh,40rem)]";

/** Fixed-height flex column whose body scrolls. */
export const WORKSPACE_PANE_CARD = `${WORKSPACE_PANE_HEIGHT} flex min-h-0 flex-col`;

/**
 * A right-hand pane that snaps its top to the video card's top while scrolling
 * normally (the page-level `scroll-snap-type: y proximity` lives in
 * `globals.css`). Panes do not overlap: each one scrolls up and out as the next
 * arrives.
 */
export const WORKSPACE_PANE_SNAP = `${WORKSPACE_PANE_CARD} lg:snap-start lg:scroll-mt-20`;

/** Extra room after the last pane so it can snap level with the video card. */
export const WORKSPACE_PANE_STACK_SPACER = "hidden h-[28vh] shrink-0 lg:block";
