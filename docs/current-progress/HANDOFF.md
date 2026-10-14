# Handoff

The single current handoff for this repo. Update it in place when work changes what the next
person needs to know: contracts, infra, deployed state, open decisions, or verification gaps.
Keep it current rather than chronological. Delete what is no longer true. History lives in
`git log -- docs/current-progress`; earlier notes can be recovered with `git show <rev>:<path>`.

Last updated: 2026-10-14.

## Status

Resonance Creator Studio is built and deployed: upload → transcript → nine-reviewer heatmap
with a predicted audience-interest lane and reviewer coverage (deployed 2026-10-13, `fbc2e80`),
drafts with grounded writing, captions, localization and dubbing, thumbnails, packaging with
optional Veo inserts, YouTube connector with publishing, a content calendar that uploads
scheduled videos, Medium, Substack and Reddit connectors with cross-posting, creator library
retrieval, and a read-only demo. Feature detail is in `README.md` and `docs/architecture.md`.

What is not yet proven is live, end-to-end behavior on the current code. See
"Verification gaps" below.

## Review loop work on local `main` (2026-10-14, not pushed or deployed)

The hackathon plan (Claude Doc "Resonance: Hackathon Plan of Action",
https://claude.ai/code/artifact/8c2813f9-0935-4e90-9cfc-3b1b557a1413) was executed by subagents in
worktrees under `../aibuildercup-wt/` and merged into local `main` (`fbc2e80..HEAD`). A push to
`main` deploys, so push only when the owner says so. Shipped in code:

- **Finding decisions.** `decision` {status accepted|revised|dismissed, note?, revisedAction?,
  decidedAt, decidedBy} via `PATCH …/analysis/{runId}/findings/{findingId}` (`decision: null`
  clears). Decisions never edit reviewer output or scores.
- **Adjudicator.** `app/agents/adjudicator.py` checks each high/critical finding against a frame or
  clip (`adjudication` {verdict confirm|downgrade|reject, reason, adjustedSeverity?, evidence}).
  Rejected findings leave bins and summary; downgrades use `adjustedSeverity`. Overlapping
  conflicting findings get one `reconciliation`. Max 12 calls per run including at most 4 conflict
  calls, atomic `adjudicatorCalls/{00..11}` reservations, `MODEL_ADJUDICATOR` falls back to the
  reviewer model. Evidence lives under `review-context/{runId}/adjudicator-{findingId}/` and is
  signed lazily by `GET …/findings/{findingId}/adjudication/evidence?kind=frame|clip`.
- **Library links.** `libraryLinks` (max 1 per finding) from the creator's library for clarity,
  truth, audience and emotion findings, medium+; cosine ≥ 0.65 (provisional), ≤ 8 findings, ≤ 1
  Gemini selector call per run. Labelled as earlier work, never evidence about this video.
- **Rough cut.** `POST …/analysis/{runId}/rough-cut` renders accepted/revised removal findings into
  a non-activated source revision with `Asset.roughCut` (keptSegments, removedSpans, durations)
  and a remapped transcript (no STT). `…/rough-cut/plan`, `…/rough-cut/edl?format=cmx3600|markdown`,
  `DELETE /assets/{assetId}` (inactive cuts only), `GET /assets/{assetId}/captions`. Analysis start
  accepts optional `assetId` for "Re-review this cut".
- **Comparison.** `GET …/analysis/compare?baseRunId=&targetRunId=` (deterministic, read-only):
  resolved / persists / new findings and bins on the source timeline via keptSegments or transcript
  alignment. `<ReviewComparison>` appears in the rough-cut module once the cut's review finishes,
  and a picker in the review panel compares any two completed runs.
- **Writer context.** `app/services/video_context.py` feeds transcript excerpt, persona (as
  preferences), accepted/revised or severe non-rejected findings, interest peaks and the strongest
  hook into drafts, assist, thumbnail planning and listings. `_fallback_blocks` is gone: failures set
  draft `status: failed` with an error. The thumbnail planner previously read the never-written
  `activeAnalysisRunId` and so saw no findings; it now resolves the latest run.
- **Publish warnings, STT fix, docs/infra cleanup and the editorial eval harness** (open items 1, 2,
  8 below and "Editorial eval" under Verification gaps).

## Next session: interest model retrain (set up 2026-10-13)

The heatmap's "Audience interest" lane and reviewer coverage tint are live (`544700f`,
deployed with `fbc2e80`). The method and current numbers are in `evals/interest/README.md`.

