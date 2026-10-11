"""Validated operator corpus installation; every user copy follows account deletion."""

import json
import logging
import math
import stat
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from typing import Any

from app.config import Settings
from app.errors import AppError
from app.schemas.creator_import import CreatorImportManifest
from app.services.creator_import_service import (
    CreatorImportService,
    PreparedImport,
    import_path,
    item_content_hash,
    object_prefix,
    prepare_import,
)
from app.services.creator_library_service import (
    _VERSION,
    LibrarySource,
    build_passages,
    with_creator_profile,
)
from app.services.firestore_service import FirestoreClient
from app.services.paths import user_path
from app.services.storage_service import StorageClient, validate_object_path

_INSTALL_LOCK = Lock()
logger = logging.getLogger(__name__)
_ARCHIVE_CAP = 100 * 1024**2
_EXPANDED_CAP = 150 * 1024**2


def preset_object(value: str) -> str:
    path = validate_object_path(value)
    if not path.startswith("creator-presets/") or not path.endswith("/bundle.zip"):
        raise ValueError("Preset must be an immutable creator-presets/.../bundle.zip object")
    return path


def prepared_source(prepared: PreparedImport) -> LibrarySource:
    items = [
        {
            **item.model_dump(),
            "text": prepared.texts.get(item.id, ""),
            "segments": prepared.segments.get(item.id, []),
            "thumbnailStoragePath": item.thumbnailFile,
            "contentHash": item_content_hash(prepared, item),
        }
        for item in prepared.manifest.items
    ]
    creator = prepared.manifest.creator.model_dump()
    return LibrarySource("", "folder_import", creator["name"], with_creator_profile(creator, items))


def validate_vectors(
    payload: dict[str, Any], prepared: PreparedImport, settings: Settings
) -> dict[str, list[float]]:
    if (
        payload.get("model") != settings.model_embedding
        or payload.get("dimensions") != settings.embedding_dimensions
        or payload.get("promptVersion") != _VERSION
    ):
        raise ValueError("Preset index model configuration does not match this backend")
    passages, _ = build_passages(prepared_source(prepared), settings)
    expected = {p.node.id for p in passages}
    vectors = payload.get("vectors", {})
    if not isinstance(vectors, dict) or set(vectors) != expected:
        raise ValueError("Preset index is incomplete or belongs to another corpus")
    for vector in vectors.values():
        if (
            not isinstance(vector, list)
            or len(vector) != settings.embedding_dimensions
            or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in vector)
            or abs(sum(v * v for v in vector) - 1) > 0.001
        ):
            raise ValueError("Invalid preset embedding vector")
    return dict(vectors)


def extract_preset(archive: Path, destination: Path) -> PreparedImport:
    if archive.stat().st_size > _ARCHIVE_CAP:
        raise ValueError("Preset archive exceeds 100 MiB")
    with zipfile.ZipFile(archive) as bundle:
        infos = bundle.infolist()
        if len(infos) > 1000 or sum(i.file_size for i in infos) > _EXPANDED_CAP:
            raise ValueError("Preset archive exceeds extraction limits")
        names: set[str] = set()
        for info in infos:
            validate_object_path(info.filename.rstrip("/"))
            if stat.S_ISLNK(info.external_attr >> 16) or info.filename in names:
                raise ValueError("Preset contains symlinks or duplicate entries")
            names.add(info.filename)
        if bundle.getinfo("manifest.json").file_size > 200 * 1024:
            raise ValueError("Preset manifest exceeds byte cap")
        manifest = CreatorImportManifest.model_validate_json(bundle.read("manifest.json"))
        wanted = {"manifest.json", "embeddings.json"}
        for item in manifest.items:
            if item.mediaFile:
                raise ValueError("Backend presets contain text and thumbnails, not full videos")
            wanted.update(path for path in (item.textFile, item.thumbnailFile) if path)
        if not wanted.issubset(names):
            raise ValueError("Preset is missing required originals or embeddings")
        for name in sorted(wanted):
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(bundle.read(name))
    return prepare_import(destination)


class CreatorPresetService:
    def __init__(
        self,
        client: FirestoreClient,
        *,
        storage: StorageClient,
        imports: CreatorImportService,
        settings: Settings,
    ) -> None:
        self.client, self.storage, self.imports, self.settings = client, storage, imports, settings

    def ensure(self, uid: str) -> None:
        if not self.settings.creator_preset_enabled:
            return
        try:
            obj = preset_object(self.settings.creator_preset_object)
            with _INSTALL_LOCK:
                user = self.client.get_document(user_path(uid))
                if user is None or user.get("ownerUid", uid) != uid:
                    raise ValueError("Creator account is unavailable")
                active = self.imports.active_library(uid)
                if user.get("creatorPresetObject") == obj and active is not None:
                    if active[0].get("presetObject") == obj:
                        return
                size = self.storage.object_size(obj)
                if size is None or size > _ARCHIVE_CAP:
                    raise ValueError("Configured creator corpus is missing or exceeds the byte cap")
                with TemporaryDirectory(prefix="creator-preset-") as tmp:
                    root = Path(tmp)
                    archive = root / "bundle.zip"
                    self.storage.download_to_filename(obj, str(archive))
                    extracted = root / "content"
                    prepared = extract_preset(archive, extracted)
                    payload = json.loads((extracted / "embeddings.json").read_text())
                    vectors = validate_vectors(payload, prepared, self.settings)
                    try:
                        self.imports.apply(uid, prepared)
                        parent = (
                            f"{import_path(uid, prepared.manifest.bundleId)}/revisions/"
                            f"{prepared.revision_id}"
                        )
                        documents = [
                            (
                                f"{parent}/semanticChunks/{key}",
                                {
                                    "ownerUid": uid,
                                    "model": self.settings.model_embedding,
                                    "dimensions": self.settings.embedding_dimensions,
                                    "promptVersion": _VERSION,
                                    "vector": vector,
                                    "createdAt": datetime.now(UTC),
                                },
                            )
                            for key, vector in vectors.items()
                        ]
                        if not self.client.set_owned_children(parent, documents, uid):
                            raise ValueError("Creator account or source was removed")
                        self.client.update_document(
                            import_path(uid, prepared.manifest.bundleId), {"presetObject": obj}
                        )
                        self.client.update_document(user_path(uid), {"creatorPresetObject": obj})
                    except Exception:
                        # A concurrent account delete must not leave freshly uploaded originals.
                        if self.client.get_document(user_path(uid)) is None:
                            self.storage.delete_prefix(
                                object_prefix(uid, prepared.manifest.bundleId)
                            )
                            self.client.delete_document_tree(
                                import_path(uid, prepared.manifest.bundleId)
                            )
                        raise
        except Exception as exc:
            logger.exception("Configured creator corpus installation failed")
            raise AppError(
                "Your creator library could not be loaded. Try again shortly.",
                code="CREATOR_LIBRARY_UNAVAILABLE",
                status_code=503,
            ) from exc
