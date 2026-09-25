# Progress — 2026-09-25 16:21 UTC — multi-reviewer analysis + heatmap (tier 1)

Built the analysis → heatmap vertical slice end to end: contracts, backend, web UI.
This is the flagship feature (`docs/technical-design/backend-plan.md` §8–9,
`api-design.md` §9, `diagrams.md` §6). Follows `2026-09-24-1555-apply-cleanup.md`,
which listed "analysis/heatmap" as the first of the deferred big items.

## What is now real

`POST /projects/{id}/analysis` queues a run → six core reviewers (plus any extended
ones requested) fan out over transcript chunks through the Gemini Developer API →
findings are validated and normalised → aggregated into 5-second heatmap bins →
the timeline UI paints one review track per dimension and the findings list drives
the video.

### Contracts (`contracts/`)

- `openapi.yaml`: analysis endpoints un-planned and implemented — `GET` (list runs),
  `POST`, `GET {runId}`, `GET {runId}/reviewers`, `GET {runId}/findings`,
  `GET {runId}/heatmap`. Added `AnalysisDimension`, `AnalysisRunStatus`,
  `ReviewerRunStatus`, `TokenUsage`, `AnalysisRun`, `ReviewerRun`,
  `SegmentReviewRequest` schemas; `Finding` gained `reviewerRunId`, `HeatmapBin`
  gained `binId`.
- `api-design.md` §9: added `GET /projects/{projectId}/analysis` (list runs). This
  route was missing from both the design table and the contract but the frontend
  plan requires it (`AnalysisRunSelector`), so it is now specified first and built.
- `POST .../segment-review` is **still `x-status: planned`** — see Boundaries below.

### Backend (`backend/`)

| Piece | Where |
|---|---|
| Path builders | `services/paths.py` — `analysisRuns/{id}` + `reviewers/`, `findings/`, `heatmapBins/` |
| Schemas | `schemas/analysis.py` — 13 dimensions (6 core + 7 extended), `Severity`, `HeatmapColor`, run/reviewer/finding/bin shapes |
| Pure aggregation | `services/heatmap.py` — `aggregate_bins`, `summarize_findings`, `color_for` |
| Reviewer base | `agents/reviewer_base.py` — shared 0–10 anchor rubric, output schema, `normalize_findings` |
| 13 reviewers | `agents/{truth,clarity,structure,safety,cultural,platform,audience,brand_voice,retention,emotion,seo,accessibility,conversion}_agent.py` |
| Fan-out | `agents/analysis_coordinator.py` — chunking, `asyncio.Semaphore`, per-dimension outcomes |
| Persistence | `services/analysis_service.py` |
| Cost | `services/cost.py` + `config.py` price table |
| Worker | `workers/analysis_worker.py` |
| API | `api/analysis.py` |

### Web (`web/`)

- `lib/analysis.ts` (API client + labels/colour tokens), `lib/types.ts` (analysis types).
- `components/projects/heatmap-tracks.tsx` — **the review ribbon** (see Gotchas).
- `components/projects/review-panel.tsx` — toolbar, severity census, reviewer strip.
- `components/projects/findings-panel.tsx` — findings list, seek-on-click.
- `project-workspace.tsx` renders the review block between the player and transcript.

## Decisions and gotchas

1. **Reviewer output is span-covering, including `severity: none`.** Reviewers are
   prompted to walk the whole review window and report every coherent span, *including
   what is fine*. That is what makes the heatmap a continuous track instead of a
   scatter of blips, and it is exactly what `severity: none` in the design's enum is
   for. `findingCounts` reports all five severity buckets so the UI can show both
   problems and "fine" stretches.

2. **Bins exist only where a finding exists.** `aggregate_bins` never invents a score
   for untouched time. Combined with (1) a finished run is still continuous, and a
   gap honestly means "the reviewer had nothing to say here". A bin's score is the
   **duration-weighted mean** of its overlapping findings; its severity is the worst
   of them; colour follows the design's bands (`>=8` green, `6–7.99` yellow,
   `4–5.99` orange, `<4` red) with **`critical` forcing red regardless of score**.

