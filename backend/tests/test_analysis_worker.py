"""Analysis worker tests: the full transcript -> findings -> heatmap path."""

from typing import Any

import pytest

from app.config import Settings
from app.providers.base import LlmCompletion, LlmUsage
from app.schemas.analysis import (
    AnalysisDimension,
    AnalysisRequest,
    AnalysisRunStatus,
    ReviewerRunStatus,
)
from app.schemas.jobs import JobStatus, JobType
from app.schemas.projects import CreateProject
from app.services.analysis_service import AnalysisService
from app.services.heatmap import FindingSummary
from app.services.job_service import JobService
from app.services.project_service import ProjectService
from app.services.transcript_service import TranscriptService
from app.services.user_service import UserService
from app.workers.analysis_worker import run_analysis
from tests.fakes import FakeFirestoreClient, FakePubSubClient, FakeStorageClient

UID = "uid-1"


class ScriptedLlm:
    """Answers per dimension, keyed by the dimension's enum value.

    Dispatches on the `(dimension)` marker in the system prompt, which is how the
    real reviewers are labelled.
    """

    def __init__(self, answers: dict[str, dict | Exception]) -> None:
        self.answers = answers
        self.calls: list[dict[str, Any]] = []

    async def complete_json(
        self, *, model, prompt_version, system, user, schema
    ) -> LlmCompletion:
        self.calls.append({"model": model, "system": system, "user": user})
        for dimension, answer in self.answers.items():
            if f"({dimension})" in system:
                if isinstance(answer, Exception):
                    raise answer
                return LlmCompletion(data=answer, usage=LlmUsage(120, 60))
        return LlmCompletion(data={"findings": []}, usage=LlmUsage(120, 60))


def finding(
    segment_id: str = "seg-1",
    *,
    start_ms: int = 0,
    end_ms: int = 900,
    score: float = 8.0,
    severity: str = "none",
) -> dict:
    return {
        "segmentId": segment_id,
        "startMs": start_ms,
        "endMs": end_ms,
        "score": score,
        "confidence": 0.9,
        "severity": severity,
        "findingType": "strength",
        "evidence": {"quote": "Hello", "explanation": "Clear opening."},
        "suggestion": "",
        "citations": [],
    }


class Harness:
    def __init__(self, llm: ScriptedLlm) -> None:
        self.client = FakeFirestoreClient()
        self.storage = FakeStorageClient()
        self.settings = Settings(
            max_reviewer_concurrency=2, llm_input_price_per_mtok=0.75
        )
        self.projects = ProjectService(self.client)
        self.jobs = JobService(self.client)
        self.transcripts = TranscriptService(self.client, storage=self.storage)
        self.users = UserService(self.client, storage=self.storage)
        self.analyses = AnalysisService(
            self.client, jobs=self.jobs, settings=self.settings
        )
        self.pubsub = FakePubSubClient()
        self.llm = llm

    def project(self, *, with_transcript: bool = True) -> str:
        project_id = self.projects.create(
            owner_uid=UID, payload=CreateProject(name="Video")
        ).projectId
        if with_transcript:
            # Four sentence ends -> four segments, with the spans the tests assert on.
            self.transcripts.save(
                owner_uid=UID,
                project_id=project_id,
                source_asset_id="asset-1",
                language="en-US",
                words=[
                    {"word": "Hello", "startMs": 0, "endMs": 200},
                    {"word": "there.", "startMs": 200, "endMs": 400},
                    {"word": "Welcome", "startMs": 400, "endMs": 650},
                    {"word": "aboard.", "startMs": 650, "endMs": 900},
                    {"word": "Let", "startMs": 900, "endMs": 1_050},
                    {"word": "us", "startMs": 1_050, "endMs": 1_150},
                    {"word": "begin.", "startMs": 1_150, "endMs": 1_400},
                    {"word": "Any", "startMs": 1_400, "endMs": 1_600},
                    {"word": "questions?", "startMs": 1_600, "endMs": 2_000},
                ],
            )
        self.client.set_document(
            f"users/{UID}",
            {
                "uid": UID,
                "persona": {
                    "version": 2,
                    "storagePath": f"users/{UID}/profile/persona.md",
                },
            },
        )
        self.storage.upload_text(f"users/{UID}/profile/persona.md", "# Persona\nDirect.")
        return project_id

    def queue(self, project_id: str, dimensions: list[str] | None = None) -> tuple[str, str]:
        run, job = self.analyses.create_run(
            owner_uid=UID,
            project_id=project_id,
            payload=AnalysisRequest(dimensions=dimensions or []),
        )
        return run.analysisRunId, job.jobId

    async def run(
        self, project_id: str, job_id: str, *, max_chunk_chars: int = 36_000
    ) -> str | None:
        return await run_analysis(
            owner_uid=UID,
            project_id=project_id,
            job_id=job_id,
            jobs=self.jobs,
            analyses=self.analyses,
            transcripts=self.transcripts,
            users=self.users,
            storage=self.storage,
            llm=self.llm,
            settings=self.settings,
            pubsub=self.pubsub,
            max_chunk_chars=max_chunk_chars,
        )

    def published_types(self) -> list[str]:
        return [event["type"] for _, event in self.pubsub.published]


