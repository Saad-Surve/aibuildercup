"""Google OAuth 2.0 (authorization code + PKCE) for the YouTube connector.

This is the only place that talks to Google's OAuth endpoints. It is deliberately dependency-light
(`requests` + PKCE built from `hashlib`) because `google-auth-oauthlib` is not installed, and we
only need four calls: authorize, exchange, refresh, revoke, plus userinfo.

Feature code never imports this directly; `ConnectionService` and the publish worker go through
the `OAuthService`/`GoogleOAuthClient` here.
"""

import base64
import hashlib
import logging
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import requests

from app.config import Settings
from app.errors import BadRequestError

logger = logging.getLogger(__name__)

AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"
USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"

#: Google returns an access token with roughly one hour left; refresh a little early so a
#: long publish never starts with a token that expires mid-upload.
_ACCESS_TOKEN_SKEW = timedelta(seconds=120)


def generate_state() -> str:
    """A URL-safe opaque state value, also used as the Firestore document id."""
    return secrets.token_urlsafe(32)


def build_pkce_pair() -> tuple[str, str]:
    """Return `(code_verifier, code_challenge)` for S256 PKCE."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


@dataclass(frozen=True)
class OAuthTokenSet:
    access_token: str
    refresh_token: str | None
    expires_at: datetime
    scopes: tuple[str, ...] = ()
    token_type: str = "Bearer"
    id_token: str | None = None

    def is_expired(self, *, now: datetime | None = None) -> bool:
        return (now or datetime.now(UTC)) + _ACCESS_TOKEN_SKEW >= self.expires_at

    def to_storage(self) -> dict[str, Any]:
        return {
            "accessToken": self.access_token,
            "refreshToken": self.refresh_token,
            "expiresAt": self.expires_at.isoformat(),
            "scopes": list(self.scopes),
            "tokenType": self.token_type,
            "idToken": self.id_token,
        }

    @classmethod
    def from_storage(cls, data: dict[str, Any]) -> "OAuthTokenSet":
        expires_raw = data.get("expiresAt")
        if isinstance(expires_raw, str):
            expires = datetime.fromisoformat(expires_raw)
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=UTC)
        elif isinstance(expires_raw, datetime):
            expires = expires_raw
        else:
            expires = datetime.now(UTC) - timedelta(seconds=1)
        return cls(
            access_token=str(data.get("accessToken") or ""),
            refresh_token=data.get("refreshToken"),
            expires_at=expires,
            scopes=tuple(data.get("scopes") or ()),
            token_type=str(data.get("tokenType") or "Bearer"),
            id_token=data.get("idToken"),
        )


@dataclass(frozen=True)
class GoogleUserInfo:
    subject: str
    email: str | None = None
    email_verified: bool = False
    name: str | None = None
    picture: str | None = None


@dataclass
class GoogleOAuthClient:
    """Thin HTTP client over Google's OAuth endpoints."""

    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: tuple[str, ...] = field(default_factory=tuple)
    timeout_seconds: int = 30

    def authorization_url(
        self,
        *,
        state: str,
        code_challenge: str,
        login_hint: str | None = None,
    ) -> str:
        params: dict[str, str] = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            # `offline` gets a refresh token; `consent` forces one on every reconnect so a
            # stale/revoked token can be replaced. `select_account` is what shows the Gmail
            # account chooser the creator uses to pick which account to connect.
            "access_type": "offline",
            "prompt": "consent select_account",
            "include_granted_scopes": "true",
        }
        if login_hint:
            params["login_hint"] = login_hint
        return f"{AUTHORIZATION_ENDPOINT}?{urlencode(params)}"

    def exchange_code(self, *, code: str, code_verifier: str) -> OAuthTokenSet:
        response = requests.post(
            TOKEN_ENDPOINT,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "code_verifier": code_verifier,
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri,
            },
            timeout=self.timeout_seconds,
        )
        payload = self._json(response, "Google rejected the authorization code.")
        return self._token_set(payload)

    def refresh(self, *, refresh_token: str) -> OAuthTokenSet:
        response = requests.post(
            TOKEN_ENDPOINT,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=self.timeout_seconds,
        )
        payload = self._json(response, "Google rejected the refresh token.")
        tokens = self._token_set(payload)
        # Google omits the refresh token on refresh responses; keep the original.
        if tokens.refresh_token is None:
            return OAuthTokenSet(
                access_token=tokens.access_token,
                refresh_token=refresh_token,
                expires_at=tokens.expires_at,
                scopes=tokens.scopes or self.scopes,
                token_type=tokens.token_type,
                id_token=tokens.id_token,
            )
        return tokens

    def userinfo(self, *, access_token: str) -> GoogleUserInfo:
        response = requests.get(
            USERINFO_ENDPOINT,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=self.timeout_seconds,
        )
        payload = self._json(response, "Google did not return the account profile.")
        return GoogleUserInfo(
            subject=str(payload.get("sub") or ""),
            email=payload.get("email"),
            email_verified=bool(payload.get("email_verified")),
            name=payload.get("name"),
            picture=payload.get("picture"),
        )

    def revoke(self, *, token: str) -> None:
        """Best-effort revocation: a failure to revoke must not block deleting the record."""
        try:
            requests.post(
                REVOKE_ENDPOINT,
                data={"token": token},
                timeout=self.timeout_seconds,
            )
        except requests.RequestException:
            logger.warning("oauth: token revocation call failed", exc_info=True)

    def _token_set(self, payload: dict[str, Any]) -> OAuthTokenSet:
        expires_in = int(payload.get("expires_in") or 3600)
        scopes = tuple(str(payload.get("scope") or "").split())
        return OAuthTokenSet(
            access_token=str(payload.get("access_token") or ""),
            refresh_token=payload.get("refresh_token"),
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
            scopes=scopes or self.scopes,
            token_type=str(payload.get("token_type") or "Bearer"),
            id_token=payload.get("id_token"),
        )

    @staticmethod
    def _json(response: requests.Response, message: str) -> dict[str, Any]:
        if response.status_code >= 400:
            detail: Any = None
            try:
                detail = response.json()
            except ValueError:
                detail = response.text[:500]
            logger.warning("oauth: %s (%s) %s", message, response.status_code, detail)
            raise BadRequestError(
                message,
                code="OAUTH_EXCHANGE_FAILED",
                details={"status": response.status_code, "googleError": detail},
            )
        try:
            data = response.json()
        except ValueError as exc:  # pragma: no cover - malformed Google response
            raise BadRequestError(message, code="OAUTH_EXCHANGE_FAILED") from exc
        if not isinstance(data, dict):
            raise BadRequestError(message, code="OAUTH_EXCHANGE_FAILED")
        return data


def build_oauth_client(settings: Settings) -> GoogleOAuthClient:
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        raise BadRequestError(
            "YouTube is not configured on the server. Set the Google OAuth client id and "
            "secret.",
            code="OAUTH_NOT_CONFIGURED",
        )
    return GoogleOAuthClient(
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
        redirect_uri=oauth_redirect_uri(settings),
        scopes=tuple(settings.google_oauth_scopes),
    )


def oauth_redirect_uri(settings: Settings) -> str:
    if settings.google_oauth_redirect_uri:
        return settings.google_oauth_redirect_uri
    base = settings.api_public_base_url.rstrip("/")
    return f"{base}/api/connections/youtube/oauth/callback"
