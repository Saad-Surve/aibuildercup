# Deploy fix: deployer SA needs secretmanager.viewer to attach OAuth secrets

## What I did

Committed and pushed the connector work (`7d2fab7`) to `main`, which triggered the `deploy`
workflow. The API job deployed successfully — **but the new revision dropped the
`GOOGLE_OAUTH_CLIENT_ID`/`SECRET` refs** that had been attached manually, leaving the deployed
connector at `OAUTH_NOT_CONFIGURED` again.

**Root cause.** The deploy workflow's `Deploy API` step attaches the OAuth secrets only when it can
see a `latest` version:

```bash
if gcloud secrets versions describe latest --secret=youtube-oauth-client-id ... \
   && gcloud secrets versions describe latest --secret=youtube-oauth-client-secret ...; then
  secrets_args="--set-secrets=..."
else
  secrets_args="--remove-secrets=GOOGLE_OAUTH_CLIENT_ID,GOOGLE_OAUTH_CLIENT_SECRET"
fi
```

CI authenticates as `creator-studio-deployer`, which had `roles/secretmanager.secretAccessor`.
That role grants only `secretmanager.versions.access`; `gcloud secrets versions describe` needs
`secretmanager.versions.get`, which lives in `roles/secretmanager.viewer`. So the check always
failed and the workflow removed the secrets — even though the versions existed.

**Fix.**
- Added `roles/secretmanager.viewer` to the `deployer` list in `infra/iam.tf` (so Terraform keeps
  it).
- Granted it live: `gcloud projects add-iam-policy-binding habeas-codus --member=serviceAccount:creator-studio-deployer@… --role=roles/secretmanager.viewer`.
- Re-ran the deploy (`gh run rerun 37177750233`). Revision `creator-studio-api-00081-84h` now has
  both secrets attached as `secretKeyRef`.

**Verified after the CI deploy (not manual):** `/api/healthz` → 200; the OAuth callback with a bogus
state → 302 to `https://habeas-codus.web.app/profile?youtube=error&reason=This connection link is no
longer valid.` This proves the CI-deployed revision has the secrets and runs the callback's
collection-group query.

## Gotchas

- This bug was latent: before the user added secret versions, the conditional also failed, so the
  secrets were simply never attached. It only became visible once the versions existed and a deploy
  removed the manual attachment.
- `infra/**` is **not** in the workflow's path filter (`backend/**`, `contracts/**`,
  `.github/workflows/deploy.yml` for api), so committing only `infra/iam.tf` will not trigger a
  redeploy. That is fine; the live IAM grant is already applied.
- The runtime SA (`creator-studio-api`) already has `secretmanager.secretAccessor`, so it can read
  the values once the refs are attached.

## Not done / next step

- Browser test still pending: connect a channel and publish.
