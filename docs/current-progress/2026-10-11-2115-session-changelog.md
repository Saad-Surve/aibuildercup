# 2026-10-11 — Session changelog (web fixes, git surgery, landing calendar)

Consolidated record of one working session. It merges these notes, all now
deleted: `2026-10-11-1615-stash-integration`, `-2029-dev-server-css-fix`,
`-2034-remove-stash-integration-and-push`, `-2043-header-and-project-card-polish`,
`-2051-landing-calendar-animation`, `-2059-sidebar-icon-and-calendar-refinements`.

---

## 1. Dev server "CssSyntaxError" was a stale `.next`, not CSS (20:29)

Next.js 16.3.5 / Turbopack was crashing on `src/app/globals.css` with a
`package.json (directory description file): SyntaxError`. The file on disk was
valid JSON (`node -e JSON.parse(...)` → OK). The dev server had evaluated
`web/package.json` **mid-write** (its mtime was newer than the running `.next`
cache) and cached the bad read.

Fix: kill the stale `next dev` processes, `rm -rf web/.next`, restart. Verified
`GET /` 200 and a 197 KB compiled Tailwind chunk. Dev logs now go to `%TEMP%`,
not the repo. **This is the recurring signature: a stale `.next` from a
mid-edit restart — not a CSS bug.**

## 2. Removed commit `41d854c`, rebased on remote, pushed (20:34)

- Backed the commit up to `backup/stash-integration-41d854c`, then
  `git reset --hard 7f4fde7` to drop it entirely.
- `git fetch` showed the remote had advanced 5 commits (`50e4d40..97d70d6`:
  packaging, Veo grounded inserts, reviewer-heatmap fixes, README/docs). Local
  had diverged, so rebased the one local commit onto `origin/main` — clean
  auto-merge, no conflicts. Validated `contracts/openapi.yaml` (81 paths).
- Pushed fast-forward, **no force**: `97d70d6..4618f58 main -> main`.
- The `2026-10-11-1615-stash-integration.md` note documented that removed
  commit; its content is folded into this file.

**Gotcha:** a rejected push means `fetch` + rebase, never force — a force here
would have destroyed 5 teammate commits.

## 3. Header + project-card polish (20:43)

- `projects/project-card.tsx`: **corner-gap fix** — `Card` renders `rounded-lg`
  but the thumbnail wrapper was `rounded-t-xl` (larger), so the fill curved in
  more than the card ring and the background showed as a crescent. Changed the
  wrapper to `rounded-t-lg`.
- `layout/user-menu.tsx`: avatar button `h-11 w-11` → `h-9 w-9`, `UserAvatar
  size={38}` → `size={30}` (whole widget 42 px → 34 px).
- `layout/app-shell.tsx`: header right cluster `gap-1` → `gap-2` (4 px → 8 px
  between the notification button and the avatar).

## 4. Landing demo 5: chat → scheduled calendar (20:51)

Replaced `ChatDemo` (the "Ask anything about your project" card) with
`CalendarDemo` in `landing/landing-page.tsx`: a static November 2026 grid with
three coloured event dots and a project/platform/time detail square on hover.

- Colours stay in the old chat's fuchsia family: fuchsia-500, violet-500,
  rose-500.
- Feature entry copy updated to match scheduling (was "Ask anything…").
- The dot is an **absolutely-positioned `<button>`**, not a flex item, so the
  `size-*` transition isn't clamped by a flex item's min-content size, and it
  grows symmetrically around the cursor without flicker.

## 5. Sidebar icon + calendar refinements (20:59)

- **Icon corrected:** the `ConstellationIcon` request was for the **sidebar**
  "Creator library" item, not the card thumbnail.
  - `layout/app-shell.tsx`: NAV "Creator library" `Bookshelf03Icon` →
    `ConstellationIcon`.
  - `projects/project-card.tsx`: thumbnail fallback reverted
    `ConstellationIcon` → `FileVideoIcon` (the `rounded-t-lg` fix stays).
- Landing: copy → **"Schedule your posts from within the app"**; removed the
  "Hover a day to preview" footer; auto-play loop added; dot moved to a badge;
  morph sped up.

## 6. Calendar badge, brand SVGs, arrows (21:15)

- **Dot is now a badge hugging the date**, not the cell corner: the day number
  and the dot share an inline span, and the button is anchored `-top-1 -right-2.5`
  relative to the number, so it sits just off the date's top-right and no longer
  floats far away or covers the number.
