# Draft editor rewritten: one free-flowing document, Tab-cycled alternatives

## What I did

Replaced the block-stack editor with a **single Obsidian-style free-flowing document**. There is
no per-block chrome (no borders, hover toolbars, delete buttons, version dropdowns) — one
contenteditable sheet renders the whole draft as formatted prose.

- **Freeflow surface.** `draft.blocks` are flattened to one Markdown string
  (`blocks.map(activeText).join("\n\n")`) and rendered once via `markdownToHtml` into a single
  `contenteditable` div. The DOM is the source of truth while typing (WYSIWYG); it is serialized
  back to Markdown with the new `htmlToMarkdown` and split into blocks by blank lines
  (`blocksFromMarkdown`, which preserves a chunk's history when it did not change).
- **Alternative indicators by level.** `markdownToHtml` now detects a whole line that is nothing
  but one `{{…}}` group and renders it as a block-level control:
  - headings → wavy underline across the text, version dots centred underneath;
  - paragraphs → clean lines with a vertical margin marker and stacked dots on the left;
  - inline word/sentence spans → the existing wavy underline + trailing dots.
- **Tab cycling.** Click a variant (or park the caret immediately beside one) and press **Tab /
  Shift+Tab**. A selected group also cycles from anywhere (window keydown), except inside the
  panel's inputs. The original is always kept and always reachable. Sound cue kept.
- **Article agreement.** `reconcileArticles` runs whenever the active option changes: a version
  that starts with a vowel sound rewrites the neighbouring "a" to "an" (and back).
- **Formatting.** WYSIWYG: floating toolbar on text selection (bold, italic, H2, H3, AI
  Alternatives, Ask AI), `# `/`## `/`### ` heading shortcut, plain-text paste. No markdown
  source needed while writing.
- **Live count.** The header now shows a client-computed word count plus the number of
  alternative groups instead of the stale per-block `versionCount`.
- **Still there.** The alternatives side panel (edit/add/reorder/delete/AI suggestions/sound)
  appears only when a group is selected, and now points at Tab.

## Files

- `web/src/components/projects/draft/free-flow-editor.tsx` — rewritten, single document.
- `web/src/lib/draft-content.ts` — added `startsWithVowelSound`, `reconcileArticles`,
  `inlineVariantHtml`, block-level rendering in `markdownToHtml`, and `htmlToMarkdown`
  (DOM → Markdown). `setActiveOption` now reconciles articles.
- `web/src/components/projects/draft/draft-workspace.tsx` — `editDoc`/`blocksFromMarkdown`
  replaces the per-block edit/split/merge/version/delete API; `suggest` takes `(text, mode)`;
  dropped the now-unused busy-block state.
- `web/src/components/projects/draft/alternatives-panel.tsx` — hint text now says Tab.
- `web/src/app/globals.css` — heading/paragraph variant styles + empty-surface placeholder.

## Decisions / gotchas

- **Atomic variants.** Alternative spans are `contenteditable="false"`, so the caret can sit
  beside them but not inside; clicking selects the group and collapses the caret just after it.
  This keeps the DOM edits from corrupting the `data-variant` payload. Editing a version's text
  is done in the panel.
- **No live markdown re-parse.** Typing does not re-render from Markdown (which would eat the
  caret); formatting is native WYSIWYG and Markdown is only produced on save. External changes
  (cycle, AI, writing partner) re-render from the stored Markdown.
- **`lastRendered` guard.** Every commit records the serialized Markdown so the render effect
  skips while typing. AI-wrapping deliberately leaves it stale so the new group gets a real
  `data-variant-index`.
- Block history is now secondary: a chunk that did not change keeps its versions; a changed
  chunk becomes a single user version. Inline alternative groups are the history now.
- Empty document falls through to the existing "Start your draft" card (pre-existing behaviour).

## Verification

- Web: `tsc` clean; `oxlint` clean; `eslint` 0 errors (1 pre-existing `<img>` warning);
  `next build` succeeds. Dev server on `:3000` recompiled and serves
  `/projects/view?projectId=…` 200 (`.logs/web.log`).
- Pure logic checked with a throwaway Bun script (deleted): article `a`↔`an` on cycle, inline /
  heading / paragraph HTML with the right classes + `contenteditable`, variant span count,
  parse/serialize round-trip.
- Backend untouched this session.

## Not done / next step

- Not click-tested in a real browser (no automation here). Most likely papercuts: block-variant
  Enter/backspace behaviour at the boundaries and floating-toolbar placement near the viewport
  edge.
- `??` quick-alternatives shortcut was removed with the rewrite; the selection toolbar's
  "Alternatives" covers it.
- The alternatives panel still edits options via its own surface; a future pass could let you
  edit the active version directly in the document.
- Uncommitted.
