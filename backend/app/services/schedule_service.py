"""Content-calendar schedules: planned posting slots, project-scoped.

A schedule lives at `users/{uid}/projects/{projectId}/schedules/{scheduleId}`, so the
recursive project/account delete covers it with no extra wiring. The month view reads across
projects through `list_for_owner`, which fans out over the caller's projects (explicit reads,
no collection-group index to provision).

Two-way link with publishes: a schedule may point at a publish attempt (`publishId`).
Creating a linked entry and rescheduling one both move the publish's `publishAt`
(the worker reads it at upload time), and `PublishService.mark_status` flips linked
schedules to `published` / `failed` / `cancelled` as the upload resolves. A slot that
wants an upload but cannot be armed yet is `planned` with a `statusDetail` blocker;
the schedules API re-tries arming it on every read and write (see
`app/api/schedules.py`).
"""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.errors import ConflictError, NotFoundError
from app.schemas.publishes import PublishStatus
from app.schemas.schedules import (
    Schedule,
    ScheduleCreate,
    ScheduleStatus,
    ScheduleUpdate,
)
from app.services.firestore_service import (
    FirestoreClient,
    publish_path,
    schedule_path,
    schedules_collection_path,
)
from app.services.project_service import ProjectService

logger = logging.getLogger(__name__)

#: Nullable link fields: an explicit null clears the link, so it must survive the update.
_LINK_FIELDS = {"publishId", "connectionId"}


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _to_schedule(schedule_id: str, data: dict[str, Any]) -> Schedule:
    return Schedule(
        scheduleId=schedule_id,
        projectId=data.get("projectId", ""),
        projectName=data.get("projectName"),
        title=data.get("title", ""),
        notes=data.get("notes", ""),
        platform=data.get("platform", "youtube"),
        scheduledAt=data["scheduledAt"],
        status=ScheduleStatus(data.get("status", ScheduleStatus.planned.value)),
        statusDetail=data.get("statusDetail"),
        publishId=data.get("publishId"),
        connectionId=data.get("connectionId"),
        connectionDisplayName=data.get("connectionDisplayName"),
        createdAt=data["createdAt"],
        updatedAt=data["updatedAt"],
    )


