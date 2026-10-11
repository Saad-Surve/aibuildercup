# Creator folder demo import

## Work completed

- User approved building the folder format/import command now, with the real folder and
  target demo account to follow later.
- Added `backend/scripts/import_creator.py` with local `validate`, preview/default-dry-run
  `import`, and preview/default-dry-run `remove` commands. Explicit `--apply` uses the existing
  real Firestore/Storage services and operator ADC permissions. No HTTP backdoor or auth bypass.
- Added a strict version-1 manifest model and bounded local preflight: safe ids, unique items,
  relative regular files inside the folder, UTF-8 text, supported extensions/image headers,
  individual/total size caps, aware publication dates and nonnegative supplied statistics.
- Supports creator biography/links, video metadata, thumbnails, optional video originals,
  SRT/VTT/TXT/MD transcripts, articles/posts and optional supplied audience reports. No
  statistics are invented. SRT/VTT timed cues and all supplied originals are retained.
- Added an original fictional example at `fixtures/creator-import-example/` and guide at
  `docs/creator-demo-import.md`. Updated backend README to remove stale pytest instructions
  and link the importer.
- Imported material feeds existing draft generation and thumbnail-reference consumption.
  A selected imported library takes precedence over connected-channel style content.
  Draft style evidence shows an imported-library badge and retrieved written examples.

## Structural changes

- Input/storage/lifecycle contract: `contracts/creator-import.md`; Firestore hierarchy updated.
- User root field: `activeCreatorImportId`. Libraries live at
  `users/{uid}/creatorImports/{bundleId}/revisions/{revisionId}/items/{itemId}`; originals at
  `users/{uid}/creator-imports/{bundleId}/{revisionId}/...` in the existing media bucket.
- Content-derived revision ids make unchanged imports converge; changed material receives a
  new immutable revision. Uploads/item writes finish before bundle activation. Older revisions
  remain until bundle removal. Existing users/connections/OAuth secrets are not copied or reset.
- Account deletion's recursive user tree and user object prefix cover import data. Operator
  removal clears active selection and deletes all revisions and originals for that bundle.
- Extended existing `CreatorContext` response with sourceType, creatorName, creatorBio and
  writtenExamples; kept OpenAPI, backend models and web types aligned. No new API endpoints.
- Signed thumbnail previews are generated at context read time, not stored in draft snapshots.
  Missing preview/signing failures do not hide text evidence. Stored image bytes supply the
  thumbnail generation references through the existing MediaPart/provider path.
- New services: `CreatorImportService` for validation/persistence/retrieval and manifest models.
  Dependency wiring injects it into ChannelContentService; no Google SDK in feature code.

## Decisions and gotchas

- This supplies collector-like input for demos while the full account-first onboarding and
  researcher/embedding pipeline remain future work. An imported library is not an authorized
  YouTube channel and cannot publish to one.
- Video originals are library assets, not automatically project source uploads. Their Storage
  path does not match the transcription source-object trigger. Use ordinary project upload
  for the video that should be analyzed during the demo.
- Imported context uses bounded Unicode lexical retrieval; no embedding/model calls occur
  during import. Writing generation and thumbnail rendering still use the existing real models
  when invoked through ordinary workflows.
- Generated draft evidence remains project-owned history after source removal. Future retrieval
  excludes removed imports; stale image previews disappear. Delete a project to remove its
  generated text/snapshots, or the account to remove everything.
- The working tree initially contained independent removal of the old public seed feature.
  Those changes were preserved; they were committed externally during this work. An unrelated
  deletion of `fixtures/seed/.gitkeep` remains and was not restored or included in our work.
- No new tests or testing dependencies were introduced. No commit/push was performed here.

## Verification

- `uv run ruff check .`: passed.
- `uv run mypy app`: passed (120 source files).
- `bun run lint` and `bun run lint:eslint`: passed.
- Formatting checks for changed frontend files: passed; new Python files Ruff-formatted.
- `bun run build`: reproduced the previously documented Turbopack CSS-worker port-binding
  failure (`Operation not permitted`). `bun run build --webpack`: passed compilation,
  TypeScript and static export. Existing export/rewrite warnings remain.
- Ran example folder validation and import/removal previews without cloud access.
- Inline local verification (no retained test files): stable content revisions, three preserved
  SRT cues, short-form VTT timing/tag stripping, draft-context serialization, rejection of
  duplicate ids, traversal, missing files, external symlinks, timezone-free dates, unknown
  manifest fields and negative statistics. Supplied analytics validation passed.
- Parsed OpenAPI and confirmed all CreatorContext model fields have contract properties.
- `git diff --check`: passed.

## Not done / next step

- No actual user folder/account was supplied, so live cloud import, removal and authenticated
  writer/thumbnail consumption have not been exercised end-to-end. No cloud writes or paid
  inference calls were made. Image/media streaming is lint/type-reviewed, not live-verified.
- When supplied, validate the folder, preview the target UID, then apply the importer with
  normal ADC credentials. Verify the style-evidence panel on a freshly generated draft and
  imported thumbnail references; remove the bundle if it is no longer wanted.
- Build account-first onboarding and background creator research next, then the embedding
  retrieval layer. Keep collection inputs provenance-aware and preserve deletion lineage.
