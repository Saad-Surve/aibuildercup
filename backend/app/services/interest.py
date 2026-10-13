"""Predicted audience interest: a continuous curve under the review heatmap.

The reviewers report exceptions, so most of a good video has no finding. This module fills
every five-second bin with a *relative* interest estimate learned from public YouTube
"Most Replayed" curves (`backend/scripts/interest_train.py`, `evals/interest/`).

The label is replay intensity normalised within each video, so the output ranks moments
inside one video. It is not retention, watch time or a cross-video quality score.

Three layers, all shared verbatim by training and inference so they cannot drift:

1. `transcript_features`: deterministic per-bin signals from word timings (pace, pauses,
   fillers, questions, numbers, direct address, lexical novelty, position).
2. `score_windows`: one bounded Gemini pass that rates each bin's transcript for hook,
   payoff, novelty, open loops, emotion, humour, practical value, visual cues and tangents.
3. `InterestModel`: a ridge regression stored as JSON coefficients
   (`app/assets/interest/model.json`), so inference needs no ML runtime.
"""

import asyncio
import json
import logging
import math
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.providers.base import LlmProvider, LlmUsage

logger = logging.getLogger(__name__)

#: Matches the review heatmap so a bin lines up with its findings.
BIN_MS = 5000

FEATURE_VERSION = "interest-features-v3"
SIGNAL_PROMPT_VERSION = "interest-signals-v2"

MODEL_PATH = Path(__file__).resolve().parents[1] / "assets" / "interest" / "model.json"

#: Bins per Gemini call. 120 bins is ten minutes of video.
SIGNAL_WINDOW_BINS = 120
#: Characters of transcript per bin handed to the model.
SIGNAL_BIN_CHARS = 220
#: Hard bound on Gemini calls per video, whatever its length.
MAX_SIGNAL_CALLS = 4

#: Gemini-rated signals, each 1-5. Order is the schema order the model generates in.
SIGNALS: tuple[tuple[str, str], ...] = (
    ("hook", "Grabs attention or promises something the viewer wants to see."),
    ("payoff", "Delivers a reveal, answer, result, punchline or promised moment."),
    ("novelty", "Introduces genuinely new information rather than restating."),
    ("open_loop", "Raises a question or teases something that comes later."),
    ("emotion", "Emotional intensity: surprise, stakes, conflict, excitement."),
    ("humor", "A joke, playful line or comic moment."),
    ("practical", "Concrete, actionable advice, steps or numbers the viewer can use."),
    ("visual", "Refers to something shown on screen: a demo, result, chart or reveal."),
    ("tangent", "Filler, rambling, housekeeping, sponsor read or off-topic aside."),
)
SIGNAL_NAMES = tuple(name for name, _ in SIGNALS)

#: Deterministic features, in model order.
TRANSCRIPT_FEATURES = (
    "pos",
    "pos_sq",
    "opening",
    "closing",
    "pos_x_length",
    "opening_x_length",
    "speech_ratio",
    "wpm",
    "pause_max",
    "filler_rate",
    "question_rate",
    "number_rate",
    "you_rate",
    "novelty_rate",
    "pace_change",
)

#: Features that also get a +-2 bin rolling mean, because interest is smooth over time.
CONTEXT_FEATURES = (
    "speech_ratio",
    "wpm",
    "pause_max",
    "novelty_rate",
    *SIGNAL_NAMES,
)

#: Features that also get a within-video version (value minus the video's mean), so the
#: model ranks a moment against the rest of its own video rather than against other videos.
RELATIVE_FEATURES = (
    "speech_ratio",
    "wpm",
    "pause_max",
    "filler_rate",
    "novelty_rate",
    *SIGNAL_NAMES,
)

#: Position-only features: the typical drop-off shape every video shares.
POSITION_FEATURES = (
    "pos",
    "pos_sq",
    "opening",
    "closing",
    "pos_x_length",
    "opening_x_length",
)

