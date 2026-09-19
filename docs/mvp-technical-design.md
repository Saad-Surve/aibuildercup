# ClarityLoop — Technical MVP Design

## 1. Product decision

**Working name:** ClarityLoop

ClarityLoop is an AI content quality and comprehension debugger for creators. A creator uploads one long-form video, selects a target audience, and receives:

1. A timestamped transcript and concept map.
2. Evidence-linked content review findings.
3. Claim verification with sources and uncertainty labels.
4. A synthetic audience diagnostic showing which personas understand which concepts.
5. An understanding heatmap and prioritized edit suggestions.
6. A repurposing pack: short-form script, caption, hashtags, poll, LinkedIn post, X post, and thumbnail.

The core differentiator is not “generate more content.” It is the **understanding heatmap**: the creator can see where specific audience personas are likely to diverge in comprehension, why, and what edit would repair the problem.

This design turns the notes in `finalised-idea.md` into one cohesive product loop and directly matches the Media, Content & Digital Experiences problem statement: creators spend too much time repackaging content, while audiences need content at a different language, reading level, pace, and format.

## 2. MVP user journey

### Step 1: Create a project

The user signs in, creates a project, and enters three audience personas. The onboarding form captures:

- Persona name: for example, “Beginner Hindi-speaking learner”.
- Locale and preferred language.
- Familiarity: beginner, intermediate, or expert.
- Goal: learn, be persuaded, subscribe, buy, or share.
- Known context and likely misconceptions.

The project is the main entity. A user can own many projects, and every project-owned record is scoped by `ownerId`.

### Step 2: Upload one source video

The browser asks the API for a short-lived V4 resumable upload URL, then uploads directly to Cloud Storage. The API never proxies video bytes. The browser sends a `media.uploaded` event after the upload completes.

MVP limits:

- One source video per analysis run.
- MP4, MOV, or WebM.
- Maximum 500 MB and 60 minutes.
- One active run per project.

### Step 3: Analyze the source

An asynchronous pipeline performs these stages:

1. Validate the object and create an immutable source-asset record.
2. Transcribe audio with Speech-to-Text V2, model `chirp_3`.
3. Extract concepts, claims, narrative structure, and timestamps with Gemini.
4. Run seven content reviewers against the transcript and concept map.
5. Verify the highest-risk claims using Gemini grounding with Google Search.
6. Generate three diagnostic questions per persona.
7. Simulate persona responses, calculate comprehension by concept, and generate the heatmap.
8. Generate the repurposing pack and one thumbnail.
9. Mark the run `READY` and stream the result to the dashboard.

The UI shows progress by stage and never waits on a long-running request.

### Step 4: Debug and accept edits

Each finding is anchored to transcript segment IDs and therefore to a timestamp. The creator can select `Keep`, `Undo`, or `Dismiss`.

- `Keep` adds the finding to the accepted edit list.
- `Undo` hides it from the working list but retains the audit history.
- `Dismiss` means “not useful for this project” and is included in later product analytics.

The MVP does not rewrite or render the original video. The accepted edits become an exportable edit brief and are used to generate the derivative pack.

### Step 5: Export

The creator can download a Markdown/JSON content pack containing the short-form script, caption, hashtags, poll, LinkedIn post, X post, evidence table, and thumbnail. The video export itself is intentionally out of scope for the MVP.

## 3. Product scope and deliberate exclusions

### Included in the hackathon MVP

- Google/Firebase authentication.
- One creator workspace and multiple projects.
- Direct video upload to Cloud Storage.
- Timestamped transcript with speaker labels where available.
- Concept map and claim list.
- Review dimensions: truth/evidence, clarity, structure, audience fit, engagement, visual/accessibility, and safety/legal risk.
- Evidence and source URLs for factual findings.
- Three configurable personas per project.
- Synthetic audience diagnostic and comprehension heatmap.
- Keep/undo/dismiss finding workflow.
- Short-form script, social copy, poll, and thumbnail generation.
- Firebase-hosted dashboard deployed through Cloud Run-backed APIs.

### Explicitly deferred

- Automatic video cutting, stitching, or final video rendering.
- Real YouTube, Instagram, LinkedIn, X, Substack, or Medium connectors.
- Real community polling and ingestion of social comments.
- Live trending-topic ingestion.
- Multi-user editorial collaboration and permissions beyond owner access.
- Full translation/dubbing workflow.
- Training or fine-tuning a custom model.
- Claims of actual audience behavior: synthetic diagnostics are labeled as simulations until real responses are collected.

This boundary is important: the MVP proves the novel comprehension-debugging workflow without spending the hackathon on media rendering and third-party OAuth integrations.

## 4. System architecture

