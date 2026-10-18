# Resonance persistence reference

Firestore is the control plane; Cloud Storage holds large media and source artifacts.
Current channel analytics and creator interest calibration also live in Firestore. BigQuery
datasets are absent from current Terraform; the runtime does not depend on them. [Contracts](../../contracts/firestore.md),
Pydantic schemas and service write paths define fields; the tree below shows implemented roles.

## Conventions

User identity is the Firebase UID. Owned child records carry `ownerUid`; all paths are
validated and checked against the requester. The historical user root can identify its
owner by its UID path. Firestore timestamps use UTC. Persist Storage object paths, not
expiring signed URLs. UUID/content hashes identify records; jobs use deterministic
owner/project/idempotency hashes and atomic creation.

## User and project hierarchy

```text
users/{uid}
├── personaRevisions/{revisionId}
├── oauthStates/{stateId}
├── connectionSecrets/{connectionId}
├── connections/{connectionId}
│   ├── interestCalibration/current
│   ├── contentItems/{videoId}
│   ├── semanticChunks/{nodeId}
│   └── semanticQueries/{queryHash}
├── creatorImports/{bundleId}
│   └── revisions/{revisionId}
│       ├── items/{itemId}
│       ├── semanticChunks/{nodeId}
│       └── semanticQueries/{queryHash}
├── interestCalibration/current
├── interestCalibrationAttempts/current
├── embeddingBudgets/{UTC-date}/calls/{slot}
└── projects/{projectId}
    ├── assets/{assetId}
    ├── jobs/{jobId}/events/{eventId}
    ├── transcripts/{transcriptId}/segments/{segmentId}
    ├── analysisRuns/{analysisRunId}
    │   ├── reviewers/{reviewerRunId}
    │   ├── findings/{findingId}
    │   ├── heatmapBins/{binId}
    │   ├── rubricCalls/00
    │   ├── editorCalls/{00..02}
    │   ├── adjudicatorCalls/{00..11}
    │   └── interest/curve
    ├── draft/main
    ├── captionRenders/{captionRenderId}
    ├── thumbnailConcepts/{thumbnailId}
    ├── localizations/{localizationId}
    ├── glossary/main
    ├── publishes/{publishId}
    ├── schedules/{scheduleId}
    ├── packaging/{recordId}
    ├── visualInserts/{insertId}
    └── visualInsertReservations/{slotId}
```

Exact helpers, including fixed record IDs and the connection secret layout, are in
`backend/app/services/paths.py`, `creator_import_service.py`, `creator_library_service.py`
and `packaging_service.py`. Not every designed collection in the original quick contract
has a writer: generic artifacts/clip candidates, video chat, feedback, exports, audit events,
platform glossaries and demo profiles remain broader proposals.

## User and connector records

The user root stores onboarding answers/progress/research, current persona metadata,
preferences and avatar. Persona Markdown/revisions live under owned Storage paths.
Connections store channel identity/status and sync references. OAuth access/refresh
secrets are encrypted with KMS in production; OAuth states expire and carry the PKCE
flow data. Content items retain titles/descriptions, selected captions, metrics and style
metadata. Audience aggregates are connector-owned records, not supplied persona facts.

Creator imports keep immutable validated revisions, originals, item attribution/language/
collection method and an active-library reference. Semantic chunks contain owner/model/
dimensions/prompt version/vector/time; their IDs bind to source content. Queries cache a
normalized vector/time under the active source. Daily embedding slots atomically bound
interactive calls. Preset installation rechecks ownership across bounded write batches.

## Projects, assets and jobs

Projects distinguish `video` and `draft`, keep source/active-transcript/current-analysis
references, processing metadata and denormalized card summaries. A linked draft is a
script reference, not copied automatically into the video's transcript. Assets retain
Storage paths and source media metadata across revisions. Edit plans are computed from current
accepted/revised findings and request labels; exports persist no assets, jobs or transcripts.
Legacy assets retain `roughCut` base source/run and cut mapping for exact comparison, plus their
existing derived transcripts. Historical `rough_cut` job documents remain parseable, but no
new jobs of that type are created. Project/account deletion covers their existing prefixes.

Jobs record type, input/output, state/progress/error and idempotency key. Their event children
support progress history. Atomic creation converges duplicate upload notifications; process-local
execution locks do not supply distributed leases or upstream-operation exactly-once behavior.

## Transcripts and analysis

A transcript retains source asset, version, language, duration and export paths; child
segments carry IDs, times, text, speaker and word data. Edits/retranscription create
versions; activating an old source can restore its corresponding transcript.

