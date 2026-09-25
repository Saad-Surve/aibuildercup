"""Reviewer base tests: prompt assembly and model-output normalisation.

`normalize_findings` is the boundary where untrusted model text becomes data that
drives the heatmap, so it gets the most attention here.
"""

from app.agents.reviewer_base import (
    FINDINGS_SCHEMA,
    OUTPUT_RULES,
    SCORE_ANCHORS,
    LlmReviewer,
    ReviewContext,
    SegmentRef,
    build_system_prompt,
    build_user_prompt,
    dimension_label,
    normalize_findings,
    resolve_segment,
    severity_for_score,
)
from app.schemas.analysis import AnalysisDimension, Severity

DIM = AnalysisDimension.clarity


def make_segments() -> tuple[SegmentRef, ...]:
    return (
        SegmentRef("seg-1", 0, 2_000, "Hello and welcome back."),
        SegmentRef("seg-2", 2_000, 5_000, "Today we talk about interviews."),
        SegmentRef("seg-3", 5_000, 9_000, "The first concept is the hook."),
        SegmentRef("seg-4", 9_000, 12_000, "Let us get into it."),
    )


def make_context() -> ReviewContext:
    return ReviewContext(
        persona="# Persona\nBe direct.",
        platform="youtube",
        audience="early-career engineers",
        language="en-US",
        duration_ms=12_000,
        segments=make_segments(),
        context_segments=(SegmentRef("seg-9", 90_000, 92_000, "Earlier."),),
    )


def entry(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "segmentId": "seg-2",
        "startMs": 2_100,
        "endMs": 4_800,
        "score": 6.5,
        "confidence": 0.8,
        "severity": "medium",
        "findingType": "ambiguity",
        "evidence": {"quote": "the first concept", "explanation": "undefined"},
        "suggestion": "Define it first.",
        "citations": [],
    }
    base.update(overrides)
    return base


# --- prompts ----------------------------------------------------------------


def test_system_prompt_carries_label_focus_anchors_and_rules() -> None:
    prompt = build_system_prompt(DIM, "Look for jargon.")
    assert "Clarity (clarity)" in prompt
    assert "Look for jargon." in prompt
    assert SCORE_ANCHORS in prompt
    assert OUTPUT_RULES in prompt


def test_dimension_label_is_readable() -> None:
    assert dimension_label(DIM) == "Clarity"
    assert dimension_label(AnalysisDimension.truth_evidence) == "Truth Evidence"


def test_user_prompt_separates_review_window_from_context() -> None:
    prompt = build_user_prompt(make_context(), DIM)
    assert "# REVIEW WINDOW (report on these)" in prompt
    assert "# CONTEXT ONLY (do not report findings for these)" in prompt
    assert "[seg-1] 0 -> 2000: Hello and welcome back." in prompt
    assert "[seg-9]" in prompt
    # The window is listed before the context block.
    assert prompt.index("[seg-1]") < prompt.index("[seg-9]")
    assert "youtube" in prompt
    assert "early-career engineers" in prompt
    assert "Be direct." in prompt
    assert "en-US" in prompt
    assert "12000 ms" in prompt


def test_user_prompt_omits_empty_optional_sections() -> None:
    context = ReviewContext(
        persona="",
        platform="",
        audience="",
        language="en",
        duration_ms=1_000,
        segments=(SegmentRef("seg-1", 0, 1_000, "hi"),),
    )
    prompt = build_user_prompt(context, DIM)
    assert "CONTEXT ONLY" not in prompt
    assert "Creator persona" not in prompt
    assert "Intended audience" not in prompt


def test_findings_schema_rejects_structural_drift() -> None:
    items = FINDINGS_SCHEMA["properties"]["findings"]["items"]
    assert set(items["required"]) >= {"score", "severity", "startMs", "endMs"}
    assert items["properties"]["severity"]["enum"] == [s.value for s in Severity]


# --- severity / segments ----------------------------------------------------


def test_severity_for_score_bands() -> None:
    assert severity_for_score(9.0) is Severity.none
    assert severity_for_score(8.0) is Severity.none
    assert severity_for_score(7.9) is Severity.low
    assert severity_for_score(6.0) is Severity.low
    assert severity_for_score(5.9) is Severity.medium
    assert severity_for_score(4.0) is Severity.medium
    assert severity_for_score(3.9) is Severity.high
    assert severity_for_score(2.0) is Severity.high
    assert severity_for_score(1.9) is Severity.critical
    assert severity_for_score(0.0) is Severity.critical


