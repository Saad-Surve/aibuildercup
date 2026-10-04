# Gotcha: OAuth client lives in the wrong GCP project

## Symptom

Connecting a YouTube channel failed with:

> YouTube Data API v3 has not been used in project **251888281276** before or it is disabled.

## Cause

The OAuth client (and consent screen) were created in **"My First Project"**
(`project-677efd98-d2b3-4288-836`, project number `251888281276`), not in `habeas-codus`
(project number `538724167565`). The console's project selector was on the default project when
the client was created.

YouTube Data API v3 calls made with a user's OAuth token are quota/billing-attributed to the
project that **owns the OAuth client**, not the project that runs the API. `habeas-codus` has the
YouTube APIs enabled, but `251888281276` did not (Analytics was missing; Data API was listed as
enabled but the call was rejected, consistent with a not-yet-propagated enablement).

## Fix applied

Enabled both APIs in the client's project:

```bash
gcloud services enable youtube.googleapis.com youtubeanalytics.googleapis.com \
  --project=251888281276
```

Confirmed enabled: `youtube.googleapis.com` (YouTube Data API v3) and
`youtubeanalytics.googleapis.com` (YouTube Analytics API).

## Decision / follow-up

- The connector works with the client in `251888281276`. For a hackathon this is acceptable.
- **Cleaner option (recommended before the final demo):** recreate the OAuth consent screen +
  client inside `habeas-codus` so quota, consent, and the app all live in one project. That needs:
  redo consent screen + client there, update `backend/.env`, add new versions of
  `youtube-oauth-client-id`/`-secret`, and redeploy. Redirect URIs are unchanged.
- Diagnostic: a Google OAuth client ID is prefixed with its project number, so
  `GOOGLE_OAUTH_CLIENT_ID` starting with `251888281276-` confirms the wrong-project placement.

## Not done / next step

- Retry the browser connect flow after propagation (~a few minutes).
