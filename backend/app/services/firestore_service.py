"""Firestore access layer.

Feature code never talks to `google.cloud.firestore` directly. It depends on the narrow
`FirestoreClient` protocol below, which has a real implementation backed by Firestore and an
in-memory implementation used by tests. Path builders live in `paths.py` and are re-exported
here for convenience.
"""

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
    draft_path,
    finding_path,
    heatmap_bin_path,
    heatmap_bins_collection_path,
    job_path,
    jobs_collection_path,
    parse_source_object_path,
    project_object_prefix,
    project_path,
    projects_collection_path,
    reviewer_run_path,
    safe_segment,
    source_object_path,
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
    "draft_path",
    "finding_path",
    "get_firestore_client",
    "heatmap_bin_path",
    "heatmap_bins_collection_path",
    "job_path",
    "jobs_collection_path",
    "parse_source_object_path",
    "project_object_prefix",
    "project_path",
    "projects_collection_path",
    "reviewer_run_path",
    "safe_segment",
    "source_object_path",
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
