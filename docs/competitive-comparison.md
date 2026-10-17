# Resonance and creator tools

Public product documentation and USD pricing checked **11 October 2026**. This is a
historical external-product snapshot compared with current Resonance source, not a hands-on
competitor benchmark. No competitor outputs, creator judgments or measured task times
have been collected. Feature availability varies by plan, region and rollout.

**The workflow the repository supports is an inspectable editorial review.** Specialist
findings link a moment, its explanation and a proposed edit to the video, and attributed
creator material feeds later writing and visual generation. Rubric review, editor filtering,
footage adjudication, creator decisions, cut-list/edit-plan exports and before/after revision review make
the loop inspectable and verified against single-prompt baselines ([evals](../evals/README.md));
longitudinal human time-saved comparisons against external commercial editors remain future work.

## Where the workflow differs

| Tool | Established workflow | Resonance's implemented distinction | Where the other tool is stronger |
|---|---|---|---|
| **Descript** | Underlord reads scripts, watches video, gives feedback and executes edits; transcript editing, cleanup, clips and media generation. [Product](https://www.descript.com/underlord) | Nine named review dimensions and a five-second seekable heatmap organize critique, evidence and proposed edits. Truth review can request Search grounding; footage tools are bounded. | Multicam/layouts, audio repair and finished clips. Resonance exports accepted cuts and edit notes; creators edit externally, upload a revision and compare re-review results. |
| **OpusClip** | ClipAnything uses visual, audio and sentiment cues to select moments, assemble clips and reframe them; paid workflows include captions and publishing. [Product](https://www.opus.pro/clipanything), [plans](https://www.opus.pro/pricing) | Reviews the source's factual support, clarity, safety and cultural fit as well as pacing; lets the creator inspect and revise specific advice before packaging. | Automated finished shorts, tracking/reframing and broader social distribution. Resonance does not currently cut source shorts automatically. |
| **YouTube Studio** | Retention from actual viewers; native title/thumbnail experiments; Ask Studio gives channel-aware ideas and feedback on scripts and unpublished videos. [Ask Studio](https://support.google.com/youtube/answer/16291691?hl=en) | An explicit multi-dimension review interface, editable transcript versions, localization glossary and downloadable media in one project. | First-party audience evidence, concurrent experiments and native channel operations. Resonance heatmap scores describe flagged moments, not predicted retention. |
| **ChatGPT** | Flexible critique, research and drafting; Projects retain files, instructions and shared context. Work can use tools and produce multi-step outputs. [Projects](https://learn.chatgpt.com/docs/projects), [usage](https://learn.chatgpt.com/docs/use-chatgpt) | A predefined video-review pipeline with a persistent player, timed findings, evidence references, revisions and media exports reduces the setup a creator must assemble. | General-purpose reasoning and flexible workflows. A well-prompted, context-rich ChatGPT project is a credible baseline; persistent context is not unique to Resonance. |
| **Gemini Apps** | Uploads and analyzes video; supports reusable instructions and reference files through [Gems](https://support.google.com/gemini/answer/15146780?hl=en). [Video uploads](https://support.google.com/gemini/answer/14903178?hl=en) | Converts video intelligence into structured review jobs, partial results, timed navigation and saved publishing assets. | Direct conversational video analysis with little setup. Gemini is also Resonance's model provider, so model intelligence itself is not an exclusive advantage. |

The current review dimensions are truth/evidence, clarity, pacing/retention, legal/safety,
cultural/localization, platform fit, audience/brand, emotional impact and conversion/CTA.
They are prompts over one shared model. Timestamp and quote normalization improves
traceability but does not establish factual correctness or calibrated severity. Legal and
safety findings are editorial judgments, not legal advice.

Creator retrieval is a separate design choice. Initial drafts retrieve attributed passages,
thumbnails retrieve original images as references, and packaging requests creator context.
Eligible findings can also receive separately attributed earlier-work examples after review.
**Heatmap reviewers and inline writing alternatives do not use semantic library retrieval.**
Do not describe every output as grounded in the creator's history.
See [architecture](architecture.md#creator-memory-and-embeddings) for the consumer boundaries.

## Price context

Representative individual plans, before taxes/promotions. Annual equivalents require
annual billing. Free plans exist for several tools; these paid options are not necessary
for every creator or a recommended stack to purchase together.

| Product | Monthly billing | Annual equivalent | Included allowance/context |
|---|---:|---:|---|
| [Descript Hobbyist](https://www.descript.com/pricing) | $24/month | $16/month | 10 media hours and 400 AI credits/month |
| Descript Creator | $35/month | $24/month | 30 media hours and 800 AI credits/month |
| [OpusClip Starter](https://www.opus.pro/pricing) | $15/month | — | 150 credits/month |
| OpusClip Pro | $29/month | $14.50/month ($174/year) | 300 credits/month |
| YouTube Studio | No separate creator-tool subscription | — | Eligibility applies to individual features |
| [ChatGPT Plus](https://learn.chatgpt.com/docs/pricing) | $20/month | — | Subscription limits; separate from API token billing |
| [Google AI Pro](https://gemini.google/us/subscriptions/) | $19.99/month, US | — | Gemini plus bundled benefits; regional prices vary |
| [Resonance scenario](costs.md#a-reproducible-example) | No retail plan established | — | Five-minute STT + assumed review tokens: **$0.1475 partial API subtotal** |

Descript meters media and AI separately; interactions have variable
[credit consumption](https://help.descript.com/billing-payments-plans/track-and-understand-your-media-minutes-and-ai-credits).
Credit counts are not counts of complete reviews. Gemini's upload documentation lists
five total video minutes without a paid Google AI plan and one hour with Pro/Ultra;
this affects baseline access, not review quality.

For illustration, ten five-minute reviews with the same assumed token usage sum to
**$1.475** in Resonance's STT/review components; 100 sum to **$14.75**. Search, footage
inputs, cleanup, rubric/editor/adjudicator passes, interest signals, library links, retries,
compute, storage, support and other generation are excluded.
These figures cannot establish savings against a full subscription or a sustainable
selling price. Measure total cost per completed review and per creator-accepted edit.

## Public productivity evidence

Descript's [LinkedIn case study](https://www.descript.com/customers/linkedin) reports
approximately **one hour saved per project** with transcript-first editing. OpusClip's
[Grant Cardone Enterprises case study](https://www.opus.pro/blog/how-this-veteran-social-media-marketer-at-grant-cardone-enterprises-increased-his-teams-daily-video-output-by-100-with-opusclip)
reports **50% less editing time**, **twice the daily video output** and **four-plus hours
saved daily** on shorts creation. These are vendor-published customer reports about
different workflows, without a shared experimental protocol. They establish market
context, not Resonance results or an effect a new creator can expect.

YouTube provides a stronger path for publication evidence: [retention key moments](https://support.google.com/youtube/answer/9314415?hl=en)
measure viewer behavior, while [native experiments](https://support.google.com/youtube/answer/16391400?hl=en)
compare up to three titles/thumbnails using watch time and may take up to two weeks.
[Automatic dubbing](https://support.google.com/youtube/answer/15569972) also overlaps with
localization; access and supported languages vary. Do not infer CTR or retention uplift
from Resonance's internal scores.

## Closer review competitors

[HookMaster](https://tryhookmaster.com/) advertises timestamped video feedback, brand/style
guidance, consultant chat and Auto Fix. [Retensis](https://retensis.com/) advertises
timestamped advice across five dimensions, creator memory, retention predictions and
YouTube data overlays. Both overlap more directly with editorial review than a clipper
does. Their prediction/accuracy claims were not independently evaluated here.
Resonance is not the only timestamped AI review tool, and it is not the only tool with
creator memory. What sets it apart is the combination: review breadth, inspectable evidence,
creator references and a Google Cloud implementation.

## What can be claimed now

The repository shows structured, source-linked editorial review and reusable creator
references. On pre-registered unseen editorial benchmarks (`HELD-OUT` + `LONG-FORM`, 54 planted
flaws across 11 videos), the nine multimodal specialists beat a single-prompt baseline
**53/54 (98.1%) vs 45/54 (83.3%)** (**8–0 discordant, exact two-sided sign test $p = 0.0078$;
9–0 on actionable medium+ issues, $p = 0.0039$**), and the shipped edited pipeline beats the
single prompt **52/54 (96.3%) vs 45/54 (83.3%)** on strict dimension matching (**8–1,
$p = 0.039$**) and **53/54 (98.1%)** on moment matching (**8–0, $p = 0.0078$**), while the
editor raises multi-reviewer precision from **34–41% to 78–91%**. Across all 59 unseen gold
issues (`HELD-OUT` + `LONG-FORM` + `REAL`), Resonance surfaces **57/59 (96.6%) vs 48/59 (81.4%)**
at the exact timestamp (**9–0, $p = 0.0039$**), including catching **4 of 5 (80%)** real
creator-admitted errors on `REAL` (`3/5` under `truth_evidence`-only matching, plus the Ukraine
`okraina`/`krajina` borderlands error caught by `cultural_localization` + `audience_brand`),
where the single all-rubric mega-prompt hit `429 RESOURCE_EXHAUSTED` and lost an entire real
video. Across all 20 benchmark videos, the nine specialists completed **180/180 (100%)** runs
and executed **1,136 live FFmpeg footage tool calls**. The [20-query retrieval diagnostic](../evals/README.md)
found the intended source first in **20/20 semantic versus 11/20 lexical** cases on its curated
corpus.

Those benchmarks compare Resonance's multi-agent architecture against single-prompt Gemini
baselines and lexical fallback on the same inputs; they do not benchmark external commercial
products. Before claiming an advantage over external tools on creator editing speed, run the
[creator comparison protocol](../evals/creator-comparison.md): same source and context,
competent baselines, complete outputs, human labels, and measured review effort.
