"""Caption burn-in endpoints.

Lets the workspace render the project's transcript onto its source video with a chosen
`CaptionStyle`. The heavy lifting happens in `caption_worker`; these routes validate input,
queue the job, list renders, and hand back short-lived download URLs.
"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Response, status

from app.dependencies import (
    AuthenticatedUser,
    CaptionScheduler,
    current_user,
    get_caption_scheduler,
    get_caption_service,
)
from app.schemas.assets import DownloadUrl
from app.schemas.captions import (
    CaptionPresetList,
    CaptionRender,
    CaptionRenderAccepted,
    CaptionRenderList,
    CaptionRenderRequest,
)
from app.schemas.jobs import JobStatus
from app.services.caption_service import CaptionRenderService
from app.services.caption_styles import preset_list

router = APIRouter(tags=["captions"])

UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
ServiceDep = Annotated[CaptionRenderService, Depends(get_caption_service)]
SchedulerDep = Annotated[CaptionScheduler, Depends(get_caption_scheduler)]


@router.get("/caption-presets", response_model=CaptionPresetList)
async def list_caption_presets(user: UserDep) -> CaptionPresetList:
    """Style presets the web client mirrors in its customizer.

    The same definitions feed `build_ass`, so the preview and the render cannot drift.
    """
    return CaptionPresetList(items=preset_list())


@router.post(
    "/projects/{projectId}/captions/renders",
    response_model=CaptionRenderAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_caption_render(
    projectId: str,
    payload: CaptionRenderRequest,
    user: UserDep,
    service: ServiceDep,
    background_tasks: BackgroundTasks,
    scheduler: SchedulerDep,
) -> CaptionRenderAccepted:
    """Queue a render of the active (or a chosen) transcript onto the source video."""
    render, job = service.create(
        owner_uid=user.uid, project_id=projectId, payload=payload
    )
    if job.status not in (JobStatus.succeeded, JobStatus.running):
        scheduler(
            background_tasks,
            owner_uid=user.uid,
            project_id=projectId,
            job_id=job.jobId,
        )
    return CaptionRenderAccepted(
        captionRenderId=render.captionRenderId,
        jobId=job.jobId,
        status=job.status.value,
    )


@router.get(
    "/projects/{projectId}/captions/renders",
    response_model=CaptionRenderList,
)
async def list_caption_renders(
    projectId: str,
    user: UserDep,
    service: ServiceDep,
) -> CaptionRenderList:
    return CaptionRenderList(
        items=service.list(owner_uid=user.uid, project_id=projectId)
    )


@router.get(
    "/projects/{projectId}/captions/renders/{captionRenderId}",
    response_model=CaptionRender,
)
async def get_caption_render(
    projectId: str,
    captionRenderId: str,
    user: UserDep,
    service: ServiceDep,
) -> CaptionRender:
    return service.get(
        owner_uid=user.uid,
        project_id=projectId,
        caption_render_id=captionRenderId,
    )


@router.get(
    "/projects/{projectId}/captions/renders/{captionRenderId}/download-url",
    response_model=DownloadUrl,
)
async def get_caption_render_download_url(
    projectId: str,
    captionRenderId: str,
    user: UserDep,
    service: ServiceDep,
) -> DownloadUrl:
    url, expires_at = service.download_url(
        owner_uid=user.uid,
        project_id=projectId,
        caption_render_id=captionRenderId,
    )
    return DownloadUrl(url=url, expiresAt=expires_at)


@router.delete(
    "/projects/{projectId}/captions/renders/{captionRenderId}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_caption_render(
    projectId: str,
    captionRenderId: str,
    user: UserDep,
    service: ServiceDep,
) -> Response:
    service.delete(
        owner_uid=user.uid,
        project_id=projectId,
        caption_render_id=captionRenderId,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
