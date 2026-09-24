# Progress — 2026-09-24 15:41 UTC — small follow-ups (DELETE 204, lifecycle, SSE)

Did the small pending items only. No work started on the big stuff (multi-reviewer
analysis/heatmap, artifacts, chat, YouTube/BigQuery, localization/shorts/Veo) — those stay
`x-status: planned` in `contracts/openapi.yaml`.

## What changed

**DELETE /projects/{id} is now 204 (was 202).** The delete is synchronous
(`ProjectService.delete` removes the GCS prefix + Firestore tree before returning), so 202
was lying. Contract-first:
- `contracts/openapi.yaml`: DELETE project → `204 Deleted, no content` (was `202 Accepted`).
- `backend/app/api/projects.py`: returns bare 204.
- `backend/tests/test_projects_api.py`: asserts 204 + empty body.
- `web/src/lib/projects.ts`: `deleteProject()` returns `Promise<void>`
  (`apiFetch` already maps 204 → `undefined`). Sole caller
  (`delete-project-dialog.tsx`) just awaits it, unchanged behaviour.

**Storage lifecycle backstop (`infra/`).**
- New `var.noncurrent_retention_days` (default 30).
- `storage.tf`: versioned buckets (`media`, `corpus`) delete noncurrent versions after N
  days (`days_since_noncurrent_time` + `with_state = ARCHIVED`). Live objects untouched —
  this only stops version pile-up. Deliberately no age-based delete on current objects:
  that would risk live user data and needs a product decision. `temp` 7-day rule unchanged.

**Web wired to SSE `GET /projects/{id}/events`.**
- `web/src/lib/projects.ts`: new `subscribeToProjectEvents()` — `fetch` + reader (plain
  `EventSource` can't send the Firebase `Authorization` header), parses `job.progress`
  frames, silent failures. Added `ProjectProgressEvent` type.
- `project-workspace.tsx`: subscribes while status is `processing`/`uploading`; events
  update the `["project"]` cache (and `["job"]` cache + `jobId` when a job rides along).
  Existing polling stays as fallback; existing `ready` → invalidate transcript effect fires
  off the event-driven cache update, so no reload/refocus needed.

## Verified

- Backend: `pytest` **151 passed**, `ruff` clean, `mypy` clean.
- Web: `bun run lint` + `bun run build` pass.
- Infra: `terraform validate` OK (not applied).
- Uncommitted, per repo rule.

## Not done / next

- `terraform apply` for the above (incl. earlier `api_url` push-path work) — not applied here.
- Prod orphans from the old soft-delete era still in place — needs explicit go-ahead.
- Big stuff deferred: analysis/heatmap, artifacts, chat, transcript regenerate, account
  export, seed script, separate worker containers.
