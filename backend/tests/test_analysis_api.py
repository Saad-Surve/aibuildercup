"""Analysis API tests (`docs/technical-design/api-design.md` section 9)."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.dependencies import (
    AuthenticatedUser,
    current_user,
    get_analysis_pubsub,
    get_analysis_scheduler,
    get_analysis_service,
)
from app.main import app
from app.schemas.analysis import (
    AnalysisDimension,
    AnalysisRunStatus,
    Finding,
    FindingEvidence,
    HeatmapBin,
    HeatmapColor,
    Severity,
)
from app.schemas.projects import CreateProject
from app.services.analysis_service import AnalysisService
from app.services.heatmap import FindingSummary
from app.services.job_service import JobService
from app.services.project_service import ProjectService
from app.services.transcript_service import TranscriptService
from tests.fakes import FakeFirestoreClient, FakePubSubClient, FakeStorageClient

UID = "uid-1"


class Ctx:
    def __init__(self) -> None:
        self.client = FakeFirestoreClient()
        self.storage = FakeStorageClient()
        self.settings = Settings(max_project_cost_usd=5.0)
        self.projects = ProjectService(self.client)
        self.jobs = JobService(self.client)
        self.transcripts = TranscriptService(self.client, storage=self.storage)
        self.service = AnalysisService(
            self.client, jobs=self.jobs, settings=self.settings
        )
        self.pubsub = FakePubSubClient()
        self.scheduled: list[dict] = []

    def new_project(self, *, with_transcript: bool = True) -> str:
        project_id = self.projects.create(
            owner_uid=UID, payload=CreateProject(name="Video")
        ).projectId
        if with_transcript:
            self.transcripts.save(
                owner_uid=UID,
                project_id=project_id,
                source_asset_id="asset-1",
                language="en-US",
                words=[
                    {"word": "Hello", "startMs": 0, "endMs": 400},
                    {"word": "world.", "startMs": 400, "endMs": 900},
                ],
            )
        return project_id

    def schedule(self, background_tasks, **kwargs) -> None:
        self.scheduled.append(kwargs)

    def start(self, project_id: str, body: dict | None = None) -> dict:
        response = TestClient(app).post(
            f"/api/projects/{project_id}/analysis", json=body or {}
        )
        assert response.status_code == 202, response.text
        return response.json()


@pytest.fixture
def ctx() -> Iterator[Ctx]:
    context = Ctx()
    app.dependency_overrides[current_user] = lambda: AuthenticatedUser(
        uid=UID, email="a@b.c"
    )
    app.dependency_overrides[get_analysis_service] = lambda: context.service
    app.dependency_overrides[get_analysis_scheduler] = lambda: context.schedule
    app.dependency_overrides[get_analysis_pubsub] = lambda: context.pubsub
    app.dependency_overrides[get_settings] = lambda: context.settings
    yield context
    app.dependency_overrides.clear()


# --- POST -------------------------------------------------------------------


def test_post_returns_run_and_job_and_schedules_the_worker(ctx: Ctx) -> None:
    project_id = ctx.new_project()
    body = ctx.start(project_id, {"dimensions": ["conversion_cta"], "platform": "youtube"})

    assert body["status"] == "queued"
    assert body["analysisRunId"]
    assert body["jobId"]
    assert ctx.scheduled == [
        {"owner_uid": UID, "project_id": project_id, "job_id": body["jobId"]}
    ]

    run = TestClient(app).get(
        f"/api/projects/{project_id}/analysis/{body['analysisRunId']}"
    ).json()
    assert run["status"] == "queued"
    assert run["requestedDimensions"][0] == "truth_evidence"
    assert "conversion_cta" in run["requestedDimensions"]
    assert run["promptVersion"] == "reviewers-v1"


def test_post_publishes_analysis_requested(ctx: Ctx) -> None:
    project_id = ctx.new_project()
    body = ctx.start(project_id)

    topics = [topic for topic, _ in ctx.pubsub.published]
    assert topics == ["analysis-events"]
    event = ctx.pubsub.published[0][1]
    assert event["type"] == "analysis.requested"
    assert event["ownerUid"] == UID
    assert event["projectId"] == project_id
    assert event["payload"]["analysisRunId"] == body["analysisRunId"]
    assert event["jobId"] == body["jobId"]


def test_post_without_a_transcript_conflicts(ctx: Ctx) -> None:
    project_id = ctx.new_project(with_transcript=False)
    response = TestClient(app).post(f"/api/projects/{project_id}/analysis", json={})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TRANSCRIPT_NOT_READY"
    assert ctx.scheduled == []


def test_post_is_refused_once_the_cost_cap_is_spent(ctx: Ctx) -> None:
    project_id = ctx.new_project()
    ctx.start(project_id)
    run = ctx.service.list_runs(owner_uid=UID, project_id=project_id)[0]
    ctx.service.finish_run(
        owner_uid=UID,
        project_id=project_id,
        analysis_run_id=run.analysisRunId,
        status=AnalysisRunStatus.ready,
        summary=FindingSummary(),
        cost_usd=5.0,
        completed_dimensions=[],
    )

    response = TestClient(app).post(f"/api/projects/{project_id}/analysis", json={})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "COST_CAP_EXCEEDED"
    assert len(ctx.scheduled) == 1


def test_post_requires_a_bearer_token(ctx: Ctx) -> None:
    project_id = ctx.new_project()
    app.dependency_overrides.clear()
    response = TestClient(app).post(f"/api/projects/{project_id}/analysis", json={})
    assert response.status_code == 401


# --- GET --------------------------------------------------------------------


def test_list_runs_is_newest_first(ctx: Ctx) -> None:
    project_id = ctx.new_project()
    first = ctx.start(project_id)
    second = ctx.start(project_id)

    body = TestClient(app).get(f"/api/projects/{project_id}/analysis").json()
    assert [item["analysisRunId"] for item in body["items"]] == [
        second["analysisRunId"],
        first["analysisRunId"],
    ]


def test_get_reviewers_reports_one_per_core_dimension(ctx: Ctx) -> None:
    project_id = ctx.new_project()
    body = ctx.start(project_id)

    reviewers = TestClient(app).get(
        f"/api/projects/{project_id}/analysis/{body['analysisRunId']}/reviewers"
    ).json()["items"]
    assert [r["dimension"] for r in reviewers] == [
        "truth_evidence",
        "clarity",
        "structure_pacing",
        "legal_safety",
        "cultural_localization",
        "platform_fit",
    ]
    assert all(r["status"] == "queued" for r in reviewers)
    assert all(r["findingCount"] == 0 for r in reviewers)


def test_get_findings_supports_filters(ctx: Ctx) -> None:
    project_id = ctx.new_project()
    body = ctx.start(project_id)
    run_id = body["analysisRunId"]

    ctx.service.save_findings(
        owner_uid=UID,
        project_id=project_id,
        analysis_run_id=run_id,
        findings=[
            Finding(
                findingId="f1",
                dimension=AnalysisDimension.clarity,
                startMs=0,
                endMs=100,
                score=7.0,
                confidence=0.5,
                severity=Severity.low,
                findingType="t",
                evidence=FindingEvidence(quote="q", explanation="e"),
                suggestion="s",
            ),
            Finding(
                findingId="f2",
                dimension=AnalysisDimension.legal_safety,
                startMs=2_000,
                endMs=3_000,
                score=2.0,
                confidence=0.5,
                severity=Severity.critical,
                findingType="t",
                evidence=FindingEvidence(quote="q", explanation="e"),
                suggestion="s",
            ),
        ],
    )

    client = TestClient(app)
    all_items = client.get(f"/api/projects/{project_id}/analysis/{run_id}/findings").json()
    assert [f["findingId"] for f in all_items["items"]] == ["f1", "f2"]

    filtered = client.get(
        f"/api/projects/{project_id}/analysis/{run_id}/findings",
        params={"dimension": "legal_safety", "severity": "critical"},
    ).json()
    assert [f["findingId"] for f in filtered["items"]] == ["f2"]

    windowed = client.get(
        f"/api/projects/{project_id}/analysis/{run_id}/findings",
        params={"startMs": 1_500},
    ).json()
    assert [f["findingId"] for f in windowed["items"]] == ["f2"]


def test_get_heatmap_returns_bins(ctx: Ctx) -> None:
    project_id = ctx.new_project()
    body = ctx.start(project_id)
    run_id = body["analysisRunId"]
    ctx.service.save_bins(
        owner_uid=UID,
        project_id=project_id,
        analysis_run_id=run_id,
        bins=[
            HeatmapBin(
                binId="clarity-0",
                dimension=AnalysisDimension.clarity,
                startMs=0,
                endMs=5_000,
                score=8.5,
                severity=Severity.none,
                color=HeatmapColor.green,
                findingIds=["f1"],
            )
        ],
    )

    body = TestClient(app).get(
        f"/api/projects/{project_id}/analysis/{run_id}/heatmap"
    ).json()
    assert body["bins"][0]["binId"] == "clarity-0"
    assert body["bins"][0]["color"] == "green"
    assert body["bins"][0]["findingIds"] == ["f1"]


def test_unknown_run_is_not_found(ctx: Ctx) -> None:
    project_id = ctx.new_project()
    client = TestClient(app)
    for path in ("", "/reviewers", "/findings", "/heatmap"):
        response = client.get(
            f"/api/projects/{project_id}/analysis/does-not-exist{path}"
        )
        assert response.status_code == 404
