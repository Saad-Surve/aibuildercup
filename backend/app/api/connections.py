"""Platform connection endpoints.

Public API:
- `GET /connections` — list the creator's connected accounts.
- `POST /connections/{platform}/oauth/start` — begin OAuth (youtube, reddit);
  returns the provider authorization URL.
- `GET /connections/{platform}/oauth/callback` — provider redirect target (no Firebase auth;
  the signed `state` is the proof of identity). Redirects back into the web app.
- `POST /connections/medium/connect` — connect Medium with a legacy token.
- `POST /connections/substack/connect` — connect a Substack publication with a session cookie.
- `POST /connections/{connectionId}/sync` — re-verify identity / refresh stats.
- `DELETE /connections/{connectionId}` — revoke where the provider allows it, then delete.
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
    AudienceProfile,
    ChannelContentProfile,
    Connection,
    ConnectionList,
    MediumConnectRequest,
    OAuthStartRequest,
    OAuthStartResponse,
    SubstackConnectRequest,
)
from app.services.channel_content_service import ChannelContentService
from app.services.connection_service import ConnectionService

router = APIRouter(tags=["connections"])

UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
ServiceDep = Annotated[ConnectionService, Depends(get_connection_service)]


@router.get("/connections", response_model=ConnectionList)
def list_connections(user: UserDep, service: ServiceDep) -> ConnectionList:
    return ConnectionList(items=service.list(owner_uid=user.uid))


@router.post(
    "/connections/{platform}/oauth/start",
    response_model=OAuthStartResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_oauth(
    platform: str,
    payload: OAuthStartRequest,
    user: UserDep,
    service: ServiceDep,
) -> OAuthStartResponse:
    return service.start_oauth(owner_uid=user.uid, platform=platform, payload=payload)


@router.get("/connections/{platform}/oauth/callback", include_in_schema=True)
def oauth_callback(
    platform: str,
    service: ServiceDep,
    state: str = "",
    code: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """The provider redirects the browser here. Always redirects; never renders JSON.

    This route is intentionally unauthenticated: the provider, not the browser's Firebase
    session, is the caller. `state` points at a short-lived server-side record created by an
    authenticated `oauth/start` call.
    """
    del platform  # only youtube is supported; the state records the real platform
    target = service.handle_callback(state=state, code=code, error=error)
    return RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)


@router.post("/connections/{connectionId}/sync", response_model=Connection)
def sync_connection(
    connectionId: str,
    user: UserDep,
    service: ServiceDep,
) -> Connection:
    return service.sync(owner_uid=user.uid, connection_id=connectionId)


@router.post(
    "/connections/medium/connect",
    response_model=Connection,
    status_code=status.HTTP_201_CREATED,
)
def connect_medium(
    payload: MediumConnectRequest,
    user: UserDep,
    service: ServiceDep,
) -> Connection:
    """Connect Medium with a pre-2025 integration token (none are issued anymore)."""
    return service.connect_medium(owner_uid=user.uid, token=payload.token)


@router.post(
    "/connections/substack/connect",
    response_model=Connection,
    status_code=status.HTTP_201_CREATED,
)
def connect_substack(
    payload: SubstackConnectRequest,
    user: UserDep,
    service: ServiceDep,
) -> Connection:
    """Connect a Substack publication with a browser session cookie."""
    return service.connect_substack(
        owner_uid=user.uid, sid=payload.sid, subdomain=payload.subdomain
    )


ContentServiceDep = Annotated[ChannelContentService, Depends(get_channel_content_service)]


@router.post(
    "/connections/{connectionId}/content/sync",
    response_model=ChannelContentProfile,
)
def sync_connection_content(
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
def get_connection_content(
    connectionId: str,
    user: UserDep,
    service: ContentServiceDep,
) -> ChannelContentProfile:
    return service.profile(owner_uid=user.uid, connection_id=connectionId)


@router.post(
    "/connections/{connectionId}/audience/sync",
    response_model=AudienceProfile,
)
def sync_connection_audience(
    connectionId: str,
    user: UserDep,
    service: ContentServiceDep,
) -> AudienceProfile:
    """Read YouTube Analytics (summary, demographics, traffic, top videos) for the channel."""
    return service.sync_audience(owner_uid=user.uid, connection_id=connectionId)


@router.get(
    "/connections/{connectionId}/audience",
    response_model=AudienceProfile,
)
def get_connection_audience(
    connectionId: str,
    user: UserDep,
    service: ContentServiceDep,
) -> AudienceProfile:
    return service.audience(owner_uid=user.uid, connection_id=connectionId)


@router.delete("/connections/{connectionId}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connection(
    connectionId: str,
    user: UserDep,
    service: ServiceDep,
) -> None:
    service.delete(owner_uid=user.uid, connection_id=connectionId)
