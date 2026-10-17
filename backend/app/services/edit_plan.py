"""Deterministic edit plans from current creator decisions. No writes or model calls."""

import re
from typing import Any, Literal

from app.errors import BadRequestError, ConflictError, NotFoundError
from app.schemas.edit_plan import EditPlan, KeptSegment, PlannedFinding, RemovedSpan
from app.services.asset_service import AssetService
from app.services.firestore_service import (
    FirestoreClient,
    analysis_findings_collection_path,
    analysis_run_path,
    transcript_path,
)
from app.services.transcript_service import TranscriptService


def classify_action(action: str, dimension: str) -> tuple[Literal["cut", "note"], str]:
    text = action.lower()
    # Replacement edits, negation and mixed instructions require human interpretation.
    if re.search(
        r"\b(rewrite|rephrase|replace|captions?|insert|overlay|add|don't|do not|not|avoid|"
        r"never|keep|retain|preserve|without|if|consider|could|might|"
        r"music|noise|watermark|blur|volume|soundtrack|cutaway|markers?|on-screen text)\b|"
        r"\bcut to\b",
        text,
    ):
        return "note", "Instruction includes a replacement, addition or qualification"
    if re.search(r"\b(remove|delete|cut|trim|shorten|drop(?![- ]offs?)|omit|skip)\b", text):
        return "cut", "Explicit removal instruction"
    if (
        dimension == "pacing_retention"
        and re.search(r"\b(tangent|repetition|repeated|redundant)\b", text)
        and re.search(r"\b(tighten|reduce|eliminate)\b", text)
    ):
        return "cut", "Pacing instruction reduces repetition or a tangent"
    return "note", "Ambiguous or non-removal instruction; creator decides"


def _merge(spans: list[RemovedSpan]) -> list[RemovedSpan]:
    merged: list[RemovedSpan] = []
    for span in sorted(spans, key=lambda s: (s.startMs, s.endMs)):
        if merged and span.startMs <= merged[-1].endMs:
            previous = merged[-1]
            previous.endMs = max(previous.endMs, span.endMs)
            previous.findingIds = list(dict.fromkeys(previous.findingIds + span.findingIds))
        else:
            merged.append(span.model_copy(deep=True))
    return merged


def build_plan(
    *,
    source_asset_id: str,
    run_id: str,
    duration_ms: int,
    findings: list[dict[str, Any]],
    boundaries: list[dict[str, Any]],
    labels: dict[str, Literal["cut", "note"]],
) -> EditPlan:
    spans: list[RemovedSpan] = []
    planned: list[PlannedFinding] = []
    for finding in sorted(findings, key=lambda f: (int(f.get("startMs", 0)), f["findingId"])):
        decision = finding.get("decision") or {}
        revised = decision.get("revisedAction") if decision.get("status") == "revised" else None
        action = str(revised or finding.get("suggestion") or finding.get("proposedAction") or "")
        dimension = str(finding.get("dimension") or "")
        label, reason = classify_action(action, dimension)
        finding_id = str(finding["findingId"])
        if finding_id in labels:
            label, reason = labels[finding_id], "Creator selected this label"
        start = max(0, min(duration_ms, int(finding.get("startMs", 0))))
        end = max(start, min(duration_ms, int(finding.get("endMs", start))))
        item = PlannedFinding(
            findingId=finding_id,
            startMs=start,
            endMs=end,
            dimension=dimension,
            action=action,
            label=label,
            labelReason=reason,
        )
        planned.append(item)
        if label != "cut":
            continue
        # Expand to whole speech units, then use up to 120 ms of surrounding silence.
        units = [
            b
            for b in boundaries
            if int(b["startMs"]) < end
            and int(b["endMs"]) > start
            and int(b["endMs"]) > int(b["startMs"])
        ]
        if units:
            cut_start = max(0, min(int(b["startMs"]) for b in units) - 120)
            cut_end = min(duration_ms, max(int(b["endMs"]) for b in units) + 120)
        elif boundaries and end > start:
            # A pause between speech units is also a valid removal. Preserve small handles.
            previous = max(
                (int(b["endMs"]) for b in boundaries if int(b["endMs"]) <= start), default=0
            )
            following = min(
                (int(b["startMs"]) for b in boundaries if int(b["startMs"]) >= end),
                default=duration_ms,
            )
            cut_start, cut_end = previous + 120, following - 120
        else:
            item.skippedReason = "No complete word or segment overlaps this span"
            continue
        # If padding touches adjacent speech, preserve that entire neighbouring unit.
        changed = True
        while changed:
            changed = False
            for unit in boundaries:
                a, b = int(unit["startMs"]), int(unit["endMs"])
                if a < cut_start < b:
                    cut_start, changed = b, True
                if a < cut_end < b:
                    cut_end, changed = a, True
            if cut_end <= cut_start:
                break
        if cut_end - cut_start < 500:
            item.skippedReason = "Safe removal is shorter than 500 ms"
            continue
        candidate = RemovedSpan(
            startMs=cut_start, endMs=cut_end, findingId=finding_id, findingIds=[finding_id]
        )
        if cut_end - cut_start > duration_ms * 0.4:
            item.skippedReason = "A single span would remove more than 40% of the video"
            continue
        combined = _merge([*spans, candidate])
        if any(s.endMs - s.startMs > duration_ms * 0.4 for s in combined):
            item.skippedReason = "Merged span would remove more than 40% of the video"
            continue
        spans = combined
    kept: list[KeptSegment] = []
    cursor = output = 0
    for span in [*spans, RemovedSpan(startMs=duration_ms, endMs=duration_ms, findingId="")]:
        if span.startMs > cursor:
            kept.append(
                KeptSegment(sourceStartMs=cursor, sourceEndMs=span.startMs, outputStartMs=output)
            )
            output += span.startMs - cursor
        cursor = span.endMs
    return EditPlan(
        sourceAssetId=source_asset_id,
        analysisRunId=run_id,
        findingIds=[f.findingId for f in planned],
        findings=planned,
        keptSegments=kept,
        removedSpans=spans,
        durationMsBefore=duration_ms,
        durationMsAfter=output,
    )


