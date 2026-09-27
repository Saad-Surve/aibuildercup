# Progress — transcript cleanup + reviewer video tools (2026-09-27 20:44)

> **Superseded (partly).** The reviewer-side design in this note (a `visualContextRequests`
> JSON field plus a second pass) was **replaced** by native Gemini function calling in
> `2026-09-27-<hhmm>-reviewer-function-calling-and-footage-ui.md`. The transcript-cleanup
> half of this note still stands. Read that note for the current reviewer tool design.

Continues `2026-09-27-1944-realtime-fixes-verified.md`. Two features:

1. **Post-Chirp transcript cleanup.** After STT returns, one cheap LLM pass fixes only
   recogniser errors and infers speakers.
2. **Reviewer visual-context tools.** Two FFmpeg-backed tools, `extract_frame` and
   `cut_clip` (+/-5s), that a reviewer can call mid-review when a finding depends on
   what is actually on screen.

## 1. Post-Chirp transcript cleanup

New `backend/app/services/transcript_repair.py`. `repair_transcript(segments, language, llm,
model)` batches segments to `TRANSCRIPT_REPAIR_MAX_CHARS` and asks the model for a
`corrections` list plus an optional `speakerLabels` map. It is deliberately conservative and
the system prompt forbids rewrite/paraphrase/translate/grammar fixes; only clear recognition
errors (homophones, mangled proper nouns, split/merged words, missing sentence punctuation) are
accepted. Applied per segment:

- `text` accepted only when it is a plausible minor edit (`<= max(60, 1.5x len + 40)` chars);
  an oversized "rewrite" is dropped.
- `speaker` accepted as an int in `[0, 63]`.
- unknown segment ids ignored.
- **Never raises**: a failed batch keeps the raw Chirp text, so cleanup can never cost a
  transcript.

Wired into `run_transcribe` between `build_segments` and `transcripts.save` (new progress step
`polishing` at 80%). `TranscriptService.save` now accepts pre-built `segments` and
`speaker_labels`; the transcript doc and canonical JSON carry `speakerLabels`. The public
`Transcript` schema gained `speakerLabels: map<int,string>` (empty when voices cannot be named).

Config: `MODEL_TRANSCRIPT_REPAIR`, `TRANSCRIPT_REPAIR_ENABLED` (default true),
`TRANSCRIPT_REPAIR_MAX_CHARS`. Deploy workflow/`.env.deploy.example` set the model to
`gemini-3.8-flash`.

## 2. Reviewer visual-context tools

New `backend/app/services/video_tools.py`:

- `MediaToolkit(source, duration_ms, window_seconds=5, max_requests=2)` with
  `extract_frame(at_ms) -> image/jpeg` and `cut_clip(center_ms) -> video/mp4` (scaled to 640w
  / 480h, CRF 30, no audio, fragmented MP4). `run_ffmpeg` shells out to the system binary.
- `source` is anything FFmpeg can read. **Production passes a short-lived GCS signed download
  URL**, so the API never downloads a large video into memory or `/tmp`. Output stays in
  memory; nothing is persisted, so there is no new delete pathway.
- Tool failures are non-fatal: recorded as notes and the reviewer finalises transcript-only.

Agent loop (`app/agents/reviewer_base.py`): when a toolkit is bound, the reviewer schema gains
an optional `visualContextRequests` array (`tool` + `timestampMs`). The first structured call may
ask for footage; the worker executes it and runs one extra **multimodal** call with the
frame/clip attached, and the final findings come from that second pass. `ReviewResult` and
`DimensionOutcome` gained `visual_context_count`, persisted on the reviewer run as
`visualContextCount` and exposed in the contract.

The prompt is directive (not optional-soft): if a moment being flagged refers to something
VISUAL ("as you can see", "this chart", "this reaction", "on screen"), the reviewer **must**
request it. This matters — the first, softer wording produced zero requests in a real run.

Provider layer gained multimodal support: `MediaPart` in `providers/base.py`, a `media` kwarg on
`complete_json`, and `_build_contents` in `providers/llm.py` using `types.Part.from_bytes`.

Built the toolkit in `analysis_worker._build_visual_tools`: gated by
`REVIEW_VISUAL_TOOLS_ENABLED`, requires ffmpeg on PATH, resolves the source asset from the run's
`sourceAssetId`, and signs a 1h URL. Any failure degrades to transcript-only reviewers.

