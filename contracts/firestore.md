# Firestore Contract

This is the persisted-data contract. [The database reference](../docs/technical-design/db-design.md)
explains current write paths and lifecycle. Planned collections are identified separately;
they do not establish implemented features.

Reviewer findings retain the existing document shape. `evidence.quote` may be empty for
an omission or an inspected visual issue; `critique_and_reasoning` explains the observation
and `suggestion` gives one concrete edit. The run's `overallScore` summarizes reported moments,
not the whole video. Reviewer `toolCalls` include shared sampled frames as well as requested
footage; shared objects live under the same project `review-context/{analysisRunId}/` prefix
and are covered by project/account deletion.

## Hierarchy

```text
users/{uid}
├── creatorImports/{bundleId}/revisions/{revisionId}
│   ├── items/{itemId}
│   ├── semanticChunks/{nodeId}
│   └── semanticQueries/{queryHash}
├── embeddingBudgets/{UTC-date}/calls/{slot}
├── connectionSecrets/{connectionId}
├── oauthStates/{stateId}
├── connections/{connectionId}
│   ├── contentItems/{videoId}
│   ├── semanticChunks/{nodeId}
│   └── semanticQueries/{queryHash}
├── personaRevisions/{revisionId}
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
    │   ├── heatmapBins/{binId}
    │   └── interest/curve
    ├── localizations/{localizationId}
    ├── glossary/main
    ├── publishes/{publishId}
    ├── schedules/{scheduleId}
    ├── packaging/{recordId}
    ├── visualInserts/{insertId}
    └── visualInsertReservations/{slotId}
```

Planned collection shapes from the broader design include connection `syncRuns`, user
`notifications`/`usagePeriods`, project `clipCandidates`, generic artifact versions,
video-chat messages, feedback, exports and audit events. Top-level `glossaries` and
`demoProfiles` also remain proposals; the current global localization corpus is bundled
JSON and demo login uses a configured Firebase UID.

## Rules

- Owned child documents carry `ownerUid`; historical user-root ownership can be verified
  by the authenticated UID path.
- Store GCS object paths, never signed URLs.
- Timestamps are Firestore Timestamps in UTC.
- Only the backend reads/writes Firestore; direct browser access is denied by rules.
- Ownership is checked in the API, not only in Firestore rules.
- Account deletion sets `users/{uid}.deletingAt`; project deletion sets the existing
  `projects/{projectId}.archivedAt` before deleting Storage objects. Ownership-checked
  child writes reject those records, so packaging workers clean up late uploads.
  These UTC markers exist only during deletion (or after a failed cleanup that can be retried);
  the final operation still removes the document trees rather than soft-deleting them.

## Job idempotency

New job IDs are the first 32 hexadecimal characters of SHA-256 over
`{ownerUid}/{projectId}/{idempotencyKey}`. The document is created atomically rather than
overwritten: concurrent requests for the same key converge on one job. Existing random
job IDs remain readable and are reused through the idempotency-key query. The job document
base fields and project deletion path are unchanged.

Transcribe jobs additionally store an internal `sttOperations` map. Its bounded keys are
`source`, `source_no_diarization`, `normalized`, and `normalized_no_diarization`. Each value
contains `submissionStarted` (boolean), `operationName` (string or null) and
`ambiguousResubmits` (integer, default 0). The worker
records the submission marker before calling STT and the returned operation name immediately
before polling. Retries and resumed jobs reuse each saved name, including failed operations;
polling failures never authorize another submission. A marker without a name (an ambiguous transport
failure or a crash before persistence) allows one resubmission, counted in
`ambiguousResubmits`, and blocks any further one. Explicitly
rejected submissions clear that marker. Only a terminal media rejection permits the normalized
audio attempt, and only a terminal diarization rejection permits the corresponding plain attempt.
Resumed jobs go directly to an already-started fallback rather than submitting the original
request again. These fields are not exposed by the public Job schema. They live under the existing job path
and are removed by project/account deletion. Requeuing a failed job preserves the map.

## User document: onboarding and research

`users/{uid}.onboarding` holds `status`, `currentStep`, `answers`, and `schemaVersion`. After
`POST /onboarding/research` the answers include `creatorLinks` (the public profile URLs the
creator gave) and a sibling `research` object records the grounding provenance:

