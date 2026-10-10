"""Content-calendar endpoints: planned posting slots across projects."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.dependencies import (
    AuthenticatedUser,
    current_user,
    get_schedule_service,
)
from app.schemas.schedules import (
    Schedule,
    ScheduleCreate,
    ScheduleList,
    ScheduleUpdate,
)
from app.services.schedule_service import ScheduleService

router = APIRouter(tags=["schedules"])

UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
ServiceDep = Annotated[ScheduleService, Depends(get_schedule_service)]


@router.get("/schedules", response_model=ScheduleList)
async def list_schedules(
    user: UserDep,
    service: ServiceDep,
    start: Annotated[datetime | None, Query()] = None,
    end: Annotated[datetime | None, Query()] = None,
) -> ScheduleList:
    return ScheduleList(
        items=service.list_for_owner(owner_uid=user.uid, start=start, end=end)
    )


@router.get("/projects/{projectId}/schedules", response_model=ScheduleList)
async def list_project_schedules(
    projectId: str,
    user: UserDep,
    service: ServiceDep,
) -> ScheduleList:
    return ScheduleList(
        items=service.list_for_project(owner_uid=user.uid, project_id=projectId)
    )


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
async def update_schedule(
    projectId: str,
    scheduleId: str,
    payload: ScheduleUpdate,
    user: UserDep,
    service: ServiceDep,
) -> Schedule:
    return service.update(
        owner_uid=user.uid, project_id=projectId, schedule_id=scheduleId, patch=payload
    )


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
