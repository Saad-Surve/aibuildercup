# Draft variants: brace-aware parsing + read-only version viewing

## The bug

Draft alternatives use the inline syntax `{{option | ~ai option | @my option}}`. Both the web
parser (`web/src/lib/draft-content.ts`) and the backend text parser
(`backend/app/services/draft_service.py`) matched the group with
`/\{\{([^{}]*)\}\}/` — the `[^{}]` cannot match a `{` or `}` inside an option. So any
alternative whose text contained braces (e.g. a JavaScript snippet, which is exactly what was
in the "Week 3 side projects" draft) failed to parse:

- the whole `{{…}}` group rendered **literally** in the editor,
- clicking a variant did nothing and **Tab never cycled** between versions,
- the backend leaked the raw syntax into word counts, project summaries, and the AI context.

## The fix

- **`findVariants` (web) / `_find_variants` (backend)**: a depth-aware scanner. It starts at
  `{{`, counts `{`/`}` inside the group, and only closes at a `}}` seen at depth 0. Balanced
  braces in the option text (nested blocks, function bodies) round-trip; the `}}` that closes
  the group is still unambiguous.
- Every web call site now goes through it: `variantSpans`, `replaceVariantAt`,
  `unwrapSingletonVariants`, `inline`, `markdownToHtml`'s `wholeLineVariant`, `markdownToPlain`,
  `resolveVariants`, `reorderVariant`, `sentenceAtOffset`. The `VARIANT` regex is gone.
- Backend `strip_html` uses `resolve_variants`; `_VARIANT` is gone.
- **Read-only drafts can now be browsed**: instead of a static render, the read-only demo draft
  renders the normal editor with `contentEditable={false}` and a `readOnly` title. Clicking a
  variant selects it and **Tab/Shift+Tab cycles versions locally** (`previewMarkdown`), so
  viewing versions works without persisting anything. The alternatives drawer, AI generation,
  and all edit actions stay disabled in read-only mode.

## Verification

- Confirmed the real stored block (1307 chars, 5 options, JS code with braces) now parses:
  `variantSpans` → 1, `parseVariantInner` → 5 options, `markdownToHtml` emits `draft-variant`
  (no literal `{{`), `setActiveOption` cycles. Backend `strip_html` resolves to the active
  option and `word_count` is sane.
- The `POST /draft/suggest` endpoint itself works (returns AI suggestions), so the failure was
  purely client-side parsing.
- `ruff` + `mypy` clean; `tsc`, `oxlint`, `eslint` (pre-existing `<img>` warning), `next build`
  all pass.

## Not done / next step

- Multi-line variant options are still not supported by `markdownToHtml` (it renders line by
  line); the current drafts are single-line. Worth handling if a whole multi-line paragraph is
  ever wrapped as one alternative group.
- Uncommitted (this round).
