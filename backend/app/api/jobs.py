from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import (
    AuthenticatedUser,
    current_user,
    get_job_service,
)
from app.schemas.jobs import Job
from app.services.job_service import JobService

router = APIRouter(tags=["jobs"])

UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
ServiceDep = Annotated[JobService, Depends(get_job_service)]


@router.get("/jobs/{jobId}", response_model=Job)
def get_job(jobId: str, user: UserDep, service: ServiceDep) -> Job:
    return service.get(owner_uid=user.uid, job_id=jobId)


@router.post("/jobs/{jobId}/cancel", response_model=Job)
def cancel_job(jobId: str, user: UserDep, service: ServiceDep) -> Job:
    return service.cancel(owner_uid=user.uid, job_id=jobId)
