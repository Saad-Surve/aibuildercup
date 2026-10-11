"""Cross-post endpoints: publish a written piece to a connected text platform.

Unlike YouTube publishes this is synchronous — Medium, Substack, and Reddit
text posts complete in one API call, so the response carries the live URL (or
the draft dashboard URL) directly. Nothing is persisted server-side.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.dependencies import (
    AuthenticatedUser,
    current_user,
    get_crosspost_service,
)
from app.schemas.connections import CrosspostRequest, CrosspostResult
from app.services.crosspost_service import CrosspostService

router = APIRouter(tags=["crossposts"])

UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
ServiceDep = Annotated[CrosspostService, Depends(get_crosspost_service)]


@router.post(
    "/projects/{projectId}/crossposts",
    response_model=CrosspostResult,
    status_code=status.HTTP_201_CREATED,
)
def create_crosspost(
    projectId: str,
    payload: CrosspostRequest,
    user: UserDep,
    service: ServiceDep,
) -> CrosspostResult:
    return service.post(owner_uid=user.uid, project_id=projectId, payload=payload)
