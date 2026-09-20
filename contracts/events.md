# Pub/Sub Event Contract

Internal only — these are not HTTP endpoints. Full detail in
`../docs/technical-design/api-design.md` (section 16).

## Envelope

```json
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
```

## Types

```text
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
```

## Rules

- Every handler is idempotent. Pub/Sub delivery can repeat.
- Every event carries `ownerUid` and `projectId` when applicable.
- Failures after max attempts go to the matching dead-letter topic.
- Never put secrets or raw private media in a payload.
