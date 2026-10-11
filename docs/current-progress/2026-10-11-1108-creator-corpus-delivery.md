# Creator corpus, automatic GCS source and visual Gemini map delivered

## Changes

- Connections now follows Persona in onboarding. Early Research contains optional public-link
  prefill only. Navigation persists the current step, existing personas load on resume, and
  YouTube OAuth saves Connections before leaving. Edit-profile flow skips Connections.
- Shared Settings/onboarding multi-platform surface: YouTube works; Instagram/X/Facebook/
  LinkedIn honestly show forthcoming states. Removed folder/demo/operator loading product copy.
- Public yt-dlp + bounded HTML providers, source configuration and operator collection CLI.
  Raw originals/report preserved in ignored `.tmp/creator-libraries/arun-prabhudesai`.
- Authentic corpus: verified channel, 14 videos, 13 actual automatic Hindi caption files,
  ten original thumbnails, five attributed Arun LinkedIn posts, official editorial biography.
  Supplied persona is labeled user preferences, with English caption preference independent
  from Hindi source language. No invented transcripts/audience analytics or full-video downloads.
- 80 Gemini Embedding 2 normalized 768-vectors (70 text, ten images), 80 logical model calls.
  Immutable GCS ZIP with originals, raw provenance, report and complete index at:
  `gs://habeas-codus-media/creator-presets/arun-prabhudesai/270c988738ad61ad6fa8b53156c4893e5b52499fea8fcd34386107db8d440533/bundle.zip`
  2,919,901 bytes. Repeat publication produced same hash with zero model calls.
- `CREATOR_PRESET_ENABLED` and `CREATOR_PRESET_OBJECT` server settings. True installs validated
  GCS corpus/vector copy under existing owned import trees; false uses real connections and
  excludes imported draft/thumbnail fallback. No model calls during GET/installation/login.
  Missing or mismatched configured artifact is a clear 503, not another creator fallback.
- GitHub repository variables set to enabled + published object; deploy workflow forwards them.
  Local gitignored `.env` enabled too. Settings/examples default false. No real user's persona,
  connections, credentials or existing library were changed directly.
- Strict archive traversal/symlink/duplicate/size/model/vector/content validation. Shared
  version removal CLI; user/account removal covers copies, vectors, queries and budgets.
- Batched source/user-checked Firestore transaction installs all precomputed vectors atomically.
  Initial one-vector-at-a-time installation was slow, so replaced with this bounded batch.
  Failure cleanup prevents concurrent account removal leaving newly copied originals.
- Actual PCA plus full-space cosine neighbors, separately labeled best opposite modality,
  thumbnails/ribbon, title-based topic facets, zoom, source language/attribution inspector,
  related-source cards and semantic search. Collision-separated image labels retain true
  PCA anchors with leader lines; no synthetic clusters or quality/confidence scores.
- API/OpenAPI/backend/web contracts updated together. Dependencies: yt-dlp, BeautifulSoup,
  NumPy. Provider-only external calls; no new infrastructure or testing libraries.
- Operator instructions: `docs/creator-public-corpus.md`, existing import guide updated.

## Verification

- Ruff and mypy passed (127 app files); oxlint, TypeScript and all changed-file oxfmt passed.
  No ESLint/webpack/full builds or tests added/run, per explicit user request.
- Parsed OpenAPI and deployment YAML; node/library/neighbor property sets match Pydantic.
  Example importer validation and preset remove preview passed.
- Live GCS publication and automatic user installation/recovery: 20 sources, 80 of 80 indexed,
  ten signed thumbnail previews. Repeat reads use installed revision; GET made no embedding
  budget writes. Actual semantic query ranked “Communication is everything.” first, then
  Arun's post on learning from mistakes. Context selected imported writing appropriately.
- Flag off excluded owned imported library/context/thumbnail references with no connected
  channels; flag on restored corpus. OAuth/content scraping of an actual logged-in channel
  was not rerun; existing connection selection code was retained.
- Owned batch rejected another UID and wrote nothing; missing configured object returned 503.
- T3 browser: loaded real library/images, semantic search highlighted authentic LinkedIn text,
  390px mobile had no overflow, rendered all five platform rows without demo loading copy,
  resumed Connections, went back to existing Persona and continued to Connections again.
  Desktop image labels were separated and inspector contained real nearest/cross-modal cards.
  Brief T3 tab automation disconnection resolved by opening a fresh collaborative tab.
- Temporary validation account `creator-corpus-validation-20261011` signed out; account tree,
  Storage originals, vectors, query cache, budgets and Firebase Auth account were removed.
  Confirmed user root/imports absent and Storage prefix already empty after deletion.
  Shared published artifact intentionally retained. Private temporary token files removed
  during cleanup; user-provided expired bearer was never stored or committed.
- `git diff --check` passed. Preserve unrelated deletion `fixtures/seed/.gitkeep` and independently
  arriving integration research docs; those are not part of this feature commit.

## Limits / next steps

- This is a bounded authentic public snapshot, not a complete archive. Instagram/author archive
  were unavailable, X yielded only a public shell, one short LinkedIn source insufficient;
  these are recorded instead of fabricated. Public automatic captions may contain errors.
- Index samples six passages across each source; originals remain complete in the corpus.
  2D distances are approximate; actual semantic edges/search use full 768 dimensions.
- Initial corpus installation requires Storage/Firestore/signing I/O; subsequent reads reuse
  the revision. Publishing a new backend model config requires a matching new preset index.
- Additional platforms are UI slots, not implemented connectors. Flag off resolves the existing
  latest synced YouTube channel. New multi-platform merging should use capability contracts.
- Commit/push was explicitly authorized earlier. Deployment is triggered by push; verify the
  workflow outcome separately before claiming the deployed site has updated.
