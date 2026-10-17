# Resonance: implementation architecture

Resonance connects uploaded footage to transcript-based review, editorial consolidation,
footage checks, creator decisions and re-review of edited revisions. Creator history feeds
writing and media preparation; YouTube and text-platform connectors handle publishing.
This describes source behavior, not a deployment audit: [HANDOFF.md](current-progress/HANDOFF.md)
tracks current status and [evals](../evals/README.md) records measurement scope.

## The editorial loop

Creators need to understand what to change before generating more material. Resonance
connects each observation to a place in the source video, then supplies an explanation
and an edit. Transcripts, footage, persona preferences and creator-history examples have
different roles; they are not interchangeable evidence.

| Evidence | Used for | Practical boundary |
|---|---|---|
| Current transcript and video | Review, subtitles, packaging and thumbnails | Recognition errors and sampled footage limit coverage. |
| Google Search | Factual review, initial writing, writing chat and persona research | Sources must still support the claim; a URL alone is not verification. |
| Persona and brief | Audience, intent, language and voice | User preferences do not establish facts or audience statistics. |
| Creator library | Post-review examples, initial drafts, thumbnail style references, packaging and exploration | Similarity indicates relevance; past content cannot prove the current video's claims. |

## Cloud stack

| Service | Implemented role | Source |
|---|---|---|
| Firebase Hosting | Static Next.js 16 export, API and project-shell rewrites | `firebase.json`, `web/next.config.ts` |
| Firebase Authentication | Google sign-in, ID-token verification, passwordless read-only demo | `backend/app/auth/`, `api/demo.py` |
| Cloud Run | FastAPI plus the current background workers; one instance, 1 GiB, CPU available outside requests | `.github/workflows/deploy.yml` |
| Firestore | Users, revisions, jobs, findings, heatmaps, drafts, connectors, library vectors and schedules | `services/firestore_service.py`, [contract](../contracts/firestore.md) |
| Cloud Storage | Signed uploads/downloads; source media, transcripts, thumbnails, rendered captions, dubs and evidence | `services/storage_service.py` |
| Pub/Sub | Storage-finalized transcription trigger; best-effort transcript and analysis announcements with no subscribers | `workers/pubsub_handlers.py`, `infra/pubsub.tf` |
| Gemini on Vertex AI / Agent Platform | Structured review, writing, research, cleanup, adaptation, packaging and thumbnail critique | `providers/llm.py` |
| Gemini Embedding 2 | Text/image embeddings for creator evidence retrieval | `providers/embeddings.py` |
| Gemini image generation | Thumbnail generation and conversational revisions | `providers/imagegen.py` |
| Speech-to-Text V2 | Chirp 3 batch recognition, word timings and optional diarization | `providers/stt.py` |
| Translation Advanced / Text-to-Speech | Translation followed by adaptation and timed speech synthesis | `providers/translate.py`, `providers/tts.py` |
| FFmpeg / ffprobe | Evidence frames/clips, caption burn-in, timed audio assembly and visual insert rendering | `services/video_tools.py`, `workers/` |
| Veo | Optional bounded six-second illustrative inserts | `providers/videogen.py` |
| YouTube Data / Analytics | OAuth-backed sync, retention-baseline calibration, upload, captions, thumbnails and scheduled publication | `connectors/youtube.py`, `providers/youtube_analytics.py` |
| Substack / Medium / Reddit | Synchronous draft cross-posting and Substack draft updates | `providers/substack.py`, `providers/medium.py`, `providers/reddit.py` |
| Secret Manager / Cloud KMS | OAuth client secrets and encryption of stored OAuth tokens | `services/token_cipher.py`, `infra/` |
| Artifact Registry / GitHub WIF | Container storage and deployment without long-lived CI service-account keys | `.github/workflows/deploy.yml`, `infra/wif.tf` |
| Cloud Billing / Pub/Sub / Cloud Function | Budget notifications and billing-detachment backstop | `infra/budget.tf`, `infra/killswitch/` |

Infrastructure and media are regional in `us-central1`. Chirp 3 uses the `us`
multi-region; Gemini uses `VERTEX_LOCATION=global` by default; Veo is regional.
Workers run inside the single Cloud Run service. There are no separate worker services,
BigQuery datasets in current Terraform or sentiment pipeline. Cloud removal of obsolete resources
is separate from their removal from Terraform; see HANDOFF.md.

## Upload, transcription and review

