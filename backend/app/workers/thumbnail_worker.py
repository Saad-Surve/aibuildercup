"""Thumbnail worker: plan, generate, critique, and persist thumbnail concepts.

Pipeline for a `thumbnail` job:

1. **Plan** — one LLM call reads the transcript, the reviewer findings, the title, and the
   creator persona, and returns a distinct concept per placeholder: a short headline, a visual
   direction, the timestamp of the moment to use, and a rationale that cites the evidence.
2. **See the creator** — FFmpeg pulls one or more frames around each concept's timestamp from the
   source video and uploads them as references, so the image is built around the real person.
3. **Generate** — the image provider (Gemini image / "Nano Banana") renders the concept, using the
   frames as references; the result is uploaded under the project prefix.
4. **Critique** — a cheap multimodal pass looks at the finished image and scores phone-size
   legibility, promise-vs-content (anti-clickbait), and platform fit, with suggestions.

`mode: revise` skips planning and feeds the active image back to the model with the creator's
edit instruction, appending a new version.

Everything is best-effort per concept: one failed concept marks itself failed without failing the
batch, so a creator still gets the ones that worked.
"""

import asyncio
import json
import logging
import os
import tempfile
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings
from app.errors import NotFoundError
from app.providers.base import ImageGenProvider, LlmProvider, MediaPart
from app.providers.imagegen import ImageGenError
from app.schemas.jobs import JobStatus
from app.schemas.thumbnails import ThumbnailCritique, ThumbnailVersion
from app.schemas.transcripts import TranscriptSegment
from app.services.analysis_service import AnalysisService
from app.services.channel_content_service import ChannelContentService
from app.services.creator_import_service import CreatorImportService
from app.services.creator_library_service import CreatorLibraryService
from app.services.firestore_service import (
    FirestoreClient,
    asset_path,
    get_firestore_client,
    project_path,
)
from app.services.job_service import JobService
from app.services.project_service import ProjectService
from app.services.storage_service import StorageClient, get_storage_client
from app.services.thumbnail_service import ThumbnailService
from app.services.transcript_service import TranscriptService
from app.services.video_context import PERSONA_NOTE, build_review_context, persona_preferences
from app.services.video_tools import MediaToolkit, VideoToolError, format_timestamp
from app.workers.guard import serialize_job

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = frozenset(
    {JobStatus.succeeded.value, JobStatus.failed.value, JobStatus.cancelled.value}
)

THUMBNAIL_PLAN_PROMPT_VERSION = "thumbnail-plan-v2"
THUMBNAIL_CRITIQUE_PROMPT_VERSION = "thumbnail-critique-v1"

_SOURCE_URL_TTL_SECONDS = 3600
#: How far either side of the chosen moment to sample a reference frame.
_REFERENCE_OFFSETS_MS = (-800, 0, 800)

PLAN_SYSTEM = (
    "You are a senior YouTube/social packaging strategist inside a creator studio. You plan "
    "thumbnail concepts that are grounded in what the video actually contains.\n"
    "Rules:\n"
    "- A thumbnail makes one clear promise that the video keeps. Never invent a promise the "
    "transcript or findings do not support. This studio treats overpromising as a defect.\n"
    "- `headline` is the text burned into the image: at most 4 words, concrete, no hashtags, no "
    "emoji, no emoji-like symbols, no quotes around it. It must be readable on a phone.\n"
    "- `visualDirection` describes the composition to an image model: subject, expression, "
    "background, framing, and use of the headline. The presenter must be the person from the "
    "reference frames when references are available.\n"
    "- `timestampMs` is the single best moment in the video to take the presenter's face from. "
    "Prefer expressive, on-camera moments; use the findings and transcript to choose. When "
    "`interestPeaks` are supplied, prefer a moment inside or next to a peak: that is where the "
    "video is predicted to hold attention best.\n"
    "- When `strongestHook` or `strengthsToKeep` are supplied, build at least one concept on that "
    "real line or moment. `reviewFindings` are problems reviewers found; do not make a promise "
    "the findings say the video fails to keep.\n"
    "- `creatorPersona` holds the creator's preferences, not facts about the video.\n"
    "- `rationale` is one or two sentences to the CREATOR explaining why this works, citing the "
    "specific evidence (a finding, a quote, a retention moment) — not generic praise.\n"
    "- Every concept must take a distinct angle. Return exactly the requested number."
)

PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "concepts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "headline": {"type": "string"},
                    "visualDirection": {"type": "string"},
                    "timestampMs": {"type": "integer"},
                    "emotion": {"type": "string"},
                    "rationale": {"type": "string"},
                    "altText": {"type": "string"},
                },
                "required": ["headline", "visualDirection", "timestampMs", "rationale"],
            },
        }
    },
    "required": ["concepts"],
}

CRITIQUE_SYSTEM = (
    "You judge a finished thumbnail the way a platform's audience and its trust-and-safety "
    "team would. You are shown the image. Score each axis 1-5 and be specific, not kind.\n"
    "- `legibility`: can the burned-in text be read at phone size, at a glance? Consider size, "
    "contrast, clutter, and whether text collides with the subject.\n"
    "- `promise`: does the thumbnail promise exactly what this video delivers? 5 = honest and "
    "compelling, 1 = clickbait the video cannot back up.\n"
    "- `platformFit`: does it follow the target platform's visual conventions and avoid obvious "
    "policy problems (misleading text, shocking imagery, collage spam)?\n"
    "- `summary`: one sentence the creator can act on.\n"
    "- `suggestions`: up to 3 short, concrete edits (each a good instruction for an image edit)."
)

CRITIQUE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "legibility": {"type": "integer"},
        "promise": {"type": "integer"},
        "platformFit": {"type": "integer"},
        "summary": {"type": "string"},
        "suggestions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["legibility", "promise", "platformFit", "summary"],
}


# --------------------------------------------------------------------- public entry


@serialize_job
async def run_thumbnail_generation(
    *,
    owner_uid: str,
    project_id: str,
    job_id: str,
    firestore: FirestoreClient,
    jobs: JobService,
    projects: ProjectService,
    thumbnails: ThumbnailService,
    transcripts: TranscriptService,
    analysis: AnalysisService,
    content: ChannelContentService,
    storage: StorageClient,
    llm: LlmProvider,
    images: ImageGenProvider,
    settings: Settings,
) -> list[str] | None:
    try:
        job = await asyncio.to_thread(
            jobs.load_for_worker, owner_uid=owner_uid, project_id=project_id, job_id=job_id
        )
    except NotFoundError:
        logger.warning("thumbnail job %s not found; skipping", job_id)
        return None
    if job.get("status") in TERMINAL_STATUSES:
        logger.info("thumbnail job %s already %s; skipping", job_id, job.get("status"))
        return (job.get("input") or {}).get("thumbnailIds")

    payload = job.get("input") or {}
    thumbnail_ids: list[str] = list(payload.get("thumbnailIds") or [])
    if not thumbnail_ids:
        await asyncio.to_thread(
            jobs.mark_failed,
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            message="Thumbnail job is missing its concept ids.",
            code="THUMBNAIL_FAILED",
        )
        return None

    try:
        if payload.get("mode") == "revise":
            await _revise(
                owner_uid=owner_uid,
                project_id=project_id,
                job_id=job_id,
                payload=payload,
                jobs=jobs,
                projects=projects,
                thumbnails=thumbnails,
                storage=storage,
                llm=llm,
                images=images,
                settings=settings,
            )
        else:
            await _generate_batch(
                owner_uid=owner_uid,
                project_id=project_id,
                job_id=job_id,
                payload=payload,
                thumbnail_ids=thumbnail_ids,
                jobs=jobs,
                projects=projects,
                thumbnails=thumbnails,
                transcripts=transcripts,
                content=content,
                firestore=firestore,
                storage=storage,
                llm=llm,
                images=images,
                settings=settings,
            )
    except Exception as exc:  # noqa: BLE001 - mark the batch failed, keep what landed
        logger.exception("thumbnail job %s failed", job_id)
        message = _failure_message(exc)
        for thumbnail_id in thumbnail_ids:
            if payload.get("mode") != "revise":
                _safe_mark_failed(
                    thumbnails,
                    owner_uid=owner_uid,
                    project_id=project_id,
                    thumbnail_id=thumbnail_id,
                    message=message,
                )
        await asyncio.to_thread(
            jobs.mark_failed,
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            message=message,
            code="THUMBNAIL_FAILED",
        )
        return None
    return thumbnail_ids


# --------------------------------------------------------------------- batch generate


