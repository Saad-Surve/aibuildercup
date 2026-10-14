"""Render a new source revision, with exact video mapping and 40 ms audio handles."""

import asyncio
import logging
import os
import tempfile
from datetime import UTC, datetime
from typing import Any
from weakref import WeakValueDictionary

from app.config import get_settings
from app.errors import ConflictError
from app.schemas.rough_cut import KeptSegment, PlannedInsert, RoughCutPlan
from app.services.asset_service import AssetService
from app.services.firestore_service import (
    asset_path,
    get_firestore_client,
    job_path,
    project_object_prefix,
    project_path,
    transcript_path,
)
from app.services.job_service import JobService
from app.services.project_service import ProjectService
from app.services.rough_cut import RoughCutService, remap_segments
from app.services.source_media import stage_source
from app.services.storage_service import get_storage_client
from app.services.transcript_service import TranscriptService
from app.services.video_tools import probe_has_audio, run_ffmpeg_with_progress
from app.workers.caption_worker import _encode_progress_reporter, _encode_timeout
from app.workers.guard import serialize_job

logger = logging.getLogger(__name__)
_project_locks: WeakValueDictionary[tuple[str, str], asyncio.Lock] = WeakValueDictionary()


class RenderCancelled(Exception):
    pass


def ffmpeg_command(
    *,
    ffmpeg: str,
    source: str,
    output: str,
    kept: list[KeptSegment],
    has_audio: bool,
    source_duration_ms: int,
    inserts: list[tuple[str, PlannedInsert]] | None = None,
    width: int = 1920,
    height: int = 1080,
) -> list[str]:
    if not kept:
        raise ValueError("A rough cut must keep some footage")
    filters: list[str] = []
    fades = [
        min(
            0.04,
            (source_duration_ms - s.sourceEndMs) / 1000,
            (s.sourceEndMs - s.sourceStartMs) / 2000,
            (kept[i + 1].sourceEndMs - kept[i + 1].sourceStartMs) / 2000,
        )
        for i, s in enumerate(kept[:-1])
    ]
    for index, segment in enumerate(kept):
        start, end = segment.sourceStartMs / 1000, segment.sourceEndMs / 1000
        filters.append(
            f"[0:v:0]trim=start={start}:end={end},setpts=PTS-STARTPTS,fps=30,setsar=1[v{index}]"
        )
        if has_audio:
            # Extend outgoing audio 40ms into the silent handle; overlap it with the next
            # segment. Total output length stays identical to the video concat and mapping.
            extension = fades[index] if index < len(fades) else 0
            filters.append(
                f"[0:a:0]atrim=start={start}:end={end + extension},"
                f"asetpts=PTS-STARTPTS,aresample=48000[a{index}]"
            )
    video_inputs = "".join(f"[v{i}]" for i in range(len(kept)))
    filters.append(f"{video_inputs}concat=n={len(kept)}:v=1:a=0[vout]")
    video_out = "vout"
    input_args: list[str] = []
    for input_index, (path, insert) in enumerate(
        [(path, insert) for path, insert in inserts or [] if insert.placements], 1
    ):
        input_args.extend(["-i", path])
        # Split an insert when its source anchor straddles a removed span.
        labels = "".join(f"[ins{input_index}_{i}]" for i in range(len(insert.placements)))
        filters.append(f"[{input_index}:v:0]split={len(insert.placements)}{labels}")
        for placement_index, placement in enumerate(insert.placements):
            name = f"{input_index}_{placement_index}"
            start = placement.insertStartMs / 1000
            length = (placement.outputEndMs - placement.outputStartMs) / 1000
            output_start, output_end = placement.outputStartMs / 1000, placement.outputEndMs / 1000
            filters.append(
                f"[ins{name}]trim=start={start}:end={start + length},"
                f"setpts=PTS-STARTPTS+{output_start}/TB,"
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1[overlay{name}]"
            )
            next_out = f"vo{name}"
            filters.append(
                f"[{video_out}][overlay{name}]overlay=eof_action=pass:repeatlast=0:"
                f"enable='gte(t,{output_start})*lt(t,{output_end})'[{next_out}]"
            )
            video_out = next_out
    audio_out = "a0"
    if has_audio:
        for index in range(1, len(kept)):
            extension = fades[index - 1]
            next_out = f"ax{index}"
            filters.append(
                f"[{audio_out}][a{index}]acrossfade=d={extension}:c1=tri:c2=tri[{next_out}]"
            )
            audio_out = next_out
    args = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-i",
        source,
        *input_args,
        "-filter_complex",
        ";".join(filters),
        "-map",
        f"[{video_out}]",
    ]
    if has_audio:
        args.extend(["-map", f"[{audio_out}]", "-c:a", "aac", "-b:a", "160k"])
    return [
        *args,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "22",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-t",
        str(sum(s.sourceEndMs - s.sourceStartMs for s in kept) / 1000),
        output,
    ]


