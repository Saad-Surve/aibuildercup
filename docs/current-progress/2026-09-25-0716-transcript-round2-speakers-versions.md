# Progress — 2026-09-25 07:16 UTC — Transcript round 2 + real speakers + server versions

Uncommitted (not requested — commit only on ask).

## Card / ring clipping ("borders cut off top and bottom")

- Root cause: horizontal scroll rows (`overflow-x-auto`) clip anything
  reaching their edge, which sliced selected `ring-2` rings and button
  rounding. Same for the transcript `<ol>` at its scroll edges.
- Fixes: avatar picker rows got `px-0.5 py-2` breathing room; transcript list
  and timeline strip got inner padding (`px-1 py-1`); timeline blocks are
  `rounded-sm` inside the padded strip.

## Transcript pane sizing + autoscroll

- Grid is now `items-stretch` (was `items-start`) so video and transcript
  cards share one height; the transcript card is `h-full flex-col` with the
  list as `flex-1 min-h-0` internal scroll, so it can never outgrow the video
  pane (stacked narrow layout keeps `max-h-[60dvh]`).
- Autoscroll no longer uses `scrollIntoView` (which scrolled the whole
  window): a `scrollRowIntoView` helper adjusts only the list's `scrollTop`
  via rect math, memoized in `useCallback`.

## Duration clamp

- Panel takes `mediaDurationMs` (asset fallback) + transcript `durationMs`;
  every edit path clamps to `[0, cap]` (`updateRow`, `insertAfter`, `split`),
  insert refuses when the video end is reached, and Save validates with a
  segment-numbered error. Server re-clamps independently (see below), so
  hand-edited buffers can never persist beyond-duration times.

## Read-only default + export menu

- Transcript is read-only until "Edit transcript" is pressed (timestamps
  still seek). Edit mode unlocks replace-all, silence/note inserts, per-row
  edit/delete, history, shortcuts, Save/Revert/Done.
- The 7 export buttons collapsed into one Export `DropdownMenu`.

## Video pane + player

- Split-mode video card uses `gap-3 py-3 / px-3` (was full card spacing) and
  the player dropped `max-w-3xl` so the video fills its column.
- video.js `controlBar`: `remainingTimeDisplay: false` with elapsed +
  divider + duration on — no more `-0:00` countdown.

## Status pill

- `ProjectStatusBadge` is now `h-7` (matches the Edit/Delete buttons) with
  tinted styles: emerald for Ready, sky for Processing/Uploading,
  destructive/outline for the rest (the solid black primary pill is gone).

## Caveat 1 fixed for real: diarized speakers

- STT provider requests `diarization_config` (empty = auto speaker count) on
  Chirp 3 batch recognition — GA and documented; word `speaker_label`s flow
  through `_response_to_dict` → `normalize_words` → `build_segments`, which
  splits on speaker turns and normalizes to "Speaker 1..N" by first
  appearance. Persisted per segment (Firestore + canonical JSON); VTT uses
  standard `<v Speaker N>` voice tags; contract + web types gained
  `speaker: string | null`.
- Fallback: diarization is language-gated server-side, so the worker retries
  once without it instead of failing the job (tested).
- UI no longer fakes speakers: single/unknown-speaker transcripts render in
  one accent with no legend; multi-speaker ones get per-speaker colors +
  "(auto-detected)" legend + speaker names in timeline tooltips.

## Caveat 2 fixed for real: server-side transcript versions

- New endpoints (contract-first, `contracts/openapi.yaml` + `firestore.md`):
  `PUT /projects/{id}/transcript` (validate + clamp + archive + replace,
  returns Transcript), `GET …/transcript/versions` (20 latest, DESC),
  `POST …/transcript/versions/{v}/restore` (archives current first, so
  restores are reversible). History lives at
  `transcripts/{id}/versions/{v}` — inside the project subtree, so the
  existing recursive delete covers it with no extra delete path.
- Web: "Save to project" PUTs the buffer (buffer + localStorage kept as the
  offline fallback on failure); History lists server versions with Restore;
  localStorage-only history removed.

## Verification

- Backend: `pytest` 167 passed (14 new), `ruff` + `mypy` clean.
- Web: `oxlint`/`oxfmt` clean, `eslint` 0 errors (1 pre-existing `<img>`
  advisory), `bun run build` passes.

## Gotchas

- Old transcripts have `speaker: null` and render neutrally — correct, not a
  bug. Re-transcription picks up diarization.
- `PUT /transcript` has no `expectedVersion` guard (single-editor demo
  assumption); noted for later if collaboration lands.
- `transcriptVersionCounter` on the project still tracks pipeline runs;
  per-edit bumps live on the transcript doc `version`.

## Next

- Caption `<track>` from transcription; backend-generated `thumbnail` assets;
  per-card delete menus; Audience/Connections/Settings pages (unchanged).
