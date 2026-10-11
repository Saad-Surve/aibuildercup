"""Import supplied creator originals through real persistence services, without OAuth.

No models run during import. The immutable library can be used by the same writer and
thumbnail workflows that consume connected-channel content, and indexed later.
"""

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.providers.base import MediaPart
from app.schemas.creator_import import CreatorImportManifest
from app.services.firestore_service import FirestoreClient
from app.services.paths import safe_segment, user_path
from app.services.storage_service import StorageClient

_TEXT_TYPES = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".srt": "application/x-subrip",
    ".vtt": "text/vtt",
}
_IMAGE_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
_VIDEO_TYPES = {".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm"}
_TIMESTAMP = re.compile(r"(?:(\d+):)?(\d{2}):(\d{2})[,.](\d{3})")
logger = logging.getLogger(__name__)


def import_path(uid: str, bundle_id: str) -> str:
    return f"{user_path(uid)}/creatorImports/{safe_segment(bundle_id, name='bundleId')}"


def object_prefix(uid: str, bundle_id: str) -> str:
    return f"{user_path(uid)}/creator-imports/{safe_segment(bundle_id, name='bundleId')}/"


@dataclass(frozen=True)
class ImportFile:
    path: Path
    relative_path: str
    content_type: str
    size: int
    digest: str


@dataclass(frozen=True)
class PreparedImport:
    manifest: CreatorImportManifest
    files: dict[str, ImportFile]
    texts: dict[str, str]
    segments: dict[str, list[dict[str, Any]]]
    revision_id: str

    def summary(self) -> dict[str, Any]:
        items = self.manifest.items
        return {
            "bundleId": self.manifest.bundleId,
            "creatorName": self.manifest.creator.name,
            "revisionId": self.revision_id,
            "items": len(items),
            "videos": sum(item.kind == "video" for item in items),
            "writtenPieces": sum(item.kind != "video" for item in items),
            "thumbnails": sum(bool(item.thumbnailFile) for item in items),
            "textFiles": sum(bool(item.textFile) for item in items),
            "mediaFiles": sum(bool(item.mediaFile) for item in items),
            "bytes": sum(file.size for file in self.files.values()),
        }


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _subtitles(raw: str) -> tuple[str, list[dict[str, Any]]]:
    segments: list[dict[str, Any]] = []
    for block in re.split(r"\n\s*\n", raw.replace("\r\n", "\n").strip()):
        lines = block.splitlines()
        timing = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing is None:
            continue
        matches = list(_TIMESTAMP.finditer(lines[timing]))
        if len(matches) != 2:
            raise ValueError("Invalid subtitle timestamp")
        times = []
        for match in matches:
            hours, minutes, seconds, millis = match.groups()
            if int(minutes) > 59 or int(seconds) > 59:
                raise ValueError("Invalid subtitle timestamp")
            times.append(
                ((int(hours or 0) * 60 + int(minutes)) * 60 + int(seconds)) * 1000 + int(millis)
            )
        text = re.sub(r"<[^>]+>", "", " ".join(lines[timing + 1 :])).strip()
        if times[1] <= times[0] or not text:
            raise ValueError("Subtitle cues need text and increasing timestamps")
        segments.append({"startMs": times[0], "endMs": times[1], "text": text})
    if not segments:
        raise ValueError("Subtitle file contains no usable timed cues")
    return " ".join(segment["text"] for segment in segments), segments


