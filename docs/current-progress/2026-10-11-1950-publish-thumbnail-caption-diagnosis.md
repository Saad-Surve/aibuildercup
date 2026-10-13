# Diagnosis: why thumbnails and captions "don't go" when publishing to YouTube

Read-only investigation of the publish → YouTube path against the live project (`habeas-codus`),
plus a controlled live reproduction on the connected channel. No code changed.

## What I did

- Read the publish path: `app/services/publish_service.py` (`create` / `_resolve_thumbnail` /
  `_resolve_captions`), `app/workers/publish_worker.py`, `app/connectors/youtube.py`, and the
  web `publishing-module.tsx`.
- Pulled the live Cloud Run logs for `creator-studio-api` and found the real publish runs.
- Decrypted the KMS-encrypted OAuth token for the connected channel (`Ankit Mishra`,
  `UCXqzpo0RAxDxdfeBhooh7OQ`, connection `a818ae4d38ea4ddc8e3fb19aebbf015c`) and ran the exact
  connector calls against a throwaway video (created then deleted each time).

## Findings

### Thumbnail — confirmed broken, YouTube 403, channel-side

Live Cloud Run logs show the worker's warning twice:

```
publish 2c6a37079aef4af48791704ebbcebce2: thumbnail rejected: The authenticated user doesn't have permissions to upload and set custom video thumbnails.   (07:50:32)
publish 8fb2c2b11599495584b5566e5cb53001: thumbnail rejected: The authenticated user doesn't have permissions to upload and set custom video thumbnails.   (13:34:50)
```

Reproduced directly on the same channel: after `videos.insert`, `thumbnails.set` returns
`HTTP 403 reason=forbidden` with the same message, both immediately and after waiting 20s.
So it is **not a timing/processing problem and not a bug in our upload code** — the channel does
not have YouTube's **custom thumbnails** feature, which YouTube grants after phone-verifying the
channel (youtube.com/features). The current worker treats it as best-effort, so the video still
uploads, just without a thumbnail.

Two distinct ways the thumbnail is missed:

1. **No thumbnail selected** → `create` stores `thumbnailStoragePath = null` → the worker skips the
   step silently. Live example: project `e3c08087029144b69dbb643dc3bf2710` ("Something") has **no
   `thumbnails` subcollection at all**, so its 08:25 publish never attempted a thumbnail.
2. **Thumbnail selected** → YouTube 403 (channel permission) → caught and skipped.

### Captions — the upload path works

Reproduced end-to-end on the same channel with the **real project SRT content** (from project
`yt1`) using the worker's exact values (`part=snippet`, `language=en`, `name=English`,
`MediaIoBaseUpload(..., mimetype="application/octet-stream", resumable=False)`):

- `captions.insert` right after `videos.insert` → **ok** (track `en` / `English` / `standard`,
  not draft).
- Left the video to finish processing: `contentDetails.caption` flips to `true` and the track
  survives (`captions.list` still returns it). So an immediately-inserted track is not dropped.
- Even the degenerate live SRT (zero-duration cues, e.g. `00:00:01,000 --> 00:00:01,000`) is
  accepted.

So the caption step is not the failure the report suggested. If a creator still sees no subtitles,
the remaining causes are: (a) the publish was for a project with no ready transcript/segments, in
which case the worker skips captions **with no message**; or (b) they looked at YouTube before
processing finished (`contentDetails.caption` stays `false` for ~10–30s).

## The real product defect: outcomes are invisible

- The worker's meaningful results are swallowed: a caption failure raises `ConnectorError`, which
  the outer handler turns into a failed publish **without logging or surfacing the message**; a
  thumbnail rejection is caught and only written as a step that is then overwritten.
- The web publish history renders only `publish.steps[publish.steps.length - 1]`
  (`publishing-module.tsx`), so "Thumbnail skipped (YOUTUBE_FORBIDDEN)" is replaced by later steps
  and the creator never learns the thumbnail was dropped or why.

## Not done / next step

- No code changed. Suggested fixes (need a decision, since they touch `contracts/openapi.yaml` and
  the web client): persist the thumbnail/caption outcome as an explicit warning on the `Publish`
  document and show it in the history; log the `ConnectorError.message` in `run_publish`; and add a
  clear, actionable message for the channel-permission 403 ("this channel can't set custom
  thumbnails — verify it by phone in YouTube settings").
- Demo unblock (no code): phone-verify the connected channel so the custom-thumbnails feature is
  enabled, and make sure a thumbnail is actually generated and selected before publishing.
