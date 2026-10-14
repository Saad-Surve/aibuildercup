"""Gold-issue editorial evaluation: one Gemini prompt versus the nine Resonance reviewers.

Answers "why not just ask Gemini?" with numbers. Every arm reviews the same constructed
videos (`evals/editorial/media`) with the same model, title, audience, brief and transcript,
and is scored against gold labels that were committed before any model ran
(`evals/editorial/labels`, rule in `evals/editorial/matching.json`; see
`evals/editorial/README.md`).

Arms:
  baseline    one prompt over the whole video plus transcript, same output shape
  rubric      the same single call, with all nine reviewer rubrics pasted into the prompt
  reviewers   the production reviewer code path: chunking, shared frames, footage tools,
              nine reviewers, per-window normalisation (`app/agents/analysis_coordinator.py`)
  adjudicated reviewers, then the production footage adjudicator
  edited      reviewers, then bounded cross-reviewer editorial consolidation
  edited_adjudicated reviewers, editor, then adjudicator (or joined saved verdicts on reuse)

Commands (from `backend/`):

    # Dry run (default): prints the plan and the call bounds, makes no model call.
    uv run python scripts/editorial_eval.py run --arms baseline,reviewers --max-calls 200
    # Live run. --max-calls is a hard stop on `generate_content` calls.
    uv run python scripts/editorial_eval.py run --arms baseline,reviewers --max-calls 200 --execute
    # Re-score saved raw outputs with zero model calls.
    uv run python scripts/editorial_eval.py replay ../evals/results/editorial-<run>.raw.json
    # Markdown tables from a scored file.
    uv run python scripts/editorial_eval.py report ../evals/results/editorial-<run>.json

Costs and call counts count logical `generate_content` calls, tool-loop rounds included. A
transient-error retry inside the provider is not counted separately for baseline/reviewer
arms; editor/adjudicator calls disable both provider and SDK retries.
"""

import argparse
import asyncio
import copy
import hashlib
import json
import subprocess
import sys
import time
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import editorial_score as scoring

from app.agents.adjudicator import ADJUDICATOR_PROMPT_VERSION, adjudicator_reservation
from app.agents.analysis_coordinator import (
    REVIEWER_CLASSES,
    build_review_contexts,
    build_reviewers,
    chunk_segments,
    run_reviewers,
)
from app.agents.editor import EDITOR_PROMPT_VERSION, edit_findings, editor_reservation
from app.agents.reviewer_base import (
    GROUNDING_PROMPT,
    MODEL_CONFIG_VERSION,
    REVIEWER_PROMPT_VERSION,
    SCORE_ANCHORS,
    SegmentRef,
    dimension_label,
    findings_schema,
    normalize_findings,
)
from app.config import Settings
from app.providers.base import MediaPart
from app.providers.llm import LlmProvider, _grounding_from, _usage_from
from app.schemas.analysis import ACTIVE_DIMENSIONS, AdjudicatorSummary, AnalysisDimension, Finding
from app.services.heatmap import effective_findings
from app.services.video_tools import MediaToolkit, ffmpeg_available
from app.workers.analysis_worker import _add_sampled_frames

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
EDITORIAL = ROOT / "evals" / "editorial"
RESULTS = ROOT / "evals" / "results"
PRE_REGISTERED_PATHS = ("labels", "transcripts", "media", "matching.json", "scripts")

BASELINE_PROMPT_VERSION = "editorial-baseline-v1"
SCHEMA_VERSION = 1
ARMS = ("baseline", "rubric", "reviewers", "adjudicated", "edited", "edited_adjudicated")
DEFAULT_ARMS = "baseline,reviewers"
DEFAULT_ADJUDICATOR = "app.agents.adjudicator:adjudicate"

#: One line per dimension for the plain baseline: what a reasonable user would write.
DIMENSION_BLURBS: dict[AnalysisDimension, str] = {
    AnalysisDimension.truth_evidence: "factual errors and unsupported claims",
    AnalysisDimension.clarity: "unclear explanations, unexplained jargon, hard-to-follow phrasing",
    AnalysisDimension.pacing_retention: "weak hooks, slow or repetitive stretches, tangents, "
    "promises that are not kept",
    AnalysisDimension.legal_safety: "legal, medical, financial or safety risks",
    AnalysisDimension.cultural_localization: "assumptions about location or culture that a "
    "worldwide audience would not share",
    AnalysisDimension.platform_fit: "how well the video fits the platform it is published on",
    AnalysisDimension.audience_brand: "fit with the intended audience and the stated tone",
    AnalysisDimension.emotional_impact: "emotional flatness or tone that does not fit the moment",
    AnalysisDimension.conversion_cta: "calls to action and next steps that serve the creator's "
    "goal",
}

BASELINE_RULES = """\
OUTPUT RULES:
1. Review the whole video. Report only real problems or exceptional strengths (score 5, severity
   none); do not narrate ordinary stretches and never invent issues to fill a quota.
2. For a spoken issue, quote the exact words (at most 25 words); for an omission, the quote may
   be empty. startMs and endMs are milliseconds from the start of the video; mark the actual span,
   or where an omission belongs. segmentId is the nearest transcript segment.
3. Set `dimension` to the area the issue belongs to. score is the 1-5 scale above; severity is
   judged separately.
4. critique_and_reasoning is 1-2 short sentences. suggestion is one concrete edit: what to trim or
   move, replacement wording, or exactly what to add here. Do not invent facts, names, numbers or
   sources. Return JSON only, matching the schema."""


