# Creator Helper Studio — Firestore Database Design

Status: proposed MVP schema

Firestore is the application control plane. Store large media and analytics elsewhere:

- Cloud Storage: videos, audio, transcripts, captions, thumbnails, clips, exports, and persona files.
- BigQuery: platform analytics, comments, sentiment results, and audience aggregates.
- Firestore: user/project metadata, workflow state, UI-ready records, and references to external artifacts.

## 1. Conventions

| Field | Convention |
|---|---|
| Document IDs | Random UUID or Firestore auto-ID; never sequential |
| User ID | Firebase Authentication UID |
| Timestamps | Firestore Timestamp in UTC |
| Storage paths | gs:// object paths, never signed URLs |
| Ownership | Every user-owned document includes ownerUid |
| Large content | Stored in Cloud Storage; Firestore stores metadata and references |

Common statuses:

~~~text
ProjectStatus    = draft | uploading | processing | ready | partial_failure | failed | archived
JobStatus        = queued | running | succeeded | failed | cancelled
ConnectionStatus = pending | connected | needs_reauth | revoked | error
AssetStatus      = pending | uploading | uploaded | processing | ready | failed | deleted
ArtifactStatus   = queued | generating | ready | failed | deleted
Severity         = none | low | medium | high | critical
~~~

All mutable documents should include ownerUid, createdAt, and updatedAt.

## 2. Complete Firestore hierarchy

~~~text
users/{uid}
├── connections/{connectionId}
│   └── syncRuns/{syncRunId}
├── personaRevisions/{revisionId}
├── notifications/{notificationId}
├── usagePeriods/{periodId}
├── projects/{projectId}
│   ├── assets/{assetId}
│   ├── jobs/{jobId}
│   │   └── events/{eventId}
│   ├── transcripts/{transcriptId}
│   │   └── segments/{segmentId}
│   ├── analysisRuns/{analysisRunId}
│   │   ├── reviewers/{reviewerRunId}
│   │   ├── findings/{findingId}
│   │   └── heatmapBins/{binId}
│   ├── clipCandidates/{candidateId}
│   ├── artifacts/{artifactId}
│   │   └── versions/{versionId}
│   ├── localizations/{localizationId}
│   ├── chatThreads/{threadId}
│   │   └── messages/{messageId}
│   ├── feedback/{feedbackId}
│   ├── exports/{exportId}
│   └── auditEvents/{auditEventId}

glossaries/{glossaryId}          platform-level, versioned terminology corpus
demoProfiles/{demoProfileId}     platform-level, stage demo scenarios
~~~

## 3. User documents

### users/{uid}

~~~json
{
  "displayName": "Priya Sharma",
  "email": "creator@example.com",
  "photoUrl": "https://...",
  "onboarding": {
    "status": "completed",
    "currentStep": "platforms",
    "completedAt": "timestamp",
    "schemaVersion": 1
  },
  "persona": {
    "storagePath": "users/uid/profile/persona.md",
    "version": 3,
    "language": "en-IN",
    "lastApprovedAt": "timestamp"
  },
  "preferences": {
    "timezone": "Asia/Kolkata",
    "defaultLanguage": "en",
    "defaultPlatforms": ["youtube", "instagram"],
    "notificationsEnabled": true
  },
  "limits": {
    "maxVideoDurationMs": 1800000,
    "maxVideoSizeBytes": 524288000
  },
  "createdAt": "timestamp",
  "updatedAt": "timestamp"
}
~~~

Do not store OAuth tokens in this document.

### users/{uid}/connections/{connectionId}

~~~json
{
  "ownerUid": "uid",
  "platform": "youtube",
  "accountType": "channel",
  "displayName": "Priya Creates",
  "externalAccountId": "UC...",
  "externalHandle": "@priyacreates",
  "status": "connected",
  "scopes": ["yt-analytics.readonly", "youtube.readonly"],
  "tokenSecretRef": "secret-reference",
  "tokenKeyVersion": "kms-key-version",
  "lastSyncAt": "timestamp",
  "nextSyncAt": "timestamp",
  "lastSyncStatus": "succeeded",
  "lastErrorCode": null,
  "createdAt": "timestamp",
  "updatedAt": "timestamp"
}
~~~

