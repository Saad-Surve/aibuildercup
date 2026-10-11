# Cost model

USD list prices checked against Google Cloud on **11 October 2026**. Examples below
are arithmetic scenarios, not measured invoices or a claim that every workflow is free.
Credits, free allowances, taxes, currency conversion and discounts are excluded.
For subscription context and its different denominator, see the
[creator-tool price comparison](competitive-comparison.md#price-context).

## Unit economics

| Component | Current basis | Example |
|---|---|---|
| Gemini review/writing | `gemini-3.8-flash`, global: $0.75/M input tokens, $3.75/M output tokens through 31 December 2026 | 45k input + 9k output/reasoning across nine reviewers: **$0.0675** |
| Chirp 3 / STT V2 | Standard recognition: $0.016/audio minute at the initial volume tier | Five minutes, one billed channel: **$0.08** |
| Draft generation | Same Flash scenario rate; use the actual configured writer/model | 8k input + 2k output/reasoning: **$0.0135** |
| Thumbnail output | Gemini 3.1 Flash Image, global, approximately $0.067 per 1K output | Four outputs: **$0.268**, before image/text inputs, planning and critique |
| Pro thumbnail output | Gemini 3 Pro Image, approximately $0.134 per 1K/2K output | Four outputs: **$0.536**, before inputs and text output |
| Text embeddings | Gemini Embedding 2: $0.20/M input text tokens | 100k indexed text tokens: **$0.02** once; repeat reads reuse stored vectors |
| Image embeddings | Gemini Embedding 2: $0.45/M input image tokens | Requires actual image-token usage; ten images does not establish token cost |
| Translation | NMT text translation: $20/M characters after allowances | 6,000 source characters, one target language: **$0.12** |
| English Neural2 dub | $16/M synthesized characters after allowances | 6,000 translated characters: **$0.096** |
| Other TTS voices | WaveNet: $4/M characters; Chirp 3 HD: $30/M characters after allowances | 6,000 characters: **$0.024 / $0.18** respectively |
| Google Search grounding | Gemini 3: $14/1,000 queries beyond the shared 5,000/month allowance | Three billable queries: **$0.042**; one model request can issue several queries |
| Optional Veo insert | Current code reserves six seconds × configured $0.40/second | **$2.40 reserved per insert**, at most two slots; a conservative reservation, not the provider invoice |

Gemini 3.8 Flash's global standard rates become **$1.50/M input and $7.50/M output on
1 January 2027**: the review example doubles to **$0.135**. Update configured prices
when introductory pricing ends. Regional endpoints can have different rates.
The local Flash-Lite example uses $0.25/M input and $1.50/M output, so the same token
counts are $0.02475; that arithmetic is not evidence of equivalent review quality.

Veo is configured for six-second 720p output without generated audio. Its current
published Fast tier lists $0.08/second for that output, or approximately $0.48 for six
seconds. The app deliberately reserves $2.40 using its configurable safety estimate.
Do not call the reserved amount actual spend, or apply one model/resolution price to
all Veo variants. No Veo generation was purchased for this evaluation.

STT uses ordinary `BatchRecognize`, not its opt-in dynamic-batch processing strategy.
The cheaper dynamic-batch rate must not be applied to current requests. Requests are
rounded to whole audio seconds and billed-channel behavior matters. Retranscriptions,
revisions and duplicate accepted upstream operations add recognition charges.

## A reproducible example

[The scenario](../evals/cost-scenario.json) specifies a five-minute video, nine
reviewers totaling 45k input / 9k output tokens, cleanup (4k/1k), one draft (8k/2k),
four 1K thumbnail outputs, translation of 6,000 characters, an adaptation pass (5k/1k)
and 6,000 characters of English Neural2 speech. Adaptation/cleanup here assume the
Flash tier; actual model settings must match the selected rate. The deployment workflow
does not currently override `MODEL_LOCALIZATION`, so its default adaptation model is
Flash-Lite even though `.env.deploy.example` recommends Flash. The calculator deliberately
uses the more expensive Flash assumption for adaptation; it is not a deployment trace.

| Chosen stages | Model/API component subtotal |
|---|---:|
| Transcription + review | **$0.1475** |
| Above + four thumbnail outputs | **$0.4155** |
| All listed scenario stages | **$0.65925** |

Recalculate from repository root:

```bash
uv run --project backend python backend/scripts/estimate_cost.py
```

The [machine-readable result](../evals/results/cost-scenario.json) preserves all
quantities and rates. These are **partial component subtotals**, not an all-in price:
Search, image inputs/text output, thumbnail planning/critique, persona research,
packaging generation, embeddings, compute, storage, egress and retries are omitted.
No margin, subscription price or profitable unit economics can be inferred from them.

## Compute, storage and network

The deployment uses `--no-cpu-throttling` so background work continues after the HTTP
response. Cloud Run therefore bills the instance's allocated lifetime, including idle
periods before scaling down; an API response time is not a compute-cost measurement.
At the published `us-central1` instance-based rate, **one vCPU + 1 GiB for 300 seconds
is $0.006** before free allowances: `300 × (0.000018 + 0.000002)`.
A continuously allocated instance for 30 days would be **$51.84** under that assumption.
Actual lifetime/allocation must come from Cloud Monitoring and Billing. Min-instances
zero permits scale-to-zero; max-instances one limits aggregate compute but also throughput.

Storage costs include source videos, output MP4/audio, thumbnails, retained revisions,
operations and data transfer. Versioned buckets also retain noncurrent objects. The
configured lifecycle expires noncurrent versions; deleting a live object alone is not
immediate removal of every stored generation. Measure GB-months and actual egress before
quoting an all-in per-video cost. Direct browser upload reduces API memory/proxy work;
it does not eliminate Storage or network charges.

Firestore batches up to 400 writes per commit to reduce RPC overhead. It still charges
per document operation. Semantic search loads vectors into Python and reads source/query
records; cached query embeddings avoid a model call, not all database reads. The 80-node
corpus needs **245,760 bytes of float32 vector values** in theory; Firestore arrays, indexes,
Python floats and metadata occupy more space. This is not measured Firestore storage size.

## What the guards actually enforce

| Guard | Behavior | Boundary |
|---|---|---|
| Analysis | Refuses a new run after stored analysis estimates reach `MAX_PROJECT_COST_USD=5` | No atomic reservation for the next run; incomplete category coverage and concurrent jobs can overshoot. |
| Thumbnails | Checks prior stored image estimates plus requested count against a separate $5 image budget; max four concepts/request | A flat $0.067 estimate also applies to Pro versions, so it understates Pro/input costs. No shared all-feature ledger. |
| Embeddings | Up to 200 atomic daily call slots per user; up to 16 missing nodes per index request; 300 nodes/ten images per library | A call-count bound, not a dollar cap. Operator preset publication has a separate explicit call limit. |
| Veo | Up to two project-owned paid reservations, also bounded by `floor($5 / estimated insert cost)`; one operation per submission, resumable polling | Reservations remain after uncertain/failed work; conservative cost is separate from actual billing. |
| Concurrency | Four reviewers and four TTS requests by default; one deployed API instance | Controls pressure, not total usage across all workflows. |
| Cloud budget | ₹8,500 configured budget with notifications and billing-detachment function | Billing data/notifications are delayed. This is a backstop, not an immediate hard cap. |

The [latest production diagnosis](current-progress/2026-10-11-1639-provider-429-diagnosis.md)
found twelve successful STT operations for one upload after polling failures triggered
resubmissions. Job-document idempotency does not prevent duplicates inside a provider's
retry loop. Separating submission from polling is a concrete reliability and cost fix;
its benefit must be measured after implementation. Image retries currently use a short
backoff window and do not provide shared pacing across jobs.

## How to report measured spend

For each workflow, record model/location/prompt version, input tokens, output **including
reasoning**, actual Search query count, billed audio seconds/channels, source and target
characters, image model/resolution and references, embedding usage, accepted operation
names and retries. Record wall time and instance lifetime separately. Sum stage costs,
then reconcile against Billing export by SKU/date; amortize corpus indexing across its
actual reuse. The current provider includes reasoning tokens in output estimates.

Useful metrics are **cost per completed review**, **cost per creator-accepted edit**,
**cost per exported asset**, failure-wasted spend and p50/p95 job cost. Their denominators
must include failures/retries where relevant. No invoice-backed totals or creator-accepted
edit counts were available for this report.

## Sources

- [Gemini, embeddings, image generation, grounding and Veo pricing](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing)
- [Speech-to-Text pricing](https://cloud.google.com/speech-to-text/pricing)
- [Translation pricing](https://cloud.google.com/translate/pricing)
- [Text-to-Speech pricing](https://cloud.google.com/text-to-speech/pricing)
- [Cloud Run pricing](https://cloud.google.com/run/pricing)
- [Cloud Storage pricing](https://cloud.google.com/storage/pricing)
- Implementation: `backend/app/config.py`, `services/cost.py`, `services/analysis_service.py`,
  `services/thumbnail_service.py`, `services/creator_library_service.py`,
  `services/packaging_service.py`, `.github/workflows/deploy.yml`, `infra/budget.tf`.
