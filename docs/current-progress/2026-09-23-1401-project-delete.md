# Progress — 2026-09-23 14:01 UTC — project delete now really deletes

`DELETE /projects/{projectId}` was a **soft delete**: it only set `status=archived`/`archivedAt`.
Every subcollection (assets, jobs, transcripts + segments) and every Cloud Storage object (source
video, canonical transcript JSON, VTT/SRT) stayed forever. An audit of prod confirmed it: user
`34EjsqxM…` had **7 project docs, 6 archived, all with full subcollections and GCS objects** still
present. The UI copy already promised "permanently deleted", so the backend was lying.

## Root cause

The narrow clients already supported real deletion — `FirestoreClient.delete_document_tree`
(Firestore `recursive_delete`) and `StorageClient.delete_prefix` — and **account deletion already
used them** (`user_service.delete_account`). Project deletion just never called them.

## Fix

- `ProjectService.delete()` (`app/services/project_service.py`) replaces `soft_delete`:
  `storage.delete_prefix(project_object_prefix(uid, project_id))` then
  `client.delete_document_tree(project_path(uid, project_id))`. It checks ownership directly (not
  `_require_owned`), so **legacy archived projects are deletable** too.
- `ProjectService` now takes an optional `storage`; `get_project_service()` passes the real client.
- `DELETE /projects/{projectId}` calls `delete`.
- Because deletion is by **prefix** (GCS) and **recursive tree** (Firestore), any future
  project-scoped data — analysis, artifacts, clips, localized media, new subcollections — is
  covered without touching the delete path again. This directly addresses "new features aren't
  covered by delete".

## Docs

- `contracts/openapi.yaml` + `api-design.md`: DELETE project is now "Delete the project and all of
  its data", not "soft-delete and queue object deletion".

## Verified

- New tests: delete removes the Firestore tree (incl. nested segments) + all GCS objects, rejects
  other owners, and cleans legacy archived projects. `pytest` **151 passed**, ruff + mypy clean.

## Not done / next

- **Existing orphans still in prod** (6 archived projects for `34EjsqxM…`, 1 for `81McqIGH…`, each
  with a source video and some with transcript JSON + captions). They are hidden from the app (the
  list filters `archivedAt`) but still consume storage. They can now be removed by re-issuing
  DELETE for each project id, or with a one-off cleanup script — **needs explicit go-ahead** since
  it deletes prod data.
- The endpoint still returns 202 for a now-synchronous delete; could become 204.
- Consider a Cloud Storage lifecycle rule as a backstop for abandoned prefixes.
