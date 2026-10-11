# Resonance fixtures and demo

Development uses live Google APIs through providers, with local media/import fixtures.
There is no cassette/mock mode. Free allowances depend on service/model/account; real calls
can be billed. [Costs](../costs.md) and [evals](../../evals/README.md) describe bounds.

## Local media

`fixtures/media/` is **gitignored**, not a bundle of committed videos. The existing local
folder includes explainers, Hindi education, technology, finance, workout and travel videos.
Use normal upload/transcription to exercise media; do not claim a fresh clone includes these
originals. Preserve existing files. AAC-in-video inputs use explicit STT decoding.

Constructed chart variants in the local folder are diagnostics, not natural creator mistakes
or viewer-study results. Their README references a preparation script absent from the current
tracked tree; verify provenance/media before using them as evidence.

## Public read-only demo

`POST /api/demo/session` mints a Firebase custom token for the configured shared UID.
Visitors sign in without a published password; backend middleware blocks writes and the web
shows disabled controls. Existing content was copied from a real workspace with
`backend/scripts/copy_user_content.py`. Historical analyses retain old prompts/dimensions;
a good demo needs fresh compatible results, not fabricated score changes.

There is no generic `seed.py`, `/demo/scenarios` API or complete fake analytics world.
Do not describe those old designs as implemented.

## Creator corpus

[Folder import](../creator-demo-import.md) validates supplied transcripts, writing and
thumbnails before installing an owned revision in Firestore/Storage. It does not grant
OAuth publishing access or automatically transcribe original videos into projects.
[Public corpus collection](../creator-public-corpus.md) retains attributed real material,
availability reports and precomputed vectors. Server-controlled preset installation reuses
that index with no new model calls, clearly naming the example creator.

Shared immutable presets survive account deletion; user copies follow the owned lifecycle.
Local source originals and embedding caches stay ignored. No private credentials, generated
replacement captions or invented audience measurements belong in evidence fixtures.

## Verification

Use Ruff/mypy, web lint/build and bounded real-data scripts. The repository does not add test
suites/testing libraries. Explicitly state which live workflows ran, what was only inspected,
and whether a demo record predates the current implementation.
