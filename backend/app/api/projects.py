from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.dependencies import AuthenticatedUser, current_user, get_project_service
from app.schemas.projects import CreateProject, Project, ProjectList, UpdateProject
from app.services.project_service import (
    ProjectService,
    decode_page_token,
    encode_page_token,
)

router = APIRouter(tags=["projects"])

UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
ServiceDep = Annotated[ProjectService, Depends(get_project_service)]


@router.get("/projects", response_model=ProjectList)
async def list_projects(
    user: UserDep,
    service: ServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    pageToken: str | None = None,
) -> ProjectList:
    offset = decode_page_token(pageToken)
    items, has_more = service.list(owner_uid=user.uid, limit=limit, offset=offset)
    next_token = encode_page_token(offset + len(items)) if has_more else None
    return ProjectList(items=items, nextPageToken=next_token)


@router.post("/projects", response_model=Project, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: CreateProject,
    user: UserDep,
    service: ServiceDep,
) -> Project:
    return service.create(owner_uid=user.uid, payload=payload)


@router.get("/projects/{projectId}", response_model=Project)
async def get_project(
    projectId: str,
    user: UserDep,
    service: ServiceDep,
) -> Project:
    return service.get(owner_uid=user.uid, project_id=projectId)


@router.patch("/projects/{projectId}", response_model=Project)
async def update_project(
    projectId: str,
    payload: UpdateProject,
    user: UserDep,
    service: ServiceDep,
) -> Project:
    return service.update(owner_uid=user.uid, project_id=projectId, patch=payload)


@router.delete("/projects/{projectId}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    projectId: str,
    user: UserDep,
    service: ServiceDep,
) -> Response:
    service.delete(owner_uid=user.uid, project_id=projectId)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