```text
Browser: React + Vite + Firebase Auth
        │
        ├── Firebase Hosting (static dashboard)
        ├── Firebase Auth (Google/email sign-in)
        └── direct resumable upload via signed URL
                         │
                         ▼
                 Cloud Storage: source media
                         │
                   API creates job
                         │
                         ▼
                   Pub/Sub: analysis-jobs
                         │ authenticated push
                         ▼
             Cloud Run: media-worker (idempotent pipeline)
                │          │          │
                │          │          ├── Speech-to-Text V2 / chirp_3
                │          ├───────── Gemini on Vertex AI
                │          │          └── Google Search grounding for claims
                │          └────────── Imagen 4 Fast thumbnail
                │
                ├── Firestore: project state and review results
                ├── Cloud Storage: transcripts, JSON outputs, thumbnail
                └── BigQuery: event and outcome analytics

Browser ── Firebase ID token ──► Cloud Run: api
                                      │
                                      ├── Firestore reads/writes
                                      ├── signed URL creation
                                      └── Pub/Sub job publishing
```

### Why this architecture

- Cloud Run gives a deployable GCP container with scale-to-zero and a clean hackathon deployment story.
- Pub/Sub separates upload/API latency from AI processing and provides retry/dead-letter behavior.
- Cloud Storage is the right place for large binary media; Firestore holds small, queryable application documents.
- BigQuery is reserved for analytics, not transactional state.
- Gemini is used for structured reasoning tied to transcript evidence, not untraceable free-form generation.

## 5. Technology stack

| Layer | Choice | Purpose |
|---|---|---|
| Frontend | React 19, Vite, TypeScript | Fast static dashboard and upload flow |
| UI | Tailwind CSS, shadcn/ui, Recharts | Accessible components and comprehension heatmap |
| Authentication | Firebase Auth | Google sign-in and email/password fallback |
| Hosting | Firebase Hosting | CDN, HTTPS, SPA fallback, Cloud Run rewrite |
| API | Python 3.12, FastAPI, Pydantic v2 | Typed REST API and auth boundary |
| AI orchestration | Python service layer with explicit pipeline stages | Deterministic, debuggable workflow |
| Gemini client | Google Gen AI SDK using Vertex AI | Structured JSON analysis and grounded claim verification |
| Speech | Cloud Speech-to-Text V2, `chirp_3` | Multilingual transcript, language detection, diarization where supported |
| Image | Imagen 4 Fast | One thumbnail per run |
| Operational DB | Cloud Firestore Native mode | Users, projects, assets, findings, personas, diagnostics |
| Object storage | Cloud Storage | Source video and generated artifacts |
| Queue | Pub/Sub | Asynchronous analysis jobs, retries, dead-letter queue |
| Analytics | BigQuery | Event funnel, time-to-ready, finding acceptance, persona scores |
| Containers | Docker, Artifact Registry | Reproducible API and worker images |
| Deployment | Cloud Build + Cloud Run | Build and deploy on every main-branch push |
| Observability | Cloud Logging, Cloud Monitoring, Error Reporting | Job traces, failures, latency, cost signals |
| Secrets | Secret Manager | Non-Firebase secrets only; prefer IAM credentials for Google APIs |

No separate vector database is required for this MVP. The transcript is short enough to pass as structured context to Gemini, and every reviewer finding must point back to transcript segments. Vector Search can be added later for multi-video projects.

## 6. GCP project configuration

Use one Google Cloud project per environment. For the hackathon, use one `dev` project and keep production-like settings in the same project with separate resource names.

### Fixed environment values

```text
PROJECT_ID       = <the hackathon Google Cloud project ID>
REGION           = asia-southeast1
BUCKET           = ${PROJECT_ID}-media
BQ_DATASET       = clarityloop_analytics
API_SERVICE      = clarityloop-api
WORKER_SERVICE   = clarityloop-worker
PUBSUB_TOPIC     = analysis-jobs
PUBSUB_SUB       = analysis-jobs-worker
PUBSUB_DLQ       = analysis-jobs-dead-letter
```

`asia-southeast1` is the single regional choice for Cloud Run, Storage, Firestore, BigQuery, and Speech-to-Text V2. It provides a practical Asia-Pacific deployment location and a GA region for Chirp 3. Gemini requests use the Vertex AI global endpoint where the selected model is available.

### APIs to enable

```text
run.googleapis.com
artifactregistry.googleapis.com
cloudbuild.googleapis.com
firestore.googleapis.com
storage.googleapis.com
pubsub.googleapis.com
speech.googleapis.com
aiplatform.googleapis.com
bigquery.googleapis.com
iamcredentials.googleapis.com
secretmanager.googleapis.com
logging.googleapis.com
monitoring.googleapis.com
firebase.googleapis.com
firebasehosting.googleapis.com
```

### Cloud Storage

Create one bucket named `${PROJECT_ID}-media`:

- Location: `asia-southeast1`.
- Storage class: Standard.
- Uniform bucket-level access: enabled.
- Public access prevention: enforced.
- Object versioning: enabled for the demo period.
- CORS: allow only the Firebase Hosting origin and local development origin; allow `GET`, `PUT`, `POST`, `HEAD`.
- Lifecycle: delete `tmp/` objects after 1 day; delete failed-run artifacts after 7 days; retain source and accepted artifacts until the user deletes the project.
- Customer-managed encryption keys are not needed for the MVP; use Google-managed encryption and IAM.

Object layout:

```text
projects/{projectId}/assets/{assetId}/source.mp4
projects/{projectId}/assets/{assetId}/audio.wav
projects/{projectId}/runs/{runId}/transcript.json
projects/{projectId}/runs/{runId}/concepts.json
projects/{projectId}/runs/{runId}/claims.json
projects/{projectId}/runs/{runId}/derivatives.json
projects/{projectId}/runs/{runId}/thumbnail.png
projects/{projectId}/runs/{runId}/export/content-pack.md
```

The API generates a V4 signed resumable upload URL with a 15-minute expiry. Result download URLs expire after 15 minutes and are generated only after ownership authorization.

### Firestore

- Database mode: Native.
- Location: `asia-southeast1`.
- Use the default database for the hackathon.
- Use server timestamps for all `createdAt` and `updatedAt` fields.
- Store large transcript text in Cloud Storage and only store a compact preview plus `transcriptStoragePath` in Firestore.
- All client reads are allowed only for the authenticated owner; writes to AI-generated fields are server-only.

### Pub/Sub

Create:

- Topic: `analysis-jobs`.
- Push subscription: `analysis-jobs-worker` targeting the authenticated `clarityloop-worker` Cloud Run URL.
- Acknowledgement deadline: 600 seconds.
- Retry policy: exponential backoff, minimum 10 seconds, maximum 600 seconds.
- Dead-letter topic: `analysis-jobs-dead-letter`, after 5 delivery attempts.
- Message ordering: disabled; idempotency is handled by `runId`.

Job message:

```json
{
  "eventType": "analysis.requested",
  "runId": "run_01J...",
  "projectId": "project_01J...",
  "assetId": "asset_01J...",
  "ownerId": "firebase-uid",
  "schemaVersion": 1,
  "requestedAt": "2026-09-19T10:00:00Z"
}
```

### BigQuery

- Dataset: `clarityloop_analytics`.
- Location: `asia-southeast1`.
- Partition event tables by `event_date`.
- Cluster by `project_id`, `run_id`, and `event_name`.
- Do not store raw video, full transcript text, auth tokens, or direct personal identifiers.

### Cloud Run API service

```text
Service: clarityloop-api
Region: asia-southeast1
CPU: 1 vCPU
Memory: 1 GiB
Min instances: 0
Max instances: 3
Concurrency: 40
Request timeout: 60 seconds
Ingress: all
Invoker: public at the Cloud Run layer; Firebase ID token required for every user endpoint
```

The service exposes `/healthz` publicly. Every other route verifies the Firebase ID token and then checks `ownerId` against the requested project. This avoids relying on a browser-supplied project ID for authorization.

### Cloud Run worker service

```text
Service: clarityloop-worker
Region: asia-southeast1
CPU: 2 vCPU
Memory: 2 GiB
Min instances: 0
Max instances: 2
Concurrency: 1
Request timeout: 900 seconds
Invoker: Pub/Sub push service account only
```

The worker acknowledges a message only after the current stage has persisted its output. If a stage fails, the worker writes `FAILED` with a safe error message and returns a non-2xx response so Pub/Sub retries. Every stage is safe to rerun because writes use deterministic document IDs derived from `runId`.

### IAM service accounts

Create two service accounts:

1. `clarityloop-api@PROJECT_ID.iam.gserviceaccount.com`
   - Firestore read/write.
   - Storage object create/read for the media bucket.
   - Pub/Sub publisher.
   - Firebase Admin verification.

2. `clarityloop-worker@PROJECT_ID.iam.gserviceaccount.com`
   - Storage object read/write for the media bucket.
   - Firestore read/write.
   - Pub/Sub subscriber.
   - BigQuery data editor for the analytics dataset.
   - Vertex AI user.
   - Speech-to-Text user.

Grant the Pub/Sub push service account `roles/run.invoker` on `clarityloop-worker`. Do not create service-account keys. Cloud Run uses its attached identity and Application Default Credentials.

### Model configuration

```text
Gemini reasoning/review model: gemini-3.5-flash
Gemini cheap classification model: gemini-3.5-flash-lite
Speech model: chirp_3 through Speech-to-Text V2
Thumbnail model: Imagen 4 Fast
Temperature: 0.2 for extraction/review; 0.7 for derivative copy
Max output: bounded per task; JSON schema required for all analysis calls
```

Use the same pinned model IDs in code, README, architecture slide, and demo notes. Keep the model names in environment variables so a model lifecycle change is a configuration change, not a code rewrite.

## 7. Firestore data model

Firestore is the operational source of truth. IDs are generated by the API with a sortable ID scheme; never use user-provided titles as document IDs.

