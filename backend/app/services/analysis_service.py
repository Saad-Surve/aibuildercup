"""Analysis run persistence: runs, reviewer status, findings, and heatmap bins.

Documents live at `users/{uid}/projects/{projectId}/analysisRuns/{analysisRunId}` and
its `reviewers` / `findings` / `heatmapBins` subcollections (`contracts/firestore.md`),
so the existing recursive project delete covers everything here.

Findings and bins for one run are a small bounded set (hundreds at most), so listing
them queries the subcollection and filters in Python. That keeps the API free of
composite Firestore indexes for `dimension == ? AND startMs >= ?` without any
measurable cost at this scale.
"""

import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.agents.analysis_coordinator import DimensionOutcome
from app.agents.reviewer_base import MODEL_CONFIG_VERSION, REVIEWER_PROMPT_VERSION
from app.config import Settings
from app.errors import ConflictError, NotFoundError
from app.realtime.events import (
    emit_analysis_progress,
    emit_analysis_ready,
    has_subscribers,
)
from app.schemas.analysis import (
    AnalysisDimension,
    AnalysisRequest,
    AnalysisRun,
    AnalysisRunStatus,
    Finding,
    FindingEvidence,
    HeatmapBin,
    ReviewerGroundingSource,
    ReviewerRun,
    ReviewerRunStatus,
    ReviewerToolCall,
    Severity,
    TokenUsage,
    resolve_dimensions,
)
from app.schemas.jobs import Job, JobType
from app.services.cost import estimate_cost_usd
from app.services.firestore_service import (
    FirestoreClient,
    analysis_findings_collection_path,
    analysis_reviewers_collection_path,
    analysis_run_path,
    analysis_runs_collection_path,
    finding_path,
    heatmap_bin_path,
    heatmap_bins_collection_path,
    project_path,
    reviewer_run_path,
    transcript_path,
    user_path,
)
from app.services.heatmap import FindingSummary
from app.services.job_service import JobService

logger = logging.getLogger(__name__)

_LIST_LIMIT = 2000


def is_owner(document: dict[str, Any], owner_uid: str) -> bool:
    return document.get("ownerUid") == owner_uid


def _to_analysis_run(analysis_run_id: str, data: dict[str, Any]) -> AnalysisRun:
    return AnalysisRun(
        analysisRunId=analysis_run_id,
        jobId=data.get("jobId", ""),
        status=AnalysisRunStatus(data.get("status", AnalysisRunStatus.queued.value)),
        transcriptId=data.get("transcriptId", ""),
        sourceAssetId=data.get("sourceAssetId"),
        personaVersion=data.get("personaVersion"),
        fanoutStrategy=data.get("fanoutStrategy", "two_tier"),
        chunkCount=int(data.get("chunkCount", 0)),
        requestedDimensions=[
            AnalysisDimension(value) for value in data.get("requestedDimensions", [])
        ],
        completedDimensions=[
            AnalysisDimension(value) for value in data.get("completedDimensions", [])
        ],
        overallScore=data.get("overallScore"),
        scoreByDimension=dict(data.get("scoreByDimension") or {}),
        findingCounts=dict(data.get("findingCounts") or {}),
        modelConfigVersion=data.get("modelConfigVersion", ""),
        promptVersion=data.get("promptVersion", ""),
        costEstimateUsd=float(data.get("costEstimateUsd", 0.0)),
        error=data.get("error"),
        createdAt=data["createdAt"],
        updatedAt=data["updatedAt"],
    )


