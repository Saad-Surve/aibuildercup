# Repository optimization: final handoff

## What changed

This completes the optimization audit started in `2026-10-10-2233-backend-concurrency-and-batching.md`.

### Backend throughput, persistence, and cost

- 75 HTTP routes with synchronous service calls now use FastAPI's thread pool; synchronous
  Firebase verification is also off-loop. Model and WebSocket endpoints stay async.
- Cloud/connector calls and media staging in all six async workers, plus draft/persona flows,
  are offloaded. Reviewer context artifact uploads and AAC extraction/muxing also yield to the
  server loop. No Google SDK was introduced into feature code.
- `FirestoreClient.set_documents` groups reviewer placeholders, findings, heatmap bins,
  transcript segments, and channel metadata into commits of up to 400 documents.
- `FirestoreClient.create_document` atomically creates rather than overwrites. New job IDs
  derive from SHA-256(owner/project/idempotency key), so racing upload-complete/Pub/Sub requests
  converge on one document. Legacy random IDs are still found/reused through the existing
  query. `serialize_job` protects all six worker entry points against simultaneous execution
  of the same job in the current single-instance deployment and cleans up idle locks.
- Reviewer findings persist before the reviewer-completed progress event. Outcome callbacks
  are serialized while cloud writes execute in threads, preserving progress ordering.
- Reuse signing credentials and serialize refreshes. Firebase initialization is thread-safe;
  write middleware shares verified claims with the auth dependency for ordinary users too.
- Preserve CORS Origin in `Vary` when adding Authorization. Missing transcript versions now
  produce the intended 404 rather than StopIteration.
- Dubbing continuously refills its bounded synthesis slots instead of waiting for each fixed
  batch's slowest member. Outstanding coroutines are canceled/drained after a failure.
- Caption/dub staging reads dimensions and duration with one ffprobe scan. On tech_review.mp4,
  five interleaved warmed runs had medians 101.9 ms (two probes) and 50.8 ms (combined), with
  identical (1280, 640, 318252 ms) metadata. This is one local fixture, not an end-to-end latency
  benchmark.
- Docker copies app files with their final ownership and avoids recursive chown of the venv,
  preventing dependency contents from being copied into another large layer.

### Frontend loading and interaction

- Split video and draft workspaces by project kind. Avatar artwork/assets load when needed;
  ordinary prose no longer initializes Shiki's syntax grammars.
- Memoize heatmap track rows, stabilize selection callbacks, and index bins by ID so hovering
  one track does not rerender every track or repeatedly scan the whole bin array.
- Coalesce realtime completion invalidations over 200 ms. Navigating away still marks pending
  queries stale. Guard pending token reads to prevent duplicate socket connection attempts;
  reject stale socket messages and send unsubscribe when the last observer leaves a project.
- Clear query caches on authentication identity changes, abort stale profile requests, and
  suppress stale refresh responses. Permanent 4xx failures do not receive an automatic query
  retry; transient server/rate errors retain one retry.
- Media cache project entries now point to asset blobs instead of duplicating full video bytes.
  Existing blob entries remain readable. Remote poster capture uses the video element's range
  requests rather than explicitly fetching and caching the entire object. Browser/container
  range behavior still determines actual bytes transferred. Existing size guard remains.
- Project poster images have explicit dimensions, async decoding, and lazy loading with Next
  Image; static export remains unoptimized for signed/data URLs. Both linters are now clean.
- Removed unused direct dependencies react-hook-form, lucide-react, and zod with Bun. zod v3
  remains transitively required by shadcn. Next's optional Playwright peer metadata is not an
  installed test library. No test files or test dependencies were added.

## Measured initial script payloads

Baseline and final use the same webpack production bundler and environment. These are script
files referenced by exported route HTML, not the total bytes loaded after authenticated
workspaces and avatar artwork mount. Gzip is a per-file estimate, not an observed CDN transfer.

