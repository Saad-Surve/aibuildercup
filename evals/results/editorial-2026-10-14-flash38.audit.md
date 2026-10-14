# Editorial audit: run editorial-2026-10-14-flash38

> **MODEL-JUDGED, NOT HUMAN-VERIFIED.** Every classification below is one model's judgment (Muse Spark 1.3 Free), using its own reasoning over the raw findings, scripts, labels, and briefs. Treat all classes — especially `spurious` and `valid_unplanted` — as claims to verify, starting with the Human spot-check list at the end.

## Method

Read every unmatched finding's full critique and suggestion in `editorial-2026-10-14-flash38.raw.json` against the planted-issue scripts (`evals/editorial/scripts/*.json`, which carry each video's title, audience, and brief), the gold labels, and the matching rule. Each of the 100 unmatched findings in `baseline`, `reviewers`, and `adjudicated` got exactly one class, judged by the same standard in every arm without knowing which arm is the product's:

- `duplicate`: same moment and underlying problem as a matched gold issue, or as a sibling finding in the same arm+video (re-lensed by another reviewer).
- `valid_unplanted`: a real, specific, actionable problem a careful human editor would raise for this creator/audience/brief; simply not planted.
- `nitpick`: defensible but low value; a creator could reasonably ignore it.
- `spurious`: wrong — misreads the transcript, calls a correct fact false, contradicts the brief, or invents something not in the video.

Truth/evidence checks state the correct fact and confidence inline. Web search was used only to confirm facts (USDA/FDA egg storage, EU egg storage, 401(k) sponsorship, espresso extraction). The adjudicated arm's findings are the reviewers' set minus removals; removal info is recorded per item (`adjudicatorKept`) in the JSON and listed below.

## Counts per arm and class

| Arm | duplicate | valid_unplanted | nitpick | spurious | Total unmatched |
|---|---|---|---|---|---|
| baseline | 1 | 1 | 2 | 0 | 4 |
| reviewers | 41 | 5 | 3 | 2 | 51 |
| adjudicated | 36 | 4 | 3 | 2 | 45 |

Headline: the reviewers' extra findings are overwhelmingly **duplicates** (41 of 51), not new discoveries or hallucinations — the same planted problem re-reported through 2-4 reviewer lenses (hook x2-3, jargon x2, tangent x3, outro x3, guarantee x2, promise x2-3). Genuinely wrong (`spurious`) findings are rare: 2 per arm (1 unique pair each, shared with adjudicated).

## Adjusted precision (flawed videos only)

Adjusted precision credits `valid_unplanted` alongside matched findings: `(matched + valid_unplanted) / issue findings on the flawed videos`. Strict is the original metric.

| Arm | Matched | Valid unplanted (flawed) | Issue findings (flawed) | Strict precision | Adjusted precision |
|---|---|---|---|---|---|
| baseline | 19 | 0 | 20 | 19/20 (95.0%) | 19/20 (95.0%) |
| reviewers | 20 | 3 | 65 | 20/65 (30.8%) | 23/65 (35.4%) |
| adjudicated | 20 | 2 | 60 | 20/60 (33.3%) | 22/60 (36.7%) |

Adjusting for real unplanted catches moves reviewers 30.8% -> 35.4% and adjudicated 33.3% -> 36.7%; baseline is unchanged at 95.0%. The precision gap is therefore **not** explained by unplanted real issues: after crediting every valid catch, ~60 points of reviewers' findings remain duplicates, nitpicks, or spurious.

## Clean-control findings per arm, with classes

### baseline (3 findings on boiled-egg-control)
- `baseline/boiled-egg-control#0` [platform_fit/platform_pacing_mismatch/high] **valid_unplanted** — "To peel, tap the egg gently on the counter, roll it under your palm, and start peeling at the wide e..." A cooking tutorial that never shows the food is a genuine gap: beginners cannot judge jammy vs firm yolks from text on a static card. A careful editor would ask for a peel demo. One allowance per arm/video for this no-footage point.
- `baseline/boiled-egg-control#1` [legal_safety/safe_handling/medium] **nitpick** — "Cooked eggs keep in the fridge for up to a week..." The one-week claim is correct per USDA/FDA for refrigerated hard-boiled eggs (correct fact, high confidence), so at most a clarification that soft/jammy eggs are best eaten sooner; a creator could reasonably ignore it.
- `baseline/boiled-egg-control#2` [pacing_retention/momentum_flatline/low] **nitpick** — "Those are the three timings to remember: six or seven minutes for jammy, eight for creamy, and ten o..." A one-sentence recap of three timings in a 2-minute tutorial is normal reinforcement, not padding; cutting it is defensible but low value.