def timecode(ms: int, fps: int) -> str:
    seconds, frames = divmod(round(ms * fps / 1000), fps)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"


def export_plan(plan: EditPlan, *, format: str, fps: int = 30) -> str:
    if format == "markdown":
        lines = [
            "# Edit plan",
            "",
            "Import the cut list in your editor, apply the notes, then upload a new revision.",
            "",
            f"Source asset: {plan.sourceAssetId} · Review: {plan.analysisRunId}",
            f"Frame rate: {fps} fps (non-drop-frame)",
            f"Duration: {plan.durationMsBefore / 1000:.2f}s → {plan.durationMsAfter / 1000:.2f}s",
            "",
        ]
        for item in plan.findings:
            action = " ".join(item.action.split())
            status = (
                f"Skipped cut: {item.skippedReason}" if item.skippedReason else item.label.title()
            )
            lines.append(
                f"- {timecode(item.startMs, fps)}–{timecode(item.endMs, fps)} "
                f"**{status}** ({item.findingId}): {action}"
            )
        lines.extend(["", "## Planned removals (source timeline)", ""])
        lines.extend(
            f"- {timecode(s.startMs, fps)}–{timecode(s.endMs, fps)}: " + ", ".join(s.findingIds)
            for s in plan.removedSpans
        )
        return "\n".join(lines) + "\n"
    lines = [
        "TITLE: RESONANCE EDIT PLAN",
        "FCM: NON-DROP FRAME",
        f"* FRAME RATE: {fps}",
        f"* SOURCE ASSET: {plan.sourceAssetId}",
        "",
    ]
    # Derive record durations from rounded source frames to avoid cumulative EDL drift.
    record_frames = 0
    for index, keep in enumerate(plan.keptSegments, 1):
        start_frames = round(keep.sourceStartMs * fps / 1000)
        end_frames = round(keep.sourceEndMs * fps / 1000)
        next_record = record_frames + end_frames - start_frames
        lines.append(
            f"{index:03d}  SOURCE   AA/V  C        "
            f"{timecode(keep.sourceStartMs, fps)} {timecode(keep.sourceEndMs, fps)} "
            f"{timecode(round(record_frames * 1000 / fps), fps)} "
            f"{timecode(round(next_record * 1000 / fps), fps)}"
        )
        lines.append(f"* FROM CLIP NAME: {plan.sourceAssetId}")
        record_frames = next_record
    for item in plan.findings:
        if item.label == "note" or item.skippedReason:
            text = " ".join(item.action.split())
            lines.append(
                f"* MARKER SOURCE {timecode(item.startMs, fps)} "
                f"{item.findingId}: {text}"
                + (f" [SKIPPED: {item.skippedReason}]" if item.skippedReason else "")
            )
    return "\n".join(lines) + "\n"