class BudgetExceeded(RuntimeError):
    pass


class MeteredLlm(LlmProvider):
    """The production provider, counting every `generate_content` call against a hard cap."""

    def __init__(self, settings: Settings, *, max_calls: int) -> None:
        super().__init__(settings)
        self.max_calls = max_calls
        self.calls: list[dict[str, Any]] = []
        self.tag = ""

    async def _generate(self, **kwargs: Any) -> Any:
        if len(self.calls) >= self.max_calls:
            raise BudgetExceeded(f"--max-calls {self.max_calls} reached")
        record: dict[str, Any] = {
            "tag": self.tag,
            "model": kwargs.get("model"),
            "grounding": bool(kwargs.get("grounding")),
            "tools": bool(kwargs.get("function_declarations")),
            "thinkingLevel": kwargs.get("thinking_level"),
        }
        self.calls.append(record)
        started = time.monotonic()
        try:
            result = await super()._generate(**kwargs)
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"[:300]
            record["elapsedMs"] = int((time.monotonic() - started) * 1000)
            raise
        usage = _usage_from(result)
        record.update(
            inputTokens=usage.input_tokens,
            outputTokens=usage.output_tokens,
            searchQueries=len(_grounding_from(result).queries),
            elapsedMs=int((time.monotonic() - started) * 1000),
            text=(result.text or "")[:60_000],
        )
        return result

    def calls_for(self, tag: str) -> list[dict[str, Any]]:
        return [call for call in self.calls if call["tag"] == tag]


# ------------------------------------------------------------------ inputs


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_labels(video_ids: Sequence[str] | None = None) -> dict[str, dict[str, Any]]:
    labels = {path.stem: read_json(path) for path in sorted((EDITORIAL / "labels").glob("*.json"))}
    if video_ids:
        missing = [video_id for video_id in video_ids if video_id not in labels]
        if missing:
            raise SystemExit(f"unknown video ids: {', '.join(missing)}")
        labels = {video_id: labels[video_id] for video_id in video_ids}
    if not labels:
        raise SystemExit("no labels found under --root/labels")
    return labels


def load_segments(video_id: str) -> list[SegmentRef]:
    transcript = read_json(EDITORIAL / "transcripts" / f"{video_id}.json")
    return [
        SegmentRef(
            segment_id=segment["segmentId"],
            start_ms=segment["startMs"],
            end_ms=segment["endMs"],
            text=segment["text"],
        )
        for segment in transcript["segments"]
    ]


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=False
    )
    return completed.stdout.strip()


def preregistration() -> dict[str, Any]:
    """Which commit last touched the pre-registered inputs, and whether they are dirty now."""
    try:
        relative = EDITORIAL.relative_to(ROOT)
    except ValueError as exc:
        raise SystemExit("--root must be inside this git worktree for pre-registration") from exc
    paths = [str(relative / name) for name in PRE_REGISTERED_PATHS]
    inputs = [
        path
        for name in PRE_REGISTERED_PATHS
        for path in (
            [EDITORIAL / name]
            if (EDITORIAL / name).is_file()
            else sorted((EDITORIAL / name).rglob("*"))
        )
        if path.is_file()
    ]
    tracked = set(git("ls-files", "--", *paths).splitlines())
    untracked = [
        str(path.relative_to(ROOT)) for path in inputs if str(path.relative_to(ROOT)) not in tracked
    ]
    return {
        "commit": git("log", "-1", "--format=%H", "--", *paths),
        "commitDate": git("log", "-1", "--format=%cI", "--", *paths),
        "dirty": bool(untracked or git("status", "--porcelain", "--", *paths)),
        "root": str(relative),
        "inputSha256": {str(path.relative_to(EDITORIAL)): sha256_file(path) for path in inputs},
        "labelSha256": {
            path.stem: sha256_file(path) for path in sorted((EDITORIAL / "labels").glob("*.json"))
        },
        "matchingSha256": sha256_file(EDITORIAL / "matching.json"),
    }


def code_fingerprint() -> dict[str, Any]:
    files = [
        BACKEND / "scripts" / "editorial_eval.py",
        BACKEND / "scripts" / "editorial_score.py",
        BACKEND / "app" / "agents" / "reviewer_base.py",
        BACKEND / "app" / "agents" / "analysis_coordinator.py",
        BACKEND / "app" / "agents" / "adjudicator.py",
        BACKEND / "app" / "agents" / "editor.py",
        BACKEND / "app" / "providers" / "base.py",
        BACKEND / "app" / "providers" / "llm.py",
        BACKEND / "app" / "config.py",
    ]
    return {
        "revision": git("rev-parse", "HEAD"),
        "dirty": bool(git("status", "--porcelain", "--", "backend", "evals")),
        "sha256": {str(path.relative_to(ROOT)): sha256_file(path) for path in files},
    }


