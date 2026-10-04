# YouTube connector: feasibility and source-data options

## What I did

Assessed the effort to build the YouTube connector and researched which creators /
videos can legally be used to seed the hackathon demo. No code changed.

## Current state (greenfield)

The connector does not exist at any layer:

- No `backend/app/connectors/`, no `providers/social.py`, no `workers/social_sync_worker.py`.
- No connections router; `contracts/openapi.yaml` has **no** `/connections` paths.
- No OAuth settings in `config.py`; `youtube.googleapis.com` is **not** enabled in
  `infra/services.tf` (only mentioned in `infra-plan.md`).
- Web nav links to `/connections` (`app-shell.tsx`) but there is **no route page**.
- `events.py` maps `social.sync.requested/completed` but nothing produces or consumes them.

The design is specified in `api-design.md` §4, `backend-plan.md` §12, and `db-design.md`
(`users/{uid}/connections/{connectionId}` + `syncRuns`, KMS/Secret Manager token refs).

## Effort tiers

- **Tier 0 - API-key seed (no OAuth):** fetch public metadata with an API key
  (`channels.list`, `playlistItems.list`, `videos.list`) and write it into the Firestore /
  BigQuery shapes via a seed script. ~1-2 days. No media, no transcripts.
- **Tier 1 - OAuth connect + metadata/stats sync:** OAuth client + consent screen (Testing),
  state/PKCE, callback, encrypted refresh token, token refresh, sync worker, 5 endpoints.
  ~3-5 days; dominated by OAuth UX, token security, quota handling. Medium risk.
- **Tier 2 - owned-video captions:** `captions.list` (50 units) + `captions.download`
  (200 units, OAuth + ownership). +1-2 days.

## The hard constraint

The official Data API gives **public metadata for any channel with a plain API key**, but:

- No transcript/caption access for videos you do not own (`captions.download` returns 403),
  and no endpoint for auto-generated captions.
- No video download. So the media needed for the heatmap player, thumbnail frames, and STT
  cannot come from the API at all.

Therefore "load a creator's data directly" is **metadata-only** unless the media/transcript
comes from an owned channel (OAuth), a rights-cleared dataset, or CC / public-domain media you
may download.

## Usable sources (rights)

- **Own / consenting channel** - cleanest; exercises the real OAuth path.
- **NASA** (+ Goddard/JPL/Ames) - US government work, public domain; large, high-quality,
  long-form. Courtesy attribution.
- **ESA** - CC BY-SA 3.0 IGO. **Blender** open movies - CC BY (full-quality downloads).
- **Prelinger Archives / Internet Archive** - public domain film.
- **CC BY filter** on YouTube search - reuse allowed with attribution (four million+ videos).
- **Caution:** CS50 / Khan / MIT OCW are CC BY-**NC**-SA (hackathon/non-commercial fine, but
  generated clips inherit ShareAlike); TED / TED-Ed are CC BY-NC-**ND** - **ND forbids the
  derivatives** the studio exists to make, so avoid ND entirely.
- **Oxylabs** training-rights sample: metadata + transcripts, but **no media files**.

## ToS / quota gotchas

- YouTube API Developer Policies: 30-day cap on storing API data, attribution, no separation
  from the player, no downloading/scraping. Fine for a prototype, but designed around.
- Quota: 10,000 units/day default; `search.list` = 100 (separate 100/day bucket after the
  June 2026 change); use `playlistItems.list` (1) instead of search for a channel's uploads.
- Unverified OAuth consent screen works in Testing mode for <=100 test users; public launch
  needs verification (weeks).

## Recommendation

Build Tier 1 for the demo story, but keep the demo deterministic with Tier 0: seed a couple of
`demoProfiles` from a public-domain/CC channel (NASA or Blender) for **media**, an owned/friendly
channel for the **OAuth** beat, and the API-key seed for **metadata**. Add `youtube.googleapis.com`
to `services.tf` and add the `/connections` paths to `contracts/openapi.yaml` first.

## Confirmed demo-seed sources (pre-authorized reuse)

To load real content and exercise the flows end to end:

- **PleIAs/YouTube-Commons** - 2.06M CC-BY videos, 721k channels, 22.7M transcripts (title /
  link / channel / upload date for attribution). Real creators, but mostly small channels and
  auto-captions; transcripts only, so media is downloaded from YouTube under CC-BY. Best "real
  creator back-catalogue" source.
- **VideoUFO** (CC BY 4.0) - 1.09M CC-BY clips + captions, high-res, under 4 minutes. Good for
  clips / thumbnails, not full-length heatmaps.
- **Public-domain / CC BY media, downloadable now:** NASA Image & Video Library (140k+ files,
  public domain, API + multi-resolution download), Blender open movies (CC BY, 4K), Prelinger /
  Internet Archive (public-domain film), Pexels / Pixabay (free stock, no attribution), VOA /
  CDC / NPS b-roll (US-government public domain).
- **Open courseware as a persona-consistent "creator":** MIT OpenCourseWare, CS50, Khan Academy
  (all CC BY-**NC**-**SA**). Abundant long-form talking-head content on one channel, so a
  back-catalogue looks coherent; NC is fine for a non-commercial hackathon, but SA binds the
  generated derivatives. **Avoid CC BY-NC-ND (TED / TED-Ed): ND forbids derivatives.**
- **Paid, consented, B2B:** Oxylabs (4M videos, mp4 + subtitles + metadata), Troveo, Avail's
  Corpus, Protege Media (Calliope). Enterprise pricing.

**Loading plan:** download video (CC-BY/PD permits it) -> existing upload path -> real STT,
reviewers, heatmap, thumbnails; or import YouTube-Commons transcripts directly to skip STT.
Pick one CC-BY channel (or MIT OCW / CS50) as the demo creator so the back-catalogue is
coherent, add NASA / Blender for variety, and record `license` / `source` on the seeded project.

## Gathered seed corpus (done)

- Extracted the CC-BY catalogue for a shortlist from `PleIAs/YouTube-Commons` (slice
  `cctube_0.parquet`) into `fixtures/seed/youtube/`: `manifest.json`, `transcripts/`,
  `ATTRIBUTION.md` - **315 videos, 6.2 MB**.
- Verified with `yt-dlp --print "%(license)s"` that samples from each channel carry
  `Creative Commons Attribution license (reuse allowed)` in YouTube's own metadata.
- Shortlist: **Psych2Go** (animated self-help), **Lawrence Systems** (tech reviews),
  **The Humanist Report** (political commentary), **Trucker Josh VLOGS** (vlog),
  **Moxie Boosted** (gaming/Shorts), **LCDC** (French movie reviews, good for localization),
  **NutritionFacts.org** (health; CC BY-NC caveat).
- Caveats: corpus transcripts are plain text with **no timestamps** (heatmap still needs
  VTT/STT); the slice is partial; NutritionFacts states CC BY-NC on its site despite the
  YouTube label.

## Gather run (in progress)

`fixtures/seed/youtube/` now holds a local, gitignored CC-BY dataset plus a resumable
gatherer (`gather.py`). It samples each channel's whole catalogue, downloads
`info.json` + subtitles (VTT) + thumbnail (JPG) per video, and **keeps only videos whose
YouTube license is CC-BY** (deleting the rest, recording them in `excluded.txt`).

- Licence coverage measured: **Lawrence Systems** and **Moxie Boosted** are CC-BY
  catalogue-wide; **Psych2Go** is CC-BY on older uploads; **The Humanist Report** is CC-BY
  from ~2024. Sampling spans the whole catalogue so the CC-BY region is captured.
- Output per channel: `index.jsonl` (compact metadata: description, tags, stats, file names),
  `data/<id>.info.json|.vtt|.jpg`, and `video/<id>.mp4` for ~4 hand-picked CC-BY videos.
- Corpus `manifest.json` + `transcripts/` (315 videos) remain as a timestamp-free CC-BY seed.
- Large media is gitignored; nothing here is committed.

## Not done / next step

Let the gather finish/resume, then build the seed loader that maps `index.jsonl` + VTT into
the app's transcript/project shapes. Heatmap still needs the timestamped VTT (or STT on the
downloaded video). Write the OpenAPI contract before connector code.