1. The API checks ownership and issues a short-lived signed upload URL. The browser
   uploads directly to Storage, keeping large payloads out of the API request path.
2. Upload completion and the Storage-finalized Pub/Sub push converge on the same
   atomically created transcription job. Chirp returns words and speaker labels;
   normalization clamps invalid timings. Optional Gemini cleanup preserves the raw
   result on failure. Transcript versions and SRT/VTT exports retain the source reference.
3. Analysis pins the asset, transcript and persona version. The coordinator partitions
   segments into approximately 36,000-character windows, with two neighboring segments
   on either side as context. Every segment and timeline interval has one owning chunk.
4. The studio requests all nine reviewers: truth/evidence, clarity, pacing/retention,
   legal/safety, cultural/localization, platform fit, audience/brand, emotional impact
   and conversion/CTA. The API always includes six core dimensions. Concurrency defaults
   to four; chunks are serial within each dimension.
5. Up to three stills for short videos or six for longer videos are shared by the
   relevant chunks. A reviewer can additionally request frames or clips through a
   bounded tool loop: three requests and two tool rounds per reviewer/chunk. Only the
   specialist truth reviewer opts into Search grounding. The additional rubric and editor
   passes can also use Search when enabled.
6. Structured outputs are normalized: timestamps are clamped, nonmatching speech quotes
   are rejected, explanations/actions are required, and exact overlapping duplicate
   advice is removed within a dimension/type. Useful partial results persist even when
   another dimension fails; the run reports incomplete coverage.
7. One bounded whole-transcript `rubric-v1` pass acts as a tenth reviewer using all nine
   specialist rubrics. It adds observations to the existing dimensions, not a tenth heatmap
   lane. Product review attaches sampled stills; the evaluation rubric attaches fixture video.
8. `editor-v6` keeps, merges or drops observations by underlying problem. Original findings
   remain stored; representative findings credit corroborating reviewer IDs. Agreement from
   the shared model is not independent verification. Oversized, failed or unaffordable
   batches remain unedited.
9. `adjudicator-v2` checks selected high/critical findings against transcript context and an
   actual frame, with silent clips for temporal dimensions. It confirms, downgrades or
   rejects advice, and can reconcile conflicting actions. It has no Search tools. A total
   of at most 12 calls includes up to four conflict checks; skipped findings remain unchecked.
10. Eligible findings can receive a separate attributed **From your earlier work** example.
    This does not change the current-video evidence, suggestion or score.
11. Five-second bins aggregate retained findings by temporal overlap. Merged/dropped and
    adjudicator-rejected observations are excluded; adjusted severity is honored and a
    critical finding forces red. Coverage distinguishes reviewed gaps from unread spans.
    Selecting a bin filters the findings and seeks the player.

Creators accept, revise, dismiss or clear a finding decision without rewriting the original
review. Decisions are separate from model verdicts. A deterministic rough-cut plan turns
selected accepted/revised actions into safe cuts or edit notes, optionally placing existing
inserts. FFmpeg renders an inactive revision, uploads it under the project prefix and remaps
the transcript without STT. The creator previews, activates or discards it; a fresh analysis
can then be compared with the original run. External edits can also be uploaded as revisions.
Comparison uses a direct cut map or bounded transcript-token alignment and reports resolved,
persisting, new and uncompared findings. Missing alignment/coverage is not evidence of a fix;
fewer flags do not establish improved audience retention.

These are specialized prompts over a shared model, not nine independent human experts.
Normalization establishes format and quote consistency; it cannot establish that a
factual verdict or edit is correct. Confidence fields are not calibrated probabilities.
The aggregate is a summary of flagged moments, not a video-wide quality or retention metric.

## Audience-interest lane

Alongside review, a bundled ridge model combines transcript features with bounded Gemini
moment signals to predict relative interest in five-second bins. A position head supplies
the generic drop-off baseline. This ranks moments within a video; it is not measured retention.
Creator calibration reads up to 40 channel videos through YouTube Analytics, at most 43
requests and a 180-second provider deadline, with one attempt per user per 24 hours and no
Gemini calls. Three eligible videos per duration bucket are required. It blends the channel's
normalized retention shape with the generic baseline; it does not retrain the content model.
Compatible saved curves are adjusted on read, leaving their stored generic snapshot intact.
Insufficient data, a disconnected channel or an incompatible run keeps the generic baseline.

## Creator memory and embeddings