- **Brand SVG beside the platform name** in the expanded square: each
  `ScheduledPost` gained a `logo` (`/youtube.svg`, `/tiktok-mono.svg`,
  `/instagram.svg`), rendered in a tiny white chip next to the uppercase name.
- **Auto-play demos only day 5** (`CAL_AUTOPLAY_DAY = 5`) — the earlier "random"
  was meant to be this one date. Manual hover/focus still wins; loop idles under
  `prefers-reduced-motion`.
- **Unicode arrows → icon components.** New shared
  `components/common/inline-arrow.tsx` (`ArrowRight01Icon`, text-aligned). All
  rendered arrows replaced:
  - `components/accounts/text-platform-connections.tsx` (two instruction
    paragraphs; the placeholder was reworded since a `placeholder` can't hold an
    icon)
  - `components/landing/landing-background.tsx` ("EN → HI")
  - `components/landing/landing-page.tsx` (`DERIVS.meta` is now a `ReactNode`
    so the Captions entry can embed the icon)
  - `components/projects/draft/draft-context-panel.tsx`
  - `app/data-deletion/page.tsx` (`&rarr;` entity)
  - Remaining arrows are all in code comments (not rendered) and were left.
  - Backend/contracts/corpus arrows are comments/docstrings/prose, not UI.

## 7. Calendar demo: logo in the middle gap, hover-only loop (21:33)

- **Brand logo moved off the start of the text.** It was inline before the
  platform name (`[logo] YOUTUBE`). It now sits centered in the card's empty
  middle gap, between the project name and the date line, in a slightly larger
  white chip (`size-5`). The platform name, project, and date are plain text.
- **The demo loop is hover-only**, matching the other landing demos: the effect
  is gated on the `active` prop (card hover), so day 5 no longer opens on its
  own while the card is idle. Open state is derived
  (`hoverDay ?? (active ? demoDay : null)`) instead of clearing state in the
  effect — oxlint's `react(set-state-in-effect)` rejects synchronous setState.

