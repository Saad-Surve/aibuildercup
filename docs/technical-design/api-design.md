# Creator Helper Studio — API Design

Status: proposed MVP contract

## Implementation status

Implemented today (see `contracts/openapi.yaml`): health, `/me`, onboarding/persona, projects,
upload-session/complete/assets, `download-url`, jobs (get, cancel), the realtime WebSocket,
transcript (get, get segment), and the internal Pub/Sub push endpoint.

Planned, not yet implemented (kept here and in the contract as `x-status: planned`): analysis
(findings, heatmap), artifacts, chat, localization/glossaries, transcript regenerate, account
export, demo/admin seeding. Do not assume these routes exist in the backend.

## 1. API conventions

Base URL:

~~~text
https://api.<domain>/v1
~~~

Authentication:

~~~http
Authorization: Bearer <Firebase ID token>
~~~

All long-running work returns 202 Accepted and a job reference. The client subscribes to a single project WebSocket for progress; polling endpoints remain as the fetch layer (and a degraded fallback when the socket is unavailable).

### Error envelope

~~~json
{
  "error": {
    "code": "PROJECT_NOT_FOUND",
    "message": "The requested project does not exist.",
    "requestId": "req_123",
    "details": {}
  }
}
~~~

### Pagination

~~~text
GET /resource?limit=20&pageToken=...
~~~

~~~json
{
  "items": [],
  "nextPageToken": null
}
~~~

### Idempotency

Mutating endpoints that create jobs accept:

~~~http
Idempotency-Key: <stable-client-generated-key>
~~~

The server stores the key and returns the original result for retries.

## 2. Health and current user

| Method | Route | Purpose |
|---|---|---|
| GET | /healthz | Unauthenticated liveness check |
| GET | /readyz | Dependency readiness check |
| GET | /me | Current application profile |

Example GET /me response:

~~~json
{
  "uid": "uid",
  "displayName": "Priya Sharma",
  "email": "creator@example.com",
  "onboardingCompleted": true,
  "personaVersion": 3,
  "preferences": {
    "timezone": "Asia/Kolkata",
    "defaultLanguage": "en"
  }
}
~~~

## 3. Onboarding and persona

| Method | Route | Purpose |
|---|---|---|
| GET | /onboarding | Read onboarding progress |
| PUT | /onboarding | Save a partial onboarding step |
| POST | /onboarding/complete | Generate and save initial persona |
| GET | /persona | Read current persona |
| PATCH | /persona | Apply user-approved persona edit |
| GET | /persona/revisions | List persona revisions |
| POST | /persona/suggestions/{suggestionId}/approve | Apply an AI proposal |

PUT /onboarding request:

~~~json
{
  "step": "creator_profile",
  "answers": {
    "creatorName": "Priya",
    "topics": ["finance", "career"],
    "primaryLanguage": "hi",
    "audience": "Indian students and early-career professionals"
  }
}
~~~

POST /onboarding/complete response:

~~~json
{
  "onboardingCompleted": true,
  "personaVersion": 1,
  "personaStoragePath": "users/uid/profile/persona.md"
}
~~~

PATCH /persona request:

~~~json
{
  "content": "# Creator Persona\n...",
  "expectedVersion": 3
}
~~~

Return 409 PERSONA_VERSION_CONFLICT if another update happened first.

## 4. Platform connections

| Method | Route | Purpose |
|---|---|---|
| GET | /connections | List connected platforms |
| POST | /connections/{platform}/oauth/start | Start OAuth |
| GET | /connections/{platform}/oauth/callback | Handle OAuth callback |
| POST | /connections/{connectionId}/sync | Start analytics/comment sync |
| DELETE | /connections/{connectionId} | Revoke and delete connection |

Initial platform values:

~~~text
youtube | instagram | facebook
~~~

POST /connections/{platform}/oauth/start response:

~~~json
{
  "authorizationUrl": "https://accounts.google.com/...",
  "state": "opaque-server-side-state"
}
~~~

The state value must be stored server-side and checked during callback handling.

POST /connections/{connectionId}/sync response:

