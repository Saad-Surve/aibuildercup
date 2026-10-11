"""Global corpus and project glossary endpoints.

`GET /glossaries` exposes the bundled global corpus (its version and covered language
pairs) so the UI can show what the translation is grounded on. The project glossary routes
read and replace the creator's own terms; the localization worker uses them.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import AuthenticatedUser, current_user, get_glossary_service
from app.schemas.localizations import (
    CorpusLanguagePair,
    GlobalCorpus,
    Glossary,
    GlossaryUpdate,
)
from app.services.glossary_service import GlossaryService
from app.services.localization_corpus import available_pairs, corpus_version

router = APIRouter(tags=["localizations"])

UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
ServiceDep = Annotated[GlossaryService, Depends(get_glossary_service)]


@router.get("/glossaries", response_model=GlobalCorpus)
def get_global_corpus(user: UserDep) -> GlobalCorpus:
    """The bundled global corpus version and the language pairs it covers."""
    return GlobalCorpus(
        version=corpus_version(),
        pairs=[
            CorpusLanguagePair(
                sourceLanguage=pair["sourceLanguage"],
                targetLanguage=pair["targetLanguage"],
            )
            for pair in available_pairs()
        ],
    )


@router.get(
    "/projects/{projectId}/glossary",
    response_model=Glossary,
)
def get_project_glossary(
    projectId: str,
    user: UserDep,
    service: ServiceDep,
) -> Glossary:
    return service.get(owner_uid=user.uid, project_id=projectId)


@router.put(
    "/projects/{projectId}/glossary",
    response_model=Glossary,
)
def put_project_glossary(
    projectId: str,
    payload: GlossaryUpdate,
    user: UserDep,
    service: ServiceDep,
) -> Glossary:
    return service.put(
        owner_uid=user.uid, project_id=projectId, payload=payload
    )
