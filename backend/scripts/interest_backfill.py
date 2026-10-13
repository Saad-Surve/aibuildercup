"""Add the interest curve and reviewer coverage to analysis runs created before they existed.

Re-uses the run's pinned transcript and its stored findings; the reviewers are not run
again. Each curve costs at most a few bounded Gemini calls (the signal pass), and
`--max-runs` caps the total. Runs that already have a curve are skipped unless `--force`.

Coverage for an old run is reconstructed conservatively: a dimension counts as reviewed
over the whole video only when its reviewer finished with no chunk failures.

    uv run python scripts/interest_backfill.py --uid <uid> [--project <id>] [--max-runs 10]
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.reviewer_base import SegmentRef
from app.config import get_settings
from app.errors import NotFoundError
from app.providers import get_providers
from app.schemas.analysis import AnalysisDimension, HeatmapCoverage
from app.services.analysis_service import AnalysisService
from app.services.firestore_service import (
    analysis_run_path,
    get_firestore_client,
    interest_curve_path,
    project_path,
)
from app.services.job_service import JobService
from app.services.storage_service import get_storage_client
from app.services.transcript_service import TranscriptService
from app.workers.analysis_worker import _link_findings, _predict_interest


def coverage_for(
    analyses: AnalysisService, *, uid: str, project_id: str, run_id: str, duration_ms: int
) -> list[HeatmapCoverage]:
    spans: list[HeatmapCoverage] = []
    for reviewer in analyses.get_reviewers(
        owner_uid=uid, project_id=project_id, analysis_run_id=run_id
    ):
        if reviewer.status.value != "succeeded" or reviewer.error:
            continue
        spans.append(
            HeatmapCoverage(dimension=reviewer.dimension, startMs=0, endMs=duration_ms)
        )
    order = {dimension: i for i, dimension in enumerate(AnalysisDimension)}
    return sorted(spans, key=lambda span: order[span.dimension])


async def backfill(args: argparse.Namespace) -> None:
    settings = get_settings()
    client = get_firestore_client()
    storage = get_storage_client()
    jobs = JobService(client)
    analyses = AnalysisService(client, jobs=jobs, settings=settings)
    transcripts = TranscriptService(client, storage=storage)
    llm = get_providers().llm

    if args.project:
        project_ids = [args.project]
    else:
        rows = client.query_collection(
            f"users/{args.uid}/projects", filters=[], order_by=[], limit=500, offset=0
        )
        project_ids = [project_id for project_id, data in rows if data.get("ownerUid") == args.uid]

    done = 0
    for project_id in project_ids:
        project: dict[str, Any] = client.get_document(project_path(args.uid, project_id)) or {}
        if project.get("archivedAt") is not None:
            continue
        try:
            runs = analyses.list_runs(owner_uid=args.uid, project_id=project_id)
        except NotFoundError:
            continue
        for run in runs:
            if args.run and run.analysisRunId != args.run:
                continue
            if run.status.value not in ("ready", "partial_failure"):
                continue
            if done >= args.max_runs:
                print(f"reached --max-runs {args.max_runs}; stopping")
                return
            has_curve = client.get_document(
                interest_curve_path(args.uid, project_id, run.analysisRunId)
            )
            if has_curve and not args.force:
                continue
            try:
                transcript = transcripts.get_by_id(
                    owner_uid=args.uid, project_id=project_id, transcript_id=run.transcriptId
                )
            except NotFoundError:
                print(f"{project_id}/{run.analysisRunId}: transcript gone; skipped")
                continue
            segments = [
                SegmentRef(
                    segment_id=s.segmentId, start_ms=s.startMs, end_ms=s.endMs, text=s.text
                )
                for s in transcript.segments
            ]
            prediction = await _predict_interest(
                llm,
                settings,
                segments=segments,
                duration_ms=transcript.durationMs,
                title=str(project.get("name") or ""),
                language=transcript.language,
            )
            if prediction is None:
                print("no bundled interest model; train it first")
                return
            curve, usage = prediction
            findings = analyses.list_findings(
                owner_uid=args.uid, project_id=project_id, analysis_run_id=run.analysisRunId
            )
            curve = _link_findings(curve, findings, analysis_run_id=run.analysisRunId)
            coverage = coverage_for(
                analyses,
                uid=args.uid,
                project_id=project_id,
                run_id=run.analysisRunId,
                duration_ms=transcript.durationMs,
            )
            label = f"{project.get('name')!r} {run.analysisRunId}"
            print(
                f"{label}: {len(curve.points)} bins, {curve.featureSource}, "
                f"{len(coverage)} covered dimensions, "
                f"{usage.input_tokens}+{usage.output_tokens} tokens"
            )
            done += 1
            if args.dry_run:
                continue
            analyses.save_interest(
                owner_uid=args.uid,
                project_id=project_id,
                analysis_run_id=run.analysisRunId,
                curve=curve,
            )
            if coverage and not run_has_coverage(analyses, args.uid, project_id, run.analysisRunId):
                client.update_document(
                    analysis_run_path(args.uid, project_id, run.analysisRunId),
                    {"coverage": [span.model_dump(mode="json") for span in coverage]},
                )
    print(f"backfilled {done} run(s){' (dry run)' if args.dry_run else ''}")


def run_has_coverage(analyses: AnalysisService, uid: str, project_id: str, run_id: str) -> bool:
    return bool(
        analyses.get_coverage(owner_uid=uid, project_id=project_id, analysis_run_id=run_id)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uid", required=True)
    parser.add_argument("--project")
    parser.add_argument("--run")
    parser.add_argument("--max-runs", type=int, default=10)
    parser.add_argument("--force", action="store_true", help="Recompute existing curves.")
    parser.add_argument("--dry-run", action="store_true")
    asyncio.run(backfill(parser.parse_args()))


if __name__ == "__main__":
    main()
