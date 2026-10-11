"""Bounded, source-owned semantic evidence; no external SDKs in feature logic."""

import hashlib
import json
import logging
import math
import mimetypes
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from app.config import Settings
from app.errors import AppError
from app.providers.base import EmbeddingProvider, MediaPart
from app.providers.creator_media import download_youtube_thumbnail
from app.schemas.creator_library import CreatorLibrary, CreatorLibraryNode, CreatorLibrarySearch
from app.services.connection_service import ConnectionService
from app.services.creator_import_service import CreatorImportService, import_path
from app.services.firestore_service import FirestoreClient, connection_path, user_path
from app.services.storage_service import StorageClient

logger = logging.getLogger(__name__)
_VERSION = "creator-passages-v1"
_MAX_NODES = 300


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def project_vectors(vectors: list[list[float]]) -> list[tuple[float, float]]:
    """Deterministic centered PCA via covariance power iteration."""
    if len(vectors) < 2:
        return [(0.5, 0.5) for _ in vectors]
    dimensions = len(vectors[0])
    mean = [sum(row[j] for row in vectors) / len(vectors) for j in range(dimensions)]
    rows = [[x - m for x, m in zip(row, mean, strict=True)] for row in vectors]
    axes: list[list[float]] = []
    coordinates: list[list[float]] = []
    for _component in range(2):
        axis = max(rows, key=lambda row: _dot(row, row))[:]
        if axes:
            axis = max(
                (
                    [x - _dot(row, axes[0]) * a for x, a in zip(row, axes[0], strict=True)]
                    for row in rows
                ),
                key=lambda row: _dot(row, row),
            )
        for _ in range(24):
            norm = math.sqrt(_dot(axis, axis))
            if norm < 1e-10:
                axis = [0.0] * dimensions
                break
            axis = [x / norm for x in axis]
            scores = [_dot(row, axis) for row in rows]
            axis = [
                sum(score * row[j] for score, row in zip(scores, rows, strict=True))
                for j in range(dimensions)
            ]
            for previous in axes:
                overlap = _dot(axis, previous)
                axis = [x - overlap * a for x, a in zip(axis, previous, strict=True)]
        norm = math.sqrt(_dot(axis, axis))
        axis = [x / norm for x in axis] if norm > 1e-10 else [0.0] * dimensions
        pivot = max(range(dimensions), key=lambda j: abs(axis[j]))
        if axis[pivot] < 0:
            axis = [-x for x in axis]
        axes.append(axis)
        coordinates.append([_dot(row, axis) for row in rows])
    result: list[tuple[float, float]] = []
    bounds = [(min(values), max(values)) for values in coordinates]
    for index in range(len(rows)):
        xy = [
            0.5 if hi - lo < 1e-9 else (coordinates[c][index] - lo) / (hi - lo)
            for c, (lo, hi) in enumerate(bounds)
        ]
        result.append((round(xy[0], 5), round(xy[1], 5)))
    return result


@dataclass
class LibrarySource:
    path: str
    source_type: Literal["folder_import", "youtube"]
    display_name: str
    items: list[dict[str, Any]]


@dataclass
class Passage:
    node: CreatorLibraryNode
    item: dict[str, Any]
    prompt: str