```json
{
  "status": "in_progress",
  "currentStep": "import",
  "answers": {
    "creatorName": "Priya Sharma",
    "topics": ["finance", "career"],
    "creatorLinks": ["https://youtube.com/@priya"]
  },
  "research": {
    "model": "gemini-3.1-flash-lite",
    "sources": [{ "title": "Priya Creates", "url": "https://youtube.com/@priya" }],
    "queries": ["Priya Sharma creator finance"],
    "searchSuggestions": "<div>…</div>",
    "updatedAt": "timestamp"
  },
  "schemaVersion": 1
}
```

It all sits on the user document, so account deletion removes it with the rest of
`users/{uid}`.

## Creator folder imports

Operator-supplied creator libraries follow [creator-import.md](./creator-import.md).
`users/{uid}.activeCreatorImportId` selects one imported bundle without creating an OAuth
connection. Import documents carry `ownerUid`; original files use the user Storage prefix.
Account deletion covers both trees. The operator import command supports removing a bundle.

## Draft document

`users/{uid}/projects/{projectId}/draft/main` is the single versioned draft for a
`kind: "draft"` project: a `brief`, ordered `blocks[]`, and each block's immutable
`versions[]`. Deletes need no special handling because the document sits under the project
subtree. The project document mirrors `draftSummary` (title, preview, word/block/version
counts) for list cards. A video project based on a draft keeps `sourceDraftId` and
`sourceDraftName` (title snapshotted at link time) on its own project document —
the draft → video → upload lineage pointer. Title-only: the draft text is never
copied. Deleting the draft leaves the pointer dangling by design: clients show the
title as plain text with an unlink action. The fields sit on the project document
itself, so project / account delete covers them with no extra wiring. After each
generation the draft document also keeps `lastCreatorContext` —
the style evidence (retrieved past videos, style signals, audience profile) the writer used — read
back by `GET /projects/{id}/draft/context` for the studio's "Style evidence" panel. The document
also keeps `grounding` (the newest grounded call's `queries`, `sources`, and
`searchSuggestions`), read back with the draft for the studio's "Grounded with Google Search"
panel. It sits under the project subtree, so project / account delete covers it.
`brief.sourceProjectId` optionally names a video project whose transcript excerpt, accepted
review findings, predicted-interest peaks and persona the writer draws on (a video made from
the draft is used when none is chosen); `videoContext` records which video, and how many
findings and peaks, the last generation used. A generation that cannot use the model sets
`status: "failed"` and an actionable `error`, leaves the previous `blocks[]` untouched, and
never substitutes canned text. Saving edited blocks on a failed draft returns it to `ready`.
Posting a Substack draft/schedule from the studio records one `linkedPosts[]`
entry `{platform, connectionId, externalId, url, status, updatedAt}` on the
draft document — the two-way link the crosspost sync endpoint pushes later edits
into. Re-posting replaces the platform's entry; deleting the remote draft clears
it on the next sync attempt.

## Analysis coverage and the interest curve

`analysisRuns/{analysisRunId}/findings/{findingId}.libraryLinks` is an optional array
(currently at most one link) of `{nodeId, sourceTitle, sourceUrl?, excerpt, startMs?,
similarity, note}`. These are attributed examples **from the creator's earlier work**,
never current-video evidence, factual verification or a reason to change a score.
`startMs` is present only for timestamped earlier videos. Missing/empty means no useful
library example; historical findings remain readable. Only indexed text passages from
other sources qualify; lexical fallback scores are never stored as cosine similarity.
The post-review step updates only `libraryLinks`, preserving concurrent decisions and
adjudications, and skips dismissed/rejected stored findings. Its embedding reservations
use the existing daily per-user slots/query cache; embedding estimates and selection-call
token usage are included in the run's `costEstimateUsd`. A failure never fails analysis.
Links are snapshots inside the project tree and follow project/account deletion.

`analysisRuns/{analysisRunId}.coverage` is written when a run finishes: an ordered list of
`{dimension, startMs, endMs}` spans each reviewer actually read (chunks that failed are
left out). Heatmap bins exist only where a finding exists; time inside a covered span with
no bin was reviewed and had nothing to flag. Runs created before this field have none.

