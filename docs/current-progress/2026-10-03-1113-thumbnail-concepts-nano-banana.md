# Thumbnail concepts with Nano Banana (grounded, real-face, versioned)

## What I did

Built the thumbnail concept feature end to end: a creator generates several grounded thumbnail
options from the video, sees an honest critique of each, edits any of them in plain language,
and applies the winner to the project's packaging promise.

The design thesis (agreed with the user): a "generate a thumbnail" button is a commodity. This
project already owns the rare input — a timestamped transcript plus nine reviewers — so the
feature argues for a thumbnail using the video's own signal, puts the creator's **real face** in
it, and tells them **why** it works.

Pipeline per batch: an LLM planner reads the transcript + the active analysis run's findings +
the title + the creator persona and writes one concept per placeholder (headline, visual
direction, source timestamp, evidence-citing rationale); FFmpeg pulls reference frames around
that timestamp from the source video; Gemini image generation ("Nano Banana") renders each
concept around the real person; a cheap multimodal pass critiques legibility, promise-vs-content
(anti-clickbait), and platform fit. Edits feed the active image back to the model and append a new
immutable version.

## Model choice and probe

Followed up `2026-10-03-1015` with live probes on Agent Platform (`global`, ADC):

- `gemini-3.1-flash-image` returns a PNG part via `client.models.generate_content` with
  `config={"response_modalities": ["IMAGE"], "image_config": {"aspect_ratio": "16:9",
  "image_size": "1K"}}`. 512 and 1K confirmed.
- Reference-image input works (a real frame as a `Part.from_bytes`), and feeding a generated
  image back with an edit instruction produces a new image — the multi-turn edit path.
- `MODEL_IMAGE` now defaults to `gemini-3.1-flash-image` in `config.py`, `.env`, and
  `.env.example`. `model_image_pro` (`gemini-3-pro-image`) is opt-in per request.

## Structural changes

- **Provider layer.** `providers/base.py`: `ImageGenProvider.generate` now takes
  `aspect_ratio`, `image_size`, `reference_images`, and `base_image`, and returns
  `GeneratedImage`. New `providers/imagegen.py` (retry + validation) and
  `providers/gemini_client.py` (one cached `genai.Client` per project/location, shared with
  `llm.py`, which was refactored to use it). `providers/__init__.py` exposes `images`.
- **Config.** `model_image`, `model_image_pro`, `imagegen_max_concepts`,
  `imagegen_default_aspect|size`, `imagegen_price_per_image_usd`, `thumbnail_reference_frames`,
  `thumbnail_frame_max_width`.
- **Contract (frozen).** `contracts/openapi.yaml`: five `/projects/{projectId}/thumbnails...`
  paths and the `Thumbnail*` schemas. `contracts/firestore.md`: `thumbnailConcepts/{thumbnailId}`
  in the hierarchy plus a document section.
- **Data.** `thumbnailConcepts/{thumbnailId}` under the project subtree; images at
  `.../thumbnails/{thumbnailId}/v{n}.{ext}`; reference frames at
  `.../thumbnails/{thumbnailId}/refs/f{ms}.jpg`. All inside the existing recursive project /
  account delete — no extra delete wiring (verified: delete removed the GCS objects).
- **Backend.** `schemas/thumbnails.py`, `services/thumbnail_service.py` (persistence, job
  hand-off, budget guard, apply), `workers/thumbnail_worker.py`, `api/thumbnails.py`,
  `dependencies.py`, `main.py`, `services/paths.py` + `firestore_service` re-exports.
- **Web.** `lib/types.ts` + `lib/projects.ts` (types/API), new
  `components/projects/studio/thumbnail-panel.tsx`, rebuilt `packaging-module.tsx` (real
  thumbnail section; clips/SEO remain mocks), `video-studio.tsx` passes props, `lib/studio.ts`
  marks `packaging` ready.

`JobType.thumbnail` and `AssetType.thumbnail` already existed and are used as-is.

## Decisions and gotchas

- **Real frames must be staged locally.** Extracting frames straight from a signed URL was
  flaky (a fragmented MP4 makes FFmpeg's seek fail): the first live batch produced 0 refs for one
  concept and 1 for another. Downloading the source to a temp dir first (same reasoning and
  budget as `caption_worker._stage_source`) fixed it — all three reference frames then extracted,
  and the ref-based concept was visibly far better (real creator, strong composition). The temp
  dir is a `TemporaryDirectory` that cleans itself on function exit.
- **Grounded, not generic.** The planner is fed the active analysis run's findings ranked by
  severity, so a rationale can cite the actual evidence; the critique is anti-clickbait by design
  (`promise` axis). This reuses the project's whole thesis rather than bolting on an image API.
- **Apply closes the loop.** `POST .../apply` writes the concept's headline + rationale to
  `project.thumbnailConcept`, which `reviewer_base` already reads as packaging context.
- **Versioned and non-destructive.** Every edit appends a `ThumbnailVersion`; the active one is
  pointed at by `activeVersionId`. Same shape as the Draft studio.
- **Budget guard.** `ThumbnailService._guard_budget` refuses a batch that would push the summed
  image cost past `max_project_cost_usd` (`THUMBNAIL_BUDGET_EXCEEDED`). Cents at demo scale.

## Verification (all run)

- Backend: `ruff check` clean; `mypy app` clean (85 files); `create_app().openapi()` lists the
  five thumbnail paths and ten `Thumbnail*` schemas.
- Web: `bunx tsc --noEmit` clean; `bun run lint` (oxlint) clean; `bun run lint:eslint` 0 errors;
  `bun run build` succeeds.
- **Live end to end** (token supplied, project `chicken curry`, which has a ready analysis with
  findings): `POST /thumbnails` (2 concepts) → job `succeeded`; concepts had real headlines,
  evidence-citing rationales, and critiques. A 1-concept batch confirmed
  `referenceTimestampsMs: [94200, 95000, 95800]` (all three frames). `POST .../revise` appended
  version 2 and preserved the likeness; `POST .../apply` wrote `project.thumbnailConcept`;
  `DELETE` returned 204 and removed the GCS objects.
- No tests added (repo policy). No commit.

## Not done / next step

- The live test left three concepts on the `chicken curry` project (one applied, two extras) as
  working demo data; delete them from the module if unwanted.
- Not yet wired: the project card could show the applied thumbnail as its poster; the reviewers
  could receive the generated image itself (not just the text concept); infographic clips and the
  SEO listing are still mocks in the packaging module.
- `imageSize` is accepted per request but the UI only offers the default; a 2K/4K control and a
  "use my own photo as a reference" upload are natural follow-ups.
