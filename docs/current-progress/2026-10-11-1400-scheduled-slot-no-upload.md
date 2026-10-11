# Scheduled slot had no upload behind it + library icon swap

## Library icon

- Sidebar `Creator library` entry now uses `Bookshelf03Icon` (was `Analytics01Icon`,
  which `Audience insights` also uses). Verified the icon exists in
  `@hugeicons/core-free-icons` before swapping. Web only.

## The 2:45 scheduled upload that never went out

Investigated live against local `:8080` (healthy/ready) using the backend's own
Firestore client (read-only) instead of the pasted token — decoded the token payload
only to get the uid + confirm `aud: habeas-codus` matches local `PROJECT_ID`.

Finding: the user has **zero publishes** and two plain calendar slots, both with
`publishId: null`:

- `Week 3 side projects` @ `2026-10-11 04:30 UTC` (= 10:00 IST), project `6e3538af…`
  (this matches the single `POST …/schedules 201` in the backend log; no
  `POST …/publishes` anywhere).
- `Something` @ `2026-10-11 09:15 UTC` (= 14:45 IST — the "2:45" slot).

A slot with no linked publish is plan-only: no video, no channel, no worker — nothing
could ever reach YouTube at 2:45. This is the product-semantics gap, not a worker bug:
the verified upload path (`publishAt` → immediate private upload with YouTube
`publishAt` → auto public) only runs when a publish exists. Likely the user made calendar
slots expecting them to upload, and possibly never connected a channel (publish without
one is a toast error, creates nothing).

Fix applied (web only, in `ScheduleDialog` create mode with no `initialPublishId`): an
explicit note that a slot alone uploads nothing, pointing at “Schedule for later” in the
publishing studio or linking an upload from the Posting schedule card.

## Gotchas

- First uid transcription from the pasted token was wrong (`…yDVTVSNk…`) and read 0
  projects; decoding the payload segment gave the true uid
  (`4TMpUIyCU5R6B21Ito9OcCRVebf2`) and the 4 projects. Lesson: decode, don't retype.
- Past-due plain slots stay `scheduled` forever (only a finished linked publish flips a
  slot to `published`). Left as-is; a `missed` state would be a later call.
- Told the user the YouTube semantic explicitly: scheduled = uploads now as private,
  flips public at the chosen time; nothing happens client-side at exactly 2:45.
- Security: reminded that the pasted Bearer is short-lived (~1h); sign out/in rotates it;
  never committed anywhere (no secret touched the tree).

## Verification

- `bun run lint` clean; `bun run build` clean (all routes prerender). Backend untouched
  this round (earlier `ruff`/`mypy` still green on those files).

## Not done / next step

- User must redo the flow correctly: connect channel → publishing studio → “Schedule for
  later” → pick time → confirm the private video + linked calendar slot appear. Then at
  the go-public time confirm YouTube flipped it.
- Optional: `missed` status for past-due unlinked slots; deferred-queue uploads (current
  design uploads immediately as private — a deliberate YouTube-native choice, keep unless
  asked).