The library ingests connected YouTube content or a validated operator folder import.
The optional hackathon preset installs a visibly attributed public example corpus under
each user's ownership; it does not overwrite their persona or grant OAuth permissions.
The current snapshot has 14 Hindi videos, five authored English posts and one editorial
biography, plus a separately labeled supplied profile.

Passages use 1,400-character windows at 1,200-character stride. Long sources contribute
at most six evenly sampled passages; the index caps at 300 nodes and ten images.
The example has 70 text nodes and ten image nodes, with 15 unsampled passages reported.
The model embeds text and thumbnail-plus-title inputs in the same space, requests 768
dimensions, checks finiteness, and normalizes vectors to unit length.

Node IDs hash source identity, excerpt, content fingerprint, model, dimensions and prompt
version. Successful vectors persist; indexing resumes up to 16 missing nodes per request.
Interactive embedding requests reserve owned daily slots, capped at 200 per user/day.
Query vectors are cached by query/model/dimensions/version, with at most 100 stored entries
per source. Preset publication precomputes vectors once; installing it makes no model calls.

Search ranks full-space cosine similarity and returns up to eight passages by default.
A provider error falls back to lexical overlap; exhausted daily allowance returns 429.
The map uses centered PCA with canonical axis signs for repeatability. Related links
use full-space cosine neighbors from distinct other sources, with an explicitly marked
other-modality link. Map distance is approximate, and cosine is not confidence.

