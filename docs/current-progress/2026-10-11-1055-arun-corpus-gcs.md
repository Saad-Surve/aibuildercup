# Public Arun corpus collected, embedded and published

- Collected verified Trakin Tech channel (`UCEPL07qzVsOcHd3sMUws65g`) with yt-dlp:
  10 recent main-feed videos + four Shorts-feed entries; 13 actual automatic Hindi caption
  tracks, one description-only fallback explicitly labeled. Ten real thumbnail originals.
- Added five public LinkedIn posts with author selector verified as Arun Prabhudesai,
  and Trak.in's official biography explicitly attributed to its editorial team. Supplied
  creator persona is marked as user preferences, separate from scraped facts/analytics.
- Local folder `.tmp/creator-libraries/arun-prabhudesai` (ignored) contains manifest,
  originals, raw source snapshots, collection report and persona declaration. No invented
  transcripts/metrics, no full-video downloads. Restricted Instagram/author archive not
  included; X public page shell is not treated as authored posts.
- Gemini Embedding 2: 80 real 768-dimensional normalized vectors (70 text, ten images),
  80 bounded calls, resumable cache; corpus 20 sources / ~90,675 flattened text characters.
- Immutable ZIP published to existing `habeas-codus-media` bucket:
  `creator-presets/arun-prabhudesai/270c988738ad61ad6fa8b53156c4893e5b52499fea8fcd34386107db8d440533/bundle.zip`
  2,919,901 bytes including originals/provenance and precomputed vectors.
- Added manifest provenance, API language/tags/attribution/content type/real cosine neighbors,
  NumPy PCA, strict capped ZIP installer. Backend flag false ignores imports and uses real
  connections. True loads configured GCS corpus into user's owned import subtree, with no
  model calls on GET. Shared-version removal CLI handles operator artifact lifecycle.
- Onboarding now has distinct Connections step after Persona; early Research is optional
  public-link prefill only. Shared Settings/onboarding connection UI shows YouTube plus honest
  forthcoming platform states; no demo/operator loading copy. OAuth saves new step.
- Larger thumbnail map/ribbon, topic filters, zoom, provenance inspector and similarity cards
  underway. Same-modality neighbors dominate this corpus, so an explicitly labeled closest
  opposite-modality relation is computed separately from the top-three overall neighbors.
- Ruff, mypy and TypeScript passed; browser/live install/source-selection/delete checks remain.
  Deployment workflow exposes server flag via repository variables (not set yet). Local ignored
  backend `.env` enabled with the published object. No user account data changed yet.
- Preserve unrelated `fixtures/seed/.gitkeep` deletion and independently arriving platform
  integration research files. Do not add tests or use ESLint/webpack/full builds.