# ------------------------------------------------------------------ baseline arms


def all_finding_types() -> list[str]:
    seen: dict[str, None] = {}
    for dimension in ACTIVE_DIMENSIONS:
        for finding_type in REVIEWER_CLASSES[dimension].finding_types:
            seen.setdefault(finding_type)
    return list(seen)


def baseline_schema(*, grounded: bool) -> dict[str, Any]:
    """The reviewers' finding shape plus the `dimension` a single prompt must choose itself."""
    schema = findings_schema(all_finding_types(), grounded=grounded)
    item = schema["properties"]["findings"]["items"]
    item["properties"]["dimension"] = {
        "type": "string",
        "enum": [dimension.value for dimension in ACTIVE_DIMENSIONS],
    }
    item["required"].append("dimension")
    return schema


def baseline_system(*, rubric: bool, grounded: bool) -> str:
    if rubric:
        areas = "\n\n".join(
            f"## {dimension_label(d)} (dimension: {d.value})\n{REVIEWER_CLASSES[d].focus.strip()}"
            for d in ACTIVE_DIMENSIONS
        )
        intro = "Review the video against all nine areas below, each with its own rubric."
    else:
        areas = "\n".join(
            f"- {dimension_label(d)} (dimension: {d.value}): {DIMENSION_BLURBS[d]}"
            for d in ACTIVE_DIMENSIONS
        )
        intro = "Review the video in these areas."
    sections = [
        "You are an expert video editor and script consultant reviewing a creator's video "
        "before it is published. The video is attached and its transcript is below. "
        f"{intro} Help the creator edit: explain the viewer friction, then give one change they "
        "can make at the marked moment, preserving their voice and intent.",
        areas,
        SCORE_ANCHORS,
        BASELINE_RULES,
    ]
    if grounded:
        sections.append(GROUNDING_PROMPT)
    return "\n\n".join(sections)


def baseline_user(label: dict[str, Any], segments: Sequence[SegmentRef]) -> str:
    header = [
        "# Review task: whole video",
        f"Video title: {label['title']}",
        f"Target platform: {label['platform']}",
        f"Spoken language: {label['language']}",
        f"Video duration: {label['durationMs']} ms",
        f"Review date: {datetime.now(UTC).date().isoformat()}. Filming date is not provided.",
        f"Creator's brief: {label['brief']}",
        f"Intended audience: {label['audience']}",
    ]
    lines = [f"[{s.segment_id}] {s.start_ms} -> {s.end_ms}: {s.text}" for s in segments]
    return "\n".join(header) + "\n\n# TRANSCRIPT\n" + "\n".join(lines)


def normalize_baseline(
    raw: dict[str, Any], segments: Sequence[SegmentRef], duration_ms: int
) -> list[dict[str, Any]]:
    """Normalise with the reviewers' own validator, grouped by the dimension the model chose."""
    entries = raw.get("findings") if isinstance(raw, dict) else None
    groups: dict[AnalysisDimension, list[Any]] = defaultdict(list)
    for entry in entries or []:
        try:
            groups[AnalysisDimension(str(entry.get("dimension")))].append(entry)
        except (ValueError, AttributeError):
            continue
    findings = []
    for dimension, group in groups.items():
        findings.extend(
            normalize_findings(
                {"findings": group},
                dimension=dimension,
                reviewer_run_id="baseline",
                segments=segments,
                duration_ms=duration_ms,
            )
        )
    findings.sort(key=lambda finding: finding.startMs)
    return [finding.model_dump(mode="json") for finding in findings]


async def run_baseline_arm(
    llm: MeteredLlm,
    *,
    model: str,
    label: dict[str, Any],
    segments: Sequence[SegmentRef],
    media_path: Path,
    rubric: bool,
    grounded: bool,
) -> dict[str, Any]:
    completion = await llm.complete_json(
        model=model,
        prompt_version=BASELINE_PROMPT_VERSION,
        system=baseline_system(rubric=rubric, grounded=grounded),
        user=baseline_user(label, segments),
        schema=baseline_schema(grounded=grounded),
        media=(
            MediaPart(mime_type="video/mp4", data=media_path.read_bytes(), label="Full video:"),
        ),
        grounding=grounded,
    )
    return {
        "rawJson": completion.data,
        "findings": normalize_baseline(completion.data, segments, int(label["durationMs"])),
    }


# ------------------------------------------------------------------ reviewer arms