### reviewers (6 findings on boiled-egg-control)
- `reviewers/boiled-egg-control#0` [cultural_localization/locale_assumption/medium] **valid_unplanted** — "Using a spoon, lower your eggs in carefully, straight from the fridge, and start..." Correct and audience-material (high confidence): much of Europe and India stores unwashed eggs at room temperature, and room-temp eggs need less cook time, so the fridge-based jammy timings would overcook them for these viewers. Specific and actionable.
- `reviewers/boiled-egg-control#1` [audience_brand/promise_mismatch/high] **valid_unplanted** — "..." Same no-footage point allowed once per arm/video: beginners cannot see what the three promised yolk textures look like, which undercuts the video's whole premise.
- `reviewers/boiled-egg-control#2` [pacing_retention/late_value/medium] **nitpick** — "Very fresh eggs can be harder to peel, so eggs that are a week or so old are a good choice...." A one-line egg-selection aside placed after the steps is a minor ordering suggestion; the line works fine as a tip where it is and moving it is low value.
- `reviewers/boiled-egg-control#3` [truth_evidence/false_claim/critical] **spurious** — "Cooked eggs keep in the fridge for up to a week, so you can make a batch..." Calls a correct fact false: USDA/FDA guidance is that refrigerated hard-boiled eggs keep up to 7 days (high confidence). A critical false_claim with salmonella warnings is a false alarm, including its severity.
- `reviewers/boiled-egg-control#4` [pacing_retention/anticlimactic_payoff/high] **duplicate** — "..." Second counting of the same no-footage problem as item 1 (overlapping recap span, same 'never shows the eggs' complaint).
- `reviewers/boiled-egg-control#5` [emotional_impact/missed_moment/medium] **duplicate** — "Those are the three timings to remember: six or seven minutes for jammy, eight for creamy, and ten o..." Third counting of the same no-footage problem as item 1, on the identical span as item 4 with an emotional lens.

### adjudicated (5 findings on boiled-egg-control)
- `adjudicated/boiled-egg-control#0` [cultural_localization/locale_assumption/medium] **valid_unplanted** — "Using a spoon, lower your eggs in carefully, straight from the fridge, and start..." Same as reviewers item 0: correct, audience-material room-temp-egg point (high confidence). Adjudicator kept it.
- `adjudicated/boiled-egg-control#1` [audience_brand/promise_mismatch/high] **valid_unplanted** — "..." Same as reviewers item 1: the once-per-arm no-footage allowance.
- `adjudicated/boiled-egg-control#2` [pacing_retention/late_value/medium] **nitpick** — "Very fresh eggs can be harder to peel, so eggs that are a week or so old are a good choice...." Same as reviewers item 2: minor tip-ordering suggestion, low value.
- `adjudicated/boiled-egg-control#3` [truth_evidence/false_claim/critical] **spurious** — "Cooked eggs keep in the fridge for up to a week, so you can make a batch..." Same false alarm as reviewers item 3, now footage-'confirmed' at critical: the one-week claim is correct per USDA/FDA (high confidence). The adjudicator checked footage, not factuality, so a wrong verdict survived.
- `adjudicated/boiled-egg-control#4` [emotional_impact/missed_moment/medium] **duplicate** — "Those are the three timings to remember: six or seven minutes for jammy, eight for creamy, and ten o..." Same no-footage problem as item 1 on the identical recap span; one problem counted twice. (The sibling duplicate, reviewers item 4, was removed by the adjudicator.)

Note: the clean control is not flawless on purpose — the room-temperature-eggs point and the no-food-footage point are judged real. The control's genuinely wrong finding is the critical `false_claim` on correct egg-storage guidance (spurious, both arms that carry it).

## The 5 most important spurious findings

Only **4 spurious items** exist across all arms audited (2 unique problems, each present in both reviewers and adjudicated). There is no fifth spurious finding; the closest call is named last for the spot-check.

