"""Localization (dubbing) records.

A *localization* is one request to dub a project's source video into a target language.
Records live at `users/{uid}/projects/{projectId}/localizations/{localizationId}` and the media
under `users/{uid}/projects/{projectId}/renders/dubs/`, so the existing project delete
(Firestore subtree + storage prefix) covers them with no extra wiring.

The service only owns persistence and the job hand-off; `dub_worker` does the translation, TTS,
and FFmpeg work.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from app.errors import BadRequestError, NotFoundError
from app.schemas.jobs import Job, JobType
from app.schemas.localizations import (
    Localization,
    LocalizationRequest,
    LocalizationStatus,
)
from app.services.dubbing import assign_voices, default_voice
from app.services.firestore_service import (
    FirestoreClient,
    asset_path,
    assets_collection_path,
    localization_object_path,
    localization_path,
    localizations_collection_path,
    project_path,
)
from app.services.glossary_service import GlossaryService
from app.services.job_service import JobService
from app.services.localization_corpus import corpus_for
from app.services.project_service import ProjectService
from app.services.storage_service import StorageClient
from app.services.transcript_service import TranscriptService


def is_owner(document: dict[str, Any], owner_uid: str) -> bool:
    return document.get("ownerUid") == owner_uid


def _speaker_key(speaker: int | None) -> str:
    return "0" if speaker is None else str(speaker)


def _to_localization(
    localization_id: str,
    data: dict[str, Any],
    *,
    download_url: str | None = None,
    captions_url: str | None = None,
) -> Localization:
    raw_voices = data.get("speakerVoices") or {}
    speaker_voices = {
        str(key): str(value) for key, value in raw_voices.items() if value is not None
    }
    return Localization(
        localizationId=localization_id,
        projectId=data.get("projectId", ""),
        status=LocalizationStatus(
            data.get("status", LocalizationStatus.queued.value)
        ),
        sourceAssetId=data.get("sourceAssetId"),
        sourceTranscriptId=data.get("sourceTranscriptId"),
        transcriptVersion=data.get("transcriptVersion"),
        sourceLanguage=data.get("sourceLanguage"),
        targetLanguage=data.get("targetLanguage", ""),
        voice=data.get("voice"),
        speakerVoices=speaker_voices,
        keepOriginalAudio=bool(data.get("keepOriginalAudio", False)),
        fileName=data.get("fileName"),
        videoStoragePath=data.get("videoStoragePath"),
        audioStoragePath=data.get("audioStoragePath"),
        captionsStoragePath=data.get("captionsStoragePath"),
        mimeType=data.get("mimeType", "video/mp4"),
        sizeBytes=int(data.get("sizeBytes") or 0),
        durationMs=int(data.get("durationMs") or 0),
        width=int(data.get("width") or 0),
        height=int(data.get("height") or 0),
        jobId=data.get("jobId"),
        error=data.get("error"),
        downloadUrl=download_url,
        captionsUrl=captions_url,
        corpusVersion=int(data.get("corpusVersion") or 0),
        glossaryVersion=int(data.get("glossaryVersion") or 0),
        createdAt=data["createdAt"],
        updatedAt=data["updatedAt"],
    )


class LocalizationService:
    def __init__(
        self,
        client: FirestoreClient,
        *,
        projects: ProjectService,
        jobs: JobService,
        transcripts: TranscriptService,
        glossaries: GlossaryService,
        storage: StorageClient,
        url_ttl_seconds: int = 900,
    ) -> None:
        self.client = client
        self.projects = projects
        self.jobs = jobs
        self.transcripts = transcripts
        self.glossaries = glossaries
        self.storage = storage
        self.url_ttl_seconds = url_ttl_seconds

    # ------------------------------------------------------------------- public API

    def create(
        self, *, owner_uid: str, project_id: str, payload: LocalizationRequest
    ) -> tuple[Localization, Job]:
        """Validate the project/transcript/voice and queue a dub job."""
        self.projects.get(owner_uid=owner_uid, project_id=project_id)
        raw_project = self.client.get_document(project_path(owner_uid, project_id)) or {}
        source_asset_id = raw_project.get("sourceAssetId") or self._first_source_asset(
            owner_uid=owner_uid, project_id=project_id
        )
        if not source_asset_id:
            raise BadRequestError(
                "This project has no source video to dub.",
                code="SOURCE_NOT_FOUND",
                details={"projectId": project_id},
            )
        asset = self.client.get_document(
            asset_path(owner_uid, project_id, source_asset_id)
        )
        if asset is None or not is_owner(asset, owner_uid):
            raise NotFoundError(
                "Source video not found", details={"projectId": project_id}
            )

        transcript = self.transcripts.get(
            owner_uid=owner_uid,
            project_id=project_id,
            version=payload.transcriptVersion,
        )

        try:
            # Resolves the requested voice and rejects an unsupported language now, rather
            # than part-way through a paid TTS run.
            default_voice(payload.targetLanguage, payload.voice)
        except ValueError as exc:
            raise BadRequestError(
                str(exc),
                code="UNSUPPORTED_LANGUAGE",
                details={"targetLanguage": payload.targetLanguage},
            ) from exc

        assignments = assign_voices(
            payload.targetLanguage,
            payload.voice,
            (segment.speaker for segment in transcript.segments),
        )
        speaker_voices = {
            _speaker_key(speaker): voice.name for speaker, voice in assignments.items()
        }

        # Snapshot the corpus/glossary the dub will use, so a later glossary edit cannot
        # change a localization that is already running (or completed).
        glossary_terms, glossary_version = self.glossaries.applicable(
            owner_uid=owner_uid,
            project_id=project_id,
            target_language=payload.targetLanguage,
        )
        corpus_version = corpus_for(
            transcript.language, payload.targetLanguage
        ).version

        localization_id = uuid4().hex
        now = datetime.now(UTC)
        document: dict[str, Any] = {
            "ownerUid": owner_uid,
            "projectId": project_id,
            "status": LocalizationStatus.queued.value,
            "sourceAssetId": source_asset_id,
            "sourceTranscriptId": transcript.transcriptId,
            "transcriptVersion": payload.transcriptVersion,
            "sourceLanguage": transcript.language or None,
            "targetLanguage": payload.targetLanguage,
            "voice": payload.voice,
            "speakerVoices": speaker_voices,
            "keepOriginalAudio": payload.keepOriginalAudio,
            "fileName": (payload.fileName or "").strip() or None,
            "videoStoragePath": None,
            "audioStoragePath": None,
            "captionsStoragePath": None,
            "mimeType": "video/mp4",
            "sizeBytes": 0,
            "durationMs": transcript.durationMs,
            "width": 0,
            "height": 0,
            "corpusVersion": corpus_version,
            "glossaryVersion": glossary_version,
            "glossaryTerms": [term.model_dump() for term in glossary_terms],
            "jobId": None,
            "error": None,
            "createdAt": now,
            "updatedAt": now,
        }
        path = localization_path(owner_uid, project_id, localization_id)
        self.client.set_document(path, document)

        job = self.jobs.create(
            owner_uid=owner_uid,
            project_id=project_id,
            job_type=JobType.dub,
            idempotency_key=f"dub-{project_id}-{localization_id}",
            input={"localizationId": localization_id},
        )
        self.client.update_document(path, {"jobId": job.jobId, "updatedAt": now})
        document["jobId"] = job.jobId
        return _to_localization(localization_id, document), job

    def list(self, *, owner_uid: str, project_id: str) -> list[Localization]:
        self.projects.get(owner_uid=owner_uid, project_id=project_id)
        rows = self.client.query_collection(
            localizations_collection_path(owner_uid, project_id),
            filters=[],
            order_by=[("createdAt", "DESCENDING")],
            limit=50,
            offset=0,
        )
        items: list[Localization] = []
        for localization_id, data in rows:
            if not is_owner(data, owner_uid):
                continue
            download_url, captions_url = self._urls(data)
            items.append(
                _to_localization(
                    localization_id,
                    data,
                    download_url=download_url,
                    captions_url=captions_url,
                )
            )
        return items

    def get(
        self, *, owner_uid: str, project_id: str, localization_id: str
    ) -> Localization:
        data = self._require_owned(
            owner_uid=owner_uid, project_id=project_id, localization_id=localization_id
        )
        download_url, captions_url = self._urls(data)
        return _to_localization(
            localization_id,
            data,
            download_url=download_url,
            captions_url=captions_url,
        )

    def download_url(
        self, *, owner_uid: str, project_id: str, localization_id: str
    ) -> tuple[str, datetime]:
        """Signed read URL for a ready dubbed video, plus its expiry."""
        data = self._require_owned(
            owner_uid=owner_uid, project_id=project_id, localization_id=localization_id
        )
        path = data.get("videoStoragePath")
        if data.get("status") != LocalizationStatus.ready.value or not path:
            raise BadRequestError(
                "The dubbed video is not ready yet.",
                code="LOCALIZATION_NOT_READY",
                details={"localizationId": localization_id},
            )
        ttl = self.url_ttl_seconds
        url = self.storage.signed_download_url(str(path), expires_seconds=ttl)
        return url, datetime.now(UTC) + timedelta(seconds=ttl)

    def delete(self, *, owner_uid: str, project_id: str, localization_id: str) -> None:
        """Remove a dub's media and record. Idempotent."""
        data = self._require_owned(
            owner_uid=owner_uid, project_id=project_id, localization_id=localization_id
        )
        for key in ("videoStoragePath", "audioStoragePath", "captionsStoragePath"):
            path = data.get(key)
            if path:
                try:
                    self.storage.delete_prefix(str(path))
                except Exception:  # noqa: BLE001 - the record delete must still proceed
                    pass
        self.client.delete_document(
            localization_path(owner_uid, project_id, localization_id)
        )

    # ------------------------------------------------------------------- worker API

    def load(
        self, *, owner_uid: str, project_id: str, localization_id: str
    ) -> dict[str, Any] | None:
        """Raw localization document for the worker (ownership checked)."""
        data = self.client.get_document(
            localization_path(owner_uid, project_id, localization_id)
        )
        if data is None or not is_owner(data, owner_uid):
            return None
        return data

    def target_paths(
        self, *, owner_uid: str, project_id: str, localization_id: str
    ) -> tuple[str, str]:
        return (
            localization_object_path(owner_uid, project_id, localization_id, "mp4"),
            localization_object_path(owner_uid, project_id, localization_id, "mp3"),
        )

    def captions_path(
        self, *, owner_uid: str, project_id: str, localization_id: str
    ) -> str:
        """Object path for the localized SRT: `.../renders/dubs/{id}.srt`."""
        return localization_object_path(owner_uid, project_id, localization_id, "srt")

    def mark_status(
        self,
        *,
        owner_uid: str,
        project_id: str,
        localization_id: str,
        status: LocalizationStatus,
    ) -> None:
        self.client.update_document(
            localization_path(owner_uid, project_id, localization_id),
            {"status": status.value, "updatedAt": datetime.now(UTC)},
        )

    def mark_ready(
        self,
        *,
        owner_uid: str,
        project_id: str,
        localization_id: str,
        video_storage_path: str,
        audio_storage_path: str,
        captions_storage_path: str | None = None,
        size_bytes: int,
        duration_ms: int,
        width: int,
        height: int,
    ) -> None:
        self.client.update_document(
            localization_path(owner_uid, project_id, localization_id),
            {
                "status": LocalizationStatus.ready.value,
                "videoStoragePath": video_storage_path,
                "audioStoragePath": audio_storage_path,
                "captionsStoragePath": captions_storage_path,
                "sizeBytes": size_bytes,
                "durationMs": duration_ms,
                "width": width,
                "height": height,
                "error": None,
                "updatedAt": datetime.now(UTC),
            },
        )

    def mark_failed(
        self,
        *,
        owner_uid: str,
        project_id: str,
        localization_id: str,
        code: str,
        message: str,
    ) -> None:
        self.client.update_document(
            localization_path(owner_uid, project_id, localization_id),
            {
                "status": LocalizationStatus.failed.value,
                "error": {"code": code, "message": message},
                "updatedAt": datetime.now(UTC),
            },
        )

    # ------------------------------------------------------------------- internals

    def _maybe_url(self, path: Any) -> str | None:
        if not path:
            return None
        try:
            return self.storage.signed_download_url(
                str(path), expires_seconds=self.url_ttl_seconds
            )
        except Exception:  # noqa: BLE001 - a signing hiccup must not hide the dub
            return None

    def _urls(self, data: dict[str, Any]) -> tuple[str | None, str | None]:
        if data.get("status") != LocalizationStatus.ready.value:
            return None, None
        return (
            self._maybe_url(data.get("videoStoragePath")),
            self._maybe_url(data.get("captionsStoragePath")),
        )

    def _first_source_asset(self, *, owner_uid: str, project_id: str) -> str | None:
        rows = self.client.query_collection(
            assets_collection_path(owner_uid, project_id),
            filters=[],
            order_by=[],
            limit=50,
            offset=0,
        )
        for asset_id, data in rows:
            if is_owner(data, owner_uid) and data.get("type") == "source_video":
                return asset_id
        return None

    def _require_owned(
        self, *, owner_uid: str, project_id: str, localization_id: str
    ) -> dict[str, Any]:
        self.projects.get(owner_uid=owner_uid, project_id=project_id)
        data = self.client.get_document(
            localization_path(owner_uid, project_id, localization_id)
        )
        if data is None or not is_owner(data, owner_uid):
            raise NotFoundError(
                "Localization not found",
                details={"localizationId": localization_id},
            )
        return data
