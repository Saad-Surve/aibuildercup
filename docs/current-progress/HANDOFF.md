# Handoff

The single current handoff for this repo. Update it in place when work changes what the next
person needs to know: contracts, infra, deployed state, open decisions, or verification gaps.
Keep it current rather than chronological. Delete what is no longer true. History lives in
`git log -- docs/current-progress`; earlier notes can be recovered with `git show <rev>:<path>`.

Last updated: 2026-10-16.

## Status

Resonance Creator Studio is built and deployed: upload → transcript → nine-reviewer heatmap
with a predicted audience-interest lane and reviewer coverage (deployed 2026-10-13, `fbc2e80`),
drafts with grounded writing, captions, localization and dubbing, thumbnails, packaging with
optional Veo inserts, YouTube connector with publishing, a content calendar that uploads
scheduled videos, Medium, Substack and Reddit connectors with cross-posting, creator library
retrieval, and a read-only demo. Feature detail is in `README.md` and `docs/architecture.md`.

UI copy and performance work are merged into local `main` (`7cb49a4`, `f565087`), verified
and ready for deployment.
The landing page describes the supported review, rough-cut, and publishing flows. The unfinished
audience navigation, placeholder platform cards, and static translation preview are removed;
Localization retains dubbing and the glossary. Job failures use friendly retry guidance, with
exception details kept in logs. API contracts and persisted data shapes are unchanged. Humation
branding and the Google stack names are intentionally retained.

Cross-language dubbing is fixed and deployed (`bbdbba7`, 2026-10-16); the API role and the
Translation/TTS services were applied with a targeted `terraform apply`. A dub through the
deployed app has not been run yet. Cloud Run had failed four
attempts at Translation with `cloudtranslate.generalModels.predict` denied: dubbing moved inline
to `creator-studio-api`, while `roles/cloudtranslate.user` remained on the retired
`creator-studio-localization` account. Terraform now assigns the role to the API account and owns
Translation/TTS API enablement. Permission failures persist an actionable stage-specific job error.
A bounded 21-second English-to-Hindi worker run against live Translation, Gemini adaptation, TTS,
Firestore and Storage succeeded on the first attempt (job `304ec32013466e875dcd5928f1bc7603`,
localization `767b952d8f67499e8ae3efb972e347cf`); FFprobe and a full decode confirmed 21-second H.264/AAC
streams. Production remains broken until the Terraform IAM change is applied; no apply, deploy or
direct IAM mutation was made.

Copy-pass verification: web lint, ESLint, TypeScript, and production export; backend ruff and mypy.
The exported landing page was checked at desktop and phone widths, including the rough-cut
example. Read-only demo sign-in, dashboard, project workspace and Review were checked locally against
live Firestore on 2026-10-15; Calendar and Settings were also checked. Fresh provider jobs and
write flows remain unverified. Existing image, array-sort,
and static-export rewrite warnings remain.

Cloud Run keeps one warm instance (`min-instances 1`, workflow `53aab18`, deployed and
confirmed 2026-10-15), at approximately $1.73/day before allowances. Return it to zero after
judging if idle costs are no longer justified. Reviewer/orchestrator models remain 3.8 Flash:
the 3.5 Flash-Lite dev comparison lost three planted issues and had quota/service failures.

What is not yet proven is live, end-to-end behavior on the current code. See
"Verification gaps" below.

## Performance work (merged into `main`)

- Notifications observe shared query data and an owner subscription on the existing tab-wide
  WebSocket. The watcher makes **zero HTTP requests**; its first cache scan waits for idle,
  hidden tabs skip scans, and the minute timer only checks local schedule reminders. Owner
  frames carry no snapshots and cause no Firestore reads. Terminal events reconcile only
  matching observed resources. Events missed while offline, and resources never observed in
  this tab, reconcile on the next normal view/focus fetch; there is no durable notification feed.
- Returning users render the shell from a local profile hint while Firebase restores and `/me`
  validates in the background. API calls wait for Firebase restoration; ownership/read-only
  enforcement stays server-side. Sign-out/account switches clear cached state. First-time users
  retain the onboarding gate. Transient `/me` errors retain an established cached shell.
