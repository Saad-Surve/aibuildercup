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
 * A right-hand pane that pins to the same top offset as the video card while
 * the page scrolls. Panes stack in DOM order, so the next one slides over the
 * previous, and a trailing spacer (`WORKSPACE_PANE_STACK_SPACER`) gives the
 * last pane room to reach the top.
 */
export const WORKSPACE_PANE_STICKY = `${WORKSPACE_PANE_CARD} lg:sticky lg:top-20`;

/** Extra room after the last pinned pane so it can be pulled up level with the video. */
export const WORKSPACE_PANE_STACK_SPACER = "hidden h-[28vh] shrink-0 lg:block";
