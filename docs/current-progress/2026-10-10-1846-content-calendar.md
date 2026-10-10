# Content calendar: sidebar entry, month/week/day views, two-way project sync

## What I did

Workspace was already in sync with `origin/main` (`12b5ef0`, `git pull --ff-only` =
Already up to date). Started the app in the background of the same git-bash shell
with `nohup … &` (PIDs reparented, survive the session):
- backend: `uv run uvicorn app.main:app --reload --port 8080` → `:8080` (`/api/healthz`
  ok, `/api/readyz` ready). Restarted once mid-session so the new routes went live.
- web: `bun dev` → `:3000` (200). Logs in
  `C:\Users\ankit\AppData\Local\Temp\opencode\{backend,web}.log`.

Built the content calendar the request asked for:

- **Sidebar:** `Calendar` entry (`Calendar01Icon`, `/calendar`) in `app-shell.tsx`
  (desktop rail + mobile nav pick it up automatically).
- **Calendar page** (`web/src/app/(app)/calendar/page.tsx`): Google-calendar-like
  month grid, week columns, and day agenda, with Today/prev/next, a month label,
  slot counts, status filter chips (all/planned/scheduled/published/cancelled),
  an Upcoming rail, click-day to plan, click-slot to edit, and deep links
  (`?schedule=<id>&date=YYYY-MM-DD` opens that slot).
- **Backend schedules** (new): `schemas/schedules.py`, `services/schedule_service.py`,
  `api/schedules.py` — `GET /api/schedules?start&end` (fans out over the caller's
  projects, filters in memory, no composite index), plus per-project
  `GET/POST /projects/{id}/schedules` and `PATCH/DELETE …/schedules/{sid}`.
- **Two-way project ↔ calendar sync:**
  - Creating a publish with `publishAt` auto-creates a linked `scheduled` slot
    (`publishes.py` router → `ScheduleService.link_publish`).
  - Rescheduling a linked slot (`PATCH`) also moves the publish's `publishAt`
    (the worker reads it at upload time); 409 if already published.
  - A finished publish flips linked slots to `published`
    (`PublishService.mark_status` → `mark_linked_published`, failure-logged only).
  - `Publish.publishAt` is now returned by the API (was write-only) and shown in
    publish history as "Goes public …".
  - Project side: new `Posting schedule` card in the publishing studio lists slots,
    offers one-click `Schedule` for uploads with no slot, and links each row to
    `/calendar?schedule=…&date=…`; calendar slots link back via Open project.
- Shared `ScheduleDialog` (create/edit, project picker in calendar mode, upload
  linker, two-step remove, read-only gating).

## Structural changes (contracts, schema, infra)

- `contracts/openapi.yaml`: `/api/schedules`, `/api/projects/{id}/schedules[/{sid}]`,
  `ScheduleId` param, `Schedule{,Create,Update,List,Status}` schemas, and
  `Publish.publishAt` (nullable datetime) response field.
- `contracts/firestore.md`: new `Schedules (content calendar)` section.
- Firestore: `users/{uid}/projects/{projectId}/schedules/{scheduleId}` (+ path helpers
  in `paths.py`, re-exported by `firestore_service.py`). Lives under the project
  subtree, so project delete (`delete_document_tree`) and account delete cover it —
  no extra delete wiring. No infra change.

## Decisions / gotchas

- No collection-group index: the month query fans out over ≤200 projects × ≤200
  slots and filters the window in memory. If libraries grow large, add a composite
  index and switch `list_for_owner` to `query_collection_group`.
- ESLint here runs react-hooks v6 rules: no `setState` in effects, no `Date.now()`
  in memos. Followed the codebase's own pattern instead — search params are read
  during render (like `projects/view/page.tsx`), dialogs mount fresh per open with
  prop-seeded state (parents key them), and `now` is a lazy `useState` initializer.
- `oxfmt` reformats unrelated lines in `publishing-module.tsx` (file predates the
  formatter); reverted that churn so the diff is 9 insertions only. New files are
  `oxfmt`-clean.

## Verification

- `uv run ruff check .` clean; `uv run mypy app` clean (119 files).
- `bun run lint` clean; `bun run lint:eslint` 0 errors (only the pre-existing
  `<img>` warning in `project-card.tsx`); `bun run build` clean, `/calendar`
  prerendered and serving 200 from dev.
- Live: `GET /api/schedules` → 401 unauthenticated (route + auth wired);
  `/openapi.json` lists the three schedule routes.

## Not done / next step

- No authenticated end-to-end exercise yet (create slot → link publish → reschedule
  → publish finishes → slot flips to published). Do it with a signed-in session
  against the running `:8080`/`:3000`.
- Optional polish later: drag-to-move on the grid, hour-grid week view, ICS export.