## Contract / schema / infra changes

- `contracts/openapi.yaml`: `Transcript.speakerLabels`; `ReviewerRun.visualContextCount`;
  `AnalysisRequest.includeVisualReview` description now points at the tier-1 tools.
- `web/src/lib/types.ts`: mirrored both fields. `transcript-panel.tsx` shows the inferred
  speaker label when present, falling back to `S{n}`.
- `backend/Dockerfile`: installs `ffmpeg` (and ca-certificates) in one cleaned apt layer.
- `db-design.md` (transcript + reviewer doc shapes), `backend-plan.md` (sections 7, 8, 11,
  config list) updated.
- `.github/workflows/deploy.yml`, `backend/.env.example`, `backend/.env.deploy.example`: new
  config (`MODEL_TRANSCRIPT_REPAIR`, `REVIEW_VISUAL_TOOLS_ENABLED`,
  `MAX_VISUAL_CONTEXT_REQUESTS`, `VISUAL_CLIP_WINDOW_SECONDS`, `FFMPEG_PATH`).

## Verification (all real services)

- `backend`: `uv run ruff check .` clean; `uv run mypy app` clean (70 files).
- `web`: `bun run lint` clean; `bun run build` (typecheck + static export) clean.
- **Transcript repair vs real Gemini**: fixed "hear -> here", "chat gbt -> ChatGPT",
  "work out -> workout", "grate -> great"; inferred speakers 0/1 across an interview; left
  filler/grammar alone and rejected a 500-char rewrite.
- **Real multimodal provider**: sent a 13 KB JPEG frame and got a correct description with
  usage reported.
- **Signed-URL tool path**: `_build_visual_tools` on a real project produced a toolkit and
  FFmpeg read a frame straight from the signed GCS URL.
- **Real reviewer tool loop**: a reviewer given visual references asked for two clips; FFmpeg
  cut them from the fixture; the second multimodal call produced the findings
  (`visual_context_count=2`, both usage legs summed).
- **End-to-end analysis via the API** (local server on :8090, real Firebase token from the
  user, real Firestore/Gemini): project `e364f01c9642473fbf09da6991f7e24c` run
  `9dcdf2f9bf6948dfb7934ecdc8ec5e7c` -> `ready`, all 6 core reviewers succeeded, 14 findings,
  `overallScore 2.29`, `costEstimateUsd $0.009566`. (That run's reviewers requested no footage —
  the earlier soft prompt; the directive prompt now triggers it, verified directly.)
- Full `run_transcribe` was not re-run end to end (would re-STT a full fixture); the repair
  step itself was verified against real Gemini and the save path is covered by mypy plus the
  pre-built-segment test.

## Notes / gotchas

- The multimodal Gemini call logs a benign google-genai warning about automatic function
  calling on `generate_content`; it is SDK chatter, not an error, and predates tools.
- `MODEL_TRANSCRIPT_REPAIR` default is `gemini-3.1-flash-lite`; deploy overrides it to
  `gemini-3.8-flash`. Repair output tokens skew high (model thinking) but each transcript is
  pennies.
- Visual tool cost is bounded per reviewer **chunk** by `MAX_VISUAL_CONTEXT_REQUESTS`; a long
  transcript has more chunks, so a run with many chunks can add several vision calls. The
  per-project cost cap (`MAX_PROJECT_COST_USD`) is the backstop.
- Test artifact left in the account: project `e364f01c9642473fbf09da6991f7e24c` now has an
  extra analysis run (`9dcdf2f9bf6948dfb7934ecdc8ec5e7c`). Delete the project if unwanted.

## Not done / next steps

1. **Deploy required** for `ffmpeg` and the new env vars to exist in prod; the Docker image now
   installs FFmpeg, but until the API is redeployed the reviewer tools are unavailable there.
2. Tier-2 deep review (`includeVisualReview`) is still the documented-but-unbuilt separate flow;
   this change gives tier 1 the same primitive, not the on-demand deep pass.
3. Consider surfacing `visualContextCount` in the review UI (data is in the API, not rendered).
4. Consider whether to also feed a frame/clip into the project chat agent tools later.