**Where it stands.** The shipped model (`backend/app/assets/interest/model.json`, recipe
`mixed/full`) uses creator videos plus a Content Behavior Corpus sample, with Gemini signals.
On 45 unseen creator channels: lift ρ **0.172 [0.099, 0.241]**, lift peak precision 0.35,
lift dip precision 0.37 (chance 0.25), overall ρ 0.30 against a position baseline of 0.26.
Transcript features alone do not beat chance (lift ρ 0.03). Gemini signals carry the effect.

**Overnight run.** A colleague is running `evals/interest/collector/run.bat` on a CPU-only
Windows laptop: 7 hours of collection (target 500, expected about 150–300 new creator videos),
then the Gemini signal pass (capped at 2,000 calls, about $2–4). They will send
`interest_data_<date>.zip`, which contains `meta/`, `subs/` and `signals/` JSON relative to
`evals/interest/raw/`.

**Local data on this machine** (gitignored `evals/interest/raw/`, about 146 MB): 283 metadata
files, 49 creator transcripts (`subs/*.lines.json`), 284 cached Gemini signal files (creator and
corpus sample), and the corpus parquet files in `raw/cbc/`. Training needs all of it, so do not
delete it. If it is lost, the collector and training READMEs rebuild it.

**Steps when the zip arrives** (from the repo root):

1. `cd evals/interest/raw && unzip -n <path>/interest_data_*.zip && cd -`. `-n` keeps
   existing files; the signal cache key matches because the model and prompt are the same.
2. Count the new data with `ls evals/interest/raw/subs | wc -l`. Any creator video without
   a signal file still needs the pass:
   `uv run --project backend --with pyarrow python backend/scripts/interest_train.py signals --max-calls 400 --concurrency 3 --cbc-train 0 --cbc-test 0`
3. Evaluate without writing:
   `uv run --project backend --with pyarrow python backend/scripts/interest_train.py train --dry-run`.
   Compare the `mixed/full` and `creator/full` rows with the numbers above. More creators
   should narrow the confidence interval.
4. If the result holds or improves, run the same command without `--dry-run`. It rewrites
   `model.json`, `evals/interest/results.json` and `videos.csv`. Then update the numbers in
   `evals/interest/README.md`, `evals/README.md`, the README evidence table and this section.
5. Refresh the demo curves:
   `uv run --project backend python backend/scripts/interest_backfill.py --uid demoCreatorHabeasCodus --max-runs 10 --force`
6. Run the checks (`ruff`, `mypy`, `bun run lint`, `bun run build`) and commit. A push to
   `main` deploys.

**Gotchas from the build.**

- YouTube IP-blocked this machine for captions (yt-dlp timedtext returns 429; the
  transcript API raises `IpBlocked`) after about 30 requests. Metadata and Most Replayed
  extraction were never blocked. The fallback is local Whisper:
  `interest_collect.py asr` (MLX, about 85 s per video on an M4), or `collect.py` with
  faster-whisper. faster-whisper needs `av<15`.
- yt-dlp's English auto-caption list includes YouTube's machine translations of Hindi videos.
  Only the original-language ASR track is a real transcript. Both collectors handle this.
- Gemini (`gemini-3.1-flash-lite`, global) returned many 429s at concurrency 8. Use 2–3.
- Training and inference share `app/services/interest.py`. Production stores segment
  timings only, so training re-segments transcripts with `build_segments` and interpolates
  words the same way. Keep it that way.
- On Windows, set `PYTHONUTF8=1` (`run.bat` does). All script IO is explicitly UTF-8.

**Ideas not built.**

- Per-creator calibration: once a creator connects YouTube (the `yt-analytics.readonly`
  scope is already granted), pull their own videos' retention (`audienceWatchRatio`) and
  captions through the official APIs, and fit the model to their audience. This uses a real
  retention label and stays within API terms. It needs channels with enough views.
- Earlier submission plan, still open: prove the nine-reviewer run end to end on the deployed
  model, record the 3-minute video around the heatmap and interest lane, build a small
  pre-registered gold-issue eval, and fix the README contradiction about connectors (it says
  Medium, Substack and Reddit are not built; they are).

