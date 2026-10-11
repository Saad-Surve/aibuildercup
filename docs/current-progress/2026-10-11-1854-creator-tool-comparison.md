# Sourced creator-tool comparison

## Work completed

- Continued the user-requested comparison against Descript, OpusClip, YouTube Studio,
  ChatGPT and Gemini Apps. Read the latest progress note and technical-design index first.
- Added `docs/competitive-comparison.md`: implemented workflow distinctions, competitor
  strengths, current public prices, separate monthly/annual billing, and vendor-reported
  productivity context. Included HookMaster and Retensis as closer review competitors.
- Added `evals/creator-comparison.md`: first supplied project/video, precise data intake,
  complete-output labeling, metrics, competent critique baselines and a separate clipping
  task. A sample is not yet a quality result; favorable excerpts cannot establish precision.
- Linked the comparison from README, costs and evaluation index; updated the evaluation
  index to acknowledge the newly supplied video/project without implying labels exist.
- Previewed the compact HTML comparison at 728px and 360px; both were readable with no
  console messages. Published it inline through the T3 HTML renderer.

## Evidence and discoveries

- User supplied project `bbf2c874926d4b3ba79063ab5d4961e9` and public YouTube video
  `ga53h0I-sO0`. YouTube oEmbed returned “Top 5 Best Smartphones Under ₹60000 ⚡ September
  2026”, Trakin Tech. This confirms public metadata only, not uploaded asset identity,
  language, duration, transcript or review quality.
- T3 shared browser tab `tab_4_25ec2470-5874-4ba8-96d3-9ba5a7519abf` initially redirected
  to the landing page. Normal read-only demo sign-in succeeded, but the supplied project
  returns “Project not found” / no access. User reports opening it; repeated status/read
  still showed only this demo session. Asked for owner-session access or complete exports.
  Did not bypass ownership, mint tokens, extract credentials or access an admin datastore.
- YouTube's current Ask Studio documentation explicitly supports unpublished-video and
  script feedback, image references, channel insights and historical retention context.
  Comparison therefore does not reduce Studio to post-publication analytics.
- Gemini Apps supports video uploads and reusable instructions/reference files through
  Gems. ChatGPT Projects persists context. Neither lacks creator memory by definition.
- Descript's LinkedIn story reports ~1 hour saved/project; OpusClip's Grant Cardone story
  reports 50% lower editing time, twice daily output and 4+ daily hours saved. These are
  vendor/customer reports, not independent studies or Resonance measurements.
- Resonance's partial five-minute API scenario remains $0.1475; hypothetical 10/100 repeats
  sum to $1.475/$14.75 with the same assumptions/exclusions. No retail price, all-in cost,
  competitor savings or cost per accepted edit is established.
- Creator semantic retrieval informs initial drafts, thumbnails and packaging, not current
  heatmap reviewers or inline alternatives. Avoid implying otherwise in differentiators.

## Structural changes

Documentation only. No endpoints, contracts, persistence, infrastructure or runtime changed.
Preserved existing packaging and other worktree changes. No commits, deployment, competitor
signups/purchases, new paid generation, tests or user-project mutations.

## Verification

- `uv run ruff check .`: passed.
- `uv run mypy app`: passed, 133 source files.
- `bun run lint`, `bun run lint:eslint`, `bun run build`: passed. Four existing Library
  `<img>` warnings and expected static-export rewrite warnings remain.
- Current changed-document local links and `git diff --check`: passed.
- Comparison visual desktop/mobile previews: passed.

## Remaining work / next step

The sourced market comparison and evaluation protocol are complete. The private-project
case study remains pending access/exports and creator judgment. Obtain complete findings,
timed transcript, run/asset metadata, intended audience and three useful plus any wrong or
generic examples. Label all issue findings before reporting precision/usefulness rates.
No competitor runs have occurred. Actual superiority, task time, invoice-backed efficiency,
CTR and retention still require the shared study; preserve original outputs before reruns.
