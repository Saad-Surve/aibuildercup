# Reviewer heatmap audit and GitHub inspiration

Research date: 2026-10-11. The initial audit below describes the code before implementation;
it involved no feature changes or live model calls. Subsequent implementation and bounded
live validation are recorded at the end and in the implementation handoff. The initial
recommendations are possibilities, not commitments to expand the feature.

## Why six appear when nine are promised

Nine active reviewer classes exist in `backend/app/agents/analysis_coordinator.py`. The design intentionally distinguishes six core dimensions from three extended dimensions:

| Always included | Available only when requested |
| --- | --- |
| Truth & Evidence | Audience & Brand |
| Spoken Clarity | Emotional Impact |
| Pacing & Retention | Conversion & CTA |
| Legal & Safety | |
| Culture & Localization | |
| Platform Dynamics | |

The exact request chain is:

1. `web/src/components/projects/review-panel.tsx:174` calls `startAnalysis(projectId, { platform })`. It has no dimension selector and supplies no extended dimensions.
2. `AnalysisRequest.dimensions` defaults to an empty list.
3. `backend/app/schemas/analysis.py:72` resolves six core dimensions plus any requested extras. An empty request therefore selects exactly six.
4. `AnalysisService.create_run` creates reviewer documents only for those selected dimensions.
5. The web renders `run.requestedDimensions`, correctly reflecting the six reviewers that actually ran.

The promise is in `web/src/lib/studio.ts:47`: “Nine reviewers score the cut and pin findings to the timeline heatmap.” The API contract explicitly describes `dimensions` as extended dimensions to add, with core dimensions always running (`contracts/openapi.yaml:2476`). This is an unwired product capability and inaccurate copy, rather than three reviewers being hidden after completing.

History confirms the distinction: commit `699979c02527336d1e0dea467c5880218efe9072` consolidated 13 dimensions into nine on September 26, preserving six core reviewers. Pacing/structure and engagement were merged; audience and brand were merged; SEO and transcript-only visual accessibility were removed. The historical progress note in that commit also explicitly says core six, extended three. No evidence in that change establishes a specific cost justification for leaving these three extended.

Recommendation: request all nine from the normal studio action. The existing request shape already supports this, so enabling the reviewers need not change the API schema. Keep the concurrency bound. Going from six to nine increases base reviewer calls per transcript chunk by 50%; actual cost and duration also depend on output, grounding, tools, retries, and concurrency. Historical six-reviewer runs should continue to show six.

## Why the feedback can feel thin

These are code-supported constraints, not a fresh measurement of production review quality.

1. **Sparse output is intentional.** The shared rubric repeats “exception-first”: only genuine flaws and exceptional strengths get findings. Ordinary acceptable sections are silent. `aggregate_bins` emits only bins touched by findings. This avoids invented scores, but silence gives no account of what was checked.
2. **Three useful creative lenses never run through the UI.** Audience/voice, emotion, and the closing ask often provide more relevant editing advice for an ordinary creator video than legal or cultural risk. Whether they find additional issues needs a live comparison.
3. **Visual coverage is reactive.** The first reviewer input is transcript plus persona, audience, platform, title, and thumbnail concept. No initial storyboard is supplied. Reviewers may request up to three frames/clips per chunk, with two tool rounds by default. They can miss visual problems that the spoken words never suggest inspecting. FFmpeg, source lookup, or signing failure degrades to transcript-only review.
4. **The output shape favors problems in existing words.** Every finding must quote exact words, and its timestamps must fall inside those words. Missing demonstrations, an absent payoff, a needed qualification, or dead air do not always have a matching quote. Adding explicit omission and interval evidence would let reviewers describe these faithfully.
5. **Long-video coherence is weak.** Reviewers process roughly 36,000-character transcript chunks with only two neighboring context segments on either side. There is no shared full-video outline or open-loop ledger. This limits reasoning about promises, contradictions, and payoffs far apart in time.
6. **Context is generic.** Reviewers receive persona text but do not retrieve the creator library. The project name doubles as the title; the worker does not pass a separate video goal or the project description. No actual audience-retention data is provided to the review context.
7. **“Overall” is an average of flagged moments.** `summarize_findings` duration-weights reported observations per dimension, then averages those dimension scores. Unreported time and dimensions without findings are excluded. One bad moment in an otherwise good video can dominate the displayed result. This is an observation score, not a calibrated whole-video grade.
8. **Review completeness is hard to see.** A dimension with some successful chunks and some failed chunks receives status `succeeded` plus a `REVIEWER_PARTIAL` error. The UI's reviewer count checks status only. A blank track may mean nothing found, missing evidence, or incomplete review.
9. **Finding confidence is not currently elicited.** It remains in the contract, but is absent from the requested model schema and defaults to 0.5 during normalization. It should not be presented as measured reliability.

An earlier real comparison (September 2026, recorded in git history) found that a coverage prompt nudge left the total unchanged at 12 findings. That is one historical content sample, not a general result, but it argues against treating more insistent wording as the whole solution.

