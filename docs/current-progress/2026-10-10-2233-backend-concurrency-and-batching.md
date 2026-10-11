# Repository optimization: backend concurrency and persistence

## Work completed

- Audited the latest handoff, design, API/Firestore contracts, provider boundaries, deployment
  configuration, and web dependencies. Working tree was clean; no tracked tests or testing
  dependencies were present.
- Moved 75 synchronous HTTP handlers and Firebase auth dependency onto FastAPI's bounded
  thread pool. Kept coroutine routes for genuine async model calls/WebSockets.
- Offloaded synchronous cloud, connector, persistence, and media staging calls from async
  workers and draft/persona services. Reviewer persistence now yields to other reviewers and
  sockets rather than blocking the server loop.
- Added `FirestoreClient.set_documents` with bounded 400-document commits, used for queued
  reviewers, findings, heatmap bins, transcript segments, and channel content metadata.
  Completion is still published only after writes complete. Billing remains per document;
  this reduces RPCs, not Firestore write charges.
- Reuse signing credentials and serialize access-token refresh for Cloud Storage signed URLs.
- Preserve existing `Vary` headers when adding Authorization (CORS Origin must survive).
- Return the intended 404 for absent transcript versions instead of leaking StopIteration.
- Made the hub's subscriber registry thread-safe. Queue overflow now wakes the writer to
  close with 1013, including events published from threads; previously it dropped the
  subscription without closing and thread-side overflow escaped as a loop callback exception.
- Verify WebSocket ownership off-loop, register before rereading the snapshot, and serialize
  the baseline against queued outbound events.

## Structural changes

- New internal Firestore bulk-write protocol method; existing document paths/shapes unchanged.
- Added `unsubscribe.project` client frame to OpenAPI and events contracts. Server can now
  remove a single project subscription without closing the shared socket.
- No infrastructure changes, deployment, or commits. All new project data remains under
  existing deletion prefixes; batching introduces no extra persistent records.

## Verification and environment gotchas

- `UV_CACHE_DIR=/private/tmp/habeas-uv-cache uv run ruff check .` passes.
- `UV_CACHE_DIR=/private/tmp/habeas-uv-cache uv run mypy app` passes (116 files).
- Baseline `bun run build --webpack` passed with network permission for Google Fonts.
- Default Turbopack build fails in this environment because its CSS worker cannot bind a
  port. Sandboxed builds also cannot resolve Google Fonts. Use a network-enabled webpack
  build for verification here; production's default build configuration remains unchanged.
- Baseline initial script bytes (raw/gzip, from static HTML): projects/view 3,373,720/868,473;
  dashboard 1,990,757/630,079; landing 959,324/300,701.

## Remaining / next step

Frontend optimization is in progress: split video/draft workspaces and avatar assets, defer
syntax-highlighter initialization, coalesce realtime cache invalidations, guard concurrent
socket connection attempts, and clear query data when authentication identity changes.
Run all web checks and measure final bundles, then review async offloading for remaining
blocking helper calls. Live GCP pipelines have not been exercised during this audit.
