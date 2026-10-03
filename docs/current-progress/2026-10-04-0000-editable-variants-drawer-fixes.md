# Draft editor round 3: editable variants, block-level detection, drawer polish

## What I did

Fixed the batch of issues from the latest feedback.

- **Drawer no longer blurs the page.** It is now a non-modal drawer (`modal={false}`), with no
  backdrop and `initialFocus={false}`. The document stays visible and interactive, so you can see
  the change while cycling. `disablePointerDismissal` keeps it from flickering when you click
  another group; close with the X or Escape.
- **Full text in the drawer.** Removed `truncate` / `line-clamp-2` on option rows and the 160-char
  slice on the chat context preview. Everything wraps and shows in full.
- **Focus-ring conflict gone.** Because the drawer no longer auto-focuses its first button, there is
  no stray focus ring competing with the selected option. Variants also use a text cursor now.
- **Variants are editable in place.** Removed `contenteditable="false"` from variant elements (the
  dots stay non-editable). `syncVariantsFromDom` folds in-place edits back into the group payload
  before serializing: editing an original/AI version forks a new **user** version (nothing is
  overwritten); editing an existing user version updates it. So you can now manually rewrite an
  AI-changed phrase and it is saved alongside the AI revisions.
- **Vertical paragraph marker only for whole paragraphs.** `markdownToHtml` now checks whether a
  whole-line group is *alone in its block*. A group that is merely one line of a multi-line
  paragraph renders inline and the paragraph is not split; a single-line block that is entirely a
  group still gets the paragraph marker. Headings stay heading-level.
- **No phantom context.** The auto-context now ignores selections that touch a variant (checked at
  both range endpoints), and wrapping a selection leaves a caret instead of a lingering selection.
  Combined with variants being editable, clicking a group no longer populates the chat context.
- **Chat rewrites target the block.** When sending with a selection, the workspace finds the block
  the selection came from and passes its `blockId` to `assist`, so the assistant revises that block
  in place instead of appending a new paragraph.
- **Revised versions: underline only.** Dropped the background tint on `[data-changed="true"]`
  (and the selection background); the signal-coloured dashed underline carries the state, with only
  a thin ring for the currently selected group.

## Files

- `web/src/lib/draft-content.ts` — editable variant markup, `syncVariantsFromDom`, block-alone
  detection in `markdownToHtml`.
- `web/src/components/projects/draft/free-flow-editor.tsx` — sync on commit, no selection collapse
  on click, endpoint-aware context guard, non-modal drawer.
- `web/src/components/ui/drawer.tsx` — non-modal, no backdrop, `initialFocus` default false.
- `web/src/components/projects/draft/alternatives-panel.tsx` — full option text.
- `web/src/components/projects/draft/draft-chat.tsx` — full context text.
- `web/src/components/projects/draft/draft-workspace.tsx` — `findBlockForSelection`, block-targeted
  assist.
- `web/src/app/globals.css` — no version background, text cursor, non-selectable dots.

## Decisions / gotchas

- Forking on the first manual edit (rather than overwriting) is what keeps the original and every
  AI version. After the fork the active option is a user version, so later keystrokes update it.
- The chat still stores block-level versions on the backend (the editor no longer surfaces the old
  version dropdown); inline groups are the visible revision history.

## Verification

- `tsc` clean, `oxlint` clean, `eslint` 0 errors (1 pre-existing `<img>` warning), `next build`
  succeeds.
- Block-level detection checked with a throwaway Bun script (deleted): single-line group →
  paragraph marker; group mid multi-line paragraph → inline and not split; heading → heading;
  group followed by text → inline.
- Backend untouched.

## Not done / next step

- Not click-tested in a browser. Worth eyeballing: typing inside a variant (caret vs. dots),
  drawer staying open while editing, and the non-modal drawer's outside-click behaviour.
- Uncommitted.
