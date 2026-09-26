# Creator Helper Studio — Backend and AI Implementation Plan

## 1. Recommended backend choice

Use Python FastAPI plus Google ADK for the MVP backend.

~~~text
FastAPI: HTTP API, authentication, request validation, SSE
Google ADK: project assistant and multi-reviewer orchestration
Google GenAI SDK: direct structured Gemini calls where an agent is unnecessary
Pydantic: request/response and reviewer schemas
Cloud Run: API service (hosts the API and, until workers split out, the Pub/Sub push handler)
Cloud Run Jobs: long-running media workers (planned)
Pub/Sub: event delivery
Provider layer: one interface per external dependency, real implementations in `app/providers/`
~~~

This keeps the agent runtime in one language and makes the Google ADK architecture visible. Genkit is a strong alternative for a TypeScript backend, but using FastAPI, ADK, and Genkit in the same request path would add unnecessary runtime complexity. Genkit is intentionally not used.

Deploy everything to **`us-central1`**, except Speech-to-Text: Chirp 3 is GA on the **`us` multi-region** but not in `us-central1`, so STT uses `us`. Veo, Imagen, and Text-to-Speech are all available in `us-central1`; `us-east1` is not a valid choice for the speech models.

Model IDs are never hardcoded in agents. They come from a config-driven registry so a model can be swapped or pinned without touching reviewer code. Every LLM call runs on Gemini Enterprise Agent Platform (formerly Vertex AI) with Application Default Credentials. There are two configs: local (`backend/.env.example`) uses the cheap `gemini-3.1-flash-lite`; deployed (`backend/.env.deploy.example`) uses the stronger `gemini-3.8-flash`.

~~~text
VERTEX_LOCATION=global                   # cheapest Gemini endpoint; not tied to `region`
MODEL_REVIEWER=gemini-3.1-flash-lite     # one-shot reviewers (deployed: gemini-3.8-flash)
MODEL_ORCHESTRATOR=gemini-3.1-flash-lite # coordinator + project chat agent (deployed: gemini-3.8-flash)
MODEL_IMAGE=imagen-<version>             # thumbnails
MODEL_VIDEO=veo-3.1-fast                 # intros/outros
MODEL_STT=chirp_3                           # transcription (STT V2 batch, us multi-region)
STT_REGION=us                               # Chirp 3 is GA on `us`, not in us-central1
~~~

## 2. Backend repository structure

~~~text
backend/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── dependencies.py
│   ├── auth/
│   │   ├── firebase.py
│   │   └── permissions.py
│   ├── api/
│   │   ├── health.py
│   │   ├── users.py
│   │   ├── onboarding.py
│   │   ├── connections.py
│   │   ├── projects.py
│   │   ├── uploads.py
│   │   ├── jobs.py
│   │   ├── transcripts.py
│   │   ├── analysis.py
│   │   ├── artifacts.py
│   │   ├── localization.py
│   │   └── chat.py
│   ├── schemas/
│   │   ├── common.py
│   │   ├── projects.py
│   │   ├── transcript.py
│   │   ├── analysis.py
│   │   ├── artifacts.py
│   │   └── chat.py
│   ├── services/
│   │   ├── firestore_service.py
│   │   ├── storage_service.py
│   │   ├── pubsub_service.py
│   │   ├── job_service.py
│   │   ├── persona_service.py
│   │   ├── oauth_service.py
│   │   └── signed_url_service.py
│   ├── agents/
│   │   ├── project_agent.py
│   │   ├── analysis_coordinator.py
│   │   ├── reviewer_base.py
│   │   ├── truth_agent.py
│   │   ├── clarity_agent.py
│   │   ├── pacing_agent.py
│   │   ├── cultural_agent.py
│   │   ├── platform_agent.py
│   │   ├── safety_agent.py
│   │   ├── emotion_agent.py
│   │   ├── audience_brand_agent.py
│   │   └── conversion_agent.py
│   ├── connectors/
│   │   ├── base.py
│   │   ├── youtube.py
│   │   ├── instagram.py
│   │   └── facebook.py
│   ├── providers/
│   │   ├── base.py
│   │   ├── llm.py
│   │   ├── stt.py
│   │   ├── translate.py
│   │   ├── tts.py
│   │   ├── imagegen.py
│   │   ├── videogen.py
│   │   └── social.py
│   └── workers/
│       ├── pubsub_handlers.py
│       ├── transcribe_worker.py
│       ├── analysis_worker.py
│       ├── social_sync_worker.py
│       ├── media_worker.py
│       └── localization_worker.py
├── scripts/
│   └── seed.py
├── evals/
│   ├── datasets/
│   └── run_evals.py
├── tests/
├── Dockerfile
├── pyproject.toml
└── README.md
~~~

