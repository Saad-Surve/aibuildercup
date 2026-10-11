# 2026-10-12 00:25 — Prompt-echo copy removed; stale-published sync fixed; backend restarted

Two user reports: (1) "why have you added my prompts as descriptions" — the
"Status is automatic — it follows the upload, not a setting." style copy; (2) a
video deleted on YouTube still shows `published`.

## 1. Copy cleanup (web, uncommitted)

Removed every place the creator's own chat phrasing had leaked into user-facing copy:

- `schedule-dialog.tsx`: deleted the "Status is automatic — it follows the upload,
  not a setting." line under the edit header (badge + label suffice).
- Toasts: "Slot updated — it still can't upload" → "Slot updated";
  "Slot saved — it can't upload yet" → "Slot saved" (warning level + the factual
  backend `statusDetail` kept).
- Create helper: "Saving queues the upload: … the slot tells you exactly what." →
  "Saving uploads the video and schedules it to go public at the chosen time.";
  "Auto-upload is wired for YouTube — …" → "Slots for this platform are plans
  only — nothing uploads."
- `notification-center.tsx`: "can't upload yet" / "Something it needs is missing —
  open the calendar." → "is blocked" / "Open the calendar for details."

Backend `statusDetail` strings are factual system text, kept as-is.

## 2. The sync bug: calendar stopped polling at `published` (real regression)

`calendar/page.tsx` polled only while a slot was `planned`/`scheduled` — the moment a
slot read `published`, polling stopped, so the backend's YouTube-deletion reconcile
(which only runs on read) never ran again and the UI showed `published` forever.
Fix: poll while any slot is `planned`/`scheduled`/`published`; only `cancelled` and
`failed` are terminal. Same polling added to the project "Posting schedule" card
(`project-schedules.tsx`), which never refetched at all. The studio publish list
already polled `published` every 120s — untouched.

## 3. Backend was a stale orphan — restarted on current code

Forensics: port 8080 was held by dead parents (netstat PIDs 17816/23432, no such
processes) via socket inheritance through orphaned `multiprocessing.spawn` children;
the tail of the old log showed the classic stalled WatchFiles reload ("Reloading…"
with no "startup complete" after it). So the server predated the uncommitted auto-arm
work and possibly late commits. Killed the orphans (10380, 14868, plus the earlier
dead-watcher tree 18292/24340) and started a fresh
`uv run uvicorn app.main:app --reload --port 8080` (logs in `%TEMP%`,
"Application startup complete", `/api/healthz` 200). Note: PID 19420 is the VS Code
formatter, 21032 trivial — both left alone.

## 4. Proved the sync end-to-end against live Firestore (uid 4TMp…ebf2)

Ran `PublishService.list` (the exact reconcile path the calendar triggers) over every
project with current code from disk:

- All genuinely-deleted videos (`jT2-hKGMy2s`, `aQJ0Gx5-ers`, `ThVr4MD0FhQ`,
  `A7mNFfBRgh8`) correctly read `deleted` with their slots `cancelled`.
- The one `published` entry (`e24d515a…` → `Yy--rrT5KsY`, the 23:49 recovery upload)
  is **still returned by the YouTube API** — i.e. "published" is the correct state
  for it right now. If the user deleted a different video, it is already synced; if
  they mean this one, YouTube still has it.

## Verification

- `ruff` + `mypy` (139 files) clean; `oxlint` + `tsc --noEmit` clean.
- Fresh backend serving current code; live reconcile exercised, not just reviewed.

## Next / open

- Nothing committed or pushed (not asked). Uncommitted tree = prior auto-arm work +
  my completion + this fix.
- If the user deletes `Yy--rrT5KsY` on YouTube now, the calendar should flip it to
  `cancelled` within ~60s (poll) — worth one live confirmation on their side.
