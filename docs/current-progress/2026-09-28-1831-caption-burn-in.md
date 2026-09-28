# Burn captions onto video (FFmpeg caption worker)

## What I did

New feature: from the transcript card's **Export** menu, "Burn captions onto video" opens a
customizer and renders a **new MP4** with styled captions burned in. The original source video
is never modified.

- **Presets + curated controls**: five presets (`clean`, `bold_pop`, `boxed`, `karaoke`,
  `minimal`), then fine-tuning of font (Montserrat/Poppins), size, bold/italic/uppercase, text
  colour, outline colour/width, shadow, background (`outline`/`box`/`none`) with colour+opacity,
  position (top/middle/bottom), edge margin, chars-per-line, karaoke highlight toggle + colour,
  and speaker-name toggle.
- **Karaoke**: optional word-fill highlight. Word-level timings are not persisted, so each
  cue's duration is split across its words by character weight and rendered as ASS `\k` runs.
- **Live preview**: the dialog shows an HTML approximation of the burned caption (the same
  preset defaults drive both the preview and the server-side ASS builder).
- **A real FFmpeg worker**: `caption_worker` builds an ASS document and overlays it with
  libass (`ass` filter) using fonts bundled in the repo, then stores the MP4 and the ASS.

## Structural changes (contracts first)

- **`contracts/openapi.yaml`** — new paths:
  - `GET /api/caption-presets`
  - `GET|POST /api/projects/{projectId}/captions/renders`
  - `GET|DELETE /api/projects/{projectId}/captions/renders/{captionRenderId}`
  - `GET /api/projects/{projectId}/captions/renders/{captionRenderId}/download-url`
  - New schemas: `CaptionStyle`, `CaptionRenderRequest`, `CaptionPreset`, `CaptionPresetList`,
    `CaptionRender`, `CaptionRenderList`, `CaptionRenderAccepted`.
- **`contracts/firestore.md`** + **`docs/technical-design/db-design.md`** — new project
  subcollection `users/{uid}/projects/{projectId}/captionRenders/{captionRenderId}` and
  `caption_render` added to the job type list.
- **Backend**
  - `schemas/captions.py` — `CaptionStyle` (validated), request/response/preset models.
  - `services/caption_styles.py` — the five presets and `build_ass()` (pure; no I/O).
  - `services/caption_service.py` — render records, job hand-off, list/get/delete/download.
  - `workers/caption_worker.py` — the FFmpeg worker + `caption_render_after_response`.
  - `api/captions.py` — the routes; registered in `main.py`; deps in `dependencies.py`.
  - `schemas/jobs.py` — `JobType.caption_render`.
  - `services/paths.py` (+ `firestore_service.py` re-exports) — caption render paths.
  - `services/storage_service.py` — `upload_from_filename`, `download_to_filename`,
    `object_size` (streaming, so large media never sits in memory).
  - `services/video_tools.py` — `probe_video_size`, `run_ffmpeg_command`.
  - `config.py` + `.env.example` — `CAPTION_MAX_SOURCE_DOWNLOAD_BYTES` (default 300 MB).
  - `app/assets/fonts/` — bundled Montserrat + Poppins (Regular/Bold, OFL) so rendering is
    identical everywhere; `ass=fontsdir=` points at this directory.
- **Web**
  - `lib/types.ts` — caption types; `lib/captions.ts` — presets/options + preview styling;
    `lib/projects.ts` — preset/render API calls.
  - `components/projects/caption-burn-dialog.tsx` — the customizer, preview, progress, render
    history (download + delete).
  - `components/projects/transcript-panel.tsx` — menu item + dialog wiring.
  - `app/layout.tsx` — Montserrat/Poppins via `next/font/google` for the preview.

## Storage and deletion