## Deployed surfaces

- Web: `https://habeas-codus.web.app`. Static Next.js 16 export on Firebase Hosting.
- API: `https://habeas-codus.web.app/api/...`. Hosting rewrites `/api/**` to the
  `creator-studio-api` Cloud Run service in `us-central1`. Prod has no CORS.
- Deploy: push to `main` runs `.github/workflows/deploy.yml` (Workload Identity Federation, no
  keys). The `changes` path filter gates parallel `api` and `web` jobs. Warm runs take about 60s.
  `infra/**` is not in the path filter, so an infra-only change does not redeploy.
- Cloud Run: one instance (`--max-instances 1`), `--no-cpu-throttling` so background work
  continues after the response.
- GCP project `habeas-codus`. Region `us-central1` everywhere except Speech-to-Text, which uses
  the `us` multi-region because Chirp 3 is GA only there.
- Infra inventory: `infra/RESOURCES.md`.

## Decisions that shape the code

- Contract first. `contracts/openapi.yaml` changes before code.
- Every external call goes through `backend/app/providers/`. Feature code never imports a
  Google SDK.
- Every LLM call uses Gemini on Agent Platform (Vertex AI) with ADC. Local uses
  `gemini-3.1-flash-lite`. Deployed uses `gemini-3.8-flash`. There is no API key.
- Delete is real. Project data lives under `users/{uid}/projects/{projectId}/...` in Firestore
  and `project_object_prefix(uid, projectId)` in Storage. Account data lives under
  `users/{uid}`. Anything outside those paths must be added to the delete path explicitly.
- Ownership is checked against the path scope and the stored document. A mismatch returns 404,
  not 403.
- Playback streams directly from GCS through signed URLs.
- Review output is exception-first. Gaps in the heatmap are shown as gaps, not filled with
  invented scores.
- Heatmap scores describe flagged moments. They are not retention predictions or calibrated
  quality ratings.
- Reviewer coverage is recorded per run (`analysisRuns/{id}.coverage`, returned by
  `GET …/heatmap`). The UI tints covered spans with no bin as "reviewed, nothing flagged".
  A chunk that failed stays unreviewed. Runs from before 2026-10-13 have no coverage unless
  they were backfilled.
- The interest curve (`app/services/interest.py`, `GET …/analysis/{id}/interest`, stored at
  `analysisRuns/{id}/interest/curve`) is a relative ranking within one video, learned from
  YouTube Most Replayed graphs. It is not retention. Peaks and dips are chosen on lift over
  the position head (the typical drop-off), and are marked only when the Gemini signal pass
  ran, because the transcript-only lift did not beat chance. Method and numbers:
  `evals/interest/README.md`.
- The interest model is JSON coefficients in `app/assets/interest/model.json`. To retrain,
  run `backend/scripts/interest_train.py` (see the eval README). The curve runs alongside
  the reviewers and never blocks or fails a run.
- Creator context is kept separate from current-video facts. A persona records preferences, past
  work supplies examples, and neither is treated as fact.
- Enforcement of read-only demo mode is an environment allowlist (`READ_ONLY_USER_UIDS`), not a
  Firestore flag. The demo account is a shared, pre-seeded showcase, and its credentials are not
  secret.
- The demo sign-in mints a custom token through the backend (`POST /api/demo/session`).
- There is no runtime feature-flag system. `web/src/lib/feature-flags.tsx` was removed on
  2026-10-11. Do not re-add flags without a reason.

Calendar and publishing (2026-10-11 to 10-12):

- Slot status is automatic. Users never set it. A slot is `planned` (no upload), `scheduled`
  (upload armed), `published`, `failed` (blocked, with `statusDetail`) or `cancelled`.
- A plan-only slot uploads nothing. Scheduled uploads ride on `publish.publishAt`. A YouTube
  slot is armed automatically on create, read and edit (`_arm_or_explain`, `_sweep_slots`).
- A future `publishAt` uploads the video `private` with `publishAt`, and YouTube holds it until
  then. A past time uploads `public` now.
- Go-live is lazy. There is no scheduler. `_promote_due` runs on publish list and get, so a
  scheduled post flips to `published` only while something polls. The calendar and studio poll
  while any item is non-terminal.
