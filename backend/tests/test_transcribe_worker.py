from typing import Any

from app.config import Settings
from app.schemas.assets import CreateUploadSession
from app.schemas.jobs import JobType
from app.schemas.projects import CreateProject
from app.services.asset_service import AssetService
from app.services.job_service import JobService
from app.services.project_service import ProjectService
from app.services.transcript_service import TranscriptService
from app.workers.transcribe_worker import run_transcribe
from tests.fakes import FakeFirestoreClient, FakeStorageClient

UID = "uid-1"


class StubStt:
    def __init__(self, response: dict[str, Any] | Exception) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def transcribe(
        self, *, gcs_uri: str, language_codes: list[str], model: str
    ) -> dict[str, Any]:
        self.calls.append({"gcs_uri": gcs_uri, "language_codes": language_codes, "model": model})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    def gcs_uri_for(self, storage_path: str) -> str:
        return f"gs://test-bucket/{storage_path}"


class RecordingPubSub:
    def __init__(self) -> None:
        self.published: list[dict[str, Any]] = []

    def publish(self, *, topic: str, event: dict[str, Any]) -> str:
        self.published.append({"topic": topic, "event": event})
        return "msg-1"


class Harness:
    def __init__(self, stt_response: dict[str, Any] | Exception) -> None:
        self.client = FakeFirestoreClient()
        self.storage = FakeStorageClient()
        self.projects = ProjectService(self.client)
        self.jobs = JobService(self.client)
        self.settings = Settings()
        self.assets = AssetService(
            self.client,
            projects=self.projects,
            jobs=self.jobs,
            storage=self.storage,
            settings=self.settings,
        )
        self.transcripts = TranscriptService(self.client, storage=self.storage)
        self.stt = StubStt(stt_response)
        self.pubsub = RecordingPubSub()

    def project(self, primary_language: str = "en") -> str:
        return self.projects.create(
            owner_uid=UID, payload=CreateProject(name="P", primaryLanguage=primary_language)
        ).projectId

    def uploaded_asset(self, project_id: str) -> str:
        session = self.assets.create_upload_session(
            owner_uid=UID,
            project_id=project_id,
            payload=CreateUploadSession(fileName="clip.mp4", contentType="video/mp4", sizeBytes=16),
        )
        self.storage.objects[session.storagePath] = "bytes"
        job = self.assets.complete_upload(
            owner_uid=UID, project_id=project_id, asset_id=session.assetId
        )
        return session.assetId, job.jobId

    def kwargs(self) -> dict[str, Any]:
        return {
            "firestore": self.client,
            "jobs": self.jobs,
            "projects": self.projects,
            "assets": self.assets,
            "transcripts": self.transcripts,
            "stt": self.stt,
            "settings": self.settings,
            "pubsub": self.pubsub,
        }


WORDS = {
    "words": [
        {"word": "Hello", "startMs": 0, "endMs": 300},
        {"word": "world.", "startMs": 300, "endMs": 600},
        {"word": "Lets", "startMs": 600, "endMs": 900},
        {"word": "begin.", "startMs": 900, "endMs": 1200},
    ]
}


async def test_run_transcribe_success_marks_project_ready() -> None:
    h = Harness(WORDS)
    project_id = h.project()
    asset_id, job_id = h.uploaded_asset(project_id)

    transcript_id = await run_transcribe(
        owner_uid=UID, project_id=project_id, job_id=job_id, **h.kwargs()
    )

    assert transcript_id is not None
    assert h.stt.calls and h.stt.calls[0]["language_codes"] == ["auto"]
    job = h.jobs.get(owner_uid=UID, job_id=job_id)
    assert job.status.value == "succeeded"
    project = h.client.docs[f"users/{UID}/projects/{project_id}"]
    assert project["status"] == "ready"
    assert project["activeTranscriptId"] == transcript_id
    asset = h.client.docs[f"users/{UID}/projects/{project_id}/assets/{asset_id}"]
    assert asset["status"] == "ready"
    transcript = h.transcripts.get(owner_uid=UID, project_id=project_id)
    assert [s.text for s in transcript.segments] == ["Hello world.", "Lets begin."]


