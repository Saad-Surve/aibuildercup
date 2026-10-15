"""Bounded, source-owned semantic evidence; no external SDKs in feature logic."""

import hashlib
import json
import logging
import math
import mimetypes
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import numpy as np

from app.config import Settings
from app.errors import AppError
from app.providers.base import EmbeddingProvider, MediaPart
from app.providers.creator_media import download_youtube_thumbnail
from app.schemas.creator_library import (
    CreatorLibrary,
    CreatorLibraryNode,
    CreatorLibrarySearch,
    SemanticNeighbor,
)
from app.services.connection_service import ConnectionService
from app.services.creator_import_service import CreatorImportService, import_path
from app.services.firestore_service import FirestoreClient, connection_path, user_path
from app.services.process_cache import ProcessCache
from app.services.storage_service import StorageClient

_LAYOUTS: ProcessCache[dict[str, CreatorLibraryNode]] = ProcessCache(16)

logger = logging.getLogger(__name__)
_VERSION = "creator-passages-v1"
_MAX_NODES = 300


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def project_vectors(vectors: list[list[float]]) -> list[tuple[float, float]]:
    """Centered PCA of real vectors; canonical axis signs keep repeated renders stable."""
    if len(vectors) < 2:
        return [(0.5, 0.5) for _ in vectors]
    rows = np.asarray(vectors, dtype=float)
    rows -= rows.mean(axis=0)
    _, _, axes = np.linalg.svd(rows, full_matrices=False)
    axes = axes[:2].copy()
    for axis in axes:
        if axis[np.argmax(np.abs(axis))] < 0:
            axis *= -1
    coords = rows @ axes.T
    result = np.full((len(rows), 2), 0.5)
    for c in range(coords.shape[1]):
        lo, hi = coords[:, c].min(), coords[:, c].max()
        if hi - lo > 1e-9:
            result[:, c] = (coords[:, c] - lo) / (hi - lo)
    return [(round(float(x), 5), round(float(y), 5)) for x, y in result]


def add_neighbors(nodes: list[CreatorLibraryNode], vectors: dict[str, list[float]]) -> None:
    """Three highest cosine neighbors, one per other source; full-space, not 2D distances."""
    if len(nodes) < 2:
        return
    rows = np.asarray([vectors[node.id] for node in nodes])
    norms = np.linalg.norm(rows, axis=1, keepdims=True)
    rows = rows / np.maximum(norms, 1e-12)
    similarities = np.clip(rows @ rows.T, -1, 1)
    for i, node in enumerate(nodes):
        seen = {node.itemId}
        for j in np.argsort(-similarities[i], kind="stable"):
            candidate = nodes[int(j)]
            if candidate.itemId in seen:
                continue
            seen.add(candidate.itemId)
            node.related.append(
                SemanticNeighbor(
                    nodeId=candidate.id, similarity=round(float(similarities[i, j]), 5)
                )
            )
            if len(node.related) == 3:
                break
        cross = next(
            (
                int(j)
                for j in np.argsort(-similarities[i], kind="stable")
                if nodes[int(j)].modality != node.modality and nodes[int(j)].itemId != node.itemId
            ),
            None,
        )
        if cross is not None and all(edge.nodeId != nodes[cross].id for edge in node.related):
            node.related.append(
                SemanticNeighbor(
                    nodeId=nodes[cross].id,
                    similarity=round(float(similarities[i, cross]), 5),
                    relation="cross_modal",
                )
            )


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


def build_passages(source: LibrarySource, settings: Settings) -> tuple[list[Passage], int]:
    passages: list[Passage] = []
    omitted = 0
    images = 0
    for item in sorted(source.items, key=lambda i: str(i["id"])):
        title = str(item.get("title", "Untitled"))
        text = str(item.get("text") or item.get("description") or title).strip()
        chunks = [(offset, text[offset : offset + 1400]) for offset in range(0, len(text), 1200)]
        omitted += max(0, len(chunks) - 6)
        candidates: list[tuple[Literal["text", "image"], str, float | None]] = []
        sampled = (
            chunks
            if len(chunks) <= 6
            else [chunks[int(index)] for index in np.linspace(0, len(chunks) - 1, 6)]
        )
        for offset, excerpt in sampled:
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
                    item["id"],
                    modality,
                    excerpt,
                    fingerprint,
                    settings.model_embedding,
                    settings.embedding_dimensions,
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
                platform=item.get("platform", "unknown"),
                language=item.get("language", "und"),
                tags=item.get("tags", []),
                contentType=item.get("contentType", "connected content"),
                attribution=item.get("attribution", ""),
                collectionMethod=item.get("collectionMethod", "connected account"),
            )
            prompt = f"title: {title} | text: {excerpt}" if modality == "text" else title
            passages.append(Passage(node, item, prompt))
    omitted += max(0, len(passages) - _MAX_NODES)
    return passages[:_MAX_NODES], omitted


