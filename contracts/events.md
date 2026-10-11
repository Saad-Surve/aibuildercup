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

---

# Realtime WebSocket protocol (browser-facing)

Replaces the retired `GET /projects/{id}/events` SSE stream. One WebSocket per browser
session; the client subscribes per project after connecting. Frame schemas are defined in
`openapi.yaml` (`WsClientMessage` / `WsServerMessage`), endpoint contract at `/api/ws`.

## Transport and auth

- Endpoint: `{WS_BASE}/api/ws?token=<firebaseIdToken>`. The token is a Firebase ID token,
  verified server-side exactly like HTTP bearer auth. Browsers cannot set an
  `Authorization` header on a WebSocket, hence the query parameter. A missing or invalid
  token closes the socket immediately with code `4401` (no data is sent first); the client
  reconnects after refreshing the token.
- In prod the socket targets the Cloud Run service URL directly (Firebase Hosting rewrites
  do not proxy WebSocket upgrades); in dev it is the API origin. `NEXT_PUBLIC_WS_BASE_URL`
  configures the base at web build time.
- Cloud Run applies its request timeout to sockets, so connection lifetime is bounded.
  Clients must reconnect on close and refresh the token each attempt (it expires hourly).

## Messages

Client → server (JSON, one object per frame):

```json
{"type": "subscribe.project", "projectId": "project-id"}
{"type": "unsubscribe.project", "projectId": "project-id"}
{"type": "ping"}
```

Server → client:

```json
{"type": "snapshot.project", "projectId": "...", "status": "processing",
 "progress": {"stage": "transcription", "percent": 30, "message": "..."},
 "job": {"jobId": "...", "type": "transcribe", "status": "running",
         "progress": {"percent": 30, "step": "speech_to_text", "message": "..."}}}

{"type": "project.progress", "projectId": "...", "status": "ready",
 "progress": {"stage": "transcription", "percent": 100, "message": null}}

{"type": "job.progress", "projectId": "...", "jobId": "...", "jobType": "transcribe",
 "status": "running", "progress": {"percent": 30, "step": "speech_to_text", "message": "..."},
 "error": null}

{"type": "transcript.ready", "projectId": "...", "transcriptId": "...",
 "jobId": "...", "durationMs": 123000, "language": "en"}

{"type": "analysis.progress", "projectId": "...", "analysisRunId": "...",
 "status": "running", "completedDimensions": ["clarity"],
 "reviewerStatuses": [{"dimension": "clarity", "status": "succeeded",
                       "findingCount": 3, "error": null}]}

{"type": "analysis.ready", "projectId": "...", "analysisRunId": "...",
 "status": "ready", "overallScore": 3.4,
 "findingCounts": {"none": 0, "low": 2, "medium": 1, "high": 0, "critical": 1}}

{"type": "pong"}
{"type": "error", "code": "NOT_FOUND", "message": "Project not found"}
```

## Rules

- The server sends `snapshot.project` immediately after a successful subscribe; the
  client uses it to prime the progress UI without an extra HTTP fetch.
- The server registers the subscription after verifying ownership and before reading
  the snapshot, so events written during the read remain queued for delivery.
- `unsubscribe.project` removes only that project's subscription from the calling
  socket. Clients send it when the last local observer leaves the project.
- A client whose bounded event queue fills is closed with code `1013`; reconnect
  and HTTP cache invalidation restore its state rather than silently losing events.
- Events are emitted when the backing documents are written, inside the job write path —
  there is no separate broker to poll. If no socket is subscribed, emission is a no-op.
- `analysis.progress` events fire per reviewer outcome (not just per job tick), giving
  reviewer-level liveness the SSE stream never had.
- Keepalive: either side sends `ping`; the peer answers `pong`. The server pings every
  ~30s. Server-initiated close → client reconnects with backoff.
- Malformed or unauthorized frames: the server sends `error` and closes the socket.
