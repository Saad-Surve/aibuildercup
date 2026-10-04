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


@dataclass(frozen=True)
class ChannelVideo:
    """A video already published on a connected channel, read back for style/RAG analysis."""

    video_id: str
    title: str
    description: str = ""
    tags: tuple[str, ...] = ()
    published_at: str | None = None
    duration_seconds: int | None = None
    view_count: int | None = None
    like_count: int | None = None
    comment_count: int | None = None
    thumbnail_url: str | None = None
    has_custom_thumbnail: bool | None = None
    language: str | None = None
    has_captions: bool = False


@dataclass(frozen=True)
class CaptionTrack:
    """One caption track on a video the authenticated user can edit."""

    caption_id: str
    language: str
    name: str
    track_kind: str
    is_auto_synced: bool


@dataclass(frozen=True)
class AnalyticsReport:
    """A raw YouTube Analytics report: column headers plus rows."""

    headers: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]


@runtime_checkable
class SocialConnector(Protocol):
    def list_channels(self, tokens: OAuthTokenSet) -> list[ChannelInfo]: ...

    def refresh_channel(self, tokens: OAuthTokenSet, channel_id: str) -> ChannelInfo: ...

    def list_videos(
        self,
        tokens: OAuthTokenSet,
        *,
        uploads_playlist_id: str,
        max_videos: int = 50,
    ) -> list[ChannelVideo]: ...

    def revoke(self, tokens: OAuthTokenSet) -> None: ...