- YouTube deletions are detected on read, not by a job. `_reconcile_live` runs on publish list and
  get, and `_reconcile_linked_uploads` runs on the calendar list endpoints. Each live video is
  re-checked at most every 60s. A deleted video marks the publish `deleted` and cancels its slot.
- Rescheduling a dead or failed upload re-uploads it (`recreate_for_schedule`). Rescheduling a
  still-waiting upload moves its go-live time. A live (`published`) upload stays blocked.
- Deleting a slot cancels a queued upload job that has not reached YouTube. Deleting a publish
  unlinks its slots. The app never deletes a video on YouTube. A calendar delete keeps a video
  that is already uploaded.
- An edit that conflicts with a live upload applies nothing. The conflict check runs before the
  slot is written.
- Crossposting shows only connected destinations. Saving or posting a draft always refetches
  connections and projects, and never trusts cached lists for the upload gate.

Writing platforms (Medium, Substack, Reddit), 2026-10-11 to 10-12:

- Substack has no official write API. Its OAuth server grants only read scopes to public
  clients, and password login is captcha-gated. The `substack.sid` session cookie is the only path
  that writes, so the connect flow accepts any paste of it. It also accepts the full cookie header,
  and a bookmarklet copies the cookie from a Substack tab.
- Substack drafts are TipTap JSON, not HTML. Posting HTML stores literal tags. The creation call
  also requires `draft_bylines`, which is the session's own profile id.
- A posted Substack draft is linked to the local draft (`Draft.linkedPosts`). Sync pushes later
  edits to the same remote draft. A remote draft deleted outside the app clears the link.
- Substack `send: true` is irreversible. The UI defaults to draft mode and labels the risk.
- Medium's API is deprecated. Only legacy tokens work, and no new tokens have been issued since
  January 2025.
- Reddit uses official OAuth with permanent refresh. Reddit has no revoke endpoint, so deletion
  relies on removing the stored secret. New Reddit apps may need manual approval from Reddit's
  developer support.

## Model choices

- Interest signals: `MODEL_INTEREST_SIGNALS=gemini-3.1-flash-lite`, pinned in both
  environments. The bundled model was trained on that model's ratings
  (`interest-signals-v2` prompt). If the configured model differs from `signalModel` in
  `model.json`, inference falls back to the transcript-only head with no moments marked.
  Change both together and retrain.

- Images: Nano Banana 2 (`gemini-3.1-flash-image`) is the default for thumbnails. It takes a
  video frame as input, edits conversationally, keeps references consistent, and renders text
  well. It runs through the same `genai` Vertex client as the rest of the app. Imagen 4 is only a
  fallback. Pro (`gemini-3-pro-image`) is for hero shots. Lite is for bulk drafts.
- Video: Veo 3.1 Fast (`veo-3.1-fast`) in `us-central1` remains the default for illustrative
  inserts. It supports image-to-video, references and 1080p, and it is GA. Gemini Omni Flash
  (`gemini-omni-flash-preview`) is a preview model with no image-to-video. It is a conversational
  edit companion, not a Veo replacement. Recheck it when it leaves preview.
- Veo cost: the app reserves six seconds at `$0.40/sec` from config. Published Fast pricing is
  lower, so treat the reservation as a conservative bound, not invoice spend.

## Gotchas

Infra and GCP:

- There is no native hard spend cap. The budget (8,500 INR, about $100) and the billing kill
  switch (`infra/budget.tf`) are a backstop, and billing data arrives late. The Agent Platform
  spend cap is console-only and should sit below the budget.
- `/healthz` is reserved by Google's front end. Use `/readyz`.
- IAM changes take 1–2 minutes to propagate.
- Terraform has a known perpetual diff on the budget project reference
  (`projects/538724167565` vs `projects/habeas-codus`). It is harmless. Do not chase it.
- Applying Firestore rules needs `firebaserules.rulesets.create`, which the local ADC lacked.
  The deployer or Firebase Rules Admin has to apply them.
- Storage signing: Cloud Run cannot sign V4 URLs directly. It signs through IAM `signBlob`. Locally
  you need `serviceAccountTokenCreator` on `creator-studio-api@…`, or impersonation.
