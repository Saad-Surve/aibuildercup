import pytest

from app.services.storage_service import GoogleStorageClient


class _SigningCreds:
    """Service-account-like credentials that can sign directly."""

    def sign_bytes(self, message: bytes) -> bytes:  # pragma: no cover - not called
        return b""


class _ComputeCreds:
    """Compute-engine-like credentials: an access token and a service-account identity."""

    service_account_email = "sa@example.iam.gserviceaccount.com"
    token = "access-token"


class _UserCreds:
    """User ADC: an access token but no service-account identity."""

    service_account_email = None
    token = "user-token"


def _client(signing_sa: str | None = None) -> GoogleStorageClient:
    return GoogleStorageClient(None, signing_service_account=signing_sa)


def test_signing_credentials_prefers_a_signing_key(monkeypatch) -> None:
    creds = _SigningCreds()
    monkeypatch.setattr("google.auth.default", lambda: (creds, "proj"))

    assert _client()._signing_credentials() == {"credentials": creds}


def test_signing_credentials_uses_ambient_service_account(monkeypatch) -> None:
    monkeypatch.setattr("google.auth.default", lambda: (_ComputeCreds(), "proj"))

    assert _client()._signing_credentials() == {
        "service_account_email": "sa@example.iam.gserviceaccount.com",
        "access_token": "access-token",
    }


def test_signing_credentials_falls_back_to_configured_service_account(
    monkeypatch,
) -> None:
    monkeypatch.setattr("google.auth.default", lambda: (_UserCreds(), "proj"))

    assert _client("runtime@example.iam.gserviceaccount.com")._signing_credentials() == {
        "service_account_email": "runtime@example.iam.gserviceaccount.com",
        "access_token": "user-token",
    }


def test_signing_credentials_without_identity_raises(monkeypatch) -> None:
    monkeypatch.setattr("google.auth.default", lambda: (_UserCreds(), None))

    with pytest.raises(RuntimeError, match="Cannot sign"):
        _client()._signing_credentials()