## GitHub projects worth borrowing from

The source files were inspected, rather than relying only on repository descriptions. These are useful building blocks and patterns; they do not demonstrate that adding them will improve our critique quality without validation.

| Project | Observed implementation | Useful adaptation here |
| --- | --- | --- |
| [PySceneDetect](https://github.com/Breakthrough/PySceneDetect) | Scene boundaries, frame export, content/fade detection, and an adaptive detector using rolling frame-change averages. | Build a shared shot map and representative storyboard. Give visual/pacing reviewers measured shot intervals and actual frames. A long shot is evidence to assess, not automatically bad editing. |
| [Auto-Editor](https://github.com/WyattBlue/auto-editor) | Audio loudness analysis, motion-based editing criteria, temporal labels, margins around cuts, and editor exports. | Measure candidate pauses and quiet intervals; offer bounded trim suggestions with preview and padding. Keep intentional pauses and musical/visual sequences subject to context. |
| [VideoAgent — YueFan1014](https://github.com/YueFan1014/VideoAgent) | Separate memory construction and question answering; segment captions and object memory queried through tools. | Construct evidence once, then let reviewers inspect relevant moments. Keep the existing Gemini provider; the research repository's GPU/model stack is unnecessary for our demo. |
| [VideoRAG](https://github.com/HKUDS/VideoRAG) | Query rewriting for visual retrieval, segment relevance filtering, and a response prompt requiring video names and start/end timestamp references. | Retrieve distant evidence for a claim or unfinished promise. Later retrieve creator-library examples for audience/brand comparisons, with source timestamps. Creator examples establish style, not factual truth. |
| [FActScore](https://github.com/shmsw25/FActScore) | Decomposes text into atomic claims, retrieves passages per claim, and records individual support decisions. | Separate claim extraction from verification and show a claim ledger: supported, contradicted, unresolved, or not checked. Retain our grounded Gemini provider and uncertainty states; the original biography/Wikipedia evaluation setup is not a universal truth checker. |
| [Video Copilot](https://github.com/vmatresu/videocopilot) | Gemini category analyzers accept timestamped keyframes and return issue descriptions, recommendations, strengths, and priority actions. | Give users a readable issue title, evidence, concrete edit, and consolidated priorities alongside the heatmap. |
| [Gapline](https://github.com/emforce77/gapline) | Audio-description pipeline: evidence-based rubric, timestamp ownership, omission review, fixes checked against the same rules, and measured narration duration. | Require every fix to solve its cited problem without introducing another one; inspect footage for visual claims and distinguish uncertainty from errors. Its specialized audio-description rules and many pipeline stages are not needed here. |

Video Copilot is the closest product reference, but its `retention-service.ts` also generates retention and engagement values with `Math.random()` and contains placeholder visual scenes. Those values are not retention measurements or validated predictions. Its visual analyzer also promotes a generic “3-second rule”; our advice should respect format, audience, and creator style instead of enforcing that universally.

Pinned source references inspected:

- PySceneDetect: [README](https://github.com/Breakthrough/PySceneDetect/blob/cb0cc3d61aa130aa99b1da41b6c0244a2c12dd65/README.md), [adaptive detector](https://github.com/Breakthrough/PySceneDetect/blob/cb0cc3d61aa130aa99b1da41b6c0244a2c12dd65/scenedetect/detectors/adaptive_detector.py).
- Auto-Editor: [README](https://github.com/WyattBlue/auto-editor/blob/4928ad4201126973ca38e5b09c245b9e75219cf0/README.md), [audio analysis](https://github.com/WyattBlue/auto-editor/blob/4928ad4201126973ca38e5b09c245b9e75219cf0/src/analyze/audio.nim).
- VideoAgent: [README](https://github.com/YueFan1014/VideoAgent/blob/42e1b70d947d4ae6ee627a3e9dda4898844e97b1/README.md), [segment/tool prompt](https://github.com/YueFan1014/VideoAgent/blob/42e1b70d947d4ae6ee627a3e9dda4898844e97b1/prompts/prompt.txt).
- VideoRAG: [retrieval and timestamp prompts](https://github.com/HKUDS/VideoRAG/blob/c412a093a820ef7a0e0dda31076ed871136198b3/VideoRAG-algorithm/videorag/prompt.py).
- FActScore: [claim-level scoring](https://github.com/shmsw25/FActScore/blob/f28272deffcf33efc1f1117d5479c10bb75221a9/factscore/factscorer.py).
- Video Copilot: [Gemini analyzers](https://github.com/vmatresu/videocopilot/blob/fb9c79755f6f1801ab20bd7b6a991ae227d0ce20/src/lib/ai/video-analyzers.ts), [retention service](https://github.com/vmatresu/videocopilot/blob/fb9c79755f6f1801ab20bd7b6a991ae227d0ce20/src/lib/analysis/retention-service.ts).
- Gapline: [README](https://github.com/emforce77/gapline/blob/fd56b7bd35c0d649f48ab6040800ff452088dd4c/README.md), [review and fix rules](https://github.com/emforce77/gapline/blob/fd56b7bd35c0d649f48ab6040800ff452088dd4c/src/lib/pipeline/review.ts), [sourced rubric](https://github.com/emforce77/gapline/blob/fd56b7bd35c0d649f48ab6040800ff452088dd4c/src/lib/pipeline/guidelines.ts), [initial visual inspection](https://github.com/emforce77/gapline/blob/fd56b7bd35c0d649f48ab6040800ff452088dd4c/src/lib/pipeline/watch.ts).

## Recommended implementation order

### 1. Make the current review honest and useful

Request all nine reviewers. Show each reviewer's completion and limitations, including partial chunk failures and whether any footage was inspected. Rename the current overall statistic to describe its actual meaning, or omit it until independent whole-video grading exists.

Add explicit rubric coverage: checked/no issue, issue found, not applicable, insufficient evidence, or failed. Coverage is separate from a finding; it should not create colored observations for fine stretches. Show an evidence label such as transcript, inspected footage, measured audio, or web source.

### 2. Turn findings into an editing plan

Extend findings with a readable title, a concrete action type (trim, rewrite, move, add demonstration, qualify claim), and evidence that can describe omissions and time intervals. Preserve exact quotes for speech critiques without requiring them for every issue type.

Deduplicate overlapping reviewer suggestions and surface the highest-value actions. The current list already sorts by severity; the improvement is consolidating repeated diagnoses and choosing useful edits, rather than adding another severity sort. A single bounded synthesis over reviewer outputs can reference existing finding IDs. If fewer than three justified actions exist, show fewer than three.

Illustrative target: “0:18–0:31 repeats the opening promise. Trim this span and start the demonstration at 0:32.” Clicking should preview the original interval and show the proposed edit. This is an example of desired output, not a finding from a video inspected in this session.

### 3. Give reviewers evidence they cannot currently see

Create one project-scoped evidence map: a global outline, promises/payoffs, measured audio intervals, shot boundaries, and a capped storyboard with guaranteed opening/ending coverage. Reuse it across reviewers and revisions of the same source. Let reviewers request clips to investigate further inside the existing single analysis flow.

Use creator-library retrieval first for Audience & Brand, where past work can support specific voice/style comparisons. Add claim extraction plus bounded grounded verification for Truth & Evidence. A transcript gap alone is not proof of audio silence; an unchanged shot is not proof of a retention problem.

## Constraints and validation for the next implementation

- Update OpenAPI and Firestore contracts before new output fields. Store evidence, decisions, and review feedback beneath the user/project document tree and matching GCS prefix so deletion covers them.
- Keep external calls in providers, GCP region rules, bounded concurrency/tool rounds, and a total per-run allowance for additional inspection and verification. Current project cost accounting is not a guarantee that an individual enlarged run cannot overshoot the remaining allowance.
- Use objective preprocessing to select evidence, then ask the model whether an edit is justified. Preserve strengths and deliberate creative choices. Do not impose a minimum finding count.
- Compare the current system and proposed system on the same real fixture videos. Manually assess grounded evidence, useful edits, missed known issues, duplication, time, and cost. This is live/manual validation, not adding test files or test libraries.
- The default reviewer model is `gemini-3.1-flash-lite`; that alone does not prove it causes thin feedback. Consider a bounded model comparison only after coverage and evidence improvements, rather than increasing model spend indiscriminately.

The best first release combines all nine reviewers, transparent coverage, concrete consolidated edits, and shared sampled footage. Scene/audio measurements and creator context then improve the evidence behind those edits. More red marks by itself is not a useful success metric.

## Implemented scope after the creator-focused clarification

Kept the existing request/response fields, screen, provider, and single-pass review flow.
The studio now requests all nine reviewers. Findings show reasoning and the specific edit
together, and the existing score/completion/empty-state text describes its limits correctly.
Reviewers share at most six sampled stills, receive the project brief and bounded continuity
excerpts, can describe omissions without fabricated quotes, and reject quote mismatches and
missing actions. Exact overlapping advice within a dimension is removed. Gapline informed
the fix self-check, without adding an independent review stage.

No claim ledger, scene detector, audio analyzer, creator-library retrieval, new finding schema,
or synthesis call was added. Those are deferred research ideas, not required next features.

Live validation used a matching five-minute Hindi smartphone video/transcript, with ephemeral
results and no project writes. The first fallback-model run exposed inappropriate cultural
rewrites, a memory-based product claim in the safety lens, and an unnecessary closing CTA.
Prompts were refined using those observations. This is a smoke check on one video, not a
controlled quality comparison or proof of general improvement. The configured Flash Lite model
returned 404 in `us-central1`; Gemini 2.5 Flash was used only in the validation runner, with its
grounding/tool compatibility limits recorded in the handoff. Repository model settings remain
unchanged.
