# Progress — 2026-09-25 06:51 UTC — Avatar fit, editor modal, compact cards, project edit, transcript studio

Uncommitted (not requested — commit only on ask).

## Avatar sizing (the "rando space left" bug)

- Root cause: `Button`'s styles force every descendant `<svg>` without a
  `size-*` class to `size-4`. The Humation `<svg>` carries no such class, so
  inside the 32px header clip it shrank to 16px and left a ring of empty
  space. Same cause in the editor preview context.
- Fix (`components/avatar/user-avatar.tsx`): wrapper is now
  `flex items-center justify-center … bg-background` (was `block … bg-muted`,
  which showed gray through the transparent art), and the Humation `<svg>`
  gets `className="size-auto"` (only opts out of the button selector — inline
  width/height still win) plus `style={{ width: size, height: size }}` and
  `display: block` (kills inline-baseline gap).
- `UserMenu` trigger: added `p-0` so the 40px circle centers the 32px avatar
  exactly (32 + 2+2 inner pad + 2+2 ring = 40).

## Avatar editor is now a modal

- `AvatarCustomizer` stays as the studio content; new `AvatarEditorDialog`
  shows the current avatar (64px) + one "Customize avatar" button that opens
  the full studio in a `Dialog` (`sm:max-w-2xl`, scrolls). Profile page uses
  the dialog instead of the always-open studio.

## Project cards + source video

- `ProjectCard`: compact layout (`gap-0 overflow-hidden py-0`, tighter
  header/content padding, 1-line description) so cards are shorter; footer now
  shows `Uploaded <date> · <language>` metadata via new `formatDate`.
- `SourceVideoPlayer`: square corners (removed `rounded-xl`/`overflow-hidden`
  rounding on the player shell and the error state) — the video element
  itself is no longer rounded.
- `ProjectWorkspace` source-video card: **no longer renders
  `storagePath`** (the `users/…/projects/…/source/…` internal path). Header
  and only line show human metadata: `size · mime · duration · Uploaded date`
  via new `formatBytes` (existing) + `formatDurationMs` + `formatDate`.

## Project edit (name/description)

- Backend already had `PATCH /projects/{id}` (`UpdateProject{name,description}`,
  contract in `contracts/openapi.yaml`) — no contract change needed.
- Web: new `EditProjectDialog` (name + description, validation, toast,
  `setQueryData` + invalidate `["projects"]`), mounted in the workspace
  header next to Delete. `lib/projects.ts` gains `updateProject()`.

## Workspace split + transcript studio

- `ProjectWorkspace`: when `status === "ready"` (transcript generated) the
  page goes full-width (`w-full`, no `max-w-3xl`) and splits into two columns
  (`xl:grid-cols-2`): source video left, transcript right; `TranscriptTimeline`
  spans full width below. Draft/uploading/processing states keep the old
  narrow stacked layout. Both panels are `key={projectId}` so per-project
  local state resets.
- `SourceVideoPlayer` now broadcasts `creator-studio:timeupdate` (throttled
  0.25s) from video.js; the transcript highlights the active segment and
  auto-scrolls (toggleable, default on).
- `TranscriptPanel` rewrite (client-local editing; server transcript is
  read-only, no new endpoints):
  - Clickable timestamps seek the video; active row follows playback.
  - Search with match count + prev/next (`/` focuses it).
  - Find/replace-all ("Correct all instances"), per-segment text edit,
    start-time edit (seconds), delete, insert-after, split at cursor
    (Enter in editor), Tab jumps to next segment, Esc cancels, Ctrl/⌘+S
    saves a version; silence (`[silence]`) and note (`[note: …]`) insertion
    buttons + per-row silence shortcut.
  - Exports: SRT, VTT, TXT, JSON, CSV, DOC (Word-readable HTML), PDF (print
    window); copy-all to clipboard; version history (localStorage, max 20,
    restore); toasts for save/export/errors; empty/pending/error states with
    next actions + retry.
  - `TranscriptTimeline`: proportional speaker-colored blocks (2-speaker
    palette + gray for silence/notes) with mini waveform bars; click seeks.
- Edits persist in `localStorage` (`transcript-edits-v1-*`); history in
  `transcript-history-v1-*`. Keyed per project; Revert restores the server
  transcript.

## Verification

- Web: `oxlint` clean, `oxfmt` clean, `eslint` 0 errors (1 pre-existing
  data-URL `<img>` advisory), `bun run build` passes.
- Backend (untouched this round): `pytest` 153 passed.

## Gotchas / follow-ups

- Tree still holds the previous session's uncommitted avatar work; this
  round's changes layer on top, nothing committed.
- Speaker colors are index-derived (no diarization data from STT yet) —
  real speaker labels await backend diarization.
- Transcript edits are local-only; a future `PUT /transcript` (versions +
  history server-side) would make them durable across browsers. Contract
  untouched on purpose.
- Word-level (not just segment-level) highlight needs word timestamps from
  the pipeline; the `timeupdate` channel is ready for it.

## Next

- Caption `<track>` from transcription; backend-generated `thumbnail` assets;
  per-card delete menus; Audience/Connections/Settings pages (unchanged).
- Optional: server-side transcript versions + collaborator-safe edits.
