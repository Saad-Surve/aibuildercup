# YouTube connector verified end-to-end (connect → publish)

## Outcome

The YouTube connector works end to end. The user connected their channel (after moving the OAuth
client into `habeas-codus`) and published a project; the video uploaded and YouTube is processing
it (shown as "uploading 0%" on YouTube's side, then processing — expected, not a pipeline bug).
Uploads stay **private** until the OAuth app passes YouTube's API audit.

## Path to green (all now resolved)

1. Console OAuth setup (consent screen, client, test users) — done by the user.
2. Secret versions created; deployer IAM fixed (`secretmanager.viewer`) so CI attaches them.
3. OAuth client was initially created in **"My First Project"** (`251888281276`) instead of
   `habeas-codus` (`538724167565`), so YouTube API calls were quota-attributed to a project without
   the API enabled. Fixed by enabling the APIs there and then moving the client to `habeas-codus`
   (new secret versions, redeploy → revision `creator-studio-api-00082-mcm`).
4. Connected a channel and published successfully.

## Notes / minor polish (optional)

- For a small upload the resumable `next_chunk()` returns the response immediately without a
  progress tick, so `uploadProgress` sits at 0 until the `processing` step sets it to 100. Not a
  correctness issue (the user saw it settle), but the card could show a "preparing/uploading"
  indeterminate state for small files instead of a 0% bar.
- The "Open on YouTube" link appears as soon as the upload returns (status `processing`), which is
  the right moment; YouTube's own processing then continues asynchronously.

## Security note

The user pasted a Firebase ID token (Bearer) into chat while debugging. It is short-lived (~1h) and
was not used; recommended they sign out/in to rotate. Worth reiterating in future sessions: never
paste tokens, only error text.

## Next step

Connector is complete. Pick the next build:
- Native **Bluesky / Mastodon** connectors (open APIs, no review), or
- **social-sync → BigQuery** analytics pipeline (infra provisioned, unused; makes Audience
  insights real).
