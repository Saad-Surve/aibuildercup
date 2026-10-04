# Firestore Contract

The full schema is in `../docs/technical-design/db-design.md`. This file is the quick reference
the code must match.

## Hierarchy

```text
users/{uid}
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

## Draft document

`users/{uid}/projects/{projectId}/draft/main` is the single versioned draft for a
`kind: "draft"` project: a `brief`, ordered `blocks[]`, and each block's immutable
`versions[]`. Deletes need no special handling because the document sits under the project
subtree. The project document mirrors `draftSummary` (title, preview, word/block/version
counts) for list cards. After each generation the draft document also keeps `lastCreatorContext` —
the style evidence (retrieved past videos, style signals, audience profile) the writer used — read
back by `GET /projects/{id}/draft/context` for the studio's "Style evidence" panel.

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

**Demo seed.** `POST /seed/youtube-content` writes a synthetic connection at
`users/{uid}/connections/seed-<slug>` (with `seedSource`, `seedLicense`, `seedAttribution`, and a
fresh `contentSyncedAt`) plus its `contentItems`, loaded from `seed/youtube/<slug>.json` in the
media bucket. It is a public CC-BY channel (see `fixtures/seed/youtube/ATTRIBUTION.md`), so a fresh
account has creator content for the style/RAG, transcript, and thumbnail-reference features. A seed
connection has no OAuth tokens, so the sync endpoints reject it (`CONNECTION_IS_SEED`).

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
