import pytest

from app.services.storage_service import GoogleStorageClient


class _SigningCreds:
    """Service-account-like credentials that can sign directly."""

    def sign_bytes(self, message: bytes) -> bytes:  # pragma: no cover - not called
        return b""


class _ComputeCreds:
    """Compute-engine-like credentials: an access token but no private key."""

    service_account_email = "sa@example.iam.gserviceaccount.com"
    token = "access-token"


class _AnonymousCreds:
    service_account_email = None
    token = None


def test_signing_credentials_prefers_a_signing_key(monkeypatch) -> None:
    creds = _SigningCreds()
    monkeypatch.setattr("google.auth.default", lambda: (creds, "proj"))

    assert GoogleStorageClient._signing_credentials() == {"credentials": creds}


def test_signing_credentials_uses_iam_when_no_key(monkeypatch) -> None:
    monkeypatch.setattr("google.auth.default", lambda: (_ComputeCreds(), "proj"))

    assert GoogleStorageClient._signing_credentials() == {
        "service_account_email": "sa@example.iam.gserviceaccount.com",
        "access_token": "access-token",
    }


def test_signing_credentials_without_identity_raises(monkeypatch) -> None:
    monkeypatch.setattr("google.auth.default", lambda: (_AnonymousCreds(), None))

    with pytest.raises(RuntimeError, match="Cannot sign"):
        GoogleStorageClient._signing_credentials()
