# Transcription and thumbnail 429 investigation

## Work completed

- Investigated the user's production failures using read-only Cloud Run configuration/logs, Cloud Billing status, Service Usage quota limits, Cloud Monitoring request/quota telemetry, and existing Speech-to-Text operations. Read the prior publishing handoff and technical-design index first.
- No application, API, schema, dependency, infrastructure, billing, quota, or deployment changes. No new transcription or image generation was requested. Unrelated working-tree files and the existing `fixtures/seed/.gitkeep` deletion remain untouched.
- Billing is enabled for `habeas-codus`. This is not evidence of a detached-billing kill switch. It does not establish current spend or available credits.

## Transcription: accepted work succeeds, polling fails

- Production failures at **2026-10-11 10:58–11:00 UTC** (16:28–16:30 IST), project `87a72d18f5594ce9adae12dad4525362`, job `69614b2f561fc2344cad67f0bd17706e`.
- Traceback places the `ResourceExhausted` 429 in `operation.result(600)` -> `Operations.GetOperation`, after `BatchRecognize` was accepted. Configuration uses the correct `us` Speech endpoint and Chirp 3.
- Actual effective quotas: US BatchRecognize **106/min**, US Operation requests **150/min**, US Resource requests **100/min**. No overrides on these limits.
- Monitoring during the failure window records batch usage of **7, 4, 1** in successive one-minute intervals, and operation quota usage of **5, 2, 6**. Request telemetry separately records GetOperation 429s. No `serviceruntime.googleapis.com/quota/exceeded` series was returned for either service in the inspected 07:30–11:15 UTC interval. This argues against exhausting the advertised project quotas; the provider's exact internal throttling reason is not exposed in the generic error.
- Listed the project's 48 existing speech operations without submitting work. **All 12 operations created during the latest failure window for this same project completed successfully**, with no operation/file error and **1,130 words each** in inline results. The app has marked an upload failed despite completed transcription being available upstream.
- Root application defect: `_recognize_with_retry` wraps submission and polling in one retry loop. A polling 429 submits another BatchRecognize operation instead of continuing to poll the original. The worker's idempotency does not prevent these duplicate upstream operations.
- Additional defect: `run_transcribe` tries normalized audio on every exception, including quota/throttling errors. This fallback is unrelated to capacity and can submit more work; it should be restricted to decoding/container failures.
- A read-only comparison on an older completed operation succeeded through both `SpeechClient.get_operation` and the generic LRO operations client. No evidence of a permanently broken polling endpoint or API-enable/IAM problem.

## Thumbnails: shared model capacity and inadequate backoff

- Two concepts failed around **2026-10-11 07:46 UTC** (13:16 IST), with all four attempts returning provider `429 RESOURCE_EXHAUSTED`. Cloud Monitoring independently records eight Vertex GenerateContent 429 responses around this window.
- The failed revision `creator-studio-api-00108-9ck` already had `VERTEX_LOCATION=global`. Current revision `creator-studio-api-00110-5pt` also uses global. Monitoring's processing location label of `us-central1` does not establish that the request endpoint was regional.
- Configured default image model is `gemini-3.1-flash-image`; the optional Pro setting is `gemini-3-pro-image`. The specific failed job's Pro flag was not confirmed, and normal image-provider info logs were not present in the retrieved window. Both configured model families use Standard PayGo shared capacity according to current Google documentation.
- Service Usage contains image-generation quota entries with default/effective **2/min**, including an explicit `gemini-experimental` dimension. **Do not present this as proof that the current GA Gemini image models are limited to two requests per minute.** Google explicitly lists Gemini 3.1 Flash Image and Gemini 3 Pro Image under Standard PayGo, without usage tiers applying to these models. Shared-capacity 429s do not necessarily mean a fixed quota was exhausted.
- `ImageGenProvider` reuses text LLM retry settings: four attempts with **0.5, 1, 2 second** waits, only 3.5 seconds of deliberate waiting. This provides little recovery window when model capacity is unavailable. Rendering is serial within a thumbnail batch, but distinct jobs can overlap and there is no shared pacing.
- Shared model capacity is the best-supported explanation for thumbnail failures, rather than billing, IAM, the wrong endpoint, or a confirmed editable quota limit. Exact per-request capacity admission decisions remain unavailable.

## Recommended next work

1. Separate STT submission retries from result polling. Retry GetOperation on the existing operation with bounded backoff and a total job deadline; do not resubmit recognition when only polling fails. Log/store the operation name under the existing project/job so retries can resume work rather than abandon it.
2. Exclude throttling/capacity errors from the normalized-audio fallback. Recover the existing failed upload from its completed upstream operation if repairing its project/job state is requested; do not incur another recognition call just to recover it.
3. Give images their own bounded retry timing, jitter, and request pacing across jobs. Preserve current cost caps and avoid unbounded retry loops or purchasing reserved throughput for the demo.
4. A Console quota increase is not justified by the inspected evidence. If 429s persist after correcting retry handling, use the timestamps, affected method/model, and low quota usage when escalating to Google support.

## References and validation

- [Google Standard PayGo: 429s and supported image models](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/standard-paygo), inspected 2026-10-11; page last updated 2026-10-10.
- [Google's 429 troubleshooting](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/deploy/error-code-429).
- [Project quotas](https://console.cloud.google.com/iam-admin/quotas?project=habeas-codus); filter Speech-to-Text for US endpoint BatchRecognize/Operation requests.
- Read-only queries returned successfully; full returned metric pages were checked where relevant. Initial broad log matching also found successful HTTP requests whose *response size* was 429 bytes; those were excluded from the diagnosis.
- Documentation-only investigation; no runtime changes requiring backend/web build checks. Ran whitespace validation for this handoff. No tests were added, and no commit/push was performed for this investigation.