- Workspace project/assets/transcript queries start together, with project-list placeholder
  data and early VideoStudio chunk loading. Cards prefetch these on hover/focus. Missing-video
  and missing-transcript states wait for their queries. Cards no longer request asset lists or
  download/decode remote videos for posters; applied covers and existing local posters remain.
- **Contracts:** `Project.sourceSummary` adds active asset id, duration, size, upload date and
  poster URL on `GET /projects`, using one batched asset read. Publish/schedule list endpoints
  accept `refreshLive` (default false); views request reconciliation once, interval refetches
  read saved state only. WebSocket client messages add `subscribe.owner`/`unsubscribe.owner`,
  scoped exclusively to the authenticated UID and deduplicated with project subscriptions.
  OpenAPI/events are updated; no persisted Firestore shape or indexes change.
- Published/planned items and idle visual inserts stop polling. Hidden tabs pause fallback
  polling. Rough cuts poll their existing job instead of repeatedly downloading the asset
  list. Signed media/evidence URL renewal while visible remains separate from job polling.
  The header shows the user's Humation avatar (the owner asked to keep it; artwork loads lazily).
  Marketing/caption fonts are no longer preloaded globally. Persona uses React Query.
- Bounded, thread-safe process caches reuse signed URLs only with more than five minutes left,
  immutable transcript generations, revision joins and library PCA/neighbors. Cached URL
  responses report the original expiry. Revision joins use index counts for cache versions;
  library versions use projected embedding timestamps/model metadata instead of full vectors.
  Ownership is checked before cache lookup; all caches disappear on container restart.
- Complete JSON responses >=1 KB are GZipped; streaming bodies/SSE/WebSockets bypass compression.
  The API lifespan gives `asyncio.to_thread` 32 workers so model calls leave I/O headroom on
  one vCPU. Reviewer concurrency defaults to 10. The rubric starts alongside reviewers when a
  conservative reviewer/interest/prior-call allowance fits; near the cap it retains the serial
  fallback. Editor and adjudicator use waves of at most three, reserve all in-flight call
  estimates before launch, and merge summaries in input order. Durable atomic call slots and
  per-call limits remain. Prompts, versions, model requests, thinking and token limits are
  unchanged (AST-checked); no evaluation outputs were regenerated.
- Verification: web oxlint, ESLint, TypeScript and static export pass (four existing library
  `<img>` ESLint warnings; existing static-export rewrite notices). Backend ruff and mypy pass
  (158 files). Uvicorn booted without reload on 8090; `/api/readyz` returned 200 and OpenAPI
  returned GZip. Local smoke checks confirmed owner isolation/deduplication, bounded call
  allowance and streaming bypass. No tests/dependencies added. No infra/workflow changes,
  deployment or paid model calls. Local read-only authenticated browsing against live GCP now passes; dashboard startup made
  only demo-session, profile and project-list requests. Actual deployed latency/pipeline
  timing remain unmeasured; increased concurrency still needs a bounded live run for quota,
  CPU and memory pressure. Spend checks remain token-price estimates, not a billing hard cap.

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

## Interest model (retrained 2026-10-14, local `main`, not deployed)

The heatmap's "Audience interest" lane and reviewer coverage tint are live (`544700f`,
deployed with `fbc2e80`). The method and current numbers are in `evals/interest/README.md`.

**Where it stands.** `backend/app/assets/interest/model.json` (recipe `mixed/full`, fallback now
`creator/transcript`) was retrained on 2026-10-14 with 87 creator videos from 81 channels (was
46). On unseen creator channels: lift ρ **0.151 [0.101, 0.200]** (was 0.172 [0.099, 0.241]),
lift peak precision 0.35, lift dip precision 0.35 (chance 0.25), overall ρ 0.28 against a position
baseline of 0.24. Transcript-only lift is 0.074 [0.029, 0.120]: above zero now, but too weak to
mark moments, so the fallback still marks none. The demo account's two runs were backfilled with
the new model (`interest_backfill.py --force`, live Firestore). Production keeps the old model
until the next deploy.

