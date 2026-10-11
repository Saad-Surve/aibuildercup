# Day arc: scheduled uploads, notifications, brand icons, draft↔video link

Compacts 8 session notes (1330 → 1525) into one. Nothing pushed before this point.

## 1. Scheduled uploads fix

Symptom: calendar scheduling "just stays like that". Two halves:

- Backend: `ScheduleService.create` with a `publishId` stored the link but never
  moved the publish's `publishAt` (only PATCH did). Create now calls
  `_sync_linked_publish`; linking a finished publish is a 409.
- Frontend: the publish form never sent `publishAt`. New "Schedule for later"
  checkbox + future-validated `datetime-local` picker; scheduled uploads force
  `private` (YouTube requires it; connector coerces too) and auto-create the
  calendar slot. `ScheduleDialog` shows which upload a slot wires and warns that
  a bare slot uploads nothing.
- Live debug with the user's token (decoded payload for uid only, read-only DB
  access, never committed): the 2:45 slot was a plan-only entry
  (`publishId: null`, 09:15 UTC = 2:45 PM IST) with zero publishes on the
  account — nothing could ever upload. YouTube semantic: scheduled = uploads now
  as private, flips public at the chosen time.

## 2. Notification center (replaces the token key button)

Bell with unread badge next to the avatar → right-side non-modal drawer:
per-item tick (mark read), X (dismiss), Mark-all-read, Clear-all; clicks
deep-link and mark read. `NotificationWatcher` polls every 60s (projects,
publishes, caption renders, dubs, analysis runs, schedules): transitions to
terminal states + one-time "goes public within the hour" reminders. First poll
baselines silently except recent terminal items (capped). LocalStorage,
per-uid; no backend surface, so no delete-pathway work. Removed
`copy-token-button.tsx` + the `copyAuthToken` flag.

## 3. Brand SVGs + link icons + library icon

All HugeIcons brand glyphs gone (repo-wide grep clean); connections surfaces use
the official `web/public/` SVGs via `PlatformLogo` (X tile was a `𝕏` char, now
`x.svg`; landing already compliant). Arrow chars in links → real icons
(internal `ArrowRight01Icon`, external `ArrowUpRight01Icon`); instructional
`→` text untouched. Sidebar Creator library → `Bookshelf03Icon`.

## 4. Draft ↔ video pipeline link

Backend (contracts first): `Project`/`CreateProject` gain `sourceDraftId` +
`sourceDraftName` (title snapshot); `UpdateProject` gains `sourceDraftId` with
explicit-null-clears semantics via `model_fields_set`. Only video projects may
link, only to owned live drafts (400s `PROJECT_NOT_A_DRAFT` /
`PROJECT_LINK_WRONG_KIND` / `PROJECT_LINK_SELF`). Title-only — an earlier
`scriptSnapshot` variant was fully reverted (schemas, service, openapi,
firestore, web types, publish prefill). `openapi.yaml` + `firestore.md` updated;
fields live on the project doc so delete is covered; dangling pointers render as
plain "(deleted)" text + unlink.

Web: draft header has Convert to video (sends title + brief language/platforms +
pointer, flushes keystrokes first, navigates on success) which becomes "Go to
video" (arrow icon) once a video exists; video workspaces show one quiet
`text-[13px]` flow line — script title → this video → upload state — linking
both ways, nothing on unlinked videos, nothing on draft pages (both per explicit
feedback after a card-based first attempt). Subtle Unlink at the row end.

## 5. Stale-backend saga (operational)

Three rounds of "linking not working" traced to `:8080` running pre-link code
(reload log never listed the edited files; Pydantic silently dropped the field)
plus one real bug found along the way: `undefined === null` is false, so an
omitted field rendered a phantom "Draft (deleted)" row — now normalised with
`?? null`. Resolved by killing `:3000`/`:8080` PIDs and restarting both in git
bash (`nohup`, logs under `Temp/opencode/`); live `/openapi.json` confirms the
link contract. Duplicate linkless videos to be deleted by the user.

## Verification (final state)

- `uv run ruff check .` + `uv run mypy app` (127 files) clean.
- `bun run lint`, `lint:eslint` 0 errors (4 pre-existing `<img>` warnings),
  `bun run build` all routes prerender. No formatter churn in the final states.
- Still needs a live auth pass: Convert → links both ways → schedule → publish →
  strip flips Live.
