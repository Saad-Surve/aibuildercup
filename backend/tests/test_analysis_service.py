"""AnalysisService tests: run creation, queries, and worker writes."""

from datetime import UTC, datetime

import pytest

from app.agents.analysis_coordinator import DimensionOutcome
from app.config import Settings
from app.errors import ConflictError, NotFoundError
from app.providers.base import LlmUsage
from app.schemas.analysis import (
    CORE_DIMENSIONS,
    AnalysisDimension,
    AnalysisRequest,
    AnalysisRunStatus,
    Finding,
    FindingEvidence,
    HeatmapBin,
    HeatmapColor,
    ReviewerRunStatus,
    Severity,
)
from app.schemas.jobs import JobType
from app.schemas.projects import CreateProject
from app.services.analysis_service import (
    AnalysisCapExceeded,
    AnalysisService,
    ensure_within_budget,
)
from app.services.heatmap import FindingSummary
from app.services.job_service import JobService
from app.services.project_service import ProjectService
from app.services.transcript_service import TranscriptService
from tests.fakes import FakeFirestoreClient, FakeStorageClient

UID = "uid-1"
OTHER_UID = "uid-2"

WORDS = [
    {"word": "Hello", "startMs": 0, "endMs": 400},
    {"word": "world.", "startMs": 400, "endMs": 900},
]


class Harness:
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

    def project(self, *, uid: str = UID, with_transcript: bool = True) -> str:
        project_id = self.projects.create(
            owner_uid=uid, payload=CreateProject(name="P")
        ).projectId
        if with_transcript:
            self.transcripts.save(
                owner_uid=uid,
                project_id=project_id,
                source_asset_id="asset-1",
                language="en-US",
                words=WORDS,
            )
        self.client.set_document(
            f"users/{uid}",
            {
                "uid": uid,
                "persona": {"version": 3, "storagePath": f"users/{uid}/profile/persona.md"},
            },
        )
        return project_id

    def new_run(self, project_id: str, **overrides: object):
        payload = AnalysisRequest(**overrides)  # type: ignore[arg-type]
        return self.service.create_run(
            owner_uid=UID, project_id=project_id, payload=payload
        )


def make_finding(
    finding_id: str,
    *,
    dimension: AnalysisDimension = AnalysisDimension.clarity,
    start_ms: int = 0,
    end_ms: int = 100,
    severity: Severity = Severity.medium,
) -> Finding:
    return Finding(
        findingId=finding_id,
        dimension=dimension,
        reviewerRunId="rev-1",
        segmentId="seg-1",
        startMs=start_ms,
        endMs=end_ms,
        score=7.0,
        confidence=0.5,
        severity=severity,
        findingType="t",
        evidence=FindingEvidence(quote="q", explanation="e"),
        suggestion="s",
    )


# --- create_run -------------------------------------------------------------


def test_create_run_resolves_transcript_asset_and_persona() -> None:
    harness = Harness()
    project_id = harness.project()
    run, job = harness.new_run(project_id)

    assert run.status is AnalysisRunStatus.queued
    assert run.transcriptId
    assert run.sourceAssetId == "asset-1"
    assert run.personaVersion == 3
    assert run.jobId == job.jobId
    assert job.type is JobType.analyze
    assert run.promptVersion == "reviewers-v1"
    assert run.modelConfigVersion == "analysis-v1"
    assert run.fanoutStrategy == "two_tier"


def test_create_run_always_includes_the_core_dimensions() -> None:
    harness = Harness()
    project_id = harness.project()
    run, _ = harness.new_run(project_id, dimensions=["conversion_cta"])

    assert run.requestedDimensions[: len(CORE_DIMENSIONS)] == list(CORE_DIMENSIONS)
    assert AnalysisDimension.conversion_cta in run.requestedDimensions
    assert len(run.requestedDimensions) == len(CORE_DIMENSIONS) + 1


def test_create_run_writes_one_queued_reviewer_per_dimension() -> None:
    harness = Harness()
    project_id = harness.project()
    run, _ = harness.new_run(project_id)

    reviewers = harness.service.get_reviewers(
        owner_uid=UID, project_id=project_id, analysis_run_id=run.analysisRunId
    )
    assert len(reviewers) == len(CORE_DIMENSIONS)
    assert all(r.status is ReviewerRunStatus.queued for r in reviewers)
    assert [r.dimension for r in reviewers] == list(CORE_DIMENSIONS)

    # The ids stored on the run are the ones the reviewer documents use.
    stored = harness.client.get_document(
        f"users/{UID}/projects/{project_id}/analysisRuns/{run.analysisRunId}"
    )
    assert set(stored["reviewerRunIds"].values()) == {r.reviewerRunId for r in reviewers}


def test_create_run_without_a_transcript_conflicts() -> None:
    harness = Harness()
    project_id = harness.project(with_transcript=False)
    with pytest.raises(ConflictError) as excinfo:
        harness.new_run(project_id)
    assert excinfo.value.code == "TRANSCRIPT_NOT_READY"


