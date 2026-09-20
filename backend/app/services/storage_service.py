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

    def signed_upload_url(
        self, path: str, *, content_type: str, expires_seconds: int = 900
    ) -> str: ...

    def delete_prefix(self, prefix: str) -> int: ...


class GoogleStorageClient:
    """`StorageClient` backed by a real Cloud Storage bucket."""

    def __init__(self, bucket: Any) -> None:
        self._bucket = bucket

    @staticmethod
    def _signing_credentials() -> dict[str, Any]:
        """Credentials usable for a V4 signed URL.

        A service-account key can sign directly. On Cloud Run the default credentials are
        compute-engine credentials with no private key, so we hand the SDK the service-account
        email and an access token, which makes it sign through the IAM `signBlob` API. That needs
        `roles/iam.serviceAccountTokenCreator` on the runtime service account.
        """
        import google.auth
        from google.auth.transport.requests import Request

        credentials, _ = google.auth.default()
        if hasattr(credentials, "sign_bytes"):
            return {"credentials": credentials}

        email = getattr(credentials, "service_account_email", None)
        if not email:
            raise RuntimeError(
                "Cannot sign Cloud Storage URLs: no signing credentials. On Cloud Run this uses "
                "the runtime service account via IAM signBlob; locally, use a service-account key "
                "or `gcloud auth application-default login --impersonate-service-account`."
            )
        if not credentials.token:
            credentials.refresh(Request())
        return {"service_account_email": email, "access_token": credentials.token}

    def _signed_url(
        self,
        path: str,
        *,
        method: str,
        expires_seconds: int,
        content_type: str | None = None,
    ) -> str:
        from datetime import timedelta

        blob = self._bucket.blob(validate_object_path(path))
        return str(
            blob.generate_signed_url(
                version="v4",
                expiration=timedelta(seconds=expires_seconds),
                method=method,
                content_type=content_type,
                **self._signing_credentials(),
            )
        )

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
        return self._signed_url(path, method="GET", expires_seconds=expires_seconds)

    def signed_upload_url(
        self, path: str, *, content_type: str, expires_seconds: int = 900
    ) -> str:
        """V4 signed PUT URL so the browser uploads directly to Cloud Storage."""
        return self._signed_url(
            path,
            method="PUT",
            expires_seconds=expires_seconds,
            content_type=content_type,
        )

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
