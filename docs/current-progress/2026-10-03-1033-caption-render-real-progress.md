# Caption burn-in: real FFmpeg progress (fix "stuck at 35%")

## What I did

- Investigated the report that caption burn-in progress "never goes over 35%" and only
  completes after a refresh.
- Read the live integration: `api/captions.py`, `services/caption_service.py`,
  `workers/caption_worker.py`, `services/job_service.py`, `services/video_tools.py`,
  `realtime/events.py`/`hub.py`/`api/ws.py`, and the web side
  (`caption-burn-dialog.tsx`, `use-project-events.ts`, `project-workspace.tsx`,
  `providers.tsx`, `lib/api-client.ts`).
- Reproduced against the running servers with the supplied Firebase token: created a render on
  the `chicken curry` project (118s source) and polled `GET /api/jobs/{jobId}`. The job advanced
  `5 -> 35 -> 100` and reached `succeeded`, output written. The backend is correct.
- Also exercised the installed `@tanstack/query-core` to rule out the two-observer
  `["job", jobId]` `refetchInterval` conflict (workspace returns `false` when the socket is up,
  the panel returns 2000): polling still runs, so that was not the bug.

## Root cause

Progress is coarse. `caption_worker._render` writes **35** immediately before the FFmpeg
encode, then nothing until **85** after it finishes (`uploading`) and **100** on success. For a
multi-minute encode the UI therefore sits at 35 the whole time and reads as "stuck"; refreshing
after it finished shows the completed render. (`docs/current-progress/2026-09-28-1831` already
flagged this as the known gap.)

## Changes

- **`backend/app/services/video_tools.py`** — new `run_ffmpeg_with_progress(args,
  timeout_seconds, duration_seconds, on_progress)`. Runs FFmpeg with `-progress pipe:1
  -nostats`, parses `out_time_us`/`out_time_ms` and `progress=end`, and calls
  `on_progress(out_time / duration)` clamped to `[0, 1]`. stderr is drained on a daemon thread
  (so a chatty encoder cannot fill a pipe); a `threading.Timer` watchdog enforces the timeout
  (streaming has no `subprocess.run(timeout=)`).
- **`backend/app/workers/caption_worker.py`** — replaced `run_ffmpeg_command` with the streaming
  runner and added `_encode_progress_reporter`, which maps the encode fraction into the job's
  `35..85` slice, throttled to one write per percent step and at most every 1.5s, and never
  raises into the encoder. The upload step still writes 85, success writes 100.
- **`web/src/components/projects/caption-burn-dialog.tsx`** — added
  `refetchIntervalInBackground: true` to the render's `["job", jobId]` query so the bar keeps
  polling if the tab loses focus mid-encode (matches `project-workspace`/`review-panel`).

No contract, schema, storage-path, or delete-path change. Progress writes are still attributed
to the same job, so the WS `job.progress` frames and the HTTP polling both carry the new values.

## Verification (all run)

- **Live reproduction (pre-change)**: render job `70dc6549…` on project `82e580d8…` observed
  `5 -> 35 -> 100`, terminal `succeeded`; render marked `ready`.
- **`run_ffmpeg_with_progress` smoke test** on `fixtures/media/resonance-constructed/clean-control.mp4`:
  reported progress and finished at `1.0`, output non-empty.
- **Reporter test**: fractions `0.25/0.6/1.0` map to `47/65/85`; rapid calls are throttled;
  all values stay within `[35, 85]`.
- **Backend**: `ruff check` clean; `mypy app` clean (79 files).
- **Web**: `bunx tsc --noEmit` clean; `bun run lint` (oxlint) clean.
- Dev server reloaded cleanly (`/docs`, `/openapi.json` -> 200).
- No tests added (repo policy). No commit.

## Not done / next step

- The supplied Firebase ID token expired mid-session, so I could not re-run a full live render
  after the change; the streaming runner and the reporter were validated directly. A single
  caption render in the app is the remaining end-to-end confirmation.
- If `ffprobe`/transcript duration is `0`, no intermediate ticks are possible (only the final
  jump); normal projects always have a duration, so this is an edge case.
- `run_ffmpeg_command` is retained (unused by the caption worker now) for future file-output
  callers.
