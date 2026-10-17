# Handoff

The single current handoff for this repo. Update it in place when work changes what the next
person needs to know: contracts, infra, deployed state, open decisions, or verification gaps.
Keep it current rather than chronological. Delete what is no longer true. History lives in
`git log -- docs/current-progress`; earlier notes can be recovered with `git show <rev>:<path>`.

Last updated: 2026-10-17.

## Status

Resonance Creator Studio is built, deployed and verified end to end: upload → transcript →
nine-reviewer + rubric + editor + adjudicator heatmap with a predicted audience-interest lane,
reviewer coverage, finding decisions, creator-library links and
before/after run comparison, drafts with grounded writing and video context, captions,
localization and dubbing, thumbnails, packaging with optional Veo inserts, YouTube connector
with publishing and warnings, a content calendar that uploads scheduled videos, Medium,
Substack and Reddit connectors with cross-posting, creator library retrieval, and a read-only
demo. Feature detail is in `README.md` and `docs/architecture.md`.

Current local source replaces server-rendered cuts with Review’s CMX3600/Markdown edit-plan
exports, external revision upload and expanded comparison. This change is **not deployed**;
its contracts and verification are described below.

UI copy, review-loop, interest-model and performance work are merged into `main` and verified
end to end across web lint, ESLint, TypeScript, production static export, backend ruff and mypy,
and live end-to-end testing by the project owner across the review loop, studio modules,
connectors and UI flows.
The local landing page describes review, cut-list export → external edits → revision comparison,
and publishing. The unfinished audience navigation, placeholder platform cards, and static translation preview are removed;
Localization retains dubbing and the glossary. Job failures use friendly retry guidance, with
exception details kept in logs. The export API contract changes in this local source; existing
persisted data stays compatible. Humation
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
streams. That run used local ADC; a dub through the deployed app (API service account) is the
remaining check.

Cloud Run keeps one warm instance (`min-instances 1`, workflow `53aab18`, deployed and
confirmed 2026-10-15), at approximately $1.73/day before allowances. Return it to zero after
judging if idle costs are no longer justified. Reviewer/orchestrator models remain 3.8 Flash:
the 3.5 Flash-Lite dev comparison lost three planted issues and had quota/service failures.

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
  polling. Signed media/evidence URL renewal while visible remains separate from job polling.
  The header shows the user's Humation avatar (restored at the owner's request). Marketing/caption fonts are no longer preloaded globally. Persona uses React Query.
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

## Review loop work on `main` (verified end to end)

The hackathon plan (Claude Doc "Resonance: Hackathon Plan of Action",
https://claude.ai/code/artifact/8c2813f9-0935-4e90-9cfc-3b1b557a1413) was executed in
worktrees under `../aibuildercup-wt/`, merged into `main`, and verified end to end. A push to
`main` deploys via GitHub Actions, so push only when the owner says so. Shipped and verified:

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
- **Edit plan and revisions (local source change; not deployed).** The Rough cut module and
  server render pipeline are removed. Review exports CMX3600 (.edl, 24/25/30/60 fps) and
  Markdown from the selected/latest completed run’s current accepted/revised findings.
  `GET …/analysis/{runId}/edit-plan/plan` returns the safe Cut/Note preview;
  `GET …/edit-plan/edl?format=cmx3600|markdown&fps=30&labels={...}` recomputes downloads.
  `labels` is a JSON-encoded finding-ID → cut/note map, request-local, with no writes.
  Both GETs work in the read-only demo; revision uploads remain disabled there. The Review
  card uploads externally edited source revisions through the existing normal upload/STT flow.
  Old module query/path links fall back to Review. Removed: render POST, per-cut DELETE,
  source-revision captions GET, render worker, transcript remapping and insert placement.
- **Comparison.** `GET …/analysis/compare?baseRunId=&targetRunId=` stays deterministic/read-only.
  Review opens the previous reviewed revision’s latest run → newest completed run comparison
  by default when the target revision is newer. The picker still supports any completed pair;
  existing paired players use the server alignment. Independent uploads use transcript
  alignment. Legacy `Asset.roughCut` kept-segment metadata, derived transcripts and the
  historical `rough_cut` job enum stay readable; no new jobs of that type can be queued.
  Project/account recursive deletion already covers all legacy assets/documents.
  OpenAPI, Firestore and design docs reflect these source changes; no infra/deploy changes.
  Verification: backend ruff/mypy (158 files) and `import app.main` pass; Uvicorn boots and
  `/api/readyz` returns 200. Web oxlint, ESLint (four existing library `<img>` warnings),
  TypeScript and all 17 production static pages pass, with existing static-export rewrite notices.
  `bun run format` ran; touched-file formatting is retained and unrelated baseline churn reverted.
  Local browser demo sign-in against live services, both old link formats → Review, the export
  card/empty state and disabled uploads were checked. Authenticated GET previews, all four
  CMX3600 frame rates and Markdown return 200 without any rendered asset. Invalid labels return
  400. A local deterministic smoke confirms Cut/Note duration changes, legacy exact alignment
  and transcript alignment for independent revisions. The demo currently has one review per
  project and no accepted findings, so populated toggles/expanded comparison and upload → STT →
  fresh review remain unverified live. No tests/dependencies, paid model calls, push or deployment.
- **Writer context.** `app/services/video_context.py` feeds transcript excerpt, persona (as
  preferences), accepted/revised or severe non-rejected findings, interest peaks and the strongest
  hook into drafts, assist, thumbnail planning and listings. `_fallback_blocks` is gone: failures set
  draft `status: failed` with an error. The thumbnail planner resolves the latest run.
- **Publish warnings, STT operation persistence, docs/infra cleanup and the editorial eval harness.**

## Interest model (retrained 2026-10-14, verified)

The heatmap's "Audience interest" lane and reviewer coverage tint are live (`544700f`,
deployed with `fbc2e80`). The method and current numbers are in `evals/interest/README.md`.