def prepare_import(folder: Path) -> PreparedImport:
    """Fully validate/hash declared files locally, before any cloud mutation."""
    root = folder.resolve(strict=True)
    manifest_path = root / "manifest.json"
    if not manifest_path.resolve(strict=True).is_relative_to(root):
        raise ValueError("Manifest resolves outside the supplied folder")
    if manifest_path.stat().st_size > 200 * 1024:
        raise ValueError("manifest.json exceeds 200 KiB")
    manifest = CreatorImportManifest.model_validate_json(manifest_path.read_text("utf-8"))
    files: dict[str, ImportFile] = {}
    texts: dict[str, str] = {}
    segments: dict[str, list[dict[str, Any]]] = {}
    for item in manifest.items:
        for field, types, cap in (
            ("textFile", _TEXT_TYPES, 200 * 1024),
            ("thumbnailFile", _IMAGE_TYPES, 5 * 1024 * 1024),
            ("mediaFile", _VIDEO_TYPES, 1024**3),
        ):
            relative = getattr(item, field)
            if relative is None:
                continue
            path = (root / relative).resolve(strict=True)
            if not path.is_relative_to(root) or not path.is_file():
                raise ValueError(f"{relative}: must be a regular file inside the folder")
            extension = path.suffix.lower()
            if extension not in types:
                raise ValueError(f"{relative}: unsupported {field} format")
            size = path.stat().st_size
            if size == 0 or size > cap:
                raise ValueError(f"{relative}: must contain 1–{cap} bytes")
            if field == "thumbnailFile":
                header = path.read_bytes()[:12]
                valid = (
                    (extension in {".jpg", ".jpeg"} and header.startswith(b"\xff\xd8\xff"))
                    or (extension == ".png" and header.startswith(b"\x89PNG\r\n\x1a\n"))
                    or (extension == ".webp" and header[:4] == b"RIFF" and header[8:12] == b"WEBP")
                )
                if not valid:
                    raise ValueError(f"{relative}: image header does not match its extension")
            files[relative] = ImportFile(path, relative, types[extension], size, _digest(path))
            if field == "textFile":
                raw = path.read_text("utf-8")
                if extension in {".srt", ".vtt"}:
                    texts[item.id], segments[item.id] = _subtitles(raw)
                else:
                    texts[item.id] = raw.strip()
                if not texts[item.id]:
                    raise ValueError(f"{relative}: no usable text")
        if sum(file.size for file in files.values()) > 2 * 1024**3:
            raise ValueError("Referenced files exceed the 2 GiB bundle limit")
    canonical = json.dumps(
        {
            "manifest": manifest.model_dump(mode="json"),
            "files": {name: file.digest for name, file in sorted(files.items())},
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    revision_id = hashlib.sha256(canonical.encode()).hexdigest()[:32]
    return PreparedImport(manifest, files, texts, segments, revision_id)


class CreatorImportService:
    def __init__(self, client: FirestoreClient, *, storage: StorageClient) -> None:
        self.client = client
        self.storage = storage

    def _user(self, uid: str) -> dict[str, Any]:
        user = self.client.get_document(user_path(uid))
        if user is None or user.get("ownerUid", uid) != uid:
            raise ValueError("Target user must already exist and belong to the supplied UID")
        return user

    def apply(self, uid: str, prepared: PreparedImport) -> dict[str, Any]:
        self._user(uid)
        manifest = prepared.manifest
        path = import_path(uid, manifest.bundleId)
        existing = self.client.get_document(path)
        if existing is not None and existing.get("ownerUid") != uid:
            raise ValueError("Import ownership mismatch")
        # Check every file again before the first write: validation must not import stale hashes.
        for file in prepared.files.values():
            if file.path.stat().st_size != file.size or _digest(file.path) != file.digest:
                raise ValueError(f"{file.relative_path}: changed after validation; retry")
        now = datetime.now(UTC)
        revision = f"{path}/revisions/{prepared.revision_id}"
        prefix = f"{object_prefix(uid, manifest.bundleId)}{prepared.revision_id}/"
        if existing is None or existing.get("revisionId") != prepared.revision_id:
            for relative, file in prepared.files.items():
                self.storage.upload_from_filename(
                    prefix + relative, str(file.path), content_type=file.content_type
                )
            documents = []
            for item in manifest.items:
                payload = item.model_dump(
                    mode="python", exclude={"textFile", "thumbnailFile", "mediaFile"}
                )
                payload.update(
                    {
                        "ownerUid": uid,
                        "sourceType": "folder_import",
                        "text": prepared.texts.get(item.id, ""),
                        "segments": prepared.segments.get(item.id, []),
                        "textStoragePath": prefix + item.textFile if item.textFile else None,
                        "thumbnailStoragePath": (
                            prefix + item.thumbnailFile if item.thumbnailFile else None
                        ),
                        "mediaStoragePath": prefix + item.mediaFile if item.mediaFile else None,
                        "contentHash": hashlib.sha256(
                            json.dumps(
                                {
                                    "item": item.model_dump(mode="json"),
                                    "files": {
                                        name: prepared.files[name].digest
                                        for name in (
                                            item.textFile,
                                            item.thumbnailFile,
                                            item.mediaFile,
                                        )
                                        if name
                                    },
                                },
                                sort_keys=True,
                            ).encode()
                        ).hexdigest(),
                    }
                )
                documents.append((f"{revision}/items/{item.id}", payload))
            self.client.set_documents(documents)
            self.client.set_document(
                revision,
                {
                    "ownerUid": uid,
                    "createdAt": now,
                    **prepared.summary(),
                },
            )
            self.client.set_document(
                path,
                {
                    "ownerUid": uid,
                    "sourceType": "folder_import",
                    "creator": manifest.creator.model_dump(),
                    "audience": manifest.audience.model_dump() if manifest.audience else None,
                    "createdAt": (existing or {}).get("createdAt", now),
                    "updatedAt": now,
                    **prepared.summary(),
                },
            )
        self.client.update_document(
            user_path(uid),
            {
                "activeCreatorImportId": manifest.bundleId,
                "updatedAt": now,
            },
        )
        return {"uid": uid, "applied": True, **prepared.summary()}

    def remove(self, uid: str, bundle_id: str) -> None:
        user = self._user(uid)
        path = import_path(uid, bundle_id)
        bundle = self.client.get_document(path)
        if bundle is not None and bundle.get("ownerUid") != uid:
            raise ValueError("Import ownership mismatch")
        if user.get("activeCreatorImportId") == bundle_id:
            self.client.update_document(
                user_path(uid),
                {
                    "activeCreatorImportId": None,
                    "updatedAt": datetime.now(UTC),
                },
            )
        self.storage.delete_prefix(object_prefix(uid, bundle_id))
        self.client.delete_document_tree(path)

    def active_library(self, uid: str) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
        user = self.client.get_document(user_path(uid)) or {}
        bundle_id = user.get("activeCreatorImportId")
        if not bundle_id or user.get("ownerUid", uid) != uid:
            return None
        path = import_path(uid, str(bundle_id))
        bundle = self.client.get_document(path)
        if bundle is None or bundle.get("ownerUid") != uid:
            return None
        revision_id = safe_segment(str(bundle["revisionId"]), name="revisionId")
        rows = self.client.query_collection(
            f"{path}/revisions/{revision_id}/items",
            filters=[("ownerUid", "==", uid)],
            order_by=[],
            limit=100,
            offset=0,
        )
        return bundle, [data for _, data in rows if data.get("ownerUid") == uid]

    def build_context(self, uid: str, *, query: str, k: int = 5) -> dict[str, Any] | None:
        active = self.active_library(uid)
        if active is None:
            return None
        bundle, items = active
        tokens = set(re.findall(r"\w+", query.casefold()))
        ranked = sorted(
            items,
            key=lambda item: len(
                tokens
                & set(
                    re.findall(
                        r"\w+", f"{item['title']} {item['description']} {item['text']}".casefold()
                    )
                )
            ),
            reverse=True,
        )
        examples = [
            {
                "videoId": item["id"],
                "title": item["title"],
                "tags": item["tags"],
                "viewCount": item.get("viewCount"),
                "likeCount": item.get("likeCount"),
                "commentCount": item.get("commentCount"),
                "publishedAt": (item["publishedAt"].isoformat() if item["publishedAt"] else None),
                "transcriptExcerpt": item["text"][:1500],
                "thumbnailStoragePath": item["thumbnailStoragePath"],
                "thumbnailUrl": None,
            }
            for item in ranked
            if item["kind"] == "video"
        ][:k]
        written = [
            {
                "itemId": item["id"],
                "title": item["title"],
                "url": item["url"],
                "excerpt": item["text"][:1500],
            }
            for item in ranked
            if item["kind"] != "video"
        ][:k]
        return {
            "sourceType": "folder_import",
            "creatorName": bundle["creator"]["name"],
            "creatorBio": bundle["creator"]["bio"],
            "connectionId": None,
            "connectionDisplayName": bundle["creator"]["name"],
            "examples": examples,
            "writtenExamples": written,
            "audience": bundle.get("audience"),
        }

    def thumbnail_references(self, uid: str, *, limit: int = 3) -> list[MediaPart]:
        active = self.active_library(uid)
        if active is None or limit <= 0:
            return []
        _, items = active
        references = []
        for item in items:
            path = item.get("thumbnailStoragePath")
            if not path or not str(path).startswith(f"{user_path(uid)}/creator-imports/"):
                continue
            data = self.storage.download_bytes(path)
            if data and len(data) <= 5 * 1024 * 1024:
                references.append(
                    MediaPart(
                        mime_type=_IMAGE_TYPES[Path(path).suffix.lower()],
                        data=data,
                        label="Supplied creator thumbnail — use as a visual style reference",
                    )
                )
            if len(references) >= limit:
                break
        return references

    def hydrate_context(self, uid: str, context: dict[str, Any]) -> dict[str, Any]:
        """Sign imported preview URLs at read time; removed files have no preview."""
        result = {**context, "examples": [dict(item) for item in context.get("examples", [])]}
        for item in result["examples"]:
            path = item.get("thumbnailStoragePath")
            item["thumbnailUrl"] = None
            if not path or not str(path).startswith(f"{user_path(uid)}/creator-imports/"):
                continue
            try:
                if self.storage.object_exists(path):
                    item["thumbnailUrl"] = self.storage.signed_download_url(path)
            except Exception:  # noqa: BLE001 - a missing preview must not hide text evidence
                logger.warning("Imported thumbnail preview unavailable", exc_info=True)
        return result