def test_resolve_segment_finds_the_containing_segment() -> None:
    segments = make_segments()
    assert resolve_segment(2_500, segments).segment_id == "seg-2"
    assert resolve_segment(0, segments).segment_id == "seg-1"
    assert resolve_segment(9_000, segments).segment_id == "seg-4"
    assert resolve_segment(12_000, segments) is None


# --- normalize_findings -----------------------------------------------------


def test_valid_entry_becomes_a_finding() -> None:
    findings = normalize_findings(
        {"findings": [entry()]},
        dimension=DIM,
        reviewer_run_id="rev-1",
        segments=make_segments(),
        duration_ms=12_000,
    )
    assert len(findings) == 1
    finding = findings[0]
    assert finding.dimension is DIM  # the reviewer's dimension, not the model's
    assert finding.reviewerRunId == "rev-1"
    assert finding.segmentId == "seg-2"
    assert (finding.startMs, finding.endMs) == (2_100, 4_800)
    assert finding.score == 6.5
    assert finding.confidence == 0.8
    assert finding.severity is Severity.medium
    assert finding.evidence.quote == "the first concept"
    assert finding.suggestion == "Define it first."
    assert finding.findingId  # generated, never model-supplied


def test_dimension_is_forced_to_the_reviewers_own() -> None:
    findings = normalize_findings(
        {"findings": [entry(segmentId="seg-1")]},
        dimension=AnalysisDimension.legal_safety,
        reviewer_run_id="rev-1",
        segments=make_segments(),
        duration_ms=12_000,
    )
    assert findings[0].dimension is AnalysisDimension.legal_safety


def test_missing_findings_key_yields_nothing() -> None:
    assert (
        normalize_findings(
            {}, dimension=DIM, reviewer_run_id="r", segments=make_segments(), duration_ms=12_000
        )
        == []
    )
    assert (
        normalize_findings(
            {"findings": "nope"},
            dimension=DIM,
            reviewer_run_id="r",
            segments=make_segments(),
            duration_ms=12_000,
        )
        == []
    )


def test_entries_without_a_score_are_dropped() -> None:
    findings = normalize_findings(
        {"findings": [entry(score=None), entry(score="not-a-number")]},
        dimension=DIM,
        reviewer_run_id="r",
        segments=make_segments(),
        duration_ms=12_000,
    )
    assert findings == []


def test_non_dict_entries_are_dropped() -> None:
    findings = normalize_findings(
        {"findings": ["oops", 42, None, entry()]},
        dimension=DIM,
        reviewer_run_id="r",
        segments=make_segments(),
        duration_ms=12_000,
    )
    assert len(findings) == 1


def test_score_and_confidence_are_clamped() -> None:
    findings = normalize_findings(
        {"findings": [entry(score=99, confidence=-3)]},
        dimension=DIM,
        reviewer_run_id="r",
        segments=make_segments(),
        duration_ms=12_000,
    )
    assert findings[0].score == 10.0
    assert findings[0].confidence == 0.0


def test_missing_confidence_defaults_to_half() -> None:
    findings = normalize_findings(
        {"findings": [entry(confidence=None)]},
        dimension=DIM,
        reviewer_run_id="r",
        segments=make_segments(),
        duration_ms=12_000,
    )
    assert findings[0].confidence == 0.5


def test_unknown_severity_is_derived_from_the_score() -> None:
    findings = normalize_findings(
        {"findings": [entry(score=3.0, severity="catastrophic"), entry(score=9, severity=None)]},
        dimension=DIM,
        reviewer_run_id="r",
        segments=make_segments(),
        duration_ms=12_000,
    )
    assert findings[0].severity is Severity.high
    assert findings[1].severity is Severity.none


def test_valid_severity_is_kept_even_when_the_score_disagrees() -> None:
    findings = normalize_findings(
        {"findings": [entry(score=9.5, severity="critical")]},
        dimension=DIM,
        reviewer_run_id="r",
        segments=make_segments(),
        duration_ms=12_000,
    )
    assert findings[0].severity is Severity.critical


