from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import AuthenticatedUser, current_user, get_creator_library_service
from app.schemas.creator_library import CreatorLibrary, CreatorLibraryQuery, CreatorLibrarySearch
from app.services.creator_library_service import CreatorLibraryService

router = APIRouter(tags=["creator-library"])
UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
ServiceDep = Annotated[CreatorLibraryService, Depends(get_creator_library_service)]


@router.get("/creator-library", response_model=CreatorLibrary)
def library(user: UserDep, service: ServiceDep) -> CreatorLibrary:
    return service.library(user.uid)


@router.post("/creator-library/index", response_model=CreatorLibrary)
def index(user: UserDep, service: ServiceDep) -> CreatorLibrary:
    return service.index(user.uid)


@router.post("/creator-library/search", response_model=CreatorLibrarySearch)
def search(
    payload: CreatorLibraryQuery, user: UserDep, service: ServiceDep
) -> CreatorLibrarySearch:
    return service.search(user.uid, payload.query)
