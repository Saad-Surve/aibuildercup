# Progress — 2026-09-20 22:00 IST

Status: **Video upload was broken in production: the signed URL could not be signed, and the bucket
CORS did not allow the deployed origin. Both fixed and verified.**

## 1. What the data showed

Firestore had one project ("Tech review") stuck in `draft` with **two `pending` source assets** and
**no `jobs` subcollection**. The media bucket had **no `projects/` objects**. So every upload attempt
created an asset record and then died before the browser PUT.

## 2. Root cause (Cloud Run logs)

```
AttributeError: you need a private key to sign credentials. the credentials you are currently
using <class 'google.auth.compute_engine.credentials.Credentials'> just contains a token.
  File "/app/app/services/storage_service.py", line 91, in signed_upload_url
```

Cloud Run's default credentials are compute-engine credentials with no private key, so
`generate_signed_url(version="v4")` raised. `POST /upload-session` returned 500, but because
`create_upload_session` wrote the asset document *before* generating the URL, each failure left an
orphan `pending` asset. A second, independent problem: the media bucket CORS only allowed
`localhost:3000/8080`, so even a valid URL would have been blocked by the browser preflight from
`https://habeas-codus.web.app` (the `PUT` carries `Content-Type: video/mp4`, which is not a
safelisted value).

## 3. Fixes

- `app/services/storage_service.py`: `GoogleStorageClient` now signs through the IAM `signBlob` API
  when the ambient credentials cannot sign — it passes `service_account_email` + `access_token` to
  `generate_signed_url`. A signing key is still used directly when present (service-account key).
  Both `signed_upload_url` and `signed_download_url` go through one `_signed_url` helper.
- `app/services/asset_service.py`: the URL is generated *before* the asset document is written, so a
  signing failure can no longer orphan a `pending` asset.
- `infra/iam.tf`: `creator-studio-api` gets `roles/iam.serviceAccountTokenCreator` on itself.
- `infra/variables.tf` + live bucket: `allowed_origins` now includes `https://habeas-codus.web.app`
  and `https://habeas-codus.firebaseapp.com`.
- `tests/test_storage_signing.py`: covers the three credential branches (signing key, IAM, none).

## 4. Applied to the live project

- `gcloud iam service-accounts add-iam-policy-binding` — tokenCreator for the runtime SA on itself.
- `gcloud storage buckets update gs://habeas-codus-media --cors-file` — new origins.
- Deleted the two orphan `pending` assets so the workspace shows the upload dropzone again.
- Verified the IAM path end to end: impersonated the runtime SA, generated a V4 PUT URL, uploaded a
  test object (`PUT -> 200`, object existed), then deleted it and removed the temporary user binding.

## 5. Verification

`uv run pytest` → **100 passed**. `ruff` and `mypy` clean.

## 6. Not done

- The project "Tech review" is left in place (now with no assets) for a retry.
- `infra/RESOURCES.md` updated for the new CORS/signing notes.
- Terraform state still has the known drift; the live changes were applied with `gcloud`. A future
  `terraform apply` should reconcile them.
