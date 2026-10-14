# Editorial held-out set (independent benchmark)

A second gold-issue benchmark for the review heatmap, authored **independently** of the
product and the dev set (`evals/editorial/`). Six videos carry **22 planted flaws** and
**two clean controls**. Nobody runs any review arm on these videos until the coordinator
does it after the editor pass is frozen.

Author: implementation sub-agent running **Meta Muse Spark 1.3** (a different model
family from the one that wrote the product and the dev set).

## Independence rule

- Written without opening `backend/app/agents/`, `backend/app/prompts`, or any prompt
  files, and without reading any dev-set file except the three named in the task
  (`scripts/espresso-basics.json`, its labels, `scripts/boiled-egg-control.json`).
- Flaws are written the way a real creator makes them (a plausible wrong number, an
  interesting off-brief story, a slow hook, a CTA that contradicts the brief), not the
  way a rubric would describe them.
- `matching.json` is copied byte-for-byte from the dev set: the matching rule is fixed
  and identical.
- No review, eval arm, or LLM call was run on these videos during authoring.

## Layout

Same as the dev set, rooted at `evals/editorial-heldout/`: `scripts/<id>.json` (spoken
script with planted flaws tagged on lines), `media/<id>.mp4`, `transcripts/<id>.json`,
`labels/<id>.json`, `matching.json`. Built with the same builder:

```bash
cd backend && uv run python scripts/editorial_build_media.py --root ../evals/editorial-heldout
```

(`--root PATH` reads scripts from `<root>/scripts` and writes media, transcripts and
labels under `<root>`; it defaults to `evals/editorial`, so existing behaviour is
unchanged.)

## The videos

| Video | Length | Spoken as | Planted flaws |
|---|---:|---|---|
| `lisbon-budget` | 3:25 | Kathy | L1 weak hook 0:00-0:21, L2 45-minute London flight 0:41-0:48, L3 street-cat tangent 1:23-1:48, L4 re-adding costs 2:12-2:41, L5 dollars/Austin/Zelle 2:54-3:08, L6 missing spreadsheet CTA 3:21-3:24 |
| `nova-x5-review` | 3:50 | Rishi | P1 spec jargon 0:42-1:01, P2 three-day battery 1:28-1:42, P3 dollars/Verizon/Best Buy 2:00-2:14, P4 sneering at budget buyers 2:31-2:47, P5 charging under pillow 3:04-3:19, P6 Pixel comparison promised and never delivered 3:37-3:49 (promise at 0:09-0:18) |
| `printing-press` | 3:48 | Reed | H1 Bible printed in 1475 0:54-1:10, H2 "twice as likely" statistic 1:38-1:54, H3 incunabula/xylography/recension 2:12-2:30, H4 museum gift-shop tangent 2:49-3:22, H5 three consequences promised, two delivered 3:38-3:47 (promise at 0:09-0:18) |
| `first-four-weeks-lifting` | 3:49 | Shelley | S1 hedging opening 0:00-0:27, S2 push through sharp pain 1:53-2:08, S3 mocking light weights 2:26-2:40, S4 warm-up explained twice 2:58-3:26, S5 missing workout-PDF CTA 3:43-3:47 |
| `weeknight-tomato-pasta` (control) | 2:12 | Sandy | none: a correct, on-brief recipe with a subscribe CTA that matches the brief |
| `first-freelance-client` (control) | 1:55 | Ralph | none: calm, honest first-client advice with a newsletter CTA that matches the brief |

Categories: weak_hook x2, jargon x2, tangent x2, pacing_drag x2, factual_error x2,
unsupported_claim x2, safety x2, broken_promise x2, locale_assumption x2,
missing_cta x2, tone_mismatch x2. Every category exactly twice; 22 flaws total.
Flaws are spread through each video (smallest gap between neighbouring flaws is
13 s) and subtler than the dev set by design.

Titles, platforms (YouTube long-form), audiences and briefs are in each script and
label. The briefs state the creator's goal, which is what makes a missing CTA or a
tone mismatch a defensible label. The India-audience review is spoken by Rishi
(en-IN); every video has a different voice.

The planted factual errors and unsafe statements are deliberately wrong fixtures,
not publishable content. Correct facts: London to Lisbon scheduled flights take
about two and a half hours (not 45 minutes); the Gutenberg Bible is dated to the
mid-1450s, around 1454-1455 (not 1475); no 5,000 mAh phone lasts three days of
heavy use; phone makers warn against charging under bedding because trapped heat
is a fire risk; sharp joint pain means stop and get checked, not push through.

## Pre-registration

The labels, transcripts, media, scripts and `matching.json` were committed before
any model saw the videos, and no model, reviewer, or eval arm was run on them
during authoring.

**Pre-registration commit: the commit titled "fix(evals): correct a survivor count in the
held-out printing-press script"** (it directly follows `d6ee085`). Before any model saw the set,
the coordinator's review found one loose fact outside the planted flaws in `printing-press` ("a
handful still survive", where about 49 Gutenberg Bibles survive). A strict Truth reviewer could
fairly flag it, which would count as an unplanted false positive. The line was corrected to "around
fifty", and that video was rebuilt (spans shifted by about 1.3 s). No other file changed.
`d6ee085` is the original authoring commit.

**Use the commit above as the pre-registration commit.** Quote the commit when reporting
held-out results; if the labels change after a run, the run is void. The matching
rule, headline metric and other variants are those of the dev set's pre-registration.
