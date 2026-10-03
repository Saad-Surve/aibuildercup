# Draft studio feedback round: no sound, dashed underlines, alternatives drawer, chat polish

## What I did

Follow-up polish on the free-flowing draft editor from the previous note.

- **Sound removed completely.** Deleted `web/src/lib/alternative-sound.ts`; dropped the Web Audio
  cue, the mute store, the speaker toggle in the panel, and every reference. Cycling is silent.
- **Dashed underline.** The wavy SVG mask on `.draft-variant::after` (and the heading variant) is
  replaced with a simple `border-top: 1.5px dashed var(--alt-color)`. Same token colour, still
  muted for the original and signal when a different version is active.
- **AI alternative text was invisible.** `OptionRow` rendered non-pinned options as
  `sr-only`. It now shows the text (clamped to two lines) for every option.
- **Alternatives moved to a right drawer.** New `web/src/components/ui/drawer.tsx` (Base UI dialog
  primitive, slides in from the right, focus-trapped, escape/backdrop to close). The editor no
  longer squeezes a side panel into the document; `AlternativesPanel` now fills the drawer.
- **Excess page scroll fixed.** Removed the `WORKSPACE_PANE_STACK_SPACER` (55vh) and the
  `lg:snap-*` classes from the draft workspace/editor — leftovers from the stacked video-studio
  layout that let the page scroll far past the cards. (The spacer is still correct and untouched
  in `video-studio.tsx`.)
- **Context as a Markdown blockquote.** Outgoing chat messages now quote the draft selection as
  `> …` and the chat renders `>` runs as blockquotes. The pending-context preview above the input
  is restyled as a blockquote too (no more bordered "Context:" chip).
- **Selection becomes context automatically.** The editor reports the current non-empty text
  selection via `onSelectText`; the workspace stores it as the chat context. Selecting text in the
  document and then sending a chat message includes it by default (the manual "Ask AI" path still
  works).
- **Chat identity.** User messages use the same `UserAvatar` (with the gradient ring) as the header
  user menu. Bubbles now have distinct widths (user `max-w-[78%]`, assistant `max-w-[88%]`) and
  asymmetric corner rounding so each side is easy to tell apart.

## Files

- `web/src/lib/alternative-sound.ts` — deleted.
- `web/src/components/ui/drawer.tsx` — new right-hand drawer.
- `web/src/components/projects/draft/free-flow-editor.tsx` — sound out, drawer in, `onSelectText`,
  snap classes out.
- `web/src/components/projects/draft/alternatives-panel.tsx` — sound out, text always visible,
  fills the drawer.
- `web/src/components/projects/draft/draft-chat.tsx` — avatar, blockquote rendering, widths,
  blockquote context preview.
- `web/src/components/projects/draft/draft-workspace.tsx` — spacer/snap out, `onSelectText`,
  blockquote message assembly.
- `web/src/app/globals.css` — dashed underlines.

## Decisions / gotchas

- The drawer is modal, so the document behind it is inert while open. Tab still cycles the
  selected group because the editor listens on `window` and only defers Tab when focus is in an
  `input`/`textarea`/`select`.
- Auto-context deliberately does **not** clear when the browser selection collapses (e.g. clicking
  into the chat box); it only updates on a new non-empty selection and is cleared after sending.
- Blockquote detection is line-based (`>` prefix), matching the format the workspace writes.

## Verification

- Web: `tsc` clean; `oxlint` clean; `eslint` 0 errors (1 pre-existing `<img>` warning);
  `next build` succeeds. Dev server recompiled and serves `/projects/view` 200 (`.logs/web.log`).
- No sound references remain (`grep` clean).
- Backend untouched.

## Not done / next step

- Not click-tested in a real browser (no automation here). Worth eyeballing: drawer slide
  animation, focus behaviour when it opens, and the auto-context firing on drag-select.
- The drawer is single-selection only (opening it makes the document inert), so switching groups
  means closing it first — fine for the Tab-first interaction, but a non-modal drawer is a
  possible follow-up.
- Uncommitted.
