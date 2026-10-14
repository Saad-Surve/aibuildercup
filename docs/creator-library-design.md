# Creator library: evidence you can explore

Creator-facing purpose: see which supplied or synced material the studio can retrieve, then
find a passage or thumbnail by describing it. Route `/library`, also linked from Settings.

## Retrieval and inspection

The map plots normalized 768-dimensional Gemini Embedding 2 vectors using deterministic
centered PCA. Text points and thumbnail tiles retain source attribution; projection distance
is approximate. Search ranks cosine similarity in the original vector space, not map distance.
Source rows provide a keyboard-accessible alternative to the map. Related links represent
computed neighbors, not invented topical clusters or confidence scores.

Library source selection first ensures a configured preset if enabled, then uses the active
folder import when present; otherwise it uses the latest connected, content-synced channel.
Disabling the preset does not disable manual imports. Initial drafts retrieve passages,
thumbnails retrieve image references, packaging requests creator context, and post-review
links retrieve indexed text. Specialist prompts and inline writing alternatives do not retrieve
semantic examples. [Architecture](architecture.md#creator-memory-and-embeddings) contains index
bounds; [import](creator-demo-import.md) and [preset setup](creator-public-corpus.md) cover preparation.

## Post-review library links

`finding_library_links.py` runs after editorial selection and footage adjudication, before bins
are saved, on effective findings. Only clarity,
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

Live end-to-end persistence and human relevance judgments remain verification gaps;
[HANDOFF.md](current-progress/HANDOFF.md) records current validation. The similarity cutoff is
provisional, not measured precision.