async def run_reviewer_arm(
    llm: MeteredLlm,
    settings: Settings,
    *,
    model: str,
    label: dict[str, Any],
    segments: Sequence[SegmentRef],
    media_path: Path,
    visual_tools: bool,
    grounded: bool,
) -> dict[str, Any]:
    """The production fan-out for one video, minus persistence (see `run_analysis`)."""
    duration_ms = int(label["durationMs"])
    chunks = chunk_segments(segments)
    contexts = build_review_contexts(
        chunks,
        persona="",
        platform=label["platform"],
        audience=label["audience"],
        language=label["language"],
        duration_ms=duration_ms,
        video_title=label["title"],
        project_brief=label["brief"],
    )
    toolkit: MediaToolkit | None = None
    if visual_tools and settings.review_visual_tools_enabled:
        if not ffmpeg_available(settings.ffmpeg_path):
            raise SystemExit(f"ffmpeg not found at {settings.ffmpeg_path}; pass --no-visual-tools")
        toolkit = MediaToolkit(
            source=str(media_path),
            duration_ms=duration_ms,
            ffmpeg_path=settings.ffmpeg_path,
            window_seconds=settings.visual_clip_window_seconds,
            max_requests=settings.max_visual_context_requests,
            max_rounds=settings.visual_tool_max_rounds,
        )
        contexts = await _add_sampled_frames(contexts, toolkit, None)
    reviewers = build_reviewers(
        llm,
        model=model,
        dimensions=list(ACTIVE_DIMENSIONS),
        visual_tools=toolkit,
        context_store=None,
        grounding_enabled=grounded,
    )
    outcomes = await run_reviewers(
        reviewers,
        contexts,
        max_concurrency=settings.max_reviewer_concurrency,
        reviewer_run_ids={d: f"eval-{d.value}" for d in ACTIVE_DIMENSIONS},
    )
    findings = sorted(
        (finding for outcome in outcomes for finding in outcome.findings),
        key=lambda finding: finding.startMs,
    )
    return {
        "findings": [finding.model_dump(mode="json") for finding in findings],
        "chunks": len(chunks),
        "reviewerStatus": {o.dimension.value: o.status.value for o in outcomes},
        "reviewerErrors": {o.dimension.value: o.error for o in outcomes if o.error},
        "footageToolCalls": sum(len(o.tool_calls) for o in outcomes),
    }


def load_adjudicator(entrypoint: str) -> Any:
    """Resolve `module:function` with the production adjudicator's interface."""
    module_name, _, function_name = entrypoint.partition(":")
    try:
        return getattr(import_module(module_name), function_name)
    except (ImportError, AttributeError) as exc:
        raise SystemExit(
            f"adjudicator '{entrypoint}' is not importable ({exc}); pass --adjudicator "
            "module:function or drop the 'adjudicated' arm."
        ) from exc


