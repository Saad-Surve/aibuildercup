# Firestore Contract

The full schema is in `../docs/technical-design/db-design.md`. This file is the quick reference
the code must match.

## Hierarchy

```text
users/{uid}
├── creatorImports/{bundleId}/revisions/{revisionId}/items/{itemId}
├── connections/{connectionId}
│   └── syncRuns/{syncRunId}
├── personaRevisions/{revisionId}
├── notifications/{notificationId}
├── usagePeriods/{periodId}
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
```

## Rules

- Every user-owned document carries `ownerUid`.
- Store GCS object paths, never signed URLs.
- Timestamps are Firestore Timestamps in UTC.
- Only the backend reads `connections`, `glossaries`, `demoProfiles`.
- Ownership is checked in the API, not only in Firestore rules.

## Job idempotency

New job IDs are the first 32 hexadecimal characters of SHA-256 over
`{ownerUid}/{projectId}/{idempotencyKey}`. The document is created atomically rather than
overwritten: concurrent requests for the same key converge on one job. Existing random
job IDs remain readable and are reused through the idempotency-key query. The job document
shape and project deletion path are unchanged.

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
channel under one Google account). It is backend-only: the browser never reads it directly, and
the API never returns tokens. The document keeps display metadata, channel stats, granted
scopes, and `tokenSecretRef` pointing at the encrypted-token document. A creator may have
several (several Gmail accounts, or several brand channels under one account); `prompt=select_account`
on the Google consent URL is what lets them pick which Gmail to connect from.

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
under the user subtree, so account deletion removes them.

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

## Publishes

`users/{uid}/projects/{projectId}/publishes/{publishId}` is one attempt to push a project to a
connected channel. It freezes the chosen source (source video / caption render / dub), the
resolved thumbnail version, and the caption text at create time, so a later edit cannot change
an in-flight upload. It stores the resulting `youtubeVideoId` / `youtubeUrl` on success. The
document lives under the project subtree, so the recursive project delete covers it; the YouTube
video it created is **not** deleted (that is external state) and is called out here deliberately.

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
  "status": "planned | scheduled | published | cancelled",
  "publishId": "publish-id | null",
  "connectionId": "connection-id | null",
  "connectionDisplayName": "Priya Creates | null",
  "createdAt": "timestamp",
  "updatedAt": "timestamp"
}
```

Two-way link with publishes: creating a publish with `publishAt` auto-creates a `scheduled`
entry pointing at it; creating a schedule with `publishId` (wiring a slot to an existing
upload) and rescheduling a linked entry (`PATCH …/schedules/{id}`) both move the
publish's `publishAt` (the worker reads it at upload time; linking a finished publish is a
409); a publish that finishes flips its linked entries to `published`. The month view reads
across projects by fanning out over the project list (no collection-group index needed).
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
