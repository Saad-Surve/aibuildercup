# Evaluation evidence

What we measured, how, and what it does and does not show. Every result links to its raw
model responses, so it can be replayed offline without new model calls.

| Question | Result | Section |
|---|---|---|
| Do nine specialist reviewers beat one Gemini prompt? | On pre-registered long-form videos: **31/32 planted issues vs 28/32** for the best single prompt, 91% precision; not yet significant. On short videos and on 5 real creator-admitted errors, a tie. | [Editorial review](#editorial-review-nine-specialists-versus-one-prompt) |
| Does the editor stage make multi-reviewer output usable? | Precision **34–41% to 78–91%** on sets it was never tuned on; with the rubric pass, no issue lost on long-form | [Editorial review](#editorial-review-nine-specialists-versus-one-prompt) |
| Can it predict where viewers lean in or drift? | **ρ = 0.15** (95% CI 0.10–0.20) beyond the typical drop-off, over 87 unseen creator videos | [Audience interest](#predicted-audience-interest) |
| Does semantic search find the creator's right source? | **20/20** first-rank hits vs 11/20 for keyword fallback | [Creator retrieval](#creator-retrieval-semantic-versus-keyword-fallback) |

Costs are explicit scenarios in [docs/costs.md](../docs/costs.md), not invoices. Every run
file is indexed in [results/README.md](results/README.md). The
[creator comparison protocol](creator-comparison.md) and
[market comparison](../docs/competitive-comparison.md) cover what is not yet measured
against other tools.

## Editorial review: nine specialists versus one prompt

The question every judge should ask: **why not just ask Gemini?** We tested it with a
gold-issue benchmark. Videos carry planted flaws in 11 categories (wrong facts, unsupported
claims, safety, jargon, tangents, pacing drag, weak hooks, broken promises, locale
assumptions, tone, missing calls to action) plus clean controls with nothing to find. Every
approach reviews the same videos with the same model (`gemini-3.8-flash`, Search grounding
on), and is scored with one fixed matching rule ([matching.json](editorial/matching.json):
same dimension, start within 5 seconds, one finding per issue).

| Approach | What it is |
|---|---|
| One prompt | One Gemini call over the whole video and transcript |
| One prompt + rubrics | The same call with all nine reviewer rubrics pasted in: the strongest single-prompt baseline |
| Nine reviewers | The nine specialist reviewers, raw |
| Nine reviewers + editor | An editor stage merges duplicates and drops weak findings |
| **Resonance** | Nine reviewers plus the rubric pass as a tenth, then the editor (`ensemble_edited`, the shipped pipeline) |

**How we kept it honest.** Labels for every set are committed before any model sees the
videos, and the harness refuses to run if they changed. The prompts were tuned only on the
DEV set and frozen before the later sets ran. The HELD-OUT and LONG-FORM sets were authored by
a different model family with no access to the reviewer prompts. Each pre-registered set was
run once.

| Set | Videos | Issues | Labels committed | Role |
|---|---:|---:|---|---|
| [DEV](editorial/README.md) | 5 short (2–3 min) | 20 | `2e13571` | Tuning; results are post-hoc |
| [HELD-OUT](editorial-heldout/README.md) | 6 short (2–4 min) | 22 | `6df94ce` | First independent test |
| [LONG-FORM](editorial-longform/README.md) | 5 long (8–12 min) | 32 | `9d48bf5` | Independent test at real creator length |
| [REAL](editorial-real/README.md) | 4 real CC BY creator videos (6–16 min) | 5 | `6f1f23f` | Errors the creators publicly corrected; recall only |

### Long-form (pre-registered, frozen pipeline)

[Report](results/editorial-2026-10-14-longform-final-flash38.md). Precision counts any
finding that matches no planted issue as wrong, so it is a lower bound.

| Approach | Recall | Precision | Clean-control findings | USD per video |
|---|---:|---:|---:|---:|
| One prompt | 27/32 (84%) | 100% | 2 | $0.069 |
| One prompt + rubrics | 28/32 (88%) | 97% | 5 | $0.080 |
| Nine reviewers | 31/32 (97%) | 41% | 14 | $0.276 |
| Nine reviewers + editor | 29/32 (91%) | 88% | 4 | $0.342 |
| **Resonance** | **31/32 (97%)** | **91%** | 6 | $0.436 |

Resonance found every issue the best single prompt found, plus three it missed (paired by
issue: 3 versus 0), including pacing drag and unsupported claims. The editor cut the raw
reviewer output from 75 findings to 34 without losing an issue. With 32 issues, a 3–0 split is
**not statistically significant** (exact sign test p = 0.25); it is a consistent direction, not
proof. Resonance costs about five times the single prompt per video.

### Held-out (pre-registered, short videos)

[Report](results/editorial-2026-10-14-heldout-flash38.md). This run predates the rubric pass,
so it has no Resonance row; the editor was version 1.

| Approach | Recall | Precision | Clean-control findings | USD per video |
|---|---:|---:|---:|---:|
| One prompt | 18/22 (82%) | 100% | 3 | $0.026 |
| One prompt + rubrics | 20/22 (91%) | 95% | 2 | $0.035 |
| Nine reviewers | 22/22 (100%) | 34% | 5 | $0.239 |
| Nine reviewers + editor | 21/22 (96%) | 78% | 1 | $0.249 |

On short videos the strongest single prompt **matched** the reviewers: 2 issues only the
editor arm found, 1 only the single prompt found. This result is why the rubric pass became a
tenth reviewer, and why we built the long-form set to test our hypothesis that specialists pay
off on longer videos, where one call has more to hold at once.

### Real creator videos (pre-registered)

[Report](results/editorial-2026-10-14-real-final-flash38.md). Four real CC BY creator videos
(6–16 min) with five errors the creators corrected in their descriptions after publishing.
Only those five are labelled, so this measures recall of known errors; precision cannot be
computed.

| Approach | Known errors found | USD per video |
|---|---:|---:|
| One prompt | 3/5 | $0.058 |
| One prompt + rubrics | 2/5 (its call failed on one video with two errors) | $0.049 |
| Nine reviewers | 2/5 | $0.271 |
| Nine reviewers + editor | 2/5 | $0.309 |
| **Resonance** | **3/5** | $0.364 |

Every approach caught John Green's Call of Duty sales mix-up, and Resonance's suggested fix
matched his published correction (say "the franchise", not one game). No approach caught a
software release year misstated as 2015 instead of 2019, which needs niche product knowledge.
Resonance and the single prompt tie at 3/5 and found different errors. Five errors is far too
few to rank approaches; this set shows the pipeline finds real, creator-admitted mistakes, not
that it beats a single prompt on them.

### Dev set (post-hoc)

[Final dev run](results/editorial-2026-10-14-editor-v2-dev-v6.md). Tuned on these videos, so
these numbers show the tuning target, not generalisation: one prompt + rubrics 19/20 at 90%
precision; Resonance 20/20 at 87%, one clean-control finding each. A model-judged
[audit](results/editorial-2026-10-14-flash38.audit.md) of the first dev run found that 41 of
51 unmatched reviewer findings were the same planted issue reported through another
reviewer's lens, and only 2 were wrong. That is what the editor was built to remove.

### What this supports, and what it does not

- Supported: on pre-registered long-form videos, the shipped pipeline caught more planted
  issues than the best single prompt, missed none that it caught, and kept precision at 91%.
- Supported: the editor turns raw multi-reviewer output (34–41% precision) into usable
  output (78–91%) on sets it was never tuned on. On its own it dropped one or two real
  issues per set; adding the rubric pass as a tenth reviewer recovered them on long-form.
- Not supported: a significant accuracy advantage. The sets are small (5–6 videos each), and
  on short videos a single prompt matched us.
- Not measured: accuracy on unconstructed creator videos beyond creator-admitted errors,
  usefulness of the proposed edits, and time saved. Constructed videos use synthetic speech
  over a plain background, so footage-based checks are barely exercised.

### Still to measure: creator-judged quality

The flagship needs two kinds of evidence: correct observations and edits the creator
actually finds useful. A creator supplied a project and public source-video link; complete
outputs and creator labels are still pending. No manual gold labels or time-saving
measurements were supplied. Historical diagnostic reviewer runs are recorded in
the reviewer heatmap handoff in [HANDOFF](../docs/current-progress/HANDOFF.md#open-items);
they used a fallback model/subsets and cannot validate the complete configured nine-reviewer
system. Finding counts and successful JSON alone are not quality scores.

A bounded first quality study can use six short videos: English and Hindi/Hinglish examples
of a factual explainer, a buying recommendation and a clean control. Include intentional
errors **and correct claims**, label relevant spans/actions before generation, pin source,
transcript, persona, model, location and prompt versions, and report failures. Have two
independent editors score outputs blind to configuration. Resolve disagreements openly.
Do not count the supplied persona or model self-critique as independent judgment.

| Area | Metric and denominator | What it establishes |
|---|---|---|
| Reliability | Successful reviewer/chunk calls ÷ attempted calls; complete runs ÷ started runs; p50/p95 time to first finding and completion | Whether useful results arrive consistently, including errors/retries |
| Review correctness | Supported/actionable issue findings ÷ all emitted issue findings | Precision, adjudicated against transcript, footage and cited sources |
| Missed issues | Gold issues matched by one supported finding ÷ all gold issues | Recall; match once within the same dimension using span IoU ≥0.5, with separately declared point-event tolerance |
| False alarms | Unsupported high/critical findings per video minute; proportion of clean controls wrongly flagged | Over-warning and harmful advice |
| Evidence | Nonempty speech quotes matching cited spans ÷ nonempty speech quotes; citations that entail the claim ÷ citations checked | Quote consistency versus actual factual support; report omitted/visual evidence separately |
| Advice quality | Specific executable edits ÷ issue findings; creator-accepted useful edits ÷ proposed edits | Practical value, preserving language, intent and voice |
| Redundancy | Semantically repeated advice ÷ issue findings, judged across dimensions | Whether nine reviewers create unnecessary work |
| Stability | Matched findings across two pinned runs; severity agreement on matched spans | Stochastic variation, not truth |
| Cost | Total attributable model/API/compute cost ÷ completed reviews and ÷ accepted useful edits | Efficiency with a meaningful denominator |

Use one-to-one gold/prediction matching so duplicate findings cannot inflate recall.
Report per dimension and per video, not only a pooled average; show sample counts and
bootstrap uncertainty by video when a representative dataset is large enough. Repeated
runs of the same six videos do not create more independent videos.

Useful ablations are transcript-only versus sampled footage, Search on/off for truth,
and initial writing with/without retrieved history. Keep everything else pinned and use
identical human judgments. Base review calls are `9 × chunks`; tools, grounding and
provider retries can add requests. Cap each study's calls and monitor spend before launching
another batch; current project estimates are not an atomic all-feature spending limit.

## Predicted audience interest

[Full report](interest/README.md), measured on 13 October 2026 and retrained on 14 October. The heatmap's interest lane is
a ridge model over transcript features and Gemini per-moment signals. It is labelled with
YouTube's public Most Replayed graph (normalised within each video, not retention) and trained
on 87 long-form creator videos plus a Content Behavior Corpus sample. In grouped
cross-validation over creator channels, its deviations from the typical drop-off correlate
with the real ones at **ρ = 0.15 (95% CI 0.10–0.20)**. Predicted dips land in the true
bottom quarter **35%** of the time and peaks in the true top quarter **35%**, against 25% by
chance. Transcript statistics alone are barely above chance (ρ = 0.07). The Gemini signals
carry the effect.

## Creator retrieval: semantic versus keyword fallback

The benchmark uses the actual Arun Prabhudesai corpus: 20 source items (14 videos,
five authored posts, one editorial biography), plus a supplied profile; 70 text nodes
and ten image nodes. All 80 cached Gemini Embedding 2 vectors passed dimension,
finiteness, unit-norm and content-identity validation. The configured space has 768
dimensions; 15 additional passages were omitted by the per-source sampling bound.

[Cases](creator-retrieval.json) were written and labeled **before** query inference.
They cover twelve English text queries, four Hindi text queries and four text-to-image
queries. Each label identifies an intended source item. This is a curated, author-labeled
relevance diagnostic on a known corpus, not an independently adjudicated or held-out dataset.

| Cohort | n | Semantic hit@1 | Keyword hit@1 | Semantic MRR@8 | Keyword MRR@8 |
|---|---:|---:|---:|---:|---:|
| English text | 12 | 12/12 | 8/12 | 1.000 | 0.691 |
| Hindi text | 4 | 4/4 | 0/4 | 1.000 | 0.042 |
| Text → thumbnail | 4 | 4/4 | 3/4 | 1.000 | 0.875 |
| **All cases** | **20** | **20/20** | **11/20** | **1.000** | **0.598** |

Overall hit@3 was **20/20 versus 12/20**; hit@8 was **20/20 versus 15/20**. The gap is
largest for Hindi requests that target English creator writing. These cases do not establish
general retrieval accuracy, and they do not show that downstream drafts or thumbnails improve.

The harness imports the production passage builder, vector validator and cosine helper.
It uses the same query prefix, lexical token overlap and stable score/node-ID ordering as
`CreatorLibraryService.search`. Results are passage-ranked with the application's top-eight
cutoff; repeated passages from one item occupy multiple slots. A hit means the intended
source appears at or before the rank; MRR@8 averages the reciprocal of its first rank,
using zero when absent. It is not passage-level entailment or recall over all useful sources.

Each cohort filters candidate modality. The public library search normally mixes modalities,
and thumbnail retrieval filters to images. The diagnostic therefore isolates text and image
retrieval and does not exercise the full public API. Image embeddings include a title next to
the real image, so text-to-image success cannot be credited to visual content alone. Several
queries name a product or source topic. The next dataset expansion should add hard negatives,
ambiguous relevance, image-only ablations and unrelated creators.

## Runtime components

[The first live report](results/2026-10-11.json) preserves query ranks, all latency
samples, corpus/case/vector hashes, source revision and machine metadata. Twenty query
embeddings completed on the global endpoint; they were cached locally. The
[offline replay](results/2026-10-11-replay.json) made **zero new model calls** and
reproduced every retrieval metric. Timing values naturally vary between runs.
The replay also hashes the benchmark and production implementation files, since a Git
revision alone cannot identify the dirty working tree used for these measurements.

| Component | Median | p95 | Scope |
|---|---:|---:|---|
| Query embedding provider call | 443.7 ms | 702.5 ms | Twenty real sequential requests; includes the first client's cold setup. Max 3,678.8 ms. |
| Cosine scoring + sort | 1.36 ms | 2.43 ms | 100 warmed local runs, 80 real 768-vectors; excludes embedding, Firestore, signing and network. |
| PCA projection | 3.53 ms | 3.56 ms | Seven warmed local runs, same 80 vectors; includes no UI rendering. |

These are component measurements on one Darwin/ARM64 machine, not production endpoint
latency, throughput capacity or an SLA. A twenty-request p95 is especially noisy.
The float32 vector-value footprint is `80 × 768 × 4 = 245,760 bytes` (240 KiB), excluding
metadata, Firestore representation/indexes and Python object overhead.

## Media metadata benchmark

The current staging code combines dimensions and duration into one ffprobe call.
The comparator invokes the existing separate size and duration probes on the same file.
One warmup per method precedes seven repetitions, alternating method order. Both methods
returned identical metadata for every fixture; hashes and samples are in the live report.

| Real video | Duration | Two probes, median | Combined, median | Reduction |
|---|---:|---:|---:|---:|
| `tech_review.mp4` | 318.252 s | 105.92 ms | 53.06 ms | 49.9% |
| `explainer.mp4` | 538.122 s | 117.23 ms | 58.13 ms | 50.4% |
| `hindi_education.mp4` | 242.927 s | 118.62 ms | 59.31 ms | 50.0% |

This is a repeated local component comparison. It does not show that transcription or dubbing
became twice as fast. The avoided second process and scan account for most of the local difference.

## Frontend payloads

The repository optimization pass (October 2026) recorded an inter-build webpack comparison
under the same environment:

| Exported route | Before gzip bytes | After gzip bytes | Reduction |
|---|---:|---:|---:|
| Project workspace | 868,473 | 399,302 | 54.0% |
| Dashboard | 630,079 | 418,564 | 33.6% |
| Onboarding | 559,601 | 346,429 | 38.1% |
| Landing | 300,701 | 301,699 | −0.3% |

The current benchmark also records raw/per-file gzip script sizes from the default
Turbopack export. Do not compare its absolute bytes directly with the historical webpack
baseline. Both measurements count unique script URLs referenced by route HTML, not chunks
loaded after authentication/workspace mounting, CSS, media or observed CDN transfer.
No LCP, INP or creator task-time improvement is inferred from script sizes.

## Reproduce

From repository root, using the already collected/indexed local corpus:

```bash
# Build the current web export.
cd web
bun run build
cd ..

# Offline replay after queries have been cached locally.
uv run --project backend python backend/scripts/benchmark.py \
  --corpus .tmp/creator-libraries/arun-prabhudesai \
  --media fixtures/media/tech_review.mp4 fixtures/media/explainer.mp4 \
          fixtures/media/hindi_education.mp4 \
  --web-bundler turbopack \
  --output .tmp/evals/replay.json
```

For a first query run, add `--embed-queries --max-calls 20`. That permits at most twenty
embedding submissions and caches successful vectors after each response. A retry/resume
only requests missing queries. There are no generation jobs, Firestore/Storage writes,
model fallbacks or silently fabricated vectors. Model/API errors stop the run; offline
replay fails if its cache is incomplete. Provider costs are not included in the script's
report because this wrapper does not return billable token usage.

The corpus and media are gitignored originals, not shipped with the benchmark report.
See [collection/import instructions](../docs/creator-public-corpus.md) to prepare access.
Recollecting changing public sources creates a different corpus; hashes must match to
reproduce this exact result. Query vectors remain in `.tmp/evals/query-vectors.json`.
The report shares IDs/ranks, not full third-party transcripts or private credentials.

## Other outcomes to measure

| Workflow | Quantitative evaluation |
|---|---|
| Transcript | WER/CER against independently transcribed speech; timing error; speaker attribution accuracy; raw Chirp versus cleanup. Hindi needs CER alongside tokenization-sensitive WER. |
| Localization | Required-term preservation; meaning/voice/idiom ratings by native speakers; mistranslations per 1,000 characters; compare raw translation with adaptation. |
| Dubbing | Segment clipping/padding rate, timing error and native-listener naturalness; selected voice/language reported separately. |
| Thumbnails/listings | Source-supported promise, brand/identity fidelity, legibility at feed size and creator selection rate. CTR needs an actual controlled publication experiment. |
| Visual inserts | Source-number/unit validity for charts, supported quote/span rate, useful-suggestion acceptance and paid render failure/resumption rate. |
| Creator impact | Paired manual versus studio task time for the same review/package task; blind final-output quality and creator-rated usefulness. Counterbalance task order. |
| UX | Task completion rate, errors, navigation steps, mobile/keyboard completion and measured LCP/INP. |
| Scale/deletion | Real concurrent workload p50/p95, duplicate-operation rate, backlog recovery, and remaining owned records/live objects/noncurrent generations after deletion. |

Time saving is `(manual time − studio time) / manual time`; include time spent checking
AI suggestions. Cost per accepted edit must include rejected suggestions and failed work.
Improvements in retention, audience growth, publishing frequency or accessibility outcomes
remain unmeasured until actual users/viewers participate.
