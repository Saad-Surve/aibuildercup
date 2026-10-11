# Creator semantic library implementation

## Completed so far

- Built the folder importer recorded in the preceding progress note; added live Gemini
  Embedding 2 provider, source-owned chunk/query caches, resumable explicit indexing,
  normalized 768-dimensional vectors and semantic retrieval with lexical fallback.
- Added authenticated library read/index/search contracts and matching backend/web schemas.
- Added `/library`: actual deterministic PCA map, modality filters, source inspector,
  search highlighting, source rows, indexing coverage and honest empty state.
- Added sidebar/Settings entry and reused YouTube connections on onboarding's optional
  Connect step. Saves that step's links before OAuth so it resumes on return.
- Drafts retrieve matching passages; thumbnail worker now receives import/library services
  and retrieves image references by the project name/brief. Fixed disconnect to delete the
  entire connection tree, including previously leaked contentItems.

## Research and decisions

- Model card: Gemini Embedding 2 GA April 22 2026; unified text/image/audio/video/PDF space.
  This slice embeds text and ten thumbnails, not full videos/audio. Text retrieval prefixes
  replace task_type; image prompts use natural titles. Cached keys pin model/dimensions/
  chunking version and source content so old models/revisions never mix.
- Model only lists global/us/eu. Uses the existing configured Gemini endpoint (global by
  default), matching other existing Gemini calls; Storage/Firestore stay us-central1.
- Current pricing: $0.20/M text tokens, $0.45/M image tokens. Pricing still says Preview while
  model card says GA. Sources and visual plan: docs/creator-library-design.md.
- Explicit indexing: at most 16 calls/request; atomically reserved 200 calls/user/UTC day
  shared with query calls, including failures. Unchanged indices and queries are cached.
- Scope is active import revision or latest synced connected channel. Six passages/source,
  300 nodes total; omitted passages reported. Thumbnail hosts allowlisted and byte bounded.
  Approximate PCA distance is never a quality/confidence score. Lines show shared source.
- Structured audience metrics and account settings remain structured, not vectorized.
  Public-link profile research remains prefill, not a full webpage content collector.

## Validation in progress

- Ruff/mypy and oxlint/TypeScript passed before final thumbnail integration.
- Live ADC call returned one normalized 768-vector from gemini-embedding-2/global.
- Created a temporary isolated validation Auth user + Firestore profile, imported the
  original fictional example with a small original PNG, indexed 4 text/image/profile nodes.
  Semantic query ranked "Finish one small project" first. Reindex made zero model calls.
  Signed thumbnail preview loaded; no raw vectors in API; another UID saw no library.
- Used ordinary Firebase custom-token sign-in for this temporary user to inspect the live
  local UI through T3 preview. Search/inspector worked, no horizontal overflow at 390px.
  No authentication bypass was added to the application. Credentials only in private /tmp.
- The user's account has no active imported/synced corpus. It has not been modified.
- Final cleanup/deletion verification, final checks, commit and push follow this note.
