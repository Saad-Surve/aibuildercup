# Progress — transcript + reviewer flows moved to a WebSocket (2026-09-27 19:15)

## What I did

Replaced the SSE stream + react-query polling with **one WebSocket per browser session**
(`GET /api/ws`). The transcript flow and the reviewer/analysis flow now both ride that socket;
react-query is the fetch/cache layer only, and polling survives solely as a degraded fallback
when the socket is down.

Motivation (from the request): the old flow was painful to manage — SSE only carried
project + latest-job state, analysis was pure polling, and every query carried its own
`refetchInterval`/`refetchIntervalInBackground`, plus the CDN-caching-404 saga.

## Architecture decision

- **One in-process hub** (`backend/app/realtime/hub.py`): `(ownerUid, projectId) -> [asyncio.Queue]`.
  Write paths call `publish`; the socket drains its queue. Publishing is fire-and-forget and
  never raises, so a realtime miss can never fail the write that triggered it.
- **Why in-process is correct today:** workers run as FastAPI `BackgroundTasks` in the same
  Cloud Run instance, and the service is deployed `--max-instances 1`, so the writer and the
  socket share one event loop. The hub is the single place to swap for Firestore snapshots /
  Pub/Sub pull if the service ever scales past one instance.
- **Transport:** Cloud Run supports WebSockets natively and already runs `--no-cpu-throttling`.
  **Firebase Hosting rewrites do not proxy WebSocket upgrades**, so in prod the socket targets
  the **Cloud Run service URL directly** (`NEXT_PUBLIC_WS_BASE_URL`, resolved in the deploy
  workflow). HTTP API keeps going through the `/api/**` rewrite. Dev derives `ws://localhost:8080/api/ws`
  from the API base — no extra config.
- **Auth:** browsers cannot set an `Authorization` header on an upgrade, so the Firebase ID
  token travels as `?token=`. Verified server-side with the same `verify_id_token`. On failure
  the server **accepts then closes with 4401** (no data sent). It does *not* use a Starlette
  401 denial response: that leaves `handshake_complete` unset and uvicorn logs
  `ASGI callable returned without completing handshake` on every rejection. Verified clean.
- **Events are push, not poll:** `job_service` / `project_service` / `analysis_service` and the
  transcribe worker emit frames at the point of the Firestore write. `analysis.progress` fires
  **per reviewer outcome**, so reviewer-level liveness exists (the old SSE never had it).
  Expensive payload work (reading the reviewer subcollection) is skipped when nobody is subscribed
  (`has_subscribers`).
- **Bounded lifetime:** the socket closes itself at ~50 min; Cloud Run is deployed `--timeout 3600`.
  The client reconnects with backoff and a **fresh token** each attempt (tokens expire hourly),
  re-subscribes, and re-invalidates the resource queries; the subscribe-time snapshot re-primes
  progress UI.

## Contract changes (contract-first)

- `contracts/openapi.yaml`: removed `GET /api/projects/{projectId}/events` (SSE); added
  `GET /api/ws` with an `x-websocket-protocol` description and **real schemas** for every frame:
  `WsClientMessage`, `WsServerMessage`, `WsSnapshotProject`, `WsEventProjectProgress`,
  `WsEventJobProgress`, `WsEventTranscriptReady`, `WsEventAnalysisProgress`, `WsEventAnalysisReady`,
  `WsError`, `WsPong`, plus `ProjectProgress`/`JobProgress` sub-objects. (The old SSE payload was
  never in the contract — that gap is closed.)
- `contracts/events.md`: new "Realtime WebSocket protocol" section (transport/auth, message list,
  rules). Pub/Sub section untouched.
- `docs/technical-design/api-design.md` §7 rewritten (WS + notes); §1 and the "long-running work"
  line updated. `frontend-plan.md`, `backend-plan.md`, `diagrams.md` SSE mentions updated.

## Backend changes