- The `oauthStates` collection-group index must exist, or the unauthenticated OAuth callback fails
  with FAILED_PRECONDITION.
- Cloud Run has two URL forms. The OAuth redirect and `API_PUBLIC_BASE_URL` both use the
  `-uc.a.run.app` form. Keep them in sync.
- Blocking functions support only `beforeCreate` and `beforeSignIn`, not `beforeUserDeleted`.
- The Firebase default bucket (`habeas-codus.firebasestorage.app`) is not used. The app uses
  `habeas-codus-media`.
- Versioned buckets keep noncurrent generations until lifecycle expiry, so deletion is not
  immediate purge.

Speech-to-Text and transcription:

- Batch recognition with `chirp_3` on the `us` multi-region. It needs an explicit output config.
  Per-file errors arrive in-band at `file_result.error`.
- STT V2 cannot auto-detect AAC in MP4, MOV or M4A. Those use explicit `MP4_AAC`, `MOV_AAC` or
  `M4A_AAC` decoding with a sample rate and channel count.
- Ripper-muxed MP4s with micro-chunked `stsc` make STT return INTERNAL. The worker retries once
  after a pure-Python demux to a clean `.m4a` staged under the project prefix.
- Diarization is language-gated. The provider retries once without it. If labels come back empty,
  set `STT_ENABLE_DIARIZATION=false`.
- Transcription starts from the GCS `object finalized` Pub/Sub push
  (`POST /api/internal/pubsub/video-events`). `POST /assets/{id}/complete` is the fast UX path.
  Both converge on one idempotent `transcribe` job.
- Older transcripts have `speaker: null`. Re-transcribe to populate labels.
- STT polling errors cause resubmission, which can create duplicate operations. See "Open items".

LLM and analysis:

- `complete_json` returns `LlmCompletion(data, usage)`. Thinking tokens count as output, which
  matches billing.
- Cost is estimated from an env price table. The `gemini-3.8-flash` intro price (0.75/3.75) doubles
  on 2027-01-01. Update the variables then.
- `POST /analysis` returns `409 COST_CAP_EXCEEDED` past `max_project_cost_usd`.
- Findings are filtered in Python over a bounded set. Avoid composite indexes for them.
- Fresh analyses are required for the current prompts. Stored findings keep the prompt and
  dimensions they were created with.
- Nine reviewers increase initial calls per chunk by 50% over six. Sampled frames add media
  tokens.
- Prompts improve judgment but do not guarantee factual correctness. Watch for false positives
  and overly broad jargon advice.

Storage, caching and realtime:

- Firebase Hosting caches rewrite responses by default. A 404 from `/api/**` once got
  `max-age=600`. The fix is `Cache-Control: no-store` and `Vary: Authorization` at the origin and
  in `firebase.json`. When the UI disagrees with Firestore, check `curl -D -` for
  `x-served-by: cache-*` first.
- The SSE and WebSocket paths need the Firebase `Authorization` header. Plain `EventSource` cannot
  send it.
- The realtime hub is process-local. Keep `--max-instances 1` until durable leases and shared
  event delivery exist. The WebSocket URL goes directly to Cloud Run because Hosting rewrites do
  not proxy WebSocket upgrades.
- Signed thumbnail and poster URLs expire after about 15 minutes. A card left open longer falls
  back until the next refetch.

Web and Next.js:

- Next.js 16 docs ship under `web/node_modules/next/dist/docs/`. Read them before framework
  code. `web/AGENTS.md` lists the version-specific rules.
- The shadcn components here are Base UI, not Radix. Base UI throws in production when a menu
  group is missing its context (`MenuGroupContext`).
- Static export has no dynamic routes. Production links to project paths do hard navigations.
- `useSearchParams` needs a `<Suspense>` boundary.
- TanStack `refetchInterval` pauses while the tab is hidden unless
  `refetchIntervalInBackground: true` is set. Two observers on the same key with different options
  conflict. The transcript query lives in one hook, `use-project-transcript.ts`.
- video.js: never put `poster` in the player-init effect dependencies. The `<video>` node is owned
  by video.js.
- oxlint forbids synchronous setState in effects.
- `oxfmt` reflows files, so an `oldString` copied from an earlier read can stop matching. Re-read
  before editing.
