"""Envelope encryption for OAuth tokens.

OAuth refresh tokens are long-lived credentials. They are encrypted before they touch
Firestore and decrypted only inside a request or worker that is about to call the platform.

Two backends, chosen by configuration:

- **Cloud KMS** (production): the token JSON is encrypted with `user-token-key`. The service
  account needs `roles/cloudkms.cryptoKeyEncrypterDecrypter`.
- **Local passphrase** (development): when `OAUTH_TOKEN_ENCRYPTION_KEY` is set, a key is derived
  from it with PBKDF2 and the tokens are encrypted with Fernet. This keeps local testing working
  without a KMS grant. Never used when the environment is not local.

The ciphertext is stored as base64 text plus a `keyVersion` string so a KeyUsage can be tied to
the key that produced it.
"""

import base64
import hashlib
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from app.config import Settings

__all__ = ["EncryptedToken", "TokenCipher", "build_token_cipher"]

#: Fixed salt: this is a local-only fallback, and a stable salt keeps tokens readable across
#: restarts (an ephemeral key would silently invalidate every stored refresh token on boot).
_LOCAL_KDF_SALT = b"creator-studio-local-token-cipher-v1"


@dataclass(frozen=True)
class EncryptedToken:
    ciphertext: str
    key_version: str


@runtime_checkable
class TokenCipher(Protocol):
    def encrypt(self, payload: dict[str, Any]) -> EncryptedToken: ...

    def decrypt(self, ciphertext: str) -> dict[str, Any]: ...


class LocalTokenCipher:
    """Fernet backed by a passphrase-derived key. Development only."""

    def __init__(self, passphrase: str) -> None:
        from cryptography.fernet import Fernet

        digest = hashlib.pbkdf2_hmac(
            "sha256", passphrase.encode("utf-8"), _LOCAL_KDF_SALT, 200_000
        )
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, payload: dict[str, Any]) -> EncryptedToken:
        import json

        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        return EncryptedToken(
            ciphertext=self._fernet.encrypt(raw).decode("ascii"),
            key_version="local",
        )

    def decrypt(self, ciphertext: str) -> dict[str, Any]:
        import json

        raw = self._fernet.decrypt(ciphertext.encode("ascii"))
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Decrypted token payload is not an object")
        return data


class KmsTokenCipher:
    """Cloud KMS `encrypt`/`decrypt`. Production path."""

    def __init__(self, key_name: str) -> None:
        from google.cloud import kms  # type: ignore[attr-defined]

        self._client = kms.KeyManagementServiceClient()
        self._key_name = key_name

    def encrypt(self, payload: dict[str, Any]) -> EncryptedToken:
        import json

        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        response = self._client.encrypt(
            request={"name": self._key_name, "plaintext": raw}
        )
        return EncryptedToken(
            ciphertext=base64.b64encode(response.ciphertext).decode("ascii"),
            key_version=str(response.name or self._key_name),
        )

    def decrypt(self, ciphertext: str) -> dict[str, Any]:
        import json

        response = self._client.decrypt(
            request={
                "name": self._key_name,
                "ciphertext": base64.b64decode(ciphertext),
            }
        )
        data = json.loads(response.plaintext.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Decrypted token payload is not an object")
        return data


def default_kms_key_name(settings: Settings) -> str:
    return (
        f"projects/{settings.project_id}/locations/{settings.region}"
        "/keyRings/creator-studio-keyring/cryptoKeys/user-token-key"
    )


def build_token_cipher(settings: Settings) -> TokenCipher:
    """Pick a cipher from settings. Local passphrase wins when set; otherwise KMS."""
    if settings.oauth_token_encryption_key:
        if not settings.is_local:
            raise RuntimeError(
                "OAUTH_TOKEN_ENCRYPTION_KEY is a local development fallback and must not "
                "be set in a non-local environment; use Cloud KMS instead."
            )
        return LocalTokenCipher(settings.oauth_token_encryption_key)
    return KmsTokenCipher(settings.kms_token_key_name or default_kms_key_name(settings))