### `users/{uid}`

```json
{
  "displayName": "Asha Creator",
  "email": "asha@example.com",
  "photoUrl": "https://...",
  "onboarding": {
    "defaultLocale": "en-IN",
    "creatorType": "educator",
    "defaultGoal": "educate"
  },
  "createdAt": "Timestamp",
  "updatedAt": "Timestamp"
}
```

### `projects/{projectId}`

```json
{
  "ownerId": "firebase-uid",
  "name": "AI literacy explainer",
  "description": "Explain AI agents to first-time builders",
  "status": "ACTIVE",
  "defaultLanguage": "en-IN",
  "targetPlatforms": ["youtube_shorts", "linkedin", "x"],
  "activeRunId": "run_01J...",
  "createdAt": "Timestamp",
  "updatedAt": "Timestamp"
}
```

### `projects/{projectId}/personas/{personaId}`

```json
{
  "name": "Beginner Hindi-speaking learner",
  "locale": "hi-IN",
  "language": "hi",
  "familiarity": "BEGINNER",
  "goal": "understand_and_share",
  "interests": ["technology", "career"],
  "knownContext": ["uses phone daily", "has heard of AI"],
  "active": true,
  "createdAt": "Timestamp",
  "updatedAt": "Timestamp"
}
```

### `projects/{projectId}/assets/{assetId}`

```json
{
  "ownerId": "firebase-uid",
  "type": "SOURCE_VIDEO",
  "fileName": "ai-agents.mp4",
  "contentType": "video/mp4",
  "sizeBytes": 183000000,
  "storagePath": "projects/project_01J.../assets/asset_01J.../source.mp4",
  "durationMs": 214000,
  "language": "en-IN",
  "uploadStatus": "COMPLETE",
  "createdAt": "Timestamp",
  "updatedAt": "Timestamp"
}
```

### `projects/{projectId}/runs/{runId}`

```json
{
  "ownerId": "firebase-uid",
  "assetId": "asset_01J...",
  "status": "READY",
  "stage": "DERIVATIVES",
  "progress": 92,
  "modelVersions": {
    "review": "gemini-3.5-flash",
    "fast": "gemini-3.5-flash-lite",
    "speech": "chirp_3",
    "thumbnail": "imagen-4-fast"
  },
  "transcriptStoragePath": "projects/.../runs/.../transcript.json",
  "conceptsStoragePath": "projects/.../runs/.../concepts.json",
  "claimsStoragePath": "projects/.../runs/.../claims.json",
  "derivativesStoragePath": "projects/.../runs/.../derivatives.json",
  "thumbnailStoragePath": "projects/.../runs/.../thumbnail.png",
  "summary": {
    "overallScore": 7.4,
    "topIssueCount": 3,
    "verifiedClaimCount": 8,
    "uncertainClaimCount": 2
  },
  "errorCode": null,
  "createdAt": "Timestamp",
  "updatedAt": "Timestamp",
  "completedAt": "Timestamp"
}
```

### `projects/{projectId}/runs/{runId}/segments/{segmentId}`

```json
{
  "index": 12,
  "startMs": 42000,
  "endMs": 58000,
  "speaker": "spk_0",
  "text": "An AI agent can call tools to complete a task.",
  "language": "en-IN",
  "confidence": 0.91
}
```

### `projects/{projectId}/runs/{runId}/concepts/{conceptId}`

```json
{
  "label": "tool calling",
  "plainLanguageSummary": "The model can use external actions instead of only writing text.",
  "importance": 0.88,
  "startMs": 42000,
  "endMs": 58000,
  "segmentIds": ["seg_012", "seg_013"],
  "prerequisiteConceptIds": []
}
```

### `projects/{projectId}/runs/{runId}/findings/{findingId}`

```json
{
  "dimension": "CLARITY",
  "score": 5,
  "confidence": 0.86,
  "severity": "MEDIUM",
  "title": "Define tool calling before using the term",
  "evidence": {
    "segmentIds": ["seg_012"],
    "quote": "The agent uses tools...",
    "startMs": 42000,
    "endMs": 58000
  },
  "suggestion": "Add a one-sentence definition and one concrete example before this section.",
  "status": "OPEN",
  "createdBy": "AI",
  "createdAt": "Timestamp",
  "updatedAt": "Timestamp"
}
```

### `projects/{projectId}/runs/{runId}/claims/{claimId}`

```json
{
  "text": "Agents can complete multi-step tasks by calling tools.",
  "segmentIds": ["seg_012", "seg_013"],
  "risk": "MEDIUM",
  "verdict": "SUPPORTED",
  "confidence": 0.84,
  "evidence": [
    {
      "title": "Official Google Cloud documentation",
      "url": "https://cloud.google.com/",
      "snippet": "...",
      "sourceType": "WEB"
    }
  ],
  "reviewRequired": false,
  "createdAt": "Timestamp",
  "updatedAt": "Timestamp"
}
```