- Run `bun` only inside `web/`. A stray root `bun add` creates a root lockfile.
- `markdownToHtml` renders line by line, so multi-line variant options are not supported yet.
- The Shiki highlighter is synchronous on purpose, because the draft editor sets `innerHTML`
  synchronously.
- Raw HTML in Markdown is disabled. The grounding panel uses HTML from `grounding_html` and
  renders it as returned, as Google requires.

Tooling:

- `web/` uses Bun, `backend/` uses uv, `infra/` uses Terraform. Do not add npm, pip, poetry or
  yarn.
- Tests are not used in this repo. The checks are `ruff`, `mypy`, `oxlint`, `eslint` and the
  build.
- The default Turbopack build can fail in sandboxes that cannot bind a port or resolve Google
  Fonts. Use `bun run build --webpack` there, with network access.
- Base UI `SelectValue` with no children renders the selected label, not the raw value. Custom
  render functions must map value to label themselves.
- `bun run format` reflows about 34 unrelated files, because the repo is not oxfmt-clean. Format
  only the files you touch.

Local development (observed on the dev machine, 2026-10-11 to 10-12):

- The backend `uvicorn --reload` watcher stalls on this machine. Edits then serve stale code and
  nothing reports it. Run the backend without `--reload`, restart it after each backend edit, and
  wait for `Application startup complete` before testing.
- A dead parent can leave orphaned `multiprocessing.spawn` children holding port 8080. Check for
  orphans before assuming the reloader is alive.
- A mid-edit restart can leave a stale `web/.next` cache. The symptom is a `CssSyntaxError` in
  `package.json` or `globals.css`. Fix it with `rm -rf web/.next` and restart `bun dev`.
- The local backend needs `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` in
  `backend/.env`. Without them, every publish after the one-hour access token expires fails with
  `CONNECTION_NEEDS_REAUTH`. The values come from Secret Manager (`youtube-oauth-client-id` and
  `youtube-oauth-client-secret`), and `backend/.env` is gitignored.
- A rejected push means `git fetch` and rebase, never force. A force push would discard teammate
  commits.

## Verification gaps

Verified in code, with bounded live checks where noted. Not yet verified end to end:

- Nine-reviewer analysis on the configured model. It was unavailable in the mandated region when
  it was last tried. The truth reviewer's Search grounding and the requested-footage tool rounds
  are not validated live.
- Dubbing and localization against live Translation and TTS.
- Caption render in the app. The last render check hit an expired demo token mid-session. The
  streaming runner was validated directly.
- The calendar and publish flows were checked by running backend services against live Firestore
  and the connected YouTube channel (2026-10-11 to 10-12). These covered upload, go-live,
  reschedule with re-upload, deletion sync and slot cancellation. They were not run through a
  signed-in browser session, so the UI path is still unverified.
- Medium and Reddit have no live test with real credentials. Substack was verified live (draft
  create, update, read-back and delete) through the backend path.
- Calendar slot and YouTube video link: a slot shows "Linked upload" but no direct YouTube link.
  The URL is only on the publish, so it is not verified from the calendar.
- Draft generation with live Search grounding, and the Search Suggestions panel.
- Multi-line Markdown in draft variants.
- Live creator-library indexing on a real folder import. The import path is lint- and
  type-checked only. A real folder has not been supplied.
- The Docker image for the API. A change to the Dockerfile was reviewed but not built.
- Browser click-through of the draft editor, drawer, read-only states and mobile workspace.
  Several UI changes were checked by build and reasoning only.
- The interest lane was checked in a browser (local API and web against live Firestore, demo
  account): curve, baseline, hover readout, info panel, dip click (seek and filter findings)
  and coverage tint all worked. A fresh analysis run through the deployed worker has not been
  run with the curve enabled. Backfill was used for the two demo runs instead.
- Creator-quality evaluation. No creator labels exist yet. The comparison protocol is in
  `evals/creator-comparison.md`.
- Editorial eval: `evals/editorial/` has five constructed videos (20 planted flaws plus a clean
  control), labels pre-registered at `2e13571`, and four arms (single prompt, single prompt with
  rubrics, nine reviewers, nine reviewers plus adjudicator) in `backend/scripts/editorial_eval.py`
  (dry run by default, `--max-calls` enforced, `replay` re-scores with no calls). The first full run
  on `gemini-3.8-flash` was started 2026-10-14 (`--run-id 2026-10-14-flash38`, log in
  `.logs/editorial-eval-2026-10-14.log`). Constructed TTS media measures planted-flaw detection, not
  accuracy on real creator videos.