async def _generate_batch(
    *,
    owner_uid: str,
    project_id: str,
    job_id: str,
    payload: dict[str, Any],
    thumbnail_ids: list[str],
    jobs: JobService,
    projects: ProjectService,
    thumbnails: ThumbnailService,
    transcripts: TranscriptService,
    content: ChannelContentService,
    firestore: FirestoreClient,
    storage: StorageClient,
    llm: LlmProvider,
    images: ImageGenProvider,
    settings: Settings,
) -> None:
    project = await asyncio.to_thread(projects.get, owner_uid=owner_uid, project_id=project_id)
    duration_ms, transcript_view, segments = _transcript_view(
        transcripts=transcripts, owner_uid=owner_uid, project_id=project_id
    )
    review = _review_view(
        firestore=firestore, owner_uid=owner_uid, project_id=project_id, segments=segments
    )
    persona = persona_preferences(firestore, storage, owner_uid, max_chars=4000)
    # The creator's own past thumbnails, as image-model style references (best-effort).
    creator_references: list[MediaPart] = []
    try:
        creator_references = await asyncio.to_thread(
            content.creator_thumbnail_references,
            owner_uid,
            limit=settings.thumbnail_creator_references,
            query=f"{project.name} {payload.get('brief') or project.thumbnailConcept}",
        )
    except Exception:  # noqa: BLE001 - style references are a bonus, never a blocker
        logger.warning("thumbnail: creator thumbnail references unavailable", exc_info=True)

    regenerate = payload.get("mode") == "regenerate"
    if regenerate:
        await asyncio.to_thread(
            jobs.mark_running,
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            step="regenerating",
            message="Re-rendering selected concepts",
        )
        # Reuse each concept's existing idea; "redo" is a fresh take, not a new plan.
        plan = []
        version_numbers = []
        concept_aspects = []
        for thumbnail_id in thumbnail_ids:
            stored = (
                await asyncio.to_thread(
                    thumbnails.load,
                    owner_uid=owner_uid,
                    project_id=project_id,
                    thumbnail_id=thumbnail_id,
                )
                or {}
            )
            plan.append(
                {
                    "headline": stored.get("headline", ""),
                    "rationale": stored.get("rationale", ""),
                    "visualDirection": "",
                    "emotion": "",
                    "timestampMs": stored.get("sourceTimestampMs"),
                }
            )
            version_numbers.append(len(stored.get("versions") or []) + 1)
            concept_aspects.append(str(stored.get("aspect") or settings.imagegen_default_aspect))
    else:
        await asyncio.to_thread(
            jobs.mark_running,
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            step="planning",
            message="Planning thumbnail concepts",
        )
        plan = await _plan(
            llm=llm,
            settings=settings,
            count=len(thumbnail_ids),
            project=project,
            persona=persona,
            brief=str(payload.get("brief") or ""),
            duration_ms=duration_ms,
            transcript_view=transcript_view,
            review=review,
        )
        version_numbers = [1] * len(thumbnail_ids)
        concept_aspects = [str(payload.get("aspect") or settings.imagegen_default_aspect)] * len(
            thumbnail_ids
        )

    image_size = str(payload.get("imageSize") or settings.imagegen_default_size)
    use_real_frames = bool(payload.get("useRealFrames", True))
    model = settings.model_image_pro if payload.get("useProModel") else settings.model_image

    toolkit = None
    tmp_handle: tempfile.TemporaryDirectory[str] | None = None
    if use_real_frames and duration_ms > 0:
        # Stage the source locally: a fragmented MP4 served over a signed URL makes
        # FFmpeg's seek unreliable (some frames fail to extract), which is exactly the
        # reference-frame flakiness that weakens a concept. The handle cleans itself up
        # when this function returns.
        tmp_handle = tempfile.TemporaryDirectory(prefix="thumbnail-")
        toolkit = _open_source(
            firestore=firestore,
            storage=storage,
            settings=settings,
            owner_uid=owner_uid,
            project_id=project_id,
            duration_ms=duration_ms,
            tmpdir=tmp_handle.name,
        )

    total = max(1, len(thumbnail_ids))
    for index, thumbnail_id in enumerate(thumbnail_ids):
        concept = plan[index] if index < len(plan) else _fallback_plan(project.name)
        headline = str(concept.get("headline") or "").strip()[:60]
        rationale = str(concept.get("rationale") or "").strip()
        direction = str(concept.get("visualDirection") or "").strip()
        emotion = str(concept.get("emotion") or "").strip()
        timestamp_ms = _clamp_ms(concept.get("timestampMs"), duration_ms)
        concept_aspect = (
            concept_aspects[index]
            if index < len(concept_aspects)
            else settings.imagegen_default_aspect
        )
        version_number = version_numbers[index] if index < len(version_numbers) else 1

        await asyncio.to_thread(
            thumbnails.mark_generating,
            owner_uid=owner_uid,
            project_id=project_id,
            thumbnail_id=thumbnail_id,
            headline=headline,
        )
        await asyncio.to_thread(
            thumbnails.save_plan,
            owner_uid=owner_uid,
            project_id=project_id,
            thumbnail_id=thumbnail_id,
            headline=headline,
            rationale=rationale,
            source_timestamp_ms=timestamp_ms,
        )
        await asyncio.to_thread(
            jobs.update_progress,
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            percent=int(8 + (index / total) * 80),
            step="generating",
            message=f"Rendering concept {index + 1} of {total}",
        )

        try:
            references, reference_timestamps = await _reference_frames(
                toolkit=toolkit,
                thumbnails=thumbnails,
                storage=storage,
                owner_uid=owner_uid,
                project_id=project_id,
                thumbnail_id=thumbnail_id,
                timestamp_ms=timestamp_ms,
                settings=settings,
            )
            frame_references = references
            references = [*frame_references, *creator_references]
            prompt = _build_generate_prompt(
                headline=headline,
                direction=direction,
                emotion=emotion,
                platform=_platform(project.targetPlatforms),
                aspect=concept_aspect,
                has_frames=bool(frame_references),
                has_creator_references=bool(creator_references),
            )
            generated = await images.generate(
                model=model,
                prompt=prompt,
                count=1,
                aspect_ratio=concept_aspect,
                image_size=image_size,
                reference_images=references,
            )
            image = generated[0]
            critique = await _critique(
                llm=llm,
                settings=settings,
                image=image.data,
                mime_type=image.mime_type,
                headline=headline,
                video_title=project.name,
                platform=_platform(project.targetPlatforms),
                hook=_hook_text(transcript_view),
            )
            version = _store_image(
                thumbnails=thumbnails,
                storage=storage,
                owner_uid=owner_uid,
                project_id=project_id,
                thumbnail_id=thumbnail_id,
                version_number=version_number,
                data=image.data,
                mime_type=image.mime_type,
                instruction=prompt,
                headline=headline,
                rationale=rationale,
                reference_timestamps=reference_timestamps,
                critique=critique,
                model=model,
                price=settings.imagegen_price_per_image_usd,
            )
            await asyncio.to_thread(
                thumbnails.add_version,
                owner_uid=owner_uid,
                project_id=project_id,
                thumbnail_id=thumbnail_id,
                version=version,
            )
        except Exception as exc:  # noqa: BLE001 - one concept must not sink the batch
            logger.warning("thumbnail %s failed: %s", thumbnail_id, exc)
            _safe_mark_failed(
                thumbnails,
                owner_uid=owner_uid,
                project_id=project_id,
                thumbnail_id=thumbnail_id,
                message=str(exc)[:300] or "Generation failed.",
            )

    await asyncio.to_thread(
        jobs.update_progress,
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        percent=95,
        step="finishing",
        message="Finalising thumbnails",
    )
    await asyncio.to_thread(
        jobs.mark_succeeded,
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        output={"artifactIds": [], "storagePaths": [], "thumbnailIds": thumbnail_ids},
        message="Thumbnail concepts ready",
    )


