# Resonance API reference

[OpenAPI](../../contracts/openapi.yaml) defines wire shapes. `backend/app/main.py` is
the registered-route inventory; Pydantic schemas and services implement validation and
ownership. The current web client/types are manually maintained against this contract.

## Conventions

Base prefix: **`/api`**, locally `http://localhost:8080/api`. Requests authenticate with
`Authorization: Bearer <Firebase ID token>`, except health, demo session, OAuth callback
and separately authenticated internal push. Owned resource mismatches return unavailable
or forbidden responses; callers do not supply an arbitrary `ownerUid`.

Errors use `{error: {code, message, requestId, details}}`; `x-request-id` links requests
and responses. Authenticated responses are no-store. List pagination/filters vary by
endpoint; use the contract rather than assuming a universal cursor shape.

Long media/analysis/packaging/publishing operations return accepted job references.
Draft generation/assist are awaited responses. Do not assume every POST is a 202 job.
Idempotency is implemented through service-specific stored job keys, especially asset
completion; a generic `Idempotency-Key` HTTP middleware is not implemented.

## Account, persona and demo

| Route family | Behavior |
|---|---|
| `GET /healthz`, `/readyz` | Liveness/readiness; runtime implementation determines actual checks |
| `POST /demo/session` | Passwordless Firebase custom token for the configured read-only demo |
| `GET /me`, `DELETE /me`, `PUT /me/avatar` | Profile, backend account deletion and avatar state |
| `GET/PUT /onboarding` | Saved creator preferences/progress |
| `POST /onboarding/research`, `/onboarding/complete` | Grounded profile research and persona creation |
| `GET/PATCH /persona` | Versioned persona read/edit |

The read-only demo can authenticate and read its owned workspace. Mutating routes are
blocked by middleware; UI disablement alone is not the enforcement. Firebase sign-in uses
Google, not the old shared demo password.

## Projects, source revisions and transcripts

| Route family | Behavior |
|---|---|
| `GET/POST /projects`, `GET/PATCH/DELETE /projects/{projectId}` | Video/draft project lifecycle |
| `POST /projects/{projectId}/upload-session` | Signed direct Storage upload session |
| `GET /projects/{projectId}/assets` | Asset metadata |
| `DELETE /projects/{projectId}/assets/{assetId}` | Discard inactive rough cut and its derived transcript/reviews |
| `GET /projects/{projectId}/assets/{assetId}/captions` | Ready revision captions without activation |
| `POST /projects/{projectId}/assets/{assetId}/complete` | Verify uploaded object and reuse/queue transcription |
| `GET /projects/{projectId}/assets/{assetId}/download-url` | Short-lived owned media download |
| `GET /projects/{projectId}/revisions` | Video revision history and associated transcript/review metadata |
| `POST /projects/{projectId}/revisions/{assetId}/activate` | Restore a revision and its transcript or queue recognition |
| `GET/PUT /projects/{projectId}/transcript` | Active transcript and edits that create a version |
| `GET /projects/{projectId}/transcript/versions` | Retained transcript versions |
| `POST /projects/{projectId}/transcript/retranscribe` | A new recognition job for the source |
| `GET /projects/{projectId}/transcript/segments/{segmentId}` | Individual segment |

