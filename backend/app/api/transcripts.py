from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import (
    AuthenticatedUser,
    current_user,
    get_transcript_service,
)
from app.schemas.transcripts import Transcript, TranscriptSegment
from app.services.transcript_service import TranscriptService

router = APIRouter(tags=["transcripts"])

UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
ServiceDep = Annotated[TranscriptService, Depends(get_transcript_service)]


@router.get("/projects/{projectId}/transcript", response_model=Transcript)
async def get_transcript(
    projectId: str,
    user: UserDep,
    service: ServiceDep,
) -> Transcript:
    return service.get(owner_uid=user.uid, project_id=projectId)


@router.get(
    "/projects/{projectId}/transcript/segments/{segmentId}",
    response_model=TranscriptSegment,
)
async def get_transcript_segment(
    projectId: str,
    segmentId: str,
    user: UserDep,
    service: ServiceDep,
) -> TranscriptSegment:
    return service.get_segment(
        owner_uid=user.uid, project_id=projectId, segment_id=segmentId
    )