Only the backend can read this collection. Firestore client rules must deny direct access.

### users/{uid}/connections/{connectionId}/syncRuns/{syncRunId}

~~~json
{
  "ownerUid": "uid",
  "platform": "youtube",
  "status": "succeeded",
  "startedAt": "timestamp",
  "finishedAt": "timestamp",
  "dateRange": {
    "from": "2026-01-01",
    "to": "2026-09-19"
  },
  "counts": {
    "posts": 42,
    "metrics": 450,
    "comments": 1200,
    "sentiments": 1200
  },
  "rawStoragePrefix": "users/uid/social/youtube/syncRuns/run-id/",
  "error": null
}
~~~

### users/{uid}/personaRevisions/{revisionId}

~~~json
{
  "ownerUid": "uid",
  "version": 4,
  "storagePath": "users/uid/profile/revisions/persona-v4.md",
  "changeType": "approved_update",
  "changeSummary": "Added preference for concise Hindi hooks.",
  "source": "onboarding | user_edit | chat | inferred_preference",
  "approvalStatus": "pending_approval | approved | rejected",
  "approvedBy": "user",
  "createdAt": "timestamp"
}
~~~

AI-inferred changes remain pending until the user explicitly approves them.

## 4. Project documents

### users/{uid}/projects/{projectId}

~~~json
{
  "ownerUid": "uid",
  "name": "Career Advice Video",
  "description": "A video about interview preparation.",
  "status": "processing",
  "visibility": "private",
  "sourceAssetId": "asset-id",
  "activeTranscriptId": "transcript-id",
  "activeAnalysisRunId": "analysis-run-id",
  "personaVersionUsed": 3,
  "primaryLanguage": "en",
  "targetLanguages": ["hi", "mr"],
  "targetPlatforms": ["youtube", "instagram", "linkedin"],
  "progress": {
    "stage": "analysis",
    "percent": 72,
    "message": "Running structure reviewer"
  },
  "summary": {
    "durationMs": 485000,
    "transcriptWordCount": 1020,
    "overallScore": 7.4,
    "criticalFindingCount": 0,
    "highFindingCount": 2
  },
  "isDemo": false,
  "demoProfileId": null,
  "createdAt": "timestamp",
  "updatedAt": "timestamp",
  "archivedAt": null
}
~~~

### users/{uid}/projects/{projectId}/assets/{assetId}

~~~json
{
  "ownerUid": "uid",
  "projectId": "project-id",
  "type": "source_video | audio | frame | clip | thumbnail | caption | export",
  "status": "uploaded",
  "storagePath": "users/uid/projects/project-id/source/video.mp4",
  "mimeType": "video/mp4",
  "sizeBytes": 184000000,
  "checksum": "sha256:...",
  "durationMs": 485000,
  "width": 1920,
  "height": 1080,
  "frameRate": 30,
  "language": "en",
  "derivedFromAssetId": null,
  "createdAt": "timestamp",
  "updatedAt": "timestamp",
  "deletedAt": null
}
~~~

### users/{uid}/projects/{projectId}/jobs/{jobId}

~~~json
{
  "ownerUid": "uid",
  "projectId": "project-id",
  "type": "upload | transcribe | analyze | sync_social | sentiment | clip | thumbnail | localize | dub | text_content | veo | export",
  "status": "running",
  "idempotencyKey": "transcribe-project-id-asset-id-v1",
  "requestedBy": "user | system | chat",
  "input": {
    "assetId": "asset-id",
    "transcriptId": null,
    "analysisRunId": null,
    "language": "hi"
  },
  "output": {
    "artifactIds": [],
    "storagePaths": []
  },
  "progress": {
    "currentStep": "speech_to_text",
    "percent": 40,
    "message": "Generating word timestamps"
  },
  "attempt": 1,
  "maxAttempts": 3,
  "error": null,
  "startedAt": "timestamp",
  "finishedAt": null,
  "createdAt": "timestamp",
  "updatedAt": "timestamp"
}
~~~

### users/{uid}/projects/{projectId}/jobs/{jobId}/events/{eventId}

