# Feature research and EmbeddingGemma 2 opportunities

## Work completed

- Read the latest handoff (`2026-10-11-0930-optimization-commit.md`), root AGENTS.md,
  technical-design overview, relevant API contracts, and current implementation.
- Inspected channel-content retrieval, draft generation/assist, transcript search,
  reviewer chunking and footage tools, thumbnail reference selection, localization,
  scheduling, provider interfaces, deployment resource limits, and connection deletion.
- Researched current Google primary sources. EmbeddingGemma 2 was released on
  **2026-10-06**; the original text-only EmbeddingGemma was released on 2025-09-04.
  The latest release is relevant to this media application because it embeds text,
  images, video, and audio in one vector space.
- Research only: no application code, dependencies, contracts, schema, deployment,
  cloud documents, or infrastructure changed. No paid inference or model downloads.

## Current implemented features versus plans

- Implemented: creator persona/onboarding research; connected YouTube content/analytics;
  draft generation, rewriting and alternatives; source-video revisions; editable,
  versioned timestamped transcripts; nine active reviewers with heatmap/findings,
  bounded frame/clip tools and truth grounding; caption burn-in; thumbnail concepts;
  glossary-aware translation/dubbing; YouTube publishing and content calendar.
- General project chat and generic artifact generation remain marked `x-status: planned`
  in OpenAPI and have no registered backend router. Draft writing-partner chat exists.
- Packaging's infographic clips and SEO listing sections are explicitly coming-soon mocks.
  The studio module's ready flag reflects the working thumbnail part, not all its sections.

## Prioritized opportunities

1. **Semantic creator examples for drafting (smallest useful embedding integration).**
   `channel_content_service.py:205` ranks only title/tag/description token overlap.
   `_WORD` recognizes ASCII tokens, so this is especially weak for non-Latin language
   queries. Transcript text does not participate in ranking; the selected video's first
   600 characters become its excerpt. Stored captions are flattened and capped at 6000
   characters, with a default fetch cap of 10 videos per sync.
   Embed title/description and transcript passages, combine semantic and lexical ranks,
   and retrieve the matching passage rather than the opening excerpt. Retain lexical
   matching for names/numbers and fallback when indexing/inference is unavailable.
   Preserve caption timing when ingesting if results need YouTube timestamp links.
   Use diverse examples of comparable format; semantic topical similarity alone does
   not demonstrate that a sample represents the creator's voice or successful content.

2. **Semantic video-moment search (strongest visible demo).**
   `transcript-editor.tsx:242` uses case-insensitive substring matching. Add a distinct
   semantic-search action returning timestamped matches on the existing timeline:
   e.g. “where do I explain the pricing tradeoff?” Text chunks first, then bounded
   frame/audio/video windows for “the shot with the comparison chart.” Keep literal
   find/replace for editing. Use neighboring context/overlap and merge overlapping hits.
   Index against sourceAssetId and transcriptId/version so revisions cannot return
   timestamps from the wrong cut. Reindex edited text and exclude inactive revisions.

3. **Cross-window evidence for reviewers (improves the flagship).**
   `analysis_coordinator.py:125` partitions by a character budget and provides two
   neighboring transcript segments. Add an explicit related-passages retrieval tool to
   locate distant repeated explanations, contradictory-looking claims, and hook/payoff
   relationships. Retrieve bounded footage candidates where useful, then have Gemini
   inspect the real transcript/media and make the judgement. Retrieval should supplement
   the existing contiguous review coverage; do not skip safety/truth review because an
   embedding classifier failed to flag a segment. Similarity is not a contradiction or
   factual correctness detector. Keep web search grounding for external factual claims.

4. **Grounded project chat (new feature).**
   Use the planned contract to implement answers over transcript passages, findings,
   drafts, localization and artifacts. Return source ids/timestamps and clickable evidence.
   One reusable retrieval layer can serve drafting, search, reviewers, and chat.

5. **Relevant thumbnail reference selection (existing feature enhancement).**
   `creator_thumbnail_references` currently downloads up to three images by walking the
   50 most recent channel items. Retrieve image/text references relevant to the topic,
   then diversify them and use explicit style cues. Do not equate embedding similarity
   with click-through rate, identity matching, legibility, or packaging honesty.

6. **Clip shortlist and calendar topic planning (new workflows).**
   Use multimodal search to propose candidate moments and cluster published/planned
   topics to expose repetition or under-covered themes. Gemini should validate a clip's
   complete setup/payoff and determine boundaries; existing FFmpeg/caption services can
   supply building blocks for export. Embeddings do not render clips or predict virality.
   Actual performance recommendations need observed analytics, not similarity scores.

