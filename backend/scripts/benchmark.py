"""Measure real cached creator retrieval, local media probes, and exported script bytes.

Offline by default. --embed-queries permits at most --max-calls embedding requests;
successful vectors are cached locally. No Firestore/Storage writes or generation jobs.
"""

import argparse
import gzip
import hashlib
import json
import platform
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from statistics import median
from typing import Any
from urllib.parse import urlsplit

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings
from app.providers.embeddings import GeminiEmbeddingProvider
from app.services.creator_import_service import prepare_import
from app.services.creator_library_service import _VERSION, _dot, build_passages, project_vectors
from app.services.creator_preset_service import prepared_source, validate_vectors
from app.services.video_tools import probe_duration_ms, probe_video_metadata, probe_video_size

ROOT = Path(__file__).resolve().parents[2]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def timing(samples: list[float]) -> dict[str, Any]:
    return {
        "n": len(samples),
        "median_ms": round(median(samples), 4),
        "p95_ms": round(float(np.percentile(samples, 95)), 4),
        "samples_ms": [round(s, 4) for s in samples],
    }


def elapsed(call: Any) -> tuple[Any, float]:
    start = time.perf_counter()
    result = call()
    return result, (time.perf_counter() - start) * 1000


def retrieval(args: argparse.Namespace) -> dict[str, Any]:
    settings = Settings(_env_file=None)
    prepared = prepare_import(args.corpus)
    passages, omitted = build_passages(prepared_source(prepared), settings)
    vectors_path = args.corpus / "embeddings.json"
    vectors = validate_vectors(json.loads(vectors_path.read_text()), prepared, settings)
    labels = json.loads(args.cases.read_text())
    if labels["corpus"] != prepared.manifest.bundleId:
        raise ValueError("Cases belong to a different creator corpus")
    cache = json.loads(args.query_cache.read_text()) if args.query_cache.exists() else {}
    provider = GeminiEmbeddingProvider(settings)
    calls = 0
    results = []
    for case in labels["cases"]:
        candidates = [p for p in passages if p.node.modality == case["modality"]]
        if not set(case["relevant_items"]).issubset({p.node.itemId for p in candidates}):
            raise ValueError(f"Missing relevant source for {case['id']}")
        prompt = f"task: search result | query: {case['query'][:1000]}"
        key = hashlib.sha256(
            json.dumps(
                [settings.model_embedding, settings.embedding_dimensions, _VERSION, prompt]
            ).encode()
        ).hexdigest()
        cached = cache.get(key)
        if cached is None and args.embed_queries:
            if calls >= args.max_calls:
                raise ValueError(
                    "Embedding-call cap reached; rerun offline or raise the explicit cap"
                )
            calls += 1
            vector, latency = elapsed(partial(provider.embed, prompt))
            cached = {
                "vector": vector,
                "latency_ms": round(latency, 3),
                "created_at": datetime.now(UTC).isoformat(),
            }
            cache[key] = cached
            args.query_cache.parent.mkdir(parents=True, exist_ok=True)
            args.query_cache.write_text(json.dumps(cache, separators=(",", ":")))
            print(f"Embedded {case['id']} ({calls}/{args.max_calls})", flush=True)
        if cached is None:
            raise ValueError("Query cache incomplete. Use --embed-queries for a bounded live run.")
        vector = cached["vector"]
        if len(vector) != settings.embedding_dimensions or not all(map(np.isfinite, vector)):
            raise ValueError("Invalid cached query vector")
        if abs(sum(x * x for x in vector) - 1) > 0.001:
            raise ValueError("Cached query vector is not normalized")
        semantic = sorted(
            [(_dot(vector, vectors[p.node.id]), p) for p in candidates],
            key=lambda entry: (-entry[0], entry[1].node.id),
        )
        words = set(re.findall(r"\w+", case["query"].casefold()))
        lexical = []
        for p in candidates:
            terms = set(re.findall(r"\w+", (p.node.title + " " + p.node.excerpt).casefold()))
            score = len(words & terms) / max(1, len(words))
            if score > 0:
                lexical.append((score, p))
        lexical.sort(key=lambda entry: (-entry[0], entry[1].node.id))
        methods = {}
        for method, ranked in [("semantic", semantic), ("lexical", lexical)]:
            # Preserve the application's passage-level top-eight retrieval cutoff.
            top = ranked[:8]
            relevance = set(case["relevant_items"])
            first = next((i + 1 for i, (_, p) in enumerate(top) if p.node.itemId in relevance), 0)
            methods[method] = {
                "hit_at_1": int(first == 1),
                "hit_at_3": int(0 < first <= 3),
                "hit_at_8": int(first > 0),
                "reciprocal_rank_at_8": 1 / first if first else 0,
                "ranked_item_ids": [p.node.itemId for _, p in top],
                "ranked_node_ids": [p.node.id for _, p in top],
                "scores": [round(score, 5) for score, _ in top],
            }
        results.append({**case, "embedding_latency_ms": cached["latency_ms"], **methods})
    groups = {}
    for group, subset in [
        ("all", results),
        ("text_en", [r for r in results if r["modality"] == "text" and r["language"] == "en"]),
        ("text_hi", [r for r in results if r["modality"] == "text" and r["language"] == "hi"]),
        ("text_to_image", [r for r in results if r["modality"] == "image"]),
    ]:
        groups[group] = {
            "n": len(subset),
            **{
                method: {
                    metric: round(sum(r[method][metric] for r in subset) / len(subset), 6)
                    for metric in ["hit_at_1", "hit_at_3", "hit_at_8", "reciprocal_rank_at_8"]
                }
                for method in ["semantic", "lexical"]
            },
        }
    # Measure only local scoring/PCA; exclude provider, network, and Firestore latency.
    sample_vector = next(iter(cache.values()))["vector"]
    scoring = lambda: sorted(  # noqa: E731
        [(_dot(sample_vector, vectors[p.node.id]), p.node.id) for p in passages], reverse=True
    )
    scoring()
    score_samples = [elapsed(scoring)[1] for _ in range(args.iterations)]
    rows = [vectors[p.node.id] for p in passages]
    project_vectors(rows)
    pca_samples = [elapsed(lambda: project_vectors(rows))[1] for _ in range(7)]
    norms = [sum(x * x for x in v) ** 0.5 for v in rows]
    items = prepared.manifest.items
    return {
        "model": settings.model_embedding,
        "location": settings.vertex_location,
        "dimensions": settings.embedding_dimensions,
        "prompt_version": _VERSION,
        "manifest_sha256": digest(args.corpus / "manifest.json"),
        "vectors_sha256": digest(vectors_path),
        "cases_sha256": digest(args.cases),
        "query_cache_sha256": digest(args.query_cache),
        "label_type": labels["label_type"],
        "item_count": len(items),
        "items_by_kind": dict(Counter(i.kind for i in items)),
        "items_by_language": dict(Counter(i.language for i in items)),
        "nodes_by_modality": dict(Counter(p.node.modality for p in passages)),
        "indexed_nodes": len(vectors),
        "omitted_passages": omitted,
        "max_unit_norm_error": max(abs(n - 1) for n in norms),
        "vector_float32_bytes": len(vectors) * settings.embedding_dimensions * 4,
        "new_embedding_calls": calls,
        "groups": groups,
        "local_scoring": timing(score_samples),
        "local_pca": timing(pca_samples),
        "query_provider_latency": timing([r["embedding_latency_ms"] for r in results]),
        "cases": results,
    }