`analysisRuns/{analysisRunId}/interest/curve` is one document holding the predicted
relative-interest curve (`InterestCurve` in `openapi.yaml`, plus `ownerUid`): one point
per five-second bin with `value` in [0, 1], drivers and signals; `peaks` and `dips` with
overlapping `findingIds`; the bundled model's `calibration`; `featureSource`; and
`costEstimateUsd`. Values rank moments within that video and are not retention. Both sit
under the project subtree, so project and account deletion remove them.

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

## Connections and OAuth tokens

`users/{uid}/connections/{connectionId}` holds one authorized external account (one YouTube
channel under one Google account, one Medium profile, one Substack publication, or one Reddit
account). It is backend-only: the browser never reads it directly, and
the API never returns tokens. The document keeps display metadata, channel stats, granted
scopes, and `tokenSecretRef` pointing at the encrypted-token document. A creator may have
several (several Gmail accounts, or several brand channels under one account); `prompt=select_account`
on the Google consent URL is what lets them pick which Gmail to connect from.
`platform` is `youtube | medium | substack | reddit`; text platforms also keep `profileUrl`.
YouTube-only fields (`uploadsPlaylistId`, `googleAccountEmail`, `subscriberCount`,
`videoCount`) are null for the others.

```json
{
  "ownerUid": "uid",
  "platform": "youtube",
  "accountType": "channel",
  "displayName": "Priya Creates",
  "externalAccountId": "UC...",
  "externalHandle": "@priyacreates",
  "googleAccountEmail": "creator@gmail.com",
  "avatarUrl": "https://...",
  "subscriberCount": 12000,
  "videoCount": 84,
  "status": "connected",
  "scopes": [".../youtube.upload"],
  "tokenSecretRef": "users/uid/connectionSecrets/connection-id",
  "tokenKeyVersion": "...",
  "lastSyncAt": "timestamp",
  "lastSyncStatus": "succeeded",
  "lastErrorCode": null,
  "createdAt": "timestamp",
  "updatedAt": "timestamp"
}
```

The encrypted token payload lives in `users/{uid}/connectionSecrets/{connectionId}` as
`{ownerUid, connectionId, platform, ciphertext, keyVersion, updatedAt}`. Both collections sit
under the user subtree, so account deletion removes them. The decrypted envelope is an
`OAuthTokenSet` for OAuth platforms (Google, Reddit) and a small credential object otherwise:
Medium stores `{"authKind": "token", "token"}` (legacy integration token), Substack stores
`{"authKind": "cookie", "sid", "subdomain"}` (browser session cookie). Server-side revoke on
delete happens only for Google; Reddit has no revoke endpoint and bearer secrets are
invalidated by deletion alone.

`users/{uid}/connections/{connectionId}/contentItems/{videoId}` holds a compact read-back copy of
one video already published on the channel: `title`, `description`, `tags`, `publishedAt`,
`durationSeconds`, `viewCount`, `likeCount`, `commentCount`, `thumbnailUrl`, `hasCustomThumbnail`,
`language`, and (for a capped number of videos) `transcript` + `transcriptLanguage`. It is written
by `POST /connections/{id}/content/sync` (the cheap uploads-playlist read plus capped
`captions.download`) and read back by the draft writer as style/RAG evidence. It lives under the
connection, so the recursive account delete covers it. The connection document also keeps
`uploadsPlaylistId`, `contentSyncedAt`, `contentItemCount`, `contentTranscriptCount`,
`audienceSyncedAt`, and the last `audienceProfile` (YouTube Analytics summary, demographics,
traffic, top videos) written by `POST /connections/{id}/audience/sync`.

`users/{uid}/oauthStates/{state}` is a single-use OAuth state record (PKCE verifier, platform,
post-login redirect path, expiry). The callback runs without Firebase auth and finds the record
by state via a collection-group query, then deletes it. Expired states are deleted on lookup.

## Creator interest calibration

