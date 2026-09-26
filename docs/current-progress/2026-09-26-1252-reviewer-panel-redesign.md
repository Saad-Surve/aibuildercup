# Progress — 2026-09-26 12:52 UTC — reviewer panel redesign (13 → 9, 1–5 scoring, packaging)

Implemented the reviewer-panel critique end to end: pruned/merged dimensions, switched to
discrete scoring, made reporting exception-first, reordered the schema for reason-then-grade,
locked `findingType` per reviewer, and added packaging context.

## Dimensions (13 → 9 active)

- **Merged** `structure_pacing` + `engagement_retention` → **`pacing_retention`**.
- **Merged** `audience_fit` + `brand_voice` → **`audience_brand`**.
- **Dropped** `seo_discoverability` (spoken keyword density is the wrong signal) and
  `visual_accessibility` (false positives without computer vision).
- New core: truth_evidence, clarity, pacing_retention, legal_safety, cultural_localization,
  platform_fit. Extended: audience_brand, emotional_impact, conversion_cta.
- **Backward compatible:** the six retired values stay in `AnalysisDimension` as
  `LEGACY_DIMENSIONS` so historical runs still deserialize; `resolve_dimensions` filters them so
  a new run can never select one. `REVIEWER_CLASSES` has no entry for them.
- Deleted `structure_agent.py`, `retention_agent.py`, `audience_agent.py`, `brand_voice_agent.py`,
  `seo_agent.py`, `accessibility_agent.py`; added `pacing_agent.py`, `audience_brand_agent.py`.

## Shared architecture (`reviewer_base.py`)

- **Role** rewritten to "elite video script and retention analyst" with the three guidelines
  (speak to the medium, be surgically specific, reason before grading). Explicit
  `DIMENSION_LABELS` map so acronyms render as `Conversion & CTA`, not `Conversion Cta`.
- **Scoring** moved from 0–10 float to discrete **1–5 integer** (`Finding.score`,
  `heatmap.color_for` bands, `severity_for_score`, `summarize_findings` averages). `HeatmapBin`
  keeps a float (bin average).
- **Exception-first reporting** replaces "cover the whole window": `OUTPUT_RULES` now emit a
  finding only for a real flaw or an exceptional strength (score 5). The heatmap is event-based
  with gaps, not a forced continuous track.
- **Schema reordered** for chain-of-thought: `evidence` (quote + `critique_and_reasoning`)
  before `findingType`/`severity`/`score`. `confidence` dropped from the schema (still on the
  `Finding` model, defaults).
- **`findingType` enum** is injected per reviewer from `LlmReviewer.finding_types`, so the model
  cannot invent types. `FINDINGS_SCHEMA` → `findings_schema(finding_types)`.
- `FindingEvidence.explanation` → **`critique_and_reasoning`** (read path falls back to the old
  field for legacy findings).
- Version bumped: `REVIEWER_PROMPT_VERSION` / `MODEL_CONFIG_VERSION` → `v2` / `analysis-v2`.

## Packaging inputs

- `ReviewContext` gained `video_title` / `thumbnail_concept`; the user prompt now prints
  `Video title` and `Thumbnail concept`.
- New optional project field **`thumbnailConcept`** end to end: `CreateProject`/`UpdateProject`/
  `Project`, `project_service`, `contracts/openapi.yaml`, web types, and the create + edit
  dialogs. The worker loads `(video_title, thumbnail_concept)` from the project
  (`name` doubles as the title) and passes both to `build_review_contexts`.

## Contracts / docs

- `contracts/openapi.yaml`: dimension enum (active + retired), `Finding.score` integer 1–5,
  `evidence.critique_and_reasoning`, `CreateProject.thumbnailConcept`.
- `backend-plan.md` (§8/§9), `api-design.md`, `db-design.md` updated to the new panel, scoring,
  and finding shape.
- `docs/reviewer-prompts.md` regenerated from the source (9 reviewers; script at
  `backend` + `PYTHONPATH=.`). It is a mirror, not runtime.

## Verified

- Backend: `ruff check .` clean, `mypy app` clean (64 files).
- Functional smoke: assembled a real system + user prompt (title/audience render, new anchors),
  `findings_schema` enum, `normalize_findings` returns an int score in [1,5] and the renamed
  evidence field, and the label map for all dimensions.
- `contracts/openapi.yaml` parses.
- Web: `tsc --noEmit`, `oxlint`, `next build`, `eslint` all clean (1 pre-existing `<img>`
  warning).

## Gotchas / decisions

- **Legacy data is clamped, not migrated.** Old findings stored a 0–10 float score and
  `explanation`; `_to_finding` clamps the score into [1,5] and reads either evidence field.
  Old `scoreByDimension`/`overallScore` values are on the old scale and will look off until the
  run is redone. Fine for a hackathon; a backfill would be needed for real data.
- **Exception-first changes the heatmap look.** Tracks now have gaps where nothing was flagged.
  If the demo needs a continuous ribbon, that is a deliberate product reversal — the token/latency
  win is real and was the point of the change.
- `confidence` and `includeVisualReview` remain on the models/contract but are no longer
  requested from the model.

## Not done / next step

- **Not run live.** Needs one real analysis on a `fixtures/media/` video to confirm the 9
  reviewers produce sane findings on the 1–5 scale and that `findingType` enums are respected.
- Optional: a reviewed eval set (backend-plan §"AI evaluation tests") to calibrate the new scale.