3. **Chunking is a strict partition with context-only neighbours.** `chunk_segments`
   splits by ~9k tokens and each segment belongs to exactly one chunk, so a finding
   can never be produced twice. Neighbouring segments ride along marked
   "CONTEXT ONLY", and `clip_findings_to_window` drops anything the model reports
   outside the window it owns. Tested explicitly (`test_chunked_reviewers_do_not_duplicate_findings`).

4. **Reviewer run ids are minted at run creation** (`create_run` writes the queued
   placeholders and stores `reviewerRunIds` on the run), so the worker writes results
   onto those documents instead of leaving orphans.

5. **`LlmProvider.complete_json` now returns `LlmCompletion(data, usage)`** instead of a
   bare dict. This was the only honest way to get real `tokenUsage` / `costEstimateUsd`
   onto reviewer documents. Call sites updated: `persona_service.py`, `tests/fakes.py`,
   `tests/test_providers.py`, `tests/test_persona_service.py`. Thinking tokens are
   counted as output, matching how Google bills them.

6. **Cost is estimated from a settings price table** (`llm_input_price_per_mtok=0.75`,
   `llm_output_price_per_mtok=3.75`, USD/1M tokens, flash-class). Source: the Gemini
   Developer API pricing page as of today. These **go stale when Google reprices or
   `model_reviewer` changes class** — override in `.env`, do not edit call sites.
   `POST /analysis` is refused with `409 COST_CAP_EXCEEDED` once a project's runs have
   spent `max_project_cost_usd`.

7. **Partial results are first-class.** Each reviewer is persisted independently as it
   lands (`on_outcome`), one failure never hides the others, and the run ends
   `ready` / `partial_failure` / `failed` accordingly. A fully-failed run also fails
   the job; a partial one succeeds with "Completed with gaps".

8. **Findings listing filters in Python, not Firestore.** One run's findings are a
   small bounded set, and `dimension == ? AND startMs >= ?` would need composite
   indexes. Documented in the module docstring.

9. **Delete needs no new work.** Everything lives under
   `users/{uid}/projects/{projectId}/analysisRuns/...`, so `ProjectService.delete`'s
   recursive tree delete covers it.

10. **The review ribbon (web) — the signature element.** One signal trace per
    dimension against the timeline, using the design tokens that already existed for
    exactly this (`--heat-*`, `--sev-*`; `globals.css` literally says "colour is the
    review signal"). Two non-obvious choices:
    - **Critical bins carry a bright centre notch**, so dangerous moments are findable
      by silhouette alone and colour is not the only channel.
    - **Hover paints a fixed readout strip** (scope meter, `aria-live="polite"`)
      instead of a floating tooltip — always in the same place, always announced.
    - Keyboard: **roving tabindex**, one tab stop per track with arrow keys walking
      its bins. Without this the ribbon would be 200+ tab stops.

## Verified

- Backend: `uv run pytest` **268 passed** (was 151), `uv run ruff check .` clean,
  `uv run mypy app` clean.
- Web: `bun run lint` clean, `bun run build` passes.
- New test files: `test_heatmap.py` (26), `test_reviewers.py` (26),
  `test_analysis_coordinator.py` (22), `test_analysis_service.py` (18),
  `test_analysis_api.py` (10), `test_analysis_worker.py` (15), plus new path cases
  in `test_firestore_paths.py`.

## Boundaries (deliberate, not dropped)

- **Tier-2 deep review (`POST .../segment-review`) is not built.** It needs the FFmpeg
  Cloud Run media worker (`diagrams.md` §7) which does not exist yet. Stays
  `x-status: planned` in the contract.
- **`includeVisualReview` is accepted and recorded on the run but produces no visual
  findings.** It is reserved for tier 2. The `visual_accessibility` reviewer still
  runs over the transcript and asks the model for `needs_visual_review` findings
  rather than guessing at what the video shows.
- No `analysis.requested` → worker Pub/Sub subscription yet. The API schedules the
  worker inline via `BackgroundTasks` (same pattern as `transcribe_after_response`),
  and the worker is idempotent, so a push subscription can be added without rework.

## Not done / next

- Tier-2 multimodal segment review (needs media worker).
- Deep Review button in the UI.
- Artifacts, chat, localization/shorts/Veo, transcript regenerate, account export,
  seed script, separate worker containers — unchanged from the previous notes.
- A real video under `fixtures/media/` should be run through this live before demoing,
  to check the reviewer prompts score sensibly and not all at 7.
