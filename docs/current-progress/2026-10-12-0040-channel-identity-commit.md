# 2026-10-12 00:40 — One channel identity + commit/push of the upload-flow work

## Channel "duplicate" (user report)

User saw "2 YT channels" (`2102ankit` + `ankitmishra21022003@gmail.com`) in the
project video page's channel picker. Probed live Firestore three ways (user's
`connections` subcollection, the exact `ConnectionService.list` path, and every
user's subcollection across the DB): there is exactly **one** YouTube connection
(`a818ae4d…`, `@2102ankit`, `connected`) — no duplicate anywhere. The picker
renders one row per connection, so the "two channels" were the row's subtitle
showing the Google account email AND the channel handle inline
(`email · @handle · 11 subscribers · …`), reading as two entries.

Fix (`youtube-connections.tsx`, web only): the subtitle now shows one identity —
`@handle · N subscribers · M videos read` — and the account email moved to the
row's hover tooltip (`Connected via …`). No backend/contract change; verified
`oxlint` + `tsc` clean.

## Commit + push (user-requested)

Staged only the intended files (no `.env`, no secrets) and committed the whole
upload-flow batch as one commit on top of the two unpushed local commits
(`6c85dce` bookmarklet, `f971ef4` calendar layout):

- `fix(upload-flow): finish auto-arm, wire deletes, show one channel identity`
- Covers: backend slot auto-arm + sweep (`schedules.py`), automatic status +
  `failed`/`statusDetail` (`schedules.py` schema, `schedule_service.py`,
  `publish_service.py` delete/retry/failed paths), web dialog/calendar/project
  card/notification copy + polling, channel single-identity row, `types.ts`,
  `openapi.yaml` (81 paths) + `firestore.md`, and the three progress notes
  (`2349` missed-upload, `2359` flow completion, `0025` copy+sync fix).
- Verified before commit: `ruff` + `mypy` (139 files) clean, `oxlint` +
  `tsc --noEmit` clean, fresh local backend on current code (`/api/healthz` 200),
  live reconcile exercised over all of the user's projects.
- Push: fast-forward expected (local 2 ahead, remote not diverged); no force.

## Gotcha carried forward

Port 8080 was held by dead parents' sockets via orphaned `multiprocessing.spawn`
children — `tasklist`/`netstat` PIDs disagreed until matched through
`Get-NetTCPConnection` + `Win32_Process`. If the backend ever looks stale again,
check for orphans before assuming the reloader is alive.