Verified: `oxlint` + `tsc --noEmit` clean, dev server recompiled, `GET /` 200.
Uncommitted (user didn't ask to commit this round).

---

## 8. Scheduler bug: calendar slots never uploaded to YouTube (22:12)

**Symptom.** "My scheduler is not working, it is not able to upload videos to
YT."

**Root cause (confirmed against live Firestore).** The content calendar's
"Schedule a slot" only writes a *planner* record
(`users/{uid}/projects/{pid}/schedules/{sid}` with `publishId: null`). Nothing
ever turns a bare slot into an upload — the upload pipeline is only reached by
creating a **publish** with `publishAt` (which the publishes router then mirrors
onto the calendar via `ScheduleService.link_publish`). The user's data showed
exactly that: one bare slot (`publishId: null`, `scheduledAt 09:28`) and **zero**
publish documents, while an older immediate publish had uploaded fine. So
scheduling from the calendar silently did nothing.

**Fix (`web` only).** `ScheduleDialog` gained a `createUpload` flag (set by the
calendar page's create flow). In create mode, for a YouTube slot with no
existing `initialPublishId`, it now resolves the caller's connected YouTube
channel and the project's source video and calls `createPublish` with
`publishAt = scheduledAt`, `privacyStatus: "private"`, `captionFormat: "none"`.
The backend uploads the video and auto-creates the linked calendar slot, so the
slot is real. When there is no connected channel or no source video it falls
back to the old bare-plan slot and the toast explains why. Edits and the studio's
"Plan a slot" are unchanged.

Files: `web/src/components/calendar/schedule-dialog.tsx`,
`web/src/app/(app)/calendar/page.tsx`. No backend/contract change.

Verified: `oxlint` + `tsc --noEmit` clean; `eslint` 0 errors (pre-existing
`<img>` warnings only). Not exercised end-to-end (needs a signed-in session; the
pasted bearer token was rejected by the local backend with 401 "Invalid token").

**Not fixed / open.** The pre-existing bare slot at 09:28 is untouched (fix only
affects new slots). Also note: a scheduled publish is marked `published` and its
slot flips to `published` as soon as the *upload* finishes, even though YouTube
holds it private until `publishAt` — a status-semantics wart, separate from this
bug.

---

## 9. Go-live semantics + the real local blocker (22:19)

User asked: "have you fixed everything? would I get notif after post goes live and
status in calendar be updated? and link and everything". Answer: not everything.

**Found a second, bigger problem.** The local backend has **no Google OAuth
client configured** (`GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` are
missing from `backend/.env`, present in `.env.example`). `ConnectionService.
tokens_for_use` needs them to refresh the channel's access token; once the
~1-hour access token expires, every publish fails with
`CONNECTION_NEEDS_REAUTH`. (A probe of mine also flipped the connection to
`needs_reauth` as a side effect — I restored it to `connected` +
`lastErrorCode: null`. It will flip again on the next publish until the env is
set.) The upload at 08:25 worked only because its access token was still fresh.

**Fixed go-live timing (backend).** Previously the worker marked a scheduled
publish `published` *the moment the upload finished* — hours before it went
public — which flipped the calendar slot to `published` and fired the "is live"
notification early.
- `workers/publish_worker.py`: when `publishAt` is still in the future, mark the
  publish `processing` with step "Scheduled to go public <time>" (job still
  succeeds) instead of `published`.
- `services/publish_service.py`: new `_promote_due`, called from `list` and
  `get`, flips a `processing` publish to `published` (which also flips its linked
  calendar slot via `mark_linked_published`) once `publishAt` has passed. No
  scheduler exists in this runtime, so promotion is lazy — the notification
  watcher and the publishing module poll `list`, so the flip + notification fire
  within one poll (~60s) of the real go-public time.
- `web .../calendar/page.tsx`: the schedules query now polls every 60s while any
  slot is still `scheduled`/`planned`, so the status updates in place.

**What already works.** The "live" notification (`is live on YouTube`) and the
`went live` schedule notification are both in `notification-center.tsx` and now
fire at the right moment. The YouTube link exists on the publish card
(`"Open on YouTube"` from `publish.youtubeUrl`) and is set by the worker after
upload. `publishAt` is shown as "Goes public …".

Verified: backend `ruff` + `mypy` (139 files) clean; web `oxlint` + `tsc` clean;
backend `/api/healthz` 200 and `/calendar` 200.

**Fixed the local blocker (env).** Pulled `youtube-oauth-client-id` /
`youtube-oauth-client-secret` from Secret Manager into `backend/.env`
(gitignored), restarted the backend, and verified
`ConnectionService.tokens_for_use` now refreshes (access token len 254, 7 scopes;
connection `connected`, no error). Publishing can refresh and upload locally now.
(The earlier `v5hed68hifE` video has been deleted from the channel — the API
returns no item for it.)

**Still open / not fixed.**
- ~~Set `GOOGLE_OAUTH_CLIENT_ID`/`_SECRET` in `backend/.env`~~ — done this session;
  both values now live in the gitignored `.env` (from Secret Manager).
- The calendar slot itself shows "Linked upload · <channel>" and links to the
  project, but not directly to the YouTube video (the URL lives on the publish).
  Denormalising `youtubeUrl` onto the schedule is the clean follow-up.
- Lazy promotion is a demo-grade substitute for a real scheduler (Cloud
  Scheduler + a due scan) and only runs while a client is polling.
- Whether YouTube actually flips the video public at `publishAt` depends on the
  OAuth client passing YouTube's API audit; an unaudited client's uploads stay
  private regardless, and we don't verify the real privacy status before marking
  it live.

---

## 10. The "Something" post at 22:26 failed — diagnosed and recovered (22:30)

User: "I had scheduled for a post 'Something' at 22:26 but it was not uploaded".

Firestore showed **my calendar fix did run**: a publish was created at 22:13 IST
(16:43 UTC) and its job ran immediately, but it **failed** with
`Google rejected the connection's token. Reconnect the channel.` That was
*before* the OAuth env fix (22:19) — the job was doomed by the then-missing
client id/secret. A second problem: the stored `scheduledAt` was `04:56 UTC`
= **10:26 local**, not 22:26 — the `<input type="time">` dialog's default is
10:00, and my calendar path did **not** reject past times.

**Fixes.**
- `workers/publish_worker.py`: a scheduled `publishAt` now drives privacy too —
  future → upload `private` + `publishAt` (YouTube holds it); already past → drop
  `publishAt` and upload `public` now (the go-live was intended).
- `web .../calendar/schedule-dialog.tsx`: creating an upload slot now rejects a
  time that is not in the future (the publish form already did).

**Recovery (done).** Retried the failed publish via `PublishService.retry` +
`run_publish`:
- job `4816824e80fd197fc076bb68d8a95d06` → succeeded, video
  **`ThVr4MD0FhQ`**, `https://www.youtube.com/watch?v=ThVr4MD0FhQ`
- checked via the YouTube API: **privacyStatus `public`, uploadStatus
  `processed`** → the OAuth client *is* allowed to publish publicly (so the
  earlier audit caveat does not apply here)
- the linked calendar slot flipped to `published`.

Verified: `ruff` + `mypy` (139 files) clean; `oxlint` + `tsc` clean.

**Default time fixed too.** The real root of the 10:26 slip: `at()` in
`web .../calendar/page.tsx` hard-coded 10:00 for every new slot, so a slot on
*today* opened in the past. It now keeps 10:00 for future days but, when the
target day is today, rounds up to the next full hour (22:31 → 23:00) so the
dialog always opens on a valid, publishable time. (Renamed the local `isToday`
to avoid shadowing an outer variable.)

**Still open.** The direct YouTube link on the calendar slot is still not added.

---

## 11. Sync a YouTube deletion back to the app (22:39)

User: "if I have deleted the video directly on YT, it does not sync back to my
calendar and project card." (They had in fact deleted `ThVr4MD0FhQ` — the channel
ow has zero uploads.)

**New status.** `PublishStatus.deleted` added to the backend enum + the web
type; the publish badge shows "Deleted on YouTube" (muted, struck through).

**Detection (lazy, batched, throttled).** `PublishService._reconcile_live`, run
from `list` and `get`, checks live publishes against YouTube via a new
`YouTubeConnector.existing_video_ids` (`videos.list(part=status)`, up to 50 ids
per call). An id the API no longer returns marks the publish `deleted`
(`YOUTUBE_VIDEO_DELETED`) and cancels its linked calendar slot
(`ScheduleService.mark_linked_cancelled`, wired in `mark_status`). A failed
check leaves the publish untouched, and each live video is only re-checked every
`_RECONCILE_SECONDS` (60s) via a `videoCheckedAt` stamp — never on every read.

**UI polling.** The studio's publish query now keeps polling (120s) while any
publish is `published`, and the calendar polls while any slot is non-terminal,
so both surfaces update after the deletion without a manual refresh.

**Verified end-to-end** (temporarily faking a deleted id, then restoring): the
publish flipped to `deleted` with the right error and the slot to `cancelled`;
`existing_video_ids` correctly excludes a missing id. Ran the same reconcile on
the real data: publish `d5dbfdd1…` → `deleted`, slot
`1f5e668f…` → `cancelled`.

Contracts: `openapi.yaml` PublishStatus enum now includes `deleted`. Verified:
`ruff` + `mypy` (139 files) clean; `oxlint` + `tsc` clean; backend `/api/healthz`
200.

---

## 12. Automatic slot status + reschedule re-uploads (23:01)

User: "status should not be a dropdown that user can manually select. it should
be automatically based and updated" and "tried uploading a video now 'Something'
which was scheduled for 22:51 … it did not get uploaded".

**Why 22:51 didn't upload.** The slot was the *original* one, still linked to the
**dead publish** (`d5dbfdd1`, video deleted on YouTube). Editing a slot only ran
`_sync_linked_publish`, which moved `publishAt` on that dead record — it never
re-uploaded. (The week-grid position was a red herring: a 30-min chip starting
22:51 legitimately crosses the 11pm line.)

**Status is now automatic.** The Status dropdown is gone from `ScheduleDialog`;
create/edit no longer send `status`. A slot is `planned` (bare plan) or
`scheduled` (linked upload) and the system moves it to `published` at go-live and
`cancelled` on a YouTube deletion. Create payloads fall back to the backend
default, edits keep the stored status.

**Rescheduling keeps a live upload.** New `_revive_slot_upload` in the schedules
`PATCH` handler:
- linked publish is `deleted`/`failed` → `PublishService.recreate_for_schedule`
  copies the dead publish's settings (video source, title, channel, captions,
  thumbnail) into a fresh scheduled publish for the new time, re-links the slot
  (`ScheduleService.relink_publish`, back to `scheduled`) and enqueues its job;