~~~json
{
  "jobId": "job-id",
  "syncRunId": "sync-run-id",
  "status": "queued"
}
~~~

## 5. Projects

| Method | Route | Purpose |
|---|---|---|
| POST | /projects | Create project |
| GET | /projects | List owned projects |
| GET | /projects/{projectId} | Get project summary |
| PATCH | /projects/{projectId} | Update project metadata |
| DELETE | /projects/{projectId} | Delete the project and all of its data (Firestore subtree + Cloud Storage objects) |

POST /projects request:

~~~json
{
  "name": "Career Advice Video",
  "description": "Interview preparation video",
  "primaryLanguage": "en",
  "targetLanguages": ["hi"],
  "targetPlatforms": ["youtube_shorts", "instagram"]
}
~~~

## 6. Video upload and assets

| Method | Route | Purpose |
|---|---|---|
| POST | /projects/{projectId}/upload-session | Create direct Cloud Storage upload |
| POST | /projects/{projectId}/assets/{assetId}/complete | Confirm client upload |
| GET | /projects/{projectId}/assets | List assets |
| GET | /projects/{projectId}/revisions | List source-video revisions |
| POST | /projects/{projectId}/revisions/{assetId}/activate | Make a revision the active video |
| GET | /projects/{projectId}/assets/{assetId}/download-url | Create short-lived download URL |

POST /upload-session request:

~~~json
{
  "fileName": "career-advice.mp4",
  "contentType": "video/mp4",
  "sizeBytes": 184000000
}
~~~

Response:

~~~json
{
  "assetId": "asset-id",
  "storagePath": "users/uid/projects/project-id/source/asset-id.mp4",
  "uploadUrl": "https://storage.googleapis.com/...",
  "expiresAt": "timestamp",
  "requiredHeaders": {
    "Content-Type": "video/mp4"
  }
}
~~~

The backend validates MIME type and size before issuing the URL. The browser uploads directly to Cloud Storage. The server still verifies that the object exists after upload.

Trigger of record:

- `POST /assets/{assetId}/complete` is authoritative for the user-visible upload state.
- The Cloud Storage `object finalized` notification is what actually starts the transcription worker, so processing still happens if the client never confirms.
- Both paths are idempotent and converge on the same asset/job records.

### Revisions

A project holds one video but keeps every revision of it. Each `POST /upload-session`
mints the next revision number on the new `source_video` asset, and completing the upload
makes it the project's active source (`sourceAssetId` / `sourceRevision` on the project)
and transcribes it automatically. Revisions are never overwritten, so transcripts and
analysis runs remain attributable to the cut they were built from. Once the new transcript
is ready the client can `POST /projects/{projectId}/analysis` to review the new revision;
the UI nudges this when the newest run's `transcriptId` differs from the active transcript.

`GET /projects/{projectId}/revisions` returns them newest first, with `isActive` on the
current one. Each revision also carries the newest transcript built from it
(`transcriptId` / `transcriptVersion`) and its `analysisRunCount`, so the history shows
what work already exists per cut. Source assets uploaded before revisions existed carry no
`revision`; they are numbered by upload order.

`POST /projects/{projectId}/revisions/{assetId}/activate` points the project back at an
earlier revision. If that revision already has a transcript, the newest one becomes active
and the project is `ready`; otherwise a fresh transcribe job is queued and its `jobId` is
returned. Existing transcripts and analysis runs are never deleted, so switching between
revisions is lossless. All revisions live under the project prefix, so project deletion
still removes them with no extra wiring.

### Drafts

A project created with `kind: "draft"` opens the versioned writing studio instead of the
video pipeline. `CreateProject.draftBrief` carries the seed brief captured in the creation
dialog. All draft routes operate on the project's single `draft/main` document.

| Method | Route | Purpose |
|---|---|---|
| GET | /projects/{projectId}/draft | Get the versioned draft (brief, blocks, versions, chat) |
| PUT | /projects/{projectId}/draft | Save client-side title/block edits |
| POST | /projects/{projectId}/draft/generate | Generate the first draft from the brief |
| POST | /projects/{projectId}/draft/assist | Chat; proposals become new block versions |

