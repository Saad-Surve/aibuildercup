# Markdown rendering: markdown-it + shiki (chat + editor code blocks)

## What I did

Replaced the ad-hoc Markdown handling with `markdown-it` + `shiki`, keeping every existing
behaviour intact.

**New:** `web/src/lib/markdown.ts`
- `markdown-it` (CommonMark) with `html: false` (raw HTML escaped), `linkify`, `breaks`.
- `shiki` via its **synchronous** core (`createHighlighterCoreSync` + `createJavaScriptRegexEngine`),
  so it works from both React and the editor's synchronous `innerHTML` path — no async loading
  state.
- Dual light/dark themes (`github-light` / `github-dark`) emitted as `--shiki-*` CSS vars; switched
  in `globals.css`.
- Languages bundled: bash, css, html, javascript, json, jsx, markdown, python, shell, tsx,
  typescript, yaml (+ aliases). Unknown languages fall back to an escaped `<pre>`.
- `highlightCode(code, lang)` tags the `<pre>` with `data-language` so the editor can round-trip.
- `renderMarkdown(source)` returns safe HTML.

**Chat** (`components/projects/draft/draft-chat.tsx`)
- `MessageBody` now renders Markdown via `renderMarkdown` instead of plain text. Assistant output
  (headings, lists, quotes, links, fenced code) renders properly and code is highlighted. Removed
  the now-unused `cn` import.

**Draft editor** (`lib/draft-content.ts`)
- `markdownToHtml` now recognises fenced code blocks (` ```lang … ``` `) and highlights them; the
  fence body is emitted verbatim (Markdown inside is not parsed).
- `serializeDomNode` handles `<pre>` → fenced block, reading `data-language` for the fence, so the
  contenteditable round-trip (`htmlToMarkdown`) preserves code blocks.
- The custom `{{ variant }}` syntax, variant spans, dots, and block/heading variants are untouched.

**Styles** (`app/globals.css`)
- `.prose-chat` for compact chat Markdown; colours are `currentColor`-relative so the same rules
  work in the assistant (muted) and user (primary) bubbles.
- `.prose-draft pre` / `pre code` for editor code blocks.
- Shiki dual-theme var switching.

## Dependencies

`bun add markdown-it shiki`; `bun add -d @types/markdown-it`. (markdown-it@15, shiki@4.5.)

## Verification

- `bunx tsc --noEmit` clean.
- `bun run lint` (oxlint) clean; `bun run lint:eslint` 0 errors (1 pre-existing `project-card.tsx`
  `<img>` warning).
- `bun run build` clean.
- Runtime smoke via `bun`: `renderMarkdown` emits shiki-highlighted `<pre data-language="ts">`,
  lists/quotes/links; unknown language falls back; `markdownToHtml` still emits the exact
  `draft-variant` span HTML while highlighting fences.

## Decisions / gotchas

- Shiki is synchronous on purpose: the draft editor sets `innerHTML` synchronously and the
  variant/selection effects depend on that. An async highlighter would have needed a loading state.
- Raw HTML stays disabled, so model output cannot inject markup. The grounding panel's
  `groundingSearchSuggestions` is **HTML** (from `grounding_html`), not Markdown, so it was left
  as-is (it still uses `dangerouslySetInnerHTML`).
- The editor's code blocks are contenteditable like everything else; editing a highlighted block
  edits the spans, and the code text is recovered on commit. Fine for the demo; a dedicated
  raw-edit affordance would be nicer later.

## Not done / next step

- Commit not made (user hasn't asked). New files: `web/src/lib/markdown.ts`; modified: chat,
  draft-content, globals.css, package.json/bun.lock.
- Possible follow-ups: render Markdown in other model-output surfaces (analysis findings), add more
  fence languages, or a copy button on code blocks.
