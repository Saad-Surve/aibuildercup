"""Dubbing (localization) endpoints.

Queues a dub of the project's source video into a target language. The heavy lifting happens
in `dub_worker`; these routes validate input, queue the job, list dubs, and hand back
short-lived download URLs. `GET /localization-voices` is the catalog the web client mirrors so
the language and voice pickers cannot drift from what the worker supports.
"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Response, status

from app.dependencies import (
    AuthenticatedUser,
    DubScheduler,
    current_user,
    get_dub_scheduler,
    get_localization_service,
)
from app.schemas.assets import DownloadUrl
from app.schemas.jobs import JobStatus
from app.schemas.localizations import (
    Localization,
    LocalizationAccepted,
    LocalizationLanguage,
    LocalizationList,
    LocalizationRequest,
    LocalizationVoice,
    LocalizationVoiceList,
    VoiceGender,
)
from app.services.dubbing import catalog
from app.services.localization_service import LocalizationService

router = APIRouter(tags=["localizations"])

UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
ServiceDep = Annotated[LocalizationService, Depends(get_localization_service)]
SchedulerDep = Annotated[DubScheduler, Depends(get_dub_scheduler)]


@router.get("/localization-voices", response_model=LocalizationVoiceList)
async def list_localization_voices(user: UserDep) -> LocalizationVoiceList:
    """Languages the dubbing pipeline can synthesize and the voices available for each."""
    return LocalizationVoiceList(
        items=[
            LocalizationLanguage(
                language=language.code,
                label=language.label,
                voices=[
                    LocalizationVoice(
                        id=voice.id,
                        name=voice.name,
                        label=voice.label,
                        gender=VoiceGender(voice.gender),
                    )
                    for voice in language.voices
                ],
            )
            for language in catalog()
        ]
    )


@router.post(
    "/projects/{projectId}/localizations",
    response_model=LocalizationAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_localization(
    projectId: str,
    payload: LocalizationRequest,
    user: UserDep,
    service: ServiceDep,
    background_tasks: BackgroundTasks,
    scheduler: SchedulerDep,
) -> LocalizationAccepted:
    """Queue a dub of the active (or a chosen) transcript into the target language."""
    localization, job = service.create(
        owner_uid=user.uid, project_id=projectId, payload=payload
    )
    if job.status not in (JobStatus.succeeded, JobStatus.running):
        scheduler(
            background_tasks,
            owner_uid=user.uid,
            project_id=projectId,
            job_id=job.jobId,
        )
    return LocalizationAccepted(
        localizationId=localization.localizationId,
        jobId=job.jobId,
        status=job.status.value,
    )


@router.get(
    "/projects/{projectId}/localizations",
    response_model=LocalizationList,
)
async def list_localizations(
    projectId: str,
    user: UserDep,
    service: ServiceDep,
) -> LocalizationList:
    return LocalizationList(
        items=service.list(owner_uid=user.uid, project_id=projectId)
    )


@router.get(
    "/projects/{projectId}/localizations/{localizationId}",
    response_model=Localization,
)
async def get_localization(
    projectId: str,
    localizationId: str,
    user: UserDep,
    service: ServiceDep,
) -> Localization:
    return service.get(
        owner_uid=user.uid,
        project_id=projectId,
        localization_id=localizationId,
    )


@router.get(
    "/projects/{projectId}/localizations/{localizationId}/download-url",
    response_model=DownloadUrl,
)
async def get_localization_download_url(
    projectId: str,
    localizationId: str,
    user: UserDep,
    service: ServiceDep,
) -> DownloadUrl:
    url, expires_at = service.download_url(
        owner_uid=user.uid,
        project_id=projectId,
        localization_id=localizationId,
    )
    return DownloadUrl(url=url, expiresAt=expires_at)


@router.delete(
    "/projects/{projectId}/localizations/{localizationId}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_localization(
    projectId: str,
    localizationId: str,
    user: UserDep,
    service: ServiceDep,
) -> Response:
    service.delete(
        owner_uid=user.uid,
        project_id=projectId,
        localization_id=localizationId,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
