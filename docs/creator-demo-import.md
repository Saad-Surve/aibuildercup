# Import a creator folder for the demo

This operator command validates and stores supplied creator material without an OAuth
login. Applying an import writes to real Firestore and Cloud Storage using Application
Default Credentials; validation/dry runs do not. Import does not run models or create a
publishing connection. The demo's API write restrictions remain enforced.

**Current source selection:** the runtime uses synced YouTube content when
`CREATOR_PRESET_ENABLED=false`. When true, it installs the configured precomputed preset,
which takes precedence over a manually imported folder. To serve a new supplied corpus,
publish/configure it using [the preset workflow](creator-public-corpus.md#collect-and-publish).
The commands below manage owned import records; importing alone does not switch runtime retrieval.

## Folder

Start from `fixtures/creator-import-example/manifest.json` and the complete input contract in
`contracts/creator-import.md`. Add local material and reference it in the manifest:

```text
creator-folder/
  manifest.json
  thumbnails/      # .jpg, .png, .webp — e.g. 10 representative thumbnails
  transcripts/     # .srt, .vtt, .txt, .md
  writing/         # articles/posts as .txt or .md
  videos/          # optional .mp4, .mov, .webm originals
```

Only manifest-listed files are imported. You can supply fewer than ten of anything. Relative
paths cannot escape the folder; missing/invalid files fail validation before cloud writes.
SRT/VTT timestamps and original files are retained. Video originals are stored as library
material, not automatically turned into projects or transcribed. Use the ordinary project
upload flow for the demo video you want to analyze.

Optional supplied view/like/comment counts and audience reports are supported by the manifest
contract. They are labeled as part of the imported library; absent statistics stay absent.

The example is original, fictional sample text with no fabricated audience statistics. Replace
it with your own/licensed material. Raw local creator folders need not be committed.

## Commands

From `backend/`, validate locally (no cloud credentials needed):

```bash
uv run python scripts/import_creator.py validate ../fixtures/creator-import-example
```

Preview an import for an existing app account:

```bash
uv run python scripts/import_creator.py import /absolute/path/to/creator-folder --uid DEMO_UID
```

Import and record its active revision for the account:

```bash
uv run python scripts/import_creator.py import /absolute/path/to/creator-folder --uid DEMO_UID --apply
```

Use an account created through the app; the importer does not create or overwrite a user profile.
ADC must have normal write permissions for the configured project/bucket. A read-only demo
account can be populated by this operator command; API write restrictions do not change.

Reimporting unchanged material reuses its content revision. Changed content becomes a new
revision; only the selected revision is retrieved. Previous revisions remain until removal.
Different bundles can coexist; the last successfully imported bundle is marked active.
No real connections are changed. The configured preset can replace that selection on the
next library read. Disable the preset flag to return to synced channel examples.

Preview removal, then explicitly delete it:

```bash
uv run python scripts/import_creator.py remove --uid DEMO_UID --bundle-id creator-demo
uv run python scripts/import_creator.py remove --uid DEMO_UID --bundle-id creator-demo --apply
```

Removal covers all Firestore revisions and current uploaded objects and clears active
selection. Account deletion covers the owned tree/prefix too. Noncurrent Storage generations
follow bucket lifecycle retention. Generated project/draft history remains until that
project is deleted; old thumbnail previews disappear gracefully when the original is removed.

## How imported material is used

- When selected by the preset workflow, draft generation receives creator bio, video
  transcript examples and authored writing.
- Thumbnail generation can retrieve imported creator thumbnails as image references.
- Draft context API identifies `sourceType: folder_import`; it returns written examples and
  short-lived image URLs without persisting signed URLs in Firestore.
- It does not require a public seed endpoint or pretend that supplied data came from OAuth.

Onboarding research and semantic indexing are implemented separate flows. Import neither
scrapes public sources nor infers a persona. Indexed retrieval uses cosine similarity;
the lexical fallback remains available when semantic retrieval cannot run.

## Semantic library and demo walkthrough

With the prepared preset enabled, sign in and open **Creator library** (`/library`)
from the sidebar or Settings. The import is clearly labeled; it does not become an OAuth
connection. The preset already supplies validated vectors. For synced-channel content,
**Index library** creates the next batch of up to 16 Gemini embeddings; continue until
coverage reads ready. The map plots actual text and thumbnail vectors; click a
point or row to inspect its source passage. Search with a phrase to retrieve matching writing,
transcripts and images. Draft generation automatically retrieves matching passages from an
indexed library, with word matching as a fallback. Original videos are still uploaded through
the ordinary project upload to trigger transcription.

The index uses `gemini-embedding-2` at 768 dimensions and the existing Gemini `global`
endpoint. No video/audio embeddings or crawler calls run during import. Index and query
calls share a 200-call per-user daily allowance, including failed attempts. GET/map browsing
never calls a model. Six text passages per source, up to ten thumbnails and 300 total nodes
enter the demo index; the page reports omitted passages. Unchanged content/model settings
reuse the saved vectors. Republish/reconfigure a changed preset, or disable it and sync
a channel to change current retrieval; old revisions never enter current retrieval.

Account setup now offers the same YouTube connection controls before the profile questions,
with public links alongside them. OAuth returns to that step with the links saved. Public-link
research prefills the profile; it is not a full-page content collector. Only synced connector
content and supplied originals enter this library. A read-only demo account can browse an
already indexed library; use the operator account to prepare indexing before handing it out.

## Automatic prepared corpus source

The backend source flag now controls whether an imported corpus participates in retrieval.
See [public corpus setup](creator-public-corpus.md) for collection, precomputed Gemini vectors,
GCS publication, automatic installation and returning to connected accounts. Folder import
alone does not override real connections when `CREATOR_PRESET_ENABLED=false`.
