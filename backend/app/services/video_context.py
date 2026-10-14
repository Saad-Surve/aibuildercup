"""Bounded context from a video project's transcript and review, for downstream writers.

Drafts, thumbnails and the YouTube listing all write about a video the creator already
reviewed. This module turns that project's latest analysis run into a small, labelled block
the writer prompts can carry: findings the creator accepted (or the severe ones nobody
rejected), the predicted-interest peaks, a capped transcript excerpt and the persona.

Everything here is read-only and defensive. Findings are read as stored dicts so the
`decision` (creator accepted/revised/dismissed) and `adjudication` (second-pass verdict)
fields are honoured when present and ignored when they are not. Quotes and timestamps come
from the stored data and the transcript, never from a model.
"""

import logging
from collections.abc import Sequence
from typing import Any

from app.schemas.analysis import SEVERITY_RANK, Severity
from app.schemas.transcripts import Transcript, TranscriptSegment
from app.services.firestore_service import (
    FirestoreClient,
    analysis_findings_collection_path,
    analysis_runs_collection_path,
    interest_curve_path,
    user_path,
)
from app.services.storage_service import StorageClient
from app.services.transcript_service import TranscriptService

logger = logging.getLogger(__name__)

#: Runs with usable findings. A partial failure still reviewed most dimensions.
_USABLE_RUN_STATUSES = frozenset({"ready", "partial_failure"})
_RUN_SCAN_LIMIT = 10
_FINDING_SCAN_LIMIT = 2000
_SEVERE = frozenset({Severity.high.value, Severity.critical.value})
_HOOK_WINDOW_MS = 45_000
_QUOTE_CHARS = 240
_ACTION_CHARS = 300

#: Said once, next to the persona, so a prompt can never treat it as evidence about the video.
PERSONA_NOTE = (
    "The creator's own stated preferences (voice, audience, goals). These are preferences, "
    "not facts about this video or its audience."
)


def latest_run_id(client: FirestoreClient, owner_uid: str, project_id: str) -> str | None:
    """The newest analysis run that finished with findings, or None."""
    rows = client.query_collection(
        analysis_runs_collection_path(owner_uid, project_id),
        filters=[],
        order_by=[("createdAt", "DESCENDING")],
        limit=_RUN_SCAN_LIMIT,
        offset=0,
    )
    for run_id, data in rows:
        if data.get("ownerUid") == owner_uid and data.get("status") in _USABLE_RUN_STATUSES:
            return run_id
    return None


def _severity(data: dict[str, Any]) -> str:
    value = str(data.get("severity") or Severity.none.value)
    values = [value if value in {s.value for s in Severity} else Severity.none.value]
    for field in ("editorial", "adjudication"):
        metadata = data.get(field)
        if isinstance(metadata, dict) and metadata.get("adjustedSeverity") in {
            s.value for s in Severity
        }:
            values.append(metadata["adjustedSeverity"])
    return min(values, key=lambda severity: SEVERITY_RANK[Severity(severity)])


def _decision(data: dict[str, Any]) -> tuple[str, str]:
    """(status, revisedAction) from a stored finding's optional `decision` field."""
    raw = data.get("decision")
    if not isinstance(raw, dict):
        return "", ""
    return str(raw.get("status") or ""), str(raw.get("revisedAction") or "").strip()


def _adjudicated_reject(data: dict[str, Any]) -> bool:
    editorial = data.get("editorial")
    if isinstance(editorial, dict) and editorial.get("verdict") in {"drop", "merge"}:
        return True
    raw = data.get("adjudication")
    return isinstance(raw, dict) and str(raw.get("verdict") or "") == "reject"


def _quote(data: dict[str, Any]) -> str:
    evidence = data.get("evidence")
    if not isinstance(evidence, dict):
        return ""
    return str(evidence.get("quote") or "")[:_QUOTE_CHARS]


def _score(data: dict[str, Any]) -> int:
    try:
        return int(round(float(data.get("score", 1))))
    except (TypeError, ValueError):
        return 1


