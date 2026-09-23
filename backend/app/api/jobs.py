import asyncio
import json
import time
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.dependencies import (
    AuthenticatedUser,
    current_user,
    get_job_service,
    get_project_service,
)
from app.schemas.jobs import Job
from app.services.job_service import JobService
from app.services.project_service import ProjectService

router = APIRouter(tags=["jobs"])

UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
ServiceDep = Annotated[JobService, Depends(get_job_service)]
ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]

# Project states that mean no further progress events will arrive.
_TERMINAL_PROJECT_STATUSES = {"ready", "failed", "archived", "partial_failure"}
_STREAM_INTERVAL_SECONDS = 2
_STREAM_MAX_SECONDS = 600


@router.get("/jobs/{jobId}", response_model=Job)
async def get_job(jobId: str, user: UserDep, service: ServiceDep) -> Job:
    return service.get(owner_uid=user.uid, job_id=jobId)


@router.post("/jobs/{jobId}/cancel", response_model=Job)
async def cancel_job(jobId: str, user: UserDep, service: ServiceDep) -> Job:
    return service.cancel(owner_uid=user.uid, job_id=jobId)


@router.get("/projects/{projectId}/events")
async def project_events(
    projectId: str,
    user: UserDep,
    projects: ProjectServiceDep,
    jobs: ServiceDep,
) -> StreamingResponse:
    """Server-Sent Events stream of project/job progress (api-design section 7)."""

    def snapshot() -> dict:
        project = projects.get(owner_uid=user.uid, project_id=projectId)
        job = jobs.latest_for_project(owner_uid=user.uid, project_id=projectId)
        return {
            "projectId": project.projectId,
            "status": project.status.value,
            "progress": project.progress.model_dump() if project.progress else None,
            "job": (
                {
                    "jobId": job.jobId,
                    "status": job.status.value,
                    "progress": job.progress.model_dump(),
                }
                if job
                else None
            ),
        }

    async def stream():
        previous: dict | None = None
        deadline = time.monotonic() + _STREAM_MAX_SECONDS
        while True:
            payload = snapshot()
            if payload != previous:
                yield f"event: job.progress\ndata: {json.dumps(payload)}\n\n"
                previous = payload
            if payload["status"] in _TERMINAL_PROJECT_STATUSES:
                break
            if time.monotonic() >= deadline:
                break
            await asyncio.sleep(_STREAM_INTERVAL_SECONDS)

    return StreamingResponse(stream(), media_type="text/event-stream")
