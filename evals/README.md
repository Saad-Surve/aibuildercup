# Evaluation evidence

What we measured, how, and what it does and does not show. Every result links to its raw
model responses, so it can be replayed offline without new model calls.

| Question | Result | Section |
|---|---|---|
| Do nine specialist multimodal reviewers beat dumping everything into one Gemini prompt? | **Yes, statistically significantly on unseen pre-registered sets.** Across 54 unseen planted flaws (`HELD-OUT` + `LONG-FORM`), specialists caught **53/54 (98.1%) vs 45/54 (83.3%)** for a single prompt (**8–0 discordant, two-sided sign test $p = 0.0078$; 9–0 on actionable medium+ issues, $p = 0.0039$**), and the shipped edited pipeline caught **52/54 (96.3%, 8–1, $p = 0.039$)** on strict dimension matching and **53/54 (98.1%, 8–0, $p = 0.0078$)** on moment matching. Across all 59 unseen gold issues (`HELD-OUT` + `LONG-FORM` + `REAL`), Resonance surfaced **57/59 (96.6%) vs 48/59 (81.4%)** at the exact timestamp (**9–0, $p = 0.0039$**). | [Editorial review](#editorial-review-nine-specialists-versus-one-prompt) |
| What happens on real creator videos when you dump all nine rubrics into one call? | On 4 real CC BY creator videos (5 post-publish corrections), the single all-rubric mega-prompt hit `429 RESOURCE_EXHAUSTED` on the 9-minute Ukraine video and lost the whole review (**2/5, 40%**). Resonance's chunked specialists completed **180/180 (100%)** runs across all 20 benchmark videos with **1,136 live FFmpeg footage tool calls**, catching **4/5 (80%)** real errors at the exact moment (all `medium` severity; **3/5** under strict `truth_evidence`-only matching) because its `cultural_localization` + `audience_brand` specialists caught John Green's Ukraine `okraina`/`krajina` borderlands mistake. | [Real creator videos](#real-creator-videos-pre-registered) |
| Does the editor stage make multi-reviewer output usable? | Precision rises from **34–41% to 78–91%** on unseen sets it was never tuned on (compressing raw findings by 55–65% and recording `corroboratedBy` agreement); with the rubric pass, zero issues are lost on long-form (**31/32, 97%**). | [Editorial review](#editorial-review-nine-specialists-versus-one-prompt) |
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

### Pooled unseen pre-registered results (`HELD-OUT` + `LONG-FORM` + `REAL`)

Each single set has 5–6 videos ($n = 5$ to $32$ issues), so reading one subset in isolation has
low statistical power. Pooling the independent, pre-registered unseen sets that were never
tuned on (`HELD-OUT` 22 + `LONG-FORM` 32 = **54 unseen planted issues** across 11 videos; plus
`REAL` 5 = **59 unseen gold issues** across 15 videos) answers the core architectural question
with exact paired binomial sign tests:

| Comparison on unseen pre-registered sets | Variant | Specialist / Resonance recall | Single-prompt recall | Paired discordant (Ours vs Single) | Exact sign test $p$ |
|---|---|---:|---:|---:|---:|
| **Nine specialists vs One prompt (`baseline`)** — 54 unseen planted issues (`HELD-OUT` + `LONG-FORM`) | `headline` (strict dimension + 5 s) | **53/54 (98.1%)** | 45/54 (83.3%) | **8 vs 0** | **$p = 0.0078$** (two-sided), **$0.0039$** (one-sided) |
| **Nine specialists vs One prompt (`baseline`)** — 54 unseen planted issues | `actionable` (severity ≥ medium) | **53/54 (98.1%)** | 44/54 (81.5%) | **9 vs 0** | **$p = 0.0039$** (two-sided), **$0.0020$** (one-sided) |
| **Shipped edited pipeline vs One prompt (`baseline`)** — 54 unseen planted issues | `headline` (strict dimension + 5 s) | **52/54 (96.3%)** | 45/54 (83.3%) | **8 vs 1** | **$p = 0.0391$** (two-sided), **$0.0195$** (one-sided) |
| **Shipped edited pipeline vs One prompt (`baseline`)** — 54 unseen planted issues | `timeOnly` (moment within 5 s) | **53/54 (98.1%)** | 45/54 (83.3%) | **8 vs 0** | **$p = 0.0078$** (two-sided), **$0.0039$** (one-sided) |
| **Shipped edited pipeline vs One prompt (`baseline`)** — all 59 unseen gold issues (`HELD-OUT` + `LONG-FORM` + `REAL`) | `timeOnly` (moment within 5 s) | **57/59 (96.6%)** | 48/59 (81.4%) | **9 vs 0** | **$p = 0.0039$** (two-sided), **$0.0020$** (one-sided) |
| **Shipped edited pipeline vs One prompt (`baseline`)** — all 59 unseen gold issues | `actionable` (severity ≥ medium) | **53/59 (89.8%)** | 46/59 (78.0%) | **8 vs 1** | **$p = 0.0391$** (two-sided), **$0.0195$** (one-sided) |
| **Resonance (`ensemble_edited`) vs One prompt + all 9 rubrics (`rubric`)** — 37 unseen issues (`LONG-FORM` + `REAL`) | `timeOnly` / `headline` | **35/37 (94.6%)** / **34/37 (91.9%)** | 30/37 (81.1%) / 30/37 (81.1%) | **5 vs 0** / **4 vs 0** | **$p = 0.0312$** / **$0.0625$** (one-sided) |

*(Note: Both `baseline` and `rubric` already receive Resonance's millisecond segment transcript,
reason-before-grade JSON schema, `SCORE_ANCHORS`, Google Search grounding, and deterministic
`normalize_findings` quote-verification gate, plus the entire raw MP4 inline.)*

**Why dumping everything into one context window loses to specialized multimodal agents:**
1. **Attention dilution across dimensions and duration.** When a single prompt must monitor nine
   competing rubrics across a full video simultaneously, it catches early or obvious errors but
   drops mid- and late-video pacing drags, unsupported claims and subtle omissions (missing 9 of
   54 unseen planted flaws at actionable severity that the specialists caught, while finding
   **zero** flaws the specialists missed).
2. **Domain-specific lenses catch what generalist fact-checking misses.** On John Green's real
   Ukraine video (`mMZYKxgc9TE`), `truth_evidence` missed his statement that Ukraine *"literally
   means borderlands"*, because "borderlands" is a common English gloss. The
   **Cultural & Localization** specialist (`cultural_localization`) caught it (`4:23–4:27`,
   `translation_trap`), explaining the Russian imperial `'okraina'` vs. Ukrainian `'krajina'`
   (homeland) etymology, corroborated by `audience_brand` and verified by `editor-v6`.
3. **Fault isolation vs. single-call blast radius.** Dumping a 9-minute MP4 + transcript + nine
   rubrics + Search into a single `rubric` request on `mMZYKxgc9TE` hit `429 RESOURCE_EXHAUSTED`
   and returned **0 findings for the entire video**. Across all 20 benchmark videos, Resonance's
   chunked specialists completed **180/180 (100%)** reviewer runs with zero lost dimensions,
   executing **1,136 live FFmpeg `extract_frame` / `cut_clip` tool calls** (`54–61` per video)
   to inspect frames and motion on demand rather than relying on coarse whole-video context.

### Long-form (pre-registered, frozen pipeline)

[Report](results/editorial-2026-10-14-longform-final-flash38.md). Precision counts any
finding that matches no planted issue as wrong, so it is a lower bound.

| Approach | Recall (`headline`) | Recall (`timeOnly`) | Precision | Clean-control findings | Footage tool calls | Citations | USD per video |
|---|---:|---:|---:|---:|---:|---:|---:|
| One prompt (`baseline`) | 27/32 (84%) | 27/32 (84%) | 100% | 2 | 0 | 13 | $0.069 |
| One prompt + rubrics (`rubric`) | 28/32 (88%) | 28/32 (88%) | 97% | 5 | 0 | 14 | $0.080 |
| Nine reviewers | 31/32 (97%) | 31/32 (97%) | 41% | 14 | 278 | 27 | $0.276 |
| Nine reviewers + editor | 29/32 (91%) | 30/32 (94%) | 88% | 4 | 278 | 25 | $0.342 |
| **Resonance (`ensemble_edited`)** | **31/32 (97%)** | **31/32 (97%)** | **91%** | 6 | **278** | **23** | $0.436 |

Resonance found every issue the plain single prompt found plus **4 it missed** (4–0 discordant),
and every issue the 9-rubric mega-prompt found plus **3 it missed** (3–0 discordant, including
`pacing_drag` and `unsupported_claim` where `rubric` dropped to 2/4). The editor cut the raw
reviewer output from 75 findings to 34 (all 34 carrying `corroboratedBy` agreement) without
losing a single issue. Within this 5-video subset alone ($n = 32$), a 3–0 split against `rubric`
has exact two-sided sign test $p = 0.25$ (4–0 vs `baseline` is $p = 0.125$); pooled with the
other unseen sets above, the advantage over a single prompt is statistically significant
($p = 0.0039$ to $0.039$).

### Held-out (pre-registered, short videos)

[Report](results/editorial-2026-10-14-heldout-flash38.md). This run predates the rubric pass,
so its shipped arm is `edited` (nine reviewers + `editor-v1`).

| Approach | Recall (`headline`) | Recall (`actionable`) | Recall (`timeOnly`) | Precision | Clean-control findings | Footage tool calls | USD per video |
|---|---:|---:|---:|---:|---:|---:|---:|
| One prompt (`baseline`) | 18/22 (82%) | 17/22 (77%) | 18/22 (82%) | 100% | 3 | 0 | $0.026 |
| One prompt + rubrics (`rubric`) | 20/22 (91%) | 20/22 (91%) | 21/22 (96%) | 95% | 2 | 0 | $0.035 |
| Nine reviewers | **22/22 (100%)** | **22/22 (100%)** | **22/22 (100%)** | 34% | 5 | 343 | $0.239 |
| **Nine reviewers + editor (`edited`)** | **21/22 (96%)** | 19/22 (86%) | **22/22 (100%)** | **78%** | **1** | **343** | $0.249 |

The nine specialists found **all 22 planted issues (100%)** at `medium+` severity—beating the
plain single prompt **4–0** on discordant issues (`22/22` vs `18/22`, and `22/22` vs `17/22` on
actionable recall where `baseline` missed both tangents and both unsupported claims) and beating
`rubric` **2–0** (`22/22` vs `20/22`). The editor kept **22/22 (100%)** of the moments on the
timeline (`timeOnly`), **21/22 (96%)** on strict dimension matching, and reduced clean-control
false alarms to **1** (fewer than both `baseline` [3] and `rubric` [2]). Because `editor-v1`
dropped one `broken_promise` dimension label that `rubric` kept (2 vs 1 discordant between
`edited` and `rubric`), Phase 4 added the rubric pass as a tenth input to the editor
(`ensemble_edited`), which then achieved **31/32 (97%)** on the long-form set with zero editor
losses.

### Real creator videos (pre-registered)

[Report](results/editorial-2026-10-14-real-final-flash38.md). Four real CC BY creator videos
(6–16 min) with five errors the creators corrected in their descriptions after publishing.
Only those five are labelled (`partialGold: true`), so this measures recall of known errors;
precision cannot be computed because unmatched findings may flag real unlabelled issues.

| Approach | Recall (`headline`: `truth_evidence` only) | Recall (`actionable`, sev ≥ medium) | Recall (`timeOnly`: exact moment) | Failed calls | Footage tool calls | USD per video |
|---|---:|---:|---:|---:|---:|---:|
| One prompt (`baseline`) | 3/5 (60%) | 2/5 (40%) | 3/5 (60%) | 0 | 0 | $0.058 |
| One prompt + rubrics (`rubric`) | 2/5 (40%) | 2/5 (40%) | 2/5 (40%) | **2** (lost `mMZYKxgc9TE`) | 0 | $0.049 |
| Nine reviewers | 2/5 (40%) | 2/5 (40%) | 3/5 (60%) | 0 | 230 | $0.271 |
| Nine reviewers + editor (`edited`) | 2/5 (40%) | 2/5 (40%) | 3/5 (60%) | 0 | 230 | $0.309 |
| **Resonance (`ensemble_edited`)** | **3/5 (60%)** | **3/5 (60%)** | **4/5 (80%)** | 2 (rubric pass only; all 9 specialists succeeded) | **230** | $0.364 |

What the four real creator videos show in detail (`editorial-2026-10-14-real-final-flash38.raw.json`):
1. **Call of Duty sales mix-up (`BBvze0lGcZg`, `0:25–0:36`):** Caught by every arm; Resonance's
   suggested fix matched John Green's pinned correction (*"the Call of Duty video game franchise
   has sold more copies..."*).
2. **Sierra Leone `bedaquiline` cohort error (`JhVJMO0wgTE`, `4:15–4:21`):** Caught by Resonance
   (*"Henry became one of the first patients in Sierra Leone..."*) and missed completely by the
   plain single prompt (`baseline`).
3. **Ukraine national languages (`mMZYKxgc9TE`, `0:16–0:26`):** Caught by Resonance's
   `truth_evidence` specialist, citing **Article 10 of the Constitution of Ukraine (Council of
   Europe / Verkhovna Rada)** via Google Search grounding.
4. **Ukraine `"borderlands"` etymology (`mMZYKxgc9TE`, `4:23–4:27`):** Caught by Resonance's
   **`cultural_localization` specialist** (finding `46605c6c340148bf9b3ac52fdfa1c71b`,
   corroborated by `audience_brand`, verified and kept by `editor-v6`), which quoted *"especially
   when the name of your country literally means borderlands, as Ukraine does"* and explained the
   Russian imperial `'okraina'` vs. Ukrainian `'krajina'` (homeland) etymology. Because
   `matching.json` restricted `factual_error` to `truth_evidence`, strict `headline` scoring
   counted this as a dimension mismatch (`3/5`), while the pre-registered `timeOnly` variant
   recorded it as a match (**`4/5, 80%`**). Meanwhile, `baseline` rated it `low` severity
   (dropping `baseline` to **2/5** on actionable recall), and `rubric` hit `429 RESOURCE_EXHAUSTED`
   when sending the whole 9-minute video + all nine rubrics in one request, returning **0 findings**
   on `mMZYKxgc9TE`.
5. **Cubase release year 2015 vs. 2019 (`FqYg-gjCrPw`):** Missed by all approaches.

### Dev set (post-hoc)

[Final dev run](results/editorial-2026-10-14-editor-v2-dev-v6.md). Tuned on these videos, so
these numbers show the tuning target, not generalisation: Resonance (`ensemble_edited`) achieved
**20/20 (100%)** recall at **87% precision** (1 clean-control finding, 285 footage tool calls),
versus 19/20 at 95% (3 clean-control findings) for `baseline` and 19/20 at 90% (1 clean-control
finding, 2 failed calls) for `rubric`. A model-judged
[audit](results/editorial-2026-10-14-flash38.audit.md) of the first dev run found that 41 of
51 unmatched reviewer findings were the same planted issue reported through another
reviewer's lens, and only 2 were wrong. That is what the editor was built to remove.

### What this supports, and what it does not

- **Supported (statistically significant across unseen pre-registered sets):** Across the 54
  unseen planted issues (`HELD-OUT` + `LONG-FORM`), the nine specialists beat a single prompt
  **53/54 (98.1%) vs 45/54 (83.3%)** (**8–0 discordant, two-sided $p = 0.0078$; 9–0 on actionable
  recall, $p = 0.0039$**), and the shipped edited pipeline beats a single prompt **52/54 vs 45/54**
  on strict dimension matching (**8–1, $p = 0.039$**) and **53/54 vs 45/54** on moment matching
  (**8–0, $p = 0.0078$**). Across all 59 unseen gold issues (`HELD-OUT` + `LONG-FORM` + `REAL`),
  Resonance leads **57/59 (96.6%) vs 48/59 (81.4%)** on moment detection (**9–0, $p = 0.0039$**).
- **Supported:** The editor turns raw multi-reviewer output (**34–41% precision**) into usable
  output (**78–91% precision**) on unseen sets it was never tuned on, while preserving
  cross-reviewer `corroboratedBy` provenance and losing **0 issues** on long-form (**31/32, 97%**).
- **Supported:** Specialized lenses and chunked execution isolate failures and catch domain
  nuances (`cultural_localization` catching the Ukraine `okraina`/`krajina` etymology trap; 180/180
  specialist runs succeeding across 20 videos with 1,136 live FFmpeg footage tool calls) where a
  single whole-video all-rubric call hit `429 RESOURCE_EXHAUSTED` and lost an entire real video.
- **Scope boundary:** Against the strongest single-call baseline (`rubric`, which already embeds
  all nine Resonance rubrics and normalisers) on `LONG-FORM` + `REAL` ($n = 37$), Resonance leads
  **34/37 vs 30/37** on `headline` (4–0 discordant, one-sided $p = 0.0625$) and **35/37 vs 30/37**
  on `timeOnly` (5–0 discordant, one-sided $p = 0.0312$). Constructed videos use synthetic speech
  over caption cards, so while 1,136 footage tool calls executed end to end, visual-only defects
  and human creator time saved still need a larger recorded study.

### Next measurement step: longitudinal creator study

The benchmark sets above establish pre-registered flaw detection (`DEV`, `HELD-OUT`, `LONG-FORM`)
and real creator-admitted error recall (`REAL`) across 20 videos (**180/180** complete
nine-reviewer runs on `gemini-3.8-flash` with **1,136** live FFmpeg footage tool calls). The next
step beyond fixed gold-issue recall is measuring human creator acceptance rates and editing time
saved across a longitudinal creator cohort ([protocol](creator-comparison.md)).

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
