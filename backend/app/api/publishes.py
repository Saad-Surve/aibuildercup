"""Publish endpoints: send a project's video, thumbnail, and captions to a connected channel."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, status

from app.dependencies import (
    AuthenticatedUser,
    PublishScheduler,
    current_user,
    get_publish_scheduler,
    get_publish_service,
)
from app.schemas.jobs import JobStatus
from app.schemas.publishes import (
    Publish,
    PublishAccepted,
    PublishList,
    PublishRequest,
)
from app.services.publish_service import PublishService, accepted

router = APIRouter(tags=["publishes"])

UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
ServiceDep = Annotated[PublishService, Depends(get_publish_service)]
SchedulerDep = Annotated[PublishScheduler, Depends(get_publish_scheduler)]


@router.post(
    "/projects/{projectId}/publishes",
    response_model=PublishAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_publish(
    projectId: str,
    payload: PublishRequest,
    user: UserDep,
    service: ServiceDep,
    background_tasks: BackgroundTasks,
    scheduler: SchedulerDep,
) -> PublishAccepted:
    publish, job = service.create(owner_uid=user.uid, project_id=projectId, payload=payload)
    if job.status not in (JobStatus.succeeded, JobStatus.running):
        scheduler(
            background_tasks,
            owner_uid=user.uid,
            project_id=projectId,
            job_id=job.jobId,
        )
    return accepted(publish, job)


@router.get("/projects/{projectId}/publishes", response_model=PublishList)
async def list_publishes(
    projectId: str,
    user: UserDep,
    service: ServiceDep,
) -> PublishList:
    return PublishList(items=service.list(owner_uid=user.uid, project_id=projectId))


@router.get("/projects/{projectId}/publishes/{publishId}", response_model=Publish)
async def get_publish(
    projectId: str,
    publishId: str,
    user: UserDep,
    service: ServiceDep,
) -> Publish:
    return service.get(owner_uid=user.uid, project_id=projectId, publish_id=publishId)


@router.post(
    "/projects/{projectId}/publishes/{publishId}/retry",
    response_model=PublishAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_publish(
    projectId: str,
    publishId: str,
    user: UserDep,
    service: ServiceDep,
    background_tasks: BackgroundTasks,
    scheduler: SchedulerDep,
) -> PublishAccepted:
    publish, job = service.retry(
        owner_uid=user.uid, project_id=projectId, publish_id=publishId
    )
    if job.status not in (JobStatus.succeeded, JobStatus.running):
        scheduler(
            background_tasks,
            owner_uid=user.uid,
            project_id=projectId,
            job_id=job.jobId,
        )
    return accepted(publish, job)


@router.delete(
    "/projects/{projectId}/publishes/{publishId}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_publish(
    projectId: str,
    publishId: str,
    user: UserDep,
    service: ServiceDep,
) -> None:
    service.delete(owner_uid=user.uid, project_id=projectId, publish_id=publishId)
