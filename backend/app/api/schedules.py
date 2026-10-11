"""Content-calendar endpoints: planned posting slots across projects."""

import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status

from app.dependencies import (
    AuthenticatedUser,
    PublishScheduler,
    current_user,
    get_publish_scheduler,
    get_publish_service,
    get_schedule_service,
)
from app.errors import NotFoundError
from app.schemas.publishes import PublishStatus
from app.schemas.schedules import (
    Schedule,
    ScheduleCreate,
    ScheduleList,
    ScheduleUpdate,
)
from app.services.publish_service import PublishService
from app.services.schedule_service import ScheduleService

router = APIRouter(tags=["schedules"])
logger = logging.getLogger(__name__)

UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
ServiceDep = Annotated[ScheduleService, Depends(get_schedule_service)]
PublishesDep = Annotated[PublishService, Depends(get_publish_service)]
SchedulerDep = Annotated[PublishScheduler, Depends(get_publish_scheduler)]


@router.get("/schedules", response_model=ScheduleList)
def list_schedules(
    user: UserDep,
    service: ServiceDep,
    publishes: PublishesDep,
    start: Annotated[datetime | None, Query()] = None,
    end: Annotated[datetime | None, Query()] = None,
) -> ScheduleList:
    items = service.list_for_owner(owner_uid=user.uid, start=start, end=end)
    if any(item.publishId for item in items):
        _reconcile_linked_uploads(user.uid, items, publishes)
        items = service.list_for_owner(owner_uid=user.uid, start=start, end=end)
    return ScheduleList(items=items)


@router.get("/projects/{projectId}/schedules", response_model=ScheduleList)
def list_project_schedules(
    projectId: str,
    user: UserDep,
    service: ServiceDep,
    publishes: PublishesDep,
) -> ScheduleList:
    items = service.list_for_project(owner_uid=user.uid, project_id=projectId)
    if any(item.publishId for item in items):
        _reconcile_linked_uploads(user.uid, items, publishes)
        items = service.list_for_project(owner_uid=user.uid, project_id=projectId)
    return ScheduleList(items=items)


@router.post(
    "/projects/{projectId}/schedules",
    response_model=Schedule,
    status_code=status.HTTP_201_CREATED,
)
async def create_schedule(
    projectId: str,
    payload: ScheduleCreate,
    user: UserDep,
    service: ServiceDep,
) -> Schedule:
    return service.create(owner_uid=user.uid, project_id=projectId, payload=payload)


@router.patch("/projects/{projectId}/schedules/{scheduleId}", response_model=Schedule)
def update_schedule(
    projectId: str,
    scheduleId: str,
    payload: ScheduleUpdate,
    user: UserDep,
    service: ServiceDep,
    publishes: PublishesDep,
    background_tasks: BackgroundTasks,
    scheduler: SchedulerDep,
) -> Schedule:
    updated = service.update(
        owner_uid=user.uid, project_id=projectId, schedule_id=scheduleId, patch=payload
    )
    if updated.publishId:
        updated = _revive_slot_upload(
            slot=updated,
            owner_uid=user.uid,
            project_id=projectId,
            schedules=service,
            publishes=publishes,
            background_tasks=background_tasks,
            scheduler=scheduler,
        )
    return updated


@router.delete(
    "/projects/{projectId}/schedules/{scheduleId}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_schedule(
    projectId: str,
    scheduleId: str,
    user: UserDep,
    service: ServiceDep,
) -> None:
    service.delete(owner_uid=user.uid, project_id=projectId, schedule_id=scheduleId)


def _reconcile_linked_uploads(
    owner_uid: str, items: list[Schedule], publishes: PublishService
) -> None:
    """Reconcile live videos when the calendar is read.

    The publishing studio already reconciles, but the calendar should not depend
    on it: deleting a video on YouTube must flip its slot here too. `list` runs
    the (throttled, batched) deletion check and cancels linked slots.
    """
    project_ids = sorted({item.projectId for item in items if item.publishId})
    for project_id in project_ids:
        try:
            publishes.list(owner_uid=owner_uid, project_id=project_id)
        except Exception:  # noqa: BLE001 - the calendar must still render
            logger.warning(
                "calendar: reconcile failed for project %s", project_id, exc_info=True
            )


def _revive_slot_upload(
    *,
    slot: Schedule,
    owner_uid: str,
    project_id: str,
    schedules: ScheduleService,
    publishes: PublishService,
    background_tasks: BackgroundTasks,
    scheduler: PublishScheduler,
) -> Schedule:
    """Keep a rescheduled slot pointed at a live upload.

    A slot whose linked upload is gone (`deleted`/`failed`) gets a fresh upload
    for the new time, so rescheduling actually re-uploads instead of only moving
    a dead record's go-public field. A still-waiting upload is rescheduled on
    YouTube so its real go-live matches the new slot time.
    """
    publish_id = slot.publishId
    if not publish_id:
        return slot
    try:
        publish = publishes.load(
            owner_uid=owner_uid, project_id=project_id, publish_id=publish_id
        )
    except NotFoundError:
        publish = None
    if publish is None:
        return slot

    current = publish.get("status")
    if current in (PublishStatus.deleted.value, PublishStatus.failed.value):
        fresh, job = publishes.recreate_for_schedule(
            owner_uid=owner_uid,
            project_id=project_id,
            source=publish,
            publish_at=slot.scheduledAt,
        )
        schedules.relink_publish(
            owner_uid=owner_uid,
            project_id=project_id,
            schedule_id=slot.scheduleId,
            publish_id=fresh.publishId,
            connection_id=fresh.connectionId,
            connection_display_name=fresh.connectionDisplayName,
        )
        scheduler(
            background_tasks,
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job.jobId,
        )
        return schedules.get(
            owner_uid=owner_uid, project_id=project_id, schedule_id=slot.scheduleId
        )

    if current in (
        PublishStatus.queued.value,
        PublishStatus.uploading.value,
        PublishStatus.processing.value,
    ) and publish.get("youtubeVideoId"):
        background_tasks.add_task(
            publishes.reschedule_on_youtube,
            owner_uid=owner_uid,
            project_id=project_id,
            publish_id=publish_id,
        )
    return slot
