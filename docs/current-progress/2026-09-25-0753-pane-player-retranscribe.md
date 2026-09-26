# Progress — 2026-09-25 07:53 UTC — Pane heights, rows, player, transcript delete/retranscribe

Uncommitted (not requested — commit only on ask).

## Video height vs transcript pane (was backwards)

- Last round stretched both cards to the tallest (`items-stretch`), which
  grew the video area. Reverted: grid is `items-start` again so the video
  keeps its natural height; the transcript card is now the one that yields —
  `xl:sticky xl:top-20 xl:max-h-[calc(100dvh-6rem)]` with its list scrolling
  internally. Narrow/stacked layout unchanged (`max-h-[60dvh]`).

## Transcript row alignment

- Rows are now a fixed grid (`auto auto 1fr auto`, `items-center`) instead of
  a loose flex: dot, timestamp, text, and actions share one centered axis and
  can't drift. Text renders `tracking-normal break-words text-left`, and the
  timestamp button is explicitly left-aligned (plain `<button>` defaults to
  centered text). No global CSS was setting letter-spacing — verified in
  `globals.css`.

## Sidebar collapse icon

- The toggle used `SidebarLeft01Icon` in both states. It now shows
  `SidebarRight01Icon` + "Expand" when collapsed, `SidebarLeft01Icon` +
  "Collapse" when open.

## Player: grey play button + elapsed time

- Big-play button is standard grey (`rgb(82 82 82)`) instead of signal blue;
  progress fill stays blue.
- Elapsed time: the `remainingTimeDisplay: false` option was already in the
  player config (likely a stale player instance/deployment on the reporter's
  side), but it's now enforced in CSS too — `.vjs-remaining-time` is hidden
  and current/divider/duration are forced visible — so no build can show the
  `-0:00` countdown again.

## Transcript delete + retranscribe (new backend)

- `TranscriptService.delete_transcript`: removes the transcript doc tree
  (segments + versions) and derived storage files (`transcripts/`,
  `captions/` prefixes), clears `activeTranscriptId`, resets the project to
  draft. Video asset untouched.
- `AssetService.retranscribe_source`: finds the latest source video, verifies
  the storage object, and mints a NEW transcribe job via a per-project run
  counter (`transcribe-…-r{N}`) — re-completing the upload would only return
  the original idempotent job, so this was required for a true rerun.
- Endpoints (in `contracts/openapi.yaml`): `DELETE /projects/{id}/transcript`
  (204) and `POST /projects/{id}/transcript/retranscribe` (202, same
  schedule-if-not-terminal logic as upload-complete).
- Web: pending state has "Generate transcript"; toolbar has "Retranscribe"
  (read-only + edit mode) and "Delete" (edit mode), both behind AlertDialog
  confirms; success refreshes project/assets/transcript queries so the
  workspace flips to processing and lines stream back automatically.

## Earlier-prompts audit (requested)

- Grep-verified present: avatar modal on profile, avatar `size-auto` fit fix,
  project Edit dialog wired, no internal storage paths in cards, timeline
  mounted, elapsed-time option + CSS. Nothing from the earlier rounds was
  missing in code; the elapsed-time sighting was a stale client.

## Verification

- Backend: `pytest` 171 passed (4 new), `ruff` + `mypy` clean.
- Web: `oxlint`/`oxfmt` clean, `eslint` 0 errors (1 pre-existing `<img>`
  advisory), `bun run build` passes.

## Gotchas

- Test `test_transcripts_api.py` needed a `get_project_service` override:
  the app builds a separate Firestore client per service, so project GETs
  404'd against an empty client without it.
- `PUT /transcript` still has no `expectedVersion` guard (single-editor
  assumption).

## Next

- Caption `<track>` from transcription; backend-generated `thumbnail` assets;
  per-card delete menus; Audience/Connections/Settings pages (unchanged).