# --- happy path -------------------------------------------------------------


async def test_full_run_produces_findings_bins_and_scores() -> None:
    harness = Harness(
        ScriptedLlm(
            {
                "clarity": {"findings": [finding(score=9.0)]},
                "truth_evidence": {"findings": [finding(score=3.0, severity="high")]},
            }
        )
    )
    project_id = harness.project()
    analysis_run_id, job_id = harness.queue(project_id)

    assert await harness.run(project_id, job_id) == analysis_run_id

    run = harness.analyses.get_run(
        owner_uid=UID, project_id=project_id, analysis_run_id=analysis_run_id
    )
    assert run.status is AnalysisRunStatus.ready
    assert run.overallScore is not None
    assert run.scoreByDimension["clarity"] == 9.0
    assert run.scoreByDimension["truth_evidence"] == 3.0
    assert run.findingCounts["high"] == 1
    assert run.findingCounts["none"] == 1
    assert run.costEstimateUsd > 0
    assert run.chunkCount == 1

    findings = harness.analyses.list_findings(
        owner_uid=UID, project_id=project_id, analysis_run_id=analysis_run_id
    )
    assert len(findings) == 2
    assert {f.dimension for f in findings} == {
        AnalysisDimension.clarity,
        AnalysisDimension.truth_evidence,
    }
    # Every finding is stamped with the reviewer that produced it.
    assert all(f.reviewerRunId for f in findings)

    bins = harness.analyses.list_bins(
        owner_uid=UID, project_id=project_id, analysis_run_id=analysis_run_id
    )
    assert bins
    assert all(b.findingIds for b in bins)

    job = harness.jobs.load_for_worker(
        owner_uid=UID, project_id=project_id, job_id=job_id
    )
    assert job["status"] == JobStatus.succeeded.value
    assert job["output"]["analysisRunId"] == analysis_run_id
    assert job["output"]["findingCount"] == 2

    assert harness.published_types().count("reviewer.completed") == 6
    assert harness.published_types()[-1] == "analysis.ready"


async def test_run_records_which_persona_it_used() -> None:
    harness = Harness(ScriptedLlm({}))
    project_id = harness.project()
    analysis_run_id, job_id = harness.queue(project_id)
    await harness.run(project_id, job_id)

    run = harness.analyses.get_run(
        owner_uid=UID, project_id=project_id, analysis_run_id=analysis_run_id
    )
    assert run.personaVersion == 2
    assert run.sourceAssetId == "asset-1"
    # The persona was actually put in front of the reviewers.
    assert any("# Persona" in call["user"] for call in harness.llm.calls)