def with_creator_profile(
    creator: dict[str, Any], items: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not creator.get("bio"):
        return items
    return [
        *items,
        {
            "id": "creator-profile",
            "kind": "profile",
            "title": creator["name"],
            "text": creator["bio"],
            "platform": "profile",
            "language": "en",
            "tags": ["identity", "voice"],
            "contentType": "user-supplied persona",
            "attribution": "User-supplied preferences",
            "collectionMethod": "supplied",
        },
    ]


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
        if self.settings.creator_preset_enabled:
            from app.services.creator_preset_service import CreatorPresetService

            CreatorPresetService(
                self.client, storage=self.storage, imports=self.imports, settings=self.settings
            ).ensure(uid)
        imported = self.imports.active_library(uid)
        if imported is not None:
            bundle, items = imported
            path = f"{import_path(uid, bundle['bundleId'])}/revisions/{bundle['revisionId']}"
            creator = bundle["creator"]
            items = with_creator_profile(creator, items)
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
                "platform": "youtube",
                "collectionMethod": "connected account",
                "text": data.get("transcript", ""),
                "url": f"https://www.youtube.com/watch?v={item_id}",
            }
            for item_id, data in self._rows(f"{path}/contentItems", uid, 100)
            if data.get("ownerUid") == uid
        ]
        return LibrarySource(path, "youtube", connection.displayName, items)

    def _passages(self, source: LibrarySource) -> tuple[list[Passage], int]:
        return build_passages(source, self.settings)

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
        # Chunk vectors are immutable between index writes (which replace createdAt).
        # Read only version metadata on a hit; no 600-vector transfer or PCA per GET.
        versions = self.client.query_collection(
            f"{source.path}/semanticChunks",
            filters=[("ownerUid", "==", uid)],
            order_by=[],
            limit=600,
            offset=0,
            fields=["ownerUid", "createdAt", "updatedAt", "model", "dimensions", "promptVersion"],
        )
        previews: dict[str, str | None] = {}
        nodes = [self._preview(uid, p, previews) for p in passages]

        def load_layout() -> dict[str, CreatorLibraryNode]:
            vectors = self._vectors(source, uid)
            indexed = [node.model_copy(deep=True) for node in nodes if node.id in vectors]
            coords = project_vectors([vectors[node.id] for node in indexed])
            for node, (x, y) in zip(indexed, coords, strict=True):
                node.indexed, node.x, node.y = True, x, y
            add_neighbors(indexed, vectors)
            return {node.id: node for node in indexed}

        layout = _LAYOUTS.get_or_load(
            (
                self.client,
                uid,
                source.path,
                self.settings.model_embedding,
                self.settings.embedding_dimensions,
                _VERSION,
                _hash(sorted(versions)),
                tuple(node.id for node in nodes),
            ),
            load_layout,
        )
        for node in nodes:
            cached = layout.get(node.id)
            if cached:
                node.indexed, node.x, node.y, node.related = (
                    True,
                    cached.x,
                    cached.y,
                    cached.related,
                )
        indexed = [node for node in nodes if node.indexed]
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
        self,
        uid: str,
        query: str,
        *,
        k: int = 8,
        modality: Literal["text", "image"] | None = None,
        passage_filter: Callable[[Passage], bool] | None = None,
        on_embedding: Callable[[str], None] | None = None,
    ) -> CreatorLibrarySearch:
        """Reuse query vectors; optionally filter sources and account for cache misses."""
        source = self.source(uid)
        if source is None:
            return CreatorLibrarySearch(mode="lexical", matches=[])
        passages, _ = self._passages(source)
        if modality is not None:
            passages = [p for p in passages if p.node.modality == modality]
        if passage_filter is not None:
            passages = [p for p in passages if passage_filter(p)]
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
                    prompt = f"task: search result | query: {query[:1000]}"
                    if on_embedding is not None:
                        on_embedding(prompt)
                    vector = self.embeddings.embed(prompt)
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