def media(args: argparse.Namespace) -> list[dict[str, Any]]:
    rows = []
    for path in args.media:
        combined = partial(probe_video_metadata, str(path))

        def separate(source: str = str(path)) -> Any:
            size = probe_video_size(source)
            duration = probe_duration_ms(source)
            return (*size, duration) if size else None

        combined()
        separate()
        old, new = [], []
        old_result = new_result = None
        for i in range(7):
            # Alternate order to reduce warm-cache/order bias.
            order = (
                [(separate, old), (combined, new)]
                if i % 2 == 0
                else [(combined, new), (separate, old)]
            )
            for call, samples in order:
                result, ms = elapsed(call)
                if result is None:
                    raise ValueError(f"Could not probe {path}")
                if call is separate:
                    old_result = result
                else:
                    new_result = result
                samples.append(ms)
        if old_result != new_result:
            raise ValueError(f"Metadata mismatch for {path}")
        rows.append(
            {
                "file": path.name,
                "sha256": digest(path),
                "bytes": path.stat().st_size,
                "metadata": new_result,
                "two_probes": timing(old),
                "one_probe": timing(new),
                "median_reduction_fraction": round(1 - median(new) / median(old), 6),
            }
        )
    return rows


def bundles(export: Path) -> list[dict[str, Any]]:
    rows = []
    for route in [
        "index.html",
        "dashboard.html",
        "projects.html",
        "projects/view.html",
        "onboarding.html",
    ]:
        html = export / route
        if not html.exists():
            continue
        scripts = set(re.findall(r'<script\b[^>]*\bsrc="([^"]+)"', html.read_text()))
        paths = [export / urlsplit(url).path.lstrip("/") for url in scripts]
        if any(not p.is_relative_to(export) or not p.exists() for p in paths):
            raise ValueError(f"Missing or unsafe exported script for {route}")
        rows.append(
            {
                "route_html": route,
                "script_count": len(paths),
                "raw_bytes": sum(p.stat().st_size for p in paths),
                "gzip_bytes": sum(len(gzip.compress(p.read_bytes(), mtime=0)) for p in paths),
                "scope": "scripts referenced by route HTML; excludes subsequently loaded chunks",
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--cases", type=Path, default=ROOT / "evals/creator-retrieval.json")
    parser.add_argument("--query-cache", type=Path, default=ROOT / ".tmp/evals/query-vectors.json")
    parser.add_argument("--embed-queries", action="store_true")
    parser.add_argument("--max-calls", type=int, choices=range(1, 21), default=20)
    parser.add_argument("--iterations", type=int, choices=range(20, 201), default=100)
    parser.add_argument("--media", type=Path, nargs="*", default=[])
    parser.add_argument("--web-export", type=Path, default=ROOT / "web/out")
    parser.add_argument("--web-bundler", choices=["turbopack", "webpack"], default="turbopack")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "git_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "working_tree_dirty": bool(
            subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)
        ),
        "implementation_sha256": {
            name: digest(ROOT / name)
            for name in [
                "backend/scripts/benchmark.py",
                "backend/app/config.py",
                "backend/app/providers/embeddings.py",
                "backend/app/services/creator_import_service.py",
                "backend/app/services/creator_library_service.py",
                "backend/app/services/creator_preset_service.py",
                "backend/app/services/video_tools.py",
            ]
        },
        "machine": {
            "os": platform.system(),
            "architecture": platform.machine(),
            "python": platform.python_version(),
        },
        "retrieval": retrieval(args),
        "media": media(args),
        "web_initial_scripts": bundles(args.web_export),
        "web_bundler": args.web_bundler,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {"output": str(args.output), "retrieval": report["retrieval"]["groups"]}, indent=2
        )
    )


if __name__ == "__main__":
    main()
