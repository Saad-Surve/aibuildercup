# Progress — 2026-09-22 16:45 UTC — transcript ready but UI showed nothing

After the IAM fix, a real upload (project `7ae5d0f6…`, user `34EjsqxM…`) completed:
transcript **677 words / 68 segments**, project `ready`, VTT in GCS. The UI showed "Transcript
ready" (processing card) but no transcript content.

## Diagnosis: backend is correct, frontend never fetched

- Prod Firestore has the transcript + 68 segments; `TranscriptService.get` returns them.
- Live `GET /api/projects/{id}/transcript` with a minted Firebase ID token → **200** with all
  segments. (`/projects/{id}` and `/assets` also 200.)
- Cloud Run access logs show the workspace loaded `/project` + `/assets` at 16:36:19 but **no
  `/transcript` request ever after the transcript became ready**. So the panel never fetched.

## Cause (frontend)

`TranscriptPanel` gated its polling on the `processing` prop:
`refetchInterval: (q) => q.state.data || !processing ? false : 3000`. That flag comes from the
cached project status, which can be stale after a reload/navigation (the workspace only refetched
the project when a job id was in memory). Once it was false with no transcript data, the panel
stopped and returned `null` — an empty area, no card. `ProcessingStatusCard` also kept showing
"Processing your video" with a spinner even when the project was already `ready`.

## Fix (`web/` only)

- **`transcript-panel.tsx`**: poll until data arrives regardless of `processing`
  (`refetchInterval: (q) => (q.state.data ? false : 3000)`), `refetchOnMount: "always"`, and
  always render a card (Transcribing / pending / unavailable) instead of `null`.
- **`project-workspace.tsx`**: poll the project while status is `processing`/`uploading` so it
  flips to ready even without a job id; only render `ProcessingStatusCard` while processing or
  failed (no misleading spinner after ready).

## Verified

- `bun run lint` clean, `bun run build` succeeds (10 static pages).

## Next

- **Hard-refresh the workspace** — a fresh mount fetches the transcript and should show it now,
  even before the fix is deployed.
- Commit + push `web/` (and `infra/iam.tf` from the previous note) to deploy via the workflow.