class LocalEvidenceStore:
    """Keep the footage the model checked alongside the evaluation's raw output."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def save(self, part: MediaPart, *, reviewer_run_id: str, tool: str, index: int) -> str:
        directory = self.root / hashlib.sha256(reviewer_run_id.encode()).hexdigest()[:16]
        directory.mkdir(parents=True, exist_ok=True)
        extension = "mp4" if part.mime_type == "video/mp4" else "jpg"
        path = directory / f"{index:02d}-{tool}.{extension}"
        path.write_bytes(part.data)
        return str(path)


async def run_adjudicated_arm(
    llm: MeteredLlm,
    adjudicate: Any,
    *,
    settings: Settings,
    model: str,
    label: dict[str, Any],
    segments: Sequence[SegmentRef],
    reviewer_findings: list[dict[str, Any]],
    media_path: Path,
    evidence_dir: Path,
) -> dict[str, Any]:
    findings = [Finding.model_validate(item) for item in reviewer_findings]
    # --model applies to every arm; this arm always checks actual footage, independently
    # of whether reviewer-requested visual tools were enabled in the first pass.
    settings = settings.model_copy(update={"model_adjudicator": model})
    toolkit = (
        MediaToolkit(
            source=str(media_path),
            duration_ms=int(label["durationMs"]),
            ffmpeg_path=settings.ffmpeg_path,
            window_seconds=5,
        )
        if ffmpeg_available(settings.ffmpeg_path)
        else None
    )
    summary = await adjudicate(
        findings,
        llm=llm,
        settings=settings,
        segments=list(segments),
        toolkit=toolkit,
        store=LocalEvidenceStore(evidence_dir),
        budget_usd=min(settings.max_project_cost_usd, adjudicator_reservation(settings)),
        abort_on=(BudgetExceeded,),
        creator_context=(
            f"Title: {label['title']}\nBrief: {label['brief']}\nAudience: {label['audience']}\n"
            f"Platform: {label['platform']}\nLanguage: {label['language']}"
        ),
    )
    if not isinstance(summary, AdjudicatorSummary):
        raise TypeError("Adjudicator must return AdjudicatorSummary")
    return {
        "findings": [finding.model_dump(mode="json") for finding in effective_findings(findings)],
        "allFindings": [finding.model_dump(mode="json") for finding in findings],
        "adjudicator": summary.model_dump(mode="json"),
    }


# ------------------------------------------------------------------ run


def summarize_calls(calls: Sequence[dict[str, Any]]) -> dict[str, Any]:
    return {
        "usage": {
            "inputTokens": sum(c.get("inputTokens", 0) for c in calls),
            "outputTokens": sum(c.get("outputTokens", 0) for c in calls),
        },
        "modelRequests": len(calls),
        "searchQueries": sum(c.get("searchQueries", 0) for c in calls),
        "errors": [c["error"] for c in calls if c.get("error")],
        "elapsedMs": sum(c.get("elapsedMs", 0) for c in calls),
    }


def plan_calls(arms: Sequence[str], labels: dict[str, dict[str, Any]], settings: Settings) -> dict:
    """Bounds on `generate_content` calls: reviewers add tool-loop rounds up to the cap."""
    per_arm: dict[str, tuple[int, int]] = {}
    extra_rounds = settings.visual_tool_max_rounds if settings.review_visual_tools_enabled else 0
    for arm in arms:
        if arm in ("baseline", "rubric"):
            per_arm[arm] = (len(labels), len(labels))
        elif arm == "reviewers":
            chunk_total = sum(len(chunk_segments(load_segments(v))) for v in labels)
            per_arm[arm] = (
                len(ACTIVE_DIMENSIONS) * chunk_total,
                len(ACTIVE_DIMENSIONS) * chunk_total * (1 + extra_rounds),
            )
        elif arm in ("adjudicated", "edited_adjudicated"):
            per_arm[arm] = (0, len(labels) * settings.max_adjudicator_calls)
        elif arm == "edited":
            per_arm[arm] = (
                0,
                sum(
                    min(
                        settings.max_editor_calls,
                        max(1, (int(v["durationMs"]) + 599_999) // 600_000),
                    )
                    for v in labels.values()
                ),
            )
    return {
        "perArm": {arm: {"min": low, "max": high} for arm, (low, high) in per_arm.items()},
        "min": sum(low for low, _ in per_arm.values()),
        "max": sum(high for _, high in per_arm.values()),
    }


def combined_summary(*entries: dict[str, Any]) -> dict[str, Any]:
    return {
        "usage": {
            key: sum(e.get("usage", {}).get(key, 0) for e in entries)
            for key in ("inputTokens", "outputTokens")
        },
        **{
            key: sum(e.get(key, 0) for e in entries)
            for key in ("modelRequests", "searchQueries", "elapsedMs")
        },
        "errors": [error for e in entries for error in e.get("errors", [])],
    }


def validate_reuse(
    raw: dict[str, Any],
    registration: dict[str, Any],
    model: str,
    labels: dict[str, dict[str, Any]],
    arms: list[str],
) -> None:
    if raw["labels"].get("inputSha256") and (
        raw["labels"]["inputSha256"] != registration["inputSha256"]
    ):
        raise SystemExit("reuse pre-registered inputs differ from the saved run")
    if raw["model"] != model:
        raise SystemExit("reuse requires the same model as the saved reviewer run")
    if raw["labels"]["matchingSha256"] != registration["matchingSha256"] or any(
        raw["labels"]["labelSha256"].get(v) != registration["labelSha256"][v] for v in labels
    ):
        raise SystemExit("reuse labels/matching rule differ from the saved run")
    if not set(arms) <= {"edited", "edited_adjudicated"}:
        raise SystemExit("--reuse-raw makes only editor calls: choose edited,edited_adjudicated")
    for video_id in labels:
        if video_id not in raw.get("arms", {}).get("reviewers", {}).get("videos", {}):
            raise SystemExit(f"reuse lacks reviewers for {video_id}")
        if "edited_adjudicated" in arms and video_id not in raw.get("arms", {}).get(
            "adjudicated", {}
        ).get("videos", {}):
            raise SystemExit(f"reuse lacks adjudicated findings for {video_id}")


async def run_arms(args: argparse.Namespace, settings: Settings, model: str) -> Path:
    labels = load_labels(args.videos.split(",") if args.videos else None)
    arms = args.arms.split(",")
    prices = {"inputPerMTok": args.input_price, "outputPerMTok": args.output_price}
    registration = preregistration()
    reused = read_json(args.reuse_raw) if args.reuse_raw else None
    if reused:
        validate_reuse(reused, registration, model, labels, arms)
        if reused["prices"] != prices:
            raise SystemExit("reuse requires identical prices for honest cumulative cost")
    settings = settings.model_copy(
        update={
            "model_editor": model,
            "editor_input_price_per_mtok": args.input_price,
            "editor_output_price_per_mtok": args.output_price,
            "adjudicator_input_price_per_mtok": args.input_price,
            "adjudicator_output_price_per_mtok": args.output_price,
            "truth_grounding_enabled": args.grounding,
        }
    )
    run_id = args.run_id or datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / f"editorial-{run_id}.raw.json"
    if raw_path.exists():
        raise SystemExit(f"refusing to overwrite {raw_path}; choose a new run ID")
    llm = MeteredLlm(settings, max_calls=args.max_calls)
    adjudicate = (
        load_adjudicator(args.adjudicator)
        if any(a in arms for a in ("adjudicated", "edited_adjudicated")) and not reused
        else None
    )
    raw: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "editorial-eval-raw",
        "runId": run_id,
        "startedAt": datetime.now(UTC).isoformat(),
        "model": model,
        "prices": prices,
        "options": {
            "arms": arms,
            "root": str(EDITORIAL.relative_to(ROOT)),
            "grounding": args.grounding,
            "visualTools": args.visual_tools,
            "maxCalls": args.max_calls,
            "reviewerConcurrency": settings.max_reviewer_concurrency,
            "maxVisualContextRequests": settings.max_visual_context_requests,
            "visualToolMaxRounds": settings.visual_tool_max_rounds,
            "maxAdjudicatorCalls": settings.max_adjudicator_calls,
            "maxConflictCalls": settings.max_conflict_calls,
            "maxEditorCalls": settings.max_editor_calls,
            "editorThinkingLevel": settings.editor_thinking_level,
        },
        "promptVersions": {
            "reviewers": REVIEWER_PROMPT_VERSION,
            "modelConfig": MODEL_CONFIG_VERSION,
            "baseline": BASELINE_PROMPT_VERSION,
            "adjudicator": ADJUDICATOR_PROMPT_VERSION,
            "editor": EDITOR_PROMPT_VERSION,
        },
        "labels": registration,
        "code": code_fingerprint(),
        "arms": {arm: {"videos": {}} for arm in arms},
    }
    if reused:
        raw["reuse"] = {
            "path": str(args.reuse_raw),
            "sha256": sha256_file(args.reuse_raw),
            "runId": reused["runId"],
            "onlyNewStage": "editor",
            "adjudication": "Saved verdicts joined by original ID; absent means not checked",
            "sourceCode": reused["code"],
            "sourcePromptVersions": reused["promptVersions"],
        }
        for arm, data in reused["arms"].items():
            if arm in ("baseline", "rubric", "reviewers", "adjudicated"):
                raw["arms"][arm] = {
                    "videos": {
                        v: copy.deepcopy(e) for v, e in data["videos"].items() if v in labels
                    },
                    "reused": True,
                }
        raw["arms"] = {a: raw["arms"][a] for a in ARMS if a in raw["arms"]}

    def save() -> None:
        raw["totalModelRequests"] = len(llm.calls)
        raw_path.write_text(scoring.dump(raw))

    try:
        for video_id, label in labels.items():
            segments = load_segments(video_id)
            media_path = EDITORIAL / label["source"]["media"]
            reviewer_entry = copy.deepcopy(
                raw["arms"].get("reviewers", {}).get("videos", {}).get(video_id, {})
            )
            edited_entry: dict[str, Any] = {}
            for arm in arms:
                tag = f"{arm}:{video_id}"
                llm.tag = tag
                print(f"{tag} ...", flush=True)
                entry: dict[str, Any]
                base_summary: dict[str, Any] = {}
                try:
                    if arm in ("baseline", "rubric"):
                        entry = await run_baseline_arm(
                            llm,
                            model=model,
                            label=label,
                            segments=segments,
                            media_path=media_path,
                            rubric=arm == "rubric",
                            grounded=args.grounding,
                        )
                    elif arm == "reviewers":
                        entry = await run_reviewer_arm(
                            llm,
                            settings,
                            model=model,
                            label=label,
                            segments=segments,
                            media_path=media_path,
                            visual_tools=args.visual_tools,
                            grounded=args.grounding,
                        )
                    elif arm == "edited":
                        findings = [Finding.model_validate(f) for f in reviewer_entry["findings"]]
                        summary = await edit_findings(
                            findings,
                            segments=segments,
                            duration_ms=int(label["durationMs"]),
                            llm=llm,
                            settings=settings,
                            budget_usd=editor_reservation(settings),
                            creator_context=(
                                f"Title: {label['title']}\nPlatform: {label['platform']}\n"
                                f"Audience: {label['audience']}\nBrief: {label['brief']}"
                            ),
                            abort_on=(BudgetExceeded,),
                        )
                        entry = {
                            "findings": [
                                f.model_dump(mode="json") for f in effective_findings(findings)
                            ],
                            "allFindings": [f.model_dump(mode="json") for f in findings],
                            "editor": summary.model_dump(mode="json"),
                        }
                        base_summary = reviewer_entry
                    elif arm == "edited_adjudicated" and reused:
                        findings = [Finding.model_validate(f) for f in edited_entry["allFindings"]]
                        saved = raw["arms"]["adjudicated"]["videos"][video_id]
                        verdicts = {
                            f["findingId"]: f.get("adjudication") for f in saved["allFindings"]
                        }
                        surviving = {f.findingId for f in effective_findings(findings)}
                        checked = 0
                        for f in findings:
                            if f.findingId in surviving and verdicts.get(f.findingId):
                                f.adjudication = Finding.model_validate(
                                    {**f.model_dump(), "adjudication": verdicts[f.findingId]}
                                ).adjudication
                                checked += 1
                        entry = {
                            "findings": [
                                f.model_dump(mode="json") for f in effective_findings(findings)
                            ],
                            "allFindings": [f.model_dump(mode="json") for f in findings],
                            "editor": edited_entry["editor"],
                            "savedAdjudicationJoined": True,
                            "checkedSurvivingCount": checked,
                            "notCheckedSurvivingCount": len(surviving) - checked,
                        }
                        # Retain the historic full adjudicator cost.
                        base_summary = combined_summary(saved, edited_entry["editorMarginal"])
                    else:
                        source = edited_entry if arm == "edited_adjudicated" else reviewer_entry
                        entry = await run_adjudicated_arm(
                            llm,
                            adjudicate,
                            settings=settings,
                            model=model,
                            label=label,
                            segments=segments,
                            reviewer_findings=source.get("allFindings", source["findings"]),
                            media_path=media_path,
                            evidence_dir=out_dir / f"editorial-{run_id}.evidence" / video_id,
                        )
                        base_summary = source
                        if arm == "edited_adjudicated":
                            entry["editor"] = edited_entry["editor"]
                except BudgetExceeded:
                    raw["abortedAt"] = tag
                    raise
                except Exception as exc:  # noqa: BLE001 - keep original findings on optional failure
                    entry = {
                        "findings": copy.deepcopy(reviewer_entry.get("findings", [])),
                        "fatal": f"{type(exc).__name__}: {exc}"[:300],
                    }
                calls = llm.calls_for(tag)
                marginal = summarize_calls(calls)
                if "fatal" in entry:
                    marginal["errors"].append(entry["fatal"])
                elif arm == "edited":
                    marginal["errors"].extend(entry["editor"]["errors"])
                entry.update(combined_summary(base_summary, marginal))
                entry["calls"] = calls
                if arm == "edited":
                    entry["editorMarginal"] = marginal
                    edited_entry = entry
                if arm == "reviewers":
                    reviewer_entry = entry
                raw["arms"][arm]["videos"][video_id] = entry
                save()
    except BudgetExceeded as exc:
        save()
        raise SystemExit(f"stopped: {exc}. Partial raw output saved to {raw_path}") from exc
    raw["finishedAt"] = datetime.now(UTC).isoformat()
    raw["newCallCostUsd"] = scoring.usd(
        sum(c.get("inputTokens", 0) for c in llm.calls),
        sum(c.get("outputTokens", 0) for c in llm.calls),
        prices,
    )
    save()
    return raw_path


# ------------------------------------------------------------------ scoring, replay, report


def findings_for_scoring(
    raw: dict[str, Any], labels: dict[str, dict[str, Any]]
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Stored findings, except single-prompt arms are re-normalised from the raw model JSON so
    a normaliser fix is picked up by replay without touching a model."""
    out: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for arm, runs in raw["arms"].items():
        out[arm] = {}
        for video_id, run in runs["videos"].items():
            if arm in ("baseline", "rubric") and "rawJson" in run:
                out[arm][video_id] = normalize_baseline(
                    run["rawJson"], load_segments(video_id), int(labels[video_id]["durationMs"])
                )
            else:
                out[arm][video_id] = run["findings"]
    return out


