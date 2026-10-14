from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Response

from app.dependencies import AuthenticatedUser, current_user
from app.schemas.rough_cut import RoughCutAccepted, RoughCutPlan, RoughCutRequest
from app.services.rough_cut import RoughCutService
from app.workers.rough_cut_worker import live_service, rough_cut_after_response

router = APIRouter(tags=["analysis"])
UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
ServiceDep = Annotated[RoughCutService, Depends(live_service)]
_BASE = "/projects/{projectId}/analysis/{analysisRunId}/rough-cut"


@router.get(f"{_BASE}/plan", response_model=RoughCutPlan)
def preview_plan(
    projectId: str, analysisRunId: str, user: UserDep, service: ServiceDep
) -> RoughCutPlan:
    plan, _ = service.plan(
        owner_uid=user.uid, project_id=projectId, run_id=analysisRunId, payload=RoughCutRequest()
    )
    return plan


@router.post(f"{_BASE}/plan", response_model=RoughCutPlan)
def preview_selection(
    projectId: str, analysisRunId: str, payload: RoughCutRequest, user: UserDep, service: ServiceDep
) -> RoughCutPlan:
    plan, _ = service.plan(
        owner_uid=user.uid, project_id=projectId, run_id=analysisRunId, payload=payload
    )
    return plan


@router.post(_BASE, response_model=RoughCutAccepted, status_code=202)
def render_preview(
    projectId: str,
    analysisRunId: str,
    user: UserDep,
    service: ServiceDep,
    background_tasks: BackgroundTasks,
    payload: RoughCutRequest | None = None,
) -> RoughCutAccepted:
    accepted = service.create(
        owner_uid=user.uid,
        project_id=projectId,
        run_id=analysisRunId,
        payload=payload or RoughCutRequest(),
    )
    rough_cut_after_response(
        background_tasks, owner_uid=user.uid, project_id=projectId, job_id=accepted.jobId
    )
    return accepted


@router.get(f"{_BASE}/edl")
def download_edl(
    projectId: str,
    analysisRunId: str,
    user: UserDep,
    service: ServiceDep,
    format: Literal["cmx3600", "markdown"] = "cmx3600",
    fps: Literal[24, 25, 30, 60] = 30,
    assetId: str | None = None,
) -> Response:
    text = service.export(
        owner_uid=user.uid,
        project_id=projectId,
        run_id=analysisRunId,
        asset_id=assetId,
        format=format,
        fps=fps,
    )
    extension = "md" if format == "markdown" else "edl"
    return Response(
        text,
        media_type="text/markdown" if format == "markdown" else "text/plain",
        headers={"Content-Disposition": f'attachment; filename="rough-cut.{extension}"'},
    )


@router.delete("/projects/{projectId}/assets/{assetId}", status_code=204)
def discard_preview(projectId: str, assetId: str, user: UserDep, service: ServiceDep) -> Response:
    service.discard(owner_uid=user.uid, project_id=projectId, asset_id=assetId)
    return Response(status_code=204)


@router.get("/projects/{projectId}/assets/{assetId}/captions")
def source_captions(projectId: str, assetId: str, user: UserDep, service: ServiceDep) -> Response:
    return Response(
        service.captions(owner_uid=user.uid, project_id=projectId, asset_id=assetId),
        media_type="text/vtt",
    )
