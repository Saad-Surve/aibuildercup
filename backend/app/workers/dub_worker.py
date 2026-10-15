"""Dubbing worker: turn a project's transcript into a dubbed video.

Pipeline: a `dub` job is queued by the API -> translate the transcript when the source
language differs from the target -> synthesize one Text-to-Speech take per segment (bounded
concurrency) -> decode each take with FFmpeg, tempo-bend it to fit its timestamp window, and
lay the takes on one silent timeline -> mux the track onto the source video -> upload the
dubbed MP4 and the dubbed audio under the project prefix -> localization + job marked ready.

The job is idempotent: a terminal job is left untouched, and a localization that is already
ready is not re-dubbed. FFmpeg reads the source from a staged local file or a short-lived
signed URL, and writes its output to a temp file that is streamed back to Cloud Storage.
"""

import asyncio
import logging
import os
import shutil
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.config import Settings, get_settings
from app.errors import NotFoundError
from app.providers import Providers, get_providers
from app.schemas.jobs import JobStatus
from app.schemas.localizations import LocalizationStatus
from app.services.dubbing import assign_voices, build_track_wav, tempo_for
from app.services.firestore_service import (
    FirestoreClient,
    asset_path,
    get_firestore_client,
)
from app.services.glossary_service import GlossaryService
from app.services.job_service import JobService
from app.services.localization_adapt import adapt_translations
from app.services.localization_corpus import Corpus, GlossaryTerm, corpus_for
from app.services.localization_service import LocalizationService
from app.services.project_service import ProjectService
from app.services.source_media import stage_source
from app.services.storage_service import StorageClient, get_storage_client
from app.services.transcript_service import TranscriptService
from app.services.video_tools import (
    VideoToolError,
    ffmpeg_available,
    probe_duration_ms,
    probe_has_audio,
    run_ffmpeg,
    run_ffmpeg_command,
)
from app.workers.guard import serialize_job

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = frozenset(
    {JobStatus.succeeded.value, JobStatus.failed.value, JobStatus.cancelled.value}
)

#: Bounded encode settings: fast enough for a demo, good enough for a feed.
_ENCODE_TIMEOUT_MIN_SECONDS = 300
_ENCODE_TIMEOUT_MAX_SECONDS = 3600
_TTS_TIMEOUT_SECONDS = 120
#: Cloud Translation caps a request at 30k codepoints; stay well under it and keep line
#: counts small enough that a failed batch is cheap to retry.
_TRANSLATE_MAX_CHARS = 8_000
_TRANSLATE_MAX_ITEMS = 60

#: Merge consecutive same-speaker segments into one Text-to-Speech take so the speech flows
#: instead of being chopped into one rigid window per line (which leaves a pause after a short
#: take and clips the tail of a long one). The caps bound a single take and its window.
_CHUNK_MAX_MS = 15_000
_CHUNK_MAX_CHARS = 300
_CHUNK_MAX_GAP_MS = 1_000


def _encode_timeout(duration_ms: int) -> int:
    seconds = max(0, int(duration_ms or 0)) / 1000
    # Allow roughly 4x realtime; clamp so a runaway encode cannot hang a worker forever.
    return int(
        max(
            _ENCODE_TIMEOUT_MIN_SECONDS,
            min(_ENCODE_TIMEOUT_MAX_SECONDS, seconds * 4),
        )
    )