| Route HTML | Before raw bytes | After raw bytes | Reduction | Before gzip bytes | After gzip bytes | Reduction |
|---|---:|---:|---:|---:|---:|---:|
| index.html | 959,324 | 961,725 | -0.3% | 300,701 | 301,699 | -0.3% |
| dashboard.html | 1,990,757 | 1,286,948 | 35.4% | 630,079 | 418,564 | 33.6% |
| projects/view.html | 3,373,720 | 1,230,387 | 63.5% | 868,473 | 399,302 | 54.0% |
| projects.html | 1,990,196 | 1,286,387 | 35.4% | 629,825 | 418,311 | 33.6% |
| onboarding.html | 1,779,543 | 1,073,909 | 39.7% | 559,601 | 346,429 | 38.1% |

The marketing entry's approximately 1 KB gzip increase comes with shared auth/query safeguards;
most savings are in authenticated routes and onboarding.

## Structural / contract changes

- OpenAPI and events protocol gained `unsubscribe.project`; HTTP payloads/endpoints are unchanged.
- Firestore quick contract documents deterministic, atomically created job IDs. Existing job
  document fields remain unchanged. Internal Firestore protocol gained bulk set/atomic create.
- Backend design records the sync/async boundary, bulk writes, and worker guard.
- Browser cache project aliases retain backward compatibility and existing purge keys.
- No new persistent collections or storage prefixes: existing project/account deletion covers
  every backend record. No Terraform changes, deployment, commits, or AI model/cost-cap changes.

## Verification completed

- `UV_CACHE_DIR=/private/tmp/habeas-uv-cache uv run ruff check .`: clean.
- `UV_CACHE_DIR=/private/tmp/habeas-uv-cache uv run mypy app`: clean, 117 files.
- `bun run lint`, `bun run lint:eslint`: clean, no warnings.
- oxfmt check on all 11 changed/new frontend source files: clean.
- `bun run build --webpack`: production static export succeeds, TypeScript succeeds, all routes
  generated. `git diff --check`: clean.
- One-off runtime checks (no test files): health 200, unauthenticated projects 401, CORS Vary
  includes Origin and Authorization; project-scoped unsubscribe preserves the other project;
  thread-originated queue overflow produces the internal close signal and unregisters the socket.
- OpenAPI YAML parses and references the unsubscribe frame. Representative API routers resolve
  synchronous handlers. Real ffprobe ran on the existing fixture, as recorded above.
- Read-only live Firestore lookup of the documented demo user succeeded. User docs identify the
  owner by the document path; the historical demo root has no matching ownerUid field. No cloud
  documents were written by verification and no paid AI calls were made.
- T3 collaborative preview loaded the built marketing page at desktop (1280 px) and mobile
  (390 px); heading is present, no horizontal overflow, no broken images, no failed script
  requests observed. Snapshot/screenshot calls repeatedly failed in the preview provider;
  DOM inspection through its evaluate tool worked.

## Limits / next step

- Default Turbopack cannot bind its CSS-worker port in this sandbox. Sandboxed builds cannot
  resolve Google Fonts either; network-enabled webpack builds verified the actual production
  output. CI still uses the unchanged default Turbopack configuration.
- Local Docker daemon is stopped, so the Dockerfile change was reviewed but the image was not
  built. Start Docker and build the backend image before deployment.
- Full authenticated upload/transcription/review/dub/publish and browser media-cache flows have
  not been exercised end-to-end. Smoke-run an existing fixture with two simultaneous upload
  completion deliveries and confirm one job/transcription, reviewer findings, captions, and
  dubbing. Atomic/batched cloud writes were type/lint reviewed, not exercised against live data.
- Atomic job creation is cross-instance safe; worker execution serialization remains in-process.
  Keep max-instances 1 until a distributed claim/lease and shared realtime transport exist.
- Firestore batching reduces RPC overhead, not per-document billing. No service latency or
  cloud cost reduction is claimed from a synthetic load test.