An analysis run pins asset/transcript/persona versions and requested dimensions, records
chunk/reviewer IDs, model/prompt configuration, status and cost estimate. Reviewer children
retain status, token usage, grounding/source metadata and shared/requested footage references.
Findings retain dimension, span, score/severity/confidence, quote/reasoning, concrete suggestion
and citations. A blank quote is permitted for omission/inspected visual evidence.
Optional `editorial`, `corroboratedBy`, `adjudication`, `reconciliation`, `decision` and
`libraryLinks` fields keep model filtering, footage checks, creator intent and historical
examples separate from immutable reviewer evidence. Rubric/editor/adjudicator summaries and
atomic call reservations record bounds, usage and uncertain spend. Compare responses are
computed without persistent comparison documents. See the
[editorial fields](../../contracts/firestore.md#finding-decisions-and-independent-adjudication)
and [editor/rubric contract](../../contracts/firestore.md#rubric-reviewer-and-editor-v7).

Heatmap bins use deterministic dimension/start IDs, five-second spans, overlap-weighted
scores, worst severity/color and referenced finding IDs. The run summary describes reported
moments; missing bins are not invented positive scores. Editor-merged/dropped and adjudicator-
rejected findings are excluded; effective severity honors model adjustments. Dismissal does
not rewrite stored bins, but comparison excludes dismissed findings. Partial errors stay visible.
The saved interest curve retains its generic baseline; compatible creator calibration is
applied on read. Calibration heads/pointer/cooldown are user/connection-owned, covered by deletion.

## Drafts and generated media

`draft/main` stores the brief, blocks with immutable versions/active pointers, chat messages,
grounding, last selected creator context, selected video context and linked cross-post metadata. Project `draftSummary` supplies list-card
counts/preview. Current state is versioned, but final prose quality still needs evaluation.

Caption renders keep source/transcript, style, job/status/progress and MP4 output metadata.
Thumbnail concepts retain the plan, critique, image versions and applied packaging promise.
Localizations snapshot corpus/project-glossary terms/versions, speaker voices, language,
source/transcript and caption/audio/video paths. Project glossary changes increment their
version; an in-flight localization uses its saved snapshot.

Publish records store connection, source/output selection, listing, job/progress, optional
captions/thumbnail/schedule, nonfatal attachment warnings and external YouTube identifiers. Calendar entries are project-owned
and can link to a publication. Packaging records/visual ideas retain source/transcript and
evidence; changed references make them stale. Paid visual insert reservations persist even
if a render is deleted or uncertain, preventing deletion from resetting the allowance.

## Storage

Project outputs use `users/{uid}/projects/{projectId}/...`: source media, transcript exports,
caption MP4, thumbnails/references, localized outputs, review context and visual inserts.
Persona/import originals use their matching user prefixes. Paths come from validated helpers;
short-lived download URLs are minted on read.

Shared `creator-presets/{bundleId}/{archiveHash}/bundle.zip` is an immutable operator artifact
outside user prefixes. It is deliberately shared and separately removed by the operator.
The runtime localization corpus is bundled JSON in the container, not user-owned media.

## Indexes, reads and updates

Firestore indexes support project ordering and contract-defined queries. Bulk writes use
up to 400 documents per RPC; billed operations are unchanged. Ownership-safe transactional
child writes are used where reservations/installation need create-only behavior. Semantic
retrieval reads bounded vectors into Python; large-library managed indexing is future work.
Calendar aggregation currently reads across owned projects rather than a dedicated global
schedule index.

## Security

Firestore client rules deny direct browser data access. The backend verifies Firebase
identity and checks owned documents. No secret is a public client field. Shared demo
mutations are rejected by middleware. Signed URLs and Storage object references follow
ownership/expiry checks; explicit user prefixes are essential to lifecycle coverage.

## Deletion

`ProjectService.delete` recursively removes the owned Firestore subtree and current Storage
objects under the project prefix. `UserService.delete_account` revokes OAuth grants
best-effort, removes current user-prefix objects and the Firestore user tree. These are
real deletes, not archive flags. User-owned creator imports, vector/query caches and
embedding budgets are covered by account deletion.

Deletion first marks project `archivedAt` or user `deletingAt`; ownership-checked child
writes reject these markers. Packaging workers recheck ownership after uploading and
clean up abandoned output. These guards reduce races; they are not a measured guarantee
that every external operation stops immediately.

**Storage generation boundary:** `delete_prefix` currently lists/deletes live blobs; versioned
media/corpus buckets can retain noncurrent generations, with a default 30-day lifecycle.
Explicitly purging all generations is not implemented. A Storage retention claim must reflect
that boundary. Shared presets survive account deletion and need explicit operator removal.
Remote YouTube publications also survive deletion of local project/publish records.