`GET /projects/{projectId}/draft` returns the single draft document for the project:

~~~json
{
  "projectId": "project-id",
  "title": "Why side projects stall",
  "status": "ready",
  "brief": { "topic": "...", "format": "written", "audience": "...", "tone": "...",
             "platform": "...", "language": "en", "instructions": "", "targetWords": 0 },
  "blocks": [
    { "blockId": "b1", "type": "paragraph",
      "versions": [ { "versionId": "v1", "text": "...", "label": "Draft",
                      "origin": "assistant", "createdAt": "timestamp" } ],
      "activeVersionId": "v1" }
  ],
  "messages": [ { "messageId": "m1", "role": "user", "content": "...",
                  "createdAt": "timestamp" } ],
  "error": null,
  "summary": { "title": "...", "preview": "...", "wordCount": 612,
               "blockCount": 8, "versionCount": 14 },
  "createdAt": "timestamp", "updatedAt": "timestamp"
}
~~~

`POST .../generate` calls the writing model with the stored brief (optionally overridden in
the body) and replaces the blocks with a fresh first draft, one version each. If the model
is unavailable a deterministic template keeps the demo working. `POST .../assist` appends
the user's message, asks the model for a reply plus block edits, and applies each edit as a
new `versions[]` entry on its block (or a new block). The full draft is returned, and the
project document's `draftSummary` is refreshed so list cards stay current. `PUT` rejects
unknown `blockId`s so an edit can never silently drop content. Draft data lives under
`users/{uid}/projects/{projectId}/draft/main`, so project deletion removes it automatically.

## 7. Jobs and progress

| Method | Route | Purpose |
|---|---|---|
| GET | /jobs/{jobId} | Get job status |
| POST | /jobs/{jobId}/cancel | Cancel queued/running job |
| WS | /api/ws | Realtime project progress (WebSocket) |

GET /jobs/{jobId} response:

~~~json
{
  "jobId": "job-id",
  "type": "analyze",
  "status": "running",
  "progress": {
    "percent": 72,
    "step": "structure_reviewer",
    "message": "Running structure reviewer"
  },
  "error": null,
  "createdAt": "timestamp",
  "updatedAt": "timestamp"
}
~~~

Realtime (WebSocket). The former SSE stream (`GET /projects/{id}/events`) was
replaced: it was a server-side Firestore poll, and the client still had to poll
alongside it. One socket now carries project, job, transcript, and analysis
events.

~~~text
GET {WS_BASE}/api/ws?token=<firebaseIdToken>

client -> {"type":"subscribe.project","projectId":"project-id"}
server -> {"type":"snapshot.project","status":"processing", ...}   # immediate
server -> {"type":"project.progress","status":"ready", ...}
server -> {"type":"job.progress","jobId":"...","progress":{"percent":72}}
server -> {"type":"transcript.ready","transcriptId":"...","durationMs":123000}
server -> {"type":"analysis.progress","analysisRunId":"...","reviewerStatuses":[...]}
server -> {"type":"analysis.ready","analysisRunId":"...","findingCounts":{...}}
~~~

Details:

- Browsers cannot set an `Authorization` header on the upgrade, so the Firebase
  ID token travels as `?token=`; the server verifies it exactly like HTTP bearer
  auth and closes with code 4401 on failure (accepting first, so no spurious
  ASGI handshake error is logged).
- Events are emitted from the job/project/analysis write paths via an in-process
  hub (`backend/app/realtime/`), so they fire when the backing documents are
  written, not on a timer. Publish is a no-op when nobody is subscribed.
- In production the socket targets the **Cloud Run service URL** directly
  (`NEXT_PUBLIC_WS_BASE_URL`): Firebase Hosting rewrites do not proxy WebSocket
  upgrades. The HTTP API still goes through the `/api/**` rewrite.
- Cloud Run bounds request duration; the client reconnects with backoff and a
  fresh token. On reconnect it re-invalidates the resource queries, and the
  subscriber-time snapshot re-primes the progress UI.