class ScheduleService:
    def __init__(self, client: FirestoreClient, *, projects: ProjectService) -> None:
        self.client = client
        self.projects = projects

    # ------------------------------------------------------------------ create

    def create(
        self, *, owner_uid: str, project_id: str, payload: ScheduleCreate
    ) -> Schedule:
        project = self.projects.get(owner_uid=owner_uid, project_id=project_id)
        connection_name: str | None = None
        if payload.publishId:
            publish = self.client.get_document(
                publish_path(owner_uid, project_id, payload.publishId)
            )
            if publish is None or publish.get("ownerUid") != owner_uid:
                raise NotFoundError(
                    "Publish not found", details={"publishId": payload.publishId}
                )
            connection_name = publish.get("connectionDisplayName")
        # Status is automatic, never client-chosen: a slot wired to an upload waits
        # for it (`scheduled`), anything else starts blocked (`planned`) until the
        # schedules API arms it. Trusting a client `status` here once stranded
        # linked slots on `planned` with a live upload attached.
        status = (
            ScheduleStatus.scheduled if payload.publishId else ScheduleStatus.planned
        )
        schedule_id = uuid4().hex
        now = datetime.now(UTC)
        document: dict[str, Any] = {
            "ownerUid": owner_uid,
            "projectId": project_id,
            "projectName": project.name,
            "title": payload.title,
            "notes": payload.notes,
            "platform": payload.platform,
            "scheduledAt": _as_utc(payload.scheduledAt),
            "status": status.value,
            "statusDetail": None,
            "publishId": payload.publishId,
            "connectionId": payload.connectionId,
            "connectionDisplayName": connection_name,
            "createdAt": now,
            "updatedAt": now,
        }
        self.client.set_document(
            schedule_path(owner_uid, project_id, schedule_id), document
        )
        created = _to_schedule(schedule_id, document)
        if payload.publishId is not None:
            # Wiring a slot to an existing upload moves that upload's go-public
            # time, exactly like rescheduling a linked slot does. Without this
            # the calendar entry and the upload silently disagree.
            self._sync_linked_publish(owner_uid, project_id, created)
        return created

    def link_publish(
        self,
        *,
        owner_uid: str,
        project_id: str,
        publish_id: str,
        title: str,
        scheduled_at: datetime,
        connection_id: str | None,
        connection_display_name: str | None,
        platform: str = "youtube",
    ) -> Schedule:
        """Create the calendar entry for a publish that carries a `publishAt`.

        Called right after `PublishService.create`, so the new upload shows up on the
        calendar without the creator scheduling it twice.
        """
        project = self.projects.get(owner_uid=owner_uid, project_id=project_id)
        schedule_id = uuid4().hex
        now = datetime.now(UTC)
        document: dict[str, Any] = {
            "ownerUid": owner_uid,
            "projectId": project_id,
            "projectName": project.name,
            "title": title,
            "notes": "",
            "platform": platform,
            "scheduledAt": _as_utc(scheduled_at),
            "status": ScheduleStatus.scheduled.value,
            "statusDetail": None,
            "publishId": publish_id,
            "connectionId": connection_id,
            "connectionDisplayName": connection_display_name,
            "createdAt": now,
            "updatedAt": now,
        }
        self.client.set_document(
            schedule_path(owner_uid, project_id, schedule_id), document
        )
        return _to_schedule(schedule_id, document)

    # ------------------------------------------------------------------ read

    def list_for_project(self, *, owner_uid: str, project_id: str) -> list[Schedule]:
        self.projects.get(owner_uid=owner_uid, project_id=project_id)
        rows = self.client.query_collection(
            schedules_collection_path(owner_uid, project_id),
            filters=[],
            order_by=[("scheduledAt", "ASCENDING")],
            limit=200,
            offset=0,
        )
        return [
            _to_schedule(schedule_id, data)
            for schedule_id, data in rows
            if data.get("ownerUid") == owner_uid
        ]

    def list_for_owner(
        self,
        *,
        owner_uid: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Schedule]:
        """Every schedule across the caller's projects, oldest first.

        Fans out over the project list (explicit reads, no composite index) and applies
        the window in memory; 200 projects × 200 schedules bounds the read fan-out.
        """
        projects, _ = self.projects.list(owner_uid=owner_uid, limit=200, offset=0)
        items: list[Schedule] = []
        for project in projects:
            rows = self.client.query_collection(
                schedules_collection_path(owner_uid, project.projectId),
                filters=[],
                order_by=[("scheduledAt", "ASCENDING")],
                limit=200,
                offset=0,
            )
            items.extend(
                _to_schedule(schedule_id, data)
                for schedule_id, data in rows
                if data.get("ownerUid") == owner_uid
            )
        if start is not None:
            floor = _as_utc(start)
            items = [item for item in items if _as_utc(item.scheduledAt) >= floor]
        if end is not None:
            ceiling = _as_utc(end)
            items = [item for item in items if _as_utc(item.scheduledAt) <= ceiling]
        items.sort(key=lambda item: _as_utc(item.scheduledAt))
        return items

    def get(self, *, owner_uid: str, project_id: str, schedule_id: str) -> Schedule:
        return _to_schedule(schedule_id, self._require(owner_uid, project_id, schedule_id))

    # ------------------------------------------------------------------ write

    def update(
        self, *, owner_uid: str, project_id: str, schedule_id: str, patch: ScheduleUpdate
    ) -> Schedule:
        data = self._require(owner_uid, project_id, schedule_id)
        raw = patch.model_dump(exclude_unset=True)
        changes: dict[str, Any] = {
            key: value
            for key, value in raw.items()
            if value is not None or key in _LINK_FIELDS
        }
        if "scheduledAt" in changes and isinstance(changes["scheduledAt"], datetime):
            changes["scheduledAt"] = _as_utc(changes["scheduledAt"])
        if "publishId" in changes and changes["publishId"] is not None:
            publish = self.client.get_document(
                publish_path(owner_uid, project_id, changes["publishId"])
            )
            if publish is None or publish.get("ownerUid") != owner_uid:
                raise NotFoundError(
                    "Publish not found", details={"publishId": changes["publishId"]}
                )
            if "connectionDisplayName" not in changes:
                changes["connectionDisplayName"] = publish.get("connectionDisplayName")
        moved = "scheduledAt" in changes
        if changes:
            # Validate + move the linked publish BEFORE writing the slot, so a
            # conflict (a live post) never half-applies a new time.
            if moved:
                self._sync_linked_publish(
                    owner_uid, project_id, _to_schedule(schedule_id, {**data, **changes})
                )
            changes["updatedAt"] = datetime.now(UTC)
            self.client.update_document(
                schedule_path(owner_uid, project_id, schedule_id), changes
            )
            data.update(changes)
        return _to_schedule(schedule_id, data)

    def delete(self, *, owner_uid: str, project_id: str, schedule_id: str) -> None:
        self._require(owner_uid, project_id, schedule_id)
        self.client.delete_document(schedule_path(owner_uid, project_id, schedule_id))

    # ------------------------------------------------------------------ publish sync

    def _sync_linked_publish(
        self, owner_uid: str, project_id: str, schedule: Schedule
    ) -> None:
        """Move a linked publish's `publishAt` when its calendar entry moves.

        The publish worker reads `publishAt` at upload time, so a queued publish picks up
        the new slot with no re-queue. A finished publish cannot be moved.
        """
        if schedule.publishId is None:
            return
        path = publish_path(owner_uid, project_id, schedule.publishId)
        publish = self.client.get_document(path)
        if publish is None or publish.get("ownerUid") != owner_uid:
            # The upload record is gone; nothing to move (a rescheduled slot will
            # get a fresh upload via the schedules API).
            logger.warning(
                "schedule: linked publish %s is missing; nothing to sync",
                schedule.publishId,
            )
            return
        if publish.get("status") == PublishStatus.published.value:
            raise ConflictError(
                "This video already published; its calendar slot is history.",
                code="SCHEDULE_PUBLISH_FINISHED",
                details={"publishId": schedule.publishId},
            )
        self.client.update_document(
            path,
            {"publishAt": _as_utc(schedule.scheduledAt), "updatedAt": datetime.now(UTC)},
        )

    def mark_linked_published(
        self, *, owner_uid: str, project_id: str, publish_id: str
    ) -> None:
        """Flip linked calendar entries to `published` once their upload finishes."""
        rows = self.client.query_collection(
            schedules_collection_path(owner_uid, project_id),
            filters=[("publishId", "==", publish_id)],
            order_by=[],
            limit=50,
            offset=0,
        )
        now = datetime.now(UTC)
        for schedule_id, data in rows:
            if data.get("ownerUid") != owner_uid:
                continue
            if data.get("status") == ScheduleStatus.published.value:
                continue
            try:
                self.client.update_document(
                    schedule_path(owner_uid, project_id, schedule_id),
                    {
                        "status": ScheduleStatus.published.value,
                        "statusDetail": None,
                        "updatedAt": now,
                    },
                )
            except Exception:  # noqa: BLE001 - a calendar write must not fail the publish
                logger.warning(
                    "schedule: could not mark %s published for publish %s",
                    schedule_id,
                    publish_id,
                )

    def mark_linked_cancelled(
        self, *, owner_uid: str, project_id: str, publish_id: str
    ) -> None:
        """Cancel linked calendar entries when a live video is deleted on YouTube."""
        rows = self.client.query_collection(
            schedules_collection_path(owner_uid, project_id),
            filters=[("publishId", "==", publish_id)],
            order_by=[],
            limit=50,
            offset=0,
        )
        now = datetime.now(UTC)
        for schedule_id, data in rows:
            if data.get("ownerUid") != owner_uid:
                continue
            if data.get("status") == ScheduleStatus.cancelled.value:
                continue
            try:
                self.client.update_document(
                    schedule_path(owner_uid, project_id, schedule_id),
                    {
                        "status": ScheduleStatus.cancelled.value,
                        "statusDetail": None,
                        "updatedAt": now,
                    },
                )
            except Exception:  # noqa: BLE001 - a calendar write must not fail the publish
                logger.warning(
                    "schedule: could not cancel %s for deleted publish %s",
                    schedule_id,
                    publish_id,
                )

    def relink_publish(
        self,
        *,
        owner_uid: str,
        project_id: str,
        schedule_id: str,
        publish_id: str,
        connection_id: str | None,
        connection_display_name: str | None,
    ) -> None:
        """Point an existing slot at a freshly re-created upload, back to scheduled."""
        self._require(owner_uid, project_id, schedule_id)
        self.client.update_document(
            schedule_path(owner_uid, project_id, schedule_id),
            {
                "publishId": publish_id,
                "connectionId": connection_id,
                "connectionDisplayName": connection_display_name,
                "status": ScheduleStatus.scheduled.value,
                "statusDetail": None,
                "updatedAt": datetime.now(UTC),
            },
        )

    def mark_linked_failed(
        self, *, owner_uid: str, project_id: str, publish_id: str, message: str | None
    ) -> None:
        """Flip linked calendar entries to `failed` when their upload dies.

        Without this a failed upload left its slot on `scheduled` forever, telling
        the creator a go-live was still coming when nothing was.
        """
        rows = self.client.query_collection(
            schedules_collection_path(owner_uid, project_id),
            filters=[("publishId", "==", publish_id)],
            order_by=[],
            limit=50,
            offset=0,
        )
        now = datetime.now(UTC)
        for schedule_id, data in rows:
            if data.get("ownerUid") != owner_uid:
                continue
            if data.get("status") in (
                ScheduleStatus.published.value,
                ScheduleStatus.cancelled.value,
            ):
                continue
            try:
                self.client.update_document(
                    schedule_path(owner_uid, project_id, schedule_id),
                    {
                        "status": ScheduleStatus.failed.value,
                        "statusDetail": message or "The upload failed.",
                        "updatedAt": now,
                    },
                )
            except Exception:  # noqa: BLE001 - a calendar write must not fail the publish
                logger.warning(
                    "schedule: could not mark %s failed for publish %s",
                    schedule_id,
                    publish_id,
                )

    def mark_linked_scheduled(
        self, *, owner_uid: str, project_id: str, publish_id: str
    ) -> None:
        """Back to `scheduled` when a failed upload is retried."""
        rows = self.client.query_collection(
            schedules_collection_path(owner_uid, project_id),
            filters=[("publishId", "==", publish_id)],
            order_by=[],
            limit=50,
            offset=0,
        )
        now = datetime.now(UTC)
        for schedule_id, data in rows:
            if data.get("ownerUid") != owner_uid:
                continue
            if data.get("status") != ScheduleStatus.failed.value:
                continue
            try:
                self.client.update_document(
                    schedule_path(owner_uid, project_id, schedule_id),
                    {
                        "status": ScheduleStatus.scheduled.value,
                        "statusDetail": None,
                        "updatedAt": now,
                    },
                )
            except Exception:  # noqa: BLE001 - a calendar write must not fail the retry
                logger.warning(
                    "schedule: could not reschedule %s for retried publish %s",
                    schedule_id,
                    publish_id,
                )

    def unlink_publish(self, *, owner_uid: str, project_id: str, publish_id: str) -> None:
        """Detach slots from a publish that was deleted in the app.

        Without this a deleted upload leaves its slot `scheduled` forever, pointing
        at a record that no longer exists. Unlinked slots go back to `planned`
        (`failed` once their time has passed) with an explanation, so editing or
        simply reading them re-arms a fresh upload.
        """
        rows = self.client.query_collection(
            schedules_collection_path(owner_uid, project_id),
            filters=[("publishId", "==", publish_id)],
            order_by=[],
            limit=50,
            offset=0,
        )
        now = datetime.now(UTC)
        for schedule_id, data in rows:
            if data.get("ownerUid") != owner_uid:
                continue
            if data.get("status") in (
                ScheduleStatus.published.value,
                ScheduleStatus.cancelled.value,
            ):
                continue
            moment = data.get("scheduledAt")
            past_due = (
                _as_utc(moment).astimezone(UTC) <= now
                if isinstance(moment, datetime)
                else False
            )
            try:
                self.client.update_document(
                    schedule_path(owner_uid, project_id, schedule_id),
                    {
                        "publishId": None,
                        "connectionId": None,
                        "connectionDisplayName": None,
                        "status": (
                            ScheduleStatus.failed.value
                            if past_due
                            else ScheduleStatus.planned.value
                        ),
                        "statusDetail": (
                            "Its upload was deleted — edit this slot to schedule "
                            "a fresh upload."
                        ),
                        "updatedAt": now,
                    },
                )
            except Exception:  # noqa: BLE001 - the publish delete already succeeded
                logger.warning(
                    "schedule: could not unlink %s from deleted publish %s",
                    schedule_id,
                    publish_id,
                )

    def mark_blocked(
        self, *, owner_uid: str, schedule: Schedule, detail: str, past_due: bool
    ) -> bool:
        """Record why an unarmed slot is not uploading. Returns True on a change.

        A blocked slot whose time is still ahead stays `planned` (it can arm the
        moment the blocker clears); one whose time already passed is `failed`.
        No-ops when nothing changed, so the read-triggered sweep does not rewrite
        the same explanation on every calendar poll.
        """
        next_status = (
            ScheduleStatus.failed.value if past_due else ScheduleStatus.planned.value
        )
        if (
            schedule.status.value == next_status
            and (schedule.statusDetail or None) == detail
        ):
            return False
        self.client.update_document(
            schedule_path(owner_uid, schedule.projectId, schedule.scheduleId),
            {"status": next_status, "statusDetail": detail, "updatedAt": datetime.now(UTC)},
        )
        return True

    def _require(
        self, owner_uid: str, project_id: str, schedule_id: str
    ) -> dict[str, Any]:
        self.projects.get(owner_uid=owner_uid, project_id=project_id)
        data = self.client.get_document(schedule_path(owner_uid, project_id, schedule_id))
        if data is None or data.get("ownerUid") != owner_uid:
            raise NotFoundError("Schedule not found", details={"scheduleId": schedule_id})
        return data
