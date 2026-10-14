"""Score editorial-eval arms against the pre-registered gold labels. Pure: no network, no models.

Used by `editorial_eval.py` for live runs and for `replay`. The matching rule lives in
`evals/editorial/matching.json` so it is committed with the labels, before any model run.

A finding matches a gold issue when
  1. its [startMs, endMs] span is within `toleranceMs` of the issue span (or one of the issue's
     `additionalSpans`; zero gap means the spans overlap), and
  2. its dimension is the issue's expected dimension or one of the dimensions listed for the
     issue's category in `categoryDimensions`.
Matching is one-to-one and greedy: candidate pairs are ordered by (touching the span before
only being near it, expected dimension before a merely compatible one, smaller gap, smaller
centre distance) and each issue and each finding is used at most once. Strengths (severity
`none`) are not issue findings and are ignored.
"""

import json
import math
import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

#: Variants reported for every arm. Pre-registered in the README.
VARIANTS: dict[str, tuple[str, bool]] = {
    # name: (severity set key in the rule, dimension must be compatible)
    "headline": ("issueSeverities", True),
    "actionable": ("actionableSeverities", True),
    "timeOnly": ("issueSeverities", False),
}


@dataclass(frozen=True)
class Pair:
    issue_index: int
    finding_index: int
    gap_ms: int
    exact_dimension: bool
    start_error_ms: int
    center_error_ms: int


def interval_gap(start_a: int, end_a: int, start_b: int, end_b: int) -> int:
    """Milliseconds between two spans; zero when they overlap or touch."""
    return max(0, max(start_a, start_b) - min(end_a, end_b))


def issue_spans(issue: Mapping[str, Any]) -> list[tuple[int, int]]:
    spans = [(int(issue["startMs"]), int(issue["endMs"]))]
    spans.extend((int(s["startMs"]), int(s["endMs"])) for s in issue.get("additionalSpans", []))
    return spans


def compatible_dimensions(issue: Mapping[str, Any], rule: Mapping[str, Any]) -> set[str]:
    return {issue["expectedDimension"], *rule["categoryDimensions"].get(issue["category"], [])}


def issue_findings(
    findings: Sequence[Mapping[str, Any]], severities: Sequence[str]
) -> list[Mapping[str, Any]]:
    return [finding for finding in findings if finding.get("severity") in severities]


