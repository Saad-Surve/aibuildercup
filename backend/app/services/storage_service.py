"""Cloud Storage access layer.

Like Firestore, Storage is behind a narrow protocol so feature code and tests never touch the
Google SDK. Only object paths are stored in Firestore; signed URLs are generated on demand.
"""

from functools import lru_cache
from typing import Any, Protocol, runtime_checkable

from app.config import get_settings

__all__ = [
    "GoogleStorageClient",
    "StorageClient",
    "get_storage_client",
    "validate_object_path",
]


class InvalidObjectPath(ValueError):
    """Raised when a storage object path is malformed or attempts traversal."""


def validate_object_path(path: str) -> str:
    """Validate a GCS object path.

    Object names may contain dots (`persona.md`, `video.mp4`), so unlike Firestore
    document ids they are not restricted to alphanumerics. The only requirements are
    that the path is relative and no segment is empty, `.`, or `..`.
    """
    if not path or path.startswith("/") or "\\" in path:
        raise InvalidObjectPath(f"Invalid object path: {path!r}")
    for segment in path.split("/"):
        if segment in ("", ".", ".."):
            raise InvalidObjectPath(f"Invalid object path: {path!r}")
    return path


@runtime_checkable
class StorageClient(Protocol):
    def upload_text(
        self, path: str, text: str, *, content_type: str = "text/markdown"
    ) -> None: ...

    def download_text(self, path: str) -> str: ...

    def object_exists(self, path: str) -> bool: ...

    def signed_download_url(self, path: str, *, expires_seconds: int = 900) -> str: ...

    def delete_prefix(self, prefix: str) -> int: ...


class GoogleStorageClient:
    """`StorageClient` backed by a real Cloud Storage bucket."""

    def __init__(self, bucket: Any) -> None:
        self._bucket = bucket

    def upload_text(
        self, path: str, text: str, *, content_type: str = "text/markdown"
    ) -> None:
        blob = self._bucket.blob(validate_object_path(path))
        blob.upload_from_string(text.encode("utf-8"), content_type=content_type)

    def download_text(self, path: str) -> str:
        blob = self._bucket.blob(validate_object_path(path))
        return blob.download_as_text()

    def object_exists(self, path: str) -> bool:
        return bool(self._bucket.blob(validate_object_path(path)).exists())

    def signed_download_url(self, path: str, *, expires_seconds: int = 900) -> str:
        from datetime import timedelta

        blob = self._bucket.blob(validate_object_path(path))
        return str(blob.generate_signed_url(expiration=timedelta(seconds=expires_seconds)))

    def delete_prefix(self, prefix: str) -> int:
        """Delete every object whose name starts with `prefix`. Returns the count."""
        blobs = list(self._bucket.list_blobs(prefix=prefix))
        if blobs:
            self._bucket.delete_blobs(blobs)
        return len(blobs)


@lru_cache
def get_storage_client() -> StorageClient:
    from google.cloud import storage  # type: ignore[attr-defined]

    settings = get_settings()
    bucket = storage.Client(project=settings.project_id).bucket(settings.media_bucket)
    return GoogleStorageClient(bucket)
