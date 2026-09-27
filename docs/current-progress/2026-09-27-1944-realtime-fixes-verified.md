# Progress — realtime flow debugged and verified end to end (2026-09-27 19:44)

Follow-up to `2026-09-27-1915-websocket-transcript-reviewer-flow.md`. The first cut of the
WebSocket flow did not actually work in production. Two root-cause bugs, both mine, found by
running an authenticated end-to-end test with a real Firebase ID token (the previous note's
local smoke test only covered *unauthenticated* rejection, which is why it passed). Fixed in
`ca6e484` and verified on prod.

## Bug 1 — the socket never completed its handshake

`ws_endpoint` only accepted the socket implicitly on the first `send`, which was the writer's
**30s ping**. Until then the handshake sat unaccepted, so Cloud Run's front end timed out the
upgrade and returned **HTTP 403** (empty body, `server: Google Frontend`, which initially made
it look like a Google-side rejection). Effects:

- browser logged a WS request that "did nothing" — never opened, never received frames;
- client reconnect loop (backoff) → on every reconnect the hook re-invalidated project /
  transcript / analysis-runs / assets → **the `/transcript` calls the user saw repeatedly**;
- `connected` never became true → the polling fallback stayed on → **slow, noisy loads**.

Why the earlier prod probe misled me: a *bogus* token hit `_authenticate`'s failure path, which
**does** call `accept()` (then closes 4401) — so it looked healthy. Only a valid token reached
the success path that forgot to accept. A tampered-signature token also took the failure path,
which is how the diagnosis was narrowed.

Fix: call `await socket.accept()` immediately after auth succeeds. Evidence: prod now connects
in ~2s and delivers `snapshot.project` in ~2.5s.

## Bug 2 — the LLM call blocked the event loop

`providers/llm.py` called the **synchronous** `client.models.generate_content` inside an `async`
function. Each reviewer call blocked the whole event loop (a single-instance service) for
seconds, starving the socket's heartbeat (the test client died with `1011 keepalive ping
timeout`) and stalling every HTTP request while a job ran. This is the "refresh takes ~60s"
behaviour when an analysis is in flight.

Fix: `await asyncio.to_thread(client.models.generate_content, ...)` and build the genai client
once (`get_providers` is `lru_cache`d, so the instance cache is effective) instead of per call.

## Verification

Local (uvicorn, real token, real Firestore):

- WS upgraded in 1.4s, snapshot in 3.8s.
- Started a real analysis while subscribed: received `analysis.progress` per reviewer
  (incrementally listing succeeded dimensions) and `analysis.ready` — the socket stayed open.

Production (`wss://creator-studio-api-3sim77rugq-uc.a.run.app`, real token):

- **Full flow**: created project `4cd8572f70024c5b9652097e351c1b10` ("fixtures e2e (WS)"),
  uploaded `fixtures/media/career_advice.mp4` via the signed URL, `complete` → 202.
- Frames over the socket: `project processing` + `job 5% speech_to_text` at 8s →
  `job 70% segmenting` at 52s → `project ready` + `job succeeded` + `transcript.ready`.
- Then `POST /analysis` → per-reviewer `job.progress` 22→85% and `analysis.ready`
  (`overallScore 3.2`, finding counts) at 94s.
- Entire upload → transcript → analysis took **94 seconds**.
- The test project is left in the account so it can be checked in the browser; delete it if not
  wanted (`DELETE /projects/{id}` covers the GCS prefix + Firestore tree).

## Also observed (not fixed — user decision)

- Running 6 core reviewers concurrently hit Gemini **429 RESOURCE_EXHAUSTED** on vertex and
  retried (`llm_retry_base_seconds`). Analysis still completed. If it gets worse, lower
  `max_concurrency` in the analysis fan-out or raise the retry budget.
- Sync Firestore/Storage calls still block the loop briefly (ms). The multi-second calls
  (STT, LLM) are now off-loop. GCS transcript/VTT/SRT writes in the transcribe worker are the
  next candidates if loop latency matters.

## Not done

- Browser verification by the user (the headless script proves transport + frames, not the
  React rendering).
- Consider reducing the client's reconnect-invalidation set (it invalidates 4 keys on every
  reconnect; now that reconnects are rare it is no longer hot).
