# Firestore Contract

The full schema is in `../docs/technical-design/db-design.md`. This file is the quick reference
the code must match.

## Hierarchy

```text
users/{uid}
├── connections/{connectionId}
│   └── syncRuns/{syncRunId}
├── personaRevisions/{revisionId}
├── notifications/{notificationId}
├── usagePeriods/{periodId}
└── projects/{projectId}
    ├── assets/{assetId}
    ├── jobs/{jobId}/events/{eventId}
    ├── transcripts/{transcriptId}/segments/{segmentId}
    ├── captionRenders/{captionRenderId}
    ├── thumbnailConcepts/{thumbnailId}
    ├── draft/main
    ├── analysisRuns/{analysisRunId}
    │   ├── reviewers/{reviewerRunId}
    │   ├── findings/{findingId}
    │   └── heatmapBins/{binId}
    ├── clipCandidates/{candidateId}
    ├── artifacts/{artifactId}/versions/{versionId}
    ├── localizations/{localizationId}
    ├── chatThreads/{threadId}/messages/{messageId}
    ├── feedback/{feedbackId}
    ├── exports/{exportId}
    └── auditEvents/{auditEventId}

glossaries/{glossaryId}       platform
demoProfiles/{demoProfileId}  platform
```

## Rules

- Every user-owned document carries `ownerUid`.
- Store GCS object paths, never signed URLs.
- Timestamps are Firestore Timestamps in UTC.
- Only the backend reads `connections`, `glossaries`, `demoProfiles`.
- Ownership is checked in the API, not only in Firestore rules.

## Draft document

`users/{uid}/projects/{projectId}/draft/main` is the single versioned draft for a
`kind: "draft"` project: a `brief`, ordered `blocks[]`, and each block's immutable
`versions[]`. Deletes need no special handling because the document sits under the project
subtree. The project document mirrors `draftSummary` (title, preview, word/block/version
counts) for list cards.

## Thumbnail concept documents

`users/{uid}/projects/{projectId}/thumbnailConcepts/{thumbnailId}` holds one candidate
thumbnail: the planned `headline`, the evidence-citing `rationale`, the `aspect`, the
`referenceTimestampsMs` used to keep the creator's likeness, and an append-only `versions[]`
(each with its `storagePath`, `critique`, `model`, and `costUsd`). The generated images live
under the project object prefix at `.../thumbnails/{thumbnailId}/v{n}.{ext}`, and the reference
frames at `.../thumbnails/{thumbnailId}/refs/f{ms}.jpg`. Both the Firestore subtree and the
object prefix are covered by the existing recursive project / account delete, so thumbnail data
needs no extra delete wiring. Applying a concept writes its headline + rationale to
`project.thumbnailConcept`, which the reviewers already read as packaging context.

## Localizations (dubbing)

A localization is one request to dub a project's source video into a target language. The
field shape lives in `../docs/technical-design/db-design.md`; the implemented subset is:

```json
{
  "ownerUid": "uid",
  "projectId": "project-id",
  "sourceAssetId": "asset-id",
  "sourceTranscriptId": "transcript-id",
  "transcriptVersion": 2,
  "sourceLanguage": "en",
  "targetLanguage": "en",
  "status": "queued | translating | synthesizing | muxing | ready | failed",
  "voice": "en-us-neural-a",
  "speakerVoices": { "0": "en-US-Neural2-D" },
  "keepOriginalAudio": false,
  "fileName": null,
  "videoStoragePath": "users/uid/projects/project-id/renders/dubs/localization-id.mp4",
  "audioStoragePath": "users/uid/projects/project-id/renders/dubs/localization-id.mp3",
  "captionsStoragePath": "users/uid/projects/project-id/renders/dubs/localization-id.srt",
  "mimeType": "video/mp4",
  "sizeBytes": 0,
  "durationMs": 0,
  "width": 0,
  "height": 0,
  "corpusVersion": 1,
  "glossaryVersion": 3,
  "glossaryTerms": [{ "source": "credit score", "target": "क्रेडिट स्कोर", "targetLanguage": "hi" }],
  "jobId": "job-id",
  "error": null,
  "createdAt": "timestamp",
  "updatedAt": "timestamp"
}
```

The doc lives at `users/{uid}/projects/{projectId}/localizations/{localizationId}` and its
media under `users/{uid}/projects/{projectId}/renders/dubs/`, so the recursive project delete
covers both.

`corpusVersion`/`glossaryVersion` record what the run was built with (for reproducibility),
and `glossaryTerms` is the snapshot of the applicable project terms taken at create time, so a
later glossary edit cannot change a running or finished dub. `glossaryTerms` is internal and is
not part of the API response.

## Project glossary

`users/{uid}/projects/{projectId}/glossary/main` is the creator's own terminology for one
project. It sits under the project subtree, so the recursive project delete removes it too.

```json
{
  "ownerUid": "uid",
  "projectId": "project-id",
  "sourceLanguage": "en",
  "terms": [{ "source": "credit score", "target": "क्रेडिट स्कोर", "targetLanguage": "hi" }],
  "version": 3,
  "createdAt": "timestamp",
  "updatedAt": "timestamp"
}
```

A term with an empty `targetLanguage` applies to every target. `PUT /projects/{id}/glossary`
replaces the terms and bumps `version`; the global corpus (glossary + trap list) is the
bundled `backend/app/assets/corpus/global.json`, versioned separately.
