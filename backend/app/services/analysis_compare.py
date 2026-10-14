"""Deterministic, read-only comparison of pinned analysis runs.

No model or object-storage calls. Cut metadata gives an exact map; independent revisions use
bounded normalized-token alignment with interpolated segment word times. Unmapped
footage and incomplete reviews cannot be counted as successful fixes.
"""

import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from app.errors import BadRequestError, ConflictError, NotFoundError
from app.schemas.analysis import (
    SEVERITY_RANK,
    AnalysisDimension,
    Finding,
    HeatmapBin,
    HeatmapCoverage,
    InterestCurve,
    Severity,
)
from app.schemas.analysis_compare import (
    AnalysisComparison,
    ComparisonAlignment,
    ComparisonBin,
    ComparisonBinCounts,
    ComparisonFinding,
    ComparisonInterestChange,
    ComparisonInterestPoint,
    ComparisonRun,
    ComparisonSpan,
    ComparisonSummary,
    ComparisonTimeSegment,
)
from app.services.analysis_service import _to_finding, is_owner
from app.services.firestore_service import (
    FirestoreClient,
    analysis_findings_collection_path,
    analysis_run_path,
    asset_path,
    interest_curve_path,
    project_path,
    transcript_path,
)
from app.services.heatmap import aggregate_bins, normalize_span

_MAX_FINDINGS = 2000
_MAX_SEGMENTS = 20_000
_MAX_TOKENS = 8000
_MATCH_TOLERANCE_MS = 5000


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


@dataclass
class RunInput:
    run_id: str
    document: dict[str, Any]
    asset: dict[str, Any]
    transcript: dict[str, Any]
    segments: list[dict[str, Any]]
    findings: list[Finding]
    accepted_ids: set[str]
    coverage: list[HeatmapCoverage]
    interest: InterestCurve | None

    @property
    def duration_ms(self) -> int:
        return max(0, int(self.transcript.get("durationMs") or 0))


def _tokens(segments: list[dict[str, Any]]) -> list[tuple[str, int, int]]:
    words: list[tuple[str, int, int]] = []
    for segment in sorted(segments, key=lambda s: (s.get("startMs", 0), s.get("index", 0))):
        # Keep combining marks with their letters (e.g. Hindi vowel signs).
        text = unicodedata.normalize("NFKC", str(segment.get("text") or "")).casefold()
        normalized = "".join(
            char if unicodedata.category(char)[0] in "LMN" else " " for char in text
        )
        tokens = normalized.split()
        start, end = int(segment.get("startMs") or 0), int(segment.get("endMs") or 0)
        if end <= start or not tokens:
            continue
        for index, token in enumerate(tokens):
            words.append(
                (
                    token,
                    start + (end - start) * index // len(tokens),
                    start + (end - start) * (index + 1) // len(tokens),
                )
            )
            if len(words) > _MAX_TOKENS:
                return words
    return words


def _rough_cut(base: RunInput, target: RunInput) -> ComparisonAlignment | None:
    cut = _dict(target.asset.get("roughCut"))
    if not cut or cut.get("sourceAssetId") != base.document.get("sourceAssetId"):
        return None
    segments: list[ComparisonTimeSegment] = []
    source_end = output_end = 0
    removed: list[ComparisonSpan] = []
    try:
        if (
            int(cut["durationMsBefore"]) != base.duration_ms
            or int(cut["durationMsAfter"]) != target.duration_ms
        ):
            return None
        for raw in cut["keptSegments"]:
            start, end, output = (
                int(raw["sourceStartMs"]),
                int(raw["sourceEndMs"]),
                int(raw["outputStartMs"]),
            )
            if not (source_end <= start < end <= base.duration_ms) or output != output_end:
                return None
            if start > source_end:
                removed.append(ComparisonSpan(startMs=source_end, endMs=start))
            output_end = output + end - start
            segments.append(
                ComparisonTimeSegment(
                    sourceStartMs=start,
                    sourceEndMs=end,
                    targetStartMs=output,
                    targetEndMs=output_end,
                )
            )
            source_end = end
        if not segments or output_end != target.duration_ms:
            return None
        if source_end < base.duration_ms:
            removed.append(ComparisonSpan(startMs=source_end, endMs=base.duration_ms))
    except (KeyError, TypeError, ValueError):
        return None
    return ComparisonAlignment(
        method="rough_cut",
        confidence=1,
        targetTimeline="source",
        segments=segments,
        removedSpans=removed,
        note=(
            "Exact kept-segment map to the before video's source timeline. "
            "Hatched spans were removed."
        ),
    )


