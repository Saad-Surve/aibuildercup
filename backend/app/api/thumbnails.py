"""Thumbnail studio endpoints.

The creator asks for concepts; a `thumbnail` job plans them from the transcript and reviewer
findings, renders them with Gemini image generation, and critiques the result. These routes
validate input, queue the job, list concepts, apply one to the project's packaging, and hand
back short-lived download URLs.
"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Response, status

from app.dependencies import (
    AuthenticatedUser,
    ThumbnailScheduler,
    current_user,
    get_thumbnail_scheduler,
    get_thumbnail_service,
)
from app.schemas.assets import DownloadUrl
from app.schemas.jobs import JobStatus
from app.schemas.thumbnails import (
    GenerateThumbnailsRequest,
    ReviseThumbnailRequest,
    ThumbnailBatchAccepted,
    ThumbnailConcept,
    ThumbnailConceptList,
    ThumbnailRevisionAccepted,
    ThumbnailSelectionRequest,
)
from app.services.thumbnail_service import ThumbnailService

router = APIRouter(tags=["thumbnails"])

UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
ServiceDep = Annotated[ThumbnailService, Depends(get_thumbnail_service)]
SchedulerDep = Annotated[ThumbnailScheduler, Depends(get_thumbnail_scheduler)]


@router.get(
    "/projects/{projectId}/thumbnails", response_model=ThumbnailConceptList
)
async def list_thumbnails(
    projectId: str,
    user: UserDep,
    service: ServiceDep,
) -> ThumbnailConceptList:
    return ThumbnailConceptList(
        items=service.list(owner_uid=user.uid, project_id=projectId)
    )


@router.post(
    "/projects/{projectId}/thumbnails",
    response_model=ThumbnailBatchAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_thumbnails(
    projectId: str,
    payload: GenerateThumbnailsRequest,
    user: UserDep,
    service: ServiceDep,
    background_tasks: BackgroundTasks,
    scheduler: SchedulerDep,
) -> ThumbnailBatchAccepted:
    """Plan and render a batch of grounded thumbnail concepts."""
    concepts, job = service.create_batch(
        owner_uid=user.uid, project_id=projectId, payload=payload
    )
    if job.status not in (JobStatus.succeeded, JobStatus.running):
        scheduler(
            background_tasks,
            owner_uid=user.uid,
            project_id=projectId,
            job_id=job.jobId,
        )
    return ThumbnailBatchAccepted(
        thumbnailIds=[concept.thumbnailId for concept in concepts],
        jobId=job.jobId,
        status=job.status.value,
    )


@router.post(
    "/projects/{projectId}/thumbnails/regenerate",
    response_model=ThumbnailBatchAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def regenerate_thumbnails(
    projectId: str,
    payload: ThumbnailSelectionRequest,
    user: UserDep,
    service: ServiceDep,
    background_tasks: BackgroundTasks,
    scheduler: SchedulerDep,
) -> ThumbnailBatchAccepted:
    """Re-render each selected concept as a fresh version, keeping its idea."""
    concepts, job = service.regenerate(
        owner_uid=user.uid,
        project_id=projectId,
        thumbnail_ids=payload.thumbnailIds,
    )
    if job.status not in (JobStatus.succeeded, JobStatus.running):
        scheduler(
            background_tasks,
            owner_uid=user.uid,
            project_id=projectId,
            job_id=job.jobId,
        )
    return ThumbnailBatchAccepted(
        thumbnailIds=[concept.thumbnailId for concept in concepts],
        jobId=job.jobId,
        status=job.status.value,
    )


@router.post("/projects/{projectId}/thumbnails/download")
async def download_thumbnails(
    projectId: str,
    payload: ThumbnailSelectionRequest,
    user: UserDep,
    service: ServiceDep,
) -> Response:
    """Zip the active image of each selected concept for a bulk download."""
    data = service.download_bundle(
        owner_uid=user.uid,
        project_id=projectId,
        thumbnail_ids=payload.thumbnailIds,
    )
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="thumbnails.zip"'},
    )


@router.get(
    "/projects/{projectId}/thumbnails/{thumbnailId}", response_model=ThumbnailConcept
)
async def get_thumbnail(
    projectId: str,
    thumbnailId: str,
    user: UserDep,
    service: ServiceDep,
) -> ThumbnailConcept:
    return service.get(
        owner_uid=user.uid, project_id=projectId, thumbnail_id=thumbnailId
    )


@router.post(
    "/projects/{projectId}/thumbnails/{thumbnailId}/revise",
    response_model=ThumbnailRevisionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def revise_thumbnail(
    projectId: str,
    thumbnailId: str,
    payload: ReviseThumbnailRequest,
    user: UserDep,
    service: ServiceDep,
    background_tasks: BackgroundTasks,
    scheduler: SchedulerDep,
) -> ThumbnailRevisionAccepted:
    """Queue a conversational edit of the concept's active image."""
    _, job = service.revise(
        owner_uid=user.uid,
        project_id=projectId,
        thumbnail_id=thumbnailId,
        payload=payload,
    )
    if job.status not in (JobStatus.succeeded, JobStatus.running):
        scheduler(
            background_tasks,
            owner_uid=user.uid,
            project_id=projectId,
            job_id=job.jobId,
        )
    return ThumbnailRevisionAccepted(
        thumbnailId=thumbnailId, jobId=job.jobId, status=job.status.value
    )


@router.post(
    "/projects/{projectId}/thumbnails/{thumbnailId}/apply",
    response_model=ThumbnailConcept,
)
async def apply_thumbnail(
    projectId: str,
    thumbnailId: str,
    user: UserDep,
    service: ServiceDep,
) -> ThumbnailConcept:
    """Make this concept the project's packaging promise (feeds the reviewers)."""
    return service.apply(
        owner_uid=user.uid, project_id=projectId, thumbnail_id=thumbnailId
    )


@router.get(
    "/projects/{projectId}/thumbnails/{thumbnailId}/download-url",
    response_model=DownloadUrl,
)
async def get_thumbnail_download_url(
    projectId: str,
    thumbnailId: str,
    user: UserDep,
    service: ServiceDep,
) -> DownloadUrl:
    url, expires_at = service.download_url(
        owner_uid=user.uid, project_id=projectId, thumbnail_id=thumbnailId
    )
    return DownloadUrl(url=url, expiresAt=expires_at)


@router.delete(
    "/projects/{projectId}/thumbnails/{thumbnailId}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_thumbnail(
    projectId: str,
    thumbnailId: str,
    user: UserDep,
    service: ServiceDep,
) -> Response:
    service.delete(owner_uid=user.uid, project_id=projectId, thumbnail_id=thumbnailId)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
