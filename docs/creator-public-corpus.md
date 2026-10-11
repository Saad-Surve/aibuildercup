# Public creator corpus and automatic backend library

The studio can use one operator-prepared public corpus for the hackathon, with the same
owned import, evidence and semantic retrieval paths used by connected content. This is a
backend source switch; it grants no OAuth scopes or publishing access and adds no UI toggle.

## Current Arun Prabhudesai collection

Local folder: `.tmp/creator-libraries/arun-prabhudesai` (gitignored).
Source configuration and supplied persona: `fixtures/creator-sources/arun-prabhudesai.json`.

- 14 verified Trakin Tech videos: ten recent main-feed entries, four Shorts-feed entries.
- 13 actual automatic Hindi caption tracks; one video has real description text only.
- Ten original thumbnail images spanning reviews, buying guides, tech news and shorts.
- Five authored Arun LinkedIn posts on creator milestones, communication, learning from
  mistakes, AI and a technology roundtable; one official Trak.in biography, labeled as
  editorial content rather than his own writing.
- User-supplied persona is stored separately and explicitly marked as preferences. English
  caption preference does not relabel the actual Hindi speech or create audience analytics.
- 80 Gemini Embedding 2 nodes: 70 text passages and ten images, normalized 768-vectors.
  Six passages sampled across each long source, so later sections can participate too.

Collection retains raw snapshots and an availability report. X yielded a profile shell,
Instagram did not yield usable authored content, and the author archive returned HTTP403;
none are represented as scraped posts. No cookies, logins, CAPTCHA bypass or generated
replacement transcripts. This is a bounded authentic corpus, not a complete internet archive.
Original third-party content lives in the ignored folder/private bucket, not Git.

## Collect and publish

From repository root:

```bash
uv run --project backend python backend/scripts/collect_creator.py \
  fixtures/creator-sources/arun-prabhudesai.json .tmp/creator-libraries/arun-new-snapshot
uv run --project backend python backend/scripts/import_creator.py validate \
  .tmp/creator-libraries/arun-new-snapshot
uv run --project backend python backend/scripts/creator_preset.py publish \
  .tmp/creator-libraries/arun-new-snapshot
uv run --project backend python backend/scripts/creator_preset.py publish \
  .tmp/creator-libraries/arun-new-snapshot --apply
```

`publish` defaults to dry run. `--apply` makes at most 160 model calls (default cap), saves
`embeddings.json` after each call, validates completeness and uploads one immutable ZIP.
A failed run resumes cached content instead of calling the model for successful nodes again.
A repeat publish with unchanged inputs makes zero model calls and reuses the same GCS object.
Model calls do not run automatically during collection, import, GET or account login.

Published object in `habeas-codus-media`:

```
creator-presets/arun-prabhudesai/270c988738ad61ad6fa8b53156c4893e5b52499fea8fcd34386107db8d440533/bundle.zip
```

It contains originals, raw source snapshots, collection report and Gemini index, at 2.92 MB.
The loader only extracts the declared manifest/originals/index; it validates traversal,
symlinks, duplicate names, compressed/expanded size, model, dimensions, finite norms and
complete content hashes before installing the user copy. Initial installation needs bounded
Storage/Firestore I/O; later reads reuse the installed revision. No public GCS URLs required.

## Backend switch

```dotenv
CREATOR_PRESET_ENABLED=true
CREATOR_PRESET_OBJECT=creator-presets/arun-prabhudesai/270c988738ad61ad6fa8b53156c4893e5b52499fea8fcd34386107db8d440533/bundle.zip
```

The deployed workflow accepts these as GitHub repository variables. They are configured for
this corpus; changing the flag requires a deployment. Local development reads backend `.env`.

True: library reads automatically install this corpus and precomputed vectors for the existing
user; draft context and thumbnail retrieval use it. The source is visibly Arun's library with
honest platform/language/attribution details, without operator instructions in the product.
False: library, draft context and thumbnail selection use the user's actual synced connections,
even if an imported corpus remains in their account. Changing the flag never overwrites their
persona, credentials or connections. Missing/mismatched configured artifacts return 503 instead
of silently selecting a different creator. Precomputed publication must match backend model.

The map uses deterministic centered PCA; it is an approximate 2D view. Solid links show the
three nearest other sources by cosine similarity in 768 dimensions. The separately labeled
closest other-modality link is dashed. Image labels are separated for readability, with
leader lines retaining their original PCA positions. These relationships aren't confidence or quality scores,
and modality-filtered views can hide endpoints. Topic facets come from titles/collection
labels and are not invented model clusters. Thumbnails, topic lenses, zoom, source inspector,
semantic search and real related-source cards support exploration.

## Removal

User copies are under `users/{uid}/creatorImports/...` and matching Storage user prefixes.
Account deletion covers originals, semantic chunks, query cache and daily embedding budgets.
The operator importer `remove` also removes an individual owned copy. While the flag remains
on, the next library read reinstalls a removed preset. Disable it to return to connections.

Shared immutable versions intentionally survive account deletion. Remove one explicitly:

```bash
uv run --project backend python backend/scripts/creator_preset.py remove \
  --object 'creator-presets/arun-prabhudesai/ARCHIVE_HASH/bundle.zip' --apply
```

Disable/repoint the flag before removing its active shared object. Stored project evidence is
historical; delete that project/account to remove those snapshots as well.
