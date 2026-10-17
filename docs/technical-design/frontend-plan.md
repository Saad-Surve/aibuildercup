# Resonance frontend implementation

The current client is Next.js 16 App Router, React 19, TypeScript, TanStack Query,
Tailwind and Base UI, installed/run with Bun. It exports static HTML/JS to Firebase Hosting.
See [web/README.md](../../web/README.md) for setup and [architecture](../architecture.md)
for the complete workflow.

## 1. Setup

Use `bun install`, `.env.example` → `.env.local`, then `bun dev`. Read this installed
Next version's documentation in `web/node_modules/next/dist/docs/` before framework edits.
Public Firebase identifiers can be exposed; OAuth client secrets/server credentials cannot.

## 2. Structure

`src/app/` defines static routes; `components/projects/` houses player, transcript,
review, source revisions, draft editor and studio modules. `components/calendar/`,
`accounts/`, `auth/` and `layout/` hold shared flows. `lib/api-client.ts` owns HTTP auth/errors;
`lib/types.ts` holds manually maintained contract-compatible types. Feature data adapters
live beside it; hooks bind project events/transcripts/modules to the workspace.

## 3. Shell

Dashboard/projects, calendar, creator library and settings/profile share `AppShell`.
Notifications and avatar/user menu stay available. The public landing/policy routes and
onboarding have separate shells. Theme, layout and module state follow existing patterns.

## 4. Authentication

Google sign-in uses Firebase Web SDK. Guards read `/me` and onboarding state before
showing owned workspaces. Auth changes clear query caches and reject stale requests/socket
messages. Passwordless demo login requests a custom token; shared demo controls are disabled
and backend write middleware enforces the restriction.

## 5. Onboarding and persona

Creators supply preferences, links, audience, language, formats and voice. Grounded public
research can prefill the form. Persona generation is saved/versioned; creators can review
and edit it. Connection setup can be skipped. An example library never silently relabels
itself as the new user's history or becomes their persona.

## 6. Projects

Video projects use upload/processing/review; draft projects use the brief/writing editor.
Cards show poster/duration or document preview/counts. A video can link its source script.
Create, rename/edit and delete dialogs call owned APIs. Account deletion has its own control.

## 7. Workspace

`ProjectWorkspace` branches into independently loaded video/draft workspaces. A video
keeps its player visible while Overview, Transcript, Review, Captions, Packaging,
Localization and Publishing modules change. `/projects/view/project/{id}/{module}` is
served by a static project shell and parsed in the browser. Required-transcript modules
show a prerequisite/action instead of an unexplained empty screen.

## 8. Upload and revisions

The dropzone validates supported type/size, obtains a signed upload session, transfers
directly to Storage, confirms completion and follows progress. Revisions retain the source
history and allow earlier asset/transcript activation. Transcript/review changes show
when a fresh analysis is needed. Local media caching avoids duplicate full-video blobs.

## 9. Transcript and captions

The transcript editor shows timestamped segments and speaker labels, supports find/replace,
segment edits and version/export controls, and seeks the video from text. Caption styles
preview directly on the player; burn-in submits a real render job and downloads its MP4.

## 10. Review

The client requests all nine dimensions. Five-second heatmap tracks are memoized; selecting
one filters related findings and seeks the player. Findings show explanation and actionable
suggestion; exact quotes and source/footage evidence can expand. Strengths use Keep.
Severity filters reduce noise. Blank/incomplete tracks stay visible rather than implying
unreported moments were graded. Flagged moments replaces a misleading overall-quality label.
Historical runs retain their original dimensions/scores and stale-transcript warnings.
The rubric supplies observations in the same nine lanes. Editor verdicts and corroborating
reviewers, adjudicator checks/evidence and separate creator accept/revise/dismiss controls
make the filtering inspectable. Library examples appear as **From your earlier work**, not
as current-video evidence. The audience-interest lane is relative prediction with a generic
or calibrated channel baseline, separate from reviewer scores.

Review includes an Export edit plan card for the selected completed review (or latest completed
review while a run is pending). Current accepted/revised actions have toggleable Cut/Note labels,
merged-removal counts, before/after duration and 24/25/30/60 fps CMX3600 plus Markdown downloads.
An upload-revision action is disabled in the demo; read-only GET downloads remain available.
Creators edit externally, upload a revision and re-run review. The previous reviewed revision’s
latest run and newest completed run compare expanded at the top when the newer run belongs
to a newer revision; the picker can select any completed pair. Existing paired players seek
through comparison alignment. Old rough-cut module links fall back to Review.
Re-review compares two runs on aligned timelines,
showing persisting/new/resolved/uncompared issues and unmatched footage. Missing alignment
or coverage never counts as a resolved finding.

## 11. Thumbnails and packaging

Thumbnail concepts use the real pipeline, supporting batch generation, critique, version
selection/revision, apply and downloads. Packaging supports editable/generated YouTube
listings and source-linked chart/callout/illustrative insert suggestions in the current
working tree. Optional footage generation is explicitly paid and bounded. Automatic source
shorts remain separate future work; sample cards do not establish a working clip pipeline.

## 12. Localization

The project glossary, target-language/voice selectors, speaker assignment and original-audio
choice drive a real dub job. Source/translated captions, corpus/glossary versions and
SRT/audio/video downloads expose the result. A voice catalog does not establish measured
translation/naturalness quality in every language.

## 13. Connections, library and calendar

Settings connects YouTube through OAuth, syncs channel content/audience and displays status.
The creator library shows PCA-positioned passages/thumbnail tiles, keyboard-accessible
source rows, semantic search, topic/modality filters, attribution and real cosine-related
sources. Projection distance is approximate. The calendar offers month/week planning and
links YouTube publish schedules; other platform labels are planning metadata. Writing-platform
cards connect Substack, Medium and Reddit; draft cross-post dialogs use those accounts.
YouTube Analytics calibration can replace a compatible curve's baseline with a blended channel
shape; insufficient data preserves the generic baseline. Publishing displays attachment warnings.

## 14. Draft writing

The free-flow document uses optimistic edits and debounced persistence. Immutable block
versions make rewrites/alternatives reversible. Chat/grounding and selected creator-context
panels sit alongside the editor; Markdown/text and all-version exports preserve selected
text. An optional source-video selection gives generation/chat bounded transcript, review and
interest context, with an inspector for the selected material. Draft writing chat exists;
generic video-project chat does not. Cross-posting is synchronous; Substack can schedule remotely.

## 15. Realtime and hosting

A shared WebSocket subscribes by project with snapshot/reconnect/unsubscribe behavior.
Completion invalidations coalesce over 200 ms. Production connects directly to Cloud Run
because Firebase Hosting does not proxy socket upgrades. HTTP remains the fetch layer.
Firebase rewrites mirror the static project shell and `/api/**`; Next build warns that
runtime rewrites are not applied by static export. Keep both configurations aligned.

## 16. Verification

Run `bun run lint`, `bun run lint:eslint`, `bun run build`; format changed files with oxfmt.
The [evaluation report](../../evals/README.md) distinguishes initial-script payload estimates
from browser/user outcomes. No test libraries/suites are added. Landing illustrations are
not measured results; several historical marketing claims still exceed the current product.