~~~json
{
  "type": "job.started | job.progress | job.retrying | job.succeeded | job.failed",
  "message": "Structure reviewer completed",
  "metadata": {
    "reviewer": "structure_pacing",
    "count": 14
  },
  "createdAt": "timestamp"
}
~~~

## 5. Transcript and analysis documents

### users/{uid}/projects/{projectId}/transcripts/{transcriptId}

~~~json
{
  "ownerUid": "uid",
  "projectId": "project-id",
  "sourceAssetId": "asset-id",
  "version": 1,
  "status": "ready",
  "language": "en-IN",
  "storagePath": "users/uid/projects/project-id/transcripts/v1.json",
  "vttStoragePath": "users/uid/projects/project-id/captions/en.vtt",
  "srtStoragePath": "users/uid/projects/project-id/captions/en.srt",
  "durationMs": 485000,
  "wordCount": 1020,
  "segmentCount": 85,
  "speakerCount": 1,
  "createdAt": "timestamp",
  "updatedAt": "timestamp"
}
~~~

### users/{uid}/projects/{projectId}/transcripts/{transcriptId}/segments/{segmentId}

~~~json
{
  "ownerUid": "uid",
  "index": 12,
  "startMs": 42000,
  "endMs": 58000,
  "text": "The second concept is...",
  "speaker": 2,
  "paragraphIndex": 4,
  "topic": "interview preparation",
  "wordCount": 28,
  "createdAt": "timestamp"
}
~~~

Keep word-level data in the canonical Cloud Storage JSON unless word-level editing is required.

### users/{uid}/projects/{projectId}/analysisRuns/{analysisRunId}

~~~json
{
  "ownerUid": "uid",
  "projectId": "project-id",
  "transcriptId": "transcript-id",
  "sourceAssetId": "asset-id",
  "personaVersion": 3,
  "status": "ready",
  "fanoutStrategy": "two_tier",
  "chunkCount": 4,
  "requestedDimensions": ["truth_evidence", "clarity", "structure_pacing", "legal_safety"],
  "completedDimensions": ["truth_evidence", "clarity", "structure_pacing", "legal_safety"],
  "overallScore": 7.4,
  "scoreByDimension": {
    "truth_evidence": 8.2,
    "clarity": 7.0,
    "structure_pacing": 6.4,
    "legal_safety": 9.1
  },
  "findingCounts": {
    "low": 10,
    "medium": 5,
    "high": 2,
    "critical": 0
  },
  "modelConfigVersion": "analysis-v1",
  "promptVersion": "reviewers-v1",
  "costEstimateUsd": 0.42,
  "createdAt": "timestamp",
  "updatedAt": "timestamp"
}
~~~

### users/{uid}/projects/{projectId}/analysisRuns/{analysisRunId}/reviewers/{reviewerRunId}

~~~json
{
  "ownerUid": "uid",
  "dimension": "clarity",
  "status": "succeeded",
  "model": "configured-gemini-model",
  "inputSegmentCount": 85,
  "findingCount": 4,
  "tokenUsage": {
    "input": 12000,
    "output": 1800
  },
  "error": null,
  "startedAt": "timestamp",
  "finishedAt": "timestamp"
}
~~~

### users/{uid}/projects/{projectId}/analysisRuns/{analysisRunId}/findings/{findingId}

~~~json
{
  "ownerUid": "uid",
  "dimension": "clarity",
  "reviewerRunId": "reviewer-run-id",
  "segmentId": "seg-12",
  "startMs": 42000,
  "endMs": 58000,
  "score": 7,
  "confidence": 0.86,
  "severity": "medium",
  "findingType": "ambiguity",
  "evidence": {
    "quote": "The second concept...",
    "explanation": "The concept is introduced without definition."
  },
  "suggestion": "Add a one-sentence definition before continuing.",
  "citations": [],
  "model": "configured-gemini-model",
  "createdAt": "timestamp"
}
~~~

### users/{uid}/projects/{projectId}/analysisRuns/{analysisRunId}/heatmapBins/{binId}

~~~json
{
  "ownerUid": "uid",
  "dimension": "clarity",
  "startMs": 40000,
  "endMs": 45000,
  "score": 7.5,
  "severity": "medium",
  "findingIds": ["finding-1", "finding-2"],
  "color": "yellow",
  "createdAt": "timestamp"
}
~~~

