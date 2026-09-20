# Progress — 2026-09-20 20:45 IST

Status: **account deletion now clears Cloud Storage as well as Firestore.**

## What was wrong

`UserService.delete_account` only called `delete_document_tree(user_path(uid))`. Persona files live
in the media bucket under `users/{uid}/...` and were never removed, so `DELETE /api/me` left orphaned
objects (the Firebase Auth account and Firestore data were deleted, the bucket was not).

## Fix

- `app/services/paths.py`: added `user_object_prefix(uid)` → `users/{uid}/`.
- `app/services/storage_service.py`: added `delete_prefix(prefix) -> int` to the `StorageClient`
  protocol and `GoogleStorageClient` (list blobs by prefix, `delete_blobs`, return count). The fake
  in `tests/fakes.py` implements it too.
- `app/services/user_service.py`: `UserService` now takes an optional `storage` client;
  `delete_account` deletes the user's object prefix first, then the Firestore subtree (idempotent).
- `app/dependencies.py`: `get_user_service` injects `get_storage_client()`.

The runtime SA `creator-studio-api` already has `roles/storage.objectAdmin`, so no IAM change.

## Tests

- `test_user_service.py`: deletion removes the user's objects (including revision objects) and leaves
  other users' objects; works without a storage client.
- `test_users_api.py`: `DELETE /api/me` clears the bucket via the API.
- `test_storage_paths.py`: `user_object_prefix` scoping.

`ruff`, `mypy`, `pytest` all clean (64 passed).

## Not done / next

- Project hard-delete/soft-delete object cleanup is still future work (projects have no assets yet).
- Consider a periodic sweep for orphaned `users/{uid}/` prefixes whose Firestore doc is gone.