def match_findings(
    issues: Sequence[Mapping[str, Any]],
    findings: Sequence[Mapping[str, Any]],
    rule: Mapping[str, Any],
    *,
    require_dimension: bool,
) -> list[Pair]:
    """One-to-one greedy matching of findings to gold issues."""
    tolerance = int(rule["toleranceMs"])
    candidates: list[Pair] = []
    for i, issue in enumerate(issues):
        allowed = compatible_dimensions(issue, rule)
        for j, finding in enumerate(findings):
            dimension = finding.get("dimension")
            if require_dimension and dimension not in allowed:
                continue
            f_start, f_end = int(finding["startMs"]), int(finding["endMs"])
            best: tuple[int, tuple[int, int]] | None = None
            for span in issue_spans(issue):
                gap = interval_gap(f_start, f_end, *span)
                if best is None or gap < best[0]:
                    best = (gap, span)
            if best is None or best[0] > tolerance:
                continue
            gap, (s_start, s_end) = best
            candidates.append(
                Pair(
                    issue_index=i,
                    finding_index=j,
                    gap_ms=gap,
                    exact_dimension=dimension == issue["expectedDimension"],
                    start_error_ms=abs(f_start - s_start),
                    center_error_ms=abs((f_start + f_end) // 2 - (s_start + s_end) // 2),
                )
            )
    candidates.sort(
        key=lambda p: (
            p.gap_ms > 0,
            not p.exact_dimension,
            p.gap_ms,
            p.center_error_ms,
            p.issue_index,
            p.finding_index,
        )
    )
    used_issues: set[int] = set()
    used_findings: set[int] = set()
    chosen: list[Pair] = []
    for pair in candidates:
        if pair.issue_index in used_issues or pair.finding_index in used_findings:
            continue
        used_issues.add(pair.issue_index)
        used_findings.add(pair.finding_index)
        chosen.append(pair)
    return sorted(chosen, key=lambda p: p.issue_index)


def summarize_finding(finding: Mapping[str, Any]) -> dict[str, Any]:
    evidence = finding.get("evidence") or {}
    return {
        "dimension": finding.get("dimension"),
        "findingType": finding.get("findingType"),
        "severity": finding.get("severity"),
        "startMs": finding.get("startMs"),
        "endMs": finding.get("endMs"),
        "quote": str(evidence.get("quote", ""))[:120],
    }


def score_video(
    label: Mapping[str, Any],
    findings: Sequence[Mapping[str, Any]],
    rule: Mapping[str, Any],
) -> dict[str, Any]:
    """Every variant for one video: matches, misses, unmatched findings and timing error."""
    issues: list[Mapping[str, Any]] = label["issues"]
    result: dict[str, Any] = {
        "videoId": label["videoId"],
        "clean": bool(label.get("clean")),
        "durationMs": int(label["durationMs"]),
        "issueCount": len(issues),
        "strengthCount": sum(1 for f in findings if f.get("severity") == "none"),
        "variants": {},
    }
    for name, (severity_key, require_dimension) in VARIANTS.items():
        counted = issue_findings(findings, rule[severity_key])
        pairs = match_findings(issues, counted, rule, require_dimension=require_dimension)
        matched_findings = {p.finding_index for p in pairs}
        by_issue = {p.issue_index: p for p in pairs}
        result["variants"][name] = {
            "findingCount": len(counted),
            "matchedCount": len(pairs),
            "unmatchedFindingCount": len(counted) - len(pairs),
            "issues": [
                {
                    "id": issue["id"],
                    "category": issue["category"],
                    "matched": i in by_issue,
                    "startErrorMs": by_issue[i].start_error_ms if i in by_issue else None,
                    "centerErrorMs": by_issue[i].center_error_ms if i in by_issue else None,
                    "matchedDimension": (
                        counted[by_issue[i].finding_index].get("dimension")
                        if i in by_issue
                        else None
                    ),
                }
                for i, issue in enumerate(issues)
            ],
            "unmatchedFindings": [
                summarize_finding(finding)
                for j, finding in enumerate(counted)
                if j not in matched_findings
            ],
        }
    return result


def wilson(successes: int, total: int, z: float = 1.96) -> tuple[float, float] | None:
    """95% Wilson interval for a proportion, or None with no denominator."""
    if total <= 0:
        return None
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return round(max(0.0, centre - margin), 3), round(min(1.0, centre + margin), 3)


def ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 3) if denominator else None