`users/{uid}/connections/{connectionId}/interestCalibration/current` stores channel calibration plus
`ownerUid`, matching `CreatorInterestCalibration` in OpenAPI. `heads` is private storage:
keys `short` (<=180 seconds) and `long`, each with a 100-point `shape` at positions
0.005, 0.015, ..., 0.995, and `videos`, `views`, `creatorWeight`. Each shape averages
within-video z-scored `audienceWatchRatio` curves, with video weight
`min(1, report-period views / 1000)`. Each bucket needs three usable videos (each >=100
views, >=90 complete retention points spanning 0.01..0.99, non-flat). Creator weight is
sum(video weights) / (sum(video weights) + 10); remaining weight is the bundled generic
position head evaluated for the current video's length. Raw retention reports, titles,
video IDs and transcripts are not persisted. Counts/views include all usable videos,
even when one bucket has too few to fit. Missing, failed, disconnected and unmatched
buckets use the generic head. A new attempt replaces the previous calibration.

`users/{uid}/interestCalibrationAttempts/current` atomically reserves a calibration
attempt with `{ownerUid, connectionId, attemptedAt, nextAllowedAt}`. One transaction checks
the existing reservation and user ownership/deletion marker before replacing it, enforcing
a rolling 24-hour cooldown across channels and UTC midnight. Failures and interruptions
consume the attempt. `users/{uid}/interestCalibration/current` stores the active
`{ownerUid, connectionId}` selection; one channel is active for the whole workspace.
Calibration writes use ownership/deletion-checked transactions; the final write also
checks the connection. Read-only users are rejected in both middleware and the service.
Account recursive deletion covers these collections; disconnecting disables the retained
calibration.

Saved interest curves remain generic snapshots. `GET .../interest` substitutes the
creator baseline and reselects/relinks lift peaks/dips in memory, without writes or
Gemini calls. `baselineSource` in the response explains the chosen head, bucket, counts,
blend weight and date or generic fallback reason. Legacy curves recover their shared
prediction scale from the saved baseline and the pinned generic model. A model version
or training-date mismatch, missing baseline or degenerate scale keeps the original curve.
This adapts drop-off shape only, and has no measured retention-prediction accuracy.

## Publishes

`users/{uid}/projects/{projectId}/publishes/{publishId}` is one attempt to push a project to a
connected channel. It freezes the chosen source (source video / caption render / dub), the
resolved thumbnail version, and the caption text at create time, so a later edit cannot change
an in-flight upload. It stores the resulting `youtubeVideoId` / `youtubeUrl` on success. The
document lives under the project subtree, so the recursive project delete covers it; the YouTube
video it created is **not** deleted (that is external state) and is called out here deliberately.

`warnings` is an append-only array of `{code, message, step}` for non-fatal outcomes: the video
is up (status stays `published`/`processing`) but the thumbnail or captions did not make it.
Codes: `THUMBNAIL_FORBIDDEN` (channel lacks custom-thumbnail rights; needs phone verification),
`THUMBNAIL_MISSING` (none selected), `THUMBNAIL_FAILED`, `CAPTIONS_SKIPPED` (no caption text),
`CAPTIONS_FAILED`. `step` is `thumbnail` or `captions`. Retry resets it to `[]`.

## Schedules (content calendar)

`users/{uid}/projects/{projectId}/schedules/{scheduleId}` is one planned posting slot on the
content calendar: what will be posted, from which project, and when.

```json
{
  "ownerUid": "uid",
  "projectId": "project-id",
  "projectName": "Priya Explains Credit Scores",
  "title": "Credit scores explainer goes public",
  "notes": "Thumb B won the poll; use it.",
  "platform": "youtube",
  "scheduledAt": "timestamp",
  "status": "planned | scheduled | published | failed | cancelled",
  "statusDetail": "why a planned/failed slot is not uploading | null",
  "publishId": "publish-id | null",
  "connectionId": "connection-id | null",
  "connectionDisplayName": "Priya Creates | null",
  "createdAt": "timestamp",
  "updatedAt": "timestamp"
}
```

