"""Job records: creation with idempotency and lookup by id.

Jobs are stored under `users/{uid}/projects/{projectId}/jobs/{jobId}` per
`contracts/firestore.md`/`db-design.md`. The public `GET /jobs/{jobId}` is project-agnostic, so
the job document also carries a denormalised `jobId` field that a collection-group query can
match without knowing the project.
"""

from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from app.errors import ConflictError, NotFoundError
from app.realtime.events import emit_job
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

        # A query alone races under concurrent upload-complete/Pub/Sub delivery.
        # Keep the legacy lookup above, but let Firestore arbitrate new jobs at
        # a stable ID instead of creating two random IDs and charging twice.
        job_id = sha256(f"{owner_uid}/{project_id}/{idempotency_key}".encode()).hexdigest()[:32]
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
        if not self.client.create_document(job_path(owner_uid, project_id, job_id), document):
            document = self.load_for_worker(
                owner_uid=owner_uid, project_id=project_id, job_id=job_id
            )
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
            emit_job(
                owner_uid,
                project_id,
                job_id=found_id,
                status=JobStatus.cancelled,
                percent=int((data.get("progress") or {}).get("percent", 0)),
                step="cancelled",
                message="Cancelled",
            )
            return _to_job(found_id, updated)
        raise NotFoundError("Job not found", details={"jobId": job_id})

    def mark_running(
        self, *, owner_uid: str, project_id: str, job_id: str, step: str, message: str
    ) -> None:
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
        emit_job(
            owner_uid,
            project_id,
            job_id=job_id,
            status=JobStatus.running,
            percent=5,
            step=step,
            message=message,
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
        percent = max(0, min(100, percent))
        self.client.update_document(
            job_path(owner_uid, project_id, job_id),
            {
                "progress": {
                    "currentStep": step,
                    "percent": percent,
                    "message": message,
                },
                "updatedAt": datetime.now(UTC),
            },
        )
        emit_job(
            owner_uid,
            project_id,
            job_id=job_id,
            status=JobStatus.running,
            percent=percent,
            step=step,
            message=message,
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
        emit_job(
            owner_uid,
            project_id,
            job_id=job_id,
            status=JobStatus.succeeded,
            percent=100,
            step="done",
            message=message,
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
        now = datetime.now(UTC)
        error = {"code": code, "message": message}
        self.client.update_document(
            job_path(owner_uid, project_id, job_id),
            {
                "status": JobStatus.failed.value,
                "error": error,
                "finishedAt": now,
                "updatedAt": now,
            },
        )
        # No progress write on failure: send status + error and let the client
        # keep the last known progress rather than regressing to zero.
        emit_job(
            owner_uid,
            project_id,
            job_id=job_id,
            status=JobStatus.failed,
            error=error,
        )

    def requeue_failed(
        self,
        *,
        owner_uid: str,
        project_id: str,
        job_id: str,
        input: dict[str, Any] | None = None,
    ) -> Job:
        """Reset a failed job to `queued` so it can run again.

        `POST /assets/{id}/complete` finds the existing job through its idempotency key;
        without this reset the worker skips it as terminal and the project is stuck in
        `processing` forever. Only failed jobs are reset — queued, running, succeeded and
        cancelled jobs are returned untouched.
        """
        data = self.load_for_worker(owner_uid=owner_uid, project_id=project_id, job_id=job_id)
        if data.get("status") != JobStatus.failed.value:
            return _to_job(job_id, data)
        now = datetime.now(UTC)
        changes: dict[str, Any] = {
            "status": JobStatus.queued.value,
            "error": None,
            "attempt": 0,
            "progress": {
                "currentStep": "queued",
                "percent": 0,
                "message": "Waiting to start",
            },
            "startedAt": None,
            "finishedAt": None,
            "updatedAt": now,
        }
        if input is not None:
            changes["input"] = input
        self.client.update_document(job_path(owner_uid, project_id, job_id), changes)
        emit_job(
            owner_uid,
            project_id,
            job_id=job_id,
            status=JobStatus.queued,
            percent=0,
            step="queued",
            message="Waiting to start",
        )
        updated = self.client.get_document(job_path(owner_uid, project_id, job_id)) or data
        return _to_job(job_id, updated)

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
