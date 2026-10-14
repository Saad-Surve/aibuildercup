# Resonance backend implementation

This is the current implementation reference, not a scaffold to build from scratch.
[Architecture](../architecture.md) explains design tradeoffs; [reviewer prompts](../reviewer-prompts.md)
describe the actual specialist instructions.

## 1. Runtime

FastAPI handles HTTP/auth/WebSocket. Custom Python async coordination fans out Gemini
reviewers; `providers/llm.py` owns structured generation and bounded function-call loops.
Google ADK remains installed, but there is no ADK Runner in the current flows. Model IDs,
locations, concurrency and price estimates come from `app/config.py` and environment.

## 2. Layout and I/O boundaries

`api/` validates/authenticates; `schemas/` defines payloads; `services/` owns persistence
and feature logic; `providers/` wraps Google/model calls; `connectors/` adapts YouTube;
`agents/` contains reviewers; `workers/` executes jobs; `realtime/` delivers progress.

Sync cloud routes use plain `def` for FastAPI's thread pool. Async flows use
`asyncio.to_thread` for blocking cloud/media work. Model/socket work remains asynchronous.
Firestore bulk writes commit up to 400 documents; completion events follow persistence.

## 3. Local setup

Use [backend/README.md](../../backend/README.md): uv, ADC, `.env.example`, FFmpeg/ffprobe.
There is no mock/cassette mode. Development calls live services and can incur charges.

## 4. Application

`main.py` registers the actual routers with `/api`, initializes CORS, a structured error
envelope, request IDs, no-store authenticated responses and demo write enforcement.
Local `/docs` exposes runtime OpenAPI; production disables Swagger.

## 5. Authentication

Firebase verifies ID tokens. User/project reads and writes check ownership. Internal
Pub/Sub push verifies OIDC when its audience/service account are configured. Firestore
rules deny direct browser access. OAuth uses state/PKCE and encrypted stored tokens.

## 6. Jobs and events

`JobService` atomically creates deterministic IDs from owner/project/idempotency keys;
legacy IDs remain readable. Upload-complete and Storage-finalized notifications converge
on one transcribe job. Other jobs are normally scheduled through `BackgroundTasks` in
this API process. The execution guard and realtime hub are process-local.

Jobs persist status/progress/output/error and events under the project. HTTP reads remain
a degraded fallback; WebSocket subscribers receive project snapshots/events and can
unsubscribe. Queue overflow closes slow sockets rather than silently dropping progress.
Job cancellation is a stored request, not a guarantee that every upstream operation stops.

## 7. Transcription

Chirp 3 uses STT V2 batch recognition in `us`. AAC inside MP4/MOV/M4A has explicit
decoding configuration; other supported audio uses auto-detection. Word/speaker data
becomes clamped segments and versioned JSON/SRT/VTT. Optional conservative Gemini cleanup
falls back to raw speech recognition. The worker can normalize problematic AAC containers.
Transcript edits/retranscription and video revision activation preserve source references.

Submission and polling are separate provider calls. Jobs persist a submission marker and each
operation name before polling, so resumed workers reattach with GetOperation. Submission retries
are limited to explicit 429 rejections; polling retries 429/503/deadline errors with bounded
backoff and jitter, without submitting another batch. One configured deadline covers recognition
and its deliberate fallbacks per worker invocation. Only terminal audio/container failures permit
normalization; only terminal diarization rejections permit a plain attempt. Staged normalized
audio remains available while polling can resume. An ambiguous submission with no saved name
blocks automatic retry, as with Veo. Worker serialization remains process-local.

## 8. Multi-reviewer analysis

Nine active dimensions; six core are always included and the web requests all nine.
The coordinator partitions roughly 36k-character windows with neighboring context and
bounded distant continuity excerpts. Every segment/time interval has one owner. Reviewer
concurrency is four; chunks are serial per reviewer. Up to three/six shared stills are
sampled once per short/long video. Optional footage tools allow three requests and two
rounds per reviewer/chunk. Truth can use Google Search grounding.

