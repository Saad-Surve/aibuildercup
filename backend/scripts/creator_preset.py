"""Publish a pre-indexed public creator corpus to GCS; remove shared versions explicitly."""

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.providers.base import MediaPart
from app.providers.embeddings import GeminiEmbeddingProvider
from app.services.creator_import_service import prepare_import
from app.services.creator_library_service import _VERSION, build_passages
from app.services.creator_preset_service import (
    prepared_source,
    preset_object,
    validate_vectors,
)
from app.services.storage_service import get_storage_client


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    publish = commands.add_parser("publish")
    publish.add_argument("folder", type=Path)
    publish.add_argument("--apply", action="store_true")
    publish.add_argument("--max-calls", type=int, default=160, choices=range(1, 161))
    remove = commands.add_parser("remove")
    remove.add_argument("--object", required=True)
    remove.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.command == "remove":
        obj = preset_object(args.object)
        if args.apply:
            get_storage_client().delete_prefix(obj.removesuffix("bundle.zip"))
        print(json.dumps({"object": obj, "removed": args.apply, "dryRun": not args.apply}))
        return
    settings = get_settings()
    prepared = prepare_import(args.folder)
    passages, omitted = build_passages(prepared_source(prepared), settings)
    if any(item.mediaFile for item in prepared.manifest.items):
        parser.error("Backend presets do not include full videos")
    cache_path = args.folder / "embeddings.json"
    payload = {
        "model": settings.model_embedding,
        "dimensions": settings.embedding_dimensions,
        "promptVersion": _VERSION,
        "vectors": {},
    }
    if cache_path.exists():
        old = json.loads(cache_path.read_text())
        if all(old.get(key) == payload[key] for key in ["model", "dimensions", "promptVersion"]):
            payload["vectors"] = {
                key: vector
                for key, vector in old.get("vectors", {}).items()
                if key in {p.node.id for p in passages}
            }
    pending = [p for p in passages if p.node.id not in payload["vectors"]]
    print(
        json.dumps(
            {
                **prepared.summary(),
                "nodes": len(passages),
                "omitted": omitted,
                "pendingModelCalls": len(pending),
                "dryRun": not args.apply,
            }
        ),
        flush=True,
    )
    if not args.apply:
        return
    if len(pending) > args.max_calls:
        parser.error("Index exceeds requested model-call cap; reduce corpus or raise --max-calls")
    provider = GeminiEmbeddingProvider(settings)
    for i, passage in enumerate(pending):
        media = None
        if passage.node.modality == "image":
            image = prepared.files[passage.item["thumbnailStoragePath"]]
            media = MediaPart(mime_type=image.content_type, data=image.path.read_bytes())
        payload["vectors"][passage.node.id] = provider.embed(passage.prompt, media=media)
        cache_path.write_text(json.dumps(payload, separators=(",", ":")))
        if (i + 1) % 8 == 0 or i + 1 == len(pending):
            print(f"Indexed {i + 1}/{len(pending)} new nodes", flush=True)
    validate_vectors(payload, prepared, settings)
    wanted = {"manifest.json", "embeddings.json", *prepared.files}
    for path in args.folder.rglob("*"):
        if path.is_file() and (
            path.parent.name == "raw"
            or path.name in {"collection-report.json", "persona-user-supplied.json"}
        ):
            if path.is_symlink() or not path.resolve().is_relative_to(args.folder.resolve()):
                parser.error("Preset sources must be regular files within the folder")
            wanted.add(path.relative_to(args.folder).as_posix())
    if len(wanted) > 1000 or sum((args.folder / n).stat().st_size for n in wanted) > 150 * 1024**2:
        parser.error("Preset exceeds expanded archive cap")
    with TemporaryDirectory(prefix="creator-publish-") as tmp:
        archive = Path(tmp) / "bundle.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for name in sorted(wanted):
                entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                bundle.writestr(entry, (args.folder / name).read_bytes())
        if archive.stat().st_size > 100 * 1024**2:
            parser.error("Preset exceeds compressed archive cap")
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        obj = f"creator-presets/{prepared.manifest.bundleId}/{digest}/bundle.zip"
        storage = get_storage_client()
        if not storage.object_exists(obj):
            storage.upload_from_filename(obj, str(archive), content_type="application/zip")
        print(
            json.dumps(
                {
                    "object": obj,
                    "bucket": settings.media_bucket,
                    "nodes": len(passages),
                    "bytes": archive.stat().st_size,
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