#: Human labels for curve drivers: (when the feature pushes interest up, when it pulls down).
DRIVER_LABELS: dict[str, tuple[str, str]] = {
    "speech_ratio": ("dense speech", "little speech"),
    "wpm": ("fast delivery", "slow delivery"),
    "pause_max": ("a long pause", "no pauses"),
    "filler_rate": ("filler words", "few filler words"),
    "question_rate": ("questions to the viewer", "no questions"),
    "number_rate": ("specific numbers", "no specifics"),
    "you_rate": ("direct address", "little direct address"),
    "novelty_rate": ("new information", "repeated material"),
    "pace_change": ("a change of pace", "a steady pace"),
    "hook": ("a hook", "no hook"),
    "payoff": ("a payoff", "no payoff"),
    "novelty": ("new information", "restated material"),
    "open_loop": ("an open question", "no open question"),
    "emotion": ("emotional stakes", "flat emotion"),
    "humor": ("humour", "no humour"),
    "practical": ("practical value", "little practical value"),
    "visual": ("an on-screen moment", "nothing to look at"),
    "tangent": ("a tangent", "staying on topic"),
}

_TOKEN = re.compile(r"\w+", re.UNICODE)
_NUMBER = re.compile(r"\d")

_FILLERS = frozenset(
    {
        "um", "uh", "erm", "hmm", "like", "basically", "actually", "literally", "anyway",
        "okay", "ok", "so", "right", "yeah",
        "मतलब", "अच्छा", "तो", "वैसे", "यानी", "हां", "ठीक",
    }
)  # fmt: skip
_QUESTION_WORDS = frozenset(
    {
        "what", "why", "how", "when", "where", "which", "who", "ever", "imagine",
        "क्या", "क्यों", "कैसे", "कब", "कहां", "कहाँ", "कौन", "कितना", "कितने",
    }
)  # fmt: skip
_YOU_WORDS = frozenset(
    {"you", "your", "you're", "yours", "yourself", "आप", "आपको", "आपका", "आपके", "तुम", "तुम्हें"}
)
_NUMBER_WORDS = frozenset(
    {
        "hundred", "thousand", "million", "billion", "percent", "lakh", "crore",
        "सौ", "हजार", "हज़ार", "लाख", "करोड़", "प्रतिशत",
    }
)  # fmt: skip
_STOP = frozenset(
    {
        "the", "and", "that", "this", "with", "have", "from", "they", "there", "their", "what",
        "about", "would", "could", "should", "will", "just", "like", "your", "then", "than",
        "them", "when", "were", "been", "being", "into", "also", "very", "really", "because",
        "going", "know", "some", "more", "which", "where", "here", "these", "those", "only",
        "है", "हैं", "में", "की", "के", "का", "को", "से", "और", "भी", "तो", "यह", "वो", "था",
    }
)  # fmt: skip


@dataclass(frozen=True)
class TimedWord:
    text: str
    start_ms: int
    end_ms: int


def bin_count(duration_ms: int) -> int:
    return max(0, math.ceil(max(0, duration_ms) / BIN_MS))