def test_create_run_on_a_missing_project_is_not_found() -> None:
    harness = Harness()
    with pytest.raises(NotFoundError):
        harness.service.create_run(
            owner_uid=UID, project_id="nope", payload=AnalysisRequest()
        )


def test_create_run_skips_the_persona_version_when_there_is_no_user() -> None:
    harness = Harness()
    project_id = harness.project()
    harness.client.delete_document(f"users/{UID}")
    run, _ = harness.new_run(project_id)
    assert run.personaVersion is None


# --- reads ------------------------------------------------------------------


def test_list_runs_is_newest_first() -> None:
    harness = Harness()
    project_id = harness.project()
    first, _ = harness.new_run(project_id)
    second, _ = harness.new_run(project_id)

    runs = harness.service.list_runs(owner_uid=UID, project_id=project_id)
    assert [r.analysisRunId for r in runs] == [second.analysisRunId, first.analysisRunId]


def test_get_run_rejects_another_users_run() -> None:
    harness = Harness()
    project_id = harness.project()
    run, _ = harness.new_run(project_id)
    with pytest.raises(NotFoundError):
        harness.service.get_run(
            owner_uid=OTHER_UID,
            project_id=project_id,
            analysis_run_id=run.analysisRunId,
        )


def test_list_findings_filters_and_sorts() -> None:
    harness = Harness()
    project_id = harness.project()
    run, _ = harness.new_run(project_id)
    findings = [
        make_finding("f1", start_ms=0, end_ms=100, severity=Severity.low),
        make_finding("f2", start_ms=2_000, end_ms=3_000, severity=Severity.critical),
        make_finding(
            "f3",
            dimension=AnalysisDimension.legal_safety,
            start_ms=2_500,
            end_ms=4_000,
            severity=Severity.high,
        ),
    ]
    harness.service.save_findings(
        owner_uid=UID,
        project_id=project_id,
        analysis_run_id=run.analysisRunId,
        findings=findings,
    )

    def ids(**kwargs):
        return [
            f.findingId
            for f in harness.service.list_findings(
                owner_uid=UID,
                project_id=project_id,
                analysis_run_id=run.analysisRunId,
                **kwargs,
            )
        ]

    assert ids() == ["f1", "f2", "f3"]
    assert ids(dimension=AnalysisDimension.clarity) == ["f1", "f2"]
    assert ids(severity=Severity.critical) == ["f2"]
    # Overlap semantics: a window touches findings that cross its edges.
    assert ids(start_ms=1_500) == ["f2", "f3"]
    assert ids(end_ms=2_400) == ["f1", "f2"]
    assert ids(start_ms=1_500, end_ms=2_400) == ["f2"]
    assert ids(start_ms=0, end_ms=50) == ["f1"]


def test_list_bins_is_ordered_by_dimension_then_time() -> None:
    harness = Harness()
    project_id = harness.project()
    run, _ = harness.new_run(project_id)
    bins = [
        HeatmapBin(
            binId="clarity-5000",
            dimension=AnalysisDimension.clarity,
            startMs=5_000,
            endMs=10_000,
            score=7.0,
            severity=Severity.low,
            color=HeatmapColor.yellow,
            findingIds=["f1"],
        ),
        HeatmapBin(
            binId="clarity-0",
            dimension=AnalysisDimension.clarity,
            startMs=0,
            endMs=5_000,
            score=9.0,
            severity=Severity.none,
            color=HeatmapColor.green,
            findingIds=[],
        ),
        HeatmapBin(
            binId="truth_evidence-0",
            dimension=AnalysisDimension.truth_evidence,
            startMs=0,
            endMs=5_000,
            score=2.0,
            severity=Severity.critical,
            color=HeatmapColor.red,
            findingIds=["f2"],
        ),
    ]
    harness.service.save_bins(
        owner_uid=UID,
        project_id=project_id,
        analysis_run_id=run.analysisRunId,
        bins=bins,
    )

    listed = harness.service.list_bins(
        owner_uid=UID, project_id=project_id, analysis_run_id=run.analysisRunId
    )
    assert [b.binId for b in listed] == ["truth_evidence-0", "clarity-0", "clarity-5000"]
    assert listed[0].color is HeatmapColor.red
    assert listed[1].findingIds == []


def test_spent_usd_sums_the_runs() -> None:
    harness = Harness()
    project_id = harness.project()
    assert harness.service.spent_usd(owner_uid=UID, project_id=project_id) == 0.0

    for _ in range(2):
        run, _ = harness.new_run(project_id)
        harness.service.finish_run(
            owner_uid=UID,
            project_id=project_id,
            analysis_run_id=run.analysisRunId,
            status=AnalysisRunStatus.ready,
            summary=FindingSummary(),
            cost_usd=0.25,
            completed_dimensions=[],
        )
    assert harness.service.spent_usd(owner_uid=UID, project_id=project_id) == 0.5


# --- worker writes ----------------------------------------------------------


