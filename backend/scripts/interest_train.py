"""Train and evaluate the predicted-interest model on public Most Replayed curves.

Two public sources, both labelled with YouTube's "Most Replayed" graph:

- **Content Behavior Corpus** (Adobe "behavior-in-the-wild", MIT): ~24.6k short videos
  (median 61 s) from brand channels, with Whisper transcripts and replay markers. Download
  the two parquet files into `evals/interest/raw/cbc/` (see `evals/interest/README.md`).
- **Creator set**: long-form creator videos gathered by `interest_collect.py`
  (gitignored `evals/interest/raw/meta|subs`).

Evaluation trains on corpus channels only, then tests on held-out corpus channels and on
every creator video, which the evaluated model never sees. The bundled model is refit on
everything afterwards; the report states the held-out numbers. Features come from the
production code in `app/services/interest.py`, so training and inference cannot drift.

    # 1. Gemini signals for a bounded sample (cached under raw/signals/)
    uv run --project backend --with pyarrow \
        python backend/scripts/interest_train.py signals --max-calls 2500
    # 2. fit, evaluate, write the model and the report
    uv run --project backend --with pyarrow python backend/scripts/interest_train.py train
"""

import argparse
import asyncio
import hashlib
import json
import math
import random
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings
from app.providers.llm import LlmProvider
from app.services.interest import (
    BIN_MS,
    FEATURE_VERSION,
    MODEL_PATH,
    POSITION_FEATURES,
    SIGNAL_NAMES,
    SIGNAL_PROMPT_VERSION,
    TRANSCRIPT_FEATURES,
    TimedWord,
    assemble,
    bin_texts,
    feature_names,
    score_windows,
    transcript_features,
    words_from_segments,
)
from app.services.transcript_service import build_segments

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "evals" / "interest" / "raw"
CBC = RAW / "cbc"
SIGNALS_DIR = RAW / "signals"
RESULTS = ROOT / "evals" / "interest" / "results.json"
VIDEOS_CSV = ROOT / "evals" / "interest" / "videos.csv"

MODEL_VERSION = "interest-v1"
TEST_FRACTION = 0.3
ALPHAS = (0.1, 1.0, 10.0, 100.0, 1000.0)

#: Corpus filter: speech-led clips long enough to have a shape.
CBC_MIN_SECONDS = 30
CBC_MIN_WPM = 80
CBC_MIN_MARKERS = 10


# ------------------------------------------------------------------ data


def as_inference_words(words: list[TimedWord]) -> list[TimedWord]:
    """Production stores segment timings only, so rebuild segments with the production
    segmenter and spread words over them exactly as inference does."""
    segments = build_segments(
        [{"word": w.text, "startMs": w.start_ms, "endMs": w.end_ms} for w in words]
    )
    return words_from_segments(
        [(int(s["startMs"]), int(s["endMs"]), str(s["text"])) for s in segments]
    )


def parse_lines(path: Path) -> list[TimedWord]:
    """Words spread over timed caption lines (transcript API or local Whisper).

    Auto-caption lines overlap (each stays on screen into the next), so a line ends where
    the next one starts.
    """
    lines = json.loads(path.read_text(encoding="utf-8")).get("lines") or []
    spans: list[tuple[int, int, str]] = []
    for index, line in enumerate(lines):
        start = int(float(line["start"]) * 1000)
        end = start + int(float(line.get("duration") or 0) * 1000)
        if index + 1 < len(lines):
            end = min(end, int(float(lines[index + 1]["start"]) * 1000))
        text = " ".join(str(line.get("text") or "").split())
        if text and end > start:
            spans.append((start, end, text))
    return words_from_segments(spans)


def labels_at_bins(markers: list[tuple[float, float, float]], duration_ms: int) -> list[float]:
    """Replay value at each bin centre, by linear interpolation between marker centres."""
    centres = [(start + end) / 2 * 1000 for start, end, _ in markers]
    values = [value for _, _, value in markers]
    count = math.ceil(duration_ms / BIN_MS)
    xs = [min(duration_ms, index * BIN_MS + BIN_MS / 2) for index in range(count)]
    return [float(v) for v in np.interp(xs, centres, values)]