# --------------------------------------------------------------------- revise


async def _revise(
    *,
    owner_uid: str,
    project_id: str,
    job_id: str,
    payload: dict[str, Any],
    jobs: JobService,
    projects: ProjectService,
    thumbnails: ThumbnailService,
    storage: StorageClient,
    llm: LlmProvider,
    images: ImageGenProvider,
    settings: Settings,
) -> None:
    thumbnail_id = str((payload.get("thumbnailIds") or [""])[0])
    instruction = str(payload.get("instruction") or "").strip()
    concept = await asyncio.to_thread(
        thumbnails.load, owner_uid=owner_uid, project_id=project_id, thumbnail_id=thumbnail_id
    )
    if concept is None:
        raise NotFoundError("Thumbnail concept not found", details={"thumbnailId": thumbnail_id})
    active = _active_version(concept)
    storage_path = active.get("storagePath") if active else None
    if active is None or not storage_path:
        raise VideoToolError("This concept has no image to edit.")

    project = await asyncio.to_thread(projects.get, owner_uid=owner_uid, project_id=project_id)
    await asyncio.to_thread(
        jobs.mark_running,
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        step="editing",
        message="Applying your edit",
    )
    base_bytes = await asyncio.to_thread(storage.download_bytes, str(storage_path))
    mime_type = str(active.get("mimeType") or "image/png")
    generated = await images.generate(
        model=settings.model_image,
        prompt=_build_edit_prompt(instruction=instruction),
        count=1,
        aspect_ratio=str(concept.get("aspect") or settings.imagegen_default_aspect),
        image_size=settings.imagegen_default_size,
        base_image=MediaPart(mime_type=mime_type, data=base_bytes, label=""),
    )
    image = generated[0]
    previous_headline = str(concept.get("headline") or "")
    critique = await _critique(
        llm=llm,
        settings=settings,
        image=image.data,
        mime_type=image.mime_type,
        headline=previous_headline,
        video_title=project.name,
        platform=_platform(project.targetPlatforms),
        hook="",
    )
    next_number = len(concept.get("versions") or []) + 1
    version = _store_image(
        thumbnails=thumbnails,
        storage=storage,
        owner_uid=owner_uid,
        project_id=project_id,
        thumbnail_id=thumbnail_id,
        version_number=next_number,
        data=image.data,
        mime_type=image.mime_type,
        instruction=instruction,
        headline=previous_headline,
        rationale=str(concept.get("rationale") or ""),
        reference_timestamps=[int(item) for item in (concept.get("referenceTimestampsMs") or [])],
        critique=critique,
        model=settings.model_image,
        price=settings.imagegen_price_per_image_usd,
    )
    await asyncio.to_thread(
        thumbnails.add_version,
        owner_uid=owner_uid,
        project_id=project_id,
        thumbnail_id=thumbnail_id,
        version=version,
    )
    await asyncio.to_thread(
        jobs.mark_succeeded,
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        output={"artifactIds": [], "storagePaths": [version.storagePath or ""]},
        message="Edit applied",
    )