@serialize_job
async def run_dub(
    *,
    owner_uid: str,
    project_id: str,
    job_id: str,
    firestore: FirestoreClient,
    jobs: JobService,
    projects: ProjectService,
    localizations: LocalizationService,
    transcripts: TranscriptService,
    storage: StorageClient,
    settings: Settings,
    providers: Providers,
) -> str | None:
    """Run one dub. Returns the localization id, or None if skipped/failed."""
    try:
        job = await asyncio.to_thread(
            jobs.load_for_worker, owner_uid=owner_uid, project_id=project_id, job_id=job_id
        )
    except NotFoundError:
        logger.warning("dub job %s not found; skipping", job_id)
        return None

    if job.get("status") in TERMINAL_STATUSES:
        logger.info("dub job %s already %s; skipping", job_id, job.get("status"))
        return (job.get("input") or {}).get("localizationId")

    localization_id = (job.get("input") or {}).get("localizationId")
    if not localization_id:
        await asyncio.to_thread(
            jobs.mark_failed,
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            message="This dub could not start. Try dubbing again.",
            code="DUB_FAILED",
        )
        return None

    localization = await asyncio.to_thread(
        localizations.load,
        owner_uid=owner_uid,
        project_id=project_id,
        localization_id=localization_id,
    )
    if localization is None:
        await asyncio.to_thread(
            jobs.mark_failed,
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            message="This dub could not be found. Try dubbing again.",
            code="DUB_FAILED",
        )
        return None

    if localization.get("status") == LocalizationStatus.ready.value:
        await asyncio.to_thread(
            jobs.mark_succeeded,
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            output={
                "artifactIds": [],
                "storagePaths": [localization.get("videoStoragePath")]
                if localization.get("videoStoragePath")
                else [],
                "localizationId": localization_id,
            },
            message="Already dubbed",
        )
        return localization_id

    try:
        await _dub(
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            localization_id=localization_id,
            localization=localization,
            firestore=firestore,
            jobs=jobs,
            localizations=localizations,
            transcripts=transcripts,
            storage=storage,
            settings=settings,
            providers=providers,
        )
    except Exception as exc:  # noqa: BLE001 - one catch marks both records failed
        logger.exception("dub job %s failed", job_id)
        message = _failure_message(exc)
        try:
            await asyncio.to_thread(
                localizations.mark_failed,
                owner_uid=owner_uid,
                project_id=project_id,
                localization_id=localization_id,
                code="DUB_FAILED",
                message=message,
            )
        except Exception:  # noqa: BLE001 - job failure is the primary signal
            logger.exception("localization %s: could not mark failed", localization_id)
        await asyncio.to_thread(
            jobs.mark_failed,
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            message=message,
            code="DUB_FAILED",
        )
        return None
    return localization_id