def test_timestamps_are_clamped_to_the_video() -> None:
    findings = normalize_findings(
        {"findings": [entry(startMs=-500, endMs=99_000)]},
        dimension=DIM,
        reviewer_run_id="r",
        segments=make_segments(),
        duration_ms=12_000,
    )
    assert (findings[0].startMs, findings[0].endMs) == (0, 12_000)


def test_findings_entirely_past_the_end_are_dropped() -> None:
    findings = normalize_findings(
        {"findings": [entry(startMs=50_000, endMs=51_000)]},
        dimension=DIM,
        reviewer_run_id="r",
        segments=make_segments(),
        duration_ms=12_000,
    )
    assert findings == []


def test_zero_length_span_falls_back_to_the_named_segment() -> None:
    findings = normalize_findings(
        {"findings": [entry(segmentId="seg-3", startMs=5_000, endMs=5_000)]},
        dimension=DIM,
        reviewer_run_id="r",
        segments=make_segments(),
        duration_ms=12_000,
    )
    assert (findings[0].startMs, findings[0].endMs) == (5_000, 9_000)
    assert findings[0].segmentId == "seg-3"


def test_reversed_span_falls_back_to_the_named_segment() -> None:
    findings = normalize_findings(
        {"findings": [entry(segmentId="seg-2", startMs=4_000, endMs=1_000)]},
        dimension=DIM,
        reviewer_run_id="r",
        segments=make_segments(),
        duration_ms=12_000,
    )
    assert (findings[0].startMs, findings[0].endMs) == (2_000, 5_000)


def test_unusable_span_with_unknown_segment_is_dropped() -> None:
    findings = normalize_findings(
        {"findings": [entry(segmentId="seg-999", startMs=1_000, endMs=500)]},
        dimension=DIM,
        reviewer_run_id="r",
        segments=make_segments(),
        duration_ms=12_000,
    )
    assert findings == []


def test_segment_id_is_resolved_from_timestamps_when_the_model_guesses_wrong() -> None:
    findings = normalize_findings(
        {"findings": [entry(segmentId="seg-999", startMs=9_100, endMs=9_800)]},
        dimension=DIM,
        reviewer_run_id="r",
        segments=make_segments(),
        duration_ms=12_000,
    )
    assert findings[0].segmentId == "seg-4"


def test_unknown_segment_id_with_no_times_is_dropped() -> None:
    findings = normalize_findings(
        {"findings": [entry(segmentId=None, startMs=None, endMs=None)]},
        dimension=DIM,
        reviewer_run_id="r",
        segments=make_segments(),
        duration_ms=12_000,
    )
    assert findings == []


def test_malformed_evidence_and_citations_are_neutralised() -> None:
    findings = normalize_findings(
        {
            "findings": [
                entry(evidence="not a dict", citations=["not a dict", {"url": "ok"}])
            ]
        },
        dimension=DIM,
        reviewer_run_id="r",
        segments=make_segments(),
        duration_ms=12_000,
    )
    finding = findings[0]
    assert finding.evidence.quote == ""
    assert finding.evidence.explanation == ""
    assert finding.citations == [{"url": "ok"}]


def test_overlong_text_is_truncated_not_rejected() -> None:
    findings = normalize_findings(
        {"findings": [entry(suggestion="x" * 5_000)]},
        dimension=DIM,
        reviewer_run_id="r",
        segments=make_segments(),
        duration_ms=12_000,
    )
    assert len(findings[0].suggestion) == 2_000


# --- LlmReviewer ------------------------------------------------------------


class _RecordingLlm:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.calls: list[dict] = []

    async def complete_json(self, **kwargs):
        from app.providers.base import LlmCompletion, LlmUsage

        self.calls.append(kwargs)
        return LlmCompletion(data=self.response, usage=LlmUsage(3, 4))


async def test_llm_reviewer_stamps_the_reviewer_run_id() -> None:
    llm = _RecordingLlm({"findings": [entry()]})

    class _Clarity(LlmReviewer):
        dimension = DIM
        focus = "jargon"

    result = await _Clarity(llm, model="gemini-test").review(
        make_context(), reviewer_run_id="rev-42"
    )
    assert result.findings[0].reviewerRunId == "rev-42"
    assert result.usage.input_tokens == 3
    assert llm.calls[0]["model"] == "gemini-test"
    assert llm.calls[0]["schema"] is FINDINGS_SCHEMA
    assert "Clarity (clarity)" in llm.calls[0]["system"]