# --------------------------------------------------------------------- planning


async def _plan(
    *,
    llm: LlmProvider,
    settings: Settings,
    count: int,
    project: Any,
    persona: str,
    brief: str,
    duration_ms: int,
    transcript_view: list[dict[str, Any]],
    review: dict[str, Any],
) -> list[dict[str, Any]]:
    context: dict[str, Any] = {
        "task": f"Plan {count} distinct thumbnail concepts.",
        "video": {
            "title": project.name,
            "description": project.description,
            "existingThumbnailIdea": project.thumbnailConcept,
            "platforms": project.targetPlatforms or ["youtube"],
            "language": project.primaryLanguage,
            "durationMs": duration_ms,
        },
        "creatorBrief": brief,
        "transcript": transcript_view,
        # reviewFindings, strengthsToKeep, interestPeaks, strongestHook (each only if present).
        **review,
    }
    if persona:
        context["creatorPersona"] = {"note": PERSONA_NOTE, "preferences": persona}
    try:
        completion = await llm.complete_json(
            model=settings.model_writer,
            prompt_version=THUMBNAIL_PLAN_PROMPT_VERSION,
            system=PLAN_SYSTEM,
            user=json.dumps(context, ensure_ascii=False, default=str),
            schema=PLAN_SCHEMA,
        )
        concepts = [
            item
            for item in (completion.data.get("concepts") or [])
            if str(item.get("headline", "")).strip()
        ]
    except Exception:  # noqa: BLE001 - fall back to a deterministic plan
        logger.exception("thumbnail planning failed; using a deterministic plan")
        concepts = []
    while len(concepts) < count:
        concepts.append(_fallback_plan(project.name))
    return concepts[:count]


def _fallback_plan(title: str) -> dict[str, Any]:
    return {
        "headline": (title or "Watch this").strip()[:40],
        "visualDirection": (
            "The presenter, reacting to the video's main point, high-contrast clean "
            "background, headline large on one side, subject on the other."
        ),
        "timestampMs": 0,
        "emotion": "confident",
        "rationale": "A clear, honest option built from the video's own title.",
    }


# --------------------------------------------------------------------- frames


