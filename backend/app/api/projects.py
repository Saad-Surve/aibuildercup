from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.dependencies import (
    AuthenticatedUser,
    current_user,
    get_draft_service,
    get_project_service,
)
from app.schemas.draft import DraftBrief
from app.schemas.projects import (
    CreateProject,
    Project,
    ProjectKind,
    ProjectList,
    UpdateProject,
)
from app.services.draft_service import DraftService
from app.services.project_service import (
    ProjectService,
    decode_page_token,
    encode_page_token,
)

router = APIRouter(tags=["projects"])

UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
ServiceDep = Annotated[ProjectService, Depends(get_project_service)]
DraftDep = Annotated[DraftService, Depends(get_draft_service)]


def _with_poster(service: ProjectService, project: Project) -> Project:
    """Attach a signed cover URL when the project has an applied thumbnail."""
    project.posterUrl = service.poster_url(project)
    return project


@router.get("/projects", response_model=ProjectList)
def list_projects(
    user: UserDep,
    service: ServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    pageToken: str | None = None,
) -> ProjectList:
    offset = decode_page_token(pageToken)
    items, has_more = service.list(owner_uid=user.uid, limit=limit, offset=offset)
    next_token = encode_page_token(offset + len(items)) if has_more else None
    return ProjectList(
        items=[_with_poster(service, item) for item in items],
        nextPageToken=next_token,
    )


@router.post("/projects", response_model=Project, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: CreateProject,
    user: UserDep,
    service: ServiceDep,
    drafts: DraftDep,
) -> Project:
    project = service.create(owner_uid=user.uid, payload=payload)
    if payload.kind == ProjectKind.draft:
        # Seed the versioned draft document (with the brief captured in the
        # creation dialog) under the project subtree.
        drafts.ensure(
            owner_uid=user.uid,
            project_id=project.projectId,
            brief=payload.draftBrief or DraftBrief(),
            format_=payload.draftFormat,
        )
    return project


@router.get("/projects/{projectId}", response_model=Project)
def get_project(
    projectId: str,
    user: UserDep,
    service: ServiceDep,
) -> Project:
    return _with_poster(
        service, service.get(owner_uid=user.uid, project_id=projectId)
    )


@router.patch("/projects/{projectId}", response_model=Project)
def update_project(
    projectId: str,
    payload: UpdateProject,
    user: UserDep,
    service: ServiceDep,
) -> Project:
    return _with_poster(
        service,
        service.update(owner_uid=user.uid, project_id=projectId, patch=payload),
    )


@router.delete("/projects/{projectId}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    projectId: str,
    user: UserDep,
    service: ServiceDep,
) -> Response:
    service.delete(owner_uid=user.uid, project_id=projectId)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