def aggregate_arm(videos: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Pool one arm's per-video scores. Recall and precision use flawed videos only; the clean
    controls are reported as false positives, so they cannot dilute precision."""
    flawed = [v for v in videos if not v["clean"]]
    clean = [v for v in videos if v["clean"]]
    out: dict[str, Any] = {
        "flawedVideos": len(flawed),
        "cleanVideos": len(clean),
        "goldIssues": sum(v["issueCount"] for v in flawed),
    }
    for name in VARIANTS:
        matched = sum(v["variants"][name]["matchedCount"] for v in flawed)
        findings = sum(v["variants"][name]["findingCount"] for v in flawed)
        gold = out["goldIssues"]
        clean_findings = sum(v["variants"][name]["findingCount"] for v in clean)
        clean_minutes = sum(v["durationMs"] for v in clean) / 60_000
        out[name] = {
            "matched": matched,
            "recall": ratio(matched, gold),
            "recallCi95": wilson(matched, gold),
            "findings": findings,
            "precision": ratio(matched, findings),
            "precisionCi95": wilson(matched, findings),
            "unmatchedFindings": findings - matched,
            "cleanControlFindings": clean_findings,
            "cleanControlsFlagged": sum(1 for v in clean if v["variants"][name]["findingCount"]),
            "cleanControlFindingsPerMinute": (
                round(clean_findings / clean_minutes, 2) if clean_minutes else None
            ),
        }
    errors = [
        issue["startErrorMs"]
        for v in flawed
        for issue in v["variants"]["headline"]["issues"]
        if issue["matched"]
    ]
    out["startErrorMs"] = {
        "median": round(statistics.median(errors)) if errors else None,
        "mean": round(statistics.fmean(errors)) if errors else None,
        "max": max(errors) if errors else None,
        "n": len(errors),
    }
    per_category: dict[str, list[bool]] = defaultdict(list)
    for v in flawed:
        for issue in v["variants"]["headline"]["issues"]:
            per_category[issue["category"]].append(bool(issue["matched"]))
    out["byCategory"] = {
        category: {"matched": sum(hits), "total": len(hits)}
        for category, hits in sorted(per_category.items())
    }
    return out


def paired_issue_overlap(
    left: Sequence[Mapping[str, Any]], right: Sequence[Mapping[str, Any]]
) -> dict[str, int]:
    """Gold issues found by both arms, one arm, or neither (headline variant)."""

    def hits(videos: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], bool]:
        return {
            (v["videoId"], issue["id"]): bool(issue["matched"])
            for v in videos
            if not v["clean"]
            for issue in v["variants"]["headline"]["issues"]
        }

    a, b = hits(left), hits(right)
    keys = sorted(set(a) & set(b))
    return {
        "both": sum(a[k] and b[k] for k in keys),
        "onlyFirst": sum(a[k] and not b[k] for k in keys),
        "onlySecond": sum(b[k] and not a[k] for k in keys),
        "neither": sum(not a[k] and not b[k] for k in keys),
    }


def usd(input_tokens: int, output_tokens: int, prices: Mapping[str, float]) -> float:
    return round(
        (input_tokens * prices["inputPerMTok"] + output_tokens * prices["outputPerMTok"])
        / 1_000_000,
        6,
    )


def score_run(
    raw: Mapping[str, Any],
    labels: Mapping[str, Mapping[str, Any]],
    rule: Mapping[str, Any],
    findings_by_arm: Mapping[str, Mapping[str, Sequence[Mapping[str, Any]]]],
) -> dict[str, Any]:
    """Score every arm in a raw run. `findings_by_arm[arm][videoId]` are the normalised findings."""
    prices: Mapping[str, float] = raw["prices"]
    arms: dict[str, Any] = {}
    for arm, runs in raw["arms"].items():
        videos: list[dict[str, Any]] = []
        for video_id, run in runs["videos"].items():
            if video_id not in labels:
                raise KeyError(f"no label for video {video_id}")
            scored = score_video(labels[video_id], findings_by_arm[arm][video_id], rule)
            usage = run.get("usage", {})
            scored["usage"] = usage
            scored["modelRequests"] = run.get("modelRequests", 0)
            scored["searchQueries"] = run.get("searchQueries", 0)
            scored["costUsd"] = usd(
                usage.get("inputTokens", 0), usage.get("outputTokens", 0), prices
            )
            scored["errors"] = run.get("errors", [])
            videos.append(scored)
        aggregate = aggregate_arm(videos)
        input_tokens = sum(v["usage"].get("inputTokens", 0) for v in videos)
        output_tokens = sum(v["usage"].get("outputTokens", 0) for v in videos)
        cost = round(sum(v["costUsd"] for v in videos), 6)
        matched = aggregate["headline"]["matched"]
        aggregate["cost"] = {
            "inputTokens": input_tokens,
            "outputTokens": output_tokens,
            "usd": cost,
            "modelRequests": sum(v["modelRequests"] for v in videos),
            "searchQueries": sum(v["searchQueries"] for v in videos),
            "usdPerMatchedIssue": round(cost / matched, 6) if matched else None,
            "failedCalls": sum(len(v["errors"]) for v in videos),
        }
        arms[arm] = {"aggregate": aggregate, "videos": videos}
    names = list(arms)
    paired = {
        f"{first}__vs__{second}": paired_issue_overlap(
            arms[first]["videos"], arms[second]["videos"]
        )
        for index, first in enumerate(names)
        for second in names[index + 1 :]
    }
    return {"arms": arms, "paired": paired}


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.0f}%"


def pct_ci(value: float | None, ci: Sequence[float] | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.0f}% ({ci[0] * 100:.0f}-{ci[1] * 100:.0f})" if ci else pct(value)


def render_markdown(result: Mapping[str, Any]) -> str:
    """The README tables, generated from a scored results file."""
    arms: Mapping[str, Any] = result["arms"]
    lines = [
        f"Run `{result['runId']}` - model `{result['model']}`, labels at commit "
        f"`{result['labels']['commit']}`.",
        "",
        "| Arm | Recall (95% CI) | Recall, severity ≥ medium | Recall, time only | "
        "Precision | Start error, median | Clean-control findings (per min) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for arm, data in arms.items():
        agg = data["aggregate"]
        head = agg["headline"]
        err = agg["startErrorMs"]["median"]
        lines.append(
            f"| {arm} | {head['matched']}/{agg['goldIssues']} "
            f"{pct_ci(head['recall'], head['recallCi95'])} "
            f"| {agg['actionable']['matched']}/{agg['goldIssues']} "
            f"{pct(agg['actionable']['recall'])} "
            f"| {agg['timeOnly']['matched']}/{agg['goldIssues']} {pct(agg['timeOnly']['recall'])} "
            f"| {head['matched']}/{head['findings']} {pct(head['precision'])} "
            f"| {'n/a' if err is None else f'{err / 1000:.1f} s'} "
            f"| {head['cleanControlFindings']} ({head['cleanControlFindingsPerMinute']}) |"
        )
    lines += ["", "Recall by category (headline matching):", ""]
    categories = sorted({c for data in arms.values() for c in data["aggregate"]["byCategory"]})
    lines.append("| Category | " + " | ".join(arms) + " |")
    lines.append("|---|" + "---:|" * len(arms))
    for category in categories:
        cells = []
        for data in arms.values():
            cell = data["aggregate"]["byCategory"].get(category)
            cells.append(f"{cell['matched']}/{cell['total']}" if cell else "-")
        lines.append(f"| {category} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "Cost and calls (token prices "
        f"${result['prices']['inputPerMTok']}/M in, ${result['prices']['outputPerMTok']}/M out; "
        "Search queries are counted, not priced):",
        "",
        "| Arm | Model requests | Input tokens | Output tokens | Estimated USD | "
        "USD per matched issue | Failed calls |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for arm, data in arms.items():
        cost = data["aggregate"]["cost"]
        per_issue = cost["usdPerMatchedIssue"]
        lines.append(
            f"| {arm} | {cost['modelRequests']} | {cost['inputTokens']:,} | "
            f"{cost['outputTokens']:,} | ${cost['usd']:.4f} | "
            f"{'n/a' if per_issue is None else f'${per_issue:.4f}'} | {cost['failedCalls']} |"
        )
    if result.get("paired"):
        lines += [
            "",
            "Gold issues found, paired by issue (headline matching):",
            "",
            "| Pair | Both | Only first | Only second | Neither |",
            "|---|---:|---:|---:|---:|",
        ]
        for pair, counts in result["paired"].items():
            first, second = pair.split("__vs__")
            lines.append(
                f"| {first} vs {second} | {counts['both']} | {counts['onlyFirst']} | "
                f"{counts['onlySecond']} | {counts['neither']} |"
            )
    return "\n".join(lines) + "\n"


def dump(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"