Two-way link with publishes: creating a publish with `publishAt` auto-creates a `scheduled`
entry pointing at it; creating a schedule with `publishId` (wiring a slot to an existing
upload) starts `scheduled`, and rescheduling a linked entry (`PATCH …/schedules/{id}`) moves the
publish's `publishAt` (the worker reads it at upload time; linking a finished publish is a
409). Status is automatic and never client-set: a YouTube slot without a `publishId` is armed
by the API (linked publish created and queued) at create time and re-armed on every read/edit
until it sticks; a slot that cannot arm stays `planned` (`failed` once its time passes) with
`statusDetail` naming the blocker. A publish that finishes flips its linked entries to
`published`, one that fails flips them to `failed`. Deleting a slot also deletes a linked
upload that has not reached YouTube yet (queued job cancelled); deleting a publish detaches
its slots back to `planned`/`failed`. The month view reads across projects by fanning out
over the project list (no collection-group index needed).
The documents sit under the project subtree, so project / account delete covers them.

### Creator semantic library

The flag-selected prepared folder revision or latest synced connected channel is the retrieval scope.
`semanticChunks/{hash}` lives beneath its revision or connection document. Each document
contains `ownerUid`, `model`, `dimensions`, `promptVersion`, a normalized `vector`, and
`createdAt`. Hashes include item identity, content/image fingerprint, model, dimensions,
and chunking/prompt version. Only hashes regenerated from current source material are read;
stale documents are excluded, then pruned during explicit indexing. No vectors leave the API.

`users/{uid}/embeddingBudgets/{UTC-date}/calls/{slot}` atomically reserves one of 200 daily
calls before any embedding request (including search and failures). Query vectors are cached
under the source's `semanticQueries/{hash}` (bounded to 100 per source). Indexing makes at
most 16 calls per request. GET library is model-free. Search/index POST respect read-only
account enforcement. All content is bounded to 300 nodes, six passages per item, and ten
thumbnail images; omitted passages are counted. Thumbnails use supplied Storage objects or
allowlisted YouTube image hosts only. No full-video embedding or new scraping is implicit.

Import removal deletes its revision indices with the bundle tree. Disconnect now recursively
deletes the connection tree (including content, vectors and query cache). Account deletion
recursively deletes budgets, all imports/connections, and supplied Storage originals. Removing
a source does not erase already generated project evidence; project/account deletion does.

Embedding cache writes transactionally require the owned source and user to still exist.
Daily call-slot reservations use the same user-existence guard with create-only semantics;
a removed source/account cannot be resurrected by an in-flight embedding response.

### Backend preset and semantic relationships

`users/{uid}.creatorPresetObject` records the immutable backend corpus version installed in
its ordinary `creatorImports` subtree. Only `CREATOR_PRESET_ENABLED` selects those imports;
flag off uses real connections. Shared ZIP originals in `creator-presets/` are operator-owned
and have an explicit preset removal CLI, while account deletion removes every user copy.
Imported items retain platform, source language, attribution, content type, fetch time and
collection method. API node `related` contains three actual cosine neighbors from other
items plus the closest other modality when absent (explicit `cross_modal` relation), computed
from current model vectors; these are not stored confidence or quality scores.

## Packaging metadata and visual inserts

- `users/{uid}/projects/{projectId}/packaging/listing`: editable title/description/tags, alternative titles, rationale, bounded creator evidence, ownerUid, sourceAssetId, transcriptId, status, jobId, updatedAt. Staleness is computed against the active source/transcript. Only ready, current listings may prefill YouTube.
- `.../packaging/insertSuggestions`: latest suggestion jobId and ownerUid.
- `.../visualInserts/{insertId}`: grounded suggestion, chart values with server-derived transcript quotes and sourceTimestampMs per value, server-derived source offsets, sourceAssetId/transcriptId, six-second duration, render status/job, aspect, storagePath, operationName, submissionStarted, paidSlot, timestamps and errors.
- Footage direction adds `visualStyle` (observed summary, palette, lighting, composition, texture, motion and setting), `generationMode`, `conditioningReason`, `styleReferenceTimestampMs`, internal `styleReferencePath`/`referenceAspectRatio`, `negativePrompt`, `directionVersion` and internal per-candidate `frameEvidence` (literal description, people/writing, image clarity and same-scene flags). A bounded local clip plus three nearby frames ground each shot. The reference JPEG lives under the insert's existing Storage prefix, even for text-only style evidence. Image-to-video uses it as the actual opening frame, not a style-reference API. Its source aspect is fixed to avoid silently cropping/recomposing the image. Text-to-video appends the saved visual recipe to editable direction. `submittedPrompt`/`submittedNegativePrompt` record the exact request before the paid submission; operation retries preserve it. Old unsubmitted footage suggestions require fresh direction; old operations still resume.
- `.../visualInsertReservations/{slot}`: immutable paid attempt reservation. Atomic create, at most configured project limit and conservative max_project_cost_usd / six-second estimate. Never refunded or deleted with individual inserts, including provider failure. Project/account recursive deletion removes reservations.
- Media: `project_object_prefix(uid, projectId) + visual-inserts/{insertId}/...`. FFmpeg charts/callouts render exact text/numbers. Veo returns inline video bytes; the worker uploads only after checking the project still exists. No new bucket, index or external persistent record. Deletion rejects running renders to prevent late output recreating an individual insert. Workers verify parent ownership and active source before persisting output.
- Generation jobs reuse `text_content` (listing), `clip` (suggestions/graphics), and `veo` (illustrative footage). Video operation names are persisted immediately; polling retries reuse that operation and never submit paid work again. Ambiguous submission failures cannot be retried automatically.

