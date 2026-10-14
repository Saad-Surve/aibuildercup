"""Analysis and heatmap API (`docs/technical-design/api-design.md` section 9).

POST queues a tier-1 multi-reviewer run and returns immediately; the reads below are
what the timeline UI polls while it runs and shows when it finishes.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status

from app.agents.adjudicator import adjudicator_reservation
from app.config import Settings, get_settings
from app.dependencies import (
    AnalysisScheduler,
    AuthenticatedUser,
    current_user,
    get_analysis_pubsub,
    get_analysis_scheduler,
    get_analysis_service,
)
from app.errors import NotFoundError
from app.events import build_event, topic_for_event
from app.schemas.analysis import (
    AnalysisDimension,
    AnalysisRequest,
    AnalysisRun,
    AnalysisRunList,
    AnalysisStartResponse,
    ContextArtifactUrl,
    Finding,
    FindingDecisionRequest,
    FindingList,
    HeatmapResponse,
    InterestCurve,
    ReviewerRunList,
    Severity,
)
from app.schemas.analysis_compare import AnalysisComparison
from app.services.analysis_compare import AnalysisCompareService
from app.services.analysis_service import (
    AnalysisService,
    ensure_within_budget,
)
from app.services.firestore_service import project_object_prefix
from app.services.pubsub_service import PubSubClient
from app.services.storage_service import StorageClient, get_storage_client

router = APIRouter(tags=["analysis"])

UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
ServiceDep = Annotated[AnalysisService, Depends(get_analysis_service)]
SchedulerDep = Annotated[AnalysisScheduler, Depends(get_analysis_scheduler)]
PubSubDep = Annotated[PubSubClient | None, Depends(get_analysis_pubsub)]
StorageDep = Annotated[StorageClient, Depends(get_storage_client)]

#: How long a reviewer-context signed URL stays valid.
_CONTEXT_URL_TTL_SECONDS = 900


@router.get("/projects/{projectId}/analysis", response_model=AnalysisRunList)
def list_analysis_runs(
    projectId: str,
    user: UserDep,
    service: ServiceDep,
) -> AnalysisRunList:
    return AnalysisRunList(
        items=service.list_runs(owner_uid=user.uid, project_id=projectId)
    )


@router.post(
    "/projects/{projectId}/analysis",
    response_model=AnalysisStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_analysis(
    projectId: str,
    payload: AnalysisRequest,
    background_tasks: BackgroundTasks,
    user: UserDep,
    service: ServiceDep,
    scheduler: SchedulerDep,
    pubsub: PubSubDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnalysisStartResponse:
    ensure_within_budget(
        service.spent_usd(owner_uid=user.uid, project_id=projectId)
        + adjudicator_reservation(settings),
        max_project_cost_usd=settings.max_project_cost_usd,
    )
    run, job = service.create_run(
        owner_uid=user.uid, project_id=projectId, payload=payload
    )
    if pubsub is not None:
        try:
            pubsub.publish(
                topic=topic_for_event("analysis.requested"),
                event=build_event(
                    event_type="analysis.requested",
                    owner_uid=user.uid,
                    project_id=projectId,
                    job_id=job.jobId,
                    payload={
                        "analysisRunId": run.analysisRunId,
                        "dimensions": [d.value for d in run.requestedDimensions],
                        "platform": payload.platform,
                    },
                ),
            )
        except Exception:  # noqa: BLE001 - a publish failure must not fail the request
            pass
    scheduler(
        background_tasks,
        owner_uid=user.uid,
        project_id=projectId,
        job_id=job.jobId,
    )
    return AnalysisStartResponse(
        analysisRunId=run.analysisRunId,
        jobId=job.jobId,
        status=run.status.value,
    )


@router.get("/projects/{projectId}/analysis/compare", response_model=AnalysisComparison)
def compare_analysis_runs(
    projectId: str,
    user: UserDep,
    service: ServiceDep,
    baseRunId: Annotated[
        str, Query(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    ],
    targetRunId: Annotated[
        str, Query(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    ],
) -> AnalysisComparison:
    return AnalysisCompareService(service.client).compare(
        owner_uid=user.uid,
        project_id=projectId,
        base_run_id=baseRunId,
        target_run_id=targetRunId,
    )


@router.get(
    "/projects/{projectId}/analysis/{analysisRunId}", response_model=AnalysisRun
)
def get_analysis_run(
    projectId: str,
    analysisRunId: str,
    user: UserDep,
    service: ServiceDep,
) -> AnalysisRun:
    return service.get_run(
        owner_uid=user.uid, project_id=projectId, analysis_run_id=analysisRunId
    )


@router.get(
    "/projects/{projectId}/analysis/{analysisRunId}/reviewers",
    response_model=ReviewerRunList,
)
def list_analysis_reviewers(
    projectId: str,
    analysisRunId: str,
    user: UserDep,
    service: ServiceDep,
) -> ReviewerRunList:
    return ReviewerRunList(
        items=service.get_reviewers(
            owner_uid=user.uid, project_id=projectId, analysis_run_id=analysisRunId
        )
    )


@router.get(
    "/projects/{projectId}/analysis/{analysisRunId}/findings",
    response_model=FindingList,
)
def list_analysis_findings(
    projectId: str,
    analysisRunId: str,
    user: UserDep,
    service: ServiceDep,
    dimension: AnalysisDimension | None = None,
    severity: Severity | None = None,
    startMs: Annotated[int | None, Query(ge=0)] = None,
    endMs: Annotated[int | None, Query(ge=0)] = None,
) -> FindingList:
    return FindingList(
        items=service.list_findings(
            owner_uid=user.uid,
            project_id=projectId,
            analysis_run_id=analysisRunId,
            dimension=dimension,
            severity=severity,
            start_ms=startMs,
            end_ms=endMs,
        )
    )


@router.patch(
    "/projects/{projectId}/analysis/{analysisRunId}/findings/{findingId}",
    response_model=Finding,
)
def decide_finding(
    projectId: str,
    analysisRunId: str,
    findingId: str,
    payload: FindingDecisionRequest,
    user: UserDep,
    service: ServiceDep,
) -> Finding:
    return service.decide_finding(
        owner_uid=user.uid,
        project_id=projectId,
        analysis_run_id=analysisRunId,
        finding_id=findingId,
        decision=payload.decision,
    )


@router.get(
    "/projects/{projectId}/analysis/{analysisRunId}/findings/{findingId}/adjudication/evidence",
    response_model=ContextArtifactUrl,
)
def get_adjudication_evidence(
    projectId: str,
    analysisRunId: str,
    findingId: str,
    user: UserDep,
    service: ServiceDep,
    storage: StorageDep,
    kind: Literal["frame", "clip"] = "frame",
) -> ContextArtifactUrl:
    finding = service.get_finding(
        owner_uid=user.uid,
        project_id=projectId,
        analysis_run_id=analysisRunId,
        finding_id=findingId,
    )
    evidence = finding.adjudication.evidence if finding.adjudication else None
    path = (evidence.framePath if kind == "frame" else evidence.clipPath) if evidence else None
    prefix = (
        f"{project_object_prefix(user.uid, projectId)}review-context/"
        f"{analysisRunId}/adjudicator-{findingId}/"
    )
    if not path or not path.startswith(prefix):
        raise NotFoundError("Adjudication evidence not found")
    return ContextArtifactUrl(
        url=storage.signed_download_url(path, expires_seconds=_CONTEXT_URL_TTL_SECONDS),
        contentType="image/jpeg" if kind == "frame" else "video/mp4",
        expiresIn=_CONTEXT_URL_TTL_SECONDS,
    )


@router.get(
    "/projects/{projectId}/analysis/{analysisRunId}/heatmap",
    response_model=HeatmapResponse,
)
def get_analysis_heatmap(
    projectId: str,
    analysisRunId: str,
    user: UserDep,
    service: ServiceDep,
) -> HeatmapResponse:
    return HeatmapResponse(
        bins=service.list_bins(
            owner_uid=user.uid, project_id=projectId, analysis_run_id=analysisRunId
        ),
        coverage=service.get_coverage(
            owner_uid=user.uid, project_id=projectId, analysis_run_id=analysisRunId
        ),
    )


@router.get(
    "/projects/{projectId}/analysis/{analysisRunId}/interest",
    response_model=InterestCurve,
)
def get_analysis_interest(
    projectId: str,
    analysisRunId: str,
    user: UserDep,
    service: ServiceDep,
) -> InterestCurve:
    return service.get_interest(
        owner_uid=user.uid, project_id=projectId, analysis_run_id=analysisRunId
    )


@router.get(
    "/projects/{projectId}/analysis/{analysisRunId}/reviewers/{reviewerRunId}/context/{index}",
    response_model=ContextArtifactUrl,
)
def get_reviewer_context_artifact(
    projectId: str,
    analysisRunId: str,
    reviewerRunId: str,
    index: int,
    user: UserDep,
    service: ServiceDep,
    storage: StorageDep,
) -> ContextArtifactUrl:
    """A signed URL for one frame/clip a reviewer fetched (lazy; only when the UI asks).

    The stored path is verified to sit under the caller's project prefix before signing,
    so a reviewer run can only ever serve its own project's footage.
    """
    reviewer = service.get_reviewer(
        owner_uid=user.uid,
        project_id=projectId,
        analysis_run_id=analysisRunId,
        reviewer_run_id=reviewerRunId,
    )
    if index < 0 or index >= len(reviewer.toolCalls):
        raise NotFoundError(
            "Footage not found",
            details={"reviewerRunId": reviewerRunId, "index": index},
        )
    call = reviewer.toolCalls[index]
    prefix = f"{project_object_prefix(user.uid, projectId)}review-context/"
    if not call.contentPath or not call.contentPath.startswith(prefix):
        raise NotFoundError("Footage not found", details={"reviewerRunId": reviewerRunId})
    url = storage.signed_download_url(
        call.contentPath, expires_seconds=_CONTEXT_URL_TTL_SECONDS
    )
    return ContextArtifactUrl(
        url=url, contentType=call.mimeType, expiresIn=_CONTEXT_URL_TTL_SECONDS
    )