def live_service() -> RoughCutService:
    client, storage, settings = get_firestore_client(), get_storage_client(), get_settings()
    jobs = JobService(client)
    projects = ProjectService(client, storage=storage)
    return RoughCutService(
        client,
        AssetService(client, projects=projects, jobs=jobs, storage=storage, settings=settings),
        jobs,
        TranscriptService(client, storage=storage),
    )


@serialize_job
async def run_rough_cut(
    *, owner_uid: str, project_id: str, job_id: str, service: RoughCutService
) -> None:
    # Revision/transcript counters are local to the current single-instance runtime.
    key = (owner_uid, project_id)
    lock = _project_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _project_locks[key] = lock
    async with lock:
        await _render_rough_cut(
            owner_uid=owner_uid, project_id=project_id, job_id=job_id, service=service
        )


async def _render_rough_cut(
    *, owner_uid: str, project_id: str, job_id: str, service: RoughCutService
) -> None:
    jobs, assets, client = service.jobs, service.assets, service.client
    args = {"owner_uid": owner_uid, "project_id": project_id, "job_id": job_id}
    job = await asyncio.to_thread(jobs.load_for_worker, **args)
    if job.get("status") in {"succeeded", "failed", "cancelled"}:
        return
    payload = job["input"]
    asset_id = str(payload["assetId"])
    prefix = f"{project_object_prefix(owner_uid, project_id)}rough-cuts/{asset_id}/"
    transcript_id: str | None = None
    try:
        plan = RoughCutPlan.model_validate(payload["plan"])
        source_asset = await asyncio.to_thread(
            assets.get_asset,
            owner_uid=owner_uid,
            project_id=project_id,
            asset_id=plan.sourceAssetId,
        )
        transcript = await asyncio.to_thread(
            service.transcripts.get_by_id,
            owner_uid=owner_uid,
            project_id=project_id,
            transcript_id=payload["transcriptId"],
        )
        await asyncio.to_thread(
            jobs.mark_running, **args, step="preparing", message="Preparing your cut"
        )
        with tempfile.TemporaryDirectory(prefix="rough-cut-") as tmpdir:
            source, width, height, duration = await stage_source(
                storage=assets.storage,
                source_path=source_asset.storagePath,
                tmpdir=tmpdir,
                settings=assets.settings,
                fallback_duration_ms=plan.durationMsBefore,
            )
            if abs(duration - plan.durationMsBefore) > 250:
                raise ConflictError(
                    "Source duration differs from the saved transcript; refresh the source"
                )
            has_audio = await asyncio.to_thread(
                probe_has_audio, source, ffprobe_path=assets.settings.ffprobe_path
            )
            inserts: list[tuple[str, PlannedInsert]] = []
            for insert in plan.inserts:
                if not insert.placements:
                    continue
                data = await asyncio.to_thread(
                    service.load_insert,
                    owner_uid,
                    project_id,
                    insert.insertId,
                    plan.sourceAssetId,
                    payload["transcriptId"],
                )
                local_insert = os.path.join(tmpdir, f"insert-{len(inserts)}.mp4")
                size_bytes = await asyncio.to_thread(
                    assets.storage.object_size, data["storagePath"]
                )
                if not size_bytes or size_bytes > 50 * 1024 * 1024:
                    raise ConflictError("Packaging insert exceeds the preview download limit")
                await asyncio.to_thread(
                    assets.storage.download_to_filename, data["storagePath"], local_insert
                )
                inserts.append((local_insert, insert))
            output = os.path.join(tmpdir, "preview.mp4")
            command = ffmpeg_command(
                ffmpeg=assets.settings.ffmpeg_path,
                source=source,
                output=output,
                kept=plan.keptSegments,
                has_audio=has_audio,
                source_duration_ms=duration,
                inserts=inserts,
                width=width,
                height=height,
            )
            await asyncio.to_thread(
                run_ffmpeg_with_progress,
                command,
                timeout_seconds=_encode_timeout(duration),
                duration_seconds=plan.durationMsAfter / 1000,
                on_progress=_encode_progress_reporter(jobs, **args),
            )
            current = await asyncio.to_thread(jobs.load_for_worker, **args)
            if current.get("status") == "cancelled":
                raise RenderCancelled()
            await asyncio.to_thread(assets.projects.get, owner_uid=owner_uid, project_id=project_id)
            await asyncio.to_thread(
                jobs.update_progress,
                **args,
                percent=90,
                step="saving",
                message="Saving preview and remapping the transcript",
            )
            size = os.path.getsize(output)
            if size <= 0:
                raise RuntimeError("FFmpeg produced an empty preview")
            await asyncio.to_thread(
                assets.storage.upload_from_filename,
                f"{prefix}preview.mp4",
                output,
                content_type="video/mp4",
            )
        source_segments = await asyncio.to_thread(
            service.segments, owner_uid, project_id, payload["transcriptId"]
        )
        segments = remap_segments(source_segments, plan.keptSegments)
        transcript_id = await asyncio.to_thread(
            service.transcripts.save,
            owner_uid=owner_uid,
            project_id=project_id,
            source_asset_id=asset_id,
            language=transcript.language,
            words=[],
            segments=segments,
            speaker_labels=transcript.speakerLabels,
            duration_ms=plan.durationMsAfter,
            activate=False,
            storage_prefix=prefix,
        )
        project = await asyncio.to_thread(
            assets.projects.get, owner_uid=owner_uid, project_id=project_id
        )
        sources = await asyncio.to_thread(
            assets.list_assets, owner_uid=owner_uid, project_id=project_id
        )
        revision = max([project.revisionCount, *[a.revision or 0 for a in sources]]) + 1
        now = datetime.now(UTC)
        current = await asyncio.to_thread(jobs.load_for_worker, **args)
        if current.get("status") == "cancelled":
            raise RenderCancelled()
        data = {
            "ownerUid": owner_uid,
            "projectId": project_id,
            "type": "source_video",
            "status": "ready",
            "storagePath": f"{prefix}preview.mp4",
            "mimeType": "video/mp4",
            "sizeBytes": size,
            "durationMs": plan.durationMsAfter,
            "revision": revision,
            "width": width,
            "height": height,
            "derivedFromAssetId": plan.sourceAssetId,
            "roughCut": service.metadata(plan),
            "roughCutPlan": plan.model_dump(),
            "createdAt": now,
            "updatedAt": now,
            "deletedAt": None,
        }
        # Parent ownership is checked atomically, so deletion during rendering cannot resurrect it.
        persisted = await asyncio.to_thread(
            client.set_owned_child,
            project_path(owner_uid, project_id),
            asset_path(owner_uid, project_id, asset_id),
            owner_uid,
            data,
        )
        if not persisted:
            raise RuntimeError("Project was deleted while rendering")
        saved_transcript = await asyncio.to_thread(
            client.get_document, transcript_path(owner_uid, project_id, transcript_id)
        )
        if not saved_transcript or saved_transcript.get("ownerUid") != owner_uid:
            raise ConflictError("The derived transcript is no longer available")
        await asyncio.to_thread(
            client.update_document,
            project_path(owner_uid, project_id),
            {
                "sourceRevisionCounter": revision,
                "transcriptVersionCounter": saved_transcript["version"],
                "updatedAt": now,
            },
        )
        current = await asyncio.to_thread(jobs.load_for_worker, **args)
        if current.get("status") == "cancelled":
            raise RenderCancelled()
        await asyncio.to_thread(
            jobs.mark_succeeded,
            **args,
            output={
                "assetId": asset_id,
                "transcriptId": transcript_id,
                "artifactIds": [asset_id],
                "storagePaths": [
                    f"{prefix}{name}"
                    for name in ("preview.mp4", "transcript.json", "captions.vtt", "captions.srt")
                ],
            },
            message="Rough cut ready — preview before approving",
        )
    except Exception as exc:  # noqa: BLE001 - a render failure must reach the job UI
        if not isinstance(exc, RenderCancelled):
            logger.exception("rough-cut render failed")
        await asyncio.to_thread(assets.storage.delete_prefix, prefix)
        if transcript_id:
            await asyncio.to_thread(
                client.delete_document_tree, transcript_path(owner_uid, project_id, transcript_id)
            )
        await asyncio.to_thread(
            client.delete_document_tree, asset_path(owner_uid, project_id, asset_id)
        )
        # Deleted projects have no job to update; cancelled jobs keep their terminal status.
        terminal_job = await asyncio.to_thread(
            client.get_document, job_path(owner_uid, project_id, job_id)
        )
        if (
            terminal_job
            and terminal_job.get("ownerUid") == owner_uid
            and terminal_job.get("status") != "cancelled"
        ):
            await asyncio.to_thread(
                jobs.mark_failed, **args, code="ROUGH_CUT_FAILED", message=str(exc)
            )


def rough_cut_after_response(
    background_tasks: Any, *, owner_uid: str, project_id: str, job_id: str
) -> None:
    background_tasks.add_task(
        run_rough_cut,
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        service=live_service(),
    )