def _open_source(
    *,
    firestore: FirestoreClient,
    storage: StorageClient,
    settings: Settings,
    owner_uid: str,
    project_id: str,
    duration_ms: int,
    tmpdir: str,
) -> MediaToolkit:
    project = firestore.get_document(project_path(owner_uid, project_id)) or {}
    asset_id = project.get("sourceAssetId")
    if not asset_id:
        raise VideoToolError("This project has no source video to take frames from.")
    asset = firestore.get_document(asset_path(owner_uid, project_id, str(asset_id)))
    if asset is None or asset.get("ownerUid") != owner_uid:
        raise VideoToolError("The source video is missing.")
    storage_path = str(asset.get("storagePath") or "")
    if not storage_path or not storage.object_exists(storage_path):
        raise VideoToolError("The source video is missing from storage.")

    # Prefer a local copy so frame seeking is reliable; fall back to streaming the
    # signed URL when the object is too large to stage (see the caption worker for the
    # same reasoning).
    source = None
    try:
        size = storage.object_size(storage_path)
    except Exception:  # noqa: BLE001
        size = None
    if size is not None and 0 < size <= settings.caption_max_source_download_bytes:
        extension = os.path.splitext(storage_path)[1] or ".mp4"
        local_path = os.path.join(tmpdir, f"source{extension}")
        try:
            storage.download_to_filename(storage_path, local_path)
            source = local_path
        except Exception:  # noqa: BLE001 - fall back to streaming
            logger.warning("thumbnail: staging the source locally failed", exc_info=True)
    if source is None:
        source = storage.signed_download_url(storage_path, expires_seconds=_SOURCE_URL_TTL_SECONDS)
    return MediaToolkit(
        source=source,
        duration_ms=duration_ms,
        ffmpeg_path=settings.ffmpeg_path,
        frame_max_width=settings.thumbnail_frame_max_width,
        max_requests=settings.thumbnail_reference_frames * 4,
    )


async def _reference_frames(
    *,
    toolkit: MediaToolkit | None,
    thumbnails: ThumbnailService,
    storage: StorageClient,
    owner_uid: str,
    project_id: str,
    thumbnail_id: str,
    timestamp_ms: int | None,
    settings: Settings,
) -> tuple[list[MediaPart], list[int]]:
    if toolkit is None or timestamp_ms is None:
        return [], []
    references: list[MediaPart] = []
    timestamps: list[int] = []
    limit = max(1, settings.thumbnail_reference_frames)
    for offset in _REFERENCE_OFFSETS_MS[:limit]:
        at = max(0, min(toolkit.duration_ms, timestamp_ms + offset))
        try:
            part = await toolkit.extract_frame(at)
        except Exception:  # noqa: BLE001 - a missing frame is not fatal
            logger.warning("thumbnail: frame extraction failed at %d ms", at)
            continue
        part = MediaPart(
            mime_type=part.mime_type,
            data=part.data,
            label=f"Reference frame of the presenter at {format_timestamp(at)}",
        )
        object_path = thumbnails.reference_path(
            owner_uid=owner_uid,
            project_id=project_id,
            thumbnail_id=thumbnail_id,
            timestamp_ms=at,
        )
        try:
            await asyncio.to_thread(
                storage.upload_bytes, object_path, part.data, content_type=part.mime_type
            )
        except Exception:  # noqa: BLE001 - persistence of the reference is best-effort
            logger.warning("thumbnail: could not persist a reference frame")
        references.append(part)
        timestamps.append(at)
    return references, timestamps


# --------------------------------------------------------------------- critique


async def _critique(
    *,
    llm: LlmProvider,
    settings: Settings,
    image: bytes,
    mime_type: str,
    headline: str,
    video_title: str,
    platform: str,
    hook: str,
) -> ThumbnailCritique | None:
    context = {
        "videoTitle": video_title,
        "platform": platform,
        "headlineShownOnImage": headline,
        "videoHook": hook,
    }
    try:
        completion = await llm.complete_json(
            model=settings.model_reviewer,
            prompt_version=THUMBNAIL_CRITIQUE_PROMPT_VERSION,
            system=CRITIQUE_SYSTEM,
            user=json.dumps(context, ensure_ascii=False),
            schema=CRITIQUE_SCHEMA,
            media=[MediaPart(mime_type=mime_type, data=image, label="The generated thumbnail")],
        )
        return _critique_from(completion.data)
    except Exception:  # noqa: BLE001 - a critique is a bonus, never a failure
        logger.warning("thumbnail critique failed", exc_info=True)
        return None


def _critique_from(data: dict[str, Any]) -> ThumbnailCritique:
    def score(value: Any) -> int:
        try:
            return max(0, min(5, int(value)))
        except (TypeError, ValueError):
            return 0

    return ThumbnailCritique(
        legibility=score(data.get("legibility")),
        promise=score(data.get("promise")),
        platformFit=score(data.get("platformFit")),
        summary=str(data.get("summary") or "").strip(),
        suggestions=[
            str(item).strip() for item in (data.get("suggestions") or []) if str(item).strip()
        ][:3],
    )


# --------------------------------------------------------------------- prompts


def _platform(platforms: list[str]) -> str:
    return (platforms or ["youtube"])[0]