1. `reviewers/boiled-egg-control#3` [truth_evidence/false_claim/**critical**] — calls the correct one-week fridge guidance false and warns of salmonella, demanding soft/jammy eggs be eaten within two days. USDA/FDA guidance is up to 7 days refrigerated for hard-boiled eggs (high confidence). Worst item: maximum severity, false alarm, on food safety.
2. `adjudicated/boiled-egg-control#3` [truth_evidence/false_claim/**critical**] — the same false alarm, **footage-confirmed by the adjudicator**. The adjudicator checks footage for high/critical findings but does not fact-check, so a wrong verdict survived. Direct evidence for the known adjudicator gap.
3. `reviewers/python-decorators#11` [conversion_cta/friction_heavy_ask/medium] — flags 'star the example repo' as transactional friction, but the brief's stated goal *is* starring the repo. Faults the video for doing its job.
4. `adjudicated/python-decorators#9` [conversion_cta/friction_heavy_ask/medium] — the same brief-contradicting complaint, kept through adjudication.
5. *(No fifth spurious finding.)* Closest call, classified `nitpick`: `baseline/boiled-egg-control#1` [legal_safety/safe_handling/medium] — the mild version of the egg-storage point. Kept as nitpick rather than spurious because it asks for a clarification instead of declaring a correct fact false; verify this boundary.

## Adjudicator removals (reviewers -> adjudicated)

The adjudicator removed 6 findings and downgraded 4 severities (espresso false_claims high->medium x2, index unexplained_jargon high->medium, python tone_drift high->medium). Five removals were correct duplicate pruning:

- reviewers/boiled-egg-control#4 (duplicate no-footage recap)
- reviewers/espresso-basics#11 (duplicate outro/A5)
- reviewers/immune-system-cold#5 (duplicate child-fever tone/B3)
- reviewers/index-fund-mistakes#7 (duplicate guarantee/C3)
- reviewers/python-decorators#3 (duplicate broken-promise/D5)

One removal was a **mistake**: reviewers/python-decorators#5 (`clarity/missing_prerequisite_step`, high) — the valid unplanted catch that the narrated timer wrapper never returns the wrapped function's result. The adjudicator dropped the arm's single best novel code-correctness finding while keeping the brief-contradicting repo-CTA complaint (#11). Worth investigating why.

## Human spot-check (random sample, seed 20261014)

12 items drawn uniformly via `random.Random(20261014).sample`. Please verify each class independently:

| # | Item | Class (model-judged) | Agree? |
|---|---|---|---|
| 1 | `adjudicated/espresso-basics#1` [emotional_impact/empathy_gap/medium] | duplicate | ☐ |
| 2 | `adjudicated/espresso-basics#5` [truth_evidence/false_claim/medium] | valid_unplanted | ☐ |
| 3 | `adjudicated/espresso-basics#9` [cultural_localization/unit_or_format/low] | duplicate | ☐ |
| 4 | `adjudicated/immune-system-cold#2` [emotional_impact/emotional_misstep/medium] | duplicate | ☐ |
| 5 | `adjudicated/index-fund-mistakes#3` [pacing_retention/momentum_flatline/medium] | duplicate | ☐ |
| 6 | `adjudicated/index-fund-mistakes#8` [audience_brand/promise_mismatch/high] | duplicate | ☐ |
| 7 | `adjudicated/python-decorators#3` [audience_brand/condescending/medium] | duplicate | ☐ |
| 8 | `adjudicated/python-decorators#8` [emotional_impact/missed_moment/medium] | duplicate | ☐ |
| 9 | `reviewers/espresso-basics#12` [platform_fit/platform_pacing_mismatch/medium] | duplicate | ☐ |
| 10 | `reviewers/espresso-basics#9` [cultural_localization/unit_or_format/low] | duplicate | ☐ |
| 11 | `reviewers/index-fund-mistakes#12` [conversion_cta/friction_heavy_ask/medium] | duplicate | ☐ |
| 12 | `reviewers/python-decorators#2` [emotional_impact/flat/medium] | duplicate | ☐ |

## Ambiguities and judgment calls

- **How many lenses make a duplicate?** Hook/jargon/tangent/outro findings recur 2-4x per moment across dimensions (e.g. espresso outro = pacing + platform + emotional). All recurrences past the first are `duplicate` regardless of lens novelty — a deliberate strict choice; the editor pass should consolidate, not multiply.
- **The no-footage allowance.** All videos are constructed caption cards, so 'show the food/code' complaints could be dismissed as out-of-scope. I allowed one `valid_unplanted` per arm/video for it (boiled-egg only, where unseen yolk textures directly undercut the premise) and marked siblings duplicate. If the harness intends visuals to be out of scope, reclassify these as nitpick.
- **Egg-storage boundary.** The critical `false_claim` is judged spurious (the fact is correct), while the mild 'clarify for jammy eggs' versions are `nitpick`. If USDA guidance is deemed to exclude runny-yolk eggs, the critical finding upgrades to valid_unplanted — confirm with a food-safety source.
- **TDS/brew-ratio confidence is medium-high, not high.** The corrections match standard extraction science (bypass dilution; ratio set by yield; tamp research), but I did not consult a primary coffee-science source. A domain expert should confirm before these become labels.
- **Index #10 (premature outro) as duplicate of C1** is the weakest duplicate call: its conversion framing is arguably distinct, but the pitch it claims is lost arrives one line later, so no distinct problem stands.