def _append_segment(segments: list[ComparisonTimeSegment], segment: ComparisonTimeSegment) -> None:
    if segments:
        previous = segments[-1]
        same_rate = (previous.sourceEndMs - previous.sourceStartMs) * (
            segment.targetEndMs - segment.targetStartMs
        ) == (segment.sourceEndMs - segment.sourceStartMs) * (
            previous.targetEndMs - previous.targetStartMs
        )
        if (
            same_rate
            and previous.sourceEndMs == segment.sourceStartMs
            and previous.targetEndMs == segment.targetStartMs
        ):
            previous.sourceEndMs = segment.sourceEndMs
            previous.targetEndMs = segment.targetEndMs
            return
    segments.append(segment)


def build_alignment(base: RunInput, target: RunInput) -> ComparisonAlignment:
    if base.document.get("sourceAssetId") and base.document.get(
        "sourceAssetId"
    ) == target.document.get("sourceAssetId"):
        duration = min(base.duration_ms, target.duration_ms)
        return ComparisonAlignment(
            method="identity",
            confidence=1,
            targetTimeline="source",
            segments=[
                ComparisonTimeSegment(
                    sourceStartMs=0, sourceEndMs=duration, targetStartMs=0, targetEndMs=duration
                )
            ]
            if duration
            else [],
            note="Both reviews use the same source asset.",
        )
    cut = _rough_cut(base, target)
    if cut is not None:
        return cut
    before, after = _tokens(base.segments), _tokens(target.segments)
    confidence = 0.0
    segments: list[ComparisonTimeSegment] = []
    matched = 0
    bounded = max(len(before), len(after)) <= _MAX_TOKENS
    if before and after and bounded:
        matcher = SequenceMatcher(
            None, [w[0] for w in before], [w[0] for w in after], autojunk=False
        )
        for block in matcher.get_matching_blocks():
            if block.size < 3:
                continue
            matched += block.size
            for offset in range(block.size):
                source_word, target_word = before[block.a + offset], after[block.b + offset]
                if source_word[2] <= source_word[1] or target_word[2] <= target_word[1]:
                    continue
                _append_segment(
                    segments,
                    ComparisonTimeSegment(
                        sourceStartMs=source_word[1],
                        sourceEndMs=source_word[2],
                        targetStartMs=target_word[1],
                        targetEndMs=target_word[2],
                    ),
                )
        confidence = matched / min(len(before), len(after))
    strong = matched >= 6 and confidence >= 0.55
    return ComparisonAlignment(
        method="transcript" if strong else "unaligned",
        confidence=round(confidence, 4),
        targetTimeline="source" if strong else "target",
        segments=segments if strong else [],
        note=(
            (
                "Transcript alignment: matching blocks of at least 3 tokens; "
                "word times interpolate within transcript segments. Confidence is matched "
                "tokens / shorter transcript, not a calibrated probability. "
                "Unmatched footage remains on its own timeline."
            )
            if strong
            else (
                "Transcript alignment is too weak (requires 6 retained tokens and 55% overlap), "
                "missing, or exceeds 8,000 tokens. After uses its own timeline; "
                "fixes are not assumed resolved."
            )
        ),
    )


