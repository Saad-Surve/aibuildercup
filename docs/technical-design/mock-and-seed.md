# Creator Helper Studio — Fixtures, Development, and Seed Design

Goal: develop and demo the product without burning paid AI credits, while keeping every
integration real. Development calls the **live free-tier GCP services** (Gemini flash,
Speech-to-Text) against the sample videos in `fixtures/media/`.

## 1. Why

- Paid calls (Veo, Imagen, Gemini Pro) are expensive and must stay behind the cost cap.
- A demo must always render a full workspace even if a live dependency is slow.

## 2. Provider layer (no mock mode)

Every external dependency sits behind an interface in `backend/app/providers/` with a real
implementation. Feature code never imports a Google SDK directly.

The earlier cassette / `MOCK_MODE` layer (`off`/`auto`/`on`, `fixtures/cassettes/`) was
**removed**. There are no mock or cassette branches in the code; see
[backend-plan.md](./backend-plan.md) section 16. Providers today: `llm.py`, `stt.py`; the rest are
added as their features land.

## 3. Media fixtures

`fixtures/media/` holds committed sample videos used to exercise the upload -> transcription
pipeline end to end without hunting for a file:

```text
career_advice.mp4   explainer.mp4        hindi_education.mp4
cooking_recipe.mp4  home_workout.mp4     personal_finance.mp4
tech_review.mp4     travel_vlog.mp4
```

They are MP4/AAC 44.1 kHz stereo, which is why the STT provider uses an explicit AAC decoding
config (STT V2 cannot auto-detect AAC in a video container).

## 4. Seed script (planned, not built)

`backend/scripts/seed.py --demo` will create a reproducible demo world:

```text
2-3 demo users (Firebase Auth) with completed onboarding
3 projects, each with one uploaded demo video in GCS
transcripts with word timestamps + VTT/SRT
analysis runs with findings + heatmap bins
clip candidates + one rendered short
one localized (Hindi) captioned + dubbed version
a couple of chat threads with messages
BigQuery rows for posts, metrics, comments, sentiment, audience aggregates
```

It will be idempotent and read the same JSON shapes the API returns, so the frontend cannot tell
the difference between seeded and live data. `fixtures/seed/` is reserved for that bundle.

## 5. Demo scenarios (planned, not built)

`GET /demo/scenarios` will list named scenarios pinned for the stage (good video, controversial,
regional, empty/mid-processing). The project creation dialog's `projects.isDemo` flag will bind a
project to a scenario.

## 6. Frontend

- Types and the API client are generated/derived from `contracts/openapi.yaml`.
- There is no MSW mock layer; the web app calls the real API.

## 7. Acceptance

- Development runs end to end against real free-tier services with `fixtures/media/`.
- Paid calls (Veo, Imagen, Gemini Pro) never run outside the cost cap.
- The seed script reproduces an identical demo workspace on a clean project.
- No secret or token appears in any fixture.