def _to_reviewer_run(reviewer_run_id: str, data: dict[str, Any]) -> ReviewerRun:
    usage = data.get("tokenUsage") or {}
    return ReviewerRun(
        reviewerRunId=reviewer_run_id,
        dimension=AnalysisDimension(data["dimension"]),
        status=ReviewerRunStatus(data.get("status", ReviewerRunStatus.queued.value)),
        findingCount=int(data.get("findingCount", 0)),
        costEstimateUsd=float(data.get("costEstimateUsd", 0.0)),
        durationMs=int(data.get("durationMs", 0)),
        model=data.get("model"),
        inputSegmentCount=int(data.get("inputSegmentCount", 0)),
        toolCalls=[
            ReviewerToolCall(
                tool=str(entry.get("tool") or ""),
                timestampMs=int(entry.get("timestampMs") or 0),
                label=str(entry.get("label") or ""),
                mimeType=str(entry.get("mimeType") or ""),
                contentPath=str(entry.get("contentPath") or ""),
                ok=bool(entry.get("ok", True)),
            )
            for entry in (data.get("toolCalls") or [])
            if isinstance(entry, dict)
        ],
        groundingQueries=[
            str(query) for query in (data.get("groundingQueries") or []) if query
        ],
        groundingSources=[
            ReviewerGroundingSource(
                title=str(entry.get("title") or ""),
                url=str(entry.get("url") or ""),
            )
            for entry in (data.get("groundingSources") or [])
            if isinstance(entry, dict)
        ],
        groundingSearchSuggestions=str(data.get("groundingSearchSuggestions") or ""),
        tokenUsage=TokenUsage(
            input=int(usage.get("input", 0)),
            output=int(usage.get("output", 0)),
        ),
        error=data.get("error"),
        startedAt=data.get("startedAt"),
        finishedAt=data.get("finishedAt"),
    )


def _to_finding(finding_id: str, data: dict[str, Any]) -> Finding:
    raw_evidence = data.get("evidence") or {}
    if not isinstance(raw_evidence, dict):
        raw_evidence = {}
    # Legacy runs stored a 0-10 float score and an `explanation` field; clamp and
    # rename on read so old runs still render instead of 500ing.
    raw_score = data.get("score", 1)
    try:
        score = max(1, min(5, int(round(float(raw_score)))))
    except (TypeError, ValueError):
        score = 1
    return Finding(
        findingId=finding_id,
        dimension=AnalysisDimension(data["dimension"]),
        reviewerRunId=data.get("reviewerRunId"),
        segmentId=data.get("segmentId"),
        startMs=int(data.get("startMs", 0)),
        endMs=int(data.get("endMs", 0)),
        score=score,
        confidence=float(data.get("confidence", 0.0)),
        severity=Severity(data.get("severity", Severity.none.value)),
        findingType=data.get("findingType", ""),
        evidence=FindingEvidence(
            quote=str(raw_evidence.get("quote", "")),
            critique_and_reasoning=str(
                raw_evidence.get("critique_and_reasoning")
                or raw_evidence.get("explanation")
                or ""
            ),
        ),
        suggestion=data.get("suggestion", ""),
        citations=list(data.get("citations") or []),
    )


def _to_heatmap_bin(bin_id: str, data: dict[str, Any]) -> HeatmapBin:
    return HeatmapBin(
        binId=data.get("binId", bin_id),
        dimension=AnalysisDimension(data["dimension"]),
        startMs=int(data.get("startMs", 0)),
        endMs=int(data.get("endMs", 0)),
        score=float(data.get("score", 0.0)),
        severity=Severity(data.get("severity", Severity.none.value)),
        color=data.get("color", "green"),
        findingIds=list(data.get("findingIds") or []),
    )


def _dimension_order(value: str) -> int:
    try:
        return list(AnalysisDimension).index(AnalysisDimension(value))
    except ValueError:
        return len(AnalysisDimension)


class AnalysisCapExceeded(ConflictError):
    """Raised when a project has already spent its analysis cost cap."""

    code = "COST_CAP_EXCEEDED"


def ensure_within_budget(spent_usd: float, *, max_project_cost_usd: float) -> None:
    if spent_usd >= max_project_cost_usd:
        raise AnalysisCapExceeded(
            "This project has used its analysis budget. Raise max_project_cost_usd to "
            "allow more runs.",
            details={"spentUsd": spent_usd, "maxProjectCostUsd": max_project_cost_usd},
        )


