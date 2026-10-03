# Model check: Nano Banana vs Imagen, Omni vs Veo

## What I did

- Cancelled the Chirp -> Gemini 3.5 Transcribe migration per the user's decision; no code was
  changed and the 2026-10-03-1010 note stands as the record.
- Inspected how images/videos are actually wired today: `config.py` (`model_image`,
  `model_video`), `providers/base.py` (`ImageGenProvider`/`VideoGenProvider` protocols),
  `providers/` contents, `schemas/jobs.py`/`assets.py` (artifact types), and the
  thumbnail/intro-outro requirements in `backend-plan.md`/`api-design.md`.
- Researched with Firecrawl: Gemini Developer pricing, Agent Platform generative-AI pricing,
  the Nano Banana 2 and Omni Flash Agent Platform model cards, and the Veo 3.1 model card.

## Key finding that changes the question

**There is nothing to migrate.** `imagegen.py` and `videogen.py` do not exist; the only
in-tree references are the two config strings (`model_image="imagen-4.0-generate-001"`,
`model_video="veo-3.1-fast"`), unused Protocol definitions, and artifact/job type enums.
"Thumbnail" code in `analysis_coordinator.py`/`reviewer_base.py` is reviewer *judgment*
context (`thumbnailConcept`), not image generation. So this is a green-field model choice for
providers we have not built yet, not a port.

## Comparison (Agent Platform / Vertex, our path)

### Images: Imagen 4 vs Nano Banana

| | Imagen 4 / Fast / Ultra | Nano Banana 2 (`gemini-3.1-flash-image`) | Nano Banana 2 Lite | Nano Banana Pro (`gemini-3-pro-image`) |
|---|---|---|---|---|
| Price / image | $0.04 / $0.02 / $0.06 | ~$0.067 (1K), $0.045 (512), $0.101 (2K), $0.151 (4K) | ~$0.034 (1K) | $0.134 (1K/2K), $0.24 (4K) |
| Editing / multi-turn | No | Yes | Yes | Yes |
| Ref images for consistency | No | Up to 14 | Up to 14 | Up to 14 |
| Image from video input | No | Yes | Yes | Yes |
| Text-in-image | Weak | Strong | Strong | Strongest |
| Resolutions | 1K | 512 / 1K / 2K / 4K | 1K | 1K / 2K / 4K |
| Launch / region | GA | GA, `global`/`us`/`eu` | GA, broad | GA-ish |
| Batch/EU | — | Batch + Flex PayGo | Batch | Batch/Flex |

Nano Banana reads a video frame and generates directly (ideal for thumbnails), edits
conversationally, and keeps a character/brand consistent across images. It costs ~1.7-3x
Imagen 4 per image, which is cents at demo scale. It also runs through the same
`genai.Client(vertexai=True, location=global)` that `llm.py` already caches, unlike Imagen's
separate `:predict` path.

### Video: Veo 3.1 Fast vs Gemini Omni Flash

| | Veo 3.1 Fast (`veo-3.1-fast`) | Gemini Omni Flash (`gemini-omni-flash-preview`) |
|---|---|---|
| Price (720p, w/ audio) | $0.10 / sec | ~$0.101 / sec (5,792 tok/s x $17.50/1M) |
| 1080p | $0.12 / sec | $0.152 / sec |
| Max clip | 8s, up to 4 videos/prompt | 10s, up to 3 videos/prompt |
| Resolution | 720p / 1080p / 4K | 720p only |
| Text-to-video | Yes | Yes |
| Image-to-video | Yes | **No** |
| First/last frame, refs, extend | Yes | **No** |
| Video editing (conversational) | No | **Yes** |
| Sound generation | Yes | Yes (speech/music/SFX) |
| Launch / region | GA, `us-central1` | **Preview** (retires 2027-06-30), `global` |

Price is at parity with our current default for 720p; Omni is a *different* model (editing and
multi-turn), not a cheaper Veo. It loses image-to-video, reference images, first/last-frame
and extend, caps at 720p/10s, and is preview-only. Its global endpoint does match the existing
`vertex_location="global"`, while Veo must be called in `us-central1`.

## Recommendation

- **Images: make Nano Banana 2 (`gemini-3.1-flash-image`) the default** when `imagegen` is
  built. It is strictly more capable for thumbnails (frame input, editing, text, refs) and
  unifies the SDK/path. Keep Nano Banana 2 Lite for bulk drafts and Pro for hero shots; drop
  Imagen to a fallback only if the cheapest possible plain generation is ever wanted.
- **Video: keep Veo 3.1 Fast** as the generation default for intros/outros (image-to-video,
  refs, 1080p, GA, longer clip budget). Add Omni later as a *conversational edit* companion,
  not a Veo replacement. Re-check Omni when it exits preview and gains image-to-video.
- **Effort: effectively zero** because neither provider exists. Changing the model is one
  config value plus writing the green-field provider; the only real work is implementing
  `imagegen.py`/`videogen.py` and their flows, which is required regardless of model choice.
- Keep both behind the existing cost cap (`max_project_cost_usd`); Nano Banana Pro and any Veo
  tier are the expensive calls.

## Verification

- Research-only. No code, dependency, infra, contract, or schema change; no commit.
- No paid generation calls run. No tests added (repo policy).

## Not done / next step

- No providers implemented. Next step if pursued: implement `imagegen.py` on
  `gemini-3.1-flash-image` via the existing Vertex `genai` client, and keep `videogen.py` on
  `veo-3.1-fast-generate-001` in `us-central1`. Confirm with one bounded probe each before
  trusting published pricing (Cloud Veo is tabulated as "$ / 1 count"; the Developer API labels
  the same figures "per second" — treat as per second but verify).

## Sources

- https://ai.google.dev/gemini-api/docs/pricing
- https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing
- https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-1-flash-image
- https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/omni-flash-preview
- https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/veo/3-1-generate
- https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/locations
