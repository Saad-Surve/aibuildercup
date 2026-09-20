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
cassetteIndex/{cassetteKey}   platform, dev only
```

## Rules

- Every user-owned document carries `ownerUid`.
- Store GCS object paths, never signed URLs.
- Timestamps are Firestore Timestamps in UTC.
- Only the backend reads `connections`, `glossaries`, `demoProfiles`, `cassetteIndex`.
- Ownership is checked in the API, not only in Firestore rules.
