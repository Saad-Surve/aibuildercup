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
