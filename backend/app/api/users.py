from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.dependencies import (
    AuthenticatedUser,
    current_user,
    get_identity_deleter,
    get_user_service,
)
from app.schemas.users import AvatarState, Me
from app.services.user_service import UserService

router = APIRouter(tags=["users"])

UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
IdentityDeleterDep = Annotated[Callable[[str], None], Depends(get_identity_deleter)]


@router.get("/me", response_model=Me)
async def get_me(user: UserDep, service: UserServiceDep) -> Me:
    data = service.ensure_user(
        user.uid,
        display_name=user.display_name,
        email=user.email,
        photo_url=user.picture,
    )
    return service.to_me(user.uid, data)


@router.put("/me/avatar", response_model=AvatarState)
async def put_avatar(
    payload: AvatarState,
    user: UserDep,
    service: UserServiceDep,
) -> AvatarState:
    """Save the user's Humation avatar (seed + per-slot part and color overrides)."""
    return service.save_avatar(user.uid, payload)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    user: UserDep,
    service: UserServiceDep,
    delete_identity: IdentityDeleterDep,
) -> Response:
    # Data first, then the identity: if the identity delete fails the user can
    # retry, and a re-run is idempotent because the subtree is already gone.
    service.delete_account(user.uid)
    delete_identity(user.uid)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
