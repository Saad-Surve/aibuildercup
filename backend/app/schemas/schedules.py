"""Calendar entries for the content calendar.

One *schedule* is one slot on the calendar: what will be posted, from which project, and
when. A YouTube slot is meant to produce a real upload: the API arms it (creates the linked
publish) at create time and retries whenever the slot is read or edited, so `planned` only
means "blocked right now" — `statusDetail` says exactly what is missing. When linked,
rescheduling the calendar entry also moves the publish's `publishAt`, a publish that
finishes flips its linked schedules to `published`, and one that fails flips them to
`failed`. Records live under the project subtree, so the recursive project/account delete
covers them.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ScheduleStatus(StrEnum):
    #: Wants to upload but is blocked right now; `statusDetail` says by what.
    planned = "planned"
    #: Armed: a linked publish is uploaded (or uploading) and waits to go out.
    scheduled = "scheduled"
    #: The linked publish went out.
    published = "published"
    #: The upload failed, or the slot time passed while it was still blocked.
    failed = "failed"
    #: Called off; kept for the record.
    cancelled = "cancelled"


class ScheduleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    notes: str = Field(default="", max_length=2000)
    #: Target platform, e.g. `youtube`. Free-form so new platforms need no migration.
    platform: str = Field(default="youtube", max_length=40)
    scheduledAt: datetime
    #: Link to a publish attempt; set when the slot is wired to a real upload.
    publishId: str | None = Field(default=None, max_length=200)
    connectionId: str | None = Field(default=None, max_length=200)


class ScheduleUpdate(BaseModel):
    #: Status is automatic (planned/scheduled/published/failed/cancelled follow the
    #: linked upload), so it is deliberately not patchable — there is no field for it.
    title: str | None = Field(default=None, min_length=1, max_length=140)
    notes: str | None = Field(default=None, max_length=2000)
    platform: str | None = Field(default=None, max_length=40)
    scheduledAt: datetime | None = None
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
    #: Why a `planned`/`failed` slot is not uploading (channel missing, no source
    #: video, the publish error). Null while everything is on track.
    statusDetail: str | None = None
    publishId: str | None = None
    connectionId: str | None = None
    connectionDisplayName: str | None = None
    createdAt: datetime
    updatedAt: datetime


class ScheduleList(BaseModel):
    items: list[Schedule]