class AnalysisService:
    def __init__(
        self,
        client: FirestoreClient,
        *,
        jobs: JobService,
        settings: Settings,
    ) -> None:
        self.client = client
        self.jobs = jobs
        self.settings = settings

    # -------------------------------------------------------------- creation

    def create_run(
        self,
        *,
        owner_uid: str,
        project_id: str,
        payload: AnalysisRequest,
    ) -> tuple[AnalysisRun, Job]:
        """Create the run, its queued reviewer records, and the job that drives it.

        Everything the run needs to be reproducible - which transcript, which source
        asset, which persona version - is resolved and recorded here, so a later
        re-upload cannot silently retarget an in-flight analysis.

        The reviewer run ids are generated here so the worker writes results onto the
        placeholders instead of leaving orphaned documents behind.
        """
        project = self.client.get_document(project_path(owner_uid, project_id))
        if project is None or not is_owner(project, owner_uid):
            raise NotFoundError("Project not found", details={"projectId": project_id})
        transcript_id = project.get("activeTranscriptId")
        if not transcript_id:
            raise ConflictError(
                "This project has no transcript to analyse yet.",
                code="TRANSCRIPT_NOT_READY",
                details={"projectId": project_id},
            )
        transcript = self.client.get_document(
            transcript_path(owner_uid, project_id, transcript_id)
        )
        if transcript is None or not is_owner(transcript, owner_uid):
            raise NotFoundError(
                "Transcript not found", details={"transcriptId": transcript_id}
            )
        persona_version = self._persona_version(owner_uid)

        analysis_run_id = uuid4().hex
        dimensions = resolve_dimensions(payload.dimensions)
        job = self.jobs.create(
            owner_uid=owner_uid,
            project_id=project_id,
            job_type=JobType.analyze,
            idempotency_key=f"analyze:{analysis_run_id}",
            input={
                "analysisRunId": analysis_run_id,
                "dimensions": [dimension.value for dimension in dimensions],
                "platform": payload.platform,
                "includeVisualReview": payload.includeVisualReview,
            },
        )
        now = datetime.now(UTC)
        reviewer_run_ids = {dimension.value: uuid4().hex for dimension in dimensions}
        document: dict[str, Any] = {
            "ownerUid": owner_uid,
            "projectId": project_id,
            "jobId": job.jobId,
            "transcriptId": transcript_id,
            "sourceAssetId": transcript.get("sourceAssetId"),
            "personaVersion": persona_version,
            "status": AnalysisRunStatus.queued.value,
            "fanoutStrategy": "two_tier",
            "chunkCount": 0,
            "includeVisualReview": payload.includeVisualReview,
            "platform": payload.platform,
            "transcriptVersion": payload.transcriptVersion,
            "requestedDimensions": [dimension.value for dimension in dimensions],
            "completedDimensions": [],
            "reviewerRunIds": reviewer_run_ids,
            "overallScore": None,
            "scoreByDimension": {},
            "findingCounts": {},
            "modelConfigVersion": MODEL_CONFIG_VERSION,
            "promptVersion": REVIEWER_PROMPT_VERSION,
            "costEstimateUsd": 0.0,
            "error": None,
            "createdAt": now,
            "updatedAt": now,
        }
        self.client.set_document(
            analysis_run_path(owner_uid, project_id, analysis_run_id), document
        )
        for dimension in dimensions:
            self.client.set_document(
                reviewer_run_path(
                    owner_uid, project_id, analysis_run_id, reviewer_run_ids[dimension.value]
                ),
                {
                    "ownerUid": owner_uid,
                    "dimension": dimension.value,
                    "status": ReviewerRunStatus.queued.value,
                    "findingCount": 0,
                    "costEstimateUsd": 0.0,
                    "durationMs": 0,
                    "model": None,
                    "inputSegmentCount": 0,
                    "tokenUsage": {"input": 0, "output": 0},
                    "error": None,
                    "startedAt": None,
                    "finishedAt": None,
                    "createdAt": now,
                    "updatedAt": now,
                },
            )
        return _to_analysis_run(analysis_run_id, document), job

    def load_run_document(
        self, *, owner_uid: str, project_id: str, analysis_run_id: str
    ) -> dict[str, Any]:
        """Raw run document for the worker, which needs `reviewerRunIds` and friends."""
        data = self.client.get_document(
            analysis_run_path(owner_uid, project_id, analysis_run_id)
        )
        if data is None or not is_owner(data, owner_uid):
            raise NotFoundError(
                "Analysis run not found", details={"analysisRunId": analysis_run_id}
            )
        return data

    # ----------------------------------------------------------------- reads

    def get_run(
        self, *, owner_uid: str, project_id: str, analysis_run_id: str
    ) -> AnalysisRun:
        return _to_analysis_run(
            analysis_run_id,
            self.load_run_document(
                owner_uid=owner_uid,
                project_id=project_id,
                analysis_run_id=analysis_run_id,
            ),
        )

    def list_runs(self, *, owner_uid: str, project_id: str) -> list[AnalysisRun]:
        project = self.client.get_document(project_path(owner_uid, project_id))
        if project is None or not is_owner(project, owner_uid):
            raise NotFoundError("Project not found", details={"projectId": project_id})
        rows = self.client.query_collection(
            analysis_runs_collection_path(owner_uid, project_id),
            filters=[],
            order_by=[("createdAt", "DESCENDING")],
            limit=100,
            offset=0,
        )
        return [
            _to_analysis_run(run_id, data)
            for run_id, data in rows
            if is_owner(data, owner_uid)
        ]

    def get_reviewers(
        self, *, owner_uid: str, project_id: str, analysis_run_id: str
    ) -> list[ReviewerRun]:
        self.load_run_document(
            owner_uid=owner_uid, project_id=project_id, analysis_run_id=analysis_run_id
        )
        rows = self.client.query_collection(
            analysis_reviewers_collection_path(owner_uid, project_id, analysis_run_id),
            filters=[],
            order_by=[],
            limit=_LIST_LIMIT,
            offset=0,
        )
        reviewers = [
            _to_reviewer_run(reviewer_id, data)
            for reviewer_id, data in rows
            if is_owner(data, owner_uid)
        ]
        return sorted(
            reviewers,
            key=lambda reviewer: _dimension_order(reviewer.dimension.value),
        )

    def get_reviewer(
        self,
        *,
        owner_uid: str,
        project_id: str,
        analysis_run_id: str,
        reviewer_run_id: str,
    ) -> ReviewerRun:
        """One reviewer run, for the footage-artifact lookup."""
        path = reviewer_run_path(
            owner_uid, project_id, analysis_run_id, reviewer_run_id
        )
        data = self.client.get_document(path)
        if data is None or not is_owner(data, owner_uid):
            raise NotFoundError(
                "Reviewer run not found", details={"reviewerRunId": reviewer_run_id}
            )
        return _to_reviewer_run(reviewer_run_id, data)

    def list_findings(
        self,
        *,
        owner_uid: str,
        project_id: str,
        analysis_run_id: str,
        dimension: AnalysisDimension | None = None,
        severity: Severity | None = None,
        start_ms: int | None = None,
        end_ms: int | None = None,
    ) -> list[Finding]:
        self.load_run_document(
            owner_uid=owner_uid, project_id=project_id, analysis_run_id=analysis_run_id
        )
        rows = self.client.query_collection(
            analysis_findings_collection_path(owner_uid, project_id, analysis_run_id),
            filters=[],
            order_by=[],
            limit=_LIST_LIMIT,
            offset=0,
        )
        findings = [
            _to_finding(finding_id, data)
            for finding_id, data in rows
            if is_owner(data, owner_uid)
        ]
        if dimension is not None:
            findings = [f for f in findings if f.dimension is dimension]
        if severity is not None:
            findings = [f for f in findings if f.severity is severity]
        if start_ms is not None:
            findings = [f for f in findings if f.endMs > start_ms]
        if end_ms is not None:
            findings = [f for f in findings if f.startMs < end_ms]
        return sorted(findings, key=lambda finding: (finding.startMs, finding.findingId))

    def list_bins(
        self, *, owner_uid: str, project_id: str, analysis_run_id: str
    ) -> list[HeatmapBin]:
        self.load_run_document(
            owner_uid=owner_uid, project_id=project_id, analysis_run_id=analysis_run_id
        )
        rows = self.client.query_collection(
            heatmap_bins_collection_path(owner_uid, project_id, analysis_run_id),
            filters=[],
            order_by=[],
            limit=_LIST_LIMIT,
            offset=0,
        )
        bins = [
            _to_heatmap_bin(bin_id, data)
            for bin_id, data in rows
            if is_owner(data, owner_uid)
        ]
        return sorted(
            bins, key=lambda b: (_dimension_order(b.dimension.value), b.startMs)
        )

    def spent_usd(self, *, owner_uid: str, project_id: str) -> float:
        """Estimated spend on this project's analysis runs so far."""
        rows = self.client.query_collection(
            analysis_runs_collection_path(owner_uid, project_id),
            filters=[],
            order_by=[],
            limit=100,
            offset=0,
        )
        return round(
            sum(
                float(data.get("costEstimateUsd", 0.0))
                for _, data in rows
                if is_owner(data, owner_uid)
            ),
            6,
        )

    # -------------------------------------------------------- worker writes

    def mark_running(
        self,
        *,
        owner_uid: str,
        project_id: str,
        analysis_run_id: str,
        chunk_count: int,
    ) -> None:
        self._update_run(
            owner_uid,
            project_id,
            analysis_run_id,
            {"status": AnalysisRunStatus.running.value, "chunkCount": chunk_count},
        )
        self._emit_reviewer_progress(
            owner_uid, project_id, analysis_run_id, status=AnalysisRunStatus.running
        )

    def save_reviewer_outcome(
        self,
        *,
        owner_uid: str,
        project_id: str,
        analysis_run_id: str,
        outcome: DimensionOutcome,
    ) -> ReviewerRun:
        """Overwrite the queued placeholder for one dimension with its real result."""
        path = reviewer_run_path(
            owner_uid, project_id, analysis_run_id, outcome.reviewer_run_id
        )
        cost_usd = estimate_cost_usd(
            outcome.usage,
            input_price_per_mtok=self.settings.llm_input_price_per_mtok,
            output_price_per_mtok=self.settings.llm_output_price_per_mtok,
        )
        self._update_reviewer(
            owner_uid,
            project_id,
            analysis_run_id,
            outcome.reviewer_run_id,
            {
                "status": outcome.status.value,
                "findingCount": len(outcome.findings),
                "costEstimateUsd": cost_usd,
                "durationMs": outcome.duration_ms,
                "model": outcome.model,
                "inputSegmentCount": outcome.input_segment_count,
                "toolCalls": [
                    {
                        "tool": call.tool,
                        "timestampMs": call.timestamp_ms,
                        "label": call.label,
                        "mimeType": call.mime_type,
                        "contentPath": call.content_path,
                        "ok": call.ok,
                    }
                    for call in outcome.tool_calls
                ],
                "groundingQueries": outcome.grounding_queries,
                "groundingSources": outcome.grounding_sources,
                "groundingSearchSuggestions": outcome.grounding_html,
                "tokenUsage": {
                    "input": outcome.usage.input_tokens,
                    "output": outcome.usage.output_tokens,
                },
                "error": outcome.error,
                "startedAt": outcome.started_at,
                "finishedAt": outcome.finished_at,
            },
        )
        stored = self.client.get_document(path) or {}
        self._emit_reviewer_progress(
            owner_uid, project_id, analysis_run_id, status=AnalysisRunStatus.running
        )
        return _to_reviewer_run(outcome.reviewer_run_id, stored)

    def save_findings(
        self,
        *,
        owner_uid: str,
        project_id: str,
        analysis_run_id: str,
        findings: Sequence[Finding],
    ) -> int:
        now = datetime.now(UTC)
        for finding in findings:
            self.client.set_document(
                finding_path(owner_uid, project_id, analysis_run_id, finding.findingId),
                {
                    "ownerUid": owner_uid,
                    "dimension": finding.dimension.value,
                    "reviewerRunId": finding.reviewerRunId,
                    "segmentId": finding.segmentId,
                    "startMs": finding.startMs,
                    "endMs": finding.endMs,
                    "score": finding.score,
                    "confidence": finding.confidence,
                    "severity": finding.severity.value,
                    "findingType": finding.findingType,
                    "evidence": {
                        "quote": finding.evidence.quote,
                        "critique_and_reasoning": (
                            finding.evidence.critique_and_reasoning
                        ),
                    },
                    "suggestion": finding.suggestion,
                    "citations": finding.citations,
                    "createdAt": now,
                },
            )
        return len(findings)

    def save_bins(
        self,
        *,
        owner_uid: str,
        project_id: str,
        analysis_run_id: str,
        bins: Sequence[HeatmapBin],
    ) -> int:
        now = datetime.now(UTC)
        for heatmap_bin in bins:
            self.client.set_document(
                heatmap_bin_path(
                    owner_uid, project_id, analysis_run_id, heatmap_bin.binId
                ),
                {
                    "ownerUid": owner_uid,
                    "binId": heatmap_bin.binId,
                    "dimension": heatmap_bin.dimension.value,
                    "startMs": heatmap_bin.startMs,
                    "endMs": heatmap_bin.endMs,
                    "score": heatmap_bin.score,
                    "severity": heatmap_bin.severity.value,
                    "color": heatmap_bin.color.value,
                    "findingIds": heatmap_bin.findingIds,
                    "createdAt": now,
                },
            )
        return len(bins)

    def finish_run(
        self,
        *,
        owner_uid: str,
        project_id: str,
        analysis_run_id: str,
        status: AnalysisRunStatus,
        summary: FindingSummary,
        cost_usd: float,
        completed_dimensions: Sequence[AnalysisDimension],
        error: dict[str, Any] | None = None,
    ) -> AnalysisRun:
        self._update_run(
            owner_uid,
            project_id,
            analysis_run_id,
            {
                "status": status.value,
                "overallScore": summary.overall_score,
                "scoreByDimension": summary.score_by_dimension,
                "findingCounts": summary.counts,
                "costEstimateUsd": cost_usd,
                "completedDimensions": [d.value for d in completed_dimensions],
                "error": error,
            },
        )
        emit_analysis_ready(
            owner_uid,
            project_id,
            analysis_run_id=analysis_run_id,
            status=status,
            overall_score=summary.overall_score,
            finding_counts=summary.counts,
        )
        return self.get_run(
            owner_uid=owner_uid,
            project_id=project_id,
            analysis_run_id=analysis_run_id,
        )

    # ------------------------------------------------------------- internals

    def _emit_reviewer_progress(
        self,
        owner_uid: str,
        project_id: str,
        analysis_run_id: str,
        *,
        status: AnalysisRunStatus,
    ) -> None:
        """Push an `analysis.progress` frame with per-reviewer status.

        Only reads the reviewer subcollection when a socket is actually watching;
        without subscribers this is a no-op so worker writes stay cheap.
        """
        if not has_subscribers(owner_uid, project_id):
            return
        try:
            reviewers = self.get_reviewers(
                owner_uid=owner_uid,
                project_id=project_id,
                analysis_run_id=analysis_run_id,
            )
        except Exception:  # noqa: BLE001 — progress reporting must not fail the write
            logger.exception("analysis %s: could not build reviewer status", analysis_run_id)
            return
        completed = [
            r.dimension.value
            for r in reviewers
            if r.status == ReviewerRunStatus.succeeded
        ]
        statuses = [
            {
                "dimension": r.dimension.value,
                "status": r.status.value,
                "findingCount": r.findingCount,
                "error": (r.error or {}).get("message") if r.error else None,
            }
            for r in reviewers
        ]
        emit_analysis_progress(
            owner_uid,
            project_id,
            analysis_run_id=analysis_run_id,
            status=status,
            completed_dimensions=completed,
            reviewer_statuses=statuses,
        )

    def _persona_version(self, owner_uid: str) -> int | None:
        """Which persona revision this analysis is based on, when there is one."""
        user = self.client.get_document(user_path(owner_uid))
        if user is None:
            return None
        persona = user.get("persona") or {}
        version = persona.get("version")
        return int(version) if isinstance(version, (int, float)) else None

    def _update_run(
        self,
        owner_uid: str,
        project_id: str,
        analysis_run_id: str,
        patch: dict[str, Any],
    ) -> None:
        self.load_run_document(
            owner_uid=owner_uid, project_id=project_id, analysis_run_id=analysis_run_id
        )
        self.client.update_document(
            analysis_run_path(owner_uid, project_id, analysis_run_id),
            {**patch, "updatedAt": datetime.now(UTC)},
        )

    def _update_reviewer(
        self,
        owner_uid: str,
        project_id: str,
        analysis_run_id: str,
        reviewer_run_id: str,
        patch: dict[str, Any],
    ) -> None:
        path = reviewer_run_path(
            owner_uid, project_id, analysis_run_id, reviewer_run_id
        )
        existing = self.client.get_document(path)
        if existing is None or not is_owner(existing, owner_uid):
            raise NotFoundError(
                "Reviewer run not found", details={"reviewerRunId": reviewer_run_id}
            )
        self.client.update_document(path, {**patch, "updatedAt": datetime.now(UTC)})


__all__ = [
    "AnalysisCapExceeded",
    "AnalysisService",
    "ensure_within_budget",
    "is_owner",
]