## 6. Candidate and artifact documents

### users/{uid}/projects/{projectId}/clipCandidates/{candidateId}

~~~json
{
  "ownerUid": "uid",
  "transcriptId": "transcript-id",
  "startMs": 92000,
  "endMs": 131000,
  "hook": "The surprising reason most people fail interviews",
  "reason": "Self-contained idea with a clear payoff",
  "platform": "youtube_shorts",
  "score": 8.5,
  "status": "suggested | selected | rendered | rejected",
  "artifactId": null,
  "createdAt": "timestamp",
  "updatedAt": "timestamp"
}
~~~

### users/{uid}/projects/{projectId}/artifacts/{artifactId}

~~~json
{
  "ownerUid": "uid",
  "projectId": "project-id",
  "type": "short_clip | thumbnail | social_post | blog | caption | localized_video | dubbed_video | veo_intro | veo_outro | export",
  "status": "ready",
  "platform": "youtube_shorts",
  "language": "en",
  "title": "The interview mistake most people make",
  "storagePath": "users/uid/projects/project-id/clips/artifact-id.mp4",
  "mimeType": "video/mp4",
  "sizeBytes": 24000000,
  "durationMs": 39000,
  "sourceTranscriptId": "transcript-id",
  "sourceAssetIds": ["asset-id"],
  "generationJobId": "job-id",
  "metadata": {
    "startMs": 92000,
    "endMs": 131000,
    "hook": "...",
    "reason": "Self-contained idea"
  },
  "createdAt": "timestamp",
  "updatedAt": "timestamp",
  "deletedAt": null
}
~~~

### users/{uid}/projects/{projectId}/artifacts/{artifactId}/versions/{versionId}

~~~json
{
  "version": 2,
  "storagePath": "users/uid/projects/project-id/clips/artifact-id/v2.mp4",
  "prompt": "Make the hook less clickbait-oriented.",
  "createdBy": "user | agent",
  "createdAt": "timestamp"
}
~~~

## 7. Localization, chat, and operational documents

### users/{uid}/projects/{projectId}/localizations/{localizationId}

~~~json
{
  "ownerUid": "uid",
  "sourceAssetId": "asset-id",
  "sourceTranscriptId": "transcript-id",
  "sourceLanguage": "en",
  "targetLanguage": "hi",
  "status": "requested | translating | synthesizing | muxing | ready | failed",
  "captionArtifactId": "artifact-id",
  "audioArtifactId": "artifact-id",
  "videoArtifactId": "artifact-id",
  "corpusVersion": 1,
  "glossaryVersion": 2,
  "voice": "hi-IN-standard-A",
  "createdAt": "timestamp",
  "updatedAt": "timestamp"
}
~~~

### users/{uid}/projects/{projectId}/chatThreads/{threadId}

~~~json
{
  "ownerUid": "uid",
  "projectId": "project-id",
  "title": "Improve the hook",
  "status": "active | archived",
  "lastMessagePreview": "Here are three stronger hooks...",
  "messageCount": 6,
  "context": {
    "transcriptId": "transcript-id",
    "analysisRunId": "analysis-id",
    "personaVersion": 3,
    "artifactIds": ["artifact-1"]
  },
  "createdAt": "timestamp",
  "updatedAt": "timestamp"
}
~~~

### users/{uid}/projects/{projectId}/chatThreads/{threadId}/messages/{messageId}

~~~json
{
  "ownerUid": "uid",
  "role": "user | assistant | tool",
  "content": "Rewrite the opening for a Hindi-speaking audience.",
  "parts": [],
  "status": "complete | streaming | failed",
  "citations": [],
  "toolCalls": [],
  "artifactIds": [],
  "tokenUsage": {
    "input": 0,
    "output": 0
  },
  "createdAt": "timestamp"
}
~~~

### users/{uid}/projects/{projectId}/feedback/{feedbackId}

~~~json
{
  "ownerUid": "uid",
  "targetType": "finding | artifact | chat_message",
  "targetId": "id",
  "rating": "helpful | not_helpful",
  "comment": "This suggestion was useful.",
  "createdAt": "timestamp"
}
~~~

### users/{uid}/projects/{projectId}/exports/{exportId}