Allowed `verdict` values are `SUPPORTED`, `CONTRADICTED`, `UNCERTAIN`, and `NOT_CHECKED`. The UI must never display `UNCERTAIN` as a binary false claim.

### `projects/{projectId}/runs/{runId}/diagnostics/{diagnosticId}`

```json
{
  "personaId": "persona_beginner_hi",
  "conceptId": "concept_tool_calling",
  "question": "What makes an agent different from a chatbot that only replies in text?",
  "options": ["It can use tools", "It is always correct", "It never needs data"],
  "simulatedAnswer": "It can use tools",
  "correctOptionIndex": 0,
  "understandingScore": 0.92,
  "confusionReason": null,
  "source": "SYNTHETIC_PERSONA",
  "createdAt": "Timestamp"
}
```

### `projects/{projectId}/runs/{runId}/derivatives/{derivativeId}`

```json
{
  "type": "SHORT_FORM_PACK",
  "platform": "MULTI",
  "title": "What an AI agent actually does",
  "hook": "A chatbot answers. An agent takes the next action.",
  "script": "...",
  "caption": "...",
  "hashtags": ["#AIAgents", "#GenAI"],
  "poll": {
    "question": "What should an AI agent do next?",
    "options": ["Search", "Send an email", "Update a sheet"]
  },
  "linkedinPost": "...",
  "xPost": "...",
  "thumbnailStoragePath": "projects/.../thumbnail.png",
  "acceptedFindingIds": ["finding_01J..."],
  "createdAt": "Timestamp",
  "updatedAt": "Timestamp"
}
```

### Required Firestore indexes

Create these composite indexes:

```text
projects: ownerId ASC, updatedAt DESC
projects/{projectId}/runs: status ASC, createdAt DESC
findings: dimension ASC, severity ASC, status ASC
diagnostics: personaId ASC, conceptId ASC
```

## 8. BigQuery analytics schema

Create these tables under `clarityloop_analytics`:

### `events`

```text
event_date DATE REQUIRED
event_ts TIMESTAMP REQUIRED
event_name STRING REQUIRED
user_id STRING NULLABLE
project_id STRING NULLABLE
run_id STRING NULLABLE
stage STRING NULLABLE
duration_ms INT64 NULLABLE
metadata JSON NULLABLE
```

Events include `project_created`, `upload_started`, `upload_completed`, `analysis_started`, `stage_completed`, `finding_kept`, `finding_undone`, `diagnostic_viewed`, `derivative_exported`, and `analysis_failed`.

### `run_metrics`

```text
run_id STRING REQUIRED
project_id STRING REQUIRED
completed_at TIMESTAMP NULLABLE
source_duration_seconds FLOAT64 NULLABLE
transcript_segment_count INT64 NULLABLE
concept_count INT64 NULLABLE
claim_count INT64 NULLABLE
uncertain_claim_count INT64 NULLABLE
finding_count INT64 NULLABLE
accepted_finding_count INT64 NULLABLE
overall_score FLOAT64 NULLABLE
median_comprehension FLOAT64 NULLABLE
processing_seconds FLOAT64 NULLABLE
```

### `heatmap_scores`

```text
run_id STRING REQUIRED
project_id STRING REQUIRED
persona_id STRING REQUIRED
concept_id STRING REQUIRED
understanding_score FLOAT64 REQUIRED
confidence FLOAT64 REQUIRED
confusion_reason STRING NULLABLE
source STRING REQUIRED
```

The dashboard reads its initial state from Firestore. BigQuery powers the creator impact panel and the hackathon story: time-to-ready, number of actionable findings, percentage of claims with evidence, and concept-level comprehension spread.

## 9. API contract

All endpoints require a Firebase ID token except `/healthz`. The API derives `ownerId` from the verified token.

```text
POST   /v1/projects
GET    /v1/projects
GET    /v1/projects/{projectId}
PATCH  /v1/projects/{projectId}
POST   /v1/projects/{projectId}/personas
PATCH  /v1/projects/{projectId}/personas/{personaId}
POST   /v1/projects/{projectId}/assets/upload-url
POST   /v1/projects/{projectId}/assets/{assetId}/complete
POST   /v1/projects/{projectId}/runs
GET    /v1/projects/{projectId}/runs/{runId}
GET    /v1/projects/{projectId}/runs/{runId}/findings
PATCH  /v1/projects/{projectId}/runs/{runId}/findings/{findingId}
GET    /v1/projects/{projectId}/runs/{runId}/heatmap
GET    /v1/projects/{projectId}/runs/{runId}/derivatives
POST   /v1/projects/{projectId}/runs/{runId}/export
GET    /v1/projects/{projectId}/runs/{runId}/download/{artifactType}
```

`PATCH finding` accepts only:

```json
{ "status": "KEPT" }
```

or `DISMISSED`/`UNDONE`. It writes the state transition, emits an analytics event, and never mutates the model-generated evidence.

