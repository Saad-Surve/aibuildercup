"""Social connector interfaces.

A connector is the provider seam for an external platform. Feature code depends on the
`SocialConnector` protocol (or the concrete `YouTubeConnector`), never on a Google SDK.
"""

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from app.services.oauth_service import OAuthTokenSet


class ConnectorError(Exception):
    """A platform call failed. `retryable` tells the worker whether to try again."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "CONNECTOR_ERROR",
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.retryable = retryable
        self.details = details or {}


@dataclass(frozen=True)
class ChannelInfo:
    channel_id: str
    title: str
    handle: str | None = None
    thumbnail_url: str | None = None
    subscriber_count: int | None = None
    video_count: int | None = None
    uploads_playlist_id: str | None = None


@dataclass(frozen=True)
class UploadedVideo:
    video_id: str
    title: str
    privacy_status: str | None = None


@runtime_checkable
class SocialConnector(Protocol):
    def list_channels(self, tokens: OAuthTokenSet) -> list[ChannelInfo]: ...

    def refresh_channel(self, tokens: OAuthTokenSet, channel_id: str) -> ChannelInfo: ...

    def revoke(self, tokens: OAuthTokenSet) -> None: ...
