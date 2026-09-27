# Progress — truth reviewer grounded with Google Search (2026-09-27 21:46)

Follow-up to `2026-09-27-2111-reviewer-function-calling-and-footage-ui.md`. Implements the
"Truth reviewer policy" that `backend-plan.md` §8 had specified but never wired up: the truth
reviewer now verifies hard claims against the web instead of grading from model memory.

## What changed

### Provider gained grounding
`providers/base.py`: new `GroundingSource` / `GroundingInfo` and an optional
`LlmCompletion.grounding`. Both `complete_json` and `complete_json_with_tools` take a
`grounding: bool` flag.

`providers/llm.py`: when `grounding` is set it adds `types.Tool(google_search=types.GoogleSearch())`
to the request (`_generate`), and `_grounding_from` reads `webSearchQueries`, `groundingChunks`
and `searchEntryPoint.renderedContent` off the response. The tool loop merges grounding across
rounds. This works alongside the existing footage function declarations **and** the findings
`response_schema` on Gemini 3 — verified directly before building.

### Only the truth reviewer searches
`reviewer_base.LlmReviewer` gained `supports_grounding` (default False), a `grounding_enabled`
constructor arg, a `GROUNDING_PROMPT`, and a `grounded` option on `findings_schema` that adds a
`sources` array to each finding. `TruthEvidenceReviewer.supports_grounding = True`; the other
eight reviewers never search. `ReviewResult.grounding` carries the metadata back.

The prompt requires it to search before judging, attach the sources it used, and fall back to
`needs_verification` when the web does not settle a claim. Model-emitted `sources` are
normalized into `Finding.citations` (which was previously always empty).

### Persistence + contract
`DimensionOutcome` and the reviewer run carry `groundingQueries`, `groundingSources`,
`groundingSearchSuggestions`. Because `groundingChunks` can come back empty in JSON mode, the
coordinator also folds each finding's citations into the aggregate source list. Contract
(`ReviewerRun` + `ReviewerGroundingSource`) and `web/src/lib/types.ts` updated.

### UI
- New `web/src/components/projects/grounding-panel.tsx`: a "Grounded with Google Search" block
  showing the queries, the sources, and Google's Search Suggestions HTML (rendered as provided,
  as the grounding terms require). Shown in the review panel.
- `findings-panel.tsx`: each finding now lists its source links under the row.
- `Finding.citations` is typed (`FindingCitation`).

### Config
`TRUTH_GROUNDING_ENABLED` (default true). Billing is per search query after 5k free/month
(~$14/1,000), so only the truth reviewer opts in.

## Verification (real services)
- `ruff` + `mypy` clean; web `lint` + `build` clean (eslint: only the pre-existing
  `no-img-element` warning).
- Direct real-Gemini `TruthEvidenceReviewer` run: ran 3 queries, returned a real source list
  (Britannica, Wikipedia, weather.gov) and citations on both findings; `searchEntryPoint`
  present.
- Full API run (local server, real token/Firestore/Gemini), project
  `e6c4b7037edb408e9617aa7c1e9b16a7` run `385250b0c70d43689e81040384734d59` -> `ready`:
  **truth_evidence** had 2 grounding queries, 1 aggregated source, and the Search Suggestions
  HTML; every other dimension had 0 queries (and used footage tools). Cost `$0.015`.
- This also re-confirmed the footage tools still work alongside grounding.

## Notes / gotchas
- `groundingChunks` / `groundingSupports` are unreliable with `response_mime_type=json`; the
  model-emitted `sources` field is the primary citation path (folded into the aggregate list).
- Grounding is best-effort: the model can still answer from memory, so the prompt forbids it and
  the fallback is `needs_verification`.
- Tool combination (Search + footage functions) is Gemini 3, Preview. Our deployed model is
  Gemini 3.8 Flash, so it is covered.
- Search Suggestions were returned on real runs, so the chip rendering is required for terms
  compliance, not optional. The HTML is Google/API output, never user content.

## Not done / next steps
1. Deploy the API (FFmpeg layer + `TRUTH_GROUNDING_ENABLED`) for this to exist in prod.
2. A dedicated claim→verify→cite pass (plain-text grounding, where chunk metadata is reliable)
   would give tighter quote→source mapping; this slice uses the in-review tool instead.
3. Test artifact left: run `385250b0c70d43689e81040384734d59` on project
   `e6c4b7037edb408e9617aa7c1e9b16a7` (plus the earlier `92a70735...`).
