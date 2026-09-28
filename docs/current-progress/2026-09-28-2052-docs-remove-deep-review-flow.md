# Docs: fold deep review into the main multi-reviewer analysis

## What I did

The separate "deep review" / tier-2 flow no longer exists — the visual pass is part of the
main multi-reviewer analysis (reviewers call the FFmpeg `extract_frame` / `cut_clip` tools
during their own run). Removed the stale separate-flow design from the docs, the API contract
(scope agreed with the user: docs + contract), and one code docstring. The unused
`includeVisualReview` request field is kept, now documented as reserved.

## Changes

- `docs/technical-design/README.md` — key decision now describes one bounded reviewer fan-out
  with in-run footage tools, "no separate deep-review flow".
- `docs/technical-design/backend-plan.md` — `### Two-tier fan-out` → `### Reviewer fan-out`;
  dropped "Tier 1 / Tier 2", the on-demand deep-review paragraph and the Deep Review button
  trigger. The visual-context paragraph now states the multimodal pass is part of the same run.
- `docs/technical-design/diagrams.md` — section 6 flowchart now shows reviewers may call the
  FFmpeg tools mid-review and no longer branches to the deep-review node; removed section 7
  (deep-review sequence diagram) and renumbered sections 8–17 to 7–16.
- `docs/technical-design/frontend-plan.md` — removed `DeepReviewButton` and its interaction.
- `docs/technical-design/api-design.md` — removed the `segment-review` route row and the
  deep-review request example; noted `includeVisualReview` is reserved.
- `docs/technical-design/workstreams.md` — removed lane items "deep-review trigger",
  "deep multimodal segment review", and "tiered fan-out".
- `web/DESIGN.md` — removed `DeepReviewButton` from the timeline component list.
- `contracts/openapi.yaml` — removed the planned `POST .../analysis/{analysisRunId}/segment-review`
  path and the `SegmentReviewRequest` schema; reworded the `includeVisualReview` description to
  "reserved" with no separate flow.
- `backend/app/agents/reviewer_base.py` — docstring no longer says tier 2 is the separate
  `segment-review` flow (comment only; no behaviour change).

## Structural changes

Contract change: one planned endpoint (`segment-review`) and one schema (`SegmentReviewRequest`)
removed. No implemented route, persisted field, or generated client type changed — the web types
never referenced them. `includeVisualReview` remains in the request schema, the analysis-run
document, and `web/src/lib/types.ts`, now marked reserved.

## What I decided / discovered

- Historical notes in `docs/current-progress/` still describe tier-2 deep review as an open
  item; those are a log and were intentionally left untouched (this note supersedes them).
- `fanoutStrategy: "two_tier"` is still written on analysis-run documents in
  `analysis_service.py`. It is a stored label, not behaviour, so it was left alone; renaming it
  would be a data/schema change outside this task's scope.

## Verification

- `contracts/openapi.yaml` parses with `yaml.safe_load`; `segment-review` and
  `SegmentReviewRequest` are gone; `includeVisualReview` description updated.
- Repo-wide grep for deep-review/segment-review now only matches the new "there is no separate
  deep-review flow" sentences (plus a historical progress note and an unrelated `safe_segment`
  helper).
- `uv run ruff check .` clean; `uv run mypy app` clean (76 files).

## Not done / next step

- Uncommitted. Say the word and I'll commit + push.
- Optional follow-up: rename `fanoutStrategy` from `"two_tier"` to something accurate, and drop
  the reserved `includeVisualReview` field, if you want the data model to match the docs.