class CreatorLibraryService:
    def __init__(
        self,
        client: FirestoreClient,
        *,
        storage: StorageClient,
        imports: CreatorImportService,
        connections: ConnectionService,
        embeddings: EmbeddingProvider,
        settings: Settings,
    ) -> None:
        self.client = client
        self.storage = storage
        self.imports = imports
        self.connections = connections
        self.embeddings = embeddings
        self.settings = settings

    def _rows(self, path: str, uid: str, limit: int = 600) -> list[tuple[str, dict[str, Any]]]:
        return self.client.query_collection(
            path, filters=[("ownerUid", "==", uid)], order_by=[], limit=limit, offset=0
        )

    def source(self, uid: str) -> LibrarySource | None:
        imported = self.imports.active_library(uid)
        if imported is not None:
            bundle, items = imported
            path = f"{import_path(uid, bundle['bundleId'])}/revisions/{bundle['revisionId']}"
            creator = bundle["creator"]
            if creator.get("bio"):
                items = [
                    *items,
                    {
                        "id": "creator-profile",
                        "kind": "profile",
                        "title": creator["name"],
                        "text": creator["bio"],
                    },
                ]
            return LibrarySource(path, "folder_import", creator["name"], items)
        connections = [
            c
            for c in self.connections.list(owner_uid=uid)
            if c.contentSyncedAt is not None and c.status.value == "connected"
        ]
        if not connections:
            return None
        connection = max(
            connections, key=lambda c: c.contentSyncedAt.timestamp() if c.contentSyncedAt else 0
        )
        path = connection_path(uid, connection.connectionId)
        items = [
            {
                **data,
                "id": item_id,
                "kind": "video",
                "text": data.get("transcript", ""),
                "url": f"https://www.youtube.com/watch?v={item_id}",
            }
            for item_id, data in self._rows(f"{path}/contentItems", uid, 100)
            if data.get("ownerUid") == uid
        ]
        return LibrarySource(path, "youtube", connection.displayName, items)

    def _passages(self, source: LibrarySource) -> tuple[list[Passage], int]:
        passages: list[Passage] = []
        omitted = 0
        images = 0
        for item in sorted(source.items, key=lambda i: str(i["id"])):
            title = str(item.get("title", "Untitled"))
            text = str(item.get("text") or item.get("description") or title).strip()
            chunks = [
                (offset, text[offset : offset + 1400]) for offset in range(0, len(text), 1200)
            ]
            omitted += max(0, len(chunks) - 6)
            candidates: list[tuple[Literal["text", "image"], str, float | None]] = []
            for offset, excerpt in chunks[:6]:
                start = None
                if item.get("segments"):
                    position = 0
                    for segment in item["segments"]:
                        end = position + len(segment["text"]) + 1
                        if end > offset:
                            start = float(segment["startMs"]) / 1000
                            break
                        position = end
                candidates.append(("text", excerpt, start))
            if item.get("thumbnailStoragePath") or item.get("thumbnailUrl"):
                if images < 10:
                    candidates.append(("image", f"Thumbnail: {title}", None))
                    images += 1
            for modality, excerpt, start in candidates:
                fingerprint = item.get("contentHash") or item.get("thumbnailUrl")
                node_id = _hash(
                    [
                        source.path,
                        item["id"],
                        modality,
                        excerpt,
                        fingerprint,
                        self.settings.model_embedding,
                        self.settings.embedding_dimensions,
                        _VERSION,
                    ]
                )
                node = CreatorLibraryNode(
                    id=node_id,
                    itemId=str(item["id"]),
                    title=title,
                    kind=item.get("kind", "video"),
                    modality=modality,
                    excerpt=excerpt,
                    url=item.get("url"),
                    startSeconds=start,
                )
                prompt = f"title: {title} | text: {excerpt}" if modality == "text" else title
                passages.append(Passage(node, item, prompt))
        omitted += max(0, len(passages) - _MAX_NODES)
        return passages[:_MAX_NODES], omitted

    def _vectors(self, source: LibrarySource, uid: str) -> dict[str, list[float]]:
        result = {}
        for key, data in self._rows(f"{source.path}/semanticChunks", uid):
            vector = data.get("vector", [])
            if (
                data.get("ownerUid") == uid
                and data.get("model") == self.settings.model_embedding
                and data.get("promptVersion") == _VERSION
                and len(vector) == self.settings.embedding_dimensions
                and all(isinstance(x, (float, int)) and math.isfinite(x) for x in vector)
            ):
                result[key] = vector
        return result

    def _reserve_call(self, uid: str) -> None:
        day = datetime.now(UTC).strftime("%Y-%m-%d")
        path = f"{user_path(uid)}/embeddingBudgets/{day}/calls"
        occupied = {
            key for key, _ in self._rows(path, uid, self.settings.embedding_daily_call_limit)
        }
        for slot in range(self.settings.embedding_daily_call_limit):
            if str(slot) in occupied:
                continue
            if self.client.set_owned_child(
                user_path(uid),
                f"{path}/{slot}",
                uid,
                {
                    "ownerUid": uid,
                    "createdAt": datetime.now(UTC),
                    "model": self.settings.model_embedding,
                },
                create_only=True,
            ):
                return
        raise AppError(
            "Today's embedding allowance is used. Try again tomorrow.",
            code="EMBEDDING_DAILY_LIMIT",
            status_code=429,
        )

    def _image(self, uid: str, item: dict[str, Any]) -> MediaPart:
        path = item.get("thumbnailStoragePath")
        if path:
            if not str(path).startswith(f"{user_path(uid)}/creator-imports/"):
                raise ValueError("Thumbnail does not belong to this creator")
            data = self.storage.download_bytes(path)
            mime = mimetypes.guess_type(path)[0] or "image/jpeg"
        else:
            return download_youtube_thumbnail(str(item.get("thumbnailUrl", "")))
        if (
            not data
            or len(data) > 5_000_000
            or mime not in {"image/jpeg", "image/png", "image/webp"}
        ):
            raise ValueError("Unsupported thumbnail image")
        return MediaPart(mime_type=mime, data=data)

    def _preview(
        self, uid: str, passage: Passage, previews: dict[str, str | None] | None = None
    ) -> CreatorLibraryNode:
        preview_cache = previews if previews is not None else {}
        node = passage.node.model_copy()
        path = passage.item.get("thumbnailStoragePath")
        if path and str(path).startswith(f"{user_path(uid)}/creator-imports/"):
            if path not in preview_cache:
                try:
                    preview_cache[path] = self.storage.signed_download_url(path)
                except Exception:
                    preview_cache[path] = None
                    logger.warning("Creator library thumbnail signing failed", exc_info=True)
            node.thumbnailUrl = preview_cache[path]
        else:
            node.thumbnailUrl = passage.item.get("thumbnailUrl")
        return node

    def library(self, uid: str) -> CreatorLibrary:
        response = CreatorLibrary(
            model=self.settings.model_embedding, dimensions=self.settings.embedding_dimensions
        )
        source = self.source(uid)
        if source is None:
            return response
        passages, omitted = self._passages(source)
        vectors = self._vectors(source, uid)
        previews: dict[str, str | None] = {}
        nodes = [self._preview(uid, p, previews) for p in passages]
        indexed = [node for node in nodes if node.id in vectors]
        coords = project_vectors([vectors[node.id] for node in indexed])
        for node, (x, y) in zip(indexed, coords, strict=True):
            node.indexed, node.x, node.y = True, x, y
        return CreatorLibrary(
            sourceType=source.source_type,
            displayName=source.display_name,
            model=self.settings.model_embedding,
            dimensions=self.settings.embedding_dimensions,
            itemCount=sum(item.get("kind") != "profile" for item in source.items),
            totalNodes=len(nodes),
            indexedNodes=len(indexed),
            omittedPassages=omitted,
            nodes=nodes,
        )

    def index(self, uid: str) -> CreatorLibrary:
        source = self.source(uid)
        if source is None:
            return self.library(uid)
        passages, _ = self._passages(source)
        vectors = self._vectors(source, uid)
        valid = {p.node.id for p in passages}
        for key, _ in self._rows(f"{source.path}/semanticChunks", uid):
            if key not in valid:
                self.client.delete_document(f"{source.path}/semanticChunks/{key}")
        error = None
        for passage in [p for p in passages if p.node.id not in vectors][:16]:
            try:
                media = self._image(uid, passage.item) if passage.node.modality == "image" else None
                self._reserve_call(uid)
                vector = self.embeddings.embed(passage.prompt, media=media)
                current = self.source(uid)
                if current is None or current.path != source.path:
                    break
                self.client.set_owned_child(
                    source.path,
                    f"{source.path}/semanticChunks/{passage.node.id}",
                    uid,
                    {
                        "ownerUid": uid,
                        "model": self.settings.model_embedding,
                        "dimensions": self.settings.embedding_dimensions,
                        "promptVersion": _VERSION,
                        "vector": vector,
                        "createdAt": datetime.now(UTC),
                    },
                )
            except AppError:
                raise
            except Exception:
                logger.warning("Creator embedding batch stopped", exc_info=True)
                error = (
                    "Indexing stopped on a source or model error. "
                    "Completed passages are saved; retry to resume."
                )
                break
        response = self.library(uid)
        response.errorMessage = error
        return response

    def search(
        self, uid: str, query: str, *, k: int = 8, modality: Literal["text", "image"] | None = None
    ) -> CreatorLibrarySearch:
        source = self.source(uid)
        if source is None:
            return CreatorLibrarySearch(mode="lexical", matches=[])
        passages, _ = self._passages(source)
        if modality is not None:
            passages = [p for p in passages if p.node.modality == modality]
        vectors = self._vectors(source, uid)
        mode: Literal["semantic", "lexical"] = "lexical"
        ranked: list[tuple[float, Passage]] = []
        usable = [p for p in passages if p.node.id in vectors]
        if usable:
            try:
                key = _hash(
                    [
                        query,
                        self.settings.model_embedding,
                        self.settings.embedding_dimensions,
                        _VERSION,
                    ]
                )
                path = f"{source.path}/semanticQueries/{key}"
                cached = self.client.get_document(path)
                if cached and cached.get("ownerUid") == uid:
                    vector = cached["vector"]
                else:
                    self._reserve_call(uid)
                    vector = self.embeddings.embed(f"task: search result | query: {query[:1000]}")
                    cache = self._rows(f"{source.path}/semanticQueries", uid, 100)
                    if len(cache) >= 100:
                        oldest = min(
                            cache,
                            key=lambda row: row[1].get(
                                "createdAt", datetime.min.replace(tzinfo=UTC)
                            ),
                        )
                        self.client.delete_document(f"{source.path}/semanticQueries/{oldest[0]}")
                    current = self.source(uid)
                    if current is not None and current.path == source.path:
                        self.client.set_owned_child(
                            source.path,
                            path,
                            uid,
                            {"ownerUid": uid, "vector": vector, "createdAt": datetime.now(UTC)},
                        )
                ranked = [(_dot(vector, vectors[p.node.id]), p) for p in usable]
                mode = "semantic"
            except AppError:
                raise
            except Exception:
                logger.warning("Creator semantic search unavailable", exc_info=True)
        if mode == "lexical":
            words = set(re.findall(r"\w+", query.casefold()))
            ranked = [
                (
                    len(
                        words
                        & set(re.findall(r"\w+", (p.node.title + " " + p.node.excerpt).casefold()))
                    )
                    / max(1, len(words)),
                    p,
                )
                for p in passages
            ]
            ranked = [(score, p) for score, p in ranked if score > 0]
        matches = []
        previews: dict[str, str | None] = {}
        for score, passage in sorted(ranked, key=lambda entry: (-entry[0], entry[1].node.id))[:k]:
            node = self._preview(uid, passage, previews)
            node.indexed = node.id in vectors
            node.score = round(score, 5)
            matches.append(node)
        return CreatorLibrarySearch(mode=mode, matches=matches)

    def thumbnail_references(self, uid: str, query: str, *, limit: int) -> list[MediaPart]:
        hits = self.search(uid, query, k=limit, modality="image")
        source = self.source(uid)
        if source is None:
            return []
        items = {str(item["id"]): item for item in source.items}
        references = []
        for hit in hits.matches:
            if hit.itemId in items:
                try:
                    image = self._image(uid, items[hit.itemId])
                    references.append(
                        MediaPart(
                            mime_type=image.mime_type,
                            data=image.data,
                            label="Creator thumbnail — match style, do not copy",
                        )
                    )
                except Exception:
                    logger.warning("Retrieved creator thumbnail unavailable", exc_info=True)
        return references

    def improve_context(
        self, uid: str, query: str, context: dict[str, Any], *, k: int
    ) -> dict[str, Any]:
        results = self.search(uid, query, k=24)
        hits: dict[str, CreatorLibraryNode] = {}
        for hit in results.matches:
            if hit.modality == "text" and hit.kind != "profile":
                hits.setdefault(hit.itemId, hit)
        for field, id_field, excerpt_field in [
            ("examples", "videoId", "transcriptExcerpt"),
            ("writtenExamples", "itemId", "excerpt"),
        ]:
            examples = context.get(field, [])
            for example in examples:
                matching = hits.get(example.get(id_field, ""))
                if matching is not None:
                    example[excerpt_field] = matching.excerpt
            order = {item_id: rank for rank, item_id in enumerate(hits)}
            examples.sort(key=lambda example: order.get(example.get(id_field, ""), len(order)))
            context[field] = examples[:k]
        return context