def load_creator() -> list[dict[str, Any]]:
    videos = []
    for path in sorted((RAW / "meta").glob("*.json")):
        meta = json.loads(path.read_text(encoding="utf-8"))
        lines = RAW / "subs" / f"{meta['id']}.lines.json"
        if not lines.exists() or not meta.get("heatmap"):
            continue
        words = as_inference_words(parse_lines(lines))
        if len(words) < 100:
            continue
        videos.append(
            {
                "id": meta["id"],
                "source": "creator",
                "channel_id": meta["channel_id"],
                "language": meta.get("language") or "",
                "title": meta.get("title") or "",
                "words": words,
                "duration_ms": int(meta["duration"] * 1000),
                "markers": [
                    (m["start_time"], m["end_time"], float(m["value"])) for m in meta["heatmap"]
                ],
            }
        )
    return videos


def load_cbc() -> list[dict[str, Any]]:
    paths = [CBC / name for name in ("train.parquet", "test.parquet") if (CBC / name).exists()]
    if not paths:
        return []
    import pyarrow.parquet as pq

    videos = []
    for path in paths:
        table = pq.read_table(
            path, columns=["video_id", "asr_raw", "replay_graphs", "channel_data", "metadata"]
        )
        for row in table.to_pylist():
            markers = [
                (float(m["start"]), float(m["end"]), float(m["replay_score"]))
                for m in ((row.get("replay_graphs") or {}).get("markers") or [])
                if m.get("replay_score") is not None
            ]
            if len(markers) < CBC_MIN_MARKERS:
                continue
            duration_s = max(end for _, end, _ in markers)
            raw_words = [
                TimedWord(
                    str(word["text"]).strip(),
                    int(float(word["start"]) * 1000),
                    int(float(word["end"]) * 1000),
                )
                for segment in row.get("asr_raw") or []
                for word in segment.get("words") or []
                if str(word.get("text") or "").strip()
            ]
            if duration_s < CBC_MIN_SECONDS or len(raw_words) / duration_s * 60 < CBC_MIN_WPM:
                continue
            channel = (row.get("channel_data") or {}).get("channel_id") or row["video_id"]
            videos.append(
                {
                    "id": row["video_id"],
                    "source": "cbc",
                    "channel_id": channel,
                    "language": "",
                    "title": ((row.get("metadata") or {}).get("title") or "")[:200],
                    "words": as_inference_words(sorted(raw_words, key=lambda w: w.start_ms)),
                    "duration_ms": int(duration_s * 1000),
                    "markers": markers,
                }
            )
    return videos


def is_test_channel(channel_id: str) -> bool:
    return int(hashlib.sha256(channel_id.encode()).hexdigest(), 16) % 1000 < TEST_FRACTION * 1000


def signal_cache(video_id: str, model: str) -> Path:
    tag = hashlib.sha256(f"{model}|{SIGNAL_PROMPT_VERSION}".encode()).hexdigest()[:10]
    return SIGNALS_DIR / f"{video_id}.{tag}.json"


def signal_sample(
    videos: list[dict[str, Any]], *, cbc_train: int, cbc_test: int
) -> list[dict[str, Any]]:
    """Every creator video plus a seeded, channel-spread sample of the corpus."""
    creator = [v for v in videos if v["source"] == "creator"]
    rng = random.Random(23)
    corpus = [v for v in videos if v["source"] == "cbc"]
    rng.shuffle(corpus)
    train = [v for v in corpus if not is_test_channel(v["channel_id"])][:cbc_train]
    test = [v for v in corpus if is_test_channel(v["channel_id"])][:cbc_test]
    return creator + train + test


# ------------------------------------------------------------------ signals


