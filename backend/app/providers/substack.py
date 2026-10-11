"""Substack provider: identity + draft/publish/schedule over the internal API.

Substack has no official public write API. This drives the same cookie-
authenticated endpoints the web editor uses (`substack.sid` session cookie):
`POST {pub}/api/v1/drafts`, `PUT …/drafts/{id}`, `PUT …/drafts/{id}/publish`.
That is inherently fragile — cookies expire and internal endpoints move — so
every failure maps to `needs_reauth` upstream and the setup doc says so plainly.

Rate limit is ~1 request/second; calls here are single-shot, never looped.

Feature code calls this provider, never `requests` against Substack directly.
"""

import html
import re
from dataclasses import dataclass
from typing import Any

import requests

from app.connectors.base import ConnectorError

_TIMEOUT_SECONDS = 30

_AUDIENCES = ("everyone", "subscribers_only", "paid_subscribers_only")


def _translate(status: int, action: str) -> ConnectorError:
    if status in (401, 403):
        return ConnectorError(
            "Substack rejected the session. It expired or the cookie is wrong — "
            "reconnect with a fresh one.",
            code="SUBSTACK_UNAUTHORIZED",
            details={"status": status},
        )
    if status == 429:
        return ConnectorError(
            "Substack rate-limited the request (1/sec). Wait and retry.",
            code="SUBSTACK_RATE_LIMITED",
            retryable=True,
            details={"status": status},
        )
    return ConnectorError(
        f"Substack could not {action} (status {status}).",
        code="SUBSTACK_FAILED",
        retryable=status >= 500,
        details={"status": status},
    )


def markdown_to_substack_html(markdown: str) -> str:
    """Minimal Markdown → HTML for draft bodies: headings, bold, italic, links,
    paragraphs. Anything fancier stays literal text — safe, never broken HTML."""
    blocks: list[str] = []
    for chunk in re.split(r"\n{2,}", markdown.strip()):
        chunk = chunk.strip()
        if not chunk:
            continue
        heading = re.match(r"^(#{1,3})\s+(.*)$", chunk, re.DOTALL)
        if heading:
            level = len(heading.group(1)) + 1
            blocks.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            continue
        lines = [_inline(line) for line in chunk.split("\n") if line.strip()]
        if lines:
            blocks.append(f"<p>{'<br>'.join(lines)}</p>")
    return "".join(blocks) or "<p></p>"


def _inline(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", escaped)
    escaped = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', escaped
    )
    return escaped


@dataclass(frozen=True)
class SubstackPublication:
    publication_id: int
    name: str
    subdomain: str
    url: str


@dataclass(frozen=True)
class SubstackDraft:
    draft_id: int
    dashboard_url: str
    post_url: str | None = None