Output goes under the **project prefix**, not a separate temp bucket:
`users/{uid}/projects/{pid}/renders/captions/{renderId}.mp4` (+ the generated `.ass`). This was
deliberate: the existing recursive project delete (`ProjectService.delete`) and account delete
already remove every object under that prefix and the whole Firestore subtree, so the feature is
covered by the current delete pathway with no new wiring. A `DELETE` endpoint also removes a
single render's objects and record. (A separate temp bucket would have needed its own delete
path and lifecycle policy, and would leak on project delete.)

## Decisions / gotchas

- **Fragmented MP4 makes a remote `ffprobe` scan the whole object and time out.** One of the two
  real source videos is fragmented (`moov` + many `moof`/`mdat`), so probing it over a signed
  HTTP URL hung. The worker now downloads sources up to `CAPTION_MAX_SOURCE_DOWNLOAD_BYTES` to
  its temp dir, probes locally (reliable) and encodes from the local file (seeks instead of
  re-reading fragments). That cut that render from ~6.5 min to ~1.3 min. Larger sources still
  stream from a signed URL so the temp disk cannot fill up.
- **`Blob.size` is `None` after `exists()`.** The first cut used `blob.exists()` then `blob.size`
  and always read size 0, silently skipping the local download. Fixed with
  `bucket.get_blob(...)`, which populates `size`.
- **Worker pattern**: implemented as an in-process background task (like `transcribe_worker` and
  `analysis_worker`), not a Cloud Run Job as `backend-plan.md` section 11 sketches. The API image
  already installs FFmpeg for the reviewer tools, so this needs no infra change. The Cloud Run
  Job is the scaling path if renders start competing with requests.
- **libass scales `PlayRes` to the real frame**, so a probe failure only mis-records width/height
  (cosmetic); the local-download path now keeps it accurate.
- **Fonts are bundled** (Montserrat, Poppins) because Debian's ffmpeg package pulls no fonts, and
  macOS does not ship these families. Latin only; CJK/Devanagari would fall back and need
  additional bundled fonts.
- **Karaoke is approximate** (character-weighted per-cue timing). Canonical transcript JSON
  stores `words: []`, so true word timings would require persisting them in
  `TranscriptService._persist_segments`.

## Verification (all run)

- **Live end-to-end against the real account** (uid `Ylno…`, projects `avengers doomsday
  analysis` and `doomsday trailer analysis`, fresh Firebase ID token):
  - Both renders: `202` accepted -> `rendering` -> `ready`.
  - Outputs: `avengers` 1280×720, 106.8 MB (`karaoke` preset); `doomsday` 1280×720, 98.3 MB
    (`bold_pop` preset). `download-url` returns HTTP 200 for both.
  - Extracted frames at t=60/300/600s and visually confirmed the burned captions (karaoke fill
    and uppercase highlight both render correctly).
  - `DELETE /captions/renders/{id}` -> 204, exercised twice and reused.
- **`backend/`**: `ruff check .` clean; `mypy app` clean (75 files).
- **`contracts/openapi.yaml`** parses; all caption paths/schemas present.
- **`web/`**: `bunx tsc --noEmit` clean; `bun run lint` (oxlint) 0/0; `bun run lint:eslint` 0
  errors (1 pre-existing unrelated `<img>` warning in `project-card.tsx`); `bun run build`
  succeeds (11 routes); the touched files pass `oxfmt --check`.

## Not done / next step

- No automated tests (per the repo rule); the happy path is verified live, but the failure paths
  (unreadable source, missing transcript, FFmpeg timeout) are only reasoned about.
- Progress is coarse (preparing 10 → rendering 35 → uploading 85 → 100); FFmpeg's
  `-progress` output could feed a real percentage.
- Only Latin fonts are bundled. If non-Latin projects use this, bundle a matching Noto family.
- A styled `caption` asset (a downloadable `.vtt/.srt` with the chosen look) is not produced;
  only the burned MP4 and the ASS.
- Consider a Cloud Run Job if renders ever run concurrently with request traffic on one instance.
