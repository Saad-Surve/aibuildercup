"""Medium provider: identity check + post creation over the legacy API.

Medium's official API is deprecated and no new integration tokens have been
issued since January 2025 — this only works for creators who already hold a
token. Existing tokens still authenticate (`GET /v1/me`, `POST
/v1/users/{id}/posts` with `contentFormat: markdown`). There is no token
refresh and no revoke endpoint; deleting the connection just drops the token.

Feature code calls this provider, never `requests` against Medium directly.
"""

from dataclasses import dataclass
from typing import Any

import requests

from app.connectors.base import ConnectorError

_API_BASE = "https://api.medium.com/v1"
_TIMEOUT_SECONDS = 30

_PUBLISH_STATUSES = ("public", "draft", "unlisted")
_CONTENT_FORMATS = ("html", "markdown")


def _translate(status: int, body: Any, action: str) -> ConnectorError:
    if status in (401, 403):
        return ConnectorError(
            "Medium rejected the token. It may be revoked or expired — "
            "reconnect with a valid integration token.",
            code="MEDIUM_UNAUTHORIZED",
            details={"status": status},
        )
    if status == 429:
        return ConnectorError(
            "Medium rate-limited the request. Wait a minute and retry.",
            code="MEDIUM_RATE_LIMITED",
            retryable=True,
            details={"status": status},
        )
    errors = ""
    if isinstance(body, dict):
        raw = body.get("errors")
        if isinstance(raw, list):
            errors = "; ".join(str(item.get("message", item)) for item in raw[:3])
    return ConnectorError(
        f"Medium could not {action}.{f' {errors}' if errors else ''}",
        code="MEDIUM_FAILED",
        retryable=status >= 500,
        details={"status": status},
    )


@dataclass(frozen=True)
class MediumIdentity:
    user_id: str
    name: str
    username: str
    profile_url: str
    image_url: str | None = None


@dataclass(frozen=True)
class MediumPost:
    post_id: str
    url: str
    publish_status: str


class MediumProvider:
    """Thin HTTP client over Medium's legacy publishing API."""

    def __init__(self, *, timeout_seconds: int = _TIMEOUT_SECONDS) -> None:
        self.timeout_seconds = timeout_seconds

    def _headers(self, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Charset": "utf-8",
        }

    def get_me(self, token: str) -> MediumIdentity:
        try:
            response = requests.get(
                f"{_API_BASE}/me",
                headers=self._headers(token),
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise ConnectorError(
                "Could not reach Medium. Check your connection and retry.",
                code="MEDIUM_UNREACHABLE",
                retryable=True,
            ) from exc
        try:
            data = response.json().get("data", {})
        except ValueError:
            data = {}
        if response.status_code != 200 or not data.get("id"):
            raise _translate(response.status_code, data, "verify the token")
        username = str(data.get("username", ""))
        return MediumIdentity(
            user_id=str(data.get("id")),
            name=str(data.get("name") or username or "Medium author"),
            username=username,
            profile_url=str(data.get("url") or f"https://medium.com/@{username}"),
            image_url=data.get("imageUrl"),
        )

    def create_post(
        self,
        token: str,
        *,
        author_id: str,
        title: str,
        content: str,
        content_format: str = "markdown",
        publish_status: str = "draft",
        canonical_url: str | None = None,
        tags: list[str] | None = None,
    ) -> MediumPost:
        """Create a post on the author's profile. Defaults to a draft (safe)."""
        if content_format not in _CONTENT_FORMATS:
            raise ConnectorError(
                "Medium content must be markdown or html.",
                code="MEDIUM_BAD_FORMAT",
                details={"contentFormat": content_format},
            )
        if publish_status not in _PUBLISH_STATUSES:
            raise ConnectorError(
                "Medium publish status must be public, draft, or unlisted.",
                code="MEDIUM_BAD_STATUS",
                details={"publishStatus": publish_status},
            )
        clean_tags = [tag.strip().lower() for tag in (tags or []) if tag.strip()][:3]
        payload: dict[str, Any] = {
            "title": title,
            "contentFormat": content_format,
            "content": content,
            "publishStatus": publish_status,
        }
        if canonical_url:
            payload["canonicalUrl"] = canonical_url
        if clean_tags:
            payload["tags"] = clean_tags
        try:
            response = requests.post(
                f"{_API_BASE}/users/{author_id}/posts",
                headers=self._headers(token),
                json=payload,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise ConnectorError(
                "Could not reach Medium. Check your connection and retry.",
                code="MEDIUM_UNREACHABLE",
                retryable=True,
            ) from exc
        try:
            data = response.json().get("data", {})
        except ValueError:
            data = {}
        if response.status_code not in (200, 201) or not data.get("id"):
            raise _translate(response.status_code, data, "create the post")
        return MediumPost(
            post_id=str(data.get("id")),
            url=str(data.get("url") or ""),
            publish_status=str(data.get("publishStatus") or publish_status),
        )