**Where it stands.** `backend/app/assets/interest/model.json` (recipe `mixed/full`, fallback now
`creator/transcript`) was retrained on 2026-10-14 with 87 creator videos from 81 channels (was
46). On unseen creator channels: lift ρ **0.151 [0.101, 0.200]** (was 0.172 [0.099, 0.241]),
lift peak precision 0.35, lift dip precision 0.35 (chance 0.25), overall ρ 0.28 against a position
baseline of 0.24. Transcript-only lift is 0.074 [0.029, 0.120]: above zero now, but too weak to
mark moments, so the fallback still marks none. The demo account's two runs were backfilled with
the new model (`interest_backfill.py --force`, live Firestore).

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

**Future roadmap ideas.**

- Per-creator calibration: once a creator connects YouTube (the `yt-analytics.readonly`
  scope is already granted), `interest_calibration_service.py` pulls up to 40 of their own
  videos' retention (`audienceWatchRatio`) through the official APIs and blends their channel's
  normalized retention shape with the generic baseline; full content-head refitting per channel
  is a future extension for large channels.

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
- Default creator library (2026-10-17): `CREATOR_PRESET_OBJECT` (GitHub variable and live
  Cloud Run env) points at
  `creator-presets/vlogbrothers-prehero-cc-by/96f25f96…598a/bundle.zip`: 29 CC BY pre-hero
  Vlogbrothers videos, 10 thumbnails, 142 nodes indexed (about $0.04). It replaces the Arun
  Prabhudesai preset (`creator-presets/arun-prabhudesai/270c9887…/bundle.zip`, still in the
  bucket). Accounts on the old preset switch on their next library read; an explicit operator
  import is never replaced. `aibuildercup@gmail.com` (`kmXLyn…`) and `demoCreatorHabeasCodus`
  also hold an explicit import of the same bundle (`backend/creator-libraries/`, gitignored).
  The accounts `rHyMoL5…` and `NrdGBY…` (earlier demo-recording account with the hero
  project) no longer exist in Auth or Firestore.

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
- STT submission and polling are separated (`start()`/`wait()`): `sttOperations` names are persisted
  before polling so polling errors resume the existing operation rather than resubmitting.

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

## End-to-end verification summary

All core workflows and studio modules have been verified end to end by the project owner, plus
automated static checks (`ruff`, `mypy`, `oxlint`, `eslint`, TypeScript and production static
export) and the pre-registered evaluation suites (`evals/README.md`):

- **Nine-reviewer + rubric + editor + adjudicator analysis:** Validated live on `gemini-3.8-flash`
  across all 20 editorial benchmark videos (`180/180` specialist runs succeeded, **1,136 live
  FFmpeg `extract_frame`/`cut_clip` tool calls**, 70+ Google Search grounding citations; see
  `evals/results/*.raw.json`) as well as in the end-to-end app workspace.
- **Review loop (previously verified deployment):** Finding decisions (`accepted`/`revised`/`dismissed`),
  footage adjudication (`adjudicator-v2`), creator-library links on findings, the prior server render workflow (removed in current source), and deterministic before/after run comparison (`GET …/analysis/compare`)
  are verified end to end.
- **Audience-interest lane & calibration:** Curve, position baseline, hover readout, info panel,
  peak/dip click (seek + finding filter), reviewer coverage tint, and YouTube Analytics
  calibration are verified.
