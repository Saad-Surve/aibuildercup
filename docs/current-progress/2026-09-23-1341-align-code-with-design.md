# Progress — 2026-09-23 13:41 UTC — align code with the design; sync docs

The design docs are the frozen source of truth and the handoff mechanism. Earlier sessions took
shortcuts (inline trigger, no SRT, unimplemented-but-contracted routes) and recorded them only in
progress notes, so the design read as done while the code diverged. This session brings the
transcription/API surface up to the design and makes every remaining gap explicit in the docs.
Uncommitted (not requested).

## Code brought up to the design

**SRT (design diagram 5 / backend-plan §7).** `transcript_service.save` now also writes
`captions/<lang>.srt` (`paths.transcript_srt_object_path`) and stores `srtStoragePath` on the
transcript doc; `TranscriptRecord` gained the field.

**Pub/Sub event path (design diagram 4/5).** New `app/events.py` (envelope + type→topic routing),
`app/services/pubsub_service.py` (`PubSubClient` + real publisher), and the worker now publishes
`transcript.ready` to `transcription-events`. The trigger of record is now real:
media bucket `object finalized` → `video-events` → push subscription →
`POST /api/internal/pubsub/video-events` (`app/api/internal.py` + `app/workers/pubsub_handlers.py`)
→ `run_transcribe`. `POST /assets/{id}/complete` stays the fast UX path; both converge on the same
idempotent job via `AssetService.queue_transcription`. The push endpoint verifies a Pub/Sub OIDC
token when `PUBSUB_PUSH_AUDIENCE` is set (`app/auth/pubsub.py`).

**API parity (design api-design.md).** Added `GET /projects/{id}/transcript/segments/{segmentId}`
and `POST /jobs/{jobId}/cancel`; added the project SSE stream `GET /projects/{id}/events`;
renamed `playback-url`/`PlaybackUrl`/`getPlaybackUrl` → `download-url`/`DownloadUrl`/`getDownloadUrl`
to match the design (backend, contract, web).

## Infra (Terraform)

- `google_storage_notification.video_finalized` on the media bucket → `video-events`.
- `transcribe-worker-sub` is now a **push** subscription to the API endpoint (OIDC as the
  `transcribe` SA), created only when `var.api_url` is set.
- `google_service_account_iam_member.pubsub_push_token_creator` so the Pub/Sub service agent can
  mint the push token.
- New `var.api_url`; deploy workflow sets `PUBSUB_PUSH_AUDIENCE` + `PUBSUB_PUSH_SERVICE_ACCOUNT`.
- `terraform validate` passes.

## Contracts / docs

- `contracts/openapi.yaml`: new routes above; `DownloadUrl` schema; unbuilt paths
  (analysis/findings/heatmap, artifacts, chat) marked `x-status: planned`.
- `api-design.md`: added an **Implementation status** section (implemented vs planned), marked
  regenerate planned, removed the demo/MOCK endpoints, documented the push endpoint and that
  `transcript.ready` is published.
- `backend-plan.md`: fixed the stale "model long" → `chirp_3`; documented the trigger of record;
  rewrote §16 (no mock mode) and pruned the cassette files from the repo tree.
- `diagrams.md`: diagram 1 Vertex→Gemini Developer API; diagram 16 rewritten (no mock mode).
- `mock-and-seed.md` rewritten (fixtures + real services; seed/demo scenarios marked planned).
- `db-design.md`: `srtStoragePath` added; `cassetteIndex` removed.
- `frontend-plan.md`, `workstreams.md`, `README.md`, `AGENTS.md`, `contracts/firestore.md`:
  removed MSW/cassette references; noted workers run in-process for now.

## Verified

- Backend: **149 passed**, ruff + mypy clean. Web: lint + build clean. `terraform validate` OK.

## Not done / next

- **Apply the infra**: `terraform apply -var 'api_url=https://<api-url>'` (the earlier apply was
  blocked on a Firestore-rules permission unrelated to this). Until applied, the push path does
  not fire in prod; the `complete` fast path still works.
- Deferred and now documented as planned: analysis/findings/heatmap, artifacts, chat,
  localization/glossaries, transcript regenerate, account export, demo/admin seeding, seed script,
  and separate worker containers. `analysis.requested`/`analysis.ready` etc. are declared but not
  published.
- Consider wiring the web to the new SSE endpoint (it still polls `GET /jobs/{jobId}`).
- Commit + push.
