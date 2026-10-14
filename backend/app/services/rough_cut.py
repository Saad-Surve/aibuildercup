"""Conservative, inspectable edits. No model calls and no automatic activation."""

import re
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from app.errors import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.schemas.jobs import JobType
from app.schemas.rough_cut import (
    InsertPlacement,
    KeptSegment,
    PlannedFinding,
    PlannedInsert,
    RemovedSpan,
    RoughCutAccepted,
    RoughCutMetadata,
    RoughCutPlan,
    RoughCutRequest,
)
from app.services.asset_service import AssetService
from app.services.firestore_service import (
    FirestoreClient,
    analysis_findings_collection_path,
    analysis_run_path,
    analysis_runs_collection_path,
    asset_path,
    jobs_collection_path,
    project_object_prefix,
    project_path,
    transcript_path,
    transcripts_collection_path,
)
from app.services.job_service import JobService
from app.services.packaging_service import insert_path
from app.services.transcript_service import TranscriptService, build_vtt


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
) -> RoughCutPlan:
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
    return RoughCutPlan(
        sourceAssetId=source_asset_id,
        analysisRunId=run_id,
        findingIds=[f.findingId for f in planned],
        findings=planned,
        keptSegments=kept,
        removedSpans=spans,
        durationMsBefore=duration_ms,
        durationMsAfter=output,
    )