## 10. AI pipeline design

### 10.1 Transcript stage

1. Confirm the asset belongs to the project owner.
2. Send the Cloud Storage URI to Speech-to-Text V2 BatchRecognize.
3. Use `chirp_3`, automatic language detection, automatic punctuation, speaker diarization where supported, and word-level timestamps only when needed for the chosen language.
4. Normalize the response into `segments/{segmentId}`.
5. Store the full raw response in Cloud Storage and the normalized segments in Firestore.

For the demo, use an English or Hindi-English video so timestamps and language behavior are predictable.

### 10.2 Concept and claim extraction

Pass the transcript segments to Gemini with a strict JSON schema. Require every concept and claim to include one or more `segmentIds`. Reject and retry responses that contain unknown segment IDs.

Output:

```text
concepts[]: label, plainLanguageSummary, importance, segmentIds, prerequisiteConceptIds
claims[]: text, segmentIds, risk, claimType
structure: hook, sections[], conclusion, missingElements[]
```

### 10.3 Reviewer stage

Run one structured Gemini call containing seven reviewers. This is cheaper and keeps scores consistent, but the prompt defines each reviewer separately.

| Dimension | Main question |
|---|---|
| Truth/evidence | Are claims supported, qualified, and sourced? |
| Clarity | Can the target audience understand the message without guessing? |
| Structure | Is there a hook, progression, transitions, and conclusion? |
| Audience fit | Does language, depth, and context match the selected personas? |
| Engagement | Is there a reason to continue, respond, save, or share? |
| Visual/accessibility | Are captions, pacing, visual hierarchy, and accessibility addressed? |
| Safety/legal | Are there privacy, copyright, harmful, defamation, or regulated-claim risks? |

Every finding must contain:

- Score from 1 to 10.
- Confidence from 0 to 1.
- Severity: low, medium, or high.
- Exact evidence quote.
- Segment IDs and timestamps.
- One specific repair suggestion.
- A `needsHumanReview` boolean for legal/safety or low-confidence findings.

The reviewer is instructed to return `NOT_ENOUGH_EVIDENCE` instead of inventing a problem.

### 10.4 Claim verification

Only verify claims with `risk != LOW` or claims selected by the user. Use Gemini with Google Search grounding. Store the returned source title, URL, and short evidence snippet. The final verdict is one of `SUPPORTED`, `CONTRADICTED`, `UNCERTAIN`, or `NOT_CHECKED`.

The UI shows “uncertain” prominently and includes the source list. This is an evidence map, not a misleading true/false detector.

### 10.5 Synthetic audience diagnostic

For each active persona, Gemini produces three multiple-choice questions tied to the most important concepts. It then simulates that persona answering based only on the persona profile and the source content.

The prompt must force the model to explain:

- What the persona probably understood.
- Which concept caused confusion.
- Whether the confusion came from vocabulary, missing context, pacing, or unsupported assumptions.
- A confidence score.

The UI labels this panel **Synthetic audience simulation** and includes “Validate with real viewers before making product or editorial claims.”

### 10.6 Heatmap calculation

For each persona/concept cell:

```text
understandingScore = 100 × (0.70 × answerCorrectness
                           + 0.20 × explanationQuality
                           + 0.10 × modelConfidence)
```

Aggregate scores to green/amber/red:

```text
green:  >= 75
amber:  50–74
red:    < 50
```

The heatmap is an editorial diagnostic, not a scientific measurement. The UI includes the score, confidence, and reason on hover/click.

### 10.7 Derivative generation

Generate one compact derivative pack from:

- Source summary.
- Top three accepted findings.
- Target platform list.
- Persona profiles.
- Verified/uncertain claims.

The prompt must preserve factual claims and mark uncertain claims as “verify before publishing.” It must not introduce statistics or names absent from the source/evidence context.

The thumbnail prompt is generated from the chosen hook and audience, then sent to Imagen 4 Fast. Store the image in Cloud Storage and the prompt alongside the derivative record for traceability.

## 11. Prompt and output safety rules

- All extraction/reviewer calls use JSON schema and low temperature.
- The model may cite only transcript segments provided in the request for content evidence.
- External claims require a stored source URL or are marked `UNCERTAIN`.
- The model cannot change Firestore status fields; only the worker/API writes them.
- Prompt injection inside a transcript is treated as source content, never as an instruction.
- Do not send Firebase tokens, email addresses, or private metadata to Gemini.
- Strip or redact obvious personal data before analytics logging.
- Legal/safety findings are recommendations for human review, not legal advice.
- Every generated derivative carries `generatedByModel`, `modelVersion`, and `sourceRunId` metadata.

## 12. Frontend screens

### A. Project home

Project cards show source title, latest run status, top score, and last updated time. A prominent “Analyze new video” button starts the upload flow.

### B. Onboarding/personas

Three persona cards with editable fields and a short explanation of why persona context affects the analysis.

### C. Upload and processing

