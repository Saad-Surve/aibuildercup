"""Platform connection endpoints.

Public API:
- `GET /connections` — list the creator's connected channels.
- `POST /connections/{platform}/oauth/start` — begin OAuth; returns the Google authorization URL.
- `GET /connections/{platform}/oauth/callback` — Google's redirect target (no Firebase auth;
  the signed `state` is the proof of identity). Redirects back into the web app.
- `POST /connections/{connectionId}/sync` — refresh channel stats.
- `DELETE /connections/{connectionId}` — revoke at Google and delete the stored tokens.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import RedirectResponse

from app.dependencies import (
    AuthenticatedUser,
    current_user,
    get_channel_content_service,
    get_connection_service,
)
from app.schemas.connections import (
    ChannelContentProfile,
    Connection,
    ConnectionList,
    OAuthStartRequest,
    OAuthStartResponse,
)
from app.services.channel_content_service import ChannelContentService
from app.services.connection_service import ConnectionService

router = APIRouter(tags=["connections"])

UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
ServiceDep = Annotated[ConnectionService, Depends(get_connection_service)]


@router.get("/connections", response_model=ConnectionList)
async def list_connections(user: UserDep, service: ServiceDep) -> ConnectionList:
    return ConnectionList(items=service.list(owner_uid=user.uid))


@router.post(
    "/connections/{platform}/oauth/start",
    response_model=OAuthStartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_oauth(
    platform: str,
    payload: OAuthStartRequest,
    user: UserDep,
    service: ServiceDep,
) -> OAuthStartResponse:
    return service.start_oauth(owner_uid=user.uid, platform=platform, payload=payload)


@router.get("/connections/{platform}/oauth/callback", include_in_schema=True)
async def oauth_callback(
    platform: str,
    service: ServiceDep,
    state: str = "",
    code: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Google redirects the browser here. Always redirects; never renders JSON.

    This route is intentionally unauthenticated: Google, not the browser's Firebase session,
    is the caller. `state` points at a short-lived server-side record created by an
    authenticated `oauth/start` call.
    """
    del platform  # only youtube is supported; the state records the real platform
    target = service.handle_callback(state=state, code=code, error=error)
    return RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)


@router.post("/connections/{connectionId}/sync", response_model=Connection)
async def sync_connection(
    connectionId: str,
    user: UserDep,
    service: ServiceDep,
) -> Connection:
    return service.sync(owner_uid=user.uid, connection_id=connectionId)


ContentServiceDep = Annotated[ChannelContentService, Depends(get_channel_content_service)]


@router.post(
    "/connections/{connectionId}/content/sync",
    response_model=ChannelContentProfile,
)
async def sync_connection_content(
    connectionId: str,
    user: UserDep,
    service: ContentServiceDep,
) -> ChannelContentProfile:
    """Read the channel's existing videos back for style/RAG analysis."""
    return service.sync(owner_uid=user.uid, connection_id=connectionId)


@router.get(
    "/connections/{connectionId}/content",
    response_model=ChannelContentProfile,
)
async def get_connection_content(
    connectionId: str,
    user: UserDep,
    service: ContentServiceDep,
) -> ChannelContentProfile:
    return service.profile(owner_uid=user.uid, connection_id=connectionId)


@router.delete("/connections/{connectionId}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    connectionId: str,
    user: UserDep,
    service: ServiceDep,
) -> None:
    service.delete(owner_uid=user.uid, connection_id=connectionId)
