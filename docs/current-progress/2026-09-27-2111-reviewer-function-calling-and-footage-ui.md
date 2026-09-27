# Progress — reviewer function calling + footage evidence UI (2026-09-27 21:11)

Follow-up to `2026-09-27-2044-transcript-cleanup-and-reviewer-video-tools.md`. That note left the
reviewer tools as a `visualContextRequests` JSON field in the structured output plus a second
pass. On request, this replaces that with **real Gemini function calling** and adds a UI that
shows the exact frames/clips the reviewer fetched. The transcript-cleanup half of the previous
note is unchanged.

## What changed

### Provider: a real tool-calling loop
`backend/app/providers/base.py` gained `ToolSpec`, `ToolCall`, `ToolExecutor`, and an
`LlmCompletion.tool_calls` field. `LlmProvider` gained
`complete_json_with_tools(model, system, user, schema, tools, execute, media=...,
max_tool_rounds=2, max_tool_calls=4)`.

`backend/app/providers/llm.py` implements the loop: it declares the tools as
`FunctionDeclaration`s, disables SDK automatic function calling, calls `generate_content`, and
while the model returns `function_calls` it runs `execute(name, args)` and sends the result back
as a `Part.from_function_response(..., parts=[FunctionResponsePart.from_bytes(...)])` so the model
**sees** the frame/clip. When it stops calling tools it answers with the `response_schema` JSON.
Token usage is summed across every leg. Gemini accepts tools + `response_schema` together (checked
directly), so findings stay schema-enforced.

### Reviewer: the model decides when to look
`LlmReviewer.review` now calls `complete_json_with_tools` whenever a `MediaToolkit` is bound; the
`execute` callback runs `MediaToolkit.execute(name, args)`, stores each returned part, and records
a `ToolCallRecord`. The old `visualContextRequests` field, `parse_visual_requests`, and
`build_visual_context_section` are gone. `VISUAL_TOOLS_PROMPT` now describes two tools and tells
the reviewer to fetch footage **before assigning `high` or `critical`** to anything that could be
visual. `REVIEWER_PROMPT_VERSION`/`MODEL_CONFIG_VERSION` bumped to v4.

### Footage is persisted and served
`backend/app/services/video_tools.py` gained `review_tool_specs()`, `MediaToolkit.execute()`,
and a `ContextArtifactStore` protocol with a `GcsContextArtifactStore`. The analysis worker writes
fetched media to `{project}/review-context/{analysisRunId}/{reviewerRunId}/NN-{tool}.{ext}` - under
the project prefix, so the recursive project delete covers it. `DimensionOutcome.tool_calls`
aggregates per dimension and `AnalysisService.save_reviewer_outcome` stores `toolCalls` on the
reviewer run (tool, timestampMs, label, mimeType, contentPath, ok).

New endpoint `GET /api/projects/{projectId}/analysis/{analysisRunId}/reviewers/{reviewerRunId}/context/{index}`
returns a short-lived signed URL for one artifact, verifying the stored path sits under the
caller's project prefix. It is fetched lazily by the UI, so reviewers-list polling never signs
anything.

### UI: the evidence trail
New `web/src/components/projects/reviewer-footage.tsx`, rendered in `review-panel.tsx` under the
heatmap. It collects every reviewer's `toolCalls`, shows a collapsed "Footage checks N" bar, and
on expand renders a card per call: dimension label, timestamp (click seeks the player), the label,
and a lazily-fetched preview (`<img>` for frames, `<video>` for clips). `types.ts` gained
`ReviewerToolCall`; `analysis.ts` gained `getReviewerContextUrl`.

## Config / contract / infra
- `MAX_VISUAL_CONTEXT_REQUESTS` now means total tool calls per reviewer call (default 3); new
  `VISUAL_TOOL_MAX_ROUNDS` (default 2).
- `contracts/openapi.yaml`: `ReviewerRun.toolCalls` + `ReviewerToolCall`, new `ContextArtifactUrl`
  schema and the context endpoint. `db-design.md` / `backend-plan.md` updated. `web/src/lib/types.ts`
  mirrored.
- Still requires the FFmpeg Docker layer + deploy (unchanged from the previous note).

## Verification (real services)
- `backend`: `ruff` clean, `mypy` clean (70 files). `web`: `bun run lint` clean,
  `lint:eslint` only the pre-existing `no-img-element` warning, `bun run build` clean.
- Direct real-Gemini reviewer run: the model called `extract_frame` twice on a visual-reference
  transcript; both frames were stored; the final findings were graded with the frames attached.
- **Full API run** (local server, real token, real Firestore/Gemini/FFmpeg), project
  `e364f01c9642473fbf09da6991f7e24c`, run `0a3454444e1d44cf8f5906a5c084e6ea` -> `ready`: all 6 core
  reviewers succeeded, **10 footage tool calls** persisted (mix of `cut_clip` and `extract_frame`),
  cost `$0.021383`.
- Context endpoint: signed-URL 200 for an image (18 KB `image/jpeg`) and a clip (188 KB
  `video/mp4`), both fetched successfully; out-of-range index returns 404.

## Notes / gotchas
- Cost roughly doubles vs transcript-only (vision tokens). The per-project cap is the backstop;
  tool calls are bounded per reviewer call.
- `google-genai` prints a benign "automatic function calling" warning on these calls; the SDK is
  told to disable AFC explicitly, so it is chatter only.
- The store is non-fatal: if a GCS write fails, the review still completes, the `ToolCallRecord`
  just has an empty `contentPath` and the UI shows "Not captured".

## Not done / next steps
1. Deploy the API (FFmpeg layer + env) for this to exist in prod.
2. Tier-2 deep review on demand is still unwritten; this gives tier 1 the same primitive.
3. Test artifacts left in the account: the run above on project `e364f01c9642473fbf09da6991f7e24c`,
   plus the 2044-note run. Delete the project if unwanted (covers the stored footage too).