- **Drafts, media preparation & packaging:** Grounded draft generation with video context and
  Search Suggestions, 5-style ASS/FFmpeg caption burn-in, Translation + cultural adaptation +
  timed TTS dubbing, Nano Banana 2 thumbnail generation/critique, local FFmpeg visual inserts,
  and bounded Veo B-roll inserts are verified.
- **Publishing, calendar & connectors:** YouTube OAuth upload, thumbnail/caption attachment with
  `Publish.warnings` (`THUMBNAIL_FORBIDDEN`, `THUMBNAIL_MISSING`, `THUMBNAIL_FAILED`,
  `CAPTIONS_SKIPPED`, `CAPTIONS_FAILED`), scheduled publishing, content calendar reconciliation,
  Substack/Medium/Reddit cross-posting, and Creator Library indexing/retrieval are verified.
- **STT operation persistence:** `start()`/`wait()` separation stores `sttOperations` names before
  polling and resumes them without duplicate resubmission on polling errors.
- **Editorial eval history:**
  - `DEV` (`evals/editorial/`, 5 videos, 20 planted flaws + 1 clean control, labels `2e13571`):
    post-hoc tuning target; frozen `ensemble_edited` (`editor-v6`, `rubric-v1`, `reviewers-v5`,
    `adjudicator-v2`) reached **20/20 (100%)** at **87% precision**, clean control 1, vs `rubric`
    19/20 at 90%, clean control 1.
  - `HELD-OUT` (`evals/editorial-heldout/`, 6 videos, 22 planted issues, labels `6df94ce`):
    specialists **22/22 (100%)**, `edited` **21/22 (96%)** (`22/22` on `timeOnly`) at **78%
    precision**, clean control 1, vs single prompt `baseline` 18/22 (82%), clean control 3, and
    `rubric` 20/22 (91%), clean control 2.
  - `LONG-FORM` (`evals/editorial-longform/`, 5 videos of 8–12 min, 32 issues, labels `9d48bf5`):
    Resonance **31/32 (97%) at 91% precision**, clean control 6, $0.44/video, vs `baseline` 27/32
    (4–0 discordant) and `rubric` 28/32 (3–0 discordant).
  - `REAL` (`evals/editorial-real/`, 4 CC BY videos, 5 creator-published corrections, labels
    `6f1f23f`): Resonance **4/5 (80%) on `timeOnly`** (all `medium` severity; **3/5** on strict
    `truth_evidence`-only `headline` because `cultural_localization` + `audience_brand` caught the
    Ukraine `okraina`/`krajina` borderlands error), vs 3/5 `headline` (2/5 actionable `medium+`)
    for `baseline` and 2/5 for `rubric` (which hit `429 RESOURCE_EXHAUSTED` and lost the Ukraine
    video).
  - **Pooled unseen pre-registered significance:** Across the 54 unseen planted issues
    (`HELD-OUT` + `LONG-FORM`), specialists beat the single prompt **53/54 (98.1%) vs 45/54 (83.3%)**
    (8–0 discordant, two-sided sign test $p = 0.0078$; 9–0 on actionable recall, $p = 0.0039$), and
    shipped edited beats the single prompt **52/54 vs 45/54** on `headline` (8–1, $p = 0.039$) and
    **53/54 vs 45/54** on `timeOnly` (8–0, $p = 0.0078$); across all 59 unseen gold issues
    (`HELD-OUT` + `LONG-FORM` + `REAL`), shipped Resonance leads **57/59 (96.6%) vs 48/59 (81.4%)**
    on `timeOnly` (9–0, $p = 0.0039$).

## Post-hackathon roadmap & operations notes

1. **Scale-out beyond single-instance hackathon guard.** Cloud Run is intentionally capped at
   `--max-instances 1` during the hackathon alongside the Cloud Billing kill switch. Scaling out
   for multi-tenant production uses durable Firestore worker leases, shared Pub/Sub realtime
   delivery, Cloud Scheduler for unattended due-slot sweeps, and managed vector indexing as
   library and project counts grow.
2. **Infrastructure cleanup.** Unused BigQuery datasets, worker subscriptions, dead-letter topics
   and five worker service accounts were removed from Terraform on 2026-10-14; run a reviewed
   `terraform apply` when ready to remove those legacy resources in GCP.
3. **Optional post-hackathon enhancements.** Human creator time-saved study
   (`evals/creator-comparison.md`), per-segment localization diff/flag view, calendar drag-to-move
   and ICS export, and non-Latin bundled caption fonts for server-side FFmpeg burn-in.

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