## Finding decisions and independent adjudication

`users/{uid}/projects/{projectId}/analysisRuns/{analysisRunId}/findings/{findingId}`
retains the reviewer output unchanged and adds optional fields:

- `decision`: `{status: accepted|revised|dismissed, note?: string, revisedAction?: string,
  decidedAt: timestamp, decidedBy: uid}`. Absent/null is undecided; PATCH with
  `decision:null` clears the decision. Revised requires nonblank `revisedAction` (max
  4,000 characters); optional note is max 2,000. Server stamps identity/time. All reads
  and writes check project/run/finding ownership; demo writes are rejected. Decisions
  express creator intent only and never perform an edit or change heatmap scores.
- `adjudication`: `{verdict: confirm|downgrade|reject, reason, adjustedSeverity?,
  evidence: {timestampMs, framePath, clipPath?}, checkedAt: timestamp, model, promptVersion}`.
  Only normalized high/critical findings are checked. Absent means not checked (including
  cap, unavailable footage, provider error or malformed verdict). Downgrades must be
  strictly less severe. Rejected findings remain stored but are excluded from bins,
  summary and interest-moment links. Downgraded severity is used in bins/summary; original
  score and severity remain intact for inspection. The UI hides rejections by default.
- `reconciliation`: `{clusterId, findingIds: string[], recommendation, reason, model,
  promptVersion, reconciledAt: timestamp}`. The same object on each involved finding
  links at most eight overlapping observations from different dimensions with
  different proposed actions. A separate call confirms conflict before storing
  one recommendation. This advice does not replace the creator's decision.

`analysisRuns/{analysisRunId}.adjudicator` records `{model, promptVersion, callCount,
findingCallCount, conflictCallCount, errorCount, skippedCount, costEstimateUsd,
tokenUsage: {input, output}, errors: string[]}`. Calls are serial, capped at
`MAX_ADJUDICATOR_CALLS=12` total including at most `MAX_CONFLICT_CALLS=4` cluster calls.
Provider retries are disabled for these calls. Every attempted call consumes an atomic
`adjudicatorCalls/{00..11}` reservation under the run. Each slot carries `ownerUid`,
`kind: finding|conflict`, `label`, `reservedAt`, `status: reserved|completed|failed`,
`costEstimateUsd`, optional `tokenUsage` and `error`. Conflict reservations occupy only
the last four slots (or configured smaller limit). Worker retries cannot exceed either
cap. Uncertain reservations remain consumed and counted toward spend.
Errors never fail an otherwise usable analysis. Reported token cost is included in the
run estimate; uncertain failed calls conservatively reserve the configured call estimate.

Evidence objects use the existing project-owned pattern
`{project_object_prefix}/review-context/{analysisRunId}/adjudicator-{findingId}/...`.
A lazy evidence endpoint validates ownership and the run prefix before signing the frame
or clip URL. Project/account deletion covers all documents and media. Final adjudication
writes patch only model metadata, preserving creator decisions made during review.

