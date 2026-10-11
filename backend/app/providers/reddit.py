"""Reddit provider: OAuth client + identity + submit over the official Data API.

Free tier is 100 queries/minute per OAuth client id for personal,
non-commercial use; commercial use needs a Reddit contract. Auth is a standard
confidential web-app code flow (`duration=permanent` so refresh tokens keep
working); access tokens live ~1 hour. Every call carries Reddit's required
unique User-Agent.

Caveat: since late 2025 some new apps are funneled through manual Developer
Support pre-approval, so self-service registration at reddit.com/prefs/apps can
stall — the setup doc covers the fallback.

Feature code calls this provider, never `requests` against Reddit directly.
"""

import base64
import secrets
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import requests

from app.connectors.base import ConnectorError

_AUTHORIZE_URL = "https://www.reddit.com/api/v1/authorize"
_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
_API_BASE = "https://oauth.reddit.com"
_TIMEOUT_SECONDS = 30
_USER_AGENT = "web:habeas-codus:v1.0 (by /u/habeas-codus)"


def _translate(status: int, action: str, body: Any = None) -> ConnectorError:
    if status in (401, 403):
        return ConnectorError(
            "Reddit rejected the credentials. Reconnect the account.",
            code="REDDIT_UNAUTHORIZED",
            details={"status": status},
        )
    if status == 429:
        return ConnectorError(
            "Reddit rate-limited the app (100/min). Wait and retry.",
            code="REDDIT_RATE_LIMITED",
            retryable=True,
            details={"status": status},
        )
    detail = ""
    if isinstance(body, dict):
        errors = body.get("json", {}).get("errors") or []
        if errors:
            detail = "; ".join(str(part) for error in errors[:2] for part in error[:2])
    message = f"Reddit could not {action}.{f' {detail}' if detail else ''}"
    return ConnectorError(
        message,
        code="REDDIT_FAILED",
        retryable=status >= 500,
        details={"status": status},
    )


@dataclass(frozen=True)
class RedditTokens:
    access_token: str
    refresh_token: str | None
    expires_in: int


@dataclass(frozen=True)
class RedditIdentity:
    account_id: str
    username: str
    profile_url: str
    avatar_url: str | None = None
    is_employee: bool = False


@dataclass(frozen=True)
class RedditPost:
    thing_id: str
    url: str