def review_findings(
    client: FirestoreClient,
    owner_uid: str,
    project_id: str,
    run_id: str,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    """The findings worth writing from, most severe first.

    Findings the creator accepted or revised win (a revision's text replaces the original
    suggestion). When none were decided, fall back to high/critical findings that the
    second-pass adjudicator did not reject. Findings the creator dismissed never appear.
    """
    rows = client.query_collection(
        analysis_findings_collection_path(owner_uid, project_id, run_id),
        filters=[],
        order_by=[],
        limit=_FINDING_SCAN_LIMIT,
        offset=0,
    )
    owned = [
        data
        for _, data in rows
        if data.get("ownerUid") == owner_uid
        and _decision(data)[0] not in ("dismissed", "rejected")
        and not _adjudicated_reject(data)
    ]
    chosen = [data for data in owned if _decision(data)[0] in ("accepted", "revised")]
    if not chosen:
        chosen = [data for data in owned if _severity(data) in _SEVERE]

    def rank(data: dict[str, Any]) -> tuple[int, int]:
        return (-SEVERITY_RANK[Severity(_severity(data))], int(data.get("startMs", 0)))

    view: list[dict[str, Any]] = []
    for data in sorted(chosen, key=rank)[:limit]:
        status, revised = _decision(data)
        entry: dict[str, Any] = {
            "dimension": str(data.get("dimension") or ""),
            "severity": _severity(data),
            "startMs": int(data.get("startMs", 0)),
            "endMs": int(data.get("endMs", 0)),
            "quote": _quote(data),
            "suggestion": (revised or str(data.get("suggestion") or ""))[:_ACTION_CHARS],
        }
        if status:
            entry["creatorDecision"] = status
        view.append(entry)
    return view


def review_strengths(
    client: FirestoreClient, owner_uid: str, project_id: str, run_id: str, *, limit: int
) -> list[dict[str, Any]]:
    """Exceptional strengths (score 4-5, nothing wrong) the reviewers said to reinforce."""
    rows = client.query_collection(
        analysis_findings_collection_path(owner_uid, project_id, run_id),
        filters=[],
        order_by=[],
        limit=_FINDING_SCAN_LIMIT,
        offset=0,
    )
    strengths = [
        data
        for _, data in rows
        if data.get("ownerUid") == owner_uid
        and _score(data) >= 4
        and _severity(data) in (Severity.none.value, Severity.low.value)
        and _quote(data)
        and not _adjudicated_reject(data)
    ]
    strengths.sort(key=lambda data: (-_score(data), int(data.get("startMs", 0))))
    return [
        {
            "dimension": str(data.get("dimension") or ""),
            "startMs": int(data.get("startMs", 0)),
            "quote": _quote(data),
        }
        for data in strengths[:limit]
    ]


def _curve(
    client: FirestoreClient, owner_uid: str, project_id: str, run_id: str
) -> dict[str, Any] | None:
    data = client.get_document(interest_curve_path(owner_uid, project_id, run_id))
    if data is None or data.get("ownerUid") != owner_uid or data.get("status") != "ready":
        return None
    return data


def _quote_at(segments: Sequence[TranscriptSegment], start_ms: int, end_ms: int) -> str:
    text = " ".join(s.text.strip() for s in segments if s.endMs > start_ms and s.startMs < end_ms)
    return text[:_QUOTE_CHARS]


def interest_peaks(
    curve: dict[str, Any] | None,
    segments: Sequence[TranscriptSegment],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    """The curve's strongest predicted-interest moments, each with its transcript words."""
    if curve is None:
        return []
    view: list[dict[str, Any]] = []
    for peak in (curve.get("peaks") or [])[:limit]:
        if not isinstance(peak, dict):
            continue
        start, end = int(peak.get("startMs", 0)), int(peak.get("endMs", 0))
        view.append(
            {
                "startMs": start,
                "endMs": end,
                "drivers": [str(d) for d in (peak.get("drivers") or [])][:3],
                "quote": _quote_at(segments, start, end),
            }
        )
    return view


def strongest_hook(
    curve: dict[str, Any] | None, segments: Sequence[TranscriptSegment]
) -> dict[str, Any] | None:
    """The line in the opening seconds that carries the most predicted interest.

    Falls back to the first substantial line when no curve exists. Code picks the line from
    the transcript, so the wording is always the creator's.
    """
    opening = [s for s in segments if s.startMs < _HOOK_WINDOW_MS and s.text.strip()]
    if not opening:
        return None
    best = next((s for s in opening if len(s.text.split()) >= 4), opening[0])
    points = (curve or {}).get("points") or []
    window = [
        p for p in points if isinstance(p, dict) and int(p.get("startMs", 0)) < _HOOK_WINDOW_MS
    ]
    if window:
        top = max(window, key=lambda p: float(p.get("value", 0)))
        start, end = int(top.get("startMs", 0)), int(top.get("endMs", 0))
        hit = next((s for s in opening if s.endMs > start and s.startMs < end), None)
        best = hit or best
    return {"startMs": best.startMs, "quote": best.text.strip()[:_QUOTE_CHARS]}


def persona_preferences(
    client: FirestoreClient, storage: StorageClient, owner_uid: str, *, max_chars: int = 3000
) -> str:
    persona = (client.get_document(user_path(owner_uid)) or {}).get("persona") or {}
    storage_path = persona.get("storagePath")
    if not storage_path:
        return ""
    try:
        return storage.download_text(str(storage_path))[:max_chars]
    except Exception:  # noqa: BLE001 - the persona is context, never a dependency
        logger.info("video context: persona unavailable")
        return ""


def transcript_excerpt(transcript: Transcript, *, max_chars: int) -> dict[str, Any]:
    """The transcript within a character budget, spread across the whole timeline.

    A short transcript is returned whole. A long one keeps every Nth segment so the model
    still sees the opening, the middle and the ending instead of only the first minutes.
    """
    segments = [s for s in transcript.segments if s.text.strip()]
    total = sum(len(s.text) + 1 for s in segments)
    step = max(1, -(-total // max(1, max_chars)))
    lines = [
        {"startMs": s.startMs, "text": s.text.strip()}
        for index, s in enumerate(segments)
        if index % step == 0
    ]
    return {
        "language": transcript.language,
        "durationMs": transcript.durationMs,
        "sampled": step > 1,
        "segments": lines,
    }


def build_review_context(
    client: FirestoreClient,
    owner_uid: str,
    project_id: str,
    *,
    segments: Sequence[TranscriptSegment],
    max_findings: int = 10,
    max_peaks: int = 3,
) -> dict[str, Any]:
    """Findings, strengths, interest peaks and the strongest hook. Empty without a review."""
    try:
        run_id = latest_run_id(client, owner_uid, project_id)
        if run_id is None:
            return {}
        curve = _curve(client, owner_uid, project_id, run_id)
        context: dict[str, Any] = {
            "reviewFindings": review_findings(
                client, owner_uid, project_id, run_id, limit=max_findings
            ),
            "strengthsToKeep": review_strengths(client, owner_uid, project_id, run_id, limit=3),
            "interestPeaks": interest_peaks(curve, segments, limit=max_peaks),
        }
        hook = strongest_hook(curve, segments)
        if hook is not None:
            context["strongestHook"] = hook
        return {key: value for key, value in context.items() if value}
    except Exception:  # noqa: BLE001 - a review is context; writing must not depend on it
        logger.warning("video context: review unavailable for %s", project_id, exc_info=True)
        return {}


def build_video_context(
    client: FirestoreClient,
    storage: StorageClient,
    transcripts: TranscriptService,
    owner_uid: str,
    project_id: str,
    *,
    project_name: str,
    max_transcript_chars: int = 6000,
) -> dict[str, Any] | None:
    """The full labelled block a draft writer carries, or None when there is nothing to use."""
    try:
        transcript = transcripts.get(owner_uid=owner_uid, project_id=project_id)
    except Exception:  # noqa: BLE001 - a video without a transcript has nothing to offer yet
        return None
    if not transcript.segments:
        return None
    context: dict[str, Any] = {
        "videoTitle": project_name,
        "transcript": transcript_excerpt(transcript, max_chars=max_transcript_chars),
        **build_review_context(client, owner_uid, project_id, segments=transcript.segments),
    }
    persona = persona_preferences(client, storage, owner_uid)
    if persona:
        context["creatorPersona"] = {"note": PERSONA_NOTE, "preferences": persona}
    return context