Project deletion removes owned Firestore data and current Storage objects. Noncurrent
Storage generations follow bucket retention; a remote published YouTube video is outside
this delete pathway. See [database lifecycle](db-design.md#deletion).

## Jobs and realtime

`GET /jobs/{jobId}` reads an owned job; `POST /jobs/{jobId}/cancel` requests cancellation.
`/ws` authenticates a shared socket and subscribes/unsubscribes by project. Initial
snapshots and events drive React Query refreshes. REST remains the fetch/recovery layer.
The hub is process-local. [Events](../../contracts/events.md) and the OpenAPI WebSocket
description specify frames; Firebase Hosting does not proxy upgrades, so production
uses the direct Cloud Run socket origin.

## Review

| Under `/projects/{projectId}/analysis` | Behavior |
|---|---|
| `GET`, `POST` | List/start a pinned analysis run |
| `GET /{analysisRunId}` | Summary, dimensions, source/transcript/persona versions and cost estimate |
| `GET /{analysisRunId}/reviewers` | Reviewer status, usage, grounding and tool references |
| `GET /{analysisRunId}/findings` | Filtered/paginated actionable observations |
| `GET /{analysisRunId}/heatmap` | Five-second bins and reviewed-span coverage |
| `GET /{analysisRunId}/interest` | Relative-interest curve with compatible creator baseline |
| `PATCH /{analysisRunId}/findings/{findingId}` | Set/clear accepted, revised or dismissed creator decision |
| `GET /{analysisRunId}/findings/{findingId}/adjudication/evidence` | Owned frame/clip reference for a footage check |
| `GET /compare?baseRunId=...&targetRunId=...` | Read-only before/after alignment and issue comparison |
| `GET/POST /{analysisRunId}/rough-cut/plan` | Read-only safe cut/note preview, including creator selection |
| `POST /{analysisRunId}/rough-cut` | Render/upload an inactive revision, no STT or paid media generation |
| `GET /{analysisRunId}/rough-cut/edl` | CMX3600 edit decision list or Markdown plan |
| `GET /{analysisRunId}/reviewers/{reviewerRunId}/context/{index}` | Owned shared/requested footage download reference |

All nine current dimensions are selectable; six core dimensions are always included.
Legacy dimensions remain readable on old runs. `partial_failure` retains successful
findings with incomplete coverage. The score summarizes flagged observations, not
whole-video quality; source URLs/confidence fields are not independent verification. The
all-rubric pass feeds the editor, then footage adjudication and library enrichment run before
aggregation. Model-filtered findings remain stored. Decisions do not rewrite reviewer results;
comparison excludes dismissed advice and reports insufficient alignment/coverage as uncompared.

## Writing and creator library

Draft routes under `/projects/{projectId}/draft`: `GET/PUT` read/save the versioned
brief/blocks; `GET /context` exposes retrieved creator context; `POST /generate`,
`/assist`, `/suggest` generate writing, conversation/rewrites and inline alternatives.
This is the implemented writing chat; it is separate from planned video-project chat.

`GET /creator-library` reads the active library/projection, `POST /creator-library/index`
indexes a bounded batch, and `POST /creator-library/search` retrieves passages/thumbnails.
The optional server preset can install its owned precomputed corpus on the first read;
installation makes no model calls. Index/search obey a daily embedding call allowance.
Search explicitly reports `semantic` or `lexical` mode.

## Captions, localization and thumbnails

| Route family | Behavior |
|---|---|
| `GET /caption-presets` | Five caption style presets |
| `/projects/{projectId}/captions/renders` and child/download routes | Queue/list/read/delete rendered MP4 captions |
| `GET /localization-voices`, `/glossaries` | Voice catalog and bundled terminology/traps |
| `GET/PUT /projects/{projectId}/glossary` | Project-owned terminology |
| `/projects/{projectId}/localizations` and child/download routes | Queue/list/read/delete dubs; audio/video/caption downloads |
| `/projects/{projectId}/thumbnails` and child routes | Generate/list/read/delete concepts; revise/apply/download |
| `POST /projects/{projectId}/thumbnails/regenerate` | Regenerate selected concepts |
| `POST /projects/{projectId}/thumbnails/download` | Bundle download |

Each resource stores source/transcript references and job/output/error metadata.
Download routes issue short-lived signed URLs. New media stays under the project prefix.

## Packaging

`GET/PUT /projects/{projectId}/packaging/listing` reads/saves listing fields;
`POST .../listing/generate` queues grounded packaging.
`GET /projects/{projectId}/visual-inserts` lists source-linked suggestions;
`POST .../visual-inserts/suggest` plans up to three;
`POST .../visual-inserts/{insertId}/render` queues a chart/callout or paid illustrative
Veo insert; `DELETE` removes an insert. Paid footage requires explicit request consent
and an available project reservation. Source/transcript changes make older records stale.

## Connections, publication and calendar

`/connections` lists owned connectors; `/{platform}/oauth/start` and `/oauth/callback`
perform OAuth for YouTube and Reddit. `POST /connections/medium/connect` accepts a legacy
integration token; `POST /connections/substack/connect` accepts a session cookie. Connection
`/sync` refreshes identity; YouTube `/content`,
`/content/sync`, `/audience`, `/audience/sync` expose real channel/content/analytics flows;
`DELETE /connections/{connectionId}` revokes/removes the connection.

Publication routes under `/projects/{projectId}/publishes` queue/list/read/delete local
publish records and `/retry` resumes/retries according to worker state. The worker
uploads to YouTube and may attach a thumbnail, caption track or scheduled publish time.
`GET /schedules` reads the owner's calendar; project `/schedules` creates/lists entries,
and child `PATCH/DELETE` edits/removes them. Calendar labels beyond YouTube are planning
metadata; they do not trigger a post. `POST /projects/{projectId}/crossposts` synchronously
posts drafts to Substack/Medium/Reddit; `/crossposts/sync` updates linked Substack drafts.
Substack can schedule remotely; local background cross-post scheduling is absent.
`GET/POST /interest-calibration` reads/refreshes a channel retention baseline with a 24-hour
user cooldown and bounded Analytics reads. Publish responses include thumbnail/caption warnings.

## Internal push and future routes

`POST /internal/pubsub/video-events` processes Storage-finalized notifications after
Google OIDC verification when configured. It only accepts source-object paths and checks
owned assets; generated media does not recursively trigger recognition.

The generic `/projects/{projectId}/artifacts` and video-project chat message paths retain
`x-status: planned` in OpenAPI and have no registered product router. Automatic shorts,
account export bundles and generic artifact galleries are not
implemented API capabilities. Native FastAPI `/docs` is available only locally.