async def _dub(
    *,
    owner_uid: str,
    project_id: str,
    job_id: str,
    localization_id: str,
    localization: dict[str, Any],
    firestore: FirestoreClient,
    jobs: JobService,
    localizations: LocalizationService,
    transcripts: TranscriptService,
    storage: StorageClient,
    settings: Settings,
    providers: Providers,
) -> None:
    if not ffmpeg_available(settings.ffmpeg_path):
        raise VideoToolError(f"ffmpeg ({settings.ffmpeg_path}) is not available on this server")

    await asyncio.to_thread(
        jobs.mark_running,
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        step="preparing",
        message="Preparing the dub",
    )

    source_asset_id = localization.get("sourceAssetId")
    if not source_asset_id:
        raise VideoToolError("The dub has no source video.")
    asset = firestore.get_document(asset_path(owner_uid, project_id, str(source_asset_id)))
    if asset is None or asset.get("ownerUid") != owner_uid:
        raise VideoToolError("The source video is missing.")
    source_path = str(asset.get("storagePath") or "")
    if not source_path or not await asyncio.to_thread(storage.object_exists, source_path):
        raise VideoToolError("The source video is missing from storage.")

    transcript_id = localization.get("sourceTranscriptId")
    if not transcript_id:
        raise VideoToolError("The dub has no source transcript.")
    transcript = await asyncio.to_thread(
        transcripts.get_by_id,
        owner_uid=owner_uid,
        project_id=project_id,
        transcript_id=str(transcript_id),
    )
    if not transcript.segments:
        raise VideoToolError("The transcript has no segments to dub.")

    target_language = str(localization.get("targetLanguage") or "en")
    source_language = transcript.language or localization.get("sourceLanguage")

    tmpdir = tempfile.mkdtemp(prefix="dub-")
    try:
        # Stage the source first: a local copy makes the later encode seek reliable, and a
        # missing/unreadable source fails before any paid Text-to-Speech work.
        source_ref, width, height, duration_ms = await stage_source(
            storage=storage,
            source_path=source_path,
            tmpdir=tmpdir,
            settings=settings,
            fallback_duration_ms=transcript.durationMs,
        )

        assignments = assign_voices(
            target_language,
            localization.get("voice"),
            (segment.speaker for segment in transcript.segments),
        )

        corpus = _corpus(localization, source_language, target_language)
        translated = await _translate(
            transcript=transcript,
            target_language=target_language,
            source_language=source_language,
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            jobs=jobs,
            localizations=localizations,
            localization_id=localization_id,
            translate=providers.translate,
            corpus=corpus,
            llm=providers.llm,
            model=settings.model_localization,
        )

        await asyncio.to_thread(
            localizations.mark_status,
            owner_uid=owner_uid,
            project_id=project_id,
            localization_id=localization_id,
            status=LocalizationStatus.synthesizing,
        )
        placements = await _synthesize(
            segments=transcript.segments,
            texts=translated,
            assignments=assignments,
            tmpdir=tmpdir,
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            jobs=jobs,
            tts=providers.tts,
            settings=settings,
        )

        total_ms = duration_ms or _last_end_ms(transcript.segments) or transcript.durationMs
        wav_bytes = build_track_wav(
            placements,
            total_ms=total_ms,
            sample_rate_hz=settings.tts_sample_rate_hz,
        )
        wav_path = os.path.join(tmpdir, "dubbed.wav")
        with open(wav_path, "wb") as handle:
            handle.write(wav_bytes)

        audio_path = os.path.join(tmpdir, "dubbed.mp3")
        await asyncio.to_thread(
            run_ffmpeg_command,
            [
                settings.ffmpeg_path,
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-y",
                "-i",
                wav_path,
                "-c:a",
                "libmp3lame",
                "-b:a",
                "192k",
                audio_path,
            ],
            timeout_seconds=_encode_timeout(total_ms),
        )

        await asyncio.to_thread(
            localizations.mark_status,
            owner_uid=owner_uid,
            project_id=project_id,
            localization_id=localization_id,
            status=LocalizationStatus.muxing,
        )
        await asyncio.to_thread(
            jobs.update_progress,
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            percent=80,
            step="muxing",
            message="Combining the dubbed audio with the video",
        )
        out_path = os.path.join(tmpdir, "dubbed.mp4")
        keep_original = bool(
            localization.get("keepOriginalAudio") or settings.dub_keep_original_audio
        )
        has_original_audio = await asyncio.to_thread(
            probe_has_audio, source_ref, ffprobe_path=settings.ffprobe_path
        )
        await _mux(
            ffmpeg_path=settings.ffmpeg_path,
            source=source_ref,
            audio=wav_path,
            out_path=out_path,
            keep_original=keep_original and has_original_audio,
            original_volume=settings.dub_original_audio_volume,
            timeout_seconds=_encode_timeout(total_ms),
        )
        if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
            raise VideoToolError("ffmpeg produced an empty video.")

        await asyncio.to_thread(
            jobs.update_progress,
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            percent=90,
            step="uploading",
            message="Saving the dubbed video",
        )
        video_object, audio_object = localizations.target_paths(
            owner_uid=owner_uid,
            project_id=project_id,
            localization_id=localization_id,
        )
        captions_object = localizations.captions_path(
            owner_uid=owner_uid,
            project_id=project_id,
            localization_id=localization_id,
        )
        size_bytes = os.path.getsize(out_path)
        await asyncio.to_thread(
            storage.upload_from_filename, video_object, out_path, content_type="video/mp4"
        )
        await asyncio.to_thread(
            storage.upload_from_filename, audio_object, audio_path, content_type="audio/mpeg"
        )
        await asyncio.to_thread(
            storage.upload_text,
            captions_object,
            _build_srt(transcript.segments, translated),
            content_type="application/x-subrip",
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    await asyncio.to_thread(
        localizations.mark_ready,
        owner_uid=owner_uid,
        project_id=project_id,
        localization_id=localization_id,
        video_storage_path=video_object,
        audio_storage_path=audio_object,
        captions_storage_path=captions_object,
        size_bytes=size_bytes,
        duration_ms=total_ms,
        width=width,
        height=height,
    )
    await asyncio.to_thread(
        jobs.mark_succeeded,
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        output={
            "artifactIds": [],
            "storagePaths": [video_object, audio_object],
            "localizationId": localization_id,
        },
        message="Dubbed video ready",
    )
    logger.info(
        "dub %s done: %dx%d, %.1fs, %.1f MB, %d segments",
        localization_id,
        width,
        height,
        total_ms / 1000,
        size_bytes / 1e6,
        len(transcript.segments),
    )


async def _translate(
    *,
    transcript: Any,
    target_language: str,
    source_language: str | None,
    owner_uid: str,
    project_id: str,
    job_id: str,
    jobs: JobService,
    localizations: LocalizationService,
    localization_id: str,
    translate: Any,
    corpus: Corpus,
    llm: Any,
    model: str,
) -> list[str]:
    """Return the segment texts in the target language."""
    texts = [segment.text for segment in transcript.segments]
    source_base = (source_language or "").replace("_", "-").split("-", 1)[0].lower()
    target_base = target_language.replace("_", "-").split("-", 1)[0].lower()
    if source_base and source_base == target_base:
        return list(texts)

    await asyncio.to_thread(
        localizations.mark_status,
        owner_uid=owner_uid,
        project_id=project_id,
        localization_id=localization_id,
        status=LocalizationStatus.translating,
    )
    await asyncio.to_thread(
        jobs.update_progress,
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        percent=10,
        step="translating",
        message=f"Translating the transcript into {target_language}",
    )

    translated = list(texts)
    indexed = [(index, text) for index, text in enumerate(texts) if text.strip()]
    for chunk in _chunks([text for _, text in indexed]):
        batch_indices = [indexed[position][0] for position in chunk]
        batch = [indexed[position][1] for position in chunk]
        result = await translate.translate(
            texts=batch,
            target_language=target_language,
            source_language=source_language,
            glossary_id=None,
        )
        for index, value in zip(batch_indices, result, strict=False):
            translated[index] = value

    # Second pass: Gemini adapts the literal draft against the corpus and glossary
    # (idioms, brands, code-mixing, units, honorifics). Best-effort: a failure keeps
    # the raw machine translation.
    return await adapt_translations(
        texts,
        translated,
        source_language=source_language,
        target_language=target_language,
        corpus=corpus,
        llm=llm,
        model=model,
    )


def _chunks(texts: Sequence[str]) -> list[list[int]]:
    """Group text indexes into translation-sized batches."""
    chunks: list[list[int]] = []
    current: list[int] = []
    size = 0
    for index, text in enumerate(texts):
        if current and (
            len(current) >= _TRANSLATE_MAX_ITEMS
            or size + len(text) > _TRANSLATE_MAX_CHARS
        ):
            chunks.append(current)
            current = []
            size = 0
        current.append(index)
        size += len(text)
    if current:
        chunks.append(current)
    return chunks


@dataclass(frozen=True)
class _SpeechChunk:
    start_ms: int
    end_ms: int
    text: str
    speaker: int | None


def _chunk_segments(
    segments: Sequence[Any], texts: Sequence[str]
) -> list[_SpeechChunk]:
    """Group consecutive same-speaker segments into continuous Text-to-Speech takes.

    Synthesizing one clip per transcript line comes out choppy: every line gets a hard
    window, so a short take leaves a silence and a long one is truncated mid-word. Joining
    adjacent lines that share a speaker and are not separated by a real pause keeps the
    prosody and removes most of those gaps.
    """
    chunks: list[_SpeechChunk] = []
    for index, segment in enumerate(segments):
        text = (texts[index] if index < len(texts) else segment.text).strip()
        if not text:
            continue
        start_ms = int(segment.startMs)
        end_ms = int(segment.endMs)
        speaker = segment.speaker
        if chunks:
            current = chunks[-1]
            gap = start_ms - current.end_ms
            same_speaker = (0 if speaker is None else speaker) == (
                0 if current.speaker is None else current.speaker
            )
            joined = f"{current.text} {text}"
            if (
                same_speaker
                and gap <= _CHUNK_MAX_GAP_MS
                and len(joined) <= _CHUNK_MAX_CHARS
                and end_ms - current.start_ms <= _CHUNK_MAX_MS
            ):
                chunks[-1] = _SpeechChunk(
                    start_ms=current.start_ms,
                    end_ms=end_ms,
                    text=joined,
                    speaker=current.speaker,
                )
                continue
        chunks.append(
            _SpeechChunk(start_ms=start_ms, end_ms=end_ms, text=text, speaker=speaker)
        )
    return chunks


async def _synthesize(
    *,
    segments: Sequence[Any],
    texts: Sequence[str],
    assignments: dict[Any, Any],
    tmpdir: str,
    owner_uid: str,
    project_id: str,
    job_id: str,
    jobs: JobService,
    tts: Any,
    settings: Settings,
) -> list[tuple[int, int, bytes]]:
    """Synthesize and normalize continuous chunks, returning `(startMs, endMs, pcm)` takes."""
    concurrency = max(1, settings.dub_max_concurrency)
    placements: list[tuple[int, int, bytes]] = []
    chunks = _chunk_segments(segments, texts)
    total = len(chunks)
    fallback_voice = next(iter(assignments.values()))

    async def one(index: int) -> tuple[int, int, bytes] | None:
        chunk = chunks[index]
        voice = assignments.get(chunk.speaker) or fallback_voice
        mp3 = await tts.synthesize(text=chunk.text, language=voice.language_code, voice=voice.name)
        if not mp3:
            return None
        mp3_path = os.path.join(tmpdir, f"chunk-{index:04d}.mp3")
        with open(mp3_path, "wb") as handle:
            handle.write(mp3)
        actual_ms = await asyncio.to_thread(
            probe_duration_ms, mp3_path, ffprobe_path=settings.ffprobe_path
        )
        target_ms = max(0, chunk.end_ms - chunk.start_ms)
        tempo = tempo_for(
            actual_ms or target_ms,
            target_ms,
            min_tempo=settings.dub_min_tempo,
            max_tempo=settings.dub_max_tempo,
        )
        pcm = await asyncio.to_thread(
            run_ffmpeg,
            [
                settings.ffmpeg_path,
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-i",
                mp3_path,
                "-filter:a",
                f"atempo={tempo:.4f}",
                "-ar",
                str(settings.tts_sample_rate_hz),
                "-ac",
                "1",
                "-f",
                "s16le",
                "pipe:1",
            ],
            timeout_seconds=_TTS_TIMEOUT_SECONDS,
        )
        return (chunk.start_ms, chunk.end_ms, pcm)

    semaphore = asyncio.Semaphore(concurrency)

    async def bounded_one(index: int) -> tuple[int, int, bytes] | None:
        async with semaphore:
            return await one(index)

    # Refill slots as individual chunks finish; a slow chunk no longer stalls
    # every other slot until an entire fixed batch has completed.
    tasks = [asyncio.create_task(bounded_one(index)) for index in range(total)]
    try:
        for done, task in enumerate(asyncio.as_completed(tasks), start=1):
            result = await task
            if result is not None:
                placements.append(result)
            if done % concurrency == 0 or done == total:
                await asyncio.to_thread(
                    jobs.update_progress,
                    owner_uid=owner_uid,
                    project_id=project_id,
                    job_id=job_id,
                    percent=15 + int(60 * done / max(1, total)),
                    step="synthesizing",
                    message=f"Generating voices ({done}/{total})",
                )
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    placements.sort(key=lambda item: item[0])
    return placements


async def _mux(
    *,
    ffmpeg_path: str,
    source: str,
    audio: str,
    out_path: str,
    keep_original: bool,
    original_volume: float,
    timeout_seconds: int,
) -> None:
    """Mux the dubbed track onto the video, falling back to a re-encode."""
    if keep_original:
        filter_graph = (
            f"[0:a]volume={original_volume:.3f}[orig];"
            f"[1:a]volume=1.0[dub];"
            "[orig][dub]amix=inputs=2:duration=first:normalize=0[a]"
        )
        mapping = ["-filter_complex", filter_graph, "-map", "0:v:0", "-map", "[a]"]
    else:
        mapping = ["-map", "0:v:0", "-map", "1:a:0"]

    base = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-i",
        source,
        "-i",
        audio,
        *mapping,
    ]
    tail = ["-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out_path]
    copy_args = [*base, "-c:v", "copy", *tail]
    reencode_args = [
        *base,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "22",
        "-pix_fmt",
        "yuv420p",
        *tail,
    ]
    try:
        await asyncio.to_thread(
            run_ffmpeg_command, copy_args, timeout_seconds=timeout_seconds
        )
    except VideoToolError:
        # The source's video codec may not be allowed in an MP4 (for example VP9 in WebM),
        # so re-encode just the video. Audio stays the dubbed track either way.
        logger.info("dub mux: stream copy failed; re-encoding the video")
        await asyncio.to_thread(
            run_ffmpeg_command, reencode_args, timeout_seconds=timeout_seconds
        )


def _last_end_ms(segments: Sequence[Any]) -> int:
    return max((int(segment.endMs) for segment in segments), default=0)


def _corpus(
    localization: dict[str, Any],
    source_language: str | None,
    target_language: str,
) -> Corpus:
    """The corpus + glossary snapshot a dub was created with.

    The global corpus is bundled and versioned; the project glossary is snapshotted onto the
    localization at create time, so editing the glossary cannot change a running or finished
    dub.
    """
    base = corpus_for(source_language, target_language)
    raw_terms = localization.get("glossaryTerms")
    terms: list[GlossaryTerm] = []
    if isinstance(raw_terms, list):
        for item in raw_terms:
            if not isinstance(item, dict):
                continue
            source = str(item.get("source") or "").strip()
            target = str(item.get("target") or "").strip()
            if source and target:
                terms.append(GlossaryTerm(source=source, target=target))
    return Corpus(version=base.version, glossary=tuple(terms), traps=base.traps)


def _srt_timestamp(ms: int) -> str:
    total = max(0, int(ms))
    hours, rem = divmod(total, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def _build_srt(segments: Sequence[Any], texts: Sequence[str]) -> str:
    """Localized SRT built from the translated segment texts."""
    blocks: list[str] = []
    number = 0
    for index, segment in enumerate(segments):
        text = (texts[index] if index < len(texts) else segment.text).strip()
        if not text:
            continue
        number += 1
        start = _srt_timestamp(int(segment.startMs))
        end = _srt_timestamp(max(int(segment.endMs), int(segment.startMs) + 1))
        blocks.append(f"{number}\n{start} --> {end}\n{text}\n")
    return "\n".join(blocks)


def _failure_message(exc: BaseException) -> str:
    if isinstance(exc, VideoToolError):
        detail = str(exc).strip()
        if detail:
            return "Dubbing failed. Try again."
    return "Dubbing failed. Try again."


# --------------------------------------------------------------------------- wiring


def build_worker_services(
    *,
    firestore: FirestoreClient,
    jobs: JobService,
    projects: ProjectService,
    localizations: LocalizationService,
    transcripts: TranscriptService,
    storage: StorageClient,
    settings: Settings,
    providers: Providers,
) -> dict[str, Any]:
    return {
        "firestore": firestore,
        "jobs": jobs,
        "projects": projects,
        "localizations": localizations,
        "transcripts": transcripts,
        "storage": storage,
        "settings": settings,
        "providers": providers,
    }


def live_worker_dependencies() -> dict[str, Any]:
    firestore = get_firestore_client()
    settings = get_settings()
    storage = get_storage_client()
    jobs = JobService(firestore)
    projects = ProjectService(firestore, storage=storage)
    transcripts = TranscriptService(firestore, storage=storage)
    return build_worker_services(
        firestore=firestore,
        jobs=jobs,
        projects=projects,
        localizations=LocalizationService(
            firestore,
            projects=projects,
            jobs=jobs,
            transcripts=transcripts,
            glossaries=GlossaryService(firestore, projects=projects),
            storage=storage,
            url_ttl_seconds=settings.upload_url_ttl_seconds,
        ),
        transcripts=transcripts,
        storage=storage,
        settings=settings,
        providers=get_providers(),
    )


def dub_after_response(
    background_tasks: Any,
    *,
    owner_uid: str,
    project_id: str,
    job_id: str,
) -> None:
    """Run the dub worker after the HTTP response is sent."""
    background_tasks.add_task(
        run_dub,
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        **live_worker_dependencies(),
    )
