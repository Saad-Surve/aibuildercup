# Creator folder import contract

An operator command imports locally supplied creator material into the live Firestore/Storage
library. It uses Application Default Credentials; it exposes no HTTP endpoint, login bypass,
OAuth token, or publishing connection. Default execution validates locally without cloud calls.

`manifest.json` (version 1) contains:

```json
{
  "schemaVersion": 1,
  "bundleId": "demo-creator",
  "creator": {
    "name": "Demo Creator",
    "bio": "Short creator biography",
    "language": "en",
    "links": ["https://example.com"]
  },
  "items": [
    {
      "id": "video-01",
      "kind": "video",
      "title": "A video title",
      "description": "Optional description",
      "tags": ["technology"],
      "textFile": "transcripts/video-01.srt",
      "thumbnailFile": "thumbnails/video-01.jpg",
      "mediaFile": "videos/video-01.mp4",
      "url": "https://example.com/video-01",
      "language": "en",
      "publishedAt": "2026-10-01T12:00:00Z"
    },
    {
      "id": "article-01",
      "kind": "article",
      "title": "A written piece",
      "textFile": "writing/article-01.md"
    }
  ]
}
```

`items` has 1–100 entries with unique safe ids. `kind` is `video`, `article`, or `post`.
All file fields are optional for videos, but each item needs at least one local file.
Articles/posts require `textFile`. Optional fields may be omitted. Unknown fields are rejected.
Dates require a timezone. IDs use letters, digits, `_`, `-`, and are 1–128 characters.
Links, where supplied, must use HTTP(S). No statistics are invented or required.
Videos may also include optional nonnegative `viewCount`, `likeCount`, `commentCount`,
and `durationSeconds`. Optional top-level `audience` accepts `periodDays` (1–3650),
`summary` metric/value pairs, `demographics` and `trafficSources` breakdowns
(`dimension`, `rows` of `label`/`value`). These are explicitly supplied demo data, not
reports fetched from YouTube. Omitted analytics remain absent.

Files are relative to the folder and must resolve inside it. Text accepts UTF-8 TXT/MD/SRT/VTT
(200 KiB per file), thumbnails JPEG/PNG/WebP (5 MiB), and videos MP4/MOV/WebM (1 GiB).
Total referenced input is capped at 2 GiB. Files must be regular files. Import stores supplied
originals, flattened text, and parsed timed SRT/VTT cues. It does not transcribe videos or run
research/embedding/generation models; those remain subsequent jobs.

## Storage and lifecycle

- `users/{uid}.activeCreatorImportId` explicitly selects the imported library for draft style
  and thumbnail references ahead of live connected-channel examples.
- `users/{uid}/creatorImports/{bundleId}` records `ownerUid`, `sourceType: folder_import`,
  creator metadata, `revisionId`, content hash, counts, and UTC timestamps.
- Immutable revisions live under `.../revisions/{revisionId}/items/{itemId}`. Each item records
  `ownerUid`, kind, title, description, tags, source URL, language, publication date, text,
  timed segments, content hash, and original text/thumbnail/media Storage paths.
- Objects live under `users/{uid}/creator-imports/{bundleId}/{revisionId}/...` in the existing
  media bucket. Stable content hashes select the revision; repeat imports converge on it.
- The revision and objects are uploaded before activating the bundle. No real OAuth
  connections or credentials are overwritten, created, or copied.
- Account recursive deletion and the user Storage prefix cover the import. Operator removal
  clears active selection if appropriate and deletes the bundle's complete tree/object prefix.
- Draft evidence snapshots remain project-owned history; deleting an import does not erase
  previously generated draft text, but future retrieval excludes it and stale image paths must
  not break reading draft evidence. Delete the project to remove its snapshot/history too.

## Existing draft-context API additions

`CreatorContext` gains `sourceType` (`youtube` or `folder_import`), nullable `creatorName`,
nullable `creatorBio`, and `writtenExamples[]` (`itemId`, `title`, nullable `url`, `excerpt`).
Video examples keep their existing shape. Imported libraries have null `connectionId`;
`connectionDisplayName` retains the creator name for existing consumers.
Imported thumbnail signed URLs are generated when reading context and are never persisted
in Firestore; thumbnail reference generation reads stored image bytes directly.
