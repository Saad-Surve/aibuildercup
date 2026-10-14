# Creator library: evidence you can explore

Creator-facing purpose: see which supplied or synced material the studio can retrieve, then
find a passage or thumbnail by describing it. Route `/library`, also linked from Settings.

Visual plan: existing studio palette (paper #fafafa, ink #171717, line #e5e5e5, muted #737373,
signal #5b82a6), with existing Schibsted display/body and Geist Mono for counts. A wide map
beside a narrow evidence inspector; below it, keyboard-accessible source rows. The signature
is an evidence constellation: text points and thumbnail tiles occupy an actual two-dimensional
PCA projection of Gemini vectors, passages from the selected source connect with quiet lines. Searching
highlights matching nodes while the inspector shows the exact retrieved passage/source.

Critique before implementation: generic network decoration would imply connections we did
not calculate. Use only shared-source connections, label the projection approximate, show a
list for pending nodes, and keep modality shape as well as color. No ambient movement or
invented topic labels. Responsive map/list stack on small screens. Empty state connects to
Settings and explains the operator folder import; it never invents a creator library.

Model choice: Gemini Embedding 2, GA April 22 2026, supports text and image vectors in the
same space. Use 768 dimensions, documented retrieval prefixes for text and no task_type.
Multimodal accompanying text uses natural titles. Separate each input into its own Content.
Use the existing configured Gemini location (`global` by default); the model card only lists
global/us/eu, so this intentionally follows the application's existing Gemini endpoint, not
the us-central1 Storage/Firestore region. Text $0.20/M tokens, images $0.45/M input tokens
per current pricing page (still labeled Preview there despite the model card's GA status).

Sources checked October 11 2026:
- https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/embedding-2
- https://ai.google.dev/gemini-api/docs/embeddings
- https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing

## Post-review library links

`finding_library_links.py` runs once after findings are normalized. Only clarity,
truth/evidence, audience/brand and emotional-impact findings with severity medium or
higher qualify. Dismissed/rejected findings and adjudications adjusted below medium are
skipped defensively from the stored dict. It never edits review scores, evidence,
suggestions or heatmap bins. The UI labels its separate block **From your earlier work**.

Settings (uppercase environment names):

- `FINDING_LIBRARY_MAX_FINDINGS=8`, configurable 0–10 (0 disables enrichment).
  Highest severity first, then timestamp/id; at most one embedding attempt per finding.
- `FINDING_LIBRARY_TOP_K=3`, configurable 1–5, retrieved from the existing 300-node index
  with `modality="text"`. Profile entries and current-source candidates are excluded
  before ranking, so they cannot crowd out eligible passages.
- `FINDING_LIBRARY_MIN_SIMILARITY=0.65`. This provisional, deliberately selective cutoff
  excludes weak topical neighbors before the selector. It was chosen as a starting
  heuristic, **not empirically calibrated**; cosine is relevance, never confidence or
  correctness. Tune with human judgments of useful creator examples before claiming
  precision. Lexical fallbacks are discarded entirely.
- `FINDING_LIBRARY_SELECTION_ENABLED=true`. One structured call using
  `MODEL_ORCHESTRATOR`, no tools/grounding/media, at most 2,048 output tokens. It selects
  zero or one supplied node per finding and writes one sentence explicitly attributed
  to earlier work. Returned IDs are checked against the retrieved candidates. Disabled
  or failed selection uses a deterministic note describing a related passage, without
  claiming it is better or verifies a fact. The per-call provider override disables
  transient/SDK retries for selection, so even a failure uses at most one Gemini request
  per run; there is no per-finding Gemini loop.
- `EMBEDDING_TEXT_PRICE_PER_MTOK=0.20`. Cache misses reserve the existing per-user daily
  embedding slot before calling the provider. A callback counts attempted query UTF-8
  bytes (including the retrieval prefix) as a conservative token proxy, since the
  embedding interface returns only a vector. Cache hits cost zero. This estimate plus
  reported selection-call usage joins analysis `costEstimateUsd`, feeding the existing
  project budget guard for future runs. It is an estimate, not an invoice measurement.

Queries concatenate bounded quote and critique text, reuse `semanticQueries`, and never
index missing library nodes. No library/no indexed candidate means no model calls.
Read-only users skip the entire step, including query-cache and preset writes. Failures
in retrieval, selection, ownership checks or persistence never fail the analysis run.

Current-source exclusion checks project/asset identity metadata and item IDs, source
URLs (normalizing YouTube watch/youtu.be URLs), equal project title/upload filename stem
when that metadata exists, and identical complete transcript text. Current projects are not themselves a library
source today; these checks also cover a current upload already in an imported/synced
library. Imported data has no required project provenance, so differently titled copies
without matching URL/identity/text cannot always be recognized; exact title matches
may conservatively omit a distinct earlier work with the same title.

Each finding stores at most one snapshot `{nodeId, sourceTitle, sourceUrl?, excerpt,
startMs?, similarity, note}`. Titles/excerpts/URLs/timestamps come from the source node,
never model-generated attribution. `startMs` applies only to earlier videos. Writes
update only `libraryLinks` on an existing owned finding, preserving concurrent decisions
and adjudications; project/account deletion removes these snapshots with the findings.

An active folder import is available independently of `CREATOR_PRESET_ENABLED`; that
setting controls preset installation only. Enrichment does not install missing vectors.

The resumed implementation made no new live embedding or Gemini requests. Local checks
cover cached retrieval, attribution, call limits, optional failure handling and stored
decision/adjudication preservation. Live end-to-end persistence and human relevance
judgments remain unverified; the similarity threshold is still provisional.
