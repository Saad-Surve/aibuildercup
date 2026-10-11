"""Demo seeding: load a CC-BY channel's content into the signed-in user's account.

A fresh account has no published videos, so the creator-content features have nothing to learn
from. This endpoint loads a pre-built seed (see `backend/scripts/upload_youtube_seed.py`) as a
synthetic demo connection. Authenticated: it writes to the caller's own subtree.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import (
    AuthenticatedUser,
    current_user,
    get_seed_service,
)
from app.schemas.connections import (
    SeedYouTubeContentRequest,
    SeedYouTubeContentResult,
)
from app.services.seed_service import SeedService

router = APIRouter(tags=["seed"])

UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
ServiceDep = Annotated[SeedService, Depends(get_seed_service)]


@router.post("/seed/youtube-content", response_model=SeedYouTubeContentResult)
def seed_youtube_content(
    payload: SeedYouTubeContentRequest,
    user: UserDep,
    service: ServiceDep,
) -> SeedYouTubeContentResult:
    return service.seed_youtube_content(owner_uid=user.uid, channel=payload.channel)