- New `backend/app/realtime/`: `hub.py` (EventHub, loop binding, thread-safe delivery fallback,
  overrun drops), `events.py` (frame builders + emit helpers), `__init__.py` re-exports.
- New `backend/app/api/ws.py`: the endpoint — token auth, `subscribe.project` + ownership check,
  snapshot-then-subscribe ordering, reader/writer loops, server ping every 30s, bounded lifetime,
  clean hub teardown on either side finishing.
- Emit call sites: `job_service` (`mark_running`/`update_progress`/`mark_succeeded`/`mark_failed`/
  `cancel`/`requeue_failed`), `project_service` (`mark_processing`/`mark_transcript_ready`/`mark_failed`),
  `analysis_service` (`mark_running`/`save_reviewer_outcome`/`finish_run`), transcribe worker
  (`transcript.ready`, emitted independently of Pub/Sub being configured).
- Removed the SSE endpoint from `app/api/jobs.py`; registered the ws router in `main.py`.
- **No new dependencies** (`uvicorn[standard]` already ships WebSocket support).

## Frontend changes

- New `web/src/lib/realtime.ts`: shared socket client — lazy connect, token per attempt,
  exponential backoff + jitter, auto-resubscribe, client heartbeat, 45-min proactive reconnect,
  `visibilitychange` fast-reconnect, refcounted subscriptions (StrictMode-safe).
- New `web/src/hooks/use-project-events.ts`: the only place frames touch query state. Progress
  frames `setQueryData`; completion frames `invalidateQueries` (transcript / reviewers / heatmap /
  findings / runs). On reconnect it re-invalidates the load-bearing queries.
- `project-workspace.tsx`: SSE effect removed, uses the hook; project/job queries now poll **only
  when the socket is down** (8s).
- `use-project-transcript.ts`: no timer by default; `shouldPoll` now means "socket down and
  pipeline running".
- `review-panel.tsx`: all six intervals became `!live && …` fallbacks; event-driven updates are
  primary. `transcript-panel.tsx` gained a `live` prop.
- `lib/projects.ts`: deleted `subscribeToProjectEvents` and `ProjectProgressEvent`.

## Infra / CI

- `.github/workflows/deploy.yml`: added `--timeout 3600`; web job resolves the Cloud Run service
  URL after auth and passes it as `NEXT_PUBLIC_WS_BASE_URL`; Next build cache key includes it.
- `web/.env.example`: documented `NEXT_PUBLIC_WS_BASE_URL` (unset in dev = derived).

## Verification

- `backend`: `uv run ruff check .` clean; `uv run mypy app` clean (68 files).
- `web`: `bun run lint` 0 warnings/errors; `bun run lint:eslint` 0 errors (one pre-existing,
  intentional `no-img-element` warning in `project-card.tsx`); `bun run build` (typecheck + static
  export) clean.
- Live smoke: started the API, `GET /api/readyz` 200; WS upgrade with no/bogus token
  accepted then closed `code=4401 reason='Unauthorized'`, **zero ERROR lines** in the server log.

## Not done / next steps

1. **Not run live against GCP with a real Firebase token** — local smoke covered auth rejection
   only. Do one authenticated end-to-end run (upload → transcript frames → analysis frames) once
   deployed, since `NEXT_PUBLIC_WS_BASE_URL` must resolve to the real service URL.
2. **Deploy is required for the prod socket to work** (the hosted web currently points WS at the
   API origin; the new deploy sets the direct Cloud Run URL). Until deployed, prod has no realtime
   and falls back to the degraded polling.
3. Hosting-rewrite WS was deliberately avoided; if a future change makes the hosted origin work,
   `NEXT_PUBLIC_WS_BASE_URL` can be dropped.
4. `--max-instances 1` is now load-bearing for the in-process hub. If that changes, port the hub
   to Firestore snapshots or Pub/Sub pull (single seam, commented in `hub.py`).
5. Consider `--session-affinity` only if instance count is ever raised.
