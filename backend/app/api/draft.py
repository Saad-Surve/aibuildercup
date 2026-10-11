"""Draft studio API: versioned written content and video scripts."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import (
    AuthenticatedUser,
    current_user,
    get_draft_service,
)
from app.schemas.draft import (
    AssistDraftRequest,
    CreatorContext,
    Draft,
    GenerateDraftRequest,
    SaveDraftRequest,
    SuggestDraftRequest,
    SuggestDraftResponse,
)
from app.services.draft_service import DraftService

router = APIRouter(tags=["draft"])

UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
ServiceDep = Annotated[DraftService, Depends(get_draft_service)]


@router.get("/projects/{projectId}/draft", response_model=Draft)
def get_draft(
    projectId: str,
    user: UserDep,
    service: ServiceDep,
) -> Draft:
    return service.get(owner_uid=user.uid, project_id=projectId)


@router.put("/projects/{projectId}/draft", response_model=Draft)
def save_draft(
    projectId: str,
    payload: SaveDraftRequest,
    user: UserDep,
    service: ServiceDep,
) -> Draft:
    return service.save(owner_uid=user.uid, project_id=projectId, payload=payload)


@router.get("/projects/{projectId}/draft/context", response_model=CreatorContext)
def get_draft_context(
    projectId: str,
    user: UserDep,
    service: ServiceDep,
) -> CreatorContext:
    """What the last generation retrieved from the creator's channel (style evidence)."""
    return service.creator_context(owner_uid=user.uid, project_id=projectId)


@router.post("/projects/{projectId}/draft/generate", response_model=Draft)
async def generate_draft(
    projectId: str,
    payload: GenerateDraftRequest,
    user: UserDep,
    service: ServiceDep,
) -> Draft:
    return await service.generate(
        owner_uid=user.uid, project_id=projectId, overrides=payload
    )


@router.post("/projects/{projectId}/draft/assist", response_model=Draft)
async def assist_draft(
    projectId: str,
    payload: AssistDraftRequest,
    user: UserDep,
    service: ServiceDep,
) -> Draft:
    return await service.assist(
        owner_uid=user.uid, project_id=projectId, payload=payload
    )


@router.post(
    "/projects/{projectId}/draft/suggest", response_model=SuggestDraftResponse
)
async def suggest_draft(
    projectId: str,
    payload: SuggestDraftRequest,
    user: UserDep,
    service: ServiceDep,
) -> SuggestDraftResponse:
    suggestions = await service.suggest(
        owner_uid=user.uid, project_id=projectId, payload=payload
    )
    return SuggestDraftResponse(suggestions=suggestions)
