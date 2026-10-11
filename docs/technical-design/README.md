# Creator Helper Studio — Technical Design Package

This directory contains the implementation-ready design for the Creator Helper Studio MVP.

## Documents

1. [Firestore database design](./db-design.md)
   - Complete Firestore hierarchy.
   - Nested projects, jobs, events, transcripts, analysis runs, reviewers, findings, heatmap bins, artifacts, localization, chat, audit, and deletion data.

2. [API design](./api-design.md)
   - Authentication conventions.
   - REST endpoints.
   - Asynchronous job contracts.
   - Pub/Sub event envelopes.
   - Chat, analysis, localization, artifact, and deletion APIs.

3. [Architecture and use-case diagrams](./diagrams.md)
   - Mermaid system architecture.
   - End-to-end flows for onboarding, integrations, upload, transcription, review, heatmaps, shorts, localization, thumbnails, text content, Veo, chat, persona updates, and deletion.

4. [Frontend implementation plan](./frontend-plan.md)
   - Next.js initialization.
   - Routes and component tree.
   - Onboarding, project workspace, timeline, heatmap, artifacts, localization, audience insights, and chat.

5. [Backend and AI implementation plan](./backend-plan.md)
   - FastAPI plus Google ADK decision.
   - Backend repository structure.
   - Workers, Pub/Sub, transcription, multi-reviewer analysis, project chat, connectors, media jobs, and tests.

6. [Infrastructure and IAM plan](./infra-plan.md)
   - Terraform structure.
   - GCP projects, APIs, buckets, Pub/Sub, BigQuery, Firestore, human users, service accounts, IAM, secrets, CI/CD, monitoring, and owner checklist.

7. [Fixtures and seed design](./mock-and-seed.md)
   - Provider abstraction over every external dependency (no mock mode).
   - Media fixtures, seed script, and demo scenarios.

8. [Three-engineer workstream plan](./workstreams.md)
   - Lane ownership for three engineers.
   - Repo layout, phases, and coordination rules.

9. [Localization corpus design](./localization-corpus.md)
   - Global corpus and per-project glossary.
   - Sources, storage, runtime pipeline, and versioning.

10. [Video packaging](./packaging-plan.md)
    - Saved editable YouTube listings, grounded visual inserts, rendering and paid reservations.

## Key decisions

- Region is **`us-central1`** for all services except Speech-to-Text, which uses the **`us` multi-region** (the multilingual Chirp 3 model is GA there but not in `us-central1`); Veo, Imagen, and Text-to-Speech use `us-central1`.
- Backend is Python FastAPI + Google ADK. Genkit is intentionally not used, to keep one agent runtime.
- All external dependencies sit behind providers; development runs against the real free-tier services with `fixtures/media/`.
- Reviewer analysis fans out one reviewer per dimension in a single bounded pass; a reviewer may pull frames or short clips mid-review (FFmpeg function-calling tools) to ground visual claims, so there is no separate deep-review flow.

## Suggested implementation order

~~~text
1. Contracts, provider layer, seed skeleton, Terraform bootstrap
2. Firebase Authentication and API authentication
3. Project creation and direct Cloud Storage upload
4. Pub/Sub event handling and transcription worker
5. Transcript viewer and timeline
6. Multi-reviewer analysis and heatmap
7. Artifact generation and project chat
8. YouTube sync and BigQuery insights
9. Localization, thumbnails, shorts, and optional Veo generation
10. Security, deletion, observability, and demo polish
~~~