def map_span(
    start: int, end: int, alignment: ComparisonAlignment, *, inverse: bool = False
) -> list[tuple[ComparisonSpan, ComparisonSpan]]:
    """(mapped span, native slice), split at every discontinuity; never bridge cuts."""
    result: list[tuple[ComparisonSpan, ComparisonSpan]] = []
    for segment in alignment.segments:
        lo, hi = (
            (segment.sourceStartMs, segment.sourceEndMs)
            if inverse
            else (segment.targetStartMs, segment.targetEndMs)
        )
        out_lo, out_hi = (
            (segment.targetStartMs, segment.targetEndMs)
            if inverse
            else (segment.sourceStartMs, segment.sourceEndMs)
        )
        left, right = max(start, lo), min(max(start + 1, end), hi)
        if right <= left or hi <= lo:
            continue
        mapped_start = out_lo + round((left - lo) * (out_hi - out_lo) / (hi - lo))
        mapped_end = out_lo + round((right - lo) * (out_hi - out_lo) / (hi - lo))
        result.append(
            (
                ComparisonSpan(startMs=mapped_start, endMs=max(mapped_start + 1, mapped_end)),
                ComparisonSpan(startMs=left, endMs=right),
            )
        )
    return result


def _gaps(start: int, end: int, spans: list[ComparisonSpan]) -> list[ComparisonSpan]:
    gaps: list[ComparisonSpan] = []
    cursor = start
    for span in sorted(spans, key=lambda s: s.startMs):
        left, right = max(start, span.startMs), min(end, span.endMs)
        if right <= left:
            continue
        if left > cursor:
            gaps.append(ComparisonSpan(startMs=cursor, endMs=left))
        cursor = max(cursor, right)
    if cursor < end:
        gaps.append(ComparisonSpan(startMs=cursor, endMs=end))
    return gaps


def _counts(bins: list[HeatmapBin]) -> ComparisonBinCounts:
    by_time: dict[int, Severity] = {}
    for bin_ in bins:
        if bin_.severity not in (Severity.critical, Severity.high, Severity.medium):
            continue
        previous = by_time.get(bin_.startMs, Severity.none)
        if SEVERITY_RANK[bin_.severity] > SEVERITY_RANK[previous]:
            by_time[bin_.startMs] = bin_.severity
    return ComparisonBinCounts(
        total=len(by_time),
        **{
            severity.value: list(by_time.values()).count(severity)
            for severity in (Severity.critical, Severity.high, Severity.medium)
        },
    )


def _native_bins(run: RunInput) -> list[HeatmapBin]:
    return [
        b.model_copy(update={"endMs": min(b.endMs, run.duration_ms)})
        for b in aggregate_bins(run.findings, duration_ms=run.duration_ms)
    ]


def _display_run(
    run: RunInput, bins: list[HeatmapBin], alignment: ComparisonAlignment | None = None
) -> ComparisonRun:
    displayed: list[ComparisonBin] = []
    unmapped: list[ComparisonBin] = []
    for bin_ in bins:
        pairs = (
            map_span(bin_.startMs, bin_.endMs, alignment)
            if alignment
            else [
                (
                    ComparisonSpan(startMs=bin_.startMs, endMs=bin_.endMs),
                    ComparisonSpan(startMs=bin_.startMs, endMs=bin_.endMs),
                )
            ]
        )
        for index, (mapped, native) in enumerate(pairs):
            displayed.append(
                ComparisonBin(
                    **{
                        **bin_.model_dump(),
                        **mapped.model_dump(),
                        "binId": f"{bin_.binId}:{index}",
                    },
                    nativeStartMs=native.startMs,
                    nativeEndMs=native.endMs,
                )
            )
        if alignment:
            for index, gap in enumerate(
                _gaps(bin_.startMs, bin_.endMs, [native for _, native in pairs])
            ):
                unmapped.append(
                    ComparisonBin(
                        **{
                            **bin_.model_dump(),
                            **gap.model_dump(),
                            "binId": f"{bin_.binId}:unmapped:{index}",
                        },
                        nativeStartMs=gap.startMs,
                        nativeEndMs=gap.endMs,
                    )
                )
    coverage: list[HeatmapCoverage] = []
    for span in run.coverage:
        mapped_spans = (
            [mapped for mapped, _ in map_span(span.startMs, span.endMs, alignment)]
            if alignment
            else [span]
        )
        coverage.extend(
            HeatmapCoverage(dimension=span.dimension, startMs=s.startMs, endMs=s.endMs)
            for s in mapped_spans
        )
    interest: list[ComparisonInterestPoint] = []
    if run.interest:
        for point in run.interest.points:
            interest_spans = (
                [mapped for mapped, _ in map_span(point.startMs, point.endMs, alignment)]
                if alignment
                else [point]
            )
            interest.extend(
                ComparisonInterestPoint(
                    startMs=s.startMs, endMs=s.endMs, value=point.value, baseline=point.baseline
                )
                for s in interest_spans
            )
    dimensions = list(
        dict.fromkeys(
            [AnalysisDimension(d) for d in run.document.get("requestedDimensions", [])]
            + [f.dimension for f in run.findings]
        )
    )
    return ComparisonRun(
        runId=run.run_id,
        sourceAssetId=run.document.get("sourceAssetId"),
        durationMs=run.duration_ms,
        status=run.document["status"],
        dimensions=dimensions,
        bins=displayed,
        unmappedBins=unmapped,
        coverage=coverage,
        interest=interest,
    )