def test_save_reviewer_outcome_overwrites_the_placeholder() -> None:
    harness = Harness()
    project_id = harness.project()
    run, _ = harness.new_run(project_id)
    reviewer_run_id = harness.client.get_document(
        f"users/{UID}/projects/{project_id}/analysisRuns/{run.analysisRunId}"
    )["reviewerRunIds"]["clarity"]

    outcome = DimensionOutcome(
        dimension=AnalysisDimension.clarity,
        reviewer_run_id=reviewer_run_id,
        status=ReviewerRunStatus.succeeded,
        findings=[make_finding("f1")],
        usage=LlmUsage(100, 50),
        model="gemini-flash-latest",
        input_segment_count=12,
        duration_ms=8_200,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    saved = harness.service.save_reviewer_outcome(
        owner_uid=UID,
        project_id=project_id,
        analysis_run_id=run.analysisRunId,
        outcome=outcome,
    )

    assert saved.status is ReviewerRunStatus.succeeded
    assert saved.findingCount == 1
    assert saved.tokenUsage.input == 100
    assert saved.tokenUsage.output == 50
    assert saved.model == "gemini-flash-latest"
    assert saved.durationMs == 8_200
    # Priced from the settings table, not a guess.
    expected = round(
        (
            100 * harness.settings.llm_input_price_per_mtok
            + 50 * harness.settings.llm_output_price_per_mtok
        )
        / 1_000_000,
        6,
    )
    assert saved.costEstimateUsd == expected

    # Still exactly one reviewer document - no orphaned placeholder left behind.
    reviewers = harness.service.get_reviewers(
        owner_uid=UID, project_id=project_id, analysis_run_id=run.analysisRunId
    )
    assert len(reviewers) == len(CORE_DIMENSIONS)
    assert reviewers[1].reviewerRunId == reviewer_run_id


def test_save_reviewer_outcome_for_an_unknown_reviewer_is_not_found() -> None:
    harness = Harness()
    project_id = harness.project()
    run, _ = harness.new_run(project_id)
    with pytest.raises(NotFoundError):
        harness.service.save_reviewer_outcome(
            owner_uid=UID,
            project_id=project_id,
            analysis_run_id=run.analysisRunId,
            outcome=DimensionOutcome(
                dimension=AnalysisDimension.clarity,
                reviewer_run_id="not-a-real-id",
                status=ReviewerRunStatus.succeeded,
            ),
        )


def test_finish_run_records_the_summary() -> None:
    harness = Harness()
    project_id = harness.project()
    run, _ = harness.new_run(project_id)

    summary = FindingSummary(
        counts={"none": 1, "low": 2, "medium": 0, "high": 0, "critical": 0},
        score_by_dimension={"clarity": 7.5},
        overall_score=7.5,
    )
    finished = harness.service.finish_run(
        owner_uid=UID,
        project_id=project_id,
        analysis_run_id=run.analysisRunId,
        status=AnalysisRunStatus.partial_failure,
        summary=summary,
        cost_usd=0.42,
        completed_dimensions=[AnalysisDimension.clarity],
        error={"code": "SOME_REVIEWERS_FAILED", "message": "1 reviewer(s) failed."},
    )

    assert finished.status is AnalysisRunStatus.partial_failure
    assert finished.overallScore == 7.5
    assert finished.scoreByDimension == {"clarity": 7.5}
    assert finished.findingCounts["low"] == 2
    assert finished.costEstimateUsd == 0.42
    assert finished.completedDimensions == [AnalysisDimension.clarity]
    assert finished.error["code"] == "SOME_REVIEWERS_FAILED"


def test_worker_writes_reject_another_user() -> None:
    harness = Harness()
    project_id = harness.project()
    run, _ = harness.new_run(project_id)
    with pytest.raises(NotFoundError):
        harness.service.mark_running(
            owner_uid=OTHER_UID,
            project_id=project_id,
            analysis_run_id=run.analysisRunId,
            chunk_count=1,
        )


def test_mark_running_sets_the_chunk_count() -> None:
    harness = Harness()
    project_id = harness.project()
    run, _ = harness.new_run(project_id)
    harness.service.mark_running(
        owner_uid=UID,
        project_id=project_id,
        analysis_run_id=run.analysisRunId,
        chunk_count=3,
    )
    updated = harness.service.get_run(
        owner_uid=UID, project_id=project_id, analysis_run_id=run.analysisRunId
    )
    assert updated.status is AnalysisRunStatus.running
    assert updated.chunkCount == 3


# --- budget -----------------------------------------------------------------


def test_ensure_within_budget_allows_spend_under_the_cap() -> None:
    ensure_within_budget(4.99, max_project_cost_usd=5.0)


def test_ensure_within_budget_blocks_once_the_cap_is_hit() -> None:
    with pytest.raises(AnalysisCapExceeded) as excinfo:
        ensure_within_budget(5.0, max_project_cost_usd=5.0)
    assert excinfo.value.status_code == 409
    assert excinfo.value.code == "COST_CAP_EXCEEDED"
    assert excinfo.value.details["spentUsd"] == 5.0
