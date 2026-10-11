"""Authenticated packaging APIs. Services own persistence and deletion."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Response

from app.dependencies import AuthenticatedUser, current_user, get_packaging_service
from app.schemas.jobs import Job, JobStatus
from app.schemas.packaging import (
    ListingFields,
    PackagingAccepted,
    PackagingBrief,
    PackagingListing,
    RenderVisualInsertRequest,
    VisualInsertList,
)
from app.services.packaging_service import PackagingService
from app.workers.packaging_worker import run_packaging

router = APIRouter(tags=["packaging"])
User = Annotated[AuthenticatedUser, Depends(current_user)]
Service = Annotated[PackagingService, Depends(get_packaging_service)]


def _schedule(tasks: BackgroundTasks, user: User, project_id: str, job: Job) -> PackagingAccepted:
    if job.status == JobStatus.queued:
        tasks.add_task(run_packaging, owner_uid=user.uid, project_id=project_id, job_id=job.jobId)
    return PackagingAccepted(jobId=job.jobId, status=job.status.value)


@router.get("/projects/{projectId}/packaging/listing", response_model=PackagingListing | None)
def get_listing(projectId: str, user: User, service: Service):
    return service.listing(user.uid, projectId)


@router.put("/projects/{projectId}/packaging/listing", response_model=PackagingListing)
def save_listing(projectId: str, payload: ListingFields, user: User, service: Service):
    return service.save_listing(user.uid, projectId, payload)


@router.post(
    "/projects/{projectId}/packaging/listing/generate",
    response_model=PackagingAccepted,
    status_code=202,
)
def generate_listing(
    projectId: str,
    payload: PackagingBrief,
    user: User,
    service: Service,
    background_tasks: BackgroundTasks,
):
    return _schedule(
        background_tasks, user, projectId, service.generate(user.uid, projectId, "listing", payload)
    )


@router.get("/projects/{projectId}/visual-inserts", response_model=VisualInsertList)
def list_inserts(projectId: str, user: User, service: Service):
    return service.list_inserts(user.uid, projectId)


@router.post(
    "/projects/{projectId}/visual-inserts/suggest",
    response_model=PackagingAccepted,
    status_code=202,
)
def suggest_inserts(
    projectId: str,
    payload: PackagingBrief,
    user: User,
    service: Service,
    background_tasks: BackgroundTasks,
):
    return _schedule(
        background_tasks, user, projectId, service.generate(user.uid, projectId, "suggest", payload)
    )


@router.post(
    "/projects/{projectId}/visual-inserts/{insertId}/render",
    response_model=PackagingAccepted,
    status_code=202,
)
def render_insert(
    projectId: str,
    insertId: str,
    payload: RenderVisualInsertRequest,
    user: User,
    service: Service,
    background_tasks: BackgroundTasks,
):
    return _schedule(
        background_tasks, user, projectId, service.render(user.uid, projectId, insertId, payload)
    )


@router.delete("/projects/{projectId}/visual-inserts/{insertId}", status_code=204)
def delete_insert(projectId: str, insertId: str, user: User, service: Service):
    service.delete_insert(user.uid, projectId, insertId)
    return Response(status_code=204)
