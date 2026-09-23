"""Job records: creation with idempotency and lookup by id.

Jobs are stored under `users/{uid}/projects/{projectId}/jobs/{jobId}` per
`contracts/firestore.md`/`db-design.md`. The public `GET /jobs/{jobId}` is project-agnostic, so
the job document also carries a denormalised `jobId` field that a collection-group query can
match without knowing the project.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.errors import ConflictError, NotFoundError
from app.schemas.jobs import Job, JobProgress, JobStatus, JobType
from app.services.firestore_service import (
    FirestoreClient,
    job_path,
    jobs_collection_path,
)


def _to_job(job_id: str, data: dict[str, Any]) -> Job:
    progress = data.get("progress") or {}
    return Job(
        jobId=job_id,
        type=JobType(data.get("type", JobType.transcribe.value)),
        status=JobStatus(data.get("status", JobStatus.queued.value)),
        progress=JobProgress(
            percent=progress.get("percent", 0),
            step=progress.get("currentStep"),
            message=progress.get("message"),
        ),
        error=data.get("error"),
        createdAt=data["createdAt"],
        updatedAt=data["updatedAt"],
    )


def is_owner(document: dict[str, Any], owner_uid: str) -> bool:
    return document.get("ownerUid") == owner_uid


class JobService:
    def __init__(self, client: FirestoreClient) -> None:
        self.client = client

    def create(
        self,
        *,
        owner_uid: str,
        project_id: str,
        job_type: JobType,
        idempotency_key: str,
        input: dict[str, Any] | None = None,
        requested_by: str = "system",
    ) -> Job:
        existing = self._find_by_idempotency_key(
            owner_uid=owner_uid,
            project_id=project_id,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            return existing

        job_id = uuid4().hex
        now = datetime.now(UTC)
        document: dict[str, Any] = {
            "jobId": job_id,
            "ownerUid": owner_uid,
            "projectId": project_id,
            "type": job_type.value,
            "status": JobStatus.queued.value,
            "idempotencyKey": idempotency_key,
            "requestedBy": requested_by,
            "input": input or {},
            "output": {"artifactIds": [], "storagePaths": []},
            "progress": {
                "currentStep": "queued",
                "percent": 0,
                "message": "Waiting to start",
            },
            "attempt": 0,
            "maxAttempts": 3,
            "error": None,
            "startedAt": None,
            "finishedAt": None,
            "createdAt": now,
            "updatedAt": now,
        }
        self.client.set_document(job_path(owner_uid, project_id, job_id), document)
        return _to_job(job_id, document)

    def get(self, *, owner_uid: str, job_id: str) -> Job:
        rows = self.client.query_collection_group(
            "jobs", filters=[("jobId", "==", job_id)], limit=5
        )
        for found_id, data in rows:
            if is_owner(data, owner_uid):
                return _to_job(found_id, data)
        raise NotFoundError("Job not found", details={"jobId": job_id})

    def load_for_worker(self, *, owner_uid: str, project_id: str, job_id: str) -> dict[str, Any]:
        """Fetch the raw job document for a worker that already knows the project."""
        data = self.client.get_document(job_path(owner_uid, project_id, job_id))
        if data is None or not is_owner(data, owner_uid):
            raise NotFoundError("Job not found", details={"jobId": job_id})
        return data

    def latest_for_project(self, *, owner_uid: str, project_id: str) -> Job | None:
        rows = self.client.query_collection(
            jobs_collection_path(owner_uid, project_id),
            filters=[],
            order_by=[("createdAt", "DESCENDING")],
            limit=1,
            offset=0,
        )
        if not rows:
            return None
        job_id, data = rows[0]
        if not is_owner(data, owner_uid):
            return None
        return _to_job(job_id, data)

    def cancel(self, *, owner_uid: str, job_id: str) -> Job:
        """Cancel a queued/running job. Terminal jobs are a conflict."""
        rows = self.client.query_collection_group(
            "jobs", filters=[("jobId", "==", job_id)], limit=5
        )
        for found_id, data in rows:
            if not is_owner(data, owner_uid):
                continue
            status = data.get("status")
            if status not in (JobStatus.queued.value, JobStatus.running.value):
                raise ConflictError(
                    "Only queued or running jobs can be cancelled.",
                    code="JOB_NOT_CANCELLABLE",
                    details={"jobId": job_id, "status": status},
                )
            project_id = data["projectId"]
            path = job_path(owner_uid, project_id, found_id)
            now = datetime.now(UTC)
            self.client.update_document(
                path,
                {
                    "status": JobStatus.cancelled.value,
                    "progress": {
                        "currentStep": "cancelled",
                        "percent": int((data.get("progress") or {}).get("percent", 0)),
                        "message": "Cancelled",
                    },
                    "finishedAt": now,
                    "updatedAt": now,
                },
            )
            updated = self.client.get_document(path) or data
            return _to_job(found_id, updated)
        raise NotFoundError("Job not found", details={"jobId": job_id})

    def mark_running(
        self, *, owner_uid: str, project_id: str, job_id: str, step: str, message: str
    ) -> None:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        self.client.update_document(
            job_path(owner_uid, project_id, job_id),
            {
                "status": JobStatus.running.value,
                "progress": {"currentStep": step, "percent": 5, "message": message},
                "startedAt": now,
                "updatedAt": now,
            },
        )

    def update_progress(
        self,
        *,
        owner_uid: str,
        project_id: str,
        job_id: str,
        percent: int,
        step: str,
        message: str,
    ) -> None:
        from datetime import UTC, datetime

        self.client.update_document(
            job_path(owner_uid, project_id, job_id),
            {
                "progress": {
                    "currentStep": step,
                    "percent": max(0, min(100, percent)),
                    "message": message,
                },
                "updatedAt": datetime.now(UTC),
            },
        )

    def mark_succeeded(
        self,
        *,
        owner_uid: str,
        project_id: str,
        job_id: str,
        output: dict[str, Any] | None = None,
        message: str = "Completed",
    ) -> None:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        self.client.update_document(
            job_path(owner_uid, project_id, job_id),
            {
                "status": JobStatus.succeeded.value,
                "progress": {
                    "currentStep": "done",
                    "percent": 100,
                    "message": message,
                },
                "output": output or {"artifactIds": [], "storagePaths": []},
                "finishedAt": now,
                "updatedAt": now,
            },
        )

    def mark_failed(
        self,
        *,
        owner_uid: str,
        project_id: str,
        job_id: str,
        message: str,
        code: str = "TRANSCRIBE_FAILED",
    ) -> None:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        self.client.update_document(
            job_path(owner_uid, project_id, job_id),
            {
                "status": JobStatus.failed.value,
                "error": {"code": code, "message": message},
                "finishedAt": now,
                "updatedAt": now,
            },
        )

    def _find_by_idempotency_key(
        self, *, owner_uid: str, project_id: str, idempotency_key: str
    ) -> Job | None:
        rows = self.client.query_collection(
            jobs_collection_path(owner_uid, project_id),
            filters=[("idempotencyKey", "==", idempotency_key)],
            order_by=[],
            limit=1,
            offset=0,
        )
        if not rows:
            return None
        job_id, data = rows[0]
        return _to_job(job_id, data)