Drag-and-drop upload, progress bar, file constraints, and stage progress. The page remains usable while processing and polls the run document every 2 seconds with exponential backoff after 30 seconds.

### D. Review dashboard

Top row: overall score, claims checked, high-severity findings, median simulated comprehension.

Main area: video player, transcript with clickable timestamps, and finding cards. Selecting a finding seeks the video to its evidence timestamp.

### E. Understanding heatmap

Rows are personas; columns are concepts. Cell color follows the threshold above. Selecting a red cell opens the diagnostic question, simulated response, confidence, and suggested edit.

### F. Repurpose studio

Tabs for short-form script, caption/hashtags, poll, LinkedIn, X, and thumbnail. Each output shows source claims and accepted finding IDs. A single export action downloads the content pack.

## 13. Security and data handling

- Firebase Auth is the user identity provider.
- API verifies Firebase ID tokens using Firebase Admin SDK.
- Firestore rules deny all direct writes from clients except allowed profile/persona fields; AI results are server-owned.
- Cloud Storage is private; all browser access uses signed URLs.
- Cloud Run service accounts use least-privilege IAM and no JSON keys.
- Cloud Run API rejects project IDs that do not belong to the authenticated user.
- Raw source video is retained for the project; temporary derivatives are lifecycle-deleted.
- Add a visible “Delete project” action after the demo; deletion removes Firestore documents and moves Storage objects to a `deleted/` prefix before final deletion.
- Configure a billing budget alert at $10 and $50, plus a dashboard for Cloud Run requests, Gemini calls, Speech-to-Text minutes, Storage bytes, and Pub/Sub dead letters.

## 14. Reliability and observability

Every run has a `runId` and every worker log includes it. Log these fields:

```text
runId, projectId, assetId, stage, model, latencyMs, inputBytes, outputBytes, status, errorCode
```

Required behaviors:

- Stage writes are idempotent.
- A duplicate Pub/Sub delivery does not create duplicate findings.
- A failed stage can be retried from the failed stage without retranscribing if the transcript exists.
- Dead-letter messages appear in an admin-only error view and Cloud Logging.
- The API returns a stable `run.status` and `run.stage` rather than exposing provider errors.

## 15. Build sequence and acceptance criteria

### Milestone 1 — Foundation

Build Firebase Auth, project CRUD, persona CRUD, Firestore rules, Cloud Storage bucket, and direct signed uploads.

**Acceptance:** a signed-in user can create a project, define three personas, upload an MP4, and see the asset record.

### Milestone 2 — Async analysis

Build Pub/Sub, API/worker containers, Cloud Run deployment, Speech-to-Text transcription, and run progress updates.

**Acceptance:** an uploaded video reaches `TRANSCRIBED` without the browser waiting on the request; a duplicate job is harmless.

### Milestone 3 — Reviewer and evidence model

Build concept extraction, seven reviewers, claim verification, Firestore findings, and transcript-linked dashboard.

**Acceptance:** every finding shows a score, reason, timestamp, and evidence quote; every factual finding is supported, contradicted, or uncertain with a source list.

### Milestone 4 — Comprehension debugger

Build diagnostic questions, persona simulations, heatmap calculation, and visualization.

**Acceptance:** the same source produces different score cells for at least three personas, and selecting a cell explains the divergence.

### Milestone 5 — Repurposing and export

Build derivative pack, Imagen thumbnail, keep/undo/dismiss actions, Markdown/JSON export, and event logging.

**Acceptance:** the creator can keep two findings, regenerate a derivative pack using those edits, and download a complete content pack.

### Milestone 6 — Demo hardening

Add loading/error states, safety labels, budget alerts, Cloud Logging screenshots, seeded demo data, and Firebase Hosting deployment.

**Acceptance:** the complete demo can be run in under three minutes from upload/result replay, with no manual database edits.

## 16. Three-minute demo script

1. **0:00–0:20 — Problem:** “Creators can see likes, but not where different audiences stop understanding.” Show the same concept being clear for one persona and vague for another.
2. **0:20–0:45 — Setup:** Create a project with beginner, intermediate, and Hindi-speaking personas; upload one short source video.
3. **0:45–1:20 — AI pipeline:** Show live progress: transcript, concepts, claim evidence, and reviewers. Open a red clarity finding and jump to its timestamp.
4. **1:20–1:55 — Heatmap:** Show the persona-by-concept heatmap. Select a red cell and reveal the diagnostic question, confusion reason, and repair suggestion.
5. **1:55–2:25 — Editorial action:** Keep the top two findings, regenerate the short-form script and caption, and show the evidence/accepted-finding links.
6. **2:25–2:45 — Output:** Show the thumbnail, poll, LinkedIn post, and X post; export the Markdown pack.
7. **2:45–3:00 — Architecture and impact:** Show Firebase, Cloud Run, Pub/Sub, Speech-to-Text, Gemini, Cloud Storage, Firestore, and BigQuery. Close with measurable MVP outcomes: time-to-analysis, evidence coverage, actionable findings, and comprehension spread.

