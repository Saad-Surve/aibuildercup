# Progress — 2026-09-20 22:15 IST

Status: **Verified that account deletion removes the whole project subtree, not just the user
document and persona.**

## 1. How deletion works

`UserService.delete_account(uid)`:

1. `storage.delete_prefix("users/{uid}/")` — every object under the user prefix, which includes
   `users/{uid}/projects/{projectId}/source/...`.
2. `client.delete_document_tree("users/{uid}")` — recursive Firestore delete, which includes
   `projects/{projectId}` and its `assets`, `jobs`, and every other subcollection.

`DELETE /api/me` calls this and then `delete_identity(uid)` for the Firebase Auth account.

## 2. Live verification (real Firestore + GCS)

Seeded a throwaway user with a full subtree and a control user, then called
`UserService(get_firestore_client(), storage=get_storage_client()).delete_account(uid)`:

- Firestore docs seeded: `users/{uid}`, `projects/p1`, `projects/p1/assets/a1`,
  `projects/p1/jobs/j1`, `personaRevisions/r1`.
- Objects seeded: `users/{uid}/profile/persona.md`, `.../profile/revisions/persona-v1.md`,
  `.../projects/p1/source/a1.mp4`.
- Result: **0 remaining docs**, **0 remaining objects** for the deleted user; the control user's
  doc, sub-doc, and object were untouched. Control data cleaned up afterwards.

## 3. Unit test strengthened

`tests/test_user_service.py::test_delete_account_removes_firestore_and_storage` now seeds a project
subtree (project + asset + job + revision) and project objects, and asserts they are gone while a
second user's subtree survives.

## 4. Verification

`uv run pytest` → **101 passed**. `ruff` and `mypy` clean.

## 5. Note

Deletion is by prefix and document tree, so anything stored under `users/{uid}/` is covered
automatically — no per-resource cleanup is needed as new project subcollections or object paths are
added.