def _covered(run: RunInput, finding: Finding, spans: list[ComparisonSpan]) -> bool:
    coverage = [
        ComparisonSpan(startMs=s.startMs, endMs=s.endMs)
        for s in run.coverage
        if s.dimension == finding.dimension
    ]
    if not coverage:
        # Historical fully successful runs predate recorded coverage.
        return (
            not run.document.get("coverage")
            and run.document.get("status") == "ready"
            and finding.dimension in run.document.get("completedDimensions", [])
        )
    return bool(spans) and all(not _gaps(s.startMs, s.endMs, coverage) for s in spans)


def _distance(left: ComparisonSpan, right: ComparisonSpan) -> int:
    return max(0, left.startMs - right.endMs, right.startMs - left.endMs)


def compare_findings(
    base: RunInput, target: RunInput, alignment: ComparisonAlignment
) -> list[ComparisonFinding]:
    target_spans_by_id = {
        f.findingId: normalize_span(f.startMs, f.endMs, duration_ms=target.duration_ms)
        for f in target.findings
    }
    mapped = {
        finding_id: [s for s, _ in map_span(span[0], span[1], alignment)] if span else []
        for finding_id, span in target_spans_by_id.items()
    }
    matches: dict[str, str] = {}
    used: set[str] = set()
    for before in base.findings:
        span = normalize_span(before.startMs, before.endMs, duration_ms=base.duration_ms)
        if span is None:
            continue
        target_spans = [s for s, _ in map_span(span[0], span[1], alignment, inverse=True)]
        if not target_spans:
            continue
        candidates: list[tuple[int, int, str]] = []
        for after in target.findings:
            if before.dimension != after.dimension or (
                (before.severity == Severity.none) != (after.severity == Severity.none)
            ):
                continue
            target_span = target_spans_by_id[after.findingId]
            if target_span is None:
                continue
            distance = min(
                _distance(s, ComparisonSpan(startMs=target_span[0], endMs=target_span[1]))
                for s in target_spans
            )
            if distance <= _MATCH_TOLERANCE_MS:
                candidates.append(
                    (
                        distance,
                        int(before.findingType != after.findingType),
                        after.findingId,
                    )
                )
        if candidates:
            _, _, after_id = min(candidates)
            matches[before.findingId] = after_id
            used.add(after_id)
    targets = {f.findingId: f for f in target.findings}
    changes: list[ComparisonFinding] = []
    for before in base.findings:
        span = normalize_span(before.startMs, before.endMs, duration_ms=base.duration_ms)
        source_spans = [ComparisonSpan(startMs=span[0], endMs=span[1])] if span else []
        target_spans = (
            [s for s, _ in map_span(span[0], span[1], alignment, inverse=True)] if span else []
        )
        change = ComparisonFinding(
            status="uncompared",
            reason="alignment_uncertain",
            baseFinding=before,
            sourceSpans=source_spans,
            accepted=before.findingId in base.accepted_ids,
        )
        if before.findingId in matches:
            change.status, change.reason = "persists", "matched"
            change.targetFinding = targets[matches[before.findingId]]
        elif alignment.method == "rough_cut" and span and not target_spans:
            change.status, change.reason = "resolved", "removed"
        elif target_spans:
            assert span is not None
            retained_source = [
                native for _, native in map_span(span[0], span[1], alignment, inverse=True)
            ]
            fully_mapped = alignment.method == "rough_cut" or all(
                not _gaps(s.startMs, s.endMs, retained_source) for s in source_spans
            )
            if not fully_mapped:
                change.reason = "alignment_uncertain"
            elif _covered(target, before, target_spans):
                change.status, change.reason = "resolved", "no_match"
            else:
                change.reason = "review_incomplete"
        changes.append(change)
    for after in target.findings:
        if after.findingId not in used:
            changes.append(
                ComparisonFinding(
                    status="uncompared" if alignment.targetTimeline == "target" else "new",
                    reason=(
                        "alignment_uncertain"
                        if alignment.targetTimeline == "target"
                        else "unmatched_target"
                    ),
                    targetFinding=after,
                    sourceSpans=mapped[after.findingId],
                )
            )
    return changes


