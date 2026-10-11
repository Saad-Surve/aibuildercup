# Fix scheduled uploads + notification bell (replaces token key)

Started with `git pull --rebase` (`cf15167..149a516`, fast-forward, clean).

## 1. Scheduled uploads fix ("it just stays like that as it is")

Root cause, two halves:

- **Backend:** `ScheduleService.create` with a `publishId` stored the link but never moved
  the publish's `publishAt` (only `PATCH` did, via `_sync_linked_publish`). So wiring a
  calendar slot to an existing upload changed nothing on the upload itself — the slot and
  the upload silently disagreed. `create` now calls `_sync_linked_publish` on the created
  schedule, so creating a linked slot and rescheduling one behave identically. Linking a
  finished publish is a 409 (`SCHEDULE_PUBLISH_FINISHED`).
- **Frontend:** the publishing form never sent `publishAt` at all, so there was no way to
  schedule at upload time. The Listing card now has a "Schedule for later" checkbox with a
  `datetime-local` go-public picker (future-time validated, button disabled until a time is
  picked). A scheduled upload forces `privacyStatus: private` (YouTube only accepts
  `publishAt` on private videos; the connector already coerces server-side) and the backend
  auto-creates the linked calendar slot as before. `ScheduleDialog` in create-with-upload
  mode now shows which upload it wires ("For upload: …") plus a hint that saving moves the
  upload's go-public time.

## Structural changes (contracts, schema, infra)

- No endpoint/shape change: `publishAt` was already in `openapi.yaml` (`PublishRequest`,
  `Publish`). No infra change.
- `contracts/firestore.md`: two-way-link note updated — schedule create with `publishId`
  also moves `publishAt`; linking a finished publish is a 409.
- Web: `copy-token-button.tsx` deleted, `copyAuthToken` flag removed from
  `lib/feature-flags.tsx` (settings page renders flags dynamically, so the toggle just
  disappears). New: `lib/notifications.ts` (store), `components/layout/notification-center.tsx`
  (bell + drawer + watcher). No new backend surface, so no delete-pathway wiring needed
  (items live in per-user localStorage; signing out switches scope).

## 2. Notification bell (replaces the key icon next to the avatar)

- Header now shows a bell with an unread-count badge instead of the token key button.
  Clicking opens a right-side drawer (`Drawer`, non-modal like the draft alternatives
  drawer): unread/total subtitle, per-item unread dot, click-through marks read and
  deep-links (project workspace / calendar), per-item tick marks read without navigating,
  per-item X dismisses, header has Mark-all-read and Clear-all.
- `NotificationWatcher` (mounted in `AppShell`, behind the auth gate) polls every 60s:
  projects (transcription/processing finished/failed), per-project publishes
  (live/failed), caption renders, dubs, analysis runs, and global schedules (went live +
  one-time "goes public within the hour" reminder). Only transitions notify; the first run
  establishes a baseline silently except recently-updated terminal items (capped per poll),
  so a returning creator still learns what finished while away. All poll failures are
  swallowed; empty-state copy explains what will appear.

## Decisions / gotchas

- Frontend-only inbox (localStorage, per-uid key) instead of a backend
  `users/{uid}/notifications` collection: no contract/infra/delete-path work, works in the
  read-only demo, enough for a hackathon demo. Cross-tab sync via `storage` events.
- `Transcript` has no status field, so transcription-done is derived from project
  status/stage transitions (`processing` → `ready`, stage-aware wording).
- `bun run format` (oxfmt) reformatted ~86 unrelated files; reverted all churn outside the
  touched files (same precedent as the calendar note). New files are oxfmt-clean.
- Revert caution: the churn revert briefly reverted the backend/contracts edits too
  (web status prints them as `../` paths); re-applied and re-verified.

## Verification

- `uv run ruff check .` clean; `uv run mypy app` clean (127 files).
- `bun run lint` clean (fixed one `consistent-function-scoping` warning); `bun run
  lint:eslint` 0 errors (only pre-existing `<img>` warnings); `bun run build` clean,
  `/calendar` + all routes prerender.
- Not authenticated end-to-end (no signed-in session): schedule-create → publishAt sync,
  scheduled publish flow, and watcher transitions still need a live pass against
  `:8080`/`:3000` with a real project, connection, and upload.

## Not done / next step

- Live auth pass above; also confirm the "goes public soon" reminder timing and that
  deleting a linked schedule intentionally leaves `publishAt` (upload still goes out).
- Optional later: server-backed inbox (multi-device), drag-to-move on the grid, ICS export.
