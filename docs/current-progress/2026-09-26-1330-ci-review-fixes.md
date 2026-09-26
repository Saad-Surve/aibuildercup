# Progress — 2026-09-26 13:30 UTC — CI review fixes

Reviewed the local deploy-pipeline optimisation (see `2026-09-26-1300-deploy-pipeline-optimization.md`)
against the live docs and applied the fixes. No backend or web feature code changed.

## Corrected claims (the 1300 note was wrong)

- **`--mount=type=cache` is not persisted by `type=gha`.** Docker docs, "Cache mounts":
  *"BuildKit doesn't preserve cache mounts in the GitHub Actions cache by default"*; see also
  `moby/buildkit#3011`. The uv cache mount only helps a persistent local builder. In CI the
  win is the cached `uv sync` **layer** (`cache-from: type=gha`). Comment in `backend/Dockerfile`
  and the 1300 note corrected.
- Verified the pinned uv digest (`sha256:04d046b1…424`) **is** the current `uv:latest` index
  digest, so the pin is valid.
- `setup-gcloud` + `skip_install: true` is documented and correct (system gcloud is used;
  extra components can't be installed, which we don't need).
- Node 20 wording was accurate: `using: node20` actions are force-rewritten to Node 24 and do
  not fail. The 23 Sep 2026 date removed the `ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION` opt-out.

## Changes made

### `.github/workflows/deploy.yml`

- **Fail-open job conditions.** `api`/`web` now use
  `if: ${{ always() && (workflow_dispatch || outputs.<x> == 'true' || needs.changes.result != 'success') }}`.
  Before, if the `changes` filter job errored, `needs: changes` skipped both deploys **and the
  workflow still went green** — a silent non-deploy. Now a filter failure deploys both sides.
- **Action majors bumped** (all Node 24): `actions/cache@v5`, `google-github-actions/auth@v3`,
  `google-github-actions/setup-gcloud@v3`, `docker/setup-buildx-action@v4`,
  `docker/build-push-action@v7`. Clears the Node 20 annotations.
- **Third-party actions SHA-pinned** (they gate/perform the deploy):
  `dorny/paths-filter@ceb8a2b8…` (v4.0.3), `oven-sh/setup-bun@0c5077e5…` (v2.2.0).
- **Next cache key now includes `vars.API_URL`.** `NEXT_PUBLIC_*` are inlined at build time, so
  without this a changed API URL could restore and deploy a stale `.next` build.
- **Docker cache `mode=max` → `mode=min`, added `ignore-error=true`.** The Docker layer cache
  shares the repo's 10 GB GitHub cache budget with the three `actions/cache` entries; `mode=max`
  risked evicting them. `min` still includes every layer of this single-stage image (incl. the
  `uv sync` layer). `ignore-error` stops a cache failure from failing a deploy.
- **`fetch-depth: 0` → `2`** on the `changes` checkout (push diff needs only the previous commit;
  the action deepens on demand for multi-commit pushes).
- **Least privilege:** `id-token: write` moved from workflow level to the `api`/`web` jobs.
- **firebase-tools cache scoped to `~/.npm/_npx`** instead of all of `~/.npm`.

### `backend/Dockerfile` / `backend/.dockerignore`

- Corrected the cache-mount comment (see above).
- Added `backend/.dockerignore` (`.venv`, caches, `tests`, `.env*`). `backend/` is 384 MB locally;
  without it any local/self-hosted build ships that as context.

## Measured (run 36244193869)

**Warm: 60s wall, success — was ~2m45s on the old single-job workflow (~2.8x faster).**

- Cold (first run, empty caches): 3m29s — the Docker build is a full build (1m25s) since there
  is no layer cache yet. Steady state is the warm number below.
- Warm (rerun with populated caches): 60s wall. The `changes` gate is 6s, then `api` (43s) and
  `web` (46s) run in parallel, so wall ≈ gate + max ≈ 60s.

| Step | Old flow | Warm now |
|---|---|---|
| API image build + push | ~40s | **4s** |
| API Cloud Run deploy | ~28s | 15s |
| web `bun install` + `next build` | ~31s | **8s** |
| web Firebase deploy | ~25s | 11s |
| `setup-gcloud` | ~25s (SDK download) | 5s (`skip_install`) |

The gha layer cache is doing the heavy lifting on the image build; the bun/Next caches on the
web build. Both were populated by the cold run.

## Not done / next step

- The warm run confirms the caches are working, so `mode=min` is fine — no need to touch the
  Docker cache. The Next cache is the same size class; watch it only if the repo cache hits 10 GB.
- **`actions/checkout@v5` left as-is** (already Node 24). `checkout@v6`/`v7` and `cache@v6` exist;
  bump only after reading their release notes.
- **`cancel-in-progress: true`** can kill a run mid `gcloud run deploy`. Acceptable for now; flip
  to `false` for deploys if half-rolled revisions ever show up.
- The web job hardcodes the public Firebase config and `vars.API_URL` is used only if set —
  unset yields a relative `/api`, which the Firebase rewrite handles, so no action needed.