async def compute_signals(args: argparse.Namespace) -> None:
    settings = Settings()
    model = settings.model_interest_signals
    llm = LlmProvider(settings)
    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    corpus = load_cbc() if args.cbc_train or args.cbc_test else []
    videos = signal_sample(
        load_creator() + corpus, cbc_train=args.cbc_train, cbc_test=args.cbc_test
    )
    pending = [v for v in videos if not signal_cache(v["id"], model).exists()]
    print(f"{len(videos)} sampled videos, {len(pending)} need signals ({model})", flush=True)
    budget = {"calls": args.max_calls, "input": 0, "output": 0, "done": 0, "failed": 0}
    semaphore = asyncio.Semaphore(args.concurrency)

    async def one(video: dict[str, Any]) -> None:
        texts = bin_texts(video["words"], video["duration_ms"])
        calls = max(1, math.ceil(len(texts) / 120))
        async with semaphore:
            if budget["calls"] < calls:
                return
            budget["calls"] -= calls
            try:
                result = await score_windows(
                    llm,
                    model=model,
                    texts=texts,
                    title=video["title"],
                    language=video["language"],
                )
            except Exception as exc:  # noqa: BLE001
                budget["failed"] += 1
                print(f"signals failed for {video['id']}: {exc}", flush=True)
                return
        budget["input"] += result.usage.input_tokens
        budget["output"] += result.usage.output_tokens
        if result.rows is None:
            budget["failed"] += 1
            return
        signal_cache(video["id"], model).write_text(json.dumps(result.rows), encoding="utf-8")
        budget["done"] += 1
        if budget["done"] % 100 == 0:
            print(f"{budget['done']} done", flush=True)

    await asyncio.gather(*(one(video) for video in pending))
    cost = (
        budget["input"] / 1e6 * settings.llm_input_price_per_mtok
        + budget["output"] / 1e6 * settings.llm_output_price_per_mtok
    )
    print(
        json.dumps(
            {
                "done": budget["done"],
                "failed": budget["failed"],
                "callsLeft": budget["calls"],
                "inputTokens": budget["input"],
                "outputTokens": budget["output"],
                "estimatedCostUsd": round(cost, 4),
            },
            indent=2,
        )
    )


# ------------------------------------------------------------------ fitting


def features_of(item: dict[str, Any], names: tuple[str, ...], *, plain: bool) -> np.ndarray:
    """The item's feature matrix for `names`, cached: the same matrices are reused across
    many cross-validation fits."""
    cache = item.setdefault("_x", {})
    key = (names, plain)
    if key not in cache:
        rows = item["rows_plain"] if plain else item["rows"]
        cache[key] = np.array([[row.get(name, 0.0) for name in names] for row in rows])
    return cache[key]


def zscore(values: list[float]) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    std = array.std()
    return (array - array.mean()) / std if std > 1e-9 else array * 0


@dataclass(frozen=True)
class Spec:
    """One model to fit: its features, whether it reads Gemini signals."""

    names: tuple[str, ...]
    signals: bool


def fit_ridge(spec: Spec, items: list[dict[str, Any]], alpha: float) -> dict[str, Any]:
    """Weighted ridge on standardised features. `item["w"]` weights every bin of a video,
    so a few long creator videos are not drowned out by thousands of short clips."""
    xs = [features_of(item, spec.names, plain=not spec.signals) for item in items]
    x = np.vstack(xs)
    y = np.concatenate([np.asarray(item["y"]) for item in items])
    w = np.concatenate([np.full(len(item["y"]), item.get("w", 1.0)) for item in items])
    w = w / w.mean()
    mean = np.average(x, axis=0, weights=w)
    std = np.sqrt(np.average((x - mean) ** 2, axis=0, weights=w))
    std[std < 1e-9] = 1.0
    z = (x - mean) / std
    y_mean = float(np.average(y, weights=w))
    root = np.sqrt(w)[:, None]
    zw = z * root
    coef = np.linalg.solve(
        zw.T @ zw + alpha * np.eye(z.shape[1]), zw.T @ ((y - y_mean) * root[:, 0])
    )
    return {
        "features": list(spec.names),
        "mean": mean.tolist(),
        "std": std.tolist(),
        "weights": coef.tolist(),
        "intercept": y_mean,
    }


def predict(head: dict[str, Any], x: np.ndarray) -> np.ndarray:
    scaled = (x - np.array(head["mean"])) / np.array(head["std"])
    return head["intercept"] + scaled @ np.array(head["weights"])


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 3:
        return float("nan")
    ra = np.argsort(np.argsort(a))
    rb = np.argsort(np.argsort(b))
    if ra.std() == 0 or rb.std() == 0:
        return 0.0
    return float(np.corrcoef(ra, rb)[0, 1])


