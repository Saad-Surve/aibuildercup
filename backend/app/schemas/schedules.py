"""Planned calendar entries for the content calendar.

One *schedule* is one slot on the calendar: what will be posted, from which project, and
when. A schedule may stand alone (a rough plan) or link to a publish attempt (`publishId`);
when linked, rescheduling the calendar entry also moves the publish's `publishAt`, and a
publish that finishes flips its linked schedules to `published`. Records live under the
project subtree, so the recursive project/account delete covers them.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ScheduleStatus(StrEnum):
    #: A rough plan with no publish wired up yet.
    planned = "planned"
    #: Has a date and (usually) a linked publish waiting to go out.
    scheduled = "scheduled"
    #: The linked publish went out.
    published = "published"
    #: Called off; kept for the record.
    cancelled = "cancelled"


class ScheduleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    notes: str = Field(default="", max_length=2000)
    #: Target platform, e.g. `youtube`. Free-form so new platforms need no migration.
    platform: str = Field(default="youtube", max_length=40)
    scheduledAt: datetime
    status: ScheduleStatus = ScheduleStatus.planned
    #: Link to a publish attempt; set when the slot is wired to a real upload.
    publishId: str | None = Field(default=None, max_length=200)
    connectionId: str | None = Field(default=None, max_length=200)


class ScheduleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=140)
    notes: str | None = Field(default=None, max_length=2000)
    platform: str | None = Field(default=None, max_length=40)
    scheduledAt: datetime | None = None
    status: ScheduleStatus | None = None
    #: Explicit null unlinks the publish; omitted keeps the current link.
    publishId: str | None = Field(default=None, max_length=200)
    connectionId: str | None = Field(default=None, max_length=200)


class Schedule(BaseModel):
    scheduleId: str
    projectId: str
    #: Snapshot of the project name at create time, so the calendar renders without a join.
    projectName: str | None = None
    title: str
    notes: str = ""
    platform: str = "youtube"
    scheduledAt: datetime
    status: ScheduleStatus
    publishId: str | None = None
    connectionId: str | None = None
    connectionDisplayName: str | None = None
    createdAt: datetime
    updatedAt: datetime


class ScheduleList(BaseModel):
    items: list[Schedule]