- Frame schemas: `WsClientMessage` / `WsServerMessage` in `contracts/openapi.yaml`;
  protocol rules in `contracts/events.md`.

## 8. Transcripts

| Method | Route | Purpose |
|---|---|---|
| GET | /projects/{projectId}/transcript | Get transcript metadata and segments |
| GET | /projects/{projectId}/transcript/segments/{segmentId} | Get one segment |
| POST | /projects/{projectId}/transcript/regenerate | Create a new transcript version (planned) |

Transcript regeneration options:

~~~json
{
  "language": "en-IN",
  "enableSpeakerDiarization": true,
  "generateCaptions": true
}
~~~

## 9. Analysis and heatmap

| Method | Route | Purpose |
|---|---|---|
| GET | /projects/{projectId}/analysis | List analysis runs, newest first |
| POST | /projects/{projectId}/analysis | Start multi-reviewer analysis |
| GET | /projects/{projectId}/analysis/{analysisRunId} | Get analysis summary |
| GET | /projects/{projectId}/analysis/{analysisRunId}/reviewers | Per-reviewer status and cost |
| GET | /projects/{projectId}/analysis/{analysisRunId}/findings | List findings |
| GET | /projects/{projectId}/analysis/{analysisRunId}/heatmap | Get UI-ready heatmap bins |

POST /analysis request:

~~~json
{
  "dimensions": [
    "truth_evidence",
    "clarity",
    "pacing_retention",
    "legal_safety",
    "cultural_localization",
    "platform_fit",
    "audience_brand",
    "emotional_impact",
    "conversion_cta"
  ],
  "platform": "youtube",
  "includeVisualReview": true,
  "transcriptVersion": 1
}
~~~

The first six dimensions are core and always run. The rest are extended and configurable.

`includeVisualReview` is reserved: reviewers pull frames or clips themselves through the FFmpeg
footage tools during the run, so there is no separate deep-review request.

GET reviewers response:

~~~json
{
  "items": [
    {
      "reviewerRunId": "id",
      "dimension": "clarity",
      "status": "succeeded",
      "findingCount": 4,
      "costEstimateUsd": 0.03,
      "durationMs": 8200
    }
  ]
}
~~~

Response:

~~~json
{
  "analysisRunId": "analysis-id",
  "jobId": "job-id",
  "status": "queued"
}
~~~

Findings query parameters:

~~~text
dimension=clarity
severity=high
startMs=0
endMs=60000
~~~

## 10. Generated artifacts

| Method | Route | Purpose |
|---|---|---|
| POST | /projects/{projectId}/artifacts | Start generation |
| GET | /projects/{projectId}/artifacts | List artifacts |
| GET | /projects/{projectId}/artifacts/{artifactId} | Get artifact metadata |
| GET | /projects/{projectId}/artifacts/{artifactId}/download-url | Download artifact |
| POST | /projects/{projectId}/artifacts/{artifactId}/regenerate | Generate new version |
| DELETE | /projects/{projectId}/artifacts/{artifactId} | Soft-delete artifact |

Supported artifact types:

~~~text
short_clip
caption
thumbnail
social_post
blog
localized_video
dubbed_video
veo_intro
veo_outro
export
~~~

POST /artifacts request:

~~~json
{
  "type": "short_clip",
  "platform": "youtube_shorts",
  "language": "en",
  "options": {
    "candidateId": "candidate-id",
    "burnCaptions": true,
    "aspectRatio": "9:16"
  }
}
~~~

Response: 202 Accepted with artifactId and jobId.

## 11. Shorts and localization

| Method | Route | Purpose |
|---|---|---|
| GET | /projects/{projectId}/clip-candidates | List short-form candidates |
| POST | /projects/{projectId}/clip-candidates/generate | Generate candidates |
| POST | /projects/{projectId}/clip-candidates/{candidateId}/render | Render selected clip |
| POST | /projects/{projectId}/localizations | Start localization |
| GET | /projects/{projectId}/localizations | List localizations |
| GET | /projects/{projectId}/localizations/{localizationId} | Get localization status |