- Everything in "Review loop work on local `main`": decisions, adjudicator v2 prompt, library
  links, rough-cut upload/activate/discard and re-review, comparison on real runs, writer context
  in thumbnails and listings. All pass ruff, mypy, lint and build; live checks were limited to one
  earlier adjudicator run (12 calls, no errors), one local rough-cut render and one draft call.

## Open items

1. **Publish warnings (fixed in code 2026-10-14, not deployed).** `Publish.warnings` records
   `THUMBNAIL_FORBIDDEN` (403, tells the creator to phone-verify at youtube.com/verify),
   `THUMBNAIL_MISSING`, `THUMBNAIL_FAILED`, `CAPTIONS_SKIPPED` and `CAPTIONS_FAILED`; a caption
   failure after upload no longer fails the publish. The 403 path is unverified against a real
   unverified channel. Demo unblock is unchanged: phone-verify the connected channel.
2. **STT resubmission (fixed in code 2026-10-14, not deployed).** Submission and polling are
   separate (`start()`/`wait()`); the job stores `sttOperations` names before polling and resumes
   them; polling errors never resubmit or trigger the normalized-audio fallback. 429/503 on submit
   retry; an ambiguous submit allows one resubmission (`ambiguousResubmits`). No live STT call has
   run on the new code. Still open: image calls need their own bounded retry timing and pacing.
3. **Full nine-reviewer validation** on the configured model, including grounded truth review and
   the footage rounds. Choose a model and region deliberately, then run a bounded comparison on
   the same real videos.
4. **Live verification of the items in "Verification gaps".** The demo depends on the
   authenticated calendar and publishing flows, so start there.
5. **Veo insert refinement.** A source-style director was added and verified on one paid
   generation. Motion and end framing still need checks. Existing suggestions need regeneration to
   use it. Pixel conditioning applies only when a clean source frame exists.
6. **Localization comparison and flag UI** (design §7 and §12). Store per-segment source and
   localized pairs. Add `POST /projects/{id}/localizations/{localizationId}/flag` and a comparison
   view. Also decide the fate of the static "Transcript translation" card. Cloud Translation
   glossary registration is not done. The glossary is enforced in the Gemini pass only.