## Read-only analysis comparison

`GET /api/projects/{projectId}/analysis/compare?baseRunId=&targetRunId=` creates no
documents. It reads owned project/run documents, pinned assets and transcripts/segments,
findings and optional `interest/curve` documents beneath the project. Current raw finding
`decision` / `adjudication` dictionaries are read defensively: dismissed and rejected
findings are excluded; accepted/revised base findings form the accepted-fix denominator.
A valid downgrade's adjustedSeverity is used when rebuilding bins.

A directly related target asset's `roughCut` follows the Phase 2 interface:
`sourceAssetId`, `analysisRunId`, `findingIds`, ordered `keptSegments` with
`sourceStartMs`, `sourceEndMs`, `outputStartMs`, `removedSpans` on the source timeline,
and `durationMsBefore` / `durationMsAfter`. The comparison requires sourceAssetId to
match the base run asset. Kept output is contiguous, at original speed, and non-overlapping;
removed spans are derived from the complement of kept segments (metadata is not proof
that an issue is fixed). Other run pairs fall back to transcript alignment.

Normalized Unicode tokens are aligned with difflib, retaining matching blocks of at
least three tokens. Token times interpolate within persisted transcript segments.
Confidence is retained matches divided by the shorter transcript's token count; at
least six matching tokens and 0.55 confidence are required. Each retained word gives
a piecewise linear time segment, so the map never interpolates across segment gaps.
Unmatched target footage stays visible on its own timeline; unmatched source words
never prove removal. Low confidence, empty speech,
or over 8,000 tokens preserve separate timelines and mark both sets of findings uncompared.
Bounds: 2,000 findings per run and 20,000 segments; overflow fails explicitly.

Counts use unique native five-second windows across dimensions with the worst
critical/high/medium severity per window, so mapped fragments cannot inflate counts.
Matching is deterministic, same dimension, within 5 s of the base span mapped to target
time (nearest first). A target observation may preserve several nearby base findings;
consuming a match cannot imply another issue was fixed. Positive Keep observations
cannot match issues. Full rough-cut removal resolves a finding; otherwise no match
resolves only when the target reviewer covered the mapped span. Partial
runs without coverage cannot imply resolution. Interest summaries describe duration-
weighted distance above each run's own normalized baseline, not retention improvement
or calibrated quality. `newIssuesCount` excludes positive Keep observations while
`newFindingsCount` includes them. No new storage, index, deletion path, paid call or worker is needed.

## Rough-cut previews

`assets/{assetId}` is a ready `source_video` revision with optional `roughCut`:
`{sourceAssetId, analysisRunId, findingIds, keptSegments: [{sourceStartMs, sourceEndMs,
outputStartMs}], removedSpans: [{startMs, endMs, findingId, findingIds}],
durationMsBefore, durationMsAfter, insertIds?}`. `roughCutPlan` additionally snapshots findings with
`action` (`decision.revisedAction` for revised decisions, otherwise stored `suggestion`),
`label`, `labelReason`, `skippedReason`. Merged spans
retain all contributor IDs. The creator explicitly activates via the revision endpoint.

Jobs use type `rough_cut`, `input: {assetId, transcriptId, plan}` (cached deterministic
labels plus creator overrides), and `output: {assetId, transcriptId, artifactIds, storagePaths}`.
Media and derived JSON/SRT/VTT live exclusively below
`users/{uid}/projects/{projectId}/rough-cuts/{assetId}/`. This avoids source-finalized STT
and keeps exports/captions isolated from the active transcript. The derived transcript is
a normal owned transcript with sourceAssetId pointing at the new revision. It never
changes activeTranscriptId. AnalysisRequest.assetId pins that revision's ready transcript
without activation. Discard refuses active cuts, running reviews and dependent previews,
deletes related review/transcript document trees, review-context media and the cut storage
prefix (noncurrent generations expire
under bucket lifecycle). Project/account recursive deletion already covers these paths.

