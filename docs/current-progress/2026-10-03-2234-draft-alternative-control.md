# Draft editor: alternative control (span-level versions, cycling, panel)

## What I did

Extended the existing Obsidian-style draft editor (`free-flow-editor.tsx`) — no new writing
surface, no restyle — with a span-level "alternative control" system.

- **Content model.** Kept the inline `{{original | alt | alt}}` Markdown syntax and added
  per-option markers at the start of each option: `*` active, `~` AI, `@` user; no marker =
  original. Legacy docs still parse (first option is original/active, rest user). Metadata
  lives in the block text, so it saves/loads with no sidecar. `draft-content.ts` gained
  parse/serialize plus `setActiveOption`, `addVariantOption`, `updateVariantOption`,
  `deleteVariantOption`, `moveVariantOption`, `unwrapSingletonVariants`, `variantSpans`,
  `variantAtOffset`, `sentenceAtOffset`.
- **Decoration.** `.draft-variant` now draws a slightly irregular wavy underline (SVG mask on
  a `::after`, colored from `--alt-color`) plus a 3-dot indicator. The wave/dots are
  `--muted-foreground` while the original is active and `--signal` (with a tint) when a
  different version is active; the selected span gets a signal ring. All existing tokens.
- **Alternatives panel** (`alternatives-panel.tsx`, new): lives inside the editor card
  (`lg:flex-row`, stacks on mobile). The original is pinned first and read-only; every other
  version has an AI/You badge, inline edit, move up/down, delete, plus add-your-own and an
  **AI suggestions** button (4 from the backend, within the 3–6 range). A speaker toggle
  controls the cycling sound.
- **In-place cycling.** Click a variant to select it, then ↑/↓ or ←/→ cycle live in the
  preview. Higher tone when moving to an alternative, lower when returning to the original
  (`lib/alternative-sound.ts`, lazy `AudioContext`, mute persisted). The original is never
  overwritten and is always reachable.
- **Quick AI.** Typing `??` in the editing textarea wraps the current sentence and attaches AI
  alternatives (reverts cleanly if the model returns nothing).
- **Backend.** `draft_service.strip_html` now resolves the `*`-active option and strips the
  markers, so word counts, summaries, and prompts never see them.

## Files

- `web/src/lib/draft-content.ts` — marker model, mutations, renderer rewrite (see below).
- `web/src/lib/alternative-sound.ts` — new Web Audio cue + `useSyncExternalStore` mute store.
- `web/src/components/projects/draft/alternatives-panel.tsx` — new side panel.
- `web/src/components/projects/draft/free-flow-editor.tsx` — selection, cycling, panel, `??`.
- `web/src/components/projects/draft/draft-workspace.tsx` — suggestion count 3 → 4.
- `web/src/app/globals.css` — variant decoration + dots.
- `backend/app/services/draft_service.py` — marker-aware `strip_html`.

## Decisions / gotchas

- **Markers instead of order.** The old model encoded the active version by reordering
  (active first), which made the panel's add/edit/reorder fight the active state. An explicit
  `*` marker keeps a stable order (original first) while the active is independent.
- **Renderer was rewriting attributes.** `markdownToHtml` escaped the whole line, then ran the
  bold/italic regexes over the result — which also mangled the `data-variant` JSON when an
  option contained `*` or `"`. Rewrote `inline()` to walk the raw Markdown, escape each segment
  at output, and format text segments before embedding JSON. Quotes now round-trip.
- **Parser trims options**, so a controlled edit field would eat a trailing space. The panel's
  inline editor is an uncontrolled textarea committed on blur/Enter, with an idempotent close
  (blur + button click both fire) to avoid a double-commit deleting the option.
- **Hydration:** the mute preference uses `useSyncExternalStore` with a server snapshot of
  `true`, so the export and first client render agree.
- Deleting the last alternative unwraps the `{{…}}` back to plain text.

## Verification

- Web: `tsc` clean, `oxlint` clean, `eslint` 0 errors (1 pre-existing `<img>` warning),
  `next build` succeeds; dev server serves the draft route (200).
- Backend: `ruff` clean, `mypy` clean (97 files). `strip_html` verified on new + legacy syntax.
- Ran a throwaway Bun script over the parser/serializer/mutations (parse, set-active, add,
  delete+unwrap, move, update, resolve, HTML with quotes) — all correct; script deleted.

## Not done / next step

- Not click-tested in a browser (no automation available). Servers are up: backend `:8080`,
  web `:3000`, both logs in `.logs/`.
- A paragraph-level variant that wraps across lines gets one underline at the bounding box
  bottom rather than a wave per line; acceptable for word/sentence spans.
- Drag-to-reorder in the panel is button-based; a real drag handle is a possible follow-up.
- Uncommitted.