#: Appended to every image prompt. The model defaults to a glossy, obviously-AI look;
#: these instructions push it toward a real photograph and away from the usual tells.
ANTI_SLOP = (
    "Make it look like a real photograph taken on a real camera, not an AI image. "
    "Natural, believable lighting and skin texture; keep the person's real face and features "
    "exactly as in the reference, with no beautification or face-swap look. Avoid: waxy or "
    "airbrushed skin, plastic sheen, over-saturated HDR, heavy vignettes, generic stock-photo "
    "smiles, floating or duplicated objects, extra fingers or warped hands, warped or mirrored "
    "faces, garbled or repeated letters, random symbols, fake UI elements, watermarks, "
    "signatures, and lens flares. Keep the composition intentional and slightly imperfect, like "
    "a creator's real thumbnail rather than a rendered illustration."
)


def _build_generate_prompt(
    *,
    headline: str,
    direction: str,
    emotion: str,
    platform: str,
    aspect: str,
    has_frames: bool,
    has_creator_references: bool,
) -> str:
    lines = [
        f"Create a scroll-stopping {platform} thumbnail, {aspect} aspect ratio.",
        f'The EXACT text to render on the image, large and high-contrast: "{headline}".',
    ]
    if direction:
        lines.append(f"Composition: {direction}")
    if emotion:
        lines.append(f"Presenter's expression/emotion: {emotion}.")
    if has_frames:
        lines.append(
            "Use the person from the reference frames as the presenter: preserve their face "
            "and identity. Do not replace them with a different person."
        )
    if has_creator_references:
        lines.append(
            "Some reference images are past thumbnails from this creator's channel. Match their "
            "visual style — colour, typography, and composition — but do not copy them or "
            "reproduce their text."
        )
    lines.extend(
        [
            "Keep the headline fully readable at phone size, with clear margins and strong "
            "contrast. Do not add emoji, watermarks, logos, UI chrome, or extra words.",
            ANTI_SLOP,
        ]
    )
    return " ".join(lines)


def _build_edit_prompt(*, instruction: str) -> str:
    return (
        "Edit the supplied thumbnail. Apply exactly this change: "
        f"{instruction}. Keep the same person, the same overall concept, and the on-image "
        f"text legible and correctly spelled. Return the full edited image. {ANTI_SLOP}"
    )


# --------------------------------------------------------------------- view builders


