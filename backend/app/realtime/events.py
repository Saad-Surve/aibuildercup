"""Realtime frame builders and emit helpers.

Write paths (job/project/analysis services and the transcribe worker) call these
after persisting, so browsers get pushed the same state that landed in Firestore.
Frames match the `WsEvent*` schemas in `contracts/openapi.yaml` and the protocol
in `contracts/events.md`.

Emitting is best-effort: `EventHub.publish_json` never raises, so a realtime
problem can never fail the write that triggered it.
"""

from enum import StrEnum
from typing import Any

from app.realtime.hub import get_hub


def _value(value: str | StrEnum | None) -> str | None:
    return value.value if isinstance(value, StrEnum) else value


def _progress(percent: int, step: str | None, message: str | None) -> dict[str, Any]:
    return {"percent": percent, "step": step, "message": message}


def has_subscribers(owner_uid: str, project_id: str) -> bool:
    """True when a socket is watching, so callers can skip expensive payloads."""
    return get_hub().has_subscribers(owner_uid, project_id)


def emit_project(
    owner_uid: str,
    project_id: str,
    *,
    status: str | StrEnum,
    stage: str | None,
    percent: int,
    message: str | None,
) -> None:
    get_hub().publish_json(
        owner_uid,
        project_id,
        {
            "type": "project.progress",
            "projectId": project_id,
            "status": _value(status),
            "progress": {"stage": stage, "percent": percent, "message": message},
        },
    )


def emit_job(
    owner_uid: str,
    project_id: str,
    *,
    job_id: str,
    status: str | StrEnum,
    percent: int | None = None,
    step: str | None = None,
    message: str | None = None,
    job_type: str | StrEnum | None = None,
    error: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "type": "job.progress",
        "projectId": project_id,
        "jobId": job_id,
        "jobType": _value(job_type),
        "status": _value(status),
        "error": error,
    }
    # On failure/cancel the write may not touch progress; omit it so the client
    # keeps the last known percent instead of snapping back to zero.
    if percent is not None:
        payload["progress"] = _progress(percent, step, message)
    get_hub().publish_json(owner_uid, project_id, payload)


def emit_transcript_ready(
    owner_uid: str,
    project_id: str,
    *,
    transcript_id: str,
    job_id: str | None,
    language: str | None,
    duration_ms: int,
) -> None:
    get_hub().publish_json(
        owner_uid,
        project_id,
        {
            "type": "transcript.ready",
            "projectId": project_id,
            "transcriptId": transcript_id,
            "jobId": job_id,
            "language": language,
            "durationMs": duration_ms,
        },
    )


def emit_analysis_progress(
    owner_uid: str,
    project_id: str,
    *,
    analysis_run_id: str,
    status: str | StrEnum,
    completed_dimensions: list[str],
    reviewer_statuses: list[dict[str, Any]] | None = None,
) -> None:
    get_hub().publish_json(
        owner_uid,
        project_id,
        {
            "type": "analysis.progress",
            "projectId": project_id,
            "analysisRunId": analysis_run_id,
            "status": _value(status),
            "completedDimensions": completed_dimensions,
            "reviewerStatuses": reviewer_statuses or [],
        },
    )


def emit_analysis_ready(
    owner_uid: str,
    project_id: str,
    *,
    analysis_run_id: str,
    status: str | StrEnum,
    overall_score: float | None,
    finding_counts: dict[str, int] | None,
) -> None:
    get_hub().publish_json(
        owner_uid,
        project_id,
        {
            "type": "analysis.ready",
            "projectId": project_id,
            "analysisRunId": analysis_run_id,
            "status": _value(status),
            "overallScore": overall_score,
            "findingCounts": finding_counts,
        },
    )
