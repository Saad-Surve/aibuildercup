from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, status

from app.dependencies import (
    AuthenticatedUser,
    TranscribeScheduler,
    current_user,
    get_asset_service,
    get_transcribe_scheduler,
)
from app.schemas.assets import (
    AssetList,
    CreateUploadSession,
    DownloadUrl,
    RevisionActivation,
    RevisionList,
    UploadSession,
)
from app.schemas.common import AcceptedJob
from app.schemas.jobs import JobStatus
from app.services.asset_service import AssetService

router = APIRouter(tags=["uploads"])

UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
ServiceDep = Annotated[AssetService, Depends(get_asset_service)]
SchedulerDep = Annotated[TranscribeScheduler, Depends(get_transcribe_scheduler)]


@router.post(
    "/projects/{projectId}/upload-session",
    response_model=UploadSession,
    status_code=status.HTTP_201_CREATED,
)
def create_upload_session(
    projectId: str,
    payload: CreateUploadSession,
    user: UserDep,
    service: ServiceDep,
) -> UploadSession:
    return service.create_upload_session(
        owner_uid=user.uid, project_id=projectId, payload=payload
    )


@router.get("/projects/{projectId}/assets", response_model=AssetList)
def list_assets(
    projectId: str,
    user: UserDep,
    service: ServiceDep,
) -> AssetList:
    return AssetList(items=service.list_assets(owner_uid=user.uid, project_id=projectId))


@router.get("/projects/{projectId}/revisions", response_model=RevisionList)
def list_revisions(
    projectId: str,
    user: UserDep,
    service: ServiceDep,
) -> RevisionList:
    """Source-video revisions, newest first. The active one is flagged."""
    return RevisionList(
        items=service.list_revisions(owner_uid=user.uid, project_id=projectId)
    )


@router.post(
    "/projects/{projectId}/revisions/{assetId}/activate",
    response_model=RevisionActivation,
    status_code=status.HTTP_202_ACCEPTED,
)
def activate_revision(
    projectId: str,
    assetId: str,
    user: UserDep,
    service: ServiceDep,
    background_tasks: BackgroundTasks,
    scheduler: SchedulerDep,
) -> RevisionActivation:
    """Make an earlier revision the active source; transcribe it if it has no transcript."""
    activation, job = service.activate_revision(
        owner_uid=user.uid, project_id=projectId, asset_id=assetId
    )
    if job is not None and job.status not in (JobStatus.succeeded, JobStatus.running):
        scheduler(
            background_tasks,
            owner_uid=user.uid,
            project_id=projectId,
            job_id=job.jobId,
        )
    return activation


@router.get(
    "/projects/{projectId}/assets/{assetId}/download-url",
    response_model=DownloadUrl,
)
def download_url(
    projectId: str,
    assetId: str,
    user: UserDep,
    service: ServiceDep,
) -> DownloadUrl:
    return service.download_url(
        owner_uid=user.uid, project_id=projectId, asset_id=assetId
    )


@router.post(
    "/projects/{projectId}/assets/{assetId}/complete",
    response_model=AcceptedJob,
    status_code=status.HTTP_202_ACCEPTED,
)
def complete_upload(
    projectId: str,
    assetId: str,
    user: UserDep,
    service: ServiceDep,
    background_tasks: BackgroundTasks,
    scheduler: SchedulerDep,
) -> AcceptedJob:
    job = service.complete_upload(
        owner_uid=user.uid, project_id=projectId, asset_id=assetId
    )
    # A finished job needs no new run; anything else (queued, failed) gets one.
    # Failed jobs therefore retry by re-completing the upload.
    if job.status not in (JobStatus.succeeded, JobStatus.running):
        scheduler(
            background_tasks,
            owner_uid=user.uid,
            project_id=projectId,
            job_id=job.jobId,
        )
    return AcceptedJob(jobId=job.jobId, status=job.status.value)