def _mean_lift(curve: InterestCurve) -> float:
    weight = sum(max(0, p.endMs - p.startMs) for p in curve.points)
    return (
        sum((p.value - p.baseline) * max(0, p.endMs - p.startMs) for p in curve.points) / weight
        if weight
        else 0.0
    )


def build_comparison(base: RunInput, target: RunInput) -> AnalysisComparison:
    alignment = build_alignment(base, target)
    base_bins, target_bins = _native_bins(base), _native_bins(target)
    findings = compare_findings(base, target, alignment)
    interest_change = None
    if base.interest and target.interest and base.interest.points and target.interest.points:
        before, after = _mean_lift(base.interest), _mean_lift(target.interest)
        interest_change = ComparisonInterestChange(
            meanAboveBaselineBefore=round(before, 4),
            meanAboveBaselineAfter=round(after, 4),
            delta=round(after - before, 4),
            note=(
                "Duration-weighted distance above each run's own normalized baseline. "
                "Relative model signals, not measured retention or calibrated improvement."
            ),
        )
    return AnalysisComparison(
        base=_display_run(base, base_bins),
        target=_display_run(
            target, target_bins, alignment if alignment.targetTimeline == "source" else None
        ),
        alignment=alignment,
        findings=findings,
        summary=ComparisonSummary(
            flaggedBinsBefore=_counts(base_bins),
            flaggedBinsAfter=_counts(target_bins),
            durationMsBefore=base.duration_ms,
            durationMsAfter=target.duration_ms,
            acceptedFindingsTotal=len(base.accepted_ids),
            acceptedFindingsResolved=sum(c.accepted and c.status == "resolved" for c in findings),
            newFindingsCount=sum(c.status == "new" for c in findings),
            newIssuesCount=sum(
                c.status == "new"
                and c.targetFinding is not None
                and c.targetFinding.severity != Severity.none
                for c in findings
            ),
            uncomparedFindingsCount=sum(c.status == "uncompared" for c in findings),
            interestChange=interest_change,
        ),
    )