~~~json
{
  "ownerUid": "uid",
  "status": "queued | generating | ready | failed",
  "artifactIds": ["artifact-1", "artifact-2"],
  "storagePath": "users/uid/projects/project-id/exports/export.zip",
  "expiresAt": "timestamp",
  "createdAt": "timestamp",
  "updatedAt": "timestamp"
}
~~~

### users/{uid}/notifications/{notificationId}

~~~json
{
  "ownerUid": "uid",
  "type": "job_ready | job_failed | connection_expiring | persona_update",
  "title": "Your analysis is ready",
  "body": "The video review has completed.",
  "resourceType": "project",
  "resourceId": "project-id",
  "read": false,
  "createdAt": "timestamp"
}
~~~

### users/{uid}/projects/{projectId}/auditEvents/{auditEventId}

~~~json
{
  "ownerUid": "uid",
  "actorType": "user | service | agent",
  "actorId": "uid-or-service-account",
  "action": "project.created | connection.connected | artifact.deleted",
  "resourceType": "project",
  "resourceId": "project-id",
  "metadata": {},
  "createdAt": "timestamp"
}
~~~

## 8. Platform-level collections

### glossaries/{glossaryId}

Versioned terminology corpus. The actual term files live in Cloud Storage; Firestore stores the
metadata and the active version.

~~~json
{
  "scope": "global | project",
  "ownerUid": null,
  "sourceLanguage": "en",
  "targetLanguage": "hi",
  "category": "general | legal | education | healthcare | automobile | news | trap_list",
  "version": 1,
  "storagePath": "corpus/global/en-hi/v1.tsv",
  "termCount": 4200,
  "translationGlossaryId": "projects/.../glossaries/...",
  "status": "active | archived",
  "createdAt": "timestamp",
  "updatedAt": "timestamp"
}
~~~

### demoProfiles/{demoProfileId}

Pinned scenarios for the stage. See [mock-and-seed.md](./mock-and-seed.md).

~~~json
{
  "name": "controversial",
  "description": "A video that trips the truth and legal reviewers.",
  "projectIdTemplate": "project-id",
  "seedBundlePath": "fixtures/seed/controversial/",
  "createdAt": "timestamp"
}
~~~

## 9. Firestore indexes

Create composite indexes for:

~~~text
projects: ownerUid ASC, updatedAt DESC
projects: ownerUid ASC, status ASC, updatedAt DESC
jobs: ownerUid ASC, status ASC, createdAt DESC
analysisRuns: ownerUid ASC, createdAt DESC
findings: ownerUid ASC, dimension ASC, startMs ASC
artifacts: ownerUid ASC, type ASC, createdAt DESC
chatThreads: ownerUid ASC, updatedAt DESC
notifications: ownerUid ASC, read ASC, createdAt DESC
glossaries: scope ASC, sourceLanguage ASC, targetLanguage ASC, category ASC, version DESC
~~~

## 10. Security model

The browser may read/write only user-owned, non-sensitive project data. The browser must never directly read:

- OAuth connection tokens.
- BigQuery data.
- Raw social API payloads.
- Internal reviewer prompts.
- Worker job events containing secrets or stack traces.
- Platform collections: `glossaries` and `demoProfiles` are backend-only.

The backend must authorize using both the Firebase UID and the document ownerUid. Firestore rules are a second boundary, not a replacement for backend authorization.

## 11. Deletion

Deletion is **real, not soft**. Two reference implementations define the contract:

- `ProjectService.delete` — deletes every Cloud Storage object under `project_object_prefix`
  (`users/{uid}/projects/{projectId}/`) and recursively deletes the project Firestore subtree
  (the project doc plus every subcollection, including nested `transcripts/{id}/segments`).
- `UserService.delete_account` — deletes every object under `users/{uid}/` and recursively
  deletes the user subtree.

Because deletion is by **GCS prefix** and **Firestore recursive tree**, any new project-scoped
data is covered automatically **as long as it lives under the project's Firestore path or object
prefix**. Anything stored elsewhere (a top-level collection, a different bucket, a third-party
record) is not covered and must be added to the delete path explicitly, with a test. Treat
"where does this get deleted?" as a required design question for every new feature.
