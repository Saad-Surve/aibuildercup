"""Content-calendar endpoints: every slot is a real upload intent.

A YouTube slot is *armed* — wired to a publish that uploads right away and goes
public at the slot time — when it is created, and re-armed on every read, edit,
and poll until it sticks. A slot that cannot be armed yet stays `planned` (or
turns `failed` once its time passes) with `statusDetail` naming the blocker, so
the calendar never silently promises a go-live that is not coming.
"""

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status

from app.dependencies import (
    AuthenticatedUser,
    PublishScheduler,
    current_user,
    get_connection_service,
    get_publish_scheduler,
    get_publish_service,
    get_schedule_service,
)
from app.errors import AppError, NotFoundError
from app.schemas.connections import ConnectionStatus
from app.schemas.jobs import Job
from app.schemas.publishes import (
    PublishCaptionFormat,
    PublishRequest,
    PublishSourceKind,
    PublishStatus,
    PublishVideoSource,
    PublishVisibility,
)
from app.schemas.schedules import (
    Schedule,
    ScheduleCreate,
    ScheduleList,
    ScheduleStatus,
    ScheduleUpdate,
)
from app.services.connection_service import ConnectionService
from app.services.publish_service import PublishService
from app.services.schedule_service import ScheduleService

router = APIRouter(tags=["schedules"])
logger = logging.getLogger(__name__)

UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
ServiceDep = Annotated[ScheduleService, Depends(get_schedule_service)]
PublishesDep = Annotated[PublishService, Depends(get_publish_service)]
ConnectionsDep = Annotated[ConnectionService, Depends(get_connection_service)]
SchedulerDep = Annotated[PublishScheduler, Depends(get_publish_scheduler)]


@router.get("/schedules", response_model=ScheduleList)
def list_schedules(
    user: UserDep,
    service: ServiceDep,
    publishes: PublishesDep,
    connections: ConnectionsDep,
    background_tasks: BackgroundTasks,
    scheduler: SchedulerDep,
    start: Annotated[datetime | None, Query()] = None,
    end: Annotated[datetime | None, Query()] = None,
) -> ScheduleList:
    items = service.list_for_owner(owner_uid=user.uid, start=start, end=end)
    changed = _sweep_slots(
        items,
        owner_uid=user.uid,
        schedules=service,
        publishes=publishes,
        connections=connections,
        background_tasks=background_tasks,
        scheduler=scheduler,
    )
    if any(item.publishId for item in items):
        changed |= _reconcile_linked_uploads(user.uid, items, publishes)
    if changed:
        items = service.list_for_owner(owner_uid=user.uid, start=start, end=end)
    return ScheduleList(items=items)


@router.get("/projects/{projectId}/schedules", response_model=ScheduleList)
def list_project_schedules(
    projectId: str,
    user: UserDep,
    service: ServiceDep,
    publishes: PublishesDep,
    connections: ConnectionsDep,
    background_tasks: BackgroundTasks,
    scheduler: SchedulerDep,
) -> ScheduleList:
    items = service.list_for_project(owner_uid=user.uid, project_id=projectId)
    changed = _sweep_slots(
        items,
        owner_uid=user.uid,
        schedules=service,
        publishes=publishes,
        connections=connections,
        background_tasks=background_tasks,
        scheduler=scheduler,
    )
    if any(item.publishId for item in items):
        changed |= _reconcile_linked_uploads(user.uid, items, publishes)
    if changed:
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
    publishes: PublishesDep,
    connections: ConnectionsDep,
    background_tasks: BackgroundTasks,
    scheduler: SchedulerDep,
) -> Schedule:
    created = service.create(owner_uid=user.uid, project_id=projectId, payload=payload)
    if created.publishId is None and created.platform == "youtube":
        job, _ = _arm_or_explain(
            slot=created,
            owner_uid=user.uid,
            schedules=service,
            publishes=publishes,
            connections=connections,
        )
        if job is not None:
            scheduler(
                background_tasks,
                owner_uid=user.uid,
                project_id=projectId,
                job_id=job.jobId,
            )
        created = service.get(
            owner_uid=user.uid, project_id=projectId, schedule_id=created.scheduleId
        )
    return created


