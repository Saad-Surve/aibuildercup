from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import (
    AuthenticatedUser,
    current_user,
    get_persona_research_service,
    get_persona_service,
    get_user_service,
)
from app.schemas.onboarding import (
    OnboardingResearch,
    OnboardingResearchRequest,
    OnboardingState,
    OnboardingStep,
)
from app.schemas.persona import Persona, PersonaRef, PersonaUpdate
from app.services.persona_research import PersonaResearchService
from app.services.persona_service import PersonaService
from app.services.user_service import UserService

router = APIRouter(tags=["onboarding"])

UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
PersonaServiceDep = Annotated[PersonaService, Depends(get_persona_service)]
PersonaResearchServiceDep = Annotated[
    PersonaResearchService, Depends(get_persona_research_service)
]


@router.get("/onboarding", response_model=OnboardingState)
def get_onboarding(user: UserDep, service: UserServiceDep) -> OnboardingState:
    return service.get_onboarding(user.uid)


@router.put("/onboarding", response_model=OnboardingState)
def save_onboarding_step(
    payload: OnboardingStep,
    user: UserDep,
    service: UserServiceDep,
) -> OnboardingState:
    return service.save_onboarding_step(user.uid, payload)


@router.post("/onboarding/research", response_model=OnboardingResearch)
async def research_onboarding(
    payload: OnboardingResearchRequest,
    user: UserDep,
    service: PersonaResearchServiceDep,
) -> OnboardingResearch:
    """Research the creator from their public links and prefill the persona form."""
    return await service.research(user.uid, payload)


@router.post("/onboarding/complete", response_model=PersonaRef)
async def complete_onboarding(
    user: UserDep, service: PersonaServiceDep
) -> PersonaRef:
    return await service.complete_onboarding(user.uid)


@router.get("/persona", response_model=Persona)
def get_persona(user: UserDep, service: PersonaServiceDep) -> Persona:
    return service.get(user.uid)


@router.patch("/persona", response_model=Persona)
def update_persona(
    payload: PersonaUpdate,
    user: UserDep,
    service: PersonaServiceDep,
) -> Persona:
    return service.update(
        user.uid,
        content=payload.content,
        expected_version=payload.expectedVersion,
    )