7. **Localization corpus retrieval (later, after the corpus grows).**
   Current code selects a bundled corpus by language pair and includes all pair/universal
   traps in each adaptation prompt. The current small corpus does not need a vector store.
   As it grows, retrieve relevant idiom/code-mixing examples while keeping required
   glossary terms and universal rules deterministic. Embeddings do not replace translation,
   TTS, or exact glossary enforcement.

## Useful fixes independent of embeddings

- `DraftService._assist_context` sends the current brief/title/blocks/request but neither
  prior chat messages nor the creator context used during initial generation. Persisted
  messages are not the same as model conversation memory. Add a bounded recent history
  (or summary) and refresh relevant creator examples on assist to preserve voice/context.
- `ConnectionService.delete:304` revokes OAuth and deletes the secret and connection
  document, but does not delete the connection subtree. `FirestoreClient.delete_document`
  is a single document delete. Existing `contentItems` descendants can therefore survive
  disconnect; account recursive deletion covers them later. Fix disconnect to recursively
  delete synced content before introducing connection-scoped embedding descendants.

## Suggested integration shape and constraints

- Contracts first for any new retrieval/search API or stored document shape. Add an
  `EmbeddingProvider` interface under `backend/app/providers/`, independent of generation.
  Store project chunks under `users/{uid}/projects/{projectId}/...` and channel chunks under
  the corresponding connection subtree. Apply ownerUid and active-source filters before
  nearest-neighbor selection; enforce ownership on every result.
- Firestore already supports Python vector queries and metadata prefilters, with vector
  indexes. Its supported maximum of 2048 dimensions accommodates EmbeddingGemma 2's 768d.
  A new vector database is unnecessary for the first integration. For the currently small
  50-video default sync, bounded in-process similarity is also an option; profile reads
  before choosing native indexed querying.
- Store model/revision, dimension, task/prompt version, modality, content hash, chunk
  boundaries, and source version. Re-embed only changed content. Query/doc vectors must
  use the same model space and dimension; don't mix models or incompatible revisions.
- Start with text-only encoder loading; compare 256/512/768 dimensions on representative
  fixtures and multilingual creator queries. Use the documented query/document task
  prefixes and normalize after truncation. For media, start at 512/768 rather than 128d.
  Use float32 on CPU or supported bfloat16; the model card explicitly warns against float16.
- Do not load the full model into the existing API container without measuring memory
  and latency: deployment currently specifies **1Gi RAM**, min-instances 0, max-instances 1,
  and also handles FFmpeg/media work. Edge-device quantized memory figures do not represent
  Python/Transformers total process memory. Self-hosting incurs compute/model-load costs
  even when weights are free. Keep inference/indexing bounded and behind the existing cap.
- Launch documentation says Agent Platform Model Garden availability is **coming soon**;
  EmbeddingGemma 2 is not a drop-in replacement model id in current Gemini generation calls.
  Compare a separately served EmbeddingGemma 2 provider with the hosted Gemini embedding
  route if minimizing operations is more valuable than local inference. Verify region,
  availability, pricing and request limits before implementation/deployment.
- Local embedding inference only makes that step local. Existing cloud transcription,
  storage, generation and publishing mean the complete studio is not offline/private-local.

## Validation and next step

- Findings were verified by static reads of code/contracts and current primary-source docs.
  No runtime quality, memory, latency, or cost improvement has been measured. Application
  lint/build/type commands were not rerun because this unit of work changes only this note.
- First implementation recommendation: fix draft-assist context and disconnect deletion,
  then add text semantic retrieval for creator examples. Next add timestamped transcript
  search; extend to media/reviewer evidence only after retrieval quality is demonstrated.
- Manually compare current versus semantic retrieval on a bounded set of paraphrase,
  non-Latin/mixed-language, exact-name, no-match, distant-passage and revision queries.
  Track useful top-five results, timestamp correctness, p95 latency, indexing/query cost,
  ownership isolation, reindexing and deletion. Do not add automated test files, per AGENTS.md.

## Primary sources

- Launch, date, deployment/runtime options and Model Garden status:
  https://blog.google/innovation-and-ai/technology/developers-tools/embeddinggemma-2/
- Current overview and distinction from EmbeddingGemma 1:
  https://ai.google.dev/gemma/docs/embeddinggemma
- Model capabilities, dimensions, prefixes, encoder loading and precision:
  https://ai.google.dev/gemma/docs/embeddinggemma/model_card_2
- Firestore vector queries, indexes, filters and limitations:
  https://firebase.google.com/docs/firestore/vector-search
- Hosted multimodal embedding alternative:
  https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/embeddings/get-multimodal-embeddings
