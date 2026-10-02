# Draft editor: Obsidian-style live preview

## What I did

Rebuilt the draft editor the way it should have been: an Obsidian-style live preview with
per-span versioning.

- **Markdown storage + live preview.** Each block stores Markdown. Unfocused blocks render the
  preview (headings, bold, italic, lists, quotes, code); the block you click swaps to the raw
  Markdown in a plain editor and returns to the preview on blur. Exactly the "preview except
  while I am editing" behaviour.
- **Per-span versioning.** Selecting text and choosing Rewrite/Alternatives wraps the selection
  in an inline `{{option 1 | option 2 | option 3}}` variant. The first option is active;
  switching moves the chosen option to the front. Variant spans render with a dotted underline
  and open a version picker on click. This versions the exact word/sentence/paragraph you
  selected, not the document or the whole block.
- **Plain editor, not contenteditable.** Editing uses a textarea, so selection offsets are
  reliable: Enter splits the block at the caret, Backspace at the start merges with the previous
  block, Escape stops editing. The toolbar (Bold / Italic / Heading / Rewrite / Alternatives /
  Ask AI) acts on the current selection.
- **Same height as the chat.** The editor is now `min(78vh,44rem)`, matching the chat card, and
  scrolls internally.
- **Delete a block** from the hover controls.
- **HTML → Markdown revert.** The earlier HTML-storage experiment is gone; word counts, prompts,
  previews, and exports all resolve the Markdown (variants → active option).

## Changes

### Web

- `lib/draft-content.ts` — Markdown → HTML renderer (with the `{{…}}` variant syntax),
  `markdownToPlain`, `resolveVariants`, `parseVariant`, `reorderVariant`, `variantSyntax`.
- `components/projects/draft/free-flow-editor.tsx` — rewritten: edit/preview blocks, toolbar,
  variant popover, delete.
- `components/projects/draft/draft-workspace.tsx` — `editBlockText`/`splitBlock`/`mergeBlock`
  now return the focus target; `suggest()`; selection context; optimistic chat.
- `lib/draft-export.ts` — exports via `resolveVariants`/`markdownToPlain`.
- `app/globals.css` — `.prose-draft` styles for the rendered preview.

### Backend

- `services/draft_service.py` — `strip_html` now resolves inline variants (first option) before
  stripping any HTML, so word counts, summaries, and the assist prompt read the active text.

## What I decided / discovered

- **A textarea beats a contenteditable here.** Selection ranges, caret control, and Enter/Backspace
  handling are trivial with `selectionStart/End`, which is what made the inline versioning and the
  toolbar reliable. The cost is that formatting is authored as Markdown — which is exactly the
  Obsidian model.
- **The active variant is encoded by order** (`{{active | other}}`), so no extra state or index
  syntax is needed; switching reorders the options.
- **The height is shared with the chat** so the two columns line up.

## Verification

- Backend: `ruff` clean, `mypy` clean (79 files).
- Web: `tsc` clean, `oxlint` clean, `eslint` 0 errors (one pre-existing `<img>` warning),
  `next build` succeeds; dev server serves the routes (200).

## Not done / next step

- Uncommitted (`cf8e9cb` holds the first studio/draft pass).
- Clicking a block places the caret at the end rather than where you clicked; a follow-up could
  map the click to an offset.
- The Markdown renderer covers headings, bold, italic, lists, quotes, code; tables/links are
  future work.
