# Scroll chaining fix on transcript panes

## Root cause

Verified from the user's screenshot: the layout itself was correct — collapsed rail pinned
full-height, capped transcript pane with its own scrollbar. The real mechanism: **nested
scroll containers without overscroll containment**.

On small screens the stacked video + toolbar + capped transcript card exceed the viewport, so
the window is scrollable *behind* the pane. Wheeling inside the transcript to its limit
hands the gesture to the window (**scroll chaining**), and the whole app — video, shell,
sidebar — moves up. That is the "it allows me to scroll for some reason".

It never shows on big screens because the entire 12-row card fits inside its cap: there is
no nested scroller, so nothing to chain out of — just ordinary page scroll.

## Fix (two one-word classes, no shell/global changes)

- `web/src/components/projects/transcript-editor.tsx` — scroller is now
  `… overflow-y-auto overscroll-y-contain …`.
- `web/src/components/projects/transcript-panel.tsx` — same shape, same leak, same fix.

`overscroll-behavior-y: contain` traps wheel/touch gestures that start inside the pane; the
window only scrolls from gestures that start outside it (e.g. over the video area), which is
also how you still reach everything above.

## Verified

- `bunx tsc --noEmit` clean; `bun run lint` clean; eslint only the pre-existing
  `project-card.tsx` warning.
- `overscroll-y-contain` confirmed compiled (`overscroll-behavior-y: contain`) and present in
  the server + client bundles; both routes return 200.

## Not done

- Not committed.
- Deliberately not touching pane heights or the shell: the chaining trap is the precise fix
  for the reported symptom.