7. **Writer quality.** Video context, temperature and token limits are in (see "Review loop
   work"). Thumbnail planner and listing prompts with the new context are not verified live, and
   `activeAnalysisRunId` can be dropped from project creation.
8. **Connector scope and infra cleanup.** Native Bluesky and Mastodon connectors are candidates.
   The unused BigQuery datasets, worker subscriptions, dead-letter topics and five worker service
   accounts were removed from Terraform on 2026-10-14 but NOT applied. `terraform plan`: 2 add, 1
   change, 45 destroy; the add/change are pre-existing drift (deployer secretmanager.viewer, the
   killswitch object, the known budget diff). Check the 9 BigQuery tables are empty, then apply.
   Possibly unused and kept: `raw-social`/`exports` buckets, `meta-app-*` and
   `session-signing-secret` secrets.
9. **Account deletion revokes connector grants only best-effort.** Provider-side revocation is
   not a guaranteed part of deletion.
10. **Operations.** Set the Agent Platform spend cap below the budget. Delete the unused
    `gemini-api-key` Secret Manager secret. Decide whether deploys should use
    `cancel-in-progress`.
11. **Remaining responsive and accessibility pass** (frontend plan item 16). Dashboard, project
    list, transcript editor, profile and dialogs are still open. The desktop fixed-pane snap is
    unchanged.
12. **Scale-out.** Durable worker dispatch and leases, shared realtime delivery, and indexed vector
    retrieval as library and project counts grow.
13. **Optional polish.** Calendar drag-to-move, week view by hour, ICS export. Non-Latin caption
    fonts (only Latin is bundled). A styled caption file alongside the burned MP4. Real FFmpeg
    progress percentages. A Cloud Run Job if renders run alongside requests.
14. **Scheduler.** Go-live promotion and YouTube-deletion detection both run lazily on reads, so
    they only happen while someone is polling. Replace them with a real due scan (Cloud
    Scheduler plus a job) before relying on unattended scheduled posts. The "planned slot never
    uploads" model is still by design. A sweeper that converts due planned slots is possible
    future work.
15. **Calendar to YouTube link.** Denormalize `youtubeUrl` onto the schedule so a slot links to
    its video directly.
16. **Public upload audit.** On 2026-10-12 a public upload succeeded on the connected channel, so
    that client may not be locked to private. Confirm this for other users before the demo claims
    public posting. The earlier "forced private until audit" note may be out of date.
17. **Writing platforms.** Live credential pass for Medium, Substack and Reddit with real
    accounts. Reddit's pre-approval fallback copy is not in the UI. Medium is legacy-token only, so
    decide whether to keep it. Substack `send: true` needs a deliberate product choice. Scheduled
    crossposts would need jobs. Content read-back for style signals is future work.
18. **Calendar copy.** The landing calendar demo hard-codes November 2026.
19. **Interest model data.** It is trained on 45 long-form creator videos and a Content
    Behavior Corpus sample. More creator videos would tighten it. The overnight kit in
    `evals/interest/collector/` (Windows `run.bat`, tested on macOS only) collects, runs the
    Gemini signals and zips the result for `interest_train.py train`. Alternatively, resume
    `interest_collect.py subs` (the YouTube transcript API IP-blocked this machine after
    about 30 requests on 2026-10-13) or `asr` (local Whisper, about 85 s per video). Then
    rerun `interest_train.py signals`, `train` and the backfill. A creator's own YouTube
    Analytics retention (`audienceWatchRatio`) would be a better label once a channel with
    enough views is connected.
20. **Interest curve backfill.** Deployed. Run `interest_backfill.py` for any account whose
    existing runs should show the lane. The two demo runs are already backfilled. New
    analysis runs compute the curve automatically.

## Test and local state to clean up

- `evals/interest/raw/` (gitignored) holds the collected metadata, transcripts, Gemini signal
  cache and corpus parquet files (about 150 MB). Keep it to retrain without recollecting.
- The two demo-account runs ("yt1" and "My Transcription Project") have backfilled
  `interest/curve` documents and `coverage` fields in live Firestore.

- Test projects and artifacts from earlier live runs are still in the demo account and possibly in
  the real account. Delete them if unwanted. Deleting a project also removes its stored footage.
- Three thumbnail concepts on the `chicken curry` project were left as demo data.
- Stray debug objects may exist at the bucket root (`debug/lord_*`). Verify before deleting.
- Local `.logs/` may hold server logs from an earlier session.
- A live public test video is on the connected YouTube channel: `Yy--rrT5KsY`, titled
  "Something". It is the recovery upload from 2026-10-11. Delete it on YouTube if unwanted. The
  app will mark its publish `deleted` on the next read.
- Earlier test uploads (`ThVr4MD0FhQ`, `jT2-hKGMy2s`, `aQJ0Gx5-ers`, `A7mNFfBRgh8`) were deleted
  on YouTube. Their publish records show `deleted` and their slots show `cancelled`.

## Data and provenance

- The creator corpus for the retrieval benchmark is a bounded public snapshot, not an archive.
  Some sources were unavailable (Instagram, the X profile, one LinkedIn post). Those are recorded
  as missing, not fabricated. Auto-generated captions may contain errors.
- The YouTube connector uses a Google OAuth client. Uploads from unaudited clients are forced to
  private by YouTube. A public upload did succeed on the connected channel on 2026-10-12, so
  check this for each account before relying on it (see open item 16).
- Local and deployed OAuth tokens are not interchangeable. Local encrypts with a Fernet key from
  `OAUTH_TOKEN_ENCRYPTION_KEY`. Production uses Cloud KMS. A connection made locally reads as
  absent in production, and the reverse.
- The CC-BY seed loader was removed (2026-10-11). Its GCS copies expire under the seven-day policy.
- Public-link profile research only prefills answers. It is not a web collector.

## Pointers

- Product and features: `README.md`
- Implementation and cost bounds: `docs/architecture.md`, `docs/costs.md`
- Design and reference: `docs/technical-design/`
- API and data: `contracts/`
- Evaluation: `evals/README.md`
- Rules for agents: `AGENTS.md`