**Data.** The new videos came from a five-hour run of `evals/interest/collector/run-macos.sh` on
this machine (zips `interest_data_20261014-1210.zip` and `-1633.zip` in the collector folder,
gitignored). YouTube IP-blocked captions within the first hour, so most new transcripts are local
Whisper, at 15–25 minutes per Hindi video on CPU. That is why the run yielded 41 videos rather
than 150–300, and why the new data leans towards Hindi smartphone reviews. Gitignored
`evals/interest/raw/` now holds 298 metadata files, 87 creator transcripts and 322 signal files,
plus the corpus parquet in `raw/cbc/`. Training needs all of it. To add data, rerun the collector
(it resumes), then `interest_train.py signals …` for unsignalled videos, then
`interest_train.py train --dry-run` before writing.
A faster next run on this Mac: `collect.py` uses faster-whisper on CPU, while
`interest_collect.py asr` uses MLX at about 85 s per video, roughly ten times faster. Collect
metadata with `collect.py`, then transcribe with the MLX path.

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
- YouTube deletions are detected on explicit view, not by a job. Publish/schedule list reads
  reconcile only with `refreshLive=true`; one-publish GET still reconciles. Each live video is
  re-checked at most every 60s when requested. A deleted video marks the publish `deleted` and
  cancels its slot. Published items do not keep polling.
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
- Cross-language dubbing runs in the API Cloud Run process. Keep
  `roles/cloudtranslate.user` on `creator-studio-api`; the old localization service account is no
  longer a runtime path.
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
- Dubbing has a successful bounded live backend run through Translation, adaptation, TTS, muxing
  and Storage. The signed-in browser path and the deployed API identity remain unverified until the
  pending Translation IAM binding is applied and the code is deployed.
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
- Creator library: both the owner account and `demoCreatorHabeasCodus` have the import
  `vlogbrothers-prehero-cc-by` active (2026-10-16): 29 CC BY Vlogbrothers videos published before
  the demo hero `BBvze0lGcZg` (hero, later videos and eval-only videos excluded), 10 thumbnails,
  142/142 nodes indexed, about $0.035. Config `fixtures/creator-sources/vlogbrothers.json`; the
  collected folder is gitignored under `backend/creator-libraries/`. `source()` no longer
  replaces a deliberately imported non-preset bundle with the `CREATOR_PRESET_OBJECT` preset.
  Undo with `scripts/import_creator.py remove --uid <uid> --bundle-id vlogbrothers-prehero-cc-by
  --apply`; the preset (`arun-prabhudesai`) then reinstalls on the next read.
- The Docker image for the API. A change to the Dockerfile was reviewed but not built.
- Browser click-through of the draft editor and drawer is still open. The read-only demo and
  mobile workspace were checked at 390px and 1440px in light and dark themes, including project
  modules, transcript, review, rough cut, packaging, publishing, captions, calendar and profile.
  The writable new-project dialog was reviewed in code because its trigger is intentionally
  disabled for the demo account.
- The interest lane was checked in a browser (local API and web against live Firestore, demo
  account): curve, baseline, hover readout, info panel, dip click (seek and filter findings)
  and coverage tint all worked. A fresh analysis run through the deployed worker has not been
  run with the curve enabled. Backfill was used for the two demo runs instead.
- Creator-quality evaluation. No creator labels exist yet. The comparison protocol is in
  `evals/creator-comparison.md`.
