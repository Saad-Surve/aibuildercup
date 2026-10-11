"""Publish endpoints: send a project's video, thumbnail, and captions to a connected channel."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, status

from app.dependencies import (
    AuthenticatedUser,
    PublishScheduler,
    current_user,
    get_publish_scheduler,
    get_publish_service,
    get_schedule_service,
)
from app.schemas.jobs import JobStatus
from app.schemas.publishes import (
    Publish,
    PublishAccepted,
    PublishList,
    PublishRequest,
)
from app.services.publish_service import PublishService, accepted
from app.services.schedule_service import ScheduleService

router = APIRouter(tags=["publishes"])

UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
ServiceDep = Annotated[PublishService, Depends(get_publish_service)]
SchedulesDep = Annotated[ScheduleService, Depends(get_schedule_service)]
SchedulerDep = Annotated[PublishScheduler, Depends(get_publish_scheduler)]


@router.post(
    "/projects/{projectId}/publishes",
    response_model=PublishAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_publish(
    projectId: str,
    payload: PublishRequest,
    user: UserDep,
    service: ServiceDep,
    background_tasks: BackgroundTasks,
    scheduler: SchedulerDep,
    schedules: SchedulesDep,
) -> PublishAccepted:
    publish, job = service.create(owner_uid=user.uid, project_id=projectId, payload=payload)
    if payload.publishAt is not None:
        # The upload carries a go-public time: mirror it onto the calendar so the
        # schedule and the publish stay one thing, not two.
        schedules.link_publish(
            owner_uid=user.uid,
            project_id=projectId,
            publish_id=publish.publishId,
            title=publish.title,
            scheduled_at=payload.publishAt,
            connection_id=publish.connectionId,
            connection_display_name=publish.connectionDisplayName,
            platform=publish.platform,
        )
    if job.status not in (JobStatus.succeeded, JobStatus.running):
        scheduler(
            background_tasks,
            owner_uid=user.uid,
            project_id=projectId,
            job_id=job.jobId,
        )
    return accepted(publish, job)


@router.get("/projects/{projectId}/publishes", response_model=PublishList)
def list_publishes(
    projectId: str,
    user: UserDep,
    service: ServiceDep,
) -> PublishList:
    return PublishList(items=service.list(owner_uid=user.uid, project_id=projectId))


@router.get("/projects/{projectId}/publishes/{publishId}", response_model=Publish)
def get_publish(
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
def retry_publish(
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
def delete_publish(
    projectId: str,
    publishId: str,
    user: UserDep,
    service: ServiceDep,
) -> None:
    service.delete(owner_uid=user.uid, project_id=projectId, publish_id=publishId)
