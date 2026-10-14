# Editorial evaluation, long-form held-out set: real length, subtle flaws

An independent, pre-registered benchmark for the review heatmap. Five constructed
videos carry **32 planted flaws** and one **clean control**. Four flawed videos run
10-14 minutes each; the control runs 8-11 minutes.

Why this set exists: the dev set (`evals/editorial/`) and the first held-out set
(`evals/editorial-heldout/`) are 2-4 minute videos with one obvious flaw per
category, which favours a single model call. Real creator videos are 10-15 minutes
and their issues are subtler: a number wrong by a plausible margin, a claim stated
with more certainty than the evidence allows, a gentle tangent that is interesting
but off-brief, jargon used once without a gloss, a tone slip for the stated
audience. Most of each script is good, natural, on-brief content with long
clean stretches, as a real video would be. Long videos also drift late: pacing
drags sit in the middle, a promise from the intro is dropped in the final third,
and a closing CTA contradicts the brief.

## Authorship and independence

Authored by the `feat/editorial-longform` agent (Muse Spark 1.3 family), which is a
different model family from the one that wrote the product pipeline. Independence
rules followed during authoring:

- Never opened `backend/app/agents/`, any reviewer/editor prompt files,
  `evals/editorial-heldout/`, or any results files.
- Flaws were written the way a real creator makes them (a misremembered number,
  an overconfident aside, a story that runs long), not the way a rubric describes
  them.
- No model reviewed these videos during authoring. No review, eval arm or LLM API
  call was run on them. Only the coordinator runs the set, after the pipeline is
  frozen.

## Layout

Same shape as the dev set. `matching.json` is byte-for-byte identical to
`evals/editorial/matching.json`.

| Path | Contents |
|---|---|
| `scripts/<id>.json` | The spoken script: lines, voice, planted flaws and the lines that carry them. Hand-authored. |
| `media/<id>.mp4` | The video the arms review. Committed so the bytes are pinned. |
| `transcripts/<id>.json` | Transcript segments from the production segmenter. |
| `labels/<id>.json` | Gold labels in the same format as the dev set. Clean control has an empty `issues` list. |
| `matching.json` | Byte-identical copy of the dev set's pre-registered matching rule. |

Built with the same builder (macOS `say`, one voice per video, FFmpeg caption
card, no network, no model calls):

```bash
cd backend && uv run python scripts/editorial_build_media.py --root ../evals/editorial-longform
```

## Videos and flaws

| Video | Length | Voice | Planted flaws |
|---|---:|---|---|
| `bathroom-reno-budget` — Small Bathroom Renovation: 5 Upgrades That Matter Most. First-time homeowners, worldwide. Brief: five upgrades in priority order; goal is downloads of the free checklist at reno.example/checklist. | 11:19 | Reed | R1 weak hook 0:00-0:25; R5 mould-paint guarantee 2:39-2:55; R3 unexplained trade jargon 3:59-4:19; R4 36-inch interior door 4:56-5:13; R7 neighbour's sink story 7:25-7:57; R6 tape-measure re-explained 8:20-8:58; R2 itemised-budget promise dropped 10:24-10:46 (promised in intro 0:39-0:48); R8 no checklist CTA 11:10-11:18 |
| `salary-to-wealth-india` — Salary to Wealth: 5 Money Moves for Salaried Indians in Your Twenties. Salaried Indians 22-32, paid in rupees. Brief: five moves in order, jargon-light; goal is the free budget planner at paisa.example/planner. | 10:40 | Rishi (en-IN) | F6 emergency fund in small-cap equity 2:00-2:18; F1 PPF at nine and a half percent 4:17-4:33; F2 dollars and four-oh-one-kay 4:55-5:11; F3 ELSS beats market every year 5:38-5:56; F4 XIRR/glide-path jargon 6:43-7:01; F5 cousin's crypto story 8:57-9:27; F7 monthly-split promise dropped 9:47-10:10 (promised in intro 0:16-0:23); F8 paid masterclass push, no planner 10:26-10:39 |
| `black-holes-guide` — Black Holes Explained: What Falls In and What Comes Out. Curious adults, no physics background. Brief: everyday analogies, no maths, warm tone; goal is subscribe plus the neutron-star follow-up. | 10:26 | Kathy | S1 Sun will become a black hole 1:25-1:40; S3 Schwarzschild/Eddington jargon 2:42-2:59; S4 trampoline analogy x3 4:42-5:11; S2 information paradox proven solved 6:27-6:42; S5 sci-fi film ranking 7:04-7:32; S7 condescending aside 9:18-9:29; S6 orange-ring explanation promised, never given 9:52-10:13 (promised mid-video 7:40-7:46) |
| `study-smarter-habits` — Study Less, Remember More: Six Habits That Beat Re-Reading. Students 15-22, any country. Brief: six evidence-based habits with examples, supportive tone; goal is the free planner at study.example/planner. | 11:55 | Rocko | H1 weak hook 0:00-0:26; H2 ten-percent-of-brain 1:15-1:33; H3 Mozart plus twenty IQ points 3:58-4:14; H6 timetable read aloud twice 4:54-5:42; H5 gaming tournament story 7:37-8:10; H8 GPA/SAT/prom as universal 8:37-8:54; H4 all-nighters on energy drinks 10:15-10:31; H9 just lazy 10:47-11:02; H7 seven-day-plan promise dropped 11:18-11:40 (promised in intro 0:34-0:43) |
| `bisi-bele-bath-home` — Bisi Bele Bath at Home: A One-Pot Karnataka Classic. Home cooks who like Indian food and own a pressure cooker. Brief: weeknight method with cooker timings and tempering; goal is subscribe for regional recipes. | 8:21 | Tara (en-IN) | none: hook names the dish and promise, facts checked against standard method, cooker safety included, CTA matches brief |

Category counts (32 total, every category 2-4): weak_hook 2, jargon 3,
tangent 4, pacing_drag 3, factual_error 4, unsupported_claim 4, safety 2,
broken_promise 4, locale_assumption 2, missing_cta 2, tone_mismatch 2.
Per flawed video: 8, 8, 7, 9. Adjacent flaw spans are at least 15 seconds apart;
every flawed video has flaws ending in its final third.

Every planted factual error or unsafe statement is clearly wrong per mainstream
sources, and each label description states the correct fact: interior doors are
28-32 inches (36 is exterior); PPF has paid 7.1% since April 2020; the Sun will
end as a white dwarf (black holes need roughly twenty solar masses or more);
the information paradox is unresolved; the ten-percent brain claim is a myth;
the Mozart effect was a small temporary task boost, not permanent IQ gain;
emergency money does not belong in small-cap equity; no paint guarantees zero
mould; past fund performance does not guarantee future returns; all-nighters
plus energy drinks are unsafe exam advice; GPA/SAT/prom are US-specific.

## Pre-registration

The labels, transcripts, media, scripts and `matching.json` were committed before
any model saw the videos (same mechanism as the dev set: the runner's
pre-registration checks operate on `--root`). **Pre-registration commit: `<hash>`.**
Quote the commit in the results table; if the labels change after a run, the run
is void. What is fixed in advance: the videos and labels, the matching rule
(shared with the dev set), the headline metric (recall and precision over all
non-strength findings), and the frozen prompts (recorded by the coordinator when
the set is run).
