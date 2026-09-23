from datetime import UTC, datetime

import pytest

from app.errors import ConflictError, NotFoundError
from app.schemas.jobs import JobStatus, JobType
from app.services.job_service import JobService
from tests.fakes import FakeFirestoreClient

UID = "uid-1"


def make_service() -> tuple[JobService, FakeFirestoreClient]:
    client = FakeFirestoreClient()
    return JobService(client), client


def _create(service: JobService, key: str = "key-1"):
    return service.create(
        owner_uid=UID,
        project_id="p1",
        job_type=JobType.transcribe,
        idempotency_key=key,
        input={"assetId": "a1"},
    )


def test_create_persists_queued_job() -> None:
    service, client = make_service()
    job = _create(service)

    assert job.status == JobStatus.queued
    stored = client.docs[f"users/{UID}/projects/p1/jobs/{job.jobId}"]
    assert stored["ownerUid"] == UID
    assert stored["jobId"] == job.jobId
    assert stored["type"] == "transcribe"
    assert stored["progress"]["currentStep"] == "queued"


def test_create_is_idempotent_on_key() -> None:
    service, client = make_service()
    first = _create(service)
    second = _create(service)
    assert first.jobId == second.jobId
    assert len([key for key in client.docs if "/jobs/" in key]) == 1


def test_get_returns_owned_job() -> None:
    service, _ = make_service()
    job = _create(service)
    assert service.get(owner_uid=UID, job_id=job.jobId).jobId == job.jobId


def test_get_missing_job_raises_not_found() -> None:
    service, _ = make_service()
    with pytest.raises(NotFoundError):
        service.get(owner_uid=UID, job_id="missing")


def test_get_rejects_job_owned_by_someone_else() -> None:
    service, client = make_service()
    now = datetime.now(UTC)
    client.set_document(
        "users/other/projects/p1/jobs/j1",
        {
            "jobId": "j1",
            "ownerUid": "other",
            "type": "transcribe",
            "status": "queued",
            "progress": {},
            "createdAt": now,
            "updatedAt": now,
        },
    )
    with pytest.raises(NotFoundError):
        service.get(owner_uid=UID, job_id="j1")


def test_cancel_sets_cancelled_for_queued_job() -> None:
    service, _ = make_service()
    job = _create(service)
    cancelled = service.cancel(owner_uid=UID, job_id=job.jobId)
    assert cancelled.status == JobStatus.cancelled
    assert service.get(owner_uid=UID, job_id=job.jobId).status == JobStatus.cancelled


def test_cancel_terminal_job_conflicts() -> None:
    service, _ = make_service()
    job = _create(service)
    service.cancel(owner_uid=UID, job_id=job.jobId)
    with pytest.raises(ConflictError):
        service.cancel(owner_uid=UID, job_id=job.jobId)


def test_cancel_unknown_job_raises_not_found() -> None:
    service, _ = make_service()
    with pytest.raises(NotFoundError):
        service.cancel(owner_uid=UID, job_id="missing")


def test_latest_for_project_returns_newest_then_none() -> None:
    service, _ = make_service()
    assert service.latest_for_project(owner_uid=UID, project_id="p1") is None
    job = _create(service)
    latest = service.latest_for_project(owner_uid=UID, project_id="p1")
    assert latest is not None and latest.jobId == job.jobId