class EditPlanService:
    def __init__(
        self,
        client: FirestoreClient,
        assets: AssetService,
        transcripts: TranscriptService,
    ) -> None:
        self.client, self.assets, self.transcripts = client, assets, transcripts

    def source(self, owner_uid: str, project_id: str, run_id: str) -> dict[str, Any]:
        self.assets.projects.get(owner_uid=owner_uid, project_id=project_id)
        run = self.client.get_document(analysis_run_path(owner_uid, project_id, run_id))
        if run is None or run.get("ownerUid") != owner_uid:
            raise NotFoundError("Analysis run not found")
        if run.get("status") not in {"ready", "partial_failure"}:
            raise ConflictError("Wait for the source review to finish")
        asset = self.assets.get_asset(
            owner_uid=owner_uid, project_id=project_id, asset_id=str(run.get("sourceAssetId") or "")
        )
        if asset.type != "source_video" or asset.status != "ready":
            raise ConflictError("Source revision is not ready")
        return run

    def segments(self, owner_uid: str, project_id: str, transcript_id: str) -> list[dict[str, Any]]:
        self.transcripts.get_by_id(
            owner_uid=owner_uid, project_id=project_id, transcript_id=transcript_id
        )
        rows = self.client.query_collection(
            f"{transcript_path(owner_uid, project_id, transcript_id)}/segments",
            filters=[],
            order_by=[("index", "ASCENDING")],
            limit=2001,
            offset=0,
        )
        if len(rows) > 2000:
            raise ConflictError("Transcript exceeds the 2000-segment edit-plan limit")
        return [
            {**data, "segmentId": sid} for sid, data in rows if data.get("ownerUid") == owner_uid
        ]

    def plan(
        self,
        *,
        owner_uid: str,
        project_id: str,
        run_id: str,
        labels: dict[str, Literal["cut", "note"]],
    ) -> EditPlan:
        run = self.source(owner_uid, project_id, run_id)
        transcript_id = str(run["transcriptId"])
        transcript = self.transcripts.get_by_id(
            owner_uid=owner_uid, project_id=project_id, transcript_id=transcript_id
        )
        rows = self.client.query_collection(
            analysis_findings_collection_path(owner_uid, project_id, run_id),
            filters=[],
            order_by=[],
            limit=2001,
            offset=0,
        )
        if len(rows) > 2000:
            raise ConflictError("Review exceeds the 2000-finding edit-plan limit")
        eligible = [
            {**data, "findingId": fid}
            for fid, data in rows
            if data.get("ownerUid") == owner_uid
            and (data.get("decision") or {}).get("status") in {"accepted", "revised"}
        ]
        by_id = {f["findingId"]: f for f in eligible}
        selected = list(by_id)
        if len(selected) > 200:
            raise BadRequestError("At most 200 accepted or revised findings can be exported")
        if any(fid not in by_id for fid in labels):
            raise BadRequestError("Only current accepted or revised findings can be labelled")
        if transcript.durationMs <= 0:
            raise ConflictError("Source duration is unavailable")
        asset = self.assets.get_asset(
            owner_uid=owner_uid, project_id=project_id, asset_id=str(run["sourceAssetId"])
        )
        segments = self.segments(owner_uid, project_id, transcript_id)
        # Legacy transcripts lack word timings; those cues stay indivisible.
        boundaries = [unit for s in segments for unit in (s.get("words") or [s])]
        return build_plan(
            source_asset_id=str(run["sourceAssetId"]),
            run_id=run_id,
            duration_ms=asset.durationMs or transcript.durationMs,
            findings=[by_id[fid] for fid in selected],
            boundaries=boundaries,
            labels=labels,
        )

    def export(
        self,
        *,
        owner_uid: str,
        project_id: str,
        run_id: str,
        labels: dict[str, Literal["cut", "note"]],
        format: str,
        fps: int,
    ) -> str:
        plan = self.plan(
            owner_uid=owner_uid, project_id=project_id, run_id=run_id, labels=labels
        )
        return export_plan(plan, format=format, fps=fps)