def top_overlap(pred: np.ndarray, true: np.ndarray, *, top: bool) -> float:
    """Share of the predicted top (bottom) 10% of bins that are in the true top (bottom) 25%.

    Bottoms skip the first 15 seconds, as the product's dips do. Chance is 0.25.
    """
    n = len(pred)
    skip = 0 if top else 3
    candidates = list(range(skip, n))
    if not candidates:
        return float("nan")
    k = max(1, len(candidates) // 10)
    quarter = max(1, len(candidates) // 4)
    by_pred = sorted(candidates, key=lambda i: pred[i], reverse=top)
    by_true = sorted(candidates, key=lambda i: true[i], reverse=top)
    chosen = set(by_pred[:k])
    return len(chosen & set(by_true[:quarter])) / len(chosen)


POSITION = Spec(tuple(POSITION_FEATURES), signals=False)
TRANSCRIPT = Spec(tuple(feature_names(with_signals=False)), signals=False)
FULL = Spec(tuple(feature_names(with_signals=True)), signals=True)


def video_metrics(
    head: dict[str, Any], spec: Spec, item: dict[str, Any], position: dict[str, Any] | None
) -> dict[str, float]:
    pred = predict(head, features_of(item, spec.names, plain=not spec.signals))
    true = np.asarray(item["y"])
    out = {
        "spearman": spearman(pred, true),
        "peak": top_overlap(pred, true, top=True),
        "dip": top_overlap(pred, true, top=False),
    }
    if position is not None:
        expected = predict(position, features_of(item, POSITION.names, plain=True))
        lift_pred, lift_true = pred - expected, true - expected
        out.update(
            {
                "lift": spearman(lift_pred, lift_true),
                "liftPeak": top_overlap(lift_pred, lift_true, top=True),
                "liftDip": top_overlap(lift_pred, lift_true, top=False),
            }
        )
    return out


def summarize(per_video: list[dict[str, float]]) -> dict[str, Any]:
    if not per_video:
        return {"videos": 0}

    def mean(key: str) -> float:
        values = [v[key] for v in per_video if key in v and not math.isnan(v[key])]
        return round(float(np.mean(values)), 4) if values else float("nan")

    result: dict[str, Any] = {
        "videos": len(per_video),
        "spearman": mean("spearman"),
        "peakPrecision": mean("peak"),
        "dipPrecision": mean("dip"),
    }
    if "lift" in per_video[0]:
        result.update(
            {
                "liftSpearman": mean("lift"),
                "liftPeakPrecision": mean("liftPeak"),
                "liftDipPrecision": mean("liftDip"),
                "liftSpearman95": bootstrap_mean([v["lift"] for v in per_video]),
            }
        )
    return result


def choose_alpha(spec: Spec, items: list[dict[str, Any]], *, folds: int = 5) -> float:
    """Grouped inner CV over the items' channels; the alpha with the best mean ρ."""
    channels = sorted({item["channel_id"] for item in items})
    random.Random(11).shuffle(channels)
    groups = [set(channels[i::folds]) for i in range(folds)]
    best_alpha, best = ALPHAS[0], -2.0
    for alpha in ALPHAS:
        scores: list[float] = []
        for group in groups:
            fit_items = [item for item in items if item["channel_id"] not in group]
            held = [item for item in items if item["channel_id"] in group]
            if not fit_items or not held:
                continue
            head = fit_ridge(spec, fit_items, alpha)
            scores.extend(video_metrics(head, spec, item, None)["spearman"] for item in held)
        score = float(np.nanmean(scores)) if scores else -2.0
        if score > best:
            best_alpha, best = alpha, score
    return best_alpha


def bootstrap_mean(values: list[float], *, rounds: int = 2000) -> dict[str, float]:
    """95% bootstrap CI over videos for the mean."""
    array = np.asarray([v for v in values if not math.isnan(v)])
    if len(array) == 0:
        return {"mean": float("nan"), "low": float("nan"), "high": float("nan")}
    rng = np.random.default_rng(5)
    means = [float(rng.choice(array, size=len(array), replace=True).mean()) for _ in range(rounds)]
    return {
        "mean": round(float(array.mean()), 4),
        "low": round(float(np.percentile(means, 2.5)), 4),
        "high": round(float(np.percentile(means, 97.5)), 4),
    }


@dataclass(frozen=True)
class Recipe:
    """A way to train: which data, which content model."""

    name: str
    spec: Spec
    #: "creator": creator videos only; "mixed": corpus plus creator, balanced so both
    #: sources carry equal total weight; "corpus": corpus only.
    data: str


RECIPES = (
    Recipe("creator/transcript", TRANSCRIPT, "creator"),
    Recipe("mixed/transcript", TRANSCRIPT, "mixed"),
    Recipe("corpus/transcript", TRANSCRIPT, "corpus"),
    Recipe("creator/full", FULL, "creator"),
    Recipe("mixed/full", FULL, "mixed"),
)


def training_items(
    recipe: Recipe, creator: list[dict[str, Any]], corpus: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    def usable(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [i for i in items if i["has_signals"]] if recipe.spec.signals else items

    creator_items = usable(creator) if recipe.data in ("creator", "mixed") else []
    corpus_items = usable(corpus) if recipe.data in ("corpus", "mixed") else []
    if recipe.data == "mixed" and creator_items and corpus_items:
        creator_bins = sum(len(i["y"]) for i in creator_items)
        corpus_bins = sum(len(i["y"]) for i in corpus_items)
        corpus_items = [{**i, "w": creator_bins / corpus_bins} for i in corpus_items]
    return [{**i, "w": i.get("w", 1.0)} for i in creator_items] + corpus_items


def creator_cv(
    recipe: Recipe,
    creator: list[dict[str, Any]],
    corpus: list[dict[str, Any]],
    *,
    alpha: float | None,
    folds: int = 5,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Grouped CV over creator channels: train on the recipe's data minus the held
    channels, test on the held creator videos. Returns (recipe metrics, position
    baseline metrics from the same training data)."""
    held_pool = [i for i in creator if i["has_signals"]] if recipe.spec.signals else creator
    channels = sorted({item["channel_id"] for item in held_pool})
    random.Random(17).shuffle(channels)
    groups = [set(channels[i::folds]) for i in range(folds)]
    per_video: list[dict[str, float]] = []
    per_video_position: list[dict[str, float]] = []
    for group in groups:
        held = [item for item in held_pool if item["channel_id"] in group]
        rest = [item for item in creator if item["channel_id"] not in group]
        items = training_items(recipe, rest, corpus)
        if not held or not items:
            continue
        chosen_alpha = alpha if alpha is not None else choose_alpha(recipe.spec, items)
        head = fit_ridge(recipe.spec, items, chosen_alpha)
        position_items = training_items(Recipe("p", POSITION, recipe.data), rest, corpus)
        position = fit_ridge(POSITION, position_items, 10.0)
        for item in held:
            per_video.append(video_metrics(head, recipe.spec, item, position))
            per_video_position.append(video_metrics(position, POSITION, item, None))
    return summarize(per_video), summarize(per_video_position)


def train(args: argparse.Namespace) -> None:
    settings = Settings()
    model = settings.model_interest_signals
    videos = load_creator() + ([] if args.no_corpus else load_cbc())
    data: list[dict[str, Any]] = []
    for video in videos:
        cache = signal_cache(video["id"], model)
        signals = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else None
        transcript_rows = transcript_features(video["words"], video["duration_ms"])
        if signals is not None and len(signals) != len(transcript_rows):
            signals = None
        labels = labels_at_bins(video["markers"], video["duration_ms"])
        if len(labels) != len(transcript_rows) or len(labels) < 4:
            continue
        data.append(
            {
                "id": video["id"],
                "source": video["source"],
                "channel_id": video["channel_id"],
                "language": video["language"],
                "duration_s": video["duration_ms"] / 1000,
                "has_signals": signals is not None,
                "rows": assemble(transcript_rows, signals),
                "rows_plain": assemble(transcript_rows, None),
                "y": zscore(labels).tolist(),
            }
        )
    corpus = [d for d in data if d["source"] == "cbc"]
    creator = [d for d in data if d["source"] == "creator"]
    print(
        f"corpus {len(corpus)} ({sum(d['has_signals'] for d in corpus)} with signals), "
        f"creator {len(creator)} ({sum(d['has_signals'] for d in creator)} with signals)",
        flush=True,
    )

    # Corpus alphas are fixed once on the corpus itself (it is never a test set for the
    # creator domain), so the creator CV does not have to refit them per fold.
    corpus_alpha = {
        spec.names: choose_alpha(
            spec, [i for i in corpus if i["has_signals"] or not spec.signals], folds=3
        )
        for spec in (TRANSCRIPT, FULL)
        if any(i["has_signals"] or not spec.signals for i in corpus)
    }

    report: dict[str, Any] = {}
    for recipe in RECIPES:
        needs_corpus = recipe.data in ("mixed", "corpus")
        pool = [i for i in creator if i["has_signals"]] if recipe.spec.signals else creator
        corpus_pool = [i for i in corpus if i["has_signals"] or not recipe.spec.signals]
        if len(pool) < 10 or (needs_corpus and len(corpus_pool) < 50):
            continue
        alpha = corpus_alpha.get(recipe.spec.names) if needs_corpus else None
        metrics, position = creator_cv(recipe, creator, corpus, alpha=alpha)
        report[recipe.name] = {**metrics, "positionBaseline": position}
        print(
            f"{recipe.name:<20} n={metrics['videos']:<4} ρ={metrics['spearman']:.3f} "
            f"(position {position['spearman']:.3f}) lift ρ={metrics['liftSpearman']:.3f} "
            f"[{metrics['liftSpearman95']['low']:.3f}, {metrics['liftSpearman95']['high']:.3f}] "
            f"liftPeak={metrics['liftPeakPrecision']:.3f} "
            f"liftDip={metrics['liftDipPrecision']:.3f}",
            flush=True,
        )

    # Short-form check: corpus held-out channels, corpus-trained transcript model.
    corpus_report: dict[str, Any] = {}
    if corpus:
        corpus_train = [i for i in corpus if not is_test_channel(i["channel_id"])]
        corpus_test = [i for i in corpus if is_test_channel(i["channel_id"])]
        alpha = corpus_alpha.get(TRANSCRIPT.names, 10.0)
        head = fit_ridge(TRANSCRIPT, corpus_train, alpha)
        position = fit_ridge(POSITION, corpus_train, 10.0)
        corpus_report = {
            "transcript": summarize(
                [video_metrics(head, TRANSCRIPT, i, position) for i in corpus_test]
            ),
            "position": summarize(
                [video_metrics(position, POSITION, i, None) for i in corpus_test]
            ),
        }
        print(
            f"corpus held-out (short-form) n={len(corpus_test)} "
            f"ρ={corpus_report['transcript']['spearman']:.3f} "
            f"(position {corpus_report['position']['spearman']:.3f}) "
            f"lift ρ={corpus_report['transcript']['liftSpearman']:.3f}",
            flush=True,
        )

    # Ship the recipe with the best cross-validated lift on creator channels, and the best
    # transcript-only recipe as the fallback when the Gemini pass is unavailable.
    def best(names: list[str]) -> str:
        return max(names, key=lambda n: report[n]["liftSpearman"])

    transcript_names = [r.name for r in RECIPES if not r.spec.signals and r.name in report]
    full_names = [r.name for r in RECIPES if r.spec.signals and r.name in report]
    fallback = best(transcript_names)
    primary_name = best(transcript_names + full_names)
    primary = next(r for r in RECIPES if r.name == primary_name)
    fallback_recipe = next(r for r in RECIPES if r.name == fallback)
    print(f"primary: {primary_name}; transcript fallback: {fallback}", flush=True)

    def final_head(recipe: Recipe) -> dict[str, Any]:
        items = training_items(recipe, creator, corpus)
        alpha = (
            corpus_alpha.get(recipe.spec.names, 10.0)
            if recipe.data in ("mixed", "corpus")
            else choose_alpha(recipe.spec, items)
        )
        return fit_ridge(recipe.spec, items, alpha)

    final_fallback = final_head(fallback_recipe)
    final_full: dict[str, Any] = (
        final_head(primary)
        if primary.spec.signals
        else {
            "features": list(FULL.names),
            "mean": [0.0] * len(FULL.names),
            "std": [1.0] * len(FULL.names),
            "weights": [0.0] * len(FULL.names),
            "intercept": 0.0,
        }
    )
    final_position = fit_ridge(
        POSITION, training_items(Recipe("p", POSITION, primary.data), creator, corpus), 10.0
    )
    headline = report[primary_name]
    fallback_metrics = report[fallback]
    trained_at = datetime.now(UTC).isoformat(timespec="seconds")
    metrics = {
        "primaryHead": "full" if primary.spec.signals else "transcript_only",
        "recipe": primary_name,
        "fallbackRecipe": fallback,
        "label": "YouTube Most Replayed, normalised within each video",
        "split": "grouped cross-validation over creator channels",
        "videos": len(training_items(primary, creator, corpus)),
        "creatorVideos": sum(
            i["source"] == "creator" for i in training_items(primary, creator, corpus)
        ),
        "corpusVideos": sum(
            i["source"] == "cbc" for i in training_items(primary, creator, corpus)
        ),
        "channels": len({d["channel_id"] for d in creator}),
        "testVideos": headline["videos"],
        "heldOutSpearman": headline["spearman"],
        "positionBaselineSpearman": headline["positionBaseline"]["spearman"],
        "liftSpearman": headline["liftSpearman"],
        "liftConfidence95": headline["liftSpearman95"],
        "transcriptLiftSpearman": fallback_metrics["liftSpearman"],
        "transcriptFallbackSpearman": fallback_metrics["spearman"],
        "peakPrecision": headline["liftPeakPrecision"],
        "dipPrecision": headline["liftDipPrecision"],
        "randomPrecision": 0.25,
        "trainedAt": trained_at,
    }
    model_doc = {
        "version": MODEL_VERSION,
        "featureVersion": FEATURE_VERSION,
        "signalPromptVersion": SIGNAL_PROMPT_VERSION,
        "signalModel": model,
        "primaryHead": metrics["primaryHead"],
        "binMs": BIN_MS,
        "metrics": metrics,
        "heads": {
            "full": final_full,
            "transcript_only": final_fallback,
            "position": final_position,
        },
    }
    shipped: dict[str, Any] = final_full if primary.spec.signals else final_fallback
    weights = sorted(
        zip(shipped["features"], shipped["weights"], strict=True), key=lambda kv: -abs(kv[1])
    )
    results = {
        "generatedAt": trained_at,
        "modelVersion": MODEL_VERSION,
        "featureVersion": FEATURE_VERSION,
        "signalModel": model,
        "signalPromptVersion": SIGNAL_PROMPT_VERSION,
        "primary": primary_name,
        "fallback": fallback,
        "data": {
            "creator": {
                "videos": len(creator),
                "channels": len({d["channel_id"] for d in creator}),
                "signalled": sum(d["has_signals"] for d in creator),
                "languages": {
                    lang: sum(d["language"] == lang for d in creator)
                    for lang in sorted({d["language"] for d in creator})
                },
                "medianSeconds": (
                    round(float(np.median([d["duration_s"] for d in creator])), 1)
                    if creator
                    else None
                ),
            },
            "corpus": {
                "videos": len(corpus),
                "signalled": sum(d["has_signals"] for d in corpus),
                "channels": len({d["channel_id"] for d in corpus}),
                "medianSeconds": (
                    round(float(np.median([d["duration_s"] for d in corpus])), 1)
                    if corpus
                    else None
                ),
            },
            "binMs": BIN_MS,
        },
        "creatorCrossValidation": report,
        "corpusHeldOutShortForm": corpus_report,
        "topWeights": [{"feature": n, "weight": round(w, 4)} for n, w in weights[:15]],
        "transcriptFeatures": list(TRANSCRIPT_FEATURES),
        "signals": list(SIGNAL_NAMES),
    }
    if not args.dry_run:
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        MODEL_PATH.write_text(json.dumps(model_doc, indent=1), encoding="utf-8")
        RESULTS.parent.mkdir(parents=True, exist_ok=True)
        RESULTS.write_text(json.dumps(results, indent=1), encoding="utf-8")
        with VIDEOS_CSV.open("w", encoding="utf-8") as handle:
            handle.write("video_id,source,channel_id,has_signals\n")
            for item in creator + corpus:
                handle.write(
                    f"{item['id']},{item['source']},{item['channel_id']},"
                    f"{int(item['has_signals'])}\n"
                )
    print(json.dumps({"metrics": metrics}, indent=1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    phases = parser.add_subparsers(dest="phase", required=True)
    signals = phases.add_parser("signals", help="Rate bins with Gemini (bounded, cached).")
    signals.add_argument("--max-calls", type=int, default=2500, help="Hard cap on model calls.")
    signals.add_argument("--concurrency", type=int, default=6)
    signals.add_argument("--cbc-train", type=int, default=1500)
    signals.add_argument("--cbc-test", type=int, default=500)
    fit = phases.add_parser("train", help="Fit, evaluate and write the model.")
    fit.add_argument("--dry-run", action="store_true", help="Report only; keep the old model.")
    fit.add_argument("--no-corpus", action="store_true", help="Creator videos only.")
    args = parser.parse_args()
    if args.phase == "signals":
        asyncio.run(compute_signals(args))
    else:
        train(args)


if __name__ == "__main__":
    main()
