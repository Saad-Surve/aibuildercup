# Creator Helper Studio — API Design

Status: proposed MVP contract

## 1. API conventions

Base URL:

~~~text
https://api.<domain>/v1
~~~

Authentication:

~~~http
Authorization: Bearer <Firebase ID token>
~~~

All long-running work returns 202 Accepted and a job reference. The client polls the job endpoint or subscribes to project events with Server-Sent Events.

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
| DELETE | /projects/{projectId} | Soft-delete project and queue object deletion |

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

## 7. Jobs and progress

| Method | Route | Purpose |
|---|---|---|
| GET | /jobs/{jobId} | Get job status |
| POST | /jobs/{jobId}/cancel | Cancel queued/running job |
| GET | /projects/{projectId}/events | SSE progress stream |

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

SSE example:

~~~text
event: job.progress
data: {"jobId":"job-id","percent":72}
~~~

## 8. Transcripts

| Method | Route | Purpose |
|---|---|---|
| GET | /projects/{projectId}/transcript | Get transcript metadata and segments |
| GET | /projects/{projectId}/transcript/segments/{segmentId} | Get one segment |
| POST | /projects/{projectId}/transcript/regenerate | Create a new transcript version |

Transcript regeneration options:

~~~json
{
  "language": "en-IN",
  "enableSpeakerDiarization": false,
  "generateCaptions": true
}
~~~

## 9. Analysis and heatmap

| Method | Route | Purpose |
|---|---|---|
| POST | /projects/{projectId}/analysis | Start multi-reviewer analysis |
| GET | /projects/{projectId}/analysis/{analysisRunId} | Get analysis summary |
| GET | /projects/{projectId}/analysis/{analysisRunId}/reviewers | Per-reviewer status and cost |
| GET | /projects/{projectId}/analysis/{analysisRunId}/findings | List findings |
| GET | /projects/{projectId}/analysis/{analysisRunId}/heatmap | Get UI-ready heatmap bins |
| POST | /projects/{projectId}/analysis/{analysisRunId}/segment-review | Deep-review selected video segment |

POST /analysis request:

~~~json
{
  "dimensions": [
    "truth_evidence",
    "clarity",
    "structure_pacing",
    "legal_safety",
    "cultural_localization",
    "platform_fit",
    "audience_fit",
    "brand_voice",
    "engagement_retention",
    "emotional_impact",
    "seo_discoverability",
    "visual_accessibility",
    "conversion_cta"
  ],
  "platform": "youtube",
  "includeVisualReview": true,
  "transcriptVersion": 1
}
~~~

The first six dimensions are core and always run. The rest are extended and configurable.

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

Deep-review request:

~~~json
{
  "startMs": 42000,
  "endMs": 58000,
  "dimensions": ["clarity", "visual_accessibility", "truth_evidence"]
}
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

These are available only when `MOCK_MODE` is not `off`, and are never exposed in the live demo
configuration.

| Method | Route | Purpose |
|---|---|---|
| GET | /demo/scenarios | List pinned demo scenarios |
| POST | /admin/seed | Seed a demo world (dev only) |
| GET | /admin/cassettes | List recorded cassettes (dev only) |

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

