"""Cross-post endpoints: publish a written piece to a connected text platform.

Unlike YouTube publishes this is synchronous — Medium, Substack, and Reddit
text posts complete in one API call, so the response carries the live URL (or
the draft dashboard URL) directly. Posting a Substack draft/schedule records
the remote draft on the local draft, and the sync endpoint pushes later edits
into it — the two-way link.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.dependencies import (
    AuthenticatedUser,
    current_user,
    get_crosspost_service,
)
from app.schemas.connections import (
    CrosspostRequest,
    CrosspostResult,
    SyncCrosspostRequest,
)
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


@router.post(
    "/projects/{projectId}/crossposts/sync",
    response_model=CrosspostResult,
)
def sync_crosspost(
    projectId: str,
    payload: SyncCrosspostRequest,
    user: UserDep,
    service: ServiceDep,
) -> CrosspostResult:
    """Push the current title/body into the linked platform draft.

    The connection comes from the link recorded at post time. 409 when nothing
    is linked (post first) or the remote draft is gone (post again); 400 for
    platforms without draft updates.
    """
    return service.sync(
        owner_uid=user.uid,
        project_id=projectId,
        platform=payload.platform,
        title=payload.title,
        body=payload.body,
    )