Initial draft generation retrieves relevant passages, replaces shallow excerpts and
reorders bounded examples before sending them to the writer; the selected creator
context is persisted for inspection. Thumbnail generation retrieves original images
and supplies them to the image model as style references. Packaging also requests creator
context. Draft assist/inline alternatives and heatmap reviewers currently do not use
semantic library retrieval. A separate post-review step adds bounded text examples to eligible
findings; see [library links](creator-library-design.md#post-review-library-links). An active
folder import takes precedence over synced channel content even with the preset disabled.
Retrieval is a bounded scan in Python, not a managed vector database or a learned persona.

## Writing and media

Drafts keep an editable brief and immutable block versions. Optimistic/debounced saves
support continuous editing; chat proposals and inline alternatives remain reversible.
Initial generation and writing chat can use Search; short alternatives stay ungrounded.
The context inspector distinguishes supplied profile, original writing and channel material.
Generation failures mark the draft `status: failed` with an explicit error (no synthetic
fallback blocks). An optional linked source project supplies bounded
video context: transcript excerpts, effective findings, predicted-interest moments and persona.
Generation records the selected context; writing chat and downstream listing/thumbnail planning
also have video-context paths. Source claims and creator preferences remain separately labeled.

Captions have five bundled styles, a live overlay and asynchronous ASS/FFmpeg rendering.
Localization translates segments, then applies a Gemini adaptation pass using the bundled
terminology/trap corpus and project glossary. Corpus/glossary versions are recorded.
The voice catalog exposes 25 languages; the curated glossary covers three language pairs.
Up to four TTS requests run concurrently. Audio is tempo-adjusted to segment windows,
with padding/trimming when necessary, then muxed with optional quiet original audio.
This is timed synthesis, not lip synchronization or voice cloning.

Thumbnails are planned from transcript/findings and rendered with source frames and
creator-history references. Critiques assess promise, legibility and platform fit;
revisions retain previous versions. Requests cap at four concepts. Applying a concept
updates the packaging promise; exporting/downloading remains an explicit creator action.

## Packaging

The packaging module provides generated/editable YouTube listings and up to three
source-linked visual insert suggestions. Gemini selects transcript segment indices;
the worker derives the source quotes/timestamps and formats valid chapter starts.
Charts require quoted source numbers and common units; charts and callouts render
locally with FFmpeg. Illustrative B-roll uses one
six-second 720p Veo request, with an explicitly authorized paid-render flag and at most
two reserved slots per project. The operation name is retained so polling resumes the
same generation. Source/transcript changes mark previous packaging stale.

Live verification and deployed state are tracked in [HANDOFF.md](current-progress/HANDOFF.md),
not inferred from this implementation reference. Visual inserts supplement a video and are
separate from automatic shorts cut from the source.
Ready inserts are downloaded for use in a video editor; the studio does not splice them
into the uploaded video through packaging alone. The rough-cut path can place selected existing
inserts in a rendered revision. [The packaging reference](technical-design/packaging-plan.md)
describes editing, chapters, render/resume behavior and publication prefill.

## Publishing, security and deletion

YouTube uses OAuth with expiring state and PKCE; refresh/access tokens are encrypted
before persistence and decrypted only for connector use. The connector reads channel
videos/captions and audience aggregates. Publication stages media, optionally attaches
a thumbnail and captions, and can pass a future publish time to YouTube. The calendar
stores creator schedules; calendar slots for platforms other than YouTube are
planning labels and never post automatically. Draft projects are a writing workflow, separate
from uploading video to YouTube. A finished draft can be cross-posted synchronously to
Substack (session cookie, since Substack has no write API), Medium (legacy integration
tokens only) or Reddit (OAuth) through `providers/substack.py`, `providers/medium.py` and
`providers/reddit.py`. Substack drafts can be updated from the linked studio draft and may request Substack-side
scheduling. Cross-posts do not run as local jobs. YouTube thumbnail/caption attachment failures
produce publish warnings while preserving a successful video upload.

Firebase ID tokens authenticate requests. Owned documents are nested under
`users/{uid}` and checked against the requester; direct browser Firestore access is denied.
Pub/Sub push uses OIDC when configured. Signed media URLs expire, and authenticated
responses disable intermediary caching. Demo write restrictions are enforced in API
middleware as well as in controls.

Project/account deletion marks the parent before cleanup; ownership-checked child writes
reject those markers to reduce worker races. Project deletion recursively removes its
Firestore tree and current Storage objects under the project prefix. Versioned buckets
retain noncurrent generations until lifecycle
expiry; current deletion does not explicitly purge those generations. Account deletion
revokes connector grants best-effort and removes the user tree and Storage prefix.
Creator imports, semantic vectors, cached
queries and embedding budgets are user-scoped. Shared immutable preset archives intentionally
survive user deletion and require operator removal. Deleting a local publish record
does not delete a video already published to YouTube.

## Reliability and scale

Synchronous cloud work runs in FastAPI's thread pool or `asyncio.to_thread`, leaving
model requests and WebSockets asynchronous. Writes batch up to 400 documents per RPC;
individual document billing remains. Jobs use deterministic atomic creation, but execution
locks and the realtime hub are process-local. Most jobs still execute through in-process
background tasks; the current deployment caps Cloud Run at one instance.

Scaling needs durable worker dispatch/leases and shared event delivery first, then
indexed vector retrieval and bounded calendar queries as library/project counts grow.
Direct Storage uploads, versioned evidence, provider separation and typed contracts
make that evolution practical; they do not prove throughput at production scale.

STT submission and polling are separate: operation names are saved before polling and
resumed without resubmission. Explicit submission-time 429/503 responses permit bounded retries;
an ambiguous submission permits one deliberate resubmission, so duplicate billing is still
possible. Polling failures do not trigger normalized-audio fallback.
See [costs](costs.md) for what the current guards cover and what remains unaccounted.

## Judging evidence

The [official rubric](https://aibuildercup.com/themes.html), checked 11 October 2026,
weights technical merit 40%, problem/impact 25%, innovation 25% and experience 10%.

| Official criterion | What to inspect in Resonance |
|---|---|
| Technical Merit & Gen AI Implementation, 40% | [Live Google AI in core workflows](#cloud-stack), grounded function calling, structured partial results, typed contracts/ownership/deletion and deployed Cloud Run/Firebase. [Measured retrieval/probe results](../evals/README.md) and [cost bounds](costs.md) make tradeoffs inspectable; distributed workers remain the next scale step. |
| Problem Alignment & Impact, 25% | A timestamp leads to an edit, then captions/packaging/publishing in the same workspace. This addresses the Media, Content & Digital Experiences theme. [Creator effort and usefulness](../evals/README.md#other-outcomes-to-measure) are the next measurements; no adoption or time-saving result is assumed. |
| Innovation & Creativity, 25% | An actionable [editorial heatmap](#upload-transcription-and-review) plus [visible creator evidence](#creator-memory-and-embeddings) reused across writing and visual generation; current-video facts and historical style are kept distinct. |
| User Experience & Solution Design, 10% | Persistent player, seekable findings, editable/versioned outputs, evidence inspector, caption preview, job progress and read-only demo. [The frontend reference](technical-design/frontend-plan.md) connects those controls to actual workflows. |

For a three-minute demo, show one concrete finding and its footage, one retrieved creator
example influencing a draft or thumbnail, then the export/publishing handoff. Keep a
fresh compatible analysis in the demo account; older runs do not establish current prompt quality.