class RedditOAuthClient:
    """Thin HTTP client over Reddit's OAuth2 + submit endpoints."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scopes: tuple[str, ...] = ("identity", "submit", "read"),
        timeout_seconds: int = _TIMEOUT_SECONDS,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes
        self.timeout_seconds = timeout_seconds

    @classmethod
    def api(cls) -> "RedditOAuthClient":
        """Bearer-only client for `me`/`submit` when tokens already exist."""
        return cls(client_id="", client_secret="", redirect_uri="")

    def authorization_url(self, *, state: str) -> str:
        return f"{_AUTHORIZE_URL}?{urlencode(
            {
                'client_id': self.client_id,
                'response_type': 'code',
                'state': state,
                'redirect_uri': self.redirect_uri,
                'duration': 'permanent',
                'scope': ' '.join(self.scopes),
            }
        )}"

    def _basic_auth(self) -> str:
        raw = f"{self.client_id}:{self.client_secret}".encode()
        return f"Basic {base64.b64encode(raw).decode()}"

    def exchange_code(self, *, code: str) -> RedditTokens:
        try:
            response = requests.post(
                _TOKEN_URL,
                headers={
                    "Authorization": self._basic_auth(),
                    "User-Agent": _USER_AGENT,
                },
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                },
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise ConnectorError(
                "Could not reach Reddit. Check your connection and retry.",
                code="REDDIT_UNREACHABLE",
                retryable=True,
            ) from exc
        try:
            data = response.json()
        except ValueError:
            data = {}
        if response.status_code != 200 or not data.get("access_token"):
            raise _translate(response.status_code, "exchange the Reddit code", data)
        return RedditTokens(
            access_token=str(data["access_token"]),
            refresh_token=data.get("refresh_token"),
            expires_in=int(data.get("expires_in", 3600)),
        )

    def refresh(self, *, refresh_token: str) -> RedditTokens:
        try:
            response = requests.post(
                _TOKEN_URL,
                headers={
                    "Authorization": self._basic_auth(),
                    "User-Agent": _USER_AGENT,
                },
                data={"grant_type": "refresh_token", "refresh_token": refresh_token},
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise ConnectorError(
                "Could not reach Reddit. Check your connection and retry.",
                code="REDDIT_UNREACHABLE",
                retryable=True,
            ) from exc
        try:
            data = response.json()
        except ValueError:
            data = {}
        if response.status_code != 200 or not data.get("access_token"):
            raise _translate(response.status_code, "refresh the Reddit session", data)
        return RedditTokens(
            access_token=str(data["access_token"]),
            refresh_token=data.get("refresh_token", refresh_token),
            expires_in=int(data.get("expires_in", 3600)),
        )

    def me(self, access_token: str) -> RedditIdentity:
        try:
            response = requests.get(
                f"{_API_BASE}/api/v1/me",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "User-Agent": _USER_AGENT,
                },
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise ConnectorError(
                "Could not reach Reddit. Check your connection and retry.",
                code="REDDIT_UNREACHABLE",
                retryable=True,
            ) from exc
        if response.status_code != 200:
            raise _translate(response.status_code, "read the Reddit account")
        try:
            data = response.json()
        except ValueError as exc:
            raise ConnectorError(
                "Reddit returned an unreadable response.",
                code="REDDIT_BAD_RESPONSE",
            ) from exc
        username = str(data.get("name") or "")
        return RedditIdentity(
            account_id=str(data.get("id") or ""),
            username=username,
            profile_url=f"https://www.reddit.com/user/{username}",
            avatar_url=(data.get("snoovatar_img") or data.get("icon_img") or None),
            is_employee=bool(data.get("is_employee")),
        )

    def submit(
        self,
        access_token: str,
        *,
        subreddit: str,
        title: str,
        kind: str = "self",
        text: str = "",
        url: str | None = None,
        send_replies: bool = True,
        nsfw: bool = False,
        spoiler: bool = False,
    ) -> RedditPost:
        """Submit a text (`self`) or link post. Returns the permalink."""
        if kind not in ("self", "link"):
            raise ConnectorError(
                "Reddit posts here are text (self) or link posts.",
                code="REDDIT_BAD_KIND",
                details={"kind": kind},
            )
        if kind == "link" and not url:
            raise ConnectorError(
                "A link post needs a URL.",
                code="REDDIT_BAD_URL",
            )
        payload: dict[str, Any] = {
            "api_type": "json",
            "sr": subreddit,
            "title": title,
            "kind": kind,
            "sendreplies": send_replies,
            "nsfw": nsfw,
            "spoiler": spoiler,
        }
        if kind == "self":
            payload["text"] = text
        else:
            payload["url"] = url
        try:
            response = requests.post(
                f"{_API_BASE}/api/submit",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "User-Agent": _USER_AGENT,
                },
                data=payload,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise ConnectorError(
                "Could not reach Reddit. Check your connection and retry.",
                code="REDDIT_UNREACHABLE",
                retryable=True,
            ) from exc
        try:
            data = response.json()
        except ValueError:
            data = {}
        if response.status_code != 200:
            raise _translate(response.status_code, "submit the Reddit post", data)
        errors = (data.get("json") or {}).get("errors") or []
        if errors:
            raise _translate(200, "submit the Reddit post", data)
        result = (data.get("json") or {}).get("data") or {}
        post_url = str(result.get("url") or "")
        if not post_url:
            raise ConnectorError(
                "Reddit accepted the post but returned no URL.",
                code="REDDIT_BAD_RESPONSE",
            )
        if post_url.startswith("/"):
            post_url = f"https://www.reddit.com{post_url}"
        return RedditPost(
            thing_id=str(result.get("name") or result.get("id") or ""),
            url=post_url,
        )


def generate_state() -> str:
    return secrets.token_urlsafe(32)