def score_raw(raw: dict[str, Any], *, replay_of: Path | None) -> dict[str, Any]:
    video_ids = sorted({v for runs in raw["arms"].values() for v in runs["videos"]})
    labels = load_labels(video_ids)
    rule = read_json(EDITORIAL / "matching.json")
    current = preregistration()
    if raw["labels"].get("inputSha256") and raw["labels"]["inputSha256"] != current["inputSha256"]:
        raise SystemExit("pre-registered inputs changed since run; refusing to score")
    scored = scoring.score_run(raw, labels, rule, findings_for_scoring(raw, labels))
    if (
        any(current["labelSha256"].get(v) != raw["labels"]["labelSha256"].get(v) for v in labels)
        or current["matchingSha256"] != raw["labels"]["matchingSha256"]
    ):
        raise SystemExit("labels or matching rule changed since run; refusing to score")
    result: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "editorial-eval",
        "runId": raw["runId"],
        "model": raw["model"],
        "prices": raw["prices"],
        "options": raw["options"],
        "promptVersions": raw["promptVersions"],
        "labels": raw["labels"],
        "code": raw["code"],
        "matchingRule": rule,
        "labelsUnchangedSinceRun": current["labelSha256"] == raw["labels"]["labelSha256"]
        and current["matchingSha256"] == raw["labels"]["matchingSha256"],
        "videos": {
            video_id: {
                "title": label["title"],
                "durationMs": label["durationMs"],
                "clean": label["clean"],
            }
            for video_id, label in labels.items()
        },
        **scored,
    }
    if raw.get("reuse"):
        result["reuse"] = raw["reuse"]
    result["newCallCostUsd"] = raw.get("newCallCostUsd")
    if replay_of is not None:
        result["replayOf"] = {"path": str(replay_of), "sha256": sha256_file(replay_of)}
        result["modelCalls"] = 0
    else:
        result["modelCalls"] = raw.get("totalModelRequests", 0)
    return result


