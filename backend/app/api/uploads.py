from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.dependencies import AuthenticatedUser, current_user, get_asset_service
from app.schemas.assets import (
    AssetList,
    CreateUploadSession,
    PlaybackUrl,
    UploadSession,
)
from app.schemas.common import AcceptedJob
from app.services.asset_service import AssetService

router = APIRouter(tags=["uploads"])

UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
ServiceDep = Annotated[AssetService, Depends(get_asset_service)]


@router.post(
    "/projects/{projectId}/upload-session",
    response_model=UploadSession,
    status_code=status.HTTP_201_CREATED,
)
async def create_upload_session(
    projectId: str,
    payload: CreateUploadSession,
    user: UserDep,
    service: ServiceDep,
) -> UploadSession:
    return service.create_upload_session(
        owner_uid=user.uid, project_id=projectId, payload=payload
    )


@router.get("/projects/{projectId}/assets", response_model=AssetList)
async def list_assets(
    projectId: str,
    user: UserDep,
    service: ServiceDep,
) -> AssetList:
    return AssetList(items=service.list(owner_uid=user.uid, project_id=projectId))


@router.get(
    "/projects/{projectId}/assets/{assetId}/playback-url",
    response_model=PlaybackUrl,
)
async def playback_url(
    projectId: str,
    assetId: str,
    user: UserDep,
    service: ServiceDep,
) -> PlaybackUrl:
    return service.playback_url(
        owner_uid=user.uid, project_id=projectId, asset_id=assetId
    )


@router.post(
    "/projects/{projectId}/assets/{assetId}/complete",
    response_model=AcceptedJob,
    status_code=status.HTTP_202_ACCEPTED,
)
async def complete_upload(
    projectId: str,
    assetId: str,
    user: UserDep,
    service: ServiceDep,
) -> AcceptedJob:
    job = service.complete_upload(
        owner_uid=user.uid, project_id=projectId, asset_id=assetId
    )
    return AcceptedJob(jobId=job.jobId, status=job.status.value)