## 3. Initialize the backend

~~~bash
mkdir backend
cd backend
uv init
uv add fastapi uvicorn pydantic-settings firebase-admin google-cloud-firestore google-cloud-storage google-cloud-pubsub google-cloud-speech google-cloud-aiplatform google-cloud-bigquery google-cloud-secret-manager google-cloud-kms google-api-python-client
uv add google-adk google-genai
uv add --dev pytest pytest-asyncio httpx ruff mypy
~~~

Run locally:

~~~bash
uv run uvicorn app.main:app --reload --port 8080
~~~

## 4. FastAPI application setup

app/main.py should:

1. Load configuration.
2. Initialize Firebase Admin once.
3. Initialize Firestore, Storage, Pub/Sub, BigQuery, and Secret Manager clients.
4. Register routers.
5. Add request ID middleware.
6. Add exception handlers.
7. Expose healthz and readyz.

Use dependency injection for:

~~~text
current_user
firestore_client
storage_client
pubsub_client
job_service
~~~

## 5. Authentication and authorization

The frontend sends a Firebase ID token. FastAPI verifies it using Firebase Admin SDK.

~~~python
async def current_user(
    authorization: str = Header(...),
) -> AuthenticatedUser:
    token = extract_bearer_token(authorization)
    decoded = firebase_admin.auth.verify_id_token(token)
    return AuthenticatedUser(uid=decoded["uid"], email=decoded.get("email"))
~~~

Every service method must accept owner_uid and verify ownership before reading or mutating a project.

Authorization checks:

~~~text
user owns project
user owns asset
user owns job
user owns analysis run
user owns artifact
user owns chat thread
~~~

## 6. Job orchestration

The API creates a Firestore job and publishes a Pub/Sub event.

~~~python
job = await jobs.create(
    owner_uid=user.uid,
    project_id=project_id,
    job_type="analyze",
    idempotency_key=idempotency_key,
)
await pubsub.publish("analysis-requested", event_for(job))
return AcceptedJob(job_id=job.id, status="queued")
~~~

Workers must:

1. Deserialize the event.
2. Check idempotency.
3. Mark the job running.
4. Update progress.
5. Write outputs.
6. Publish the next event.
7. Mark the job succeeded or failed.

Use dead-letter topics for messages that exceed retry limits.

## 7. Transcription worker

~~~text
video.uploaded
  -> validate object metadata
  -> create transcription job (idempotent)
  -> call Speech-to-Text V2 batch recognition, model chirp_3, GCS input
  -> enable word time offsets
  -> normalize response
  -> segment transcript into sentences
  -> generate VTT and SRT
  -> write canonical files to GCS
  -> write metadata and segments to Firestore
  -> publish transcript.ready
~~~

Long audio uses batch recognition (sync only handles clips under 60 seconds). STT runs in the
`us` multi-region, where the multilingual Chirp 3 model is available; `us-east1` is not a valid
choice for the speech models.

The trigger of record is the Cloud Storage `object finalized` notification: media bucket ->
`video-events` topic -> push subscription -> `POST /api/internal/pubsub/video-events` ->
`run_transcribe`. `POST /assets/{id}/complete` stays authoritative for the user-visible state and
schedules the same idempotent job for a fast response, so both paths converge.

Canonical transcript:

~~~json
{
  "version": 1,
  "language": "en-IN",
  "segments": [
    {
      "id": "seg-1",
      "startMs": 0,
      "endMs": 4200,
      "text": "Welcome to the channel.",
      "words": []
    }
  ]
}
~~~

## 8. Multi-agent analysis