def _transcript_view(
    *, transcripts: TranscriptService, owner_uid: str, project_id: str
) -> tuple[int, list[dict[str, Any]], list[TranscriptSegment]]:
    try:
        transcript = transcripts.get(owner_uid=owner_uid, project_id=project_id)
    except Exception:  # noqa: BLE001 - a project without a transcript can still be planned
        logger.info("thumbnail: no transcript available")
        return 0, [], []
    segments = transcript.segments
    # Bound the prompt: the opening (the hook) plus an evenly spaced sample.
    head = segments[:30]
    stride = max(1, len(segments) // 30)
    sampled = segments[::stride]
    seen: set[str] = set()
    view: list[dict[str, Any]] = []
    for segment in [*head, *sampled]:
        if segment.segmentId in seen:
            continue
        seen.add(segment.segmentId)
        view.append(
            {
                "startMs": segment.startMs,
                "endMs": segment.endMs,
                "speaker": segment.speaker,
                "text": segment.text,
            }
        )
    return transcript.durationMs, view, segments


def _review_view(
    *,
    firestore: FirestoreClient,
    owner_uid: str,
    project_id: str,
    segments: list[TranscriptSegment],
) -> dict[str, Any]:
    """Findings, strengths, interest peaks and the strongest hook from the latest review."""
    return build_review_context(
        firestore, owner_uid, project_id, segments=segments, max_findings=12
    )


def _hook_text(transcript_view: list[dict[str, Any]]) -> str:
    return " ".join(str(item.get("text") or "") for item in transcript_view[:4]).strip()[:400]


# --------------------------------------------------------------------- helpers


def _store_image(
    *,
    thumbnails: ThumbnailService,
    storage: StorageClient,
    owner_uid: str,
    project_id: str,
    thumbnail_id: str,
    version_number: int,
    data: bytes,
    mime_type: str,
    instruction: str,
    headline: str,
    rationale: str,
    reference_timestamps: list[int],
    critique: ThumbnailCritique | None,
    model: str,
    price: float,
) -> ThumbnailVersion:
    extension = "png" if "png" in mime_type else "jpg"
    object_path = thumbnails.target_paths(
        owner_uid=owner_uid,
        project_id=project_id,
        thumbnail_id=thumbnail_id,
        version=version_number,
        extension=extension,
    )
    storage.upload_bytes(object_path, data, content_type=mime_type)
    return ThumbnailVersion(
        versionId=uuid4().hex[:12],
        version=version_number,
        storagePath=object_path,
        mimeType=mime_type,
        sizeBytes=len(data),
        instruction=instruction,
        headline=headline,
        rationale=rationale,
        referenceTimestampsMs=reference_timestamps,
        critique=critique,
        model=model,
        costUsd=price,
        createdAt=datetime.now(UTC),
    )


def _active_version(concept: dict[str, Any]) -> dict[str, Any] | None:
    active_id = concept.get("activeVersionId")
    for version in concept.get("versions") or []:
        if version.get("versionId") == active_id:
            return version
    return None


def _clamp_ms(value: Any, duration_ms: int) -> int | None:
    if value is None:
        return None
    try:
        at = int(value)
    except (TypeError, ValueError):
        return None
    if at < 0:
        return 0
    if duration_ms > 0:
        return min(at, duration_ms)
    return at


def _safe_mark_failed(
    thumbnails: ThumbnailService,
    *,
    owner_uid: str,
    project_id: str,
    thumbnail_id: str,
    message: str,
) -> None:
    try:
        thumbnails.mark_failed(
            owner_uid=owner_uid,
            project_id=project_id,
            thumbnail_id=thumbnail_id,
            code="THUMBNAIL_FAILED",
            message=message,
        )
    except Exception:  # noqa: BLE001
        logger.warning("thumbnail: could not mark %s failed", thumbnail_id)


def _failure_message(exc: BaseException) -> str:
    if isinstance(exc, VideoToolError):
        detail = str(exc).strip()
        if detail:
            return f"Thumbnail generation failed: {detail}"
    if isinstance(exc, ImageGenError):
        return "Thumbnail generation failed: the image model was unavailable."
    return "Thumbnail generation failed. Try again."


# --------------------------------------------------------------------- wiring


def build_worker_services(
    *,
    firestore: FirestoreClient,
    jobs: JobService,
    projects: ProjectService,
    thumbnails: ThumbnailService,
    transcripts: TranscriptService,
    analysis: AnalysisService,
    content: ChannelContentService,
    storage: StorageClient,
    llm: LlmProvider,
    images: ImageGenProvider,
    settings: Settings,
) -> dict[str, Any]:
    return {
        "firestore": firestore,
        "jobs": jobs,
        "projects": projects,
        "thumbnails": thumbnails,
        "transcripts": transcripts,
        "analysis": analysis,
        "content": content,
        "storage": storage,
        "llm": llm,
        "images": images,
        "settings": settings,
    }


def live_worker_dependencies() -> dict[str, Any]:
    from app.providers import get_providers
    from app.services.connection_service import ConnectionService
    from app.services.token_cipher import build_token_cipher

    firestore = get_firestore_client()
    settings = get_settings()
    storage = get_storage_client()
    jobs = JobService(firestore)
    projects = ProjectService(firestore, storage=storage)
    transcripts = TranscriptService(firestore, storage=storage)
    connections = ConnectionService(
        firestore, cipher=build_token_cipher(settings), settings=settings
    )
    providers = get_providers()
    imports = CreatorImportService(firestore, storage=storage)
    library = CreatorLibraryService(
        firestore,
        storage=storage,
        imports=imports,
        connections=connections,
        embeddings=providers.embeddings,
        settings=settings,
    )
    return build_worker_services(
        firestore=firestore,
        jobs=jobs,
        projects=projects,
        thumbnails=ThumbnailService(
            firestore,
            projects=projects,
            jobs=jobs,
            storage=storage,
            url_ttl_seconds=settings.upload_url_ttl_seconds,
            price_per_image_usd=settings.imagegen_price_per_image_usd,
            max_project_cost_usd=settings.max_project_cost_usd,
        ),
        transcripts=transcripts,
        analysis=AnalysisService(firestore, jobs=jobs, settings=settings),
        content=ChannelContentService(
            firestore, connections=connections, imports=imports, library=library, settings=settings
        ),
        storage=storage,
        llm=providers.llm,
        images=providers.images,
        settings=settings,
    )


def thumbnail_after_response(
    background_tasks: Any,
    *,
    owner_uid: str,
    project_id: str,
    job_id: str,
) -> None:
    background_tasks.add_task(
        run_thumbnail_generation,
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        **live_worker_dependencies(),
    )
