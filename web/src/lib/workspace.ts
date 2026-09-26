/**
 * Shared fixed height for the project workspace panes.
 *
 * The source video card and every card in the right-hand pane use this exact
 * class so they line up regardless of their content, and each card scrolls
 * internally instead of stretching the page. `min()` keeps it usable on short
 * viewports without ever letting a card collapse.
 */
export const WORKSPACE_PANE_HEIGHT = "h-[min(72vh,40rem)]";

/** Make a card a fixed-height flex column whose body scrolls. */
export const WORKSPACE_PANE_CARD =
  `${WORKSPACE_PANE_HEIGHT} flex min-h-0 flex-col`;
