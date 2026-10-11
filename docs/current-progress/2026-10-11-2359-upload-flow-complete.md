# 2026-10-11 23:59 — Upload-to-video flow: completed the half-done auto-arm work

Took over uncommitted work (backend slot auto-arm + `failed`/`statusDetail` + web
simplification) and finished what was left open: status is now fully automatic, the
double-arm race is closed, and both delete directions are wired.

## What the previous round had done (uncommitted, kept)

- `schedules` API arms every YouTube slot (create/read/edit sweep via `_arm_or_explain`
  + `_sweep_slots`); blocked slots stay `planned`/`failed` with `statusDetail`.
- `ScheduleStatus.failed` + `Schedule.statusDetail` (backend, openapi, web types, calendar
  UI, notification watcher).
- `ScheduleDialog` no longer gates on cached channel/project lists; backend arms instead.
- `mark_linked_failed` / `mark_linked_scheduled` backstops.

## What was still broken / missing, and the fix

1. **Status was still client-settable.** `ScheduleCreate.status` / `ScheduleUpdate.status`
   survived, so a slot wired to an existing publish (studio "Posting schedule" →
   "Schedule" button sends `publishId`) was created `planned` with a live upload
   attached — stuck there forever (sweep only handles unarmed slots) while the
   notification watcher warned "can't upload yet" about a slot that WAS uploading.
   Fix: `service.create` forces `scheduled` when `publishId` is given, `planned`
   otherwise; `status` removed from both schemas and from `service.update`.
   Web `ScheduleCreateInput`/`ScheduleUpdateInput` drop `status` to match.
2. **Double-arm race.** Two overlapping calendar reads could both see `publishId: None`
   and queue duplicate uploads (relink orphans the loser — a surprise upload with no
   slot). Fix: `_arm_or_explain` re-loads the slot and bails (changed=True) when it is
   already armed.
3. **Slot delete orphaned uploads.** `DELETE …/schedules/{id}` left a queued publish +
   job behind, which fired later with no calendar entry. Fix: shared
   `_call_off_pending_upload` deletes a linked publish that has not reached YouTube
   (job cancelled via `jobs.cancel`; worker treats cancelled as terminal). Once the
   video is on YouTube the publish record stays as studio history — a calendar delete
   never deletes a video.
4. **Publish delete stranded slots + explicit unlink double-fired.** `PublishService.delete`
   now cancels a still-queued job and calls new `ScheduleService.unlink_publish` (slots
   back to `planned`/`failed` with "Its upload was deleted — …"). Explicit
   `publishId: null` PATCH calls off the old upload before the edit re-arms a fresh one
   (previously: old upload kept firing alongside the new one).
5. **Project "Posting schedule" card didn't know `failed`.** `project-schedules.tsx`
   gains the destructive `failed` tone + `statusDetail` blocker line (mirrors calendar).
6. **Past-time toast lied.** Creating a slot in the past uploads public now (worker
   semantics); the dialog said "Goes live <past date>". Now says "Uploading now" with
   matching copy.

## Contracts

- `contracts/openapi.yaml`: `ScheduleCreate`/`ScheduleUpdate` lose `status` (documented
  as automatic); PATCH/DELETE schedule + DELETE publish descriptions cover arming,
  re-arm-on-edit, and call-off semantics. Still 81 paths, parses clean.
- `contracts/firestore.md`: schedule doc gains `statusDetail`, `failed` enum value, and
  a rewritten two-way-link paragraph (auto-arm, automatic status, delete behavior).

## Verification

- Backend: `ruff` clean, `mypy` 139 files clean, module imports OK.
- Web: `oxlint` clean, `tsc --noEmit` clean, `eslint` 0 errors (4 pre-existing `<img>`
  warnings). No full `next build` this round (component-level changes, tsc covers).
- Not exercised end-to-end against live Firestore (needs a signed-in session).

## Still open / judgment calls baked in

- `_reconcile_linked_uploads` returns True whenever any linked slot exists, so calendar
  reads do one extra fan-out re-list — correct, just an extra read per 60s poll.
- Deleting a slot whose video is uploaded-but-private-waiting keeps the publish: the
  video still goes public at `publishAt`, tracked in the studio, not the calendar.
  No YouTube-side delete exists on the connector (deliberately not added).
- Lazy promotion (poll-driven go-live flip) is still demo-grade, unchanged.
- Uncommitted: everything above + the earlier `2349` note's web fix. Nothing pushed
  (user didn't ask to commit).