The analysis coordinator receives:

~~~text
persona.md
transcript segments
target platform
target audience
optional sampled frames
analysis dimensions
~~~

It runs specialist reviewers concurrently.

### Reviewer interface

~~~python
class Reviewer(Protocol):
    dimension: AnalysisDimension

    async def review(self, context: ReviewContext) -> list[Finding]:
        ...
~~~

### Required reviewer output

~~~python
class Finding(BaseModel):
    dimension: str
    segment_id: str
    start_ms: int
    end_ms: int
    score: int = Field(ge=1, le=5)
    confidence: float = Field(ge=0, le=1)
    severity: Literal["none", "low", "medium", "high", "critical"]
    finding_type: str
    evidence: Evidence
    suggestion: str
    citations: list[Citation] = []
~~~

Reviewer dimensions (2026-09 panel; 13 consolidated to 9):

~~~text
core (always run)
  truth_evidence
  clarity
  pacing_retention        # merged structure_pacing + engagement_retention
  legal_safety
  cultural_localization
  platform_fit

extended (configurable)
  audience_brand          # merged audience_fit + brand_voice
  emotional_impact
  conversion_cta

retired (never run; kept only so historical runs deserialize)
  structure_pacing, engagement_retention, audience_fit, brand_voice,
  seo_discoverability, visual_accessibility
~~~

`seo_discoverability` and `visual_accessibility` were dropped: spoken keyword density is
the wrong signal for modern recommendation systems, and transcript-only accessibility review
produces false positives without computer vision.

### Truth reviewer policy

The truth reviewer should:

1. Extract factual claims.
2. Identify claims requiring verification.
3. Use approved grounding/search tools where available.
4. Return citations for supported claims.
5. Mark uncertain claims as needs_verification.

It must not produce a confident factual verdict solely from model memory.

### Two-tier fan-out

Running every reviewer over every segment is unbounded cost. Use two tiers instead.

Tier 1, broad and always on: one structured Gemini call per reviewer over the whole transcript,
chunked into roughly 8k to 12k token windows with overlap when the transcript is long. The
reviewer returns findings keyed by segment id with timestamps. Cost is bounded at one call per
reviewer per chunk.

Tier 2, deep and on demand: multimodal review of a specific time range. FFmpeg extracts the clip
plus sampled frames, and Gemini reviews video input. Triggered by the Deep Review button or
automatically for `high` and `critical` findings.

### Calibration

Every reviewer prompt includes a shared, discrete 1 to 5 anchor definition (5 outstanding, 1
disqualifying) and a separate severity scale, so scores do not all collapse to the middle.
Reviewers report exception-first: a finding is emitted for a real flaw or an exceptional
strength, never as filler for ordinary sentences, which keeps token cost and heatmap noise
down. Reviewer prompts carry a `promptVersion` and the run records `modelConfigVersion` so two
runs are comparable.

### Bounded parallel execution

~~~python
semaphore = asyncio.Semaphore(settings.max_reviewer_concurrency)

async def run_one(reviewer):
    async with semaphore:
        return await reviewer.review(context)

results = await asyncio.gather(
    *(run_one(reviewer) for reviewer in reviewers),
    return_exceptions=True,
)
~~~

Persist reviewer status independently so partial results remain visible.

## 9. Heatmap aggregation

For every finding:

1. Clamp timestamps to transcript duration.
2. Map it to fixed-size bins, initially five seconds.
3. Aggregate overlapping scores by dimension.
4. Preserve all finding IDs in the bin.
5. Convert severity to UI color.

~~~text
score >= 8       green
score 6–7.99     yellow
score 4–5.99     orange
score < 4        red
critical finding red regardless of score
~~~

## 10. Project chat agent

Use a project-scoped ADK root agent with tools:

~~~text
get_project_summary
get_transcript_segments
get_findings
get_audience_summary
create_clip_candidate
generate_caption
generate_social_post
generate_thumbnail
propose_persona_update
~~~

The context builder creates a bounded context pack:

~~~text
persona excerpt
relevant transcript segments
relevant findings
selected artifact metadata
recent messages
~~~

