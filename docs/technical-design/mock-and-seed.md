# Creator Helper Studio — Mock, Cassette, and Seed Design

Goal: develop the entire product without burning AI credits or needing real platform accounts,
while keeping every integration real enough to flip live for the demo.

## 1. Why

- You do not have social accounts with enough real content to make the connectors interesting.
- Repeated Gemini / Speech / Veo calls during development are expensive and slow.
- A demo must always render a full workspace even if a live API is down.

So: build the real integrations, but run development on deterministic fixtures, and record real
responses once so they can be replayed.

## 2. Provider abstraction

Every external dependency sits behind an interface with a real implementation and a fixture
implementation. Selection is by environment variable.

```text
providers/
  llm.py         Gemini / ADK       RealLlm        CassetteLlm
  stt.py         Speech-to-Text     RealStt        CassetteStt
  translate.py   Cloud Translation  RealTranslate  CassetteTranslate
  tts.py         Text-to-Speech     RealTts        CassetteTts
  videogen.py    Veo                RealVeo        CassetteVeo
  imagegen.py    Imagen             RealImage      CassetteImage
  social.py      YouTube / Meta     RealSocial     FixtureSocial
```

A reviewer, a media job, or the chat agent never imports a Google SDK directly. It calls the
provider. That is what makes the mock layer possible without littering conditionals.

## 3. Modes

| Mode | Behaviour |
|---|---|
| `MOCK_MODE=off` | Always call the real service. Used for the live demo moment. |
| `MOCK_MODE=auto` | Look up a cassette by request hash. On hit, replay. On miss, call real once and record. Default for development. |
| `MOCK_MODE=on` | Always replay from cassettes. Never touch the network. Used for offline work and CI. |

`FixtureSocial` is always fixture-backed because real platform access is not guaranteed
(see the connector risk in `infra-plan.md`). The real connector exists and is exercised manually
once against a test channel.

## 4. Cassette format

A cassette is one recorded provider response plus the key that identifies the request.

```json
{
  "key": "sha256(provider+model+promptVersion+canonicalRequest)",
  "provider": "llm",
  "model": "reviewer-flash",
  "promptVersion": "clarity-v1",
  "createdAt": "timestamp",
  "requestSummary": "clarity review, 85 segments, en-IN",
  "response": { }
}
```

Rules:

- The key is a hash of the canonicalised request, so prompt changes intentionally miss the cache.
- Cassettes live in `fixtures/cassettes/{provider}/{key}.json` and are committed.
- Never put secrets, user tokens, or private video content in a cassette.
- Every cassette response is human reviewed before commit.

## 5. Seed script

`backend/scripts/seed.py --demo` creates a reproducible demo world:

```text
2-3 demo users (Firebase Auth) with completed onboarding
3 projects, each with one uploaded demo video in GCS
transcripts with word timestamps + VTT
analysis runs with findings for all 13 dimensions + heatmap bins
clip candidates + one rendered short
one localized (Hindi) captioned + dubbed version
a couple of chat threads with messages
BigQuery rows for posts, metrics, comments, sentiment, audience aggregates
platform connections in a "connected" state pointing at fixture data
```

The seed is idempotent and can be re-run. It reads the same JSON shapes the API returns, so the
frontend cannot tell the difference between seeded and live data.

## 6. Demo scenarios

`GET /demo/scenarios` lists named scenarios pinned for the stage:

```text
good_video        a clean video with a few medium findings
controversial     a video with truth + legal findings, high severity
regional          a video that trips the cultural/localization reviewers
empty             a fresh project mid-processing to show live states
```

The project creation dialog offers a "demo project" flag (`projects.isDemo = true`) that binds a
project to a scenario, so a demo is one click and always lands on interesting content.

## 7. Frontend fixtures

- A generates TypeScript types and the API client from `contracts/openapi.yaml`.
- MSW handlers are generated from the same fixture JSON the seed script uses.
- `NEXT_PUBLIC_MOCK_MODE=on` runs the UI with zero backend, which lets A work fully parallel.

## 8. Acceptance

- `MOCK_MODE=on` runs the entire product with no network and no GCP credentials.
- `MOCK_MODE=auto` records a cassette the first time a real call happens.
- The seed script reproduces an identical demo workspace on a clean project.
- No secret, token, or private media content appears in any fixture.