def remap_segments(segments: list[dict[str, Any]], kept: list[KeptSegment]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for keep in kept:
        for segment in segments:
            start, end = int(segment["startMs"]), int(segment["endMs"])
            if end <= keep.sourceStartMs or start >= keep.sourceEndMs:
                continue
            offset = keep.outputStartMs - keep.sourceStartMs
            words = segment.get("words") or []
            retained_words = [
                {**w, "startMs": int(w["startMs"]) + offset, "endMs": int(w["endMs"]) + offset}
                for w in words
                if int(w["startMs"]) >= keep.sourceStartMs and int(w["endMs"]) <= keep.sourceEndMs
            ]
            if words:
                if not retained_words:
                    continue
                start = int(retained_words[0]["startMs"]) - offset
                end = int(retained_words[-1]["endMs"]) - offset
            elif start < keep.sourceStartMs or end > keep.sourceEndMs:
                # Without word timings the planner only cuts at whole-segment boundaries.
                raise ValueError("A cut would split an untimed transcript segment")
            index = len(result)
            result.append(
                {
                    **segment,
                    "segmentId": f"seg-{index:05d}",
                    "index": index,
                    "startMs": start + offset,
                    "endMs": end + offset,
                    "text": " ".join(str(w["word"]) for w in retained_words)
                    if words
                    else segment["text"],
                    "words": retained_words,
                }
            )
    return result


def timecode(ms: int, fps: int) -> str:
    seconds, frames = divmod(round(ms * fps / 1000), fps)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"


def export_plan(plan: RoughCutPlan, *, format: str, fps: int = 30) -> str:
    if format == "markdown":
        lines = [
            "# Rough-cut edit plan",
            "",
            "Preview only — the creator approves activation.",
            "",
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
        lines.extend(["", "## Actual removals (source timeline)", ""])
        lines.extend(
            f"- {timecode(s.startMs, fps)}–{timecode(s.endMs, fps)}: " + ", ".join(s.findingIds)
            for s in plan.removedSpans
        )
        if plan.inserts:
            lines.extend(["", "## Packaging overlays (cut timeline)", ""])
            for insert in plan.inserts:
                headline = " ".join(insert.headline.split())
                if insert.skippedReason:
                    lines.append(f"- Skipped {headline}: {insert.skippedReason}")
                for placement in insert.placements:
                    lines.append(
                        f"- {timecode(placement.outputStartMs, fps)}–"
                        f"{timecode(placement.outputEndMs, fps)}: {headline} ({insert.insertId})"
                    )
        return "\n".join(lines) + "\n"
    lines = [
        "TITLE: RESONANCE ROUGH CUT",
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
    for insert in plan.inserts:
        lines.append(f"* INSERT {insert.insertId}: {' '.join(insert.headline.split())}")
        for placement in insert.placements:
            lines.append(
                f"* OVERLAY RECORD {timecode(placement.outputStartMs, fps)} "
                f"{timecode(placement.outputEndMs, fps)}"
            )
        if insert.skippedReason:
            lines.append(f"* SKIPPED INSERT: {insert.skippedReason}")
    return "\n".join(lines) + "\n"


class RoughCutService:
    def __init__(
        self,
        client: FirestoreClient,
        assets: AssetService,
        jobs: JobService,
        transcripts: TranscriptService,
    ) -> None:
        self.client, self.assets, self.jobs, self.transcripts = client, assets, jobs, transcripts

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
            limit=2000,
            offset=0,
        )
        return [
            {**data, "segmentId": sid} for sid, data in rows if data.get("ownerUid") == owner_uid
        ]

    def load_insert(
        self,
        owner_uid: str,
        project_id: str,
        insert_id: str,
        source_asset_id: str,
        transcript_id: str,
    ) -> dict[str, Any]:
        data = self.client.get_document(insert_path(owner_uid, project_id, insert_id))
        if data is None or data.get("ownerUid") != owner_uid:
            raise NotFoundError("Packaging insert not found")
        if (
            data.get("status") != "ready"
            or data.get("sourceAssetId") != source_asset_id
            or data.get("transcriptId") != transcript_id
            or not str(data.get("storagePath") or "").startswith(
                project_object_prefix(owner_uid, project_id)
            )
        ):
            raise ConflictError("Choose a rendered insert from this source review")
        return data

    def plan(
        self, *, owner_uid: str, project_id: str, run_id: str, payload: RoughCutRequest
    ) -> tuple[RoughCutPlan, str]:
        run = self.source(owner_uid, project_id, run_id)
        transcript_id = str(run["transcriptId"])
        transcript = self.transcripts.get_by_id(
            owner_uid=owner_uid, project_id=project_id, transcript_id=transcript_id
        )
        rows = self.client.query_collection(
            analysis_findings_collection_path(owner_uid, project_id, run_id),
            filters=[],
            order_by=[],
            limit=2000,
            offset=0,
        )
        eligible = [
            {**data, "findingId": fid}
            for fid, data in rows
            if data.get("ownerUid") == owner_uid
            and (data.get("decision") or {}).get("status") in {"accepted", "revised"}
        ]
        by_id = {f["findingId"]: f for f in eligible}
        selected = (
            list(dict.fromkeys(payload.findingIds))
            if payload.findingIds is not None
            else list(by_id)
        )
        if len(selected) > 200:
            raise BadRequestError("Select at most 200 findings")
        if any(fid not in by_id for fid in selected) or any(
            fid not in selected for fid in payload.labels
        ):
            raise BadRequestError("Only selected accepted or revised findings can be labelled")
        if transcript.durationMs <= 0:
            raise ConflictError("Source duration is unavailable")
        asset = self.assets.get_asset(
            owner_uid=owner_uid, project_id=project_id, asset_id=str(run["sourceAssetId"])
        )
        segments = self.segments(owner_uid, project_id, transcript_id)
        # Legacy transcripts lack word timings; those cues stay indivisible.
        boundaries = [unit for s in segments for unit in (s.get("words") or [s])]
        plan = build_plan(
            source_asset_id=str(run["sourceAssetId"]),
            run_id=run_id,
            duration_ms=asset.durationMs or transcript.durationMs,
            findings=[by_id[fid] for fid in selected],
            boundaries=boundaries,
            labels=payload.labels,
        )
        for insert_id in dict.fromkeys(payload.insertIds):
            data = self.load_insert(
                owner_uid, project_id, insert_id, plan.sourceAssetId, transcript_id
            )
            start = int(data["sourceStartMs"])
            end = min(plan.durationMsBefore, int(data["sourceEndMs"]), start + 6000)
            placements = [
                InsertPlacement(
                    insertStartMs=max(start, keep.sourceStartMs) - start,
                    outputStartMs=keep.outputStartMs
                    + max(start, keep.sourceStartMs)
                    - keep.sourceStartMs,
                    outputEndMs=keep.outputStartMs
                    + min(end, keep.sourceEndMs)
                    - keep.sourceStartMs,
                )
                for keep in plan.keptSegments
                if min(end, keep.sourceEndMs) > max(start, keep.sourceStartMs)
            ]
            plan.insertIds.append(insert_id)
            plan.inserts.append(
                PlannedInsert(
                    insertId=insert_id,
                    headline=str(data["headline"]),
                    placements=placements,
                    skippedReason=None if placements else "Insert anchor is entirely removed",
                )
            )
        return plan, transcript_id

    def create(
        self, *, owner_uid: str, project_id: str, run_id: str, payload: RoughCutRequest
    ) -> RoughCutAccepted:
        if owner_uid in self.assets.settings.read_only_user_uids:
            raise ForbiddenError("The demo account cannot render previews")
        plan, transcript_id = self.plan(
            owner_uid=owner_uid, project_id=project_id, run_id=run_id, payload=payload
        )
        if not plan.removedSpans:
            raise BadRequestError("No safe cuts selected. Review the labels and skipped reasons.")
        asset_id = uuid4().hex
        job = self.jobs.create(
            owner_uid=owner_uid,
            project_id=project_id,
            job_type=JobType.rough_cut,
            idempotency_key=f"rough-cut:{asset_id}",
            input={"assetId": asset_id, "transcriptId": transcript_id, "plan": plan.model_dump()},
            requested_by=owner_uid,
        )
        return RoughCutAccepted(jobId=job.jobId, assetId=asset_id, status=job.status, plan=plan)

    def export(
        self,
        *,
        owner_uid: str,
        project_id: str,
        run_id: str,
        asset_id: str | None,
        format: str,
        fps: int,
    ) -> str:
        self.source(owner_uid, project_id, run_id)
        if not asset_id:
            asset_id = next(
                (
                    a.assetId
                    for a in self.assets.list_assets(owner_uid=owner_uid, project_id=project_id)
                    if a.roughCut and a.roughCut.analysisRunId == run_id and a.status == "ready"
                ),
                None,
            )
        if not asset_id:
            raise NotFoundError("Render a rough cut before exporting")
        asset = self.assets.get_asset(owner_uid=owner_uid, project_id=project_id, asset_id=asset_id)
        if not asset.roughCut or asset.status != "ready":
            raise NotFoundError("Ready rough cut not found")
        data = self.client.get_document(asset_path(owner_uid, project_id, asset_id)) or {}
        plan = RoughCutPlan.model_validate(data.get("roughCutPlan"))
        if plan.analysisRunId != run_id:
            raise NotFoundError("Rough cut does not belong to this run")
        return export_plan(plan, format=format, fps=fps)

    def captions(self, *, owner_uid: str, project_id: str, asset_id: str) -> str:
        asset = self.assets.get_asset(owner_uid=owner_uid, project_id=project_id, asset_id=asset_id)
        if asset.type != "source_video" or asset.status != "ready":
            raise NotFoundError("Ready source revision not found")
        self.assets.projects.get(owner_uid=owner_uid, project_id=project_id)
        rows = self.client.query_collection(
            transcripts_collection_path(owner_uid, project_id),
            filters=[("sourceAssetId", "==", asset_id)],
            order_by=[],
            limit=2000,
            offset=0,
        )
        owned = [
            (tid, data)
            for tid, data in rows
            if data.get("ownerUid") == owner_uid and data.get("status") == "ready"
        ]
        if not owned:
            raise NotFoundError("Transcript not ready")
        transcript_id, _ = max(owned, key=lambda row: int(row[1].get("version", 0)))
        return build_vtt(self.segments(owner_uid, project_id, transcript_id))

    def discard(self, *, owner_uid: str, project_id: str, asset_id: str) -> None:
        if owner_uid in self.assets.settings.read_only_user_uids:
            raise ForbiddenError("The demo account cannot discard previews")
        project = self.assets.projects.get(owner_uid=owner_uid, project_id=project_id)
        asset = self.assets.get_asset(owner_uid=owner_uid, project_id=project_id, asset_id=asset_id)
        if not asset.roughCut or project.sourceAssetId == asset_id:
            raise ConflictError("Only inactive rough-cut previews can be discarded")
        runs = self.client.query_collection(
            analysis_runs_collection_path(owner_uid, project_id),
            filters=[],
            order_by=[],
            limit=2000,
            offset=0,
        )
        owned_runs = [
            (rid, d)
            for rid, d in runs
            if d.get("ownerUid") == owner_uid and d.get("sourceAssetId") == asset_id
        ]
        if any(d.get("status") in {"queued", "running"} for _, d in owned_runs):
            raise ConflictError("Wait for the cut's review to finish before discarding")
        descendants = [
            a
            for a in self.assets.list_assets(owner_uid=owner_uid, project_id=project_id)
            if a.roughCut and a.roughCut.sourceAssetId == asset_id
        ]
        if descendants:
            raise ConflictError("Discard previews derived from this cut first")
        jobs = self.client.query_collection(
            jobs_collection_path(owner_uid, project_id),
            filters=[],
            order_by=[],
            limit=2000,
            offset=0,
        )
        if any(
            data.get("ownerUid") == owner_uid
            and data.get("status") in {"queued", "running"}
            and (data.get("input") or {}).get("plan", {}).get("sourceAssetId") == asset_id
            for _, data in jobs
        ):
            raise ConflictError("Wait for previews derived from this cut to finish")
        prefix = f"{project_object_prefix(owner_uid, project_id)}rough-cuts/{asset_id}/"
        self.assets.storage.delete_prefix(prefix)
        for tid, data in self.client.query_collection(
            transcripts_collection_path(owner_uid, project_id),
            filters=[],
            order_by=[],
            limit=2000,
            offset=0,
        ):
            if data.get("ownerUid") == owner_uid and data.get("sourceAssetId") == asset_id:
                self.client.delete_document_tree(transcript_path(owner_uid, project_id, tid))
        for rid, _ in owned_runs:
            self.assets.storage.delete_prefix(
                f"{project_object_prefix(owner_uid, project_id)}review-context/{rid}/"
            )
            self.client.delete_document_tree(analysis_run_path(owner_uid, project_id, rid))
        self.client.delete_document_tree(asset_path(owner_uid, project_id, asset_id))
        self.client.update_document(
            project_path(owner_uid, project_id), {"updatedAt": datetime.now(UTC)}
        )

    @staticmethod
    def metadata(plan: RoughCutPlan) -> dict[str, Any]:
        return RoughCutMetadata.model_validate(plan.model_dump()).model_dump()
