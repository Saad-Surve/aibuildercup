from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import TypeAdapter, ValidationError

from app.dependencies import (
    AuthenticatedUser,
    current_user,
    get_asset_service,
    get_transcript_service,
)
from app.errors import BadRequestError
from app.schemas.edit_plan import EditPlan, ExportFrameRate
from app.services.edit_plan import EditPlanService
from app.services.firestore_service import get_firestore_client

router = APIRouter(tags=["analysis"])
UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
_BASE = "/projects/{projectId}/analysis/{analysisRunId}/edit-plan"
_LABELS = TypeAdapter(dict[str, Literal["cut", "note"]])


def parse_labels(
    labels: Annotated[str | None, Query(max_length=20000)] = None,
) -> dict[str, Literal["cut", "note"]]:
    if labels is None:
        return {}
    try:
        return _LABELS.validate_json(labels)
    except ValidationError as exc:
        raise BadRequestError("labels must be a JSON object of finding IDs to cut or note") from exc


Labels = Annotated[dict[str, Literal["cut", "note"]], Depends(parse_labels)]


def live_service() -> EditPlanService:
    return EditPlanService(
        get_firestore_client(), get_asset_service(), get_transcript_service()
    )


ServiceDep = Annotated[EditPlanService, Depends(live_service)]


@router.get(f"{_BASE}/plan", response_model=EditPlan)
def preview_plan(
    projectId: str,
    analysisRunId: str,
    user: UserDep,
    service: ServiceDep,
    labels: Labels,
) -> EditPlan:
    return service.plan(
        owner_uid=user.uid, project_id=projectId, run_id=analysisRunId, labels=labels
    )


@router.get(f"{_BASE}/edl")
def download_plan(
    projectId: str,
    analysisRunId: str,
    user: UserDep,
    service: ServiceDep,
    labels: Labels,
    format: Literal["cmx3600", "markdown"] = "cmx3600",
    fps: ExportFrameRate = ExportFrameRate.fps30,
) -> Response:
    text = service.export(
        owner_uid=user.uid,
        project_id=projectId,
        run_id=analysisRunId,
        labels=labels,
        format=format,
        fps=fps,
    )
    extension = "md" if format == "markdown" else "edl"
    return Response(
        text,
        media_type="text/markdown" if format == "markdown" else "text/plain",
        headers={"Content-Disposition": f'attachment; filename="edit-plan.{extension}"'},
    )