Outputs include span, dimension, 1–5 quality score, severity, evidence/reasoning, suggestion
and optional citations. Normalization rejects nonmatching spoken quotes and missing
explanation/action; exact repeated advice is deduplicated within dimension/type.
Omission/visual findings can have empty quotes. Shared/requested footage remains project-owned.
Partial reviewer/chunk failures preserve useful findings and mark coverage incomplete.

These are specialized model prompts, not independent expert consensus. Confidence is not
calibrated; URL presence/quote validity cannot establish factual correctness. Evaluation
methods and actual measurement scope are in [evals](../../evals/README.md).

## 9. Heatmap

`services/heatmap.py` maps findings into five-second bins, weights overlapping quality
scores by milliseconds, preserves finding IDs, and forces critical findings red.
Empty spans have no invented score. `overallScore`/the UI's Flagged moments summary
averages reported observations, not the whole video or predicted retention.

## 10. Draft writing

Brief-driven drafts keep block versions, active version pointers, messages and grounding.
Initial generation retrieves creator passages; assist supports chat, rewrites, alternatives
and continuation. Short suggestions do not retrieve the library. Search can ground initial
writing/chat. A generation error may produce deterministic fallback blocks; ready status
alone is not proof of successful AI generation. Web exports active or all-version content.

## 11. Media

Captions render ASS overlays with FFmpeg and persist progress/output. Localization uses
Translation → corpus/glossary-aware Gemini adaptation → bounded TTS → duration adjustment
→ audio/video mux. Source dimensions/duration are probed once during staging. Thumbnail
jobs plan concepts, attach real source frames and retrieved creator images, render, critique
and preserve revisions; batches cap at four concepts.

## 12. YouTube and calendar

OAuth connects YouTube accounts; content/captions and 28-day audience analytics sync into
owned Firestore records. Publication uploads source/output media and optionally captions
and a thumbnail, with future scheduling delegated to YouTube. Month/week calendar entries
are project-owned. Other platform labels do not imply publishing connectors.

## 13. Packaging

Packaging generates/saves YouTube title/description/tags and source-linked visual ideas.
Chart numbers must occur in quoted source spans; charts/callouts render with FFmpeg.
Optional six-second Veo inserts use explicit paid authorization, atomic project slots
and a stored operation name for resumable polling. At most two slots are enabled by default.
Old source/transcript references mark packaging stale. The
[handoff](../current-progress/HANDOFF.md) records
live local generation, listing edits and a callout render. Full paid production flow
was not exercised by the documentation/evaluation run.

## 14. Verification and evaluation

Run Ruff and mypy; follow [the evaluation guide](../../evals/README.md) for real-data
benchmarks. Repository instructions prohibit adding test suites/testing dependencies.
Human-adjudicated review correctness and accepted-edit value remain unmeasured.

## 15. Deployment and scale

One API container currently hosts the workers. GitHub Actions deploys Cloud Run at
max-instances one, 1 GiB and CPU available after responses; web deploys to Firebase Hosting.
Durable dispatch, distributed leases and shared realtime are prerequisites for multiple
worker instances. Provisioned service accounts/subscriptions do not imply deployed consumers.

## 16. Providers

`llm`, `embeddings`, `stt`, `tts`, `translate`, `imagegen`, `videogen` and creator-source
providers wrap live calls. Firestore/Storage/Pub/Sub/KMS use dedicated infrastructure
adapters. Feature logic does not import Google SDKs. Gemini uses ADC and `global` by default;
STT uses `us`; Veo uses `us-central1`. No API key is needed for these Gemini paths.

## 17. Localization corpus and lifecycle

The runtime corpus is `app/assets/corpus/global.json`, not a BigQuery/GCS glossary service.
Project glossary terms and versions snapshot onto localizations. Native Translation glossary
registration is not wired; term/trap handling occurs in the Gemini adaptation pass.
See [localization](localization-corpus.md), [database/deletion](db-design.md) and
[cost guards](../costs.md) for implemented boundaries.
