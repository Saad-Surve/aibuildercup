# Remove the CC BY demo content loader

## Work completed

- Read the latest creator-presence handoff, technical-design overview/backend/frontend plans,
  and the October 4 demo-seed, channel-picker, and sync-guard progress notes. This removal
  supersedes those notes' loader implementation and attribution follow-ups.
- Removed the `Load CC-BY demo` dropdown, channel choices, mutation/toast, demo badge, and
  attribution UI from the shared YouTube connections component (profile and publish studio).
- Changed the draft style-evidence empty state to point to connecting a real YouTube channel
  and reading its content.
- Deleted the web seed client, backend seed router/service, and GCS seed upload script.
  Removed service dependency wiring, `seed_content_max_items`, connection seed fields, and the
  seed-only token guard. Real OAuth, content sync, analytics, publishing, and the separate
  read-only demo login remain available.

## Contracts and structure

- Removed `POST /api/seed/youtube-content`, its request/result schemas, and `isSeed`,
  `seedAttribution`, `seedLicense` from the OpenAPI contract before editing implementation.
  Updated Pydantic and web types together; removed the Firestore seed-connection documentation.
- No new dependencies, tests, storage paths, Terraform resources, or migrations were added.
  The local gitignored `fixtures/seed/youtube` research dataset was left in place.

## Live GCP cleanup

- Listed project buckets and checked the application data buckets. Only the media bucket had
  objects under `seed/`; corpus, exports, raw-social, and temp had no matching objects.
- Deleted every generation under `gs://habeas-codus-media/seed/youtube/` using
  `gcloud storage rm --all-versions`: three Lawrence Systems versions, two Psych2Go versions,
  and one The Humanist Report version (three logical files, six generations).
- Verified `gcloud storage ls --all-versions` now finds no objects there. The existing media
  bucket soft-delete policy retains the six deleted generations as recovery copies for seven
  days; verified them via `--soft-deleted`. The policy was not changed.
- Queried live Firestore through the existing Firestore service: one connection scanned,
  zero seed connections; zero `contentItems`, including orphan seed items. No Firestore
  deletions were necessary. No creator projects or real connections were deleted.

## Verification

- `uv run ruff check .` passed.
- `uv run mypy app` passed (118 source files).
- `bun run lint`, `bun run lint:eslint`, and `bunx tsc --noEmit` passed.
- Formatted the three modified web files with the repository's `bun run format` command.
- `bun run build` hit the pre-existing Turbopack CSS-worker port-binding restriction
  (`Operation not permitted`), also documented in the October 10 optimization notes.
  `bun run build --webpack` passed compilation, TypeScript, and all 16 static pages.
  Existing static-export rewrite warnings remain.
- Parsed the OpenAPI YAML and inspected `app.openapi()`/Pydantic fields: removed endpoint,
  seed schemas, and connection fields are absent; real connection/content-sync routes remain.
- No remaining CC BY loader references in backend, web source, contracts, infra, or CI.
  `git diff --check` passed. No test files or testing dependencies were found in the app sources.

## Not done / next step

- User requested committing and pushing this removal after verification. Commit scope includes
  only this unit's code/contracts and this note; the two earlier untracked research notes remain
  untracked. A push to main triggers the existing deployment workflow. Live GCS cleanup is
  already complete, so the previously deployed loader cannot read its seed files.
- GCS recovery copies expire under the existing seven-day policy (around October 18).
- Preserved the two pre-existing untracked October 11 research handoffs.
