"""Firestore access layer.

Feature code never talks to `google.cloud.firestore` directly. It depends on the narrow
`FirestoreClient` protocol below, which has a real implementation backed by Firestore and an
in-memory implementation used by tests. Path builders live in `paths.py` and are re-exported
here for convenience.
"""

from collections.abc import Iterable
from functools import lru_cache
from typing import Any, Protocol, runtime_checkable

from app.config import get_settings
from app.services.paths import (
    InvalidPathSegment,
    analysis_findings_collection_path,
    analysis_reviewers_collection_path,
    analysis_run_path,
    analysis_runs_collection_path,
    asset_path,
    assets_collection_path,
    caption_render_object_path,
    caption_render_path,
    caption_renders_collection_path,
    connection_path,
    connection_secret_path,
    connections_collection_path,
    content_item_path,
    content_items_collection_path,
    draft_path,
    finding_path,
    glossary_path,
    heatmap_bin_path,
    heatmap_bins_collection_path,
    job_path,
    jobs_collection_path,
    localization_object_path,
    localization_path,
    localizations_collection_path,
    oauth_state_path,
    oauth_states_collection_path,
    parse_source_object_path,
    project_object_prefix,
    project_path,
    projects_collection_path,
    publish_path,
    publishes_collection_path,
    reviewer_run_path,
    safe_segment,
    schedule_path,
    schedules_collection_path,
    source_object_path,
    thumbnail_concept_path,
    thumbnail_concepts_collection_path,
    thumbnail_object_path,
    thumbnail_reference_object_path,
    transcript_object_path,
    transcript_path,
    transcript_segment_path,
    transcript_srt_object_path,
    transcript_vtt_object_path,
    transcripts_collection_path,
    user_path,
)

__all__ = [
    "FirestoreClient",
    "GoogleFirestoreClient",
    "InvalidPathSegment",
    "analysis_findings_collection_path",
    "analysis_reviewers_collection_path",
    "analysis_run_path",
    "analysis_runs_collection_path",
    "asset_path",
    "assets_collection_path",
    "caption_render_object_path",
    "caption_render_path",
    "caption_renders_collection_path",
    "connection_path",
    "connection_secret_path",
    "connections_collection_path",
    "content_item_path",
    "content_items_collection_path",
    "draft_path",
    "finding_path",
    "get_firestore_client",
    "glossary_path",
    "heatmap_bin_path",
    "heatmap_bins_collection_path",
    "job_path",
    "jobs_collection_path",
    "localization_object_path",
    "localization_path",
    "localizations_collection_path",
    "oauth_state_path",
    "oauth_states_collection_path",
    "parse_source_object_path",
    "project_object_prefix",
    "project_path",
    "projects_collection_path",
    "publish_path",
    "publishes_collection_path",
    "reviewer_run_path",
    "safe_segment",
    "schedule_path",
    "schedules_collection_path",
    "source_object_path",
    "thumbnail_concept_path",
    "thumbnail_concepts_collection_path",
    "thumbnail_object_path",
    "thumbnail_reference_object_path",
    "transcript_object_path",
    "transcript_path",
    "transcript_segment_path",
    "transcript_srt_object_path",
    "transcript_vtt_object_path",
    "transcripts_collection_path",
    "user_path",
]


@runtime_checkable
class FirestoreClient(Protocol):
    def get_document(self, path: str) -> dict[str, Any] | None: ...

    def set_document(self, path: str, data: dict[str, Any]) -> None: ...

    def set_owned_child(
        self, parent: str, path: str, uid: str, data: dict[str, Any], *, create_only: bool = False
    ) -> bool: ...

    def set_owned_children(
        self, parent: str, documents: list[tuple[str, dict[str, Any]]], uid: str
    ) -> bool: ...

    def create_document(self, path: str, data: dict[str, Any]) -> bool: ...

    def set_documents(self, documents: Iterable[tuple[str, dict[str, Any]]]) -> None: ...

    def update_document(self, path: str, data: dict[str, Any]) -> None: ...

    def delete_document(self, path: str) -> None: ...

    def delete_document_tree(self, path: str) -> None: ...

    def query_collection(
        self,
        collection_path: str,
        *,
        filters: list[tuple[str, str, Any]],
        order_by: list[tuple[str, str]],
        limit: int,
        offset: int,
    ) -> list[tuple[str, dict[str, Any]]]: ...

    def query_collection_group(
        self,
        collection_id: str,
        *,
        filters: list[tuple[str, str, Any]],
        limit: int,
    ) -> list[tuple[str, dict[str, Any]]]: ...


