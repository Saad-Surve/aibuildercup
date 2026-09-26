# Progress — 2026-09-26 13:00 UTC — deploy pipeline optimisation

Analysed a full GitHub Actions deploy log (~163s per run) and rewrote the workflow and
Dockerfile. Could not browse for docs from the sandbox; these are the standard, well-known
GitHub Actions / BuildKit / Next.js caching optimisations.

## Where the time went (from the log)

| Phase | Time | Cause |
|---|---|---|
| `setup-gcloud@v2` | ~28s | downloads the latest Cloud SDK every run |
| `docker build` + push | ~40s | no layer cache on a fresh runner |
| Cloud Run deploy | ~28s | GCP-side revision create (hard floor) |
| `bun install` + `next build` | ~31s | no bun / Next cache |
| `npx firebase-tools@13` | ~25s | re-downloads firebase-tools every run |

## Changes

### `.github/workflows/deploy.yml`

- **Split into three jobs.** `changes` (path filter) → `api` and `web` run **in parallel**.
  They are independent (web talks to Cloud Run through a static `vars.API_URL`), so wall-clock
  drops from `api + web` to `max(api, web)`.
- **Path filtering** with `dorny/paths-filter@v3`: a backend-only commit skips the whole web
  job and vice versa. `changes` runs on every trigger so required checks still report.
  `fetch-depth: 0` on its checkout (paths-filter needs history to diff a push).
- **`setup-gcloud@v2` with `skip_install: true`** — the ubuntu runner already ships gcloud, so
  the ~25s SDK download is gone.
- **`docker/setup-buildx-action@v3` + `docker/build-push-action@v6`** with
  `cache-from: type=gha` / `cache-to: type=gha,mode=max`, so the uv layer and the uv cache
  mount survive between runs. `provenance: false` drops an unused attestation.
- **bun + Next + npm caches** (`actions/cache@v4`): `~/.bun/install/cache`, `web/.next/cache`
  (Turbopack), and `~/.npm` (the npx firebase-tools download).
- **`concurrency`** group cancels a superseded deploy instead of queueing it.
- **`--quiet`** on `gcloud run deploy`.
- **`actions/checkout@v4` → `@v5`** (Node 24) and a separate auth step in the web job (it now
  needs GCP creds for Firebase Hosting on its own).

### `backend/Dockerfile`

- `# syntax=docker/dockerfile:1` and a **`--mount=type=cache,target=/root/.cache/uv`** on
  `uv sync`. The mount only helps a persistent local builder — BuildKit does **not** export
  `--mount=type=cache` contents with the gha backend, so in CI it starts empty every run.
  What actually keeps dependency resolution warm in CI is the cached `uv sync` **layer**
  (`cache-from: type=gha`).
- **Pinned the uv image by digest** (the digest the previous `uv:latest` resolved to) so the
  dependency layer is stable.
- `UV_COMPILE_BYTECODE=1` (faster Cloud Run cold start) and `UV_LINK_MODE=copy` (the cache
  mount and final layer must not share inodes).

## Expected

- Warm run ≈ **60–80s** (was ~163s): parallel jobs, no gcloud download, cached docker
  layers, cached bun/Next, cached firebase-tools. The `changes` job now adds a short serial
  hop before `api`/`web` start; the GCP-side Cloud Run revision (~28s) is unchanged.
- Cold (cache-miss) run still saves the ~25s gcloud download.
- Only one side changed → the other job is skipped entirely.

## Verified

- Workflow YAML parses; `changes`/`api`/`web` jobs, path filters, `if` conditions, and
  `concurrency` all present.
- **Docker is not available in this sandbox**, so the Dockerfile was not built. The
  `--mount=type=cache` syntax needs BuildKit — `docker/build-push-action` uses it, so it is
  fine in CI, but a local `docker build` needs `DOCKER_BUILDKIT=1` (or a modern Docker).

## Gotchas / not done

- **Node 20 deprecation warning will persist** for actions still on Node 20 (`cache@v4`,
  `paths-filter@v3`, `setup-gcloud@v2`, `auth@v2`, `setup-buildx@v3`, `build-push@v6`). It is a
  warning only: since 16 Jun 2026 the runner rewrites `node20` to `node24`, and the
  `ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION` escape hatch was removed on 23 Sep 2026. Bumping to
  current majors (`cache@v5`, `paths-filter@v4`, `setup-gcloud@v3`, `auth@v3`, `setup-buildx@v4`,
  `build-push@v7`) clears it — see the follow-up note `2026-09-26-1330-ci-review-fixes.md`.
- `dorny/paths-filter` is a third-party action. If a required-status-check policy depends on the
  old single `deploy` job name, the check names changed (`api`/`web`).
- Cloud Run revision creation (~28s) is GCP-side and not reducible from here.
- Not run in CI yet — first push will populate the caches and show the real numbers.
