import base64
import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.errors import NotFoundError
from app.schemas.jobs import JobStatus
from app.workers import pubsub_handlers as handlers


def _envelope(payload: dict[str, Any]) -> dict[str, Any]:
    data = base64.b64encode(json.dumps(payload).encode()).decode()
    return {"message": {"data": data, "messageId": "m1"}}


def test_decode_push_envelope_roundtrips() -> None:
    assert handlers.decode_push_envelope(_envelope({"name": "x"})) == {"name": "x"}


def test_decode_push_envelope_rejects_bad_bodies() -> None:
    with pytest.raises(handlers.InvalidPubSubMessage):
        handlers.decode_push_envelope({"message": {}})
    with pytest.raises(handlers.InvalidPubSubMessage):
        handlers.decode_push_envelope({"message": {"data": "not-base64-json"}})
    with pytest.raises(handlers.InvalidPubSubMessage):
        handlers.decode_push_envelope({})


def test_source_object_from_event() -> None:
    assert handlers.source_object_from_event(
        {"name": "users/u1/projects/p1/source/a1.mp4"}
    ) == ("u1", "p1", "a1")
    assert (
        handlers.source_object_from_event(
            {"name": "users/u1/projects/p1/transcripts/v1.json"}
        )
        is None
    )
    assert handlers.source_object_from_event({}) is None


class _FakeAssets:
    def __init__(self, status: JobStatus | Exception) -> None:
        self.status = status
        self.queued: list[tuple[str, str, str]] = []

    def queue_transcription(self, *, owner_uid: str, project_id: str, asset_id: str):
        self.queued.append((owner_uid, project_id, asset_id))
        if isinstance(self.status, Exception):
            raise self.status
        return SimpleNamespace(jobId="job-1", status=self.status)


async def test_handle_video_finalized_runs_when_queued(monkeypatch: pytest.MonkeyPatch) -> None:
    ran: dict[str, Any] = {}

    async def fake_run(**kwargs: Any) -> None:
        ran.update(kwargs)

    monkeypatch.setattr(handlers, "run_transcribe", fake_run)
    assets = _FakeAssets(JobStatus.queued)
    job = await handlers.handle_video_finalized(
        {"name": "users/u1/projects/p1/source/a1.mp4"},
        dependencies={"assets": assets},
    )
    assert job == "job-1"
    assert assets.queued == [("u1", "p1", "a1")]
    assert ran["owner_uid"] == "u1"
    assert ran["job_id"] == "job-1"


async def test_handle_video_finalized_skips_non_queued(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run(**kwargs: Any) -> None:  # pragma: no cover - must not be called
        raise AssertionError("worker should not run")

    monkeypatch.setattr(handlers, "run_transcribe", fake_run)
    assets = _FakeAssets(JobStatus.succeeded)
    job = await handlers.handle_video_finalized(
        {"name": "users/u1/projects/p1/source/a1.mp4"},
        dependencies={"assets": assets},
    )
    assert job is None


async def test_handle_video_finalized_ignores_unknown_asset() -> None:
    assets = _FakeAssets(NotFoundError("Asset not found"))
    job = await handlers.handle_video_finalized(
        {"name": "users/u1/projects/p1/source/a1.mp4"},
        dependencies={"assets": assets},
    )
    assert job is None


async def test_handle_video_finalized_ignores_non_source_object() -> None:
    assets = _FakeAssets(JobStatus.queued)
    job = await handlers.handle_video_finalized(
        {"name": "users/u1/projects/p1/transcripts/v1.json"},
        dependencies={"assets": assets},
    )
    assert job is None
    assert assets.queued == []