class GoogleFirestoreClient:
    """`FirestoreClient` backed by the real Firestore SDK."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def get_document(self, path: str) -> dict[str, Any] | None:
        snapshot = self._client.document(path).get()
        if not snapshot.exists:
            return None
        return snapshot.to_dict()

    def set_document(self, path: str, data: dict[str, Any]) -> None:
        self._client.document(path).set(data)

    def set_owned_child(
        self, parent: str, path: str, uid: str, data: dict[str, Any], *, create_only: bool = False
    ) -> bool:
        """An in-flight inference must not resurrect a removed source or account."""
        from google.api_core.exceptions import AlreadyExists
        from google.cloud import firestore

        if not path.startswith(parent + "/") or data.get("ownerUid") != uid:
            raise ValueError("Child ownership mismatch")

        @firestore.transactional
        def write(transaction: Any) -> bool:
            user = self._client.document(user_path(uid)).get(transaction=transaction)
            source = self._client.document(parent).get(transaction=transaction)
            if not user.exists or not source.exists:
                return False
            if (
                user.to_dict().get("ownerUid", uid) != uid
                or source.to_dict().get("ownerUid", uid if parent == user_path(uid) else None)
                != uid
            ):
                return False
            if create_only:
                transaction.create(self._client.document(path), data)
            else:
                transaction.set(self._client.document(path), data)
            return True

        try:
            return bool(write(self._client.transaction()))
        except AlreadyExists:
            return False

    def set_owned_children(
        self, parent: str, documents: list[tuple[str, dict[str, Any]]], uid: str
    ) -> bool:
        """Install a bounded precomputed index atomically without one RPC per vector."""
        from google.cloud import firestore

        if len(documents) > 400 or any(
            not path.startswith(parent + "/") or data.get("ownerUid") != uid
            for path, data in documents
        ):
            raise ValueError("Owned batch exceeds limit or has invalid ownership")

        @firestore.transactional
        def write(transaction: Any) -> bool:
            user = self._client.document(user_path(uid)).get(transaction=transaction)
            source = self._client.document(parent).get(transaction=transaction)
            if (
                not user.exists
                or not source.exists
                or user.to_dict().get("ownerUid", uid) != uid
                or source.to_dict().get("ownerUid") != uid
            ):
                return False
            for path, data in documents:
                transaction.set(self._client.document(path), data)
            return True

        return bool(write(self._client.transaction()))

    def create_document(self, path: str, data: dict[str, Any]) -> bool:
        """Atomically create a document; return False if another writer won."""
        from google.api_core.exceptions import AlreadyExists

        try:
            self._client.document(path).create(data)
        except AlreadyExists:
            return False
        return True

    def set_documents(self, documents: Iterable[tuple[str, dict[str, Any]]]) -> None:
        """Persist bounded batches rather than one RPC per document.

        Each batch commits atomically; callers only publish completion after all
        batches succeed. Stable document IDs make a partial retry idempotent.
        """
        batch = self._client.batch()
        count = 0
        for path, data in documents:
            batch.set(self._client.document(path), data)
            count += 1
            if count == 400:
                batch.commit()
                batch = self._client.batch()
                count = 0
        if count:
            batch.commit()

    def update_document(self, path: str, data: dict[str, Any]) -> None:
        self._client.document(path).update(data)

    def delete_document(self, path: str) -> None:
        self._client.document(path).delete()

    def delete_document_tree(self, path: str) -> None:
        self._client.recursive_delete(self._client.document(path))

    def query_collection(
        self,
        collection_path: str,
        *,
        filters: list[tuple[str, str, Any]],
        order_by: list[tuple[str, str]],
        limit: int,
        offset: int,
    ) -> list[tuple[str, dict[str, Any]]]:
        from google.cloud.firestore_v1.base_query import FieldFilter

        query = self._client.collection(collection_path)
        for field, op, value in filters:
            query = query.where(filter=FieldFilter(field, op, value))
        for field, direction in order_by:
            query = query.order_by(field, direction=direction)
        query = query.offset(offset).limit(limit)
        return [(doc.id, doc.to_dict() or {}) for doc in query.stream()]

    def query_collection_group(
        self,
        collection_id: str,
        *,
        filters: list[tuple[str, str, Any]],
        limit: int,
    ) -> list[tuple[str, dict[str, Any]]]:
        """Query a collection across every parent path (e.g. all `jobs` of a user)."""
        from google.cloud.firestore_v1.base_query import FieldFilter

        query = self._client.collection_group(collection_id)
        for field, op, value in filters:
            query = query.where(filter=FieldFilter(field, op, value))
        query = query.limit(limit)
        return [(doc.id, doc.to_dict() or {}) for doc in query.stream()]


@lru_cache
def get_firestore_client() -> FirestoreClient:
    from google.cloud import firestore

    settings = get_settings()
    return GoogleFirestoreClient(firestore.Client(project=settings.project_id))