- Editorial eval: `evals/editorial/` has five constructed videos (20 planted flaws plus a clean
  control), labels pre-registered at `2e13571`, and four arms in `backend/scripts/editorial_eval.py`.
  First full run, `2026-10-14-flash38` on `gemini-3.8-flash` (`evals/results/editorial-2026-10-14-flash38.*`):
  baseline (one prompt) recall 19/20, precision 95%, clean control 3, $0.12; rubric 14/20, 88%;
  nine reviewers 20/20 but precision **31%** (45 extra findings), clean control 6, $1.14;
  adjudicated 20/20, 33%, $1.39. **The nine-reviewer path is not yet better than one prompt on
  this set.** It matches recall and loses badly on precision and cost. The adjudicator only checks
  high/critical findings against footage, so it removed 5, and it passed a critical "false claim"
  about a correct fact on the clean control. Phase 3 added an editor pass (dev precision 31% to
  74%, post-hoc), a model-judged audit (41 of 51 unmatched reviewer findings were duplicates, 2
  spurious) and an independent held-out set (`evals/editorial-heldout/`, 6 videos, 22 issues,
  labels at `6df94ce`). Held-out run `2026-10-14-heldout-flash38`: baseline 18/22, 100%, $0.16;
  rubric 20/22, 95%, $0.21; reviewers 22/22, 34%, $1.43; **edited 21/22, 78%, clean control 1,
  $1.49**; edited_adjudicated 20/22, 77%. The editor generalised, but **reviewers plus editor do
  not beat the rubric prompt** (1 vs 2 discordant issues, lower precision, ~7x cost), and the
  editor dropped broken-promise findings. The held-out set is now spent for tuning claims.
  Phase 4 (2026-10-14, merged and deployed): the rubric pass is a tenth reviewer feeding
  the editor (`ensemble_edited`, the shipped pipeline; frozen `editor-v6`, `rubric-v1`,
  `reviewers-v5`, `adjudicator-v2`), findings carry `corroboratedBy`. Dev (post-hoc): 20/20,
  87%, clean 1 vs rubric 19/20, 90%, clean 1. Two new pre-registered sets, each run once:
  **long-form** (`evals/editorial-longform/`, 5 videos of 8-12 min, 32 issues, labels
  `9d48bf5`): Resonance **31/32, 91% precision**, clean control 6, $0.44/video; one prompt +
  rubrics 28/32, 97%, clean 5, $0.08; 3-0 discordant in our favour, not significant (sign
  test p = 0.25). **Real** (`evals/editorial-real/`, 4 CC BY videos, 5 creator-published
  corrections, recall only, labels `6f1f23f`): Resonance 3/5, one prompt 3/5 (different
  errors); all arms caught the Call of Duty claim in the hero `BBvze0lGcZg`; the rubric call
  failed on the Ukraine video. Honest claim: more recall than a single prompt on long-form at
  a precision cost, a tie elsewhere. Results summary: `evals/README.md`; run index:
  `evals/results/README.md`. Demo plan and files live outside the repo in
  `~/Desktop/resonance-demo/`; the hero project still has to be run once in the deployed app
  (the app reviews sampled stills, the eval reviewed the whole video).
  Constructed TTS media measures planted-flaw detection, not
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
   view. The static "Transcript translation" card is removed on `chore/ui-polish`;
   dubbing and the glossary remain. Cloud Translation glossary registration is not done. The glossary is enforced in the Gemini pass only.
7. **Writer quality.** Video context, temperature and token limits are in (see "Review loop
   work"). Thumbnail planner and listing prompts with the new context are not verified live, and
   `activeAnalysisRunId` can be dropped from project creation.
8. **Connector scope and infra cleanup.** Native Bluesky and Mastodon connectors are candidates.
   The unused BigQuery datasets, worker subscriptions, dead-letter topics and five worker service
   accounts were removed from Terraform on 2026-10-14. The targeted dubbing apply on 2026-10-16
   also destroyed the five unused service accounts (analysis, localization, media, social_sync,
   web) as dependencies; nothing ran as them, and they are undeletable until about 2026-11-15.
   The rest is NOT applied. The remaining add/change are pre-existing
   drift (deployer secretmanager.viewer, the killswitch object, the known budget diff). Check the 9
   BigQuery tables are empty, then apply.
   Possibly unused and kept: `raw-social`/`exports` buckets, `meta-app-*` and
   `session-signing-secret` secrets.
9. **Account deletion revokes connector grants only best-effort.** Provider-side revocation is
   not a guaranteed part of deletion.
10. **Operations.** Set the Agent Platform spend cap below the budget. Delete the unused
    `gemini-api-key` Secret Manager secret. Decide whether deploys should use
    `cancel-in-progress`.
11. **Remaining responsive and accessibility pass** (frontend plan item 16). Dashboard, project
    list, transcript editor, profile and shared dialogs now have a responsive baseline. Mobile
    app/studio navigation, project-card density, profile avatar layout and dialog choices were
    tightened. Desktop fixed panes remain, but snapping is enabled only after an in-place module
    change so hard loads retain the read-only banner and project context. Remaining: exhaustive
    keyboard-only traversal and a writable browser check of create/edit dialogs.
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