async def test_reviewers_are_asked_for_the_requested_dimensions_only() -> None:
    harness = Harness(ScriptedLlm({}))
    project_id = harness.project()
    _, job_id = harness.queue(project_id, dimensions=["conversion_cta"])
    await harness.run(project_id, job_id)

    asked = set()
    for call in harness.llm.calls:
        for dimension in AnalysisDimension:
            if f"({dimension.value})" in call["system"]:
                asked.add(dimension.value)
    assert asked == {
        "truth_evidence",
        "clarity",
        "structure_pacing",
        "legal_safety",
        "cultural_localization",
        "platform_fit",
        "conversion_cta",
    }
    assert len(harness.llm.calls) == 7


# --- partial and total failure ---------------------------------------------


async def test_one_failing_reviewer_still_yields_the_others() -> None:
    harness = Harness(
        ScriptedLlm(
            {
                "clarity": {"findings": [finding(score=8.0)]},
                "legal_safety": RuntimeError("model exploded"),
            }
        )
    )
    project_id = harness.project()
    analysis_run_id, job_id = harness.queue(project_id)
    await harness.run(project_id, job_id)

    run = harness.analyses.get_run(
        owner_uid=UID, project_id=project_id, analysis_run_id=analysis_run_id
    )
    assert run.status is AnalysisRunStatus.partial_failure
    assert AnalysisDimension.clarity in run.completedDimensions
    assert AnalysisDimension.legal_safety not in run.completedDimensions

    findings = harness.analyses.list_findings(
        owner_uid=UID, project_id=project_id, analysis_run_id=analysis_run_id
    )
    assert [f.dimension for f in findings] == [AnalysisDimension.clarity]

    reviewers = harness.analyses.get_reviewers(
        owner_uid=UID, project_id=project_id, analysis_run_id=analysis_run_id
    )
    by_dimension = {r.dimension: r for r in reviewers}
    assert by_dimension[AnalysisDimension.clarity].status is ReviewerRunStatus.succeeded
    assert by_dimension[AnalysisDimension.legal_safety].status is ReviewerRunStatus.failed
    assert by_dimension[AnalysisDimension.legal_safety].error is not None

    job = harness.jobs.load_for_worker(
        owner_uid=UID, project_id=project_id, job_id=job_id
    )
    assert job["status"] == JobStatus.succeeded.value


async def test_every_reviewer_failing_fails_the_run_and_the_job() -> None:
    harness = Harness(
        ScriptedLlm(
            {
                dimension.value: RuntimeError("down")
                for dimension in AnalysisDimension
            }
        )
    )
    project_id = harness.project()
    analysis_run_id, job_id = harness.queue(project_id)
    await harness.run(project_id, job_id)

    run = harness.analyses.get_run(
        owner_uid=UID, project_id=project_id, analysis_run_id=analysis_run_id
    )
    assert run.status is AnalysisRunStatus.failed
    assert run.completedDimensions == []
    assert run.error["code"] == "SOME_REVIEWERS_FAILED"

    job = harness.jobs.load_for_worker(
        owner_uid=UID, project_id=project_id, job_id=job_id
    )
    assert job["status"] == JobStatus.failed.value


# --- idempotency and guards -------------------------------------------------


async def test_running_twice_is_a_no_op() -> None:
    harness = Harness(ScriptedLlm({"clarity": {"findings": [finding()]}}))
    project_id = harness.project()
    analysis_run_id, job_id = harness.queue(project_id)

    await harness.run(project_id, job_id)
    calls_after_first = len(harness.llm.calls)
    assert await harness.run(project_id, job_id) == analysis_run_id
    assert len(harness.llm.calls) == calls_after_first


async def test_unknown_job_is_skipped() -> None:
    harness = Harness(ScriptedLlm({}))
    assert await harness.run("p", "nope") is None


async def test_job_without_a_run_id_fails() -> None:
    harness = Harness(ScriptedLlm({}))
    project_id = harness.project()
    job = harness.jobs.create(
        owner_uid=UID,
        project_id=project_id,
        job_type=JobType.analyze,
        idempotency_key="analyze:bare",
    )
    assert await harness.run(project_id, job.jobId) is None
    stored = harness.jobs.load_for_worker(
        owner_uid=UID, project_id=project_id, job_id=job.jobId
    )
    assert stored["status"] == JobStatus.failed.value