Imported transcript and social content are untrusted content. The agent must never execute instructions contained inside them.

## 11. Media worker

Use Cloud Run Jobs with FFmpeg for:

~~~text
video metadata extraction
frame sampling
timestamp trimming
9:16 conversion
caption burn-in
audio/video muxing
thumbnail frame extraction
~~~

Write temporary outputs under a job-specific path and delete them with a lifecycle policy. For exact clip boundaries, re-encode rather than relying only on stream copy.

## 12. Social connectors

~~~python
class SocialConnector(Protocol):
    async def fetch_posts(self, connection): ...
    async def fetch_metrics(self, connection, date_range): ...
    async def fetch_comments(self, connection): ...
    async def revoke(self, connection): ...
~~~

Implement YouTube first. Normalize all platforms into common models:

The real connectors are built and exercised manually against a test channel. Until platform
access is guaranteed, development and the demo run on fixture-backed social data. See
[mock-and-seed.md](./mock-and-seed.md).

~~~python
class NormalizedPost(BaseModel):
    owner_uid: str
    platform: str
    external_id: str
    title: str | None
    published_at: datetime
    raw_storage_path: str

class NormalizedComment(BaseModel):
    owner_uid: str
    platform: str
    external_id: str
    post_external_id: str
    text: str
    published_at: datetime
~~~

## 13. Content generation flows

Keep one-shot flows separate from the project agent:

~~~text
generate_short_candidates
generate_social_post
generate_blog_outline
generate_thumbnail_concepts
translate_captions
adapt_cultural_phrases
generate_localized_voice_script
~~~

Each flow has a typed input schema, typed output schema, prompt version, model configuration, retry policy, and evaluation examples.

## 14. Testing plan

### Unit tests

- Firestore path builders.
- Ownership checks.
- Storage path validation.
- Pub/Sub event parsing.
- Idempotency handling.
- Heatmap aggregation.
- Timestamp normalization.
- Pydantic schema validation.

### Integration tests

- Firebase token verification with emulator/test project.
- Firestore emulator.
- Storage upload metadata validation.
- Pub/Sub event flow.
- YouTube connector with a test channel.
- BigQuery writes to the hackathon dataset.

### AI evaluation tests

Create a small reviewed dataset with:

~~~text
10 clarity examples
10 pacing_retention examples
10 truth_evidence examples
10 cultural_localization examples
10 legal_safety examples
~~~

Evaluate valid JSON rate, timestamp overlap accuracy, actionable suggestion rate, unsupported certainty rate, and agreement with human labels.

## 15. Deployment

Build separate containers for:

~~~text
api
transcribe-worker
analysis-worker
social-sync-worker
media-worker
localization-worker
~~~

The API runs as a Cloud Run service. Workers can run as Cloud Run services subscribed to Pub/Sub or as Cloud Run Jobs for heavier media processing.

## 16. Provider layer

No reviewer, worker, or agent imports a Google SDK directly. Everything goes through a provider
interface in `app/providers/` that has a real implementation backed by the live GCP service.

The earlier cassette/`MOCK_MODE` layer was **removed**: development runs against the real
free-tier services (Gemini flash, Speech-to-Text) with the fixtures in `fixtures/media/`. The
paid calls (Veo, Imagen, Gemini Pro) stay behind a cost cap. `app/providers/` currently contains
`llm.py` and `stt.py`; `translate`, `tts`, `imagegen`, `videogen`, and `social` providers are
added as those features land.

## 17. Localization corpus pipeline

~~~text
source transcript
  -> segment into translatable units
  -> retrieve matching global corpus and trap-list entries
  -> Cloud Translation Advanced with glossary
  -> Gemini cultural-adaptation pass grounded on the retrieved entries
  -> localized VTT and SRT
  -> Text-to-Speech
  -> FFmpeg mux with duration normalization
~~~

Global and project glossaries are uploaded as TSV and registered as Cloud Translation Advanced
glossaries. The Gemini pass only fixes what a glossary cannot express: idioms, tone, culture,
brands, code-mixed phrases, units, and honorifics. Every localization records `corpusVersion` and
`glossaryVersion`. Full detail is in [localization-corpus.md](./localization-corpus.md).