- linked publish is still waiting (`queued`/`uploading`/`processing` with a
  `youtubeVideoId`) → `reschedule_on_youtube` moves the real go-live via a new
  `YouTubeConnector.update_publish_at` (`videos.update part=status`);
- live (`published`) stays blocked by the existing `CONFLICT`.

**Verified on the real slot** (`1f5e668f`): revive re-linked it from the dead
`d5dbfdd1` to a fresh publish `b02394f2` and the worker uploaded
**`aQJ0Gx5-ers`** — YouTube API reports **`public`, `processed`**
(https://www.youtube.com/watch?v=aQJ0Gx5-ers); slot flipped to `published`.

Verified: `ruff` + `mypy` (139 files) clean; `oxlint` + `tsc` clean; full build
+ `/calendar` 200.

---

## 13. Calendar deletion sync + no half-applied reschedule (23:09)

User: "Again the sync issue. I have deleted video from YT but it is still showing
in my calendar as published" + earlier got "This video already published; its
calendar slot is history."

**Why the calendar stayed `published`.** The YouTube-deletion reconcile only ran
from the *publish* read paths (`PublishService.list/get`). The calendar reads
schedules, which never triggered it, so a deleted video kept its slot `published`
unless the publishing studio (or the notification watcher) happened to poll.

**Why the conflict half-applied.** `ScheduleService.update` wrote the new
`scheduledAt` to Firestore *before* `_sync_linked_publish` raised the
`SCHEDULE_PUBLISH_FINISHED` conflict, so a blocked edit still moved the slot time
(observed: slot 17:35 vs publish 17:21).

**Fixes.**
- `api/schedules.py`: `_reconcile_linked_uploads` runs on the calendar list
  endpoints (`GET /schedules`, `GET /projects/{id}/schedules`) — it calls
  `publishes.list` for each project with a linked slot (throttled/batched
  deletion check) and re-reads, so viewing the calendar syncs a YouTube deletion
  to `cancelled`. Those handlers are now sync (`def`) since they do I/O.
- `services/schedule_service.py`: `update` now calls `_sync_linked_publish`
  *before* writing the slot, so a conflict aborts with nothing applied;
  `_sync_linked_publish` no longer 404s on a missing publish record, it logs and
  continues (the API then re-creates a fresh upload on reschedule).

**Verified on the real slot** (`1f5e668f`): the calendar reconcile flipped it
`published` → `cancelled` and publish `b02394f2` → `deleted`; the earlier
half-written time was restored to 17:21. A direct conflict test (fake live
publish + future reschedule) raised `SCHEDULE_PUBLISH_FINISHED` and left the slot
time byte-identical.

Verified: `ruff` + `mypy` (139 files) clean; backend `/api/healthz` 200.

---

## 14. Stuck uvicorn reload (root cause) + status shown on calendar chips (23:16)

User: "I cannot even see the status … Show it in the card" and "the scheduled
entry for deleted video I have updated to previous slot but it did not send/post
it".

**Root cause of "did not post": the backend was running stale code.** The dev
`uvicorn --reload` had stalled: `%TEMP%/habeas-backend.err.log` ended at
`WatchFiles detected changes in 'app\workers\publish_worker.py'. Reloading...`
with no following `Application startup complete`. So `_revive_slot_upload`
(added later) was never loaded, the slot PATCH fell back to the old behaviour
(only move `publishAt`), and no new upload was queued. Restarted the backend;
it came up clean.

**Recovered the post.** With the fresh backend, the revive created publish
`61f9a663` and the worker uploaded **`jT2-hKGMy2s`** — YouTube API reports
**`public`, `processed`**; slot `1f5e668f` → `published`.

**Status is visible on the calendar now.** The month `EventChip` and the week-grid
chip only colour-coded the status; both now also render `STATUS_META[status].label`
(same as the day agenda, Upcoming rail, project schedule card and publish card),
and the tooltip includes it.

Verified: `oxlint` + `tsc` clean; backend `/api/healthz` 200 after restart.

**Operational gotcha:** after backend edits, confirm the reload actually
completed (`Application startup complete`) before testing — a stalled watcher
silently serves old code. When in doubt, restart the process.

---

## Verification throughout

`bun run lint` (oxlint) and `bunx tsc --noEmit` clean after every step; dev
server hot-compiled cleanly; `/`, `/dashboard`, `/library`, `/settings`,
`/data-deletion` all 200. No tests added (repo rule). No secrets touched.

## Not done / next steps

- Nothing on the landing below-the-fold was re-screenshotted here; the landing
  renders behind the client-side auth gate so SSR only returns the loader.
- Calendar month/dates remain hard-coded (November 2026).
