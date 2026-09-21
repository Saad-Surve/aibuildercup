from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.dependencies import AuthenticatedUser, current_user, get_job_service
from app.main import app
from app.schemas.jobs import JobType
from app.services.job_service import JobService
from tests.fakes import FakeFirestoreClient

UID = "uid-1"


@pytest.fixture
def service() -> Iterator[JobService]:
    job_service = JobService(FakeFirestoreClient())
    app.dependency_overrides[current_user] = lambda: AuthenticatedUser(
        uid=UID, email="a@b.c"
    )
    app.dependency_overrides[get_job_service] = lambda: job_service
    yield job_service
    app.dependency_overrides.clear()


def test_get_job(service: JobService) -> None:
    job = service.create(
        owner_uid=UID,
        project_id="p1",
        job_type=JobType.transcribe,
        idempotency_key="k",
    )
    response = TestClient(app).get(f"/api/jobs/{job.jobId}")
    assert response.status_code == 200
    body = response.json()
    assert body["jobId"] == job.jobId
    assert body["status"] == "queued"
    assert body["progress"]["step"] == "queued"


def test_get_missing_job_envelope(service: JobService) -> None:
    response = TestClient(app).get("/api/jobs/missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
