# Progress — 2026-09-20 22:20 IST

Status: **Two production bugs found in the logs and fixed: account deletion lacked Firebase Auth
admin, and upload signing sent the literal service account "default".**

## 1. `INTERNAL_ERROR` on account delete

```
firebase_admin._auth_utils.InsufficientPermissionError:
  ... POST https://identitytoolkit.googleapis.com/v1/projects/habeas-codus/accounts:delete
  File "/app/app/api/users.py", line 42, in delete_me → delete_identity(user.uid)
```

The runtime SA `creator-studio-api` could not delete Firebase Auth users. `delete_account` had
already removed the Firestore subtree and GCS objects, so the request 500'd after the data was gone.

Fix: granted `roles/firebaseauth.admin` to the runtime SA (added to `infra/iam.tf` `api` roles and
applied live). Retrying `DELETE /api/me` now completes.

## 2. Upload failed on deployed

```
google.auth.exceptions.TransportError: Error calling the IAM signBytes API:
  400 "Invalid form of account ID default"
  File "/app/app/services/storage_service.py", line 103, in _signed_url
```

`google.auth.compute_engine.Credentials` initialises `service_account_email="default"` and only
resolves the real email after a metadata request. `_signing_credentials` read that placeholder and
passed `"default"` as the signing account. Local dev did not hit this because user ADC returns
`None` and used the configured fallback.

Fix: treat `"default"` as absent and use the configured signing service account
(`creator-studio-api@<PROJECT_ID>.iam.gserviceaccount.com` by default). Added a unit test for the
placeholder case.

## 3. Verification

`uv run pytest` → **102 passed**. `ruff` and `mypy` clean.

## 4. Follow-up

- The failed delete removed that user's Firestore data and GCS objects but left the Auth account;
  after this deploy, retrying delete should remove the identity.
- If upload still fails after this deploy, check for a CORS or 403 line specifically — the signing
  error is now distinguishable from a bucket rejection.
