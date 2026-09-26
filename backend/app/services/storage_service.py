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

    def upload_bytes(self, path: str, data: bytes, *, content_type: str) -> None: ...

    def download_bytes(self, path: str) -> bytes: ...

    def object_exists(self, path: str) -> bool: ...

    def signed_download_url(self, path: str, *, expires_seconds: int = 900) -> str: ...

    def signed_upload_url(
        self, path: str, *, content_type: str, expires_seconds: int = 900
    ) -> str: ...

    def delete_prefix(self, prefix: str) -> int: ...


class GoogleStorageClient:
    """`StorageClient` backed by a real Cloud Storage bucket."""

    def __init__(
        self, bucket: Any, *, signing_service_account: str | None = None
    ) -> None:
        self._bucket = bucket
        self._signing_service_account = signing_service_account

    def _signing_credentials(self) -> dict[str, Any]:
        """Credentials usable for a V4 signed URL.

        A service-account key (or impersonated credentials) can sign directly. Otherwise we hand
        the SDK a service-account email and an access token, which makes it sign through the IAM
        `signBlob` API. On Cloud Run the email comes from the ambient credentials; with plain user
        ADC locally it comes from `STORAGE_SIGNING_SERVICE_ACCOUNT`. Either way the caller needs
        `roles/iam.serviceAccountTokenCreator` on that service account.
        """
        import google.auth
        from google.auth.transport.requests import Request

        credentials, _ = google.auth.default()
        if hasattr(credentials, "sign_bytes"):
            return {"credentials": credentials}

        # Compute-engine credentials report the placeholder "default" until a metadata request
        # resolves the real email, so treat it as absent and prefer the configured account.
        email = getattr(credentials, "service_account_email", None)
        if not email or email == "default":
            email = self._signing_service_account
        if not email:
            raise RuntimeError(
                "Cannot sign Cloud Storage URLs: no signing credentials. Set "
                "STORAGE_SIGNING_SERVICE_ACCOUNT, use a service-account key, or run "
                "`gcloud auth application-default login --impersonate-service-account`."
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

    def upload_bytes(self, path: str, data: bytes, *, content_type: str) -> None:
        blob = self._bucket.blob(validate_object_path(path))
        blob.upload_from_string(data, content_type=content_type)

    def download_bytes(self, path: str) -> bytes:
        blob = self._bucket.blob(validate_object_path(path))
        return blob.download_as_bytes()

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
    signing_sa = settings.storage_signing_service_account or (
        f"creator-studio-api@{settings.project_id}.iam.gserviceaccount.com"
    )
    return GoogleStorageClient(bucket, signing_service_account=signing_sa)