Only accepted/revised decisions are eligible, read defensively before the findings-loop
merge. No ambiguous actions are automatically removed. Bounds: 200 selected findings,
120 ms silence padding without splitting adjacent speech, >=500 ms cuts, <=40% per merged span;
word boundaries when available, otherwise complete segment boundaries. No STT or paid model calls.
Optional `plan.insertIds` (at most eight) selects owned ready packaging inserts pinned to
the same source/transcript. `plan.inserts` caches headline, skippedReason and placements
`{insertStartMs, outputStartMs, outputEndMs}` through kept footage. The worker revalidates
each selected insert and overlays its existing video without using its audio or changing
timeline duration. No insert is generated. `GET assets/{assetId}/captions` reads the latest
ready owned transcript as WebVTT for comparison players without activating the revision.

## Editorial consolidation

After reviewer normalisation and before adjudication, the bounded `editor-v6` pass adds
`findings/{findingId}.editorial`: `{verdict: keep|merge|drop, reason, mergedInto?,
adjustedSeverity?, factualStatus: verified|unverified|not_applicable, sources: object[],
checkedAt, model, promptVersion}`. Original reviewer output is never rewritten.
Merge targets must be kept issue findings in the same window, with no chains/cycles;
the target's `corroboratedBy: string[]` credits original merged finding IDs.
Drops/merges remain retrievable, hidden by default in the review panel, and excluded from
bins, summary, interest links, comparison, library enrichment and downstream writing context.
Each member grade can only be lowered; the kept representative carries the highest
justified cluster grade. Aggregation then honors adjudicator downgrades. Unverified factual
objections cannot retain high/critical severity.

`analysisRuns/{runId}.editor` stores `{model, promptVersion, callCount, errorCount,
skippedCount, keptCount, mergedCount, droppedCount, costEstimateUsd, tokenUsage,
searchQueries: string[], searchSuggestions: string, errors: string[]}`. `MODEL_EDITOR` falls back to `MODEL_REVIEWER`;
optional editor input/output prices fall back to reviewer prices. Short videos use one call;
time windows use at most `MAX_EDITOR_CALLS=3`. Each one-attempt call requires a conservative
budget allowance and an atomic `editorCalls/{00..02}` reservation (`ownerUid`, `label`,
`reservedAt`, `status`, `costEstimateUsd`, optional `tokenUsage`, `error`). Uncertain slots
remain consumed across worker retries. Errors, oversized inputs and exhausted budget leave
findings unedited and never fail the run. Search is enabled with Truth findings when configured;
returned grounding sources are retained separately from reviewer citations. Search query
charges are not included in token estimates. All documents are under the owned project tree
and covered by recursive project/account deletion. Reads/writes check ownership.

## Rubric reviewer and editor v6

Each analysis run may store `rubric: {model, promptVersion, callCount, findingCount,
skippedCount, costEstimateUsd, tokenUsage: {input, output}, searchQueries,
searchSuggestions, errors}`. The coordinator makes at most one all-nine-rubrics call
per run, using the reviewer model. `rubricCalls/00` has `ownerUid`, `reservedAt`,
`status`, `costEstimateUsd`, optional `tokenUsage` and `error`; atomic creation prevents
retrying an ambiguous paid call. Reserved/failed allowance counts toward project spend.
The existing project/account recursive deletion covers this subcollection.
Rubric observations use the existing finding shape with `reviewerRunId: "rubric"`;
they are stored alongside specialists before editing. No tenth heatmap dimension.
Oversize whole-transcript input (>100k characters) skips this pass rather than truncating it.

Editor v6 merges by underlying problem/edit, across reviewer lenses. Originals remain
immutable; `corroboratedBy` still references merged original finding IDs. The UI resolves
these to named reviewer dimensions (or "All-rubric review"), not independent expert votes.
A kept representative retains its original quote, span and dimension; choose the best
evidence. The model chooses a root problem dimension, and code selects an existing merged
member in that dimension with a quote and focused span when available, without relabelling
any observation. `editorial.adjustedSeverity` is the highest justified grade across the cluster,
bounded by the members' original grades after editor reductions. It may exceed the
representative's grade; footage adjudication may subsequently downgrade it.
Rubric findings are evaluated on the same evidence standard as specialist findings; agreement
is a keep signal, not a guarantee. Representatives use the dimension owning the underlying
problem rather than its side effects. Omission evidence can be distributed across the video
and have an empty quote; incomplete windows cannot disprove it.
