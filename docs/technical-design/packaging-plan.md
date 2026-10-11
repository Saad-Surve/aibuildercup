# Video packaging: listings and visual inserts

The packaging module offers a saved YouTube listing and suggested supplementary visual
inserts. These use the uploaded video's current transcript and sampled video frames. Each footage idea then uses three nearby
frames and a short surrounding clip to analyze the source look independently of shot design. Optional creator-library retrieval informs voice and presentation;
current-video facts remain the source for claims. The API is defined in
[OpenAPI](../../contracts/openapi.yaml); persistence in
[Firestore](../../contracts/firestore.md).

## Listing workflow

`POST /projects/{id}/packaging/listing/generate` creates a project-scoped job. Gemini
Flash Lite writes a title, description, tags, up to three alternative titles, and a rationale.
The worker formats optional chapters from actual transcript segment indices, enforcing
00:00 as the first chapter, at least three chapters and ten-second spacing. No generated
time arithmetic is trusted. `PUT /projects/{id}/packaging/listing` saves creator edits.

The packaging panel displays creator-history sources. Publishing automatically fills fields
the creator has not edited; each field stays editable. An explicit "Replace fields with saved
listing" action applies the saved listing to all three fields. Existing upload edits survive
listing refreshes. Generating or editing metadata does not upload a video. Source video or
transcript replacement marks the saved listing stale and prevents its automatic reuse.

## Visual insert workflow

`POST /projects/{id}/visual-inserts/suggest` asks Gemini for at most three six-second
supplements: a comparison chart, explanatory callout, or illustrative footage. The server
derives source timestamps and quotes from selected transcript segments. Chart values
must appear as digits in their exact cited transcript passages; model instructions also
require a common unit and comparable quantities. These checks establish literal evidence,
not an independent factual review of the source video.

Charts and callouts render to silent H.264 MP4 with Pillow-drawn geometry and
FFmpeg/libass-shaped text. Both landscape and portrait are supported. Full source evidence
remains in the panel; long on-screen quotes use a short excerpt. B-roll uses
`veo-3.1-fast-generate-001` through the video provider in `us-central1`, at 720p without audio.
The proposed `gemini-omni-1.1` name could not be verified as a callable video model.

Footage direction follows the [researched Veo guidance](../research/veo-source-style-2026-10-11.md).
An observation pass sees only source footage and records palette, lighting, framing, texture,
movement and setting. A separate director designs a single shot within that recipe. A clear,
relevant source frame can become Veo's actual opening image; otherwise it is displayed as
style evidence and Veo receives a structured text prompt plus the transferable recipe. The
panel shows the reference, observed look and conditioning reason. Image-conditioned shots
retain the source aspect and use motion-focused direction. Text-mode edits preserve observed
color/light/texture/camera qualities. Exact submitted positive/negative prompts are saved
before submission; resuming an operation never replans it. Old unsubmitted ideas need fresh
suggestions.

The creator can edit the footage prompt and choose an aspect ratio before pressing the
priced generation action. `allowPaidGeneration` is required. A transaction reserves at most
two paid slots per project, bounded further by the configured budget. The default conservative
reservation is $2.40 per six-second attempt, rather than a claim about actual invoice cost.
Reservations survive failure and insert deletion. Concurrent/duplicate render requests reuse
an active or completed job. A saved Veo operation is polled on retry; unconfirmed submissions
are never automatically resubmitted. Completed or filtered operations cannot be retried as
new billable calls. Poll timeout exposes a resume action.

Ready clips have a signed playback/download URL. Creators download and add them in their
video editor. This feature does not splice the inserts into the source video or cut automatic
shorts. Individual insert deletion removes its record and Storage prefix. All packaging
records, jobs, paid reservations and media use the existing user/project-owned paths.
Project/account deletion marks the parent before removing objects, rejects subsequent
ownership-checked writes, and lets the packaging worker remove a late upload. Versioned
Storage generations still follow the bucket lifecycle, as in the existing delete pathway.

## Configuration and implementation

`MODEL_PACKAGING`, `MODEL_VIDEO`, `VISUAL_INSERT_MAX_PAID_RENDERS`,
`VIDEOGEN_PRICE_PER_SECOND_USD`, and `VIDEOGEN_POLL_TIMEOUT_SECONDS` configure the
feature. Defaults work without infrastructure changes. Runtime requires the existing
FFmpeg/libass/font support plus Pillow, installed through uv.

- Router/schemas: `backend/app/api/packaging.py`, `backend/app/schemas/packaging.py`.
- Service/worker: `backend/app/services/packaging_service.py`,
  `backend/app/workers/packaging_worker.py`.
- Media: `backend/app/services/visual_insert_renderer.py`,
  `backend/app/providers/videogen.py`.
- Client/panels: `web/src/lib/packaging.ts`, `web/src/hooks/use-packaging-listing.ts`,
  `web/src/components/projects/studio/{listing,visual-inserts}-panel.tsx`.

Generation workers run in the existing single-instance background-job deployment. Durable
worker recovery/distributed scheduling remains the platform's next scale step; this feature
does not add a separate worker service.