def tokens(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFC", text).lower()
    return _TOKEN.findall(normalized)


def words_from_segments(segments: Sequence[tuple[int, int, str]]) -> list[TimedWord]:
    """Spread each segment's words evenly over its span.

    Edited transcripts keep segment timings but not word timings, so this is the common
    denominator. Gaps between segments, which carry the pauses that matter, are exact.
    """
    words: list[TimedWord] = []
    for start_ms, end_ms, text in segments:
        parts = text.split()
        if not parts:
            continue
        span = max(1, end_ms - start_ms)
        step = span / len(parts)
        for index, part in enumerate(parts):
            start = int(start_ms + index * step)
            words.append(TimedWord(part, start, max(start + 1, int(start_ms + (index + 1) * step))))
    words.sort(key=lambda word: word.start_ms)
    return words


def bin_texts(words: Sequence[TimedWord], duration_ms: int) -> list[str]:
    """Transcript text per bin, by each word's start time."""
    texts: list[list[str]] = [[] for _ in range(bin_count(duration_ms))]
    for word in words:
        index = min(len(texts) - 1, word.start_ms // BIN_MS) if texts else -1
        if index >= 0:
            texts[index].append(word.text)
    return [" ".join(parts) for parts in texts]


def transcript_features(words: Sequence[TimedWord], duration_ms: int) -> list[dict[str, float]]:
    """Deterministic per-bin features. Every value is bounded to roughly [0, 1]."""
    count = bin_count(duration_ms)
    if count == 0:
        return []
    per_bin: list[list[TimedWord]] = [[] for _ in range(count)]
    for word in words:
        per_bin[min(count - 1, max(0, word.start_ms // BIN_MS))].append(word)

    # Longest silence touching each bin, from gaps between consecutive words. Leading
    # silence before the first word counts too.
    pause = [0.0] * count
    previous_end = 0
    for word in words:
        gap_start, gap_end = previous_end, word.start_ms
        if gap_end - gap_start > 0:
            first = max(0, gap_start // BIN_MS)
            last = min(count - 1, max(0, (gap_end - 1) // BIN_MS))
            for index in range(first, last + 1):
                bin_start = index * BIN_MS
                overlap = min(gap_end, bin_start + BIN_MS) - max(gap_start, bin_start)
                pause[index] = max(pause[index], overlap / BIN_MS)
        previous_end = max(previous_end, word.end_ms)
    if previous_end < duration_ms:
        for index in range(min(count - 1, previous_end // BIN_MS), count):
            bin_start = index * BIN_MS
            overlap = min(duration_ms, bin_start + BIN_MS) - max(previous_end, bin_start)
            pause[index] = max(pause[index], max(0, overlap) / BIN_MS)

    # A one-minute clip and a twenty-minute video drop off differently; position terms
    # interact with log length (0 at 30 s, 1 at 30 min) so one model covers both.
    length = min(1.0, max(0.0, math.log(max(duration_ms, 30_000) / 30_000) / math.log(60)))
    seen: set[str] = set()
    rows: list[dict[str, float]] = []
    previous_wpm = 0.0
    for index, bin_words in enumerate(per_bin):
        bin_start = index * BIN_MS
        bin_end = min(duration_ms, bin_start + BIN_MS)
        width = max(1, bin_end - bin_start)
        center = (bin_start + bin_end) / 2
        pos = center / max(1, duration_ms)
        spoken = sum(
            max(0, min(bin_end, word.end_ms) - max(bin_start, word.start_ms)) for word in bin_words
        )
        toks = [token for word in bin_words for token in tokens(word.text)]
        n = len(toks)
        wpm = n * 60_000 / width
        content = [token for token in toks if len(token) > 3 and token not in _STOP]
        new = [token for token in content if token not in seen]
        seen.update(content)
        rows.append(
            {
                "pos": pos,
                "pos_sq": pos * pos,
                "opening": math.exp(-center / 20_000),
                "closing": max(0.0, (pos - 0.85) / 0.15),
                "pos_x_length": pos * length,
                "opening_x_length": math.exp(-center / 20_000) * length,
                "speech_ratio": min(1.0, spoken / width),
                "wpm": min(1.0, wpm / 240),
                "pause_max": min(1.0, pause[index]),
                "filler_rate": sum(token in _FILLERS for token in toks) / n if n else 0.0,
                "question_rate": sum(token in _QUESTION_WORDS for token in toks) / n if n else 0.0,
                "number_rate": (
                    sum(bool(_NUMBER.search(token)) or token in _NUMBER_WORDS for token in toks) / n
                    if n
                    else 0.0
                ),
                "you_rate": sum(token in _YOU_WORDS for token in toks) / n if n else 0.0,
                "novelty_rate": len(new) / len(content) if content else 0.0,
                "pace_change": min(1.0, abs(wpm - previous_wpm) / 120) if index else 0.0,
            }
        )
        previous_wpm = wpm
    return rows


# ------------------------------------------------------------------ Gemini signals

_SIGNAL_SYSTEM = """\
You annotate the transcript of an online video, five seconds at a time, for what a viewer
experiences in each moment. You are not judging quality or giving advice.

Rate every bin you are given on each signal from 1 (absent) to 5 (very strong). Rate from
the words in that bin, read in the context of the bins around it. A bin with no speech
gets 1 on everything except `visual`, which you may rate higher when the surrounding
speech points at something on screen.

Signals, in this exact order:
{signals}

For each bin return its number `i` and `r`: a string of exactly {count} digits from 1 to 5,
one digit per signal in the order above. Example for a bin that opens with a strong hook
and an open question: "513211111". Return every bin, in order. JSON only."""


def _signal_schema() -> dict[str, Any]:
    item: dict[str, Any] = {
        "i": {"type": "integer"},
        "r": {"type": "string", "minLength": len(SIGNALS), "maxLength": len(SIGNALS)},
    }
    return {
        "type": "object",
        "properties": {
            "bins": {
                "type": "array",
                "items": {"type": "object", "properties": item, "required": list(item)},
            }
        },
        "required": ["bins"],
    }


def _parse_code(code: Any) -> dict[str, float] | None:
    """`"513211111"` -> signal values scaled to [0, 1]; None when malformed."""
    digits = str(code or "").strip()
    if len(digits) != len(SIGNALS) or any(ch not in "12345" for ch in digits):
        return None
    return {name: (int(ch) - 1) / 4 for name, ch in zip(SIGNAL_NAMES, digits, strict=True)}


def _format_ms(ms: int) -> str:
    seconds = ms // 1000
    return f"{seconds // 60}:{seconds % 60:02d}"


@dataclass
class SignalResult:
    rows: list[dict[str, float]] | None
    usage: LlmUsage = field(default_factory=LlmUsage)
    calls: int = 0
    failures: int = 0


async def score_windows(
    llm: LlmProvider,
    *,
    model: str,
    texts: Sequence[str],
    title: str = "",
    language: str = "",
) -> SignalResult:
    """Rate every bin with Gemini, in at most `MAX_SIGNAL_CALLS` bounded calls.

    Returns `rows=None` when any window fails, so the caller falls back to the
    transcript-only model instead of mixing imputed and rated bins.
    """
    count = len(texts)
    if count == 0:
        return SignalResult(rows=[])
    window = max(SIGNAL_WINDOW_BINS, math.ceil(count / MAX_SIGNAL_CALLS))
    starts = list(range(0, count, window))
    system = _SIGNAL_SYSTEM.format(
        signals="\n".join(
            f"{n}. {name}: {description}" for n, (name, description) in enumerate(SIGNALS, 1)
        ),
        count=len(SIGNALS),
    )
    schema = _signal_schema()

    async def rate(start: int) -> tuple[dict[int, dict[str, float]], LlmUsage]:
        end = min(count, start + window)
        lines = [
            f"[{i}] {_format_ms(i * BIN_MS)} {texts[i][:SIGNAL_BIN_CHARS] or '(no speech)'}"
            for i in range(start, end)
        ]
        header = f"Video title: {title}\n" if title else ""
        if language:
            header += f"Language: {language}\n"
        user = (
            f"{header}Bins {start} to {end - 1} of {count}.\n\n" + "\n".join(lines)
        )
        completion = await llm.complete_json(
            model=model,
            prompt_version=SIGNAL_PROMPT_VERSION,
            system=system,
            user=user,
            schema=schema,
        )
        rated: dict[int, dict[str, float]] = {}
        for entry in completion.data.get("bins") or []:
            if not isinstance(entry, dict):
                continue
            try:
                index = int(entry.get("i", -1))
            except (TypeError, ValueError):
                continue
            values = _parse_code(entry.get("r"))
            if values is None or not start <= index < end:
                continue
            rated[index] = values
        missing = (end - start) - len(rated)
        if missing > max(2, (end - start) // 10):
            raise ValueError(f"signal window {start}-{end} missing {missing} bins")
        return rated, completion.usage

    results = await asyncio.gather(*(rate(start) for start in starts), return_exceptions=True)
    usage = LlmUsage()
    merged: dict[int, dict[str, float]] = {}
    failures = 0
    for result in results:
        if isinstance(result, BaseException):
            failures += 1
            logger.warning("interest signal window failed: %s", result)
            continue
        rated, call_usage = result
        merged.update(rated)
        usage = LlmUsage(
            input_tokens=usage.input_tokens + call_usage.input_tokens,
            output_tokens=usage.output_tokens + call_usage.output_tokens,
        )
    if failures:
        return SignalResult(rows=None, usage=usage, calls=len(starts), failures=failures)
    neutral = dict.fromkeys(SIGNAL_NAMES, 0.0)
    rows = [merged.get(index, neutral) for index in range(count)]
    return SignalResult(rows=rows, usage=usage, calls=len(starts))


# ------------------------------------------------------------------ feature assembly


def assemble(
    transcript_rows: Sequence[dict[str, float]],
    signal_rows: Sequence[dict[str, float]] | None,
) -> list[dict[str, float]]:
    """Merge per-bin features and add +-2 bin rolling means of the smooth ones."""
    rows = [
        {**row, **(signal_rows[index] if signal_rows is not None else {})}
        for index, row in enumerate(transcript_rows)
    ]
    count = len(rows)
    for name in CONTEXT_FEATURES:
        if count and name not in rows[0]:
            continue
        values = [row[name] for row in rows]
        for index in range(count):
            lo, hi = max(0, index - 2), min(count, index + 3)
            rows[index][f"{name}_ctx"] = sum(values[lo:hi]) / (hi - lo)
    for name in RELATIVE_FEATURES:
        if not count or name not in rows[0]:
            continue
        mean = sum(row[name] for row in rows) / count
        for row in rows:
            row[f"{name}_rel"] = row[name] - mean
    return rows


def feature_names(*, with_signals: bool) -> list[str]:
    names = list(TRANSCRIPT_FEATURES)
    if with_signals:
        names.extend(SIGNAL_NAMES)
    names.extend(
        f"{name}_ctx"
        for name in CONTEXT_FEATURES
        if with_signals or name not in SIGNAL_NAMES
    )
    names.extend(
        f"{name}_rel"
        for name in RELATIVE_FEATURES
        if with_signals or name not in SIGNAL_NAMES
    )
    return names


# ------------------------------------------------------------------ model


@dataclass(frozen=True)
class LinearHead:
    """Standardised ridge regression: y = b + sum(w * (x - mean) / std)."""

    features: tuple[str, ...]
    mean: tuple[float, ...]
    std: tuple[float, ...]
    weights: tuple[float, ...]
    intercept: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LinearHead":
        return cls(
            features=tuple(data["features"]),
            mean=tuple(float(v) for v in data["mean"]),
            std=tuple(float(v) or 1.0 for v in data["std"]),
            weights=tuple(float(v) for v in data["weights"]),
            intercept=float(data.get("intercept", 0.0)),
        )

    def contributions(self, row: dict[str, float]) -> list[float]:
        return [
            weight * (float(row.get(name, 0.0)) - mean) / std
            for name, mean, std, weight in zip(
                self.features, self.mean, self.std, self.weights, strict=True
            )
        ]

    def predict(self, row: dict[str, float]) -> float:
        return self.intercept + sum(self.contributions(row))


@dataclass(frozen=True)
class InterestModel:
    version: str
    full: LinearHead
    transcript_only: LinearHead
    #: The typical drop-off from position alone; the other heads are read against it.
    position: LinearHead
    signal_model: str
    metrics: dict[str, Any]
    #: "full" when the Gemini signals won cross-validation, else "transcript_only": the
    #: signal pass is then skipped, since it would cost a call without helping.
    primary: str = "full"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InterestModel":
        return cls(
            version=str(data["version"]),
            full=LinearHead.from_dict(data["heads"]["full"]),
            transcript_only=LinearHead.from_dict(data["heads"]["transcript_only"]),
            position=LinearHead.from_dict(data["heads"]["position"]),
            signal_model=str(data.get("signalModel") or ""),
            metrics=dict(data.get("metrics") or {}),
            primary=str(data.get("primaryHead") or "full"),
        )

    @property
    def uses_signals(self) -> bool:
        return self.primary == "full"


@lru_cache(maxsize=1)
def load_model(path: str = str(MODEL_PATH)) -> InterestModel | None:
    """The bundled model, or None when it has not been trained yet."""
    try:
        return InterestModel.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
    except FileNotFoundError:
        return None
    except (KeyError, ValueError, TypeError):
        logger.exception("interest model at %s is unreadable", path)
        return None


# ------------------------------------------------------------------ curve


@dataclass(frozen=True)
class CurvePoint:
    start_ms: int
    end_ms: int
    value: float
    #: The typical drop-off at this point, on the same [0, 1] scale as `value`.
    baseline: float
    #: Prediction minus the typical drop-off: what the content adds or costs here.
    lift: float
    drivers_up: tuple[str, ...]
    drivers_down: tuple[str, ...]
    signals: dict[str, float]


@dataclass(frozen=True)
class CurveMoment:
    kind: str
    start_ms: int
    end_ms: int
    value: float
    drivers: tuple[str, ...]


@dataclass(frozen=True)
class Curve:
    points: list[CurvePoint]
    peaks: list[CurveMoment]
    dips: list[CurveMoment]
    feature_source: str


def _drivers(head: LinearHead, row: dict[str, float], *, positive: bool) -> tuple[str, ...]:
    """Up to two phrases for what moves this bin up (or down).

    Something present in the moment ("a payoff", "a long pause") explains a bin better than
    something absent ("no hook"), so present features are preferred and absences are used
    only to fill the remaining slot.
    """
    present: list[tuple[float, str]] = []
    absent: list[tuple[float, str]] = []
    for name, contribution, weight in zip(
        head.features, head.contributions(row), head.weights, strict=True
    ):
        if (contribution <= 0.05) if positive else (contribution >= -0.05):
            continue
        base = name.removesuffix("_ctx").removesuffix("_rel")
        pair = DRIVER_LABELS.get(base)
        if pair is None:
            continue
        # A contribution in the requested direction comes from a value above average when
        # the weight points the same way, and from a value below average otherwise.
        above = (weight > 0) == positive
        (present if above else absent).append((abs(contribution), pair[0] if above else pair[1]))
    labels: list[str] = []
    for _, label in sorted(present, reverse=True) + sorted(absent, reverse=True):
        if label not in labels:
            labels.append(label)
        if len(labels) == 2:
            break
    return tuple(labels)


def _smooth(values: Sequence[float]) -> list[float]:
    count = len(values)
    out: list[float] = []
    for index in range(count):
        lo, hi = max(0, index - 1), min(count, index + 2)
        weights = {j: 1.0 if j == index else 0.5 for j in range(lo, hi)}
        out.append(sum(values[j] * w for j, w in weights.items()) / sum(weights.values()))
    return out


def _moments(
    points: Sequence[CurvePoint], *, kind: str, limit: int = 3, min_gap_bins: int = 6
) -> list[CurveMoment]:
    """The moments that most beat (peaks) or fall short of (dips) the typical drop-off.

    Ranked by `lift`, not by `value`, so a dip is content that underperforms its place in
    the video rather than just the late part of every video. At least `min_gap_bins`
    apart; dips skip the first 15 seconds, where the curve is dominated by arrivals.
    """
    count = len(points)
    if count < 5:
        return []
    order = sorted(
        range(count),
        key=lambda i: points[i].lift,
        reverse=kind == "peak",
    )
    chosen: list[int] = []
    for index in order:
        if kind == "dip" and points[index].start_ms < 15_000:
            continue
        if any(abs(index - other) < min_gap_bins for other in chosen):
            continue
        chosen.append(index)
        if len(chosen) == limit:
            break
    def inside(lift: float) -> bool:
        return lift > 0 if kind == "peak" else lift < 0

    moments: list[CurveMoment] = []
    for index in sorted(chosen):
        if not inside(points[index].lift):
            continue
        # Grow the moment over neighbours on the same side of the typical drop-off.
        lo = hi = index
        floor_ms = 15_000 if kind == "dip" else 0
        while (
            lo > 0
            and index - lo < 3
            and inside(points[lo - 1].lift)
            and points[lo - 1].start_ms >= floor_ms
        ):
            lo -= 1
        while hi < count - 1 and hi - index < 3 and inside(points[hi + 1].lift):
            hi += 1
        point = points[index]
        moments.append(
            CurveMoment(
                kind=kind,
                start_ms=points[lo].start_ms,
                end_ms=points[hi].end_ms,
                value=point.value,
                drivers=point.drivers_up if kind == "peak" else point.drivers_down,
            )
        )
    return moments


def build_curve(
    model: InterestModel,
    *,
    words: Sequence[TimedWord],
    duration_ms: int,
    signal_rows: Sequence[dict[str, float]] | None,
) -> Curve:
    """Predict the per-bin curve, scaled to [0, 1] within this video."""
    transcript_rows = transcript_features(words, duration_ms)
    rows = assemble(transcript_rows, signal_rows)
    head = model.full if signal_rows is not None else model.transcript_only
    smoothed = _smooth([head.predict(row) for row in rows])
    expected = _smooth([model.position.predict(row) for row in rows])
    # One scale for both lines, so the gap between them reads directly.
    both = smoothed + expected
    lo, hi = (min(both), max(both)) if both else (0.0, 0.0)
    span = hi - lo

    def scale(value: float) -> float:
        return (value - lo) / span if span > 1e-9 else 0.5

    points: list[CurvePoint] = []
    for index, row in enumerate(rows):
        start = index * BIN_MS
        value = scale(smoothed[index])
        signals = {
            "wpm": round(row["wpm"] * 240, 1),
            "speechRatio": round(row["speech_ratio"], 3),
            "pauseMs": int(row["pause_max"] * BIN_MS),
            "novelty": round(row["novelty_rate"], 3),
        }
        if signal_rows is not None:
            signals.update({name: round(row[name] * 4 + 1, 2) for name in SIGNAL_NAMES})
        points.append(
            CurvePoint(
                start_ms=start,
                end_ms=min(duration_ms, start + BIN_MS),
                value=round(value, 4),
                baseline=round(scale(expected[index]), 4),
                lift=round(smoothed[index] - expected[index], 4),
                drivers_up=_drivers(head, row, positive=True),
                drivers_down=_drivers(head, row, positive=False),
                signals=signals,
            )
        )
    # Without the Gemini signals the deviations from the typical drop-off did not beat
    # chance on held-out creators (evals/interest/README.md), so no moments are marked.
    with_signals = signal_rows is not None
    return Curve(
        points=points,
        peaks=_moments(points, kind="peak") if with_signals else [],
        dips=_moments(points, kind="dip") if with_signals else [],
        feature_source="transcript+gemini" if signal_rows is not None else "transcript",
    )


__all__ = [
    "BIN_MS",
    "FEATURE_VERSION",
    "SIGNAL_NAMES",
    "SIGNAL_PROMPT_VERSION",
    "Curve",
    "CurveMoment",
    "CurvePoint",
    "InterestModel",
    "LinearHead",
    "POSITION_FEATURES",
    "SignalResult",
    "TimedWord",
    "assemble",
    "bin_texts",
    "build_curve",
    "feature_names",
    "load_model",
    "score_windows",
    "transcript_features",
    "words_from_segments",
]
