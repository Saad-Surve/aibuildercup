# Draft studio: Google Search grounding for generation + assist

## What I did

Enabled Grounding with Google Search for the draft/script writer. Previously only the truth
reviewer (and the new persona research) used grounding; the draft flow was ungrounded and could
only rely on the brief plus retrieved channel style evidence.

Grounding is now on for:
- `_generate_blocks` — the first-draft / script generation (`model_writer`).
- `assist` — the writing-partner chat, so "verify / add the latest X" works (`model_writer`).

It stays off for `suggest` (word/sentence alternatives; no facts needed).

## Backend

- `config.py`: `draft_grounding_enabled: bool = True`.
- `schemas/draft.py`: `DraftGroundingSource`, `DraftGrounding` (`queries`, `sources`,
  `searchSuggestions`, `updatedAt`), and `Draft.grounding`.
- `draft_service.py`:
  - `DRAFT_GROUNDING_INSTRUCTION` is appended to the generation/assist system prompt only when
    grounding is on (never promise search the model can't do).
  - `GENERATE_SCHEMA` / `ASSIST_SCHEMA` gained a `sources[]` field (model-emitted citations).
  - `_grounding_from(model_sources, provider_grounding)` merges model sources with the provider
    grounding chunks, deduped by URL, http(s) only (same caveat as the truth reviewer: JSON-mode
    `groundingChunks` can be empty).
  - `_generate_blocks` now returns `(blocks, grounding)`; `generate` sets `draft.grounding`
    (fresh generation replaces/clears stale sources).
  - `assist` captures grounding and replaces it only when the turn actually searched.
- Persisted on the draft document via the existing `_persist` model dump, so it reloads on
  `GET /projects/{id}/draft` and needs no extra delete wiring (it is under the project subtree).

## Contract & docs

- `contracts/openapi.yaml`: `Draft.grounding` plus `DraftGrounding` / `DraftGroundingSource`.
- `contracts/firestore.md`: draft document now also keeps `grounding`.
- `docs/technical-design/backend-plan.md`: draft writer grounding paragraph.

## Frontend

- `lib/types.ts`: `DraftGrounding` / `DraftGroundingSource`, `Draft.grounding`.
- `components/projects/draft/draft-grounding-panel.tsx`: "Grounded with Google Search" card
  (query chips, source links, and the Search Suggestions HTML rendered exactly as provided).
- `draft-workspace.tsx`: renders the panel next to "Style evidence".

## Verification

- `uv run ruff check .` clean; `uv run mypy app` clean (116 files).
- `bun run lint` (oxlint) clean; `bun run lint:eslint` only the pre-existing `<img>` warning;
  `bun run build` (Next 16, TypeScript) clean.
- One-off check of `_grounding_from`: model + provider sources merged, `ftp` URL dropped,
  empty input returns `None`.

## Gotchas

- Grounding is billed per search query; if cost matters, set `DRAFT_GROUNDING_ENABLED=false`
  (turns it off for both generation and assist with no code change).
- Assist keeps the previous grounding when a turn does not search, so the panel does not flicker
  empty on ordinary rewrites. A regeneration always clears stale sources.
- Google's terms require the Search Suggestions HTML to be rendered as returned and sources to
  be shown; the panel does both.

## Not done / next step

- Live grounded draft generation/assist not yet exercised end-to-end. Smoke-test by generating a
  draft whose topic needs a current fact (e.g. a recent event) and confirm the panel lists
  sources and the Search Suggestions render.
