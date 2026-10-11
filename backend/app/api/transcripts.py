from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, status

from app.dependencies import (
    AuthenticatedUser,
    TranscribeScheduler,
    current_user,
    get_asset_service,
    get_transcribe_scheduler,
    get_transcript_service,
)
from app.schemas.common import AcceptedJob
from app.schemas.jobs import JobStatus
from app.schemas.transcripts import (
    Transcript,
    TranscriptSegment,
    TranscriptUpdate,
    TranscriptVersionList,
)
from app.services.asset_service import AssetService
from app.services.transcript_service import TranscriptService

router = APIRouter(tags=["transcripts"])

UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
ServiceDep = Annotated[TranscriptService, Depends(get_transcript_service)]
AssetServiceDep = Annotated[AssetService, Depends(get_asset_service)]
SchedulerDep = Annotated[TranscribeScheduler, Depends(get_transcribe_scheduler)]


@router.get("/projects/{projectId}/transcript", response_model=Transcript)
def get_transcript(
    projectId: str,
    user: UserDep,
    service: ServiceDep,
    version: int | None = None,
) -> Transcript:
    """The active transcript, or a specific saved version when `version` is given."""
    return service.get(owner_uid=user.uid, project_id=projectId, version=version)


@router.get(
    "/projects/{projectId}/transcript/versions",
    response_model=TranscriptVersionList,
)
def list_transcript_versions(
    projectId: str,
    user: UserDep,
    service: ServiceDep,
) -> TranscriptVersionList:
    return TranscriptVersionList(
        items=service.list_versions(owner_uid=user.uid, project_id=projectId)
    )


@router.post(
    "/projects/{projectId}/transcript/retranscribe",
    response_model=AcceptedJob,
    status_code=status.HTTP_202_ACCEPTED,
)
def retranscribe_transcript(
    projectId: str,
    user: UserDep,
    assets: AssetServiceDep,
    background_tasks: BackgroundTasks,
    scheduler: SchedulerDep,
) -> AcceptedJob:
    """Queue a fresh transcription run for the project's source video.

    Used by the transcript card's "Run transcript again" action; unlike re-completing the
    upload it always creates a new run, so a good transcript can be regenerated.
    """
    job = assets.retranscribe_source(owner_uid=user.uid, project_id=projectId)
    if job.status not in (JobStatus.succeeded, JobStatus.running):
        scheduler(
            background_tasks,
            owner_uid=user.uid,
            project_id=projectId,
            job_id=job.jobId,
        )
    return AcceptedJob(jobId=job.jobId, status=job.status.value)


@router.put("/projects/{projectId}/transcript", response_model=Transcript)
def update_transcript(
    projectId: str,
    payload: TranscriptUpdate,
    user: UserDep,
    service: ServiceDep,
) -> Transcript:
    """Save edited segments as a new active transcript version.

    Backs the transcript editor's Save action. Runs no STT: it persists what the
    user typed, reusing the active transcript's language and source asset.
    """
    return service.update(
        owner_uid=user.uid,
        project_id=projectId,
        language=payload.language,
        segments=[segment.model_dump() for segment in payload.segments],
        speaker_labels=payload.speakerLabels,
    )


@router.get(
    "/projects/{projectId}/transcript/segments/{segmentId}",
    response_model=TranscriptSegment,
)
def get_transcript_segment(
    projectId: str,
    segmentId: str,
    user: UserDep,
    service: ServiceDep,
) -> TranscriptSegment:
    return service.get_segment(
        owner_uid=user.uid, project_id=projectId, segment_id=segmentId
    )