async def test_run_transcribe_publishes_transcript_ready() -> None:
    h = Harness(WORDS)
    project_id = h.project()
    _, job_id = h.uploaded_asset(project_id)

    await run_transcribe(owner_uid=UID, project_id=project_id, job_id=job_id, **h.kwargs())

    assert len(h.pubsub.published) == 1
    published = h.pubsub.published[0]
    assert published["topic"] == "transcription-events"
    assert published["event"]["type"] == "transcript.ready"
    assert published["event"]["projectId"] == project_id
    assert published["event"]["payload"]["wordCount"] == 4


async def test_run_transcribe_stores_detected_language() -> None:
    h = Harness({"words": WORDS["words"], "language": "hi"})
    project_id = h.project("hi")
    _, job_id = h.uploaded_asset(project_id)

    transcript_id = await run_transcribe(
        owner_uid=UID, project_id=project_id, job_id=job_id, **h.kwargs()
    )

    assert transcript_id is not None
    assert h.stt.calls[0]["language_codes"] == ["auto"]
    transcript = h.transcripts.get(owner_uid=UID, project_id=project_id)
    assert transcript.language == "hi"


async def test_run_transcribe_falls_back_to_project_language() -> None:
    h = Harness({"words": WORDS["words"]})
    project_id = h.project("hi")
    _, job_id = h.uploaded_asset(project_id)

    transcript_id = await run_transcribe(
        owner_uid=UID, project_id=project_id, job_id=job_id, **h.kwargs()
    )

    assert transcript_id is not None
    transcript = h.transcripts.get(owner_uid=UID, project_id=project_id)
    assert transcript.language == "hi-IN"


async def test_run_transcribe_is_idempotent_on_terminal_job() -> None:
    h = Harness(WORDS)
    project_id = h.project()
    _, job_id = h.uploaded_asset(project_id)

    first = await run_transcribe(owner_uid=UID, project_id=project_id, job_id=job_id, **h.kwargs())
    calls_after_first = len(h.stt.calls)
    second = await run_transcribe(owner_uid=UID, project_id=project_id, job_id=job_id, **h.kwargs())
    assert first == second
    assert len(h.stt.calls) == calls_after_first


async def test_run_transcribe_silent_audio_succeeds_with_hint() -> None:
    h = Harness({"words": []})
    project_id = h.project()
    _, job_id = h.uploaded_asset(project_id)

    transcript_id = await run_transcribe(
        owner_uid=UID, project_id=project_id, job_id=job_id, **h.kwargs()
    )

    assert transcript_id is not None
    job = h.jobs.get(owner_uid=UID, job_id=job_id)
    assert job.status.value == "succeeded"
    assert job.progress.message == "Completed — no speech detected"
    transcript = h.transcripts.get(owner_uid=UID, project_id=project_id)
    assert transcript.segments == []


async def test_run_transcribe_missing_asset_id_fails_job() -> None:
    h = Harness(WORDS)
    project_id = h.project()
    job = h.jobs.create(
        owner_uid=UID,
        project_id=project_id,
        job_type=JobType.transcribe,
        idempotency_key="no-asset",
        input={},
    )
    result = await run_transcribe(
        owner_uid=UID, project_id=project_id, job_id=job.jobId, **h.kwargs()
    )
    assert result is None
    assert h.jobs.get(owner_uid=UID, job_id=job.jobId).status.value == "failed"
    assert h.client.docs[f"users/{UID}/projects/{project_id}"]["status"] == "failed"


async def test_run_transcribe_stt_error_fails_job() -> None:
    h = Harness(RuntimeError("boom"))
    project_id = h.project()
    _, job_id = h.uploaded_asset(project_id)
    result = await run_transcribe(owner_uid=UID, project_id=project_id, job_id=job_id, **h.kwargs())
    assert result is None
    job = h.jobs.get(owner_uid=UID, job_id=job_id)
    assert job.status.value == "failed"
    assert job.error is not None
    assert h.client.docs[f"users/{UID}/projects/{project_id}"]["status"] == "failed"


async def test_run_transcribe_unknown_job_returns_none() -> None:
    h = Harness(WORDS)
    project_id = h.project()
    assert (
        await run_transcribe(owner_uid=UID, project_id=project_id, job_id="missing", **h.kwargs())
        is None
    )


def test_uploaded_asset_helper_returns_tuple() -> None:
    h = Harness(WORDS)
    project_id = h.project()
    asset_id, job_id = h.uploaded_asset(project_id)
    assert asset_id and job_id
