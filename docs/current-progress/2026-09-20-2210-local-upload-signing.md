# Progress — 2026-09-20 22:10 IST

Status: **Local uploads now sign too. Plain user ADC has no service-account identity, so the client
falls back to the runtime SA via IAM signBlob.**

## 1. Why local still failed after the Cloud Run fix

`google.auth.default()` on a developer machine returns `google.oauth2.credentials.Credentials` — a
user token with no private key and no `service_account_email`. The Cloud Run fix only worked because
compute-engine credentials carry the SA email. Locally the client hit the "no signing credentials"
branch.

## 2. Fix

- `app/services/storage_service.py`: `GoogleStorageClient` takes a `signing_service_account`. When
  the ambient credentials have no identity, it uses that email with the current access token, so the
  SDK signs through IAM `signBlob`. Service-account keys and impersonated credentials still sign
  directly.
- `app/config.py`: `storage_signing_service_account` (defaults to
  `creator-studio-api@<PROJECT_ID>.iam.gserviceaccount.com` via `get_storage_client`).
- `.env.example`: documents `STORAGE_SIGNING_SERVICE_ACCOUNT`.
- `tests/test_storage_signing.py`: four branches now — signing key, ambient SA, configured SA
  fallback, and no identity at all.

## 3. IAM

`aibuildercup@gmail.com` was granted `roles/iam.serviceAccountTokenCreator` on the `creator-studio-api`
service account for local development. (IAM propagation took ~1–2 minutes before signBlob worked.)

## 4. Verified locally

```
signed URL generated locally (IAM signBlob via user ADC)
PUT -> 200
object exists: True
```

`uv run pytest` → **101 passed**. `ruff` and `mypy` clean.

## 5. Notes

- Engineers doing local real uploads need the same tokenCreator grant on the runtime SA; that is not
  yet in `infra/` for the engineer list. Add an SA-level binding if more people need it.
- `MOCK_MODE=on` remains the zero-setup option (MSW handles the upload in the browser).