@router.patch("/projects/{projectId}/schedules/{scheduleId}", response_model=Schedule)
def update_schedule(
    projectId: str,
    scheduleId: str,
    payload: ScheduleUpdate,
    user: UserDep,
    service: ServiceDep,
    publishes: PublishesDep,
    connections: ConnectionsDep,
    background_tasks: BackgroundTasks,
    scheduler: SchedulerDep,
) -> Schedule:
    old_publish_id: str | None = None
    if "publishId" in payload.model_dump(exclude_unset=True) and payload.publishId is None:
        # Explicit unlink: remember the old upload so it can be called off below.
        try:
            old_publish_id = service.get(
                owner_uid=user.uid, project_id=projectId, schedule_id=scheduleId
            ).publishId
        except NotFoundError:
            # service.update below raises the 404 itself.
            old_publish_id = None
    updated = service.update(
        owner_uid=user.uid, project_id=projectId, schedule_id=scheduleId, patch=payload
    )
    if old_publish_id and updated.publishId is None:
        # Unlinked on purpose: the old upload must not fire without a slot.
        _call_off_pending_upload(
            publishes, owner_uid=user.uid, project_id=projectId, publish_id=old_publish_id
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
    elif updated.platform == "youtube" and updated.status in (
        ScheduleStatus.planned,
        ScheduleStatus.failed,
    ):
        # An unarmed slot that is edited re-tries arming on the spot: editing a
        # blocked slot (or moving a failed one to a new time) is the creator
        # saying "make this work now".
        job, _ = _arm_or_explain(
            slot=updated,
            owner_uid=user.uid,
            schedules=service,
            publishes=publishes,
            connections=connections,
        )
        if job is not None:
            scheduler(
                background_tasks,
                owner_uid=user.uid,
                project_id=projectId,
                job_id=job.jobId,
            )
        updated = service.get(
            owner_uid=user.uid, project_id=projectId, schedule_id=scheduleId
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
    publishes: PublishesDep,
) -> None:
    slot = service.get(owner_uid=user.uid, project_id=projectId, schedule_id=scheduleId)
    if slot.publishId:
        # Deleting the slot calls off the upload with it — otherwise a queued
        # publish fires later with no calendar entry and no way to explain it.
        # Once the video is on YouTube the publish record stays in the studio as
        # history (deleting a calendar entry never deletes a video).
        _call_off_pending_upload(
            publishes, owner_uid=user.uid, project_id=projectId, publish_id=slot.publishId
        )
    service.delete(owner_uid=user.uid, project_id=projectId, schedule_id=scheduleId)


def _call_off_pending_upload(
    publishes: PublishService, *, owner_uid: str, project_id: str, publish_id: str
) -> None:
    """Delete a linked upload that has not reached YouTube yet, if any.

    Shared by slot delete and explicit unlink: a queued publish must not fire
    after its calendar entry is gone. Missing/already-out publishes are left
    alone (a calendar delete never deletes a video).
    """
    try:
        publish = publishes.load(
            owner_uid=owner_uid, project_id=project_id, publish_id=publish_id
        )
    except NotFoundError:
        return
    if (
        not publish.get("youtubeVideoId")
        and publish.get("status")
        not in (PublishStatus.published.value, PublishStatus.deleted.value)
    ):
        publishes.delete(owner_uid=owner_uid, project_id=project_id, publish_id=publish_id)


def _reconcile_linked_uploads(
    owner_uid: str, items: list[Schedule], publishes: PublishService
) -> bool:
    """Reconcile live videos when the calendar is read.

    The publishing studio already reconciles, but the calendar should not depend
    on it: deleting a video on YouTube must flip its slot here too. `list` runs
    the (throttled, batched) deletion check and cancels linked slots. Returns True
    when any linked project was checked, so the caller re-reads before responding.
    """
    project_ids = sorted({item.projectId for item in items if item.publishId})
    for project_id in project_ids:
        try:
            publishes.list(owner_uid=owner_uid, project_id=project_id)
        except Exception:  # noqa: BLE001 - the calendar must still render
            logger.warning(
                "calendar: reconcile failed for project %s", project_id, exc_info=True
            )
    return bool(project_ids)


def _arm_or_explain(
    *,
    slot: Schedule,
    owner_uid: str,
    schedules: ScheduleService,
    publishes: PublishService,
    connections: ConnectionService,
) -> tuple[Job | None, bool]:
    """Wire an unarmed YouTube slot to a real upload, or record why not.

    Returns (job, changed): the queued job when the slot armed, and whether the
    slot document moved (armed, or its blocker/status changed). Otherwise the
    slot keeps (or regains) `planned` — `failed` once its time has passed — with
    `statusDetail` naming the blocker, so the calendar and the notification
    watcher can tell the creator exactly what is missing instead of silently
    skipping the upload.
    """
    # The sweep arms from a possibly stale list snapshot, and two calendar reads
    # can overlap: re-load the slot so a second armer sees the first one's link
    # instead of queueing a duplicate upload that relink would then orphan.
    try:
        fresh = schedules.get(
            owner_uid=owner_uid,
            project_id=slot.projectId,
            schedule_id=slot.scheduleId,
        )
    except NotFoundError:
        return None, False
    if fresh.publishId is not None:
        return None, True
    slot = fresh
    detail: str | None = None
    job: Job | None = None
    channel = next(
        (
            connection
            for connection in connections.list(owner_uid=owner_uid)
            if connection.platform == "youtube"
            and connection.status == ConnectionStatus.connected
        ),
        None,
    )
    if channel is None:
        detail = "Connect a YouTube channel under Accounts so this slot can upload."
    else:
        project = schedules.projects.get(owner_uid=owner_uid, project_id=slot.projectId)
        if not project.sourceAssetId:
            detail = (
                f'Add a source video to "{project.name}" so there is something to upload.'
            )
        else:
            try:
                publish, job = publishes.create(
                    owner_uid=owner_uid,
                    project_id=slot.projectId,
                    payload=PublishRequest(
                        connectionId=channel.connectionId,
                        video=PublishVideoSource(kind=PublishSourceKind.source, id=None),
                        title=slot.title,
                        description="",
                        privacyStatus=PublishVisibility.private,
                        captionFormat=PublishCaptionFormat.none,
                        publishAt=slot.scheduledAt,
                    ),
                )
            except AppError as exc:
                logger.warning("schedule: arming %s failed: %s", slot.scheduleId, exc)
                detail = exc.message
                job = None
            else:
                schedules.relink_publish(
                    owner_uid=owner_uid,
                    project_id=slot.projectId,
                    schedule_id=slot.scheduleId,
                    publish_id=publish.publishId,
                    connection_id=publish.connectionId,
                    connection_display_name=publish.connectionDisplayName,
                )
    if job is not None:
        return job, True
    if detail:
        moment = slot.scheduledAt
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        past_due = moment.astimezone(UTC) <= datetime.now(UTC)
        changed = schedules.mark_blocked(
            owner_uid=owner_uid,
            schedule=slot,
            detail=detail,
            past_due=past_due,
        )
        return None, changed
    return None, False


def _sweep_slots(
    items: list[Schedule],
    *,
    owner_uid: str,
    schedules: ScheduleService,
    publishes: PublishService,
    connections: ConnectionService,
    background_tasks: BackgroundTasks,
    scheduler: PublishScheduler,
) -> bool:
    """Read-triggered watchdog for the calendar.

    - `planned`/`failed` YouTube slots re-try arming (a channel connected or a
      source video added since the last read takes effect immediately), and are
      marked `failed` once their time passes with the blocker still in place.
    - A `scheduled` slot whose upload is stuck `queued` past its go-public time
      (the worker died with the server) is fired again; the worker is idempotent.

    Returns True when any slot changed, so the caller re-reads before responding.
    """
    changed = False
    now = datetime.now(UTC)
    for slot in items:
        if (
            slot.publishId is None
            and slot.platform == "youtube"
            and slot.status in (ScheduleStatus.planned, ScheduleStatus.failed)
        ):
            try:
                job, armed_or_moved = _arm_or_explain(
                    slot=slot,
                    owner_uid=owner_uid,
                    schedules=schedules,
                    publishes=publishes,
                    connections=connections,
                )
            except Exception:  # noqa: BLE001 - the calendar must still render
                logger.warning(
                    "calendar: sweep could not arm %s", slot.scheduleId, exc_info=True
                )
                continue
            if job is not None:
                scheduler(
                    background_tasks,
                    owner_uid=owner_uid,
                    project_id=slot.projectId,
                    job_id=job.jobId,
                )
            changed |= armed_or_moved
            continue
        if slot.publishId and slot.status == ScheduleStatus.scheduled:
            try:
                publish = publishes.load(
                    owner_uid=owner_uid,
                    project_id=slot.projectId,
                    publish_id=slot.publishId,
                )
            except NotFoundError:
                continue
            moment = publish.get("publishAt")
            if not isinstance(moment, datetime):
                continue
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=UTC)
            stuck = (
                publish.get("status") == PublishStatus.queued.value
                and moment.astimezone(UTC) <= now
            )
            if stuck and publish.get("jobId"):
                logger.info(
                    "calendar: re-firing stuck publish %s for slot %s",
                    slot.publishId,
                    slot.scheduleId,
                )
                scheduler(
                    background_tasks,
                    owner_uid=owner_uid,
                    project_id=slot.projectId,
                    job_id=str(publish["jobId"]),
                )
            elif publish.get("status") == PublishStatus.failed.value:
                # Backstop: normally `mark_status` flips the slot at failure time.
                schedules.mark_linked_failed(
                    owner_uid=owner_uid,
                    project_id=slot.projectId,
                    publish_id=slot.publishId,
                    message=(publish.get("error") or {}).get("message"),
                )
                changed = True
    return changed


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