async def test_missing_transcript_fails_the_run() -> None:
    harness = Harness(ScriptedLlm({}))
    project_id = harness.project()
    analysis_run_id, job_id = harness.queue(project_id)
    # Simulate the transcript vanishing after the run was created.
    harness.client.delete_document_tree(
        f"users/{UID}/projects/{project_id}/transcripts"
    )

    assert await harness.run(project_id, job_id) is None
    run = harness.analyses.get_run(
        owner_uid=UID, project_id=project_id, analysis_run_id=analysis_run_id
    )
    assert run.status is AnalysisRunStatus.failed
    assert run.error["code"] == "TRANSCRIPT_NOT_FOUND"


async def test_empty_transcript_fails_the_run() -> None:
    harness = Harness(ScriptedLlm({}))
    project_id = harness.projects.create(
        owner_uid=UID, payload=CreateProject(name="V")
    ).projectId
    transcript_id = harness.transcripts.save(
        owner_uid=UID,
        project_id=project_id,
        source_asset_id="asset-1",
        language="en-US",
        words=[],
    )
    harness.client.set_document(f"users/{UID}", {"uid": UID})
    analysis_run_id, job_id = harness.queue(project_id)

    assert await harness.run(project_id, job_id) is None
    run = harness.analyses.get_run(
        owner_uid=UID, project_id=project_id, analysis_run_id=analysis_run_id
    )
    assert run.status is AnalysisRunStatus.failed
    assert run.error["code"] == "EMPTY_TRANSCRIPT"
    assert transcript_id  # the empty transcript still exists


async def test_chunked_reviewers_do_not_duplicate_findings() -> None:
    # A greedy reviewer reports on every segment it can see, including the ones
    # shown as context. Forcing one segment per chunk makes every call report all
    # four; only the owning chunk may keep each one, so the run ends with exactly
    # four findings rather than sixteen.
    harness = Harness(
        ScriptedLlm(
            {
                "clarity": {
                    "findings": [
                        finding(start_ms=0, end_ms=400),
                        finding(start_ms=400, end_ms=900),
                        finding(start_ms=900, end_ms=1_400),
                        finding(start_ms=1_400, end_ms=2_000),
                    ]
                }
            }
        )
    )
    project_id = harness.project()
    analysis_run_id, job_id = harness.queue(project_id, dimensions=["clarity"])
    await harness.run(project_id, job_id, max_chunk_chars=1)

    run = harness.analyses.get_run(
        owner_uid=UID, project_id=project_id, analysis_run_id=analysis_run_id
    )
    assert run.chunkCount == 4

    clarity_calls = [c for c in harness.llm.calls if "(clarity)" in c["system"]]
    assert len(clarity_calls) == 4

    findings = harness.analyses.list_findings(
        owner_uid=UID,
        project_id=project_id,
        analysis_run_id=analysis_run_id,
        dimension=AnalysisDimension.clarity,
    )
    assert [(f.startMs, f.endMs) for f in findings] == [
        (0, 400),
        (400, 900),
        (900, 1_400),
        (1_400, 2_000),
    ]


# --- summary helper used by the failure paths -------------------------------


def test_finding_summary_is_empty_but_shaped() -> None:
    summary = FindingSummary()
    assert summary.counts == {}
    assert summary.overall_score is None


@pytest.mark.parametrize(
    "dimensions",
    [[], ["audience_fit"], ["brand_voice", "engagement_retention", "emotional_impact"]],
)
async def test_extra_dimensions_run(dimensions: list[str]) -> None:
    harness = Harness(ScriptedLlm({}))
    project_id = harness.project()
    analysis_run_id, job_id = harness.queue(project_id, dimensions=dimensions)
    await harness.run(project_id, job_id)

    run = harness.analyses.get_run(
        owner_uid=UID, project_id=project_id, analysis_run_id=analysis_run_id
    )
    assert run.status is AnalysisRunStatus.ready
    assert len(run.completedDimensions) == 6 + len(dimensions)
