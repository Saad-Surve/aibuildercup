# Creator Helper Studio — Backend and AI Implementation Plan

## 1. Recommended backend choice

Use Python FastAPI plus Google ADK for the MVP backend.

~~~text
FastAPI: HTTP API, authentication, request validation, SSE
Google ADK: project assistant and multi-reviewer orchestration
Google GenAI SDK: direct structured Gemini calls where an agent is unnecessary
Pydantic: request/response and reviewer schemas
Cloud Run: API service
Cloud Run Jobs: long-running media workers
Pub/Sub: event delivery
~~~

This keeps the agent runtime in one language and makes the Google ADK architecture visible. Genkit is a strong alternative for a TypeScript backend, but using FastAPI, ADK, and Genkit in the same request path would add unnecessary runtime complexity.

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
│   │   ├── structure_agent.py
│   │   ├── cultural_agent.py
│   │   ├── platform_agent.py
│   │   ├── seo_agent.py
│   │   ├── safety_agent.py
│   │   ├── retention_agent.py
│   │   ├── accessibility_agent.py
│   │   └── brand_voice_agent.py
│   ├── connectors/
│   │   ├── base.py
│   │   ├── youtube.py
│   │   ├── instagram.py
│   │   └── facebook.py
│   └── workers/
│       ├── pubsub_handlers.py
│       ├── transcribe_worker.py
│       ├── analysis_worker.py
│       ├── social_sync_worker.py
│       ├── media_worker.py
│       └── localization_worker.py
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
  -> create transcription job
  -> call Speech-to-Text V2 with GCS input
  -> enable word time offsets
  -> normalize response
  -> segment transcript
  -> generate VTT and SRT
  -> write canonical files to GCS
  -> write metadata and segments to Firestore
  -> publish transcript.ready
~~~

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
    score: float = Field(ge=0, le=10)
    confidence: float = Field(ge=0, le=1)
    severity: Literal["none", "low", "medium", "high", "critical"]
    finding_type: str
    evidence: Evidence
    suggestion: str
    citations: list[Citation] = []
~~~

Reviewer dimensions:

~~~text
truth
clarity
structure
cultural
platform
seo
legal_safety
audience_retention
accessibility
brand_voice
~~~

### Truth reviewer policy

The truth reviewer should:

1. Extract factual claims.
2. Identify claims requiring verification.
3. Use approved grounding/search tools where available.
4. Return citations for supported claims.
5. Mark uncertain claims as needs_manual_verification.

It must not produce a confident factual verdict solely from model memory.

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
10 structure examples
10 truth and evidence examples
10 cultural and localization examples
10 safety examples
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