## 17. Success metrics

Track these in the demo and documentation:

- `time_to_ready_seconds`: upload completion to analysis-ready.
- `evidence_coverage`: claims with a source or transcript segment / total claims.
- `actionable_finding_rate`: findings kept by the creator / findings generated.
- `comprehension_spread`: max persona score minus min persona score for a concept.
- `derivative_generation_success_rate`.
- `analysis_failure_rate` and dead-letter count.

The product claim is: **ClarityLoop helps a creator find and repair audience comprehension gaps before publishing, then repurpose the repaired message into platform-ready outputs.** It does not claim to predict real-world engagement or replace human fact-checking.

## 18. Repository layout and deployment configuration

Keep the first implementation in one repository with independently deployable API and worker entry points:

```text
apps/web/                 React + Vite dashboard
services/api/             FastAPI HTTP service
services/worker/          Pub/Sub push handler and AI pipeline
packages/contracts/       Shared JSON schemas and enums
infra/                    Firestore rules, indexes, firebase.json, cloudbuild.yaml
docs/                     Product and technical documentation
```

The API and worker may share Python modules, but they must have separate container commands so the worker cannot accidentally expose public API routes.

### Runtime environment variables

```text
GOOGLE_CLOUD_PROJECT
GCP_REGION=asia-southeast1
MEDIA_BUCKET=${PROJECT_ID}-media
FIRESTORE_DATABASE=(default)
BIGQUERY_DATASET=clarityloop_analytics
PUBSUB_TOPIC=analysis-jobs
GEMINI_LOCATION=global
GEMINI_REVIEW_MODEL=gemini-3.5-flash
GEMINI_FAST_MODEL=gemini-3.5-flash-lite
SPEECH_LOCATION=asia-southeast1
SPEECH_MODEL=chirp_3
THUMBNAIL_MODEL=imagen-4-fast
FIREBASE_PROJECT_ID
```

No API keys belong in the frontend bundle. The web app receives only the Firebase configuration intended for browser initialization; Cloud Run uses its attached service account for Google APIs.

### Firebase Hosting configuration

Use a static Vite build and route `/api/**` to the API service. The production `firebase.json` should be equivalent to:

```json
{
  "hosting": {
    "public": "apps/web/dist",
    "ignore": ["firebase.json", "**/.*", "**/node_modules/**"],
    "cleanUrls": true,
    "rewrites": [
      { "source": "/api/**", "run": { "serviceId": "clarityloop-api", "region": "asia-southeast1" } },
      { "source": "**", "destination": "/index.html" }
    ],
    "headers": [
      {
        "source": "**/*.@(js|css|png|jpg|jpeg|svg|woff2)",
        "headers": [{ "key": "Cache-Control", "value": "public,max-age=31536000,immutable" }]
      }
    ]
  }
}
```

### Container build and deploy

Use Artifact Registry repository `clarityloop` in `asia-southeast1`. Build two immutable images from the same commit:

```text
asia-southeast1-docker.pkg.dev/${PROJECT_ID}/clarityloop/api:${COMMIT_SHA}
asia-southeast1-docker.pkg.dev/${PROJECT_ID}/clarityloop/worker:${COMMIT_SHA}
```

Deploy the API with the API service account and the worker with the worker service account. The worker deployment must configure the Pub/Sub push endpoint and grant only the push identity `roles/run.invoker`. Deploy revisions by image digest in CI, not mutable `latest` tags.

The Cloud Build pipeline has four stages:

1. Run frontend typecheck/build and Python unit tests.
2. Build and push the API and worker images.
3. Deploy both Cloud Run services with the fixed region, resource limits, and environment variables.
4. Deploy `apps/web/dist` to Firebase Hosting and run `/healthz` plus a signed-in smoke test.

For local development, use the Firebase Emulator Suite for Auth/Firestore, a local Pub/Sub emulator only if needed, and a development Cloud Storage prefix. The first end-to-end test should use the real GCP services in a non-production project because Speech-to-Text, Gemini, and signed URL behavior are the riskier integration points.

## 19. Source documentation

- [Media, Content & Digital Experiences problem statement](themes/04-media-content.md)
- [Finalised idea notes](finalised-idea.md)
- [Cloud Run documentation](https://docs.cloud.google.com/run/docs)
- [Cloud Storage signed URLs](https://docs.cloud.google.com/storage/docs/access-control/signed-urls)
- [Firestore data model](https://firebase.google.com/docs/firestore/data-model)
- [Pub/Sub overview](https://docs.cloud.google.com/pubsub/docs/pubsub-basics)
- [Speech-to-Text V2 Chirp 3](https://docs.cloud.google.com/speech-to-text/v2/docs/chirp-model)
- [Gemini video understanding sample](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/samples/googlegenaisdk-textgen-with-video)