def write_scored(result: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(scoring.dump(result))
    path.with_suffix(".md").write_text(scoring.render_markdown(result))
    print(f"wrote {path} and {path.with_suffix('.md')}")


def command_run(args: argparse.Namespace) -> None:
    settings = Settings(_env_file=BACKEND / ".env")  # type: ignore[call-arg]
    model = args.model or settings.model_reviewer
    arms = args.arms.split(",")
    unknown = [arm for arm in arms if arm not in ARMS]
    if unknown:
        raise SystemExit(f"unknown arms: {', '.join(unknown)} (choose from {', '.join(ARMS)})")
    for dependent, prerequisite in (
        ("adjudicated", "reviewers"),
        ("edited", "reviewers"),
        ("edited_adjudicated", "edited"),
    ):
        if dependent not in arms:
            continue
        if prerequisite not in arms:
            if args.reuse_raw and prerequisite == "reviewers":
                continue
            raise SystemExit(f"include {prerequisite} before {dependent}")
        if arms.index(prerequisite) > arms.index(dependent):
            raise SystemExit(f"put {prerequisite} before {dependent}")
    if args.input_price is None:
        args.input_price = settings.llm_input_price_per_mtok
    if args.output_price is None:
        args.output_price = settings.llm_output_price_per_mtok
    labels = load_labels(args.videos.split(",") if args.videos else None)
    plan = plan_calls(arms, labels, settings)
    registration = preregistration()
    if args.reuse_raw:
        validate_reuse(read_json(args.reuse_raw), registration, model, labels, arms)
        if "edited_adjudicated" in plan["perArm"]:
            plan["perArm"]["edited_adjudicated"] = {"min": 0, "max": 0}
        plan["max"] = sum(v["max"] for v in plan["perArm"].values())
    print(f"model            {model}")
    print(f"videos           {', '.join(labels)}")
    print(f"arms             {', '.join(arms)}")
    print(f"grounding        {args.grounding}   footage tools {args.visual_tools}")
    print(f"labels commit    {registration['commit'][:12]}  dirty={registration['dirty']}")
    for arm, bounds in plan["perArm"].items():
        print(f"  {arm:<12} {bounds['min']} to {bounds['max']} generate_content calls")
    print(f"total            {plan['min']} to {plan['max']} calls; --max-calls {args.max_calls}")
    if not args.execute:
        print("dry run: no model call made. Pass --execute to run.")
        return
    if registration["dirty"] and not args.allow_dirty_labels:
        raise SystemExit(
            "pre-registered inputs (labels, transcripts, media, matching rule) have uncommitted "
            "changes. Commit them before running, or pass --allow-dirty-labels for a smoke test."
        )
    if not registration["commit"]:
        raise SystemExit("labels are not committed; pre-registration requires a commit first")
    if plan["min"] > args.max_calls:
        raise SystemExit(
            f"the minimum plan needs {plan['min']} calls but --max-calls is {args.max_calls}"
        )
    if args.model and (args.model != settings.model_reviewer):
        if args.input_price == settings.llm_input_price_per_mtok and (
            args.output_price == settings.llm_output_price_per_mtok
        ):
            print(
                f"warning: --model {args.model} differs from the configured "
                f"{settings.model_reviewer} "
                "but token prices are the configured ones; pass --input-price and --output-price.",
                file=sys.stderr,
            )
    raw_path = asyncio.run(run_arms(args, settings, model))
    raw = read_json(raw_path)
    result = score_raw(raw, replay_of=None)
    write_scored(result, raw_path.with_name(raw_path.name.replace(".raw.json", ".json")))
    print(scoring.render_markdown(result))


def command_replay(args: argparse.Namespace) -> None:
    raw = read_json(args.raw)
    result = score_raw(raw, replay_of=args.raw)
    output = args.output or args.raw.with_name(args.raw.name.replace(".raw.json", "-replay.json"))
    write_scored(result, output)
    print(scoring.render_markdown(result))


def command_report(args: argparse.Namespace) -> None:
    print(scoring.render_markdown(read_json(args.results)), end="")


def main() -> None:
    global EDITORIAL
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run arms over the videos (dry run unless --execute).")
    run.add_argument("--arms", default=DEFAULT_ARMS, help=f"Comma list of {', '.join(ARMS)}.")
    run.add_argument("--videos", help="Comma list of video ids (default: all labelled videos).")
    run.add_argument("--model", help="Gemini model for every arm (default MODEL_REVIEWER).")
    run.add_argument("--input-price", type=float, help="USD per 1M input tokens for --model.")
    run.add_argument("--output-price", type=float, help="USD per 1M output tokens for --model.")
    run.add_argument("--max-calls", type=int, required=True, help="Hard cap on model calls.")
    run.add_argument("--execute", action="store_true", help="Make live model calls.")
    run.add_argument("--grounding", action=argparse.BooleanOptionalAction, default=True)
    run.add_argument("--visual-tools", action=argparse.BooleanOptionalAction, default=True)
    run.add_argument("--adjudicator", default=DEFAULT_ADJUDICATOR, help="module:function")
    run.add_argument(
        "--reuse-raw",
        type=Path,
        help="Reuse reviewer findings and adjudicator verdicts; only editor calls are new.",
    )
    run.add_argument("--run-id")
    run.add_argument("--output-dir", type=Path, default=RESULTS)
    run.add_argument("--allow-dirty-labels", action="store_true")
    run.set_defaults(func=command_run)

    replay = sub.add_parser("replay", help="Re-score a saved raw run with zero model calls.")
    replay.add_argument("raw", type=Path)
    replay.add_argument("--output", type=Path)
    replay.set_defaults(func=command_replay)

    report = sub.add_parser("report", help="Print markdown tables for a scored results file.")
    report.add_argument("results", type=Path)
    report.set_defaults(func=command_report)

    for command in (run, replay, report):
        command.add_argument(
            "--root",
            type=Path,
            default=EDITORIAL,
            help="Eval root containing labels/transcripts/media/scripts/matching.json.",
        )
    args = parser.parse_args()
    EDITORIAL = args.root.resolve()
    args.func(args)


if __name__ == "__main__":
    main()