class AnalysisCompareService:
    def __init__(self, client: FirestoreClient) -> None:
        self.client = client

    def _owned(self, path: str, owner_uid: str, project_id: str) -> dict[str, Any]:
        document = self.client.get_document(path)
        if (
            document is None
            or not is_owner(document, owner_uid)
            or document.get("projectId", project_id) != project_id
        ):
            raise NotFoundError("Comparison input not found")
        return document

    def _rows(self, path: str, owner_uid: str, limit: int) -> list[tuple[str, dict[str, Any]]]:
        rows = self.client.query_collection(
            path, filters=[], order_by=[], limit=limit + 1, offset=0
        )
        if len(rows) > limit:
            raise ConflictError("Comparison input exceeds the supported document limit")
        if any(not is_owner(doc, owner_uid) for _, doc in rows):
            raise NotFoundError("Comparison input not found")
        return rows

    def _load(self, owner_uid: str, project_id: str, run_id: str) -> RunInput:
        document = self._owned(
            analysis_run_path(owner_uid, project_id, run_id), owner_uid, project_id
        )
        if document.get("status") not in ("ready", "partial_failure"):
            raise ConflictError("Choose two completed analysis runs")
        transcript_id = str(document.get("transcriptId") or "")
        if not transcript_id:
            raise NotFoundError("Comparison transcript not found")
        transcript = self._owned(
            transcript_path(owner_uid, project_id, transcript_id), owner_uid, project_id
        )
        asset_id = document.get("sourceAssetId") or transcript.get("sourceAssetId")
        if asset_id and transcript.get("sourceAssetId") not in (None, asset_id):
            raise NotFoundError("Comparison asset does not match the pinned transcript")
        document = {**document, "sourceAssetId": asset_id}
        asset = (
            self._owned(asset_path(owner_uid, project_id, asset_id), owner_uid, project_id)
            if asset_id
            else {}
        )
        segments = [
            doc
            for _, doc in self._rows(
                f"{transcript_path(owner_uid, project_id, transcript_id)}/segments",
                owner_uid,
                _MAX_SEGMENTS,
            )
        ]
        findings: list[Finding] = []
        accepted_ids: set[str] = set()
        for finding_id, raw in self._rows(
            analysis_findings_collection_path(owner_uid, project_id, run_id),
            owner_uid,
            _MAX_FINDINGS,
        ):
            decision, adjudication = _dict(raw.get("decision")), _dict(raw.get("adjudication"))
            if decision.get("status") == "dismissed" or adjudication.get("verdict") == "reject":
                continue
            effective = dict(raw)
            # These optional dictionaries are interpreted above, independently of
            # the finding-decision branch's stricter wire models after it merges.
            for field in ("decision", "adjudication", "reconciliation"):
                effective.pop(field, None)
            adjusted = adjudication.get("adjustedSeverity")
            if (
                adjudication.get("verdict") == "downgrade"
                and isinstance(adjusted, str)
                and adjusted in {s.value for s in Severity}
                and SEVERITY_RANK[Severity(adjusted)]
                <= SEVERITY_RANK[Severity(raw.get("severity", Severity.none.value))]
            ):
                effective["severity"] = adjusted
            findings.append(_to_finding(finding_id, effective))
            if decision.get("status") in ("accepted", "revised"):
                accepted_ids.add(finding_id)
        coverage: list[HeatmapCoverage] = []
        for raw in document.get("coverage") or []:
            try:
                coverage.append(HeatmapCoverage.model_validate(raw))
            except ValueError:
                continue
        curve_doc = self.client.get_document(interest_curve_path(owner_uid, project_id, run_id))
        if curve_doc and not is_owner(curve_doc, owner_uid):
            raise NotFoundError("Comparison interest curve not found")
        interest = (
            InterestCurve.model_validate(curve_doc)
            if curve_doc and is_owner(curve_doc, owner_uid) and curve_doc.get("status") == "ready"
            else None
        )
        return RunInput(
            run_id,
            document,
            asset,
            transcript,
            segments,
            sorted(findings, key=lambda f: (f.startMs, f.findingId)),
            accepted_ids,
            coverage,
            interest,
        )

    def compare(
        self, *, owner_uid: str, project_id: str, base_run_id: str, target_run_id: str
    ) -> AnalysisComparison:
        self._owned(project_path(owner_uid, project_id), owner_uid, project_id)
        if base_run_id == target_run_id:
            raise BadRequestError("Choose two different analysis runs")
        return build_comparison(
            self._load(owner_uid, project_id, base_run_id),
            self._load(owner_uid, project_id, target_run_id),
        )