POST /localizations request:

~~~json
{
  "targetLanguage": "hi",
  "generateCaptions": true,
  "generateDubbedAudio": true,
  "voice": "hi-IN-standard-A",
  "corpusVersion": 1,
  "glossaryVersion": 2
}
~~~

## 12. Glossaries and corpus

| Method | Route | Purpose |
|---|---|---|
| GET | /glossaries | List available global glossaries and versions |
| GET | /projects/{projectId}/glossary | Read the project glossary |
| PUT | /projects/{projectId}/glossary | Replace the project glossary terms |
| POST | /projects/{projectId}/localizations/{localizationId}/flag | Flag a wrong localized phrase |

PUT /projects/{projectId}/glossary request:

~~~json
{
  "sourceLanguage": "en",
  "targetLanguage": "hi",
  "terms": [
    { "source": "credit score", "target": "क्रेडिट स्कोर" }
  ],
  "expectedVersion": 2
}
~~~

A flagged phrase becomes a candidate corpus entry for review. See
[localization-corpus.md](./localization-corpus.md).

## 13. Demo and development endpoints

Not implemented: the cassette/`MOCK_MODE` layer and its seeding endpoints were removed. Development
runs against the real free-tier services with `fixtures/media/`.

## 14. Project chat

| Method | Route | Purpose |
|---|---|---|
| POST | /projects/{projectId}/chat/threads | Create chat thread |
| GET | /projects/{projectId}/chat/threads | List threads |
| GET | /projects/{projectId}/chat/threads/{threadId}/messages | List messages |
| POST | /projects/{projectId}/chat/threads/{threadId}/messages | Send message |

POST message request:

~~~json
{
  "content": "Give me three better hooks for the first 20 seconds.",
  "attachments": [],
  "stream": true
}
~~~

Project tools available to the agent:

~~~text
get_transcript_segment
get_analysis_findings
get_audience_summary
generate_social_post
create_clip_candidate
update_persona_suggestion
generate_thumbnail
~~~

## 15. Feedback, export, and deletion

| Method | Route | Purpose |
|---|---|---|
| POST | /projects/{projectId}/feedback | Record feedback |
| POST | /account/export | Export user-owned data |
| DELETE | /account | Delete account and owned data |

Feedback request:

~~~json
{
  "targetType": "finding",
  "targetId": "finding-id",
  "rating": "helpful",
  "comment": "This suggestion was useful."
}
~~~

## 16. Internal Pub/Sub events

These are internal event types, not public HTTP endpoints:

~~~text
video.uploaded
transcription.requested
transcript.ready
analysis.requested
reviewer.completed
analysis.ready
social.sync.requested
social.sync.completed
artifact.requested
artifact.ready
localization.requested
localization.ready
job.failed
~~~

Event envelope:

~~~json
{
  "eventId": "evt-id",
  "type": "transcript.ready",
  "ownerUid": "uid",
  "projectId": "project-id",
  "jobId": "job-id",
  "payload": {},
  "occurredAt": "timestamp",
  "schemaVersion": 1
}
~~~

**Implemented today:** `transcript.ready` is published to `transcription-events` after a
transcript is stored, and the GCS `object finalized` notification on the media bucket publishes to
`video-events`, delivered by a push subscription to the internal endpoint:

~~~text
POST /api/internal/pubsub/video-events     # Pub/Sub push; authenticated with an OIDC token
~~~

The other event types are declared here but not yet published. Topic routing lives in
`backend/app/events.py` and mirrors `infra/pubsub.tf`.

## 17. API security requirements

- Verify Firebase ID tokens at the API boundary.
- Derive ownerUid from the token.
- Check ownership on every project-scoped route.
- Use OAuth state and PKCE.
- Never return access or refresh tokens to the browser.
- Never return permanent storage credentials.
- Use short-lived signed download URLs.
- Rate-limit generation and chat endpoints.
- Validate all AI output with Pydantic before persistence.
- Treat transcript and social text as untrusted input.