class SubstackProvider:
    """Thin HTTP client over Substack's cookie-authenticated internal API."""

    def __init__(self, *, timeout_seconds: int = _TIMEOUT_SECONDS) -> None:
        self.timeout_seconds = timeout_seconds

    def _cookies(self, sid: str) -> dict[str, str]:
        return {"substack.sid": sid}

    def _headers(self, origin: str) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": origin,
            "Referer": f"{origin}/publish",
        }

    #: `substack.sid` inside a pasted cookie header (the browser's "Copy all").
    _SID_IN_COOKIE = re.compile(r"(?:^|[;\s])substack\.sid=([^;]+)")

    def extract_sid(self, raw: str) -> str:
        """Pull the session id out of whatever the user pasted.

        Accepts a bare `substack.sid` value, a `substack.sid=…` pair, or the
        whole cookie header (devtools → Copy all), so nobody has to hunt for the
        exact field.
        """
        value = raw.strip().strip('"').strip()
        if not value:
            raise ConnectorError(
                "Paste your Substack session cookie.", code="SUBSTACK_BAD_COOKIE"
            )
        match = self._SID_IN_COOKIE.search(value)
        if match:
            value = match.group(1).strip()
        elif ";" in value or "=" in value:
            raise ConnectorError(
                "Could not find `substack.sid` in that cookie. Paste the whole "
                "cookie header, or just the substack.sid value.",
                code="SUBSTACK_BAD_COOKIE",
            )
        return value

    def list_publications(
        self, profile: dict[str, Any]
    ) -> list[SubstackPublication]:
        publications: list[SubstackPublication] = []
        for entry in profile.get("publicationUsers") or []:
            publication = entry.get("publication") or {}
            raw_id = publication.get("id")
            sub = str(publication.get("subdomain") or "")
            if raw_id is None or not sub:
                continue
            publications.append(
                SubstackPublication(
                    publication_id=int(raw_id),
                    name=str(publication.get("name") or sub),
                    subdomain=sub,
                    url=f"https://{sub}.substack.com",
                )
            )
        return publications

    def normalize_subdomain(self, value: str) -> str:
        """Accept `name`, `name.substack.com`, or a full URL; return `name`."""
        cleaned = value.strip().lower()
        cleaned = re.sub(r"^https?://", "", cleaned).split("/")[0]
        cleaned = re.sub(r"\.substack\.com$", "", cleaned)
        if not re.fullmatch(r"[a-z0-9-]+", cleaned):
            raise ConnectorError(
                "That does not look like a Substack subdomain.",
                code="SUBSTACK_BAD_SUBDOMAIN",
                details={"subdomain": value},
            )
        return cleaned

    def get_profile(self, sid: str) -> dict[str, Any]:
        """Validate the session and return the raw `/user/profile/self` payload."""
        try:
            response = requests.get(
                "https://substack.com/api/v1/user/profile/self",
                cookies=self._cookies(sid),
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise ConnectorError(
                "Could not reach Substack. Check your connection and retry.",
                code="SUBSTACK_UNREACHABLE",
                retryable=True,
            ) from exc
        if response.status_code != 200:
            raise _translate(response.status_code, "verify the session")
        try:
            return response.json()
        except ValueError as exc:
            raise ConnectorError(
                "Substack returned an unreadable response.",
                code="SUBSTACK_BAD_RESPONSE",
            ) from exc

    def pick_publication(
        self, profile: dict[str, Any], subdomain: str
    ) -> SubstackPublication:
        for publication in self.list_publications(profile):
            if publication.subdomain.lower() == subdomain:
                return publication
        raise ConnectorError(
            f"This Substack account has no publication at {subdomain}.substack.com.",
            code="SUBSTACK_NO_PUBLICATION",
            details={"subdomain": subdomain},
        )

    def create_draft(
        self,
        sid: str,
        *,
        subdomain: str,
        title: str,
        body_markdown: str,
        subtitle: str = "",
        audience: str = "everyone",
        schedule_at: str | None = None,
    ) -> SubstackDraft:
        if audience not in _AUDIENCES:
            raise ConnectorError(
                "Substack audience must be everyone, subscribers_only, or paid_subscribers_only.",
                code="SUBSTACK_BAD_AUDIENCE",
                details={"audience": audience},
            )
        origin = f"https://{subdomain}.substack.com"
        payload: dict[str, Any] = {
            "draft_title": title,
            "draft_subtitle": subtitle,
            "draft_body": markdown_to_substack_html(body_markdown),
            "type": "newsletter",
            "audience": audience,
        }
        if schedule_at:
            payload["schedule_at"] = schedule_at
        try:
            response = requests.post(
                f"{origin}/api/v1/drafts",
                cookies=self._cookies(sid),
                headers=self._headers(origin),
                json=payload,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise ConnectorError(
                "Could not reach Substack. Check your connection and retry.",
                code="SUBSTACK_UNREACHABLE",
                retryable=True,
            ) from exc
        if response.status_code not in (200, 201):
            raise _translate(response.status_code, "create the draft")
        try:
            data = response.json()
        except ValueError as exc:
            raise ConnectorError(
                "Substack returned an unreadable response.",
                code="SUBSTACK_BAD_RESPONSE",
            ) from exc
        draft_id = data.get("id")
        if not draft_id:
            raise ConnectorError(
                "Substack did not return a draft id.",
                code="SUBSTACK_BAD_RESPONSE",
            )
        return SubstackDraft(
            draft_id=int(draft_id),
            dashboard_url=f"{origin}/publish/post/{draft_id}",
            post_url=data.get("post_url") or data.get("url"),
        )

    def publish_draft(
        self,
        sid: str,
        *,
        subdomain: str,
        draft_id: int,
        send: bool,
    ) -> str | None:
        """Publish now. `send=True` emails subscribers — irreversible."""
        origin = f"https://{subdomain}.substack.com"
        try:
            response = requests.put(
                f"{origin}/api/v1/drafts/{draft_id}/publish",
                cookies=self._cookies(sid),
                headers=self._headers(origin),
                json={"send": send, "share_automatically": False},
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise ConnectorError(
                "Could not reach Substack. Check your connection and retry.",
                code="SUBSTACK_UNREACHABLE",
                retryable=True,
            ) from exc
        if response.status_code != 200:
            raise _translate(response.status_code, "publish the draft")
        try:
            data = response.json()
        except ValueError:
            return None
        return data.get("post_url") or data.get("url")
