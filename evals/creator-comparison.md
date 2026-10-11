# Creator comparison protocol

This protocol measures the [competitive hypotheses](../docs/competitive-comparison.md).
No head-to-head quality, creator time or accepted-edit results have been collected.

## First supplied example

| Field | Evidence/status |
|---|---|
| Resonance project | [bbf2c874926d4b3ba79063ab5d4961e9](https://habeas-codus.web.app/projects/view?projectId=bbf2c874926d4b3ba79063ab5d4961e9) |
| Public video | [YouTube ga53h0I-sO0](https://www.youtube.com/watch?v=ga53h0I-sO0) |
| Public metadata | YouTube oEmbed returned **“Top 5 Best Smartphones Under ₹60000 ⚡ September 2026”**, **Trakin Tech**, on 11 October 2026. Metadata alone does not verify the uploaded asset, footage, duration or language. |
| Project inspection | Shared browser's read-only demo returned “Project not found” / no access. Owner-session access or an output export is needed; no findings have been scored. |
| Creator labels | Pending: useful, wrong/unsupported and generic findings, with reasons |
| Competitor runs | None; outputs are optional for starting a Resonance-only case study |

The public video is a buying recommendation. Check price date, region, variant and
conditions when assessing factual flags; today's specification or price may not settle
a claim made at publication time. Verify that the uploaded source uses the same cut and
timestamp origin before matching any findings to the public video.

## Minimum material from the creator

1. **Complete Resonance output:** all findings, including positives, duplicates and
   failures; timed transcript; chosen asset/revision and analysis run. JSON is ideal;
   pasted complete text and SRT/VTT are sufficient. Do not select only favorable examples.
2. **Intended audience and purpose:** who the video serves, desired takeaway, language
   and any non-negotiable terminology or sponsorship/disclosure constraints.
3. **First judgments:** three findings worth acting on, and any wrong or generic findings.
   Use `timestamp | finding title/ID | useful / wrong / generic | reason | edit I'd make`.
   These selected examples support a qualitative case study, not a precision estimate.

No competitor output or analytics is required to start. No credentials are needed in
chat. Access to an authenticated project may substitute for an export. A public video
does not imply that private project outputs are publicly accessible.

## Turn the example into measurable evidence

Preserve the original run before regenerating. Record asset/transcript hashes, run time,
reviewer coverage, model/location/prompt versions, tools, grounding sources, failures and
reported usage. Distinguish source quotes that match from citations that actually support
the verdict. Inspect footage for visual claims; transcript-only review cannot settle them.

Label **every issue finding**, preferably with a second editor blind to the tool. Store
correctness, actionability, duplicate group, creator usefulness and accepted change as
separate fields. “Generic” can be correct but unhelpful; “useful” does not by itself prove
truth. Keep positive observations separate from issue precision.

| Metric | Denominator / collection |
|---|---|
| Supported issue precision | Supported issue findings ÷ all issue findings; unresolved items reported separately |
| Useful edit rate | Creator-accepted useful proposed edits ÷ all proposed edits |
| Unsupported severe warnings | Unsupported high/critical issue findings per source-video minute |
| Redundancy | Duplicate issue findings ÷ all issue findings; group across dimensions |
| Review effort | Active minutes to inspect all results, check sources and decide edits; wall-clock generation reported separately |
| Cost efficiency | Total attributable cost, including failures, ÷ completed reviews and ÷ accepted useful edits |

Report counts beside rates and the number of unique accepted edits. Recall requires
independent source review with gold issues defined before seeing outputs; no recall from
the model's own findings. A single project is a worked example, not population evidence.

## A fair baseline

For editorial critique, compare Resonance with **Descript Underlord, Ask Studio and a
well-prompted Gemini/ChatGPT workflow**, where available. Give each the same source,
timed transcript, brief and permitted creator references. Record input restrictions;
if one tool cannot consume footage, report it as a separate transcript-only condition.
Allow equivalent follow-up opportunity and record it. Freeze prompts before scoring.

Use this common brief, with the actual audience/context filled in:

> Review this video for its intended audience. Identify supported strengths and issues
> in factual evidence, clarity, pacing, safety, cultural fit, platform fit, brand voice,
> emotional impact and CTA. For each, provide timestamp/span, quote or visual evidence,
> explanation and a specific proposed edit. Verify checkable hard claims with sources
> when available; distinguish uncertainty and opinion. Preserve the creator's language
> and intent, avoid duplicate advice and unsupported retention predictions. Return no
> issue when the source does not justify one.

Randomize and anonymize outputs for correctness/usefulness scoring; separately evaluate
each native interface for navigation and task time. Keep technical judges or model
self-grading separate from creator/editor judgment. To test efficiency, counterbalance
tools across matched videos; repeating the same video after reviewing another tool's
advice contaminates task-time comparisons. Include source-review and setup time, disclose
prior tool familiarity, and record manual fallback after failures.

**OpusClip needs a separate clipping task:** source to publishable vertical clips, measuring
coherence, factual/visual fidelity, caption accuracy, subject tracking, manual corrections,
time and exported assets. Current Resonance automatic source clipping is unimplemented;
include the external editor's work if evaluating a combined Resonance workflow.

Start with this example to refine labels, then use held-out Hindi/Hinglish and English
videos with clean controls and two human reviewers. Do not tune on the reporting set.
Use the [broader evaluation definitions](README.md#editorial-quality-protocol-not-results)
for gold matching, reliability, uncertainty and ablations. Publication CTR/retention
needs actual controlled viewer evidence; a before/after upload is confounded by topic,
audience and distribution changes.
