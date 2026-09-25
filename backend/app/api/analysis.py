"""Analysis and heatmap API (`docs/technical-design/api-design.md` section 9).

POST queues a tier-1 multi-reviewer run and returns immediately; the reads below are
what the timeline UI polls while it runs and shows when it finishes.
"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status

from app.config import Settings, get_settings
from app.dependencies import (
    AnalysisScheduler,
    AuthenticatedUser,
    current_user,
    get_analysis_pubsub,
    get_analysis_scheduler,
    get_analysis_service,
)
from app.events import build_event, topic_for_event
from app.schemas.analysis import (
    AnalysisDimension,
    AnalysisRequest,
    AnalysisRun,
    AnalysisRunList,
    AnalysisStartResponse,
    FindingList,
    HeatmapResponse,
    ReviewerRunList,
    Severity,
)
from app.services.analysis_service import (
    AnalysisService,
    ensure_within_budget,
)
from app.services.pubsub_service import PubSubClient

router = APIRouter(tags=["analysis"])

UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
ServiceDep = Annotated[AnalysisService, Depends(get_analysis_service)]
SchedulerDep = Annotated[AnalysisScheduler, Depends(get_analysis_scheduler)]
PubSubDep = Annotated[PubSubClient | None, Depends(get_analysis_pubsub)]


@router.get("/projects/{projectId}/analysis", response_model=AnalysisRunList)
async def list_analysis_runs(
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
async def start_analysis(
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
        service.spent_usd(owner_uid=user.uid, project_id=projectId),
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


@router.get(
    "/projects/{projectId}/analysis/{analysisRunId}", response_model=AnalysisRun
)
async def get_analysis_run(
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
async def list_analysis_reviewers(
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
async def list_analysis_findings(
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


@router.get(
    "/projects/{projectId}/analysis/{analysisRunId}/heatmap",
    response_model=HeatmapResponse,
)
async def get_analysis_heatmap(
    projectId: str,
    analysisRunId: str,
    user: UserDep,
    service: ServiceDep,
) -> HeatmapResponse:
    return HeatmapResponse(
        bins=service.list_bins(
            owner_uid=user.uid, project_id=projectId, analysis_run_id=analysisRunId
        )
    )
