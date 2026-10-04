"""Connected social accounts.

A *connection* is one external account the creator has authorized: for YouTube that is one
channel under one Google account. The creator can connect several (several Gmail accounts, or
several brand channels under one Google account) and pick which one a publish targets.

Tokens are never part of this public schema. They live encrypted in `connectionSecrets` and are
only read by the OAuth service.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ConnectionPlatform(StrEnum):
    youtube = "youtube"


class ConnectionStatus(StrEnum):
    pending = "pending"
    connected = "connected"
    needs_reauth = "needs_reauth"
    revoked = "revoked"
    error = "error"


class Connection(BaseModel):
    connectionId: str
    platform: ConnectionPlatform
    accountType: str = "channel"
    #: The channel title (e.g. "Priya Creates").
    displayName: str
    #: The YouTube channel id (`UC...`).
    externalAccountId: str
    externalHandle: str | None = None
    #: The channel's hidden "uploads" playlist, used to read back published videos cheaply.
    uploadsPlaylistId: str | None = None
    #: The Gmail account that owns/targets the channel, shown so the creator can tell
    #: two connections apart when the same Google account owns several channels.
    googleAccountEmail: str | None = None
    avatarUrl: str | None = None
    subscriberCount: int | None = None
    videoCount: int | None = None
    status: ConnectionStatus
    scopes: list[str] = Field(default_factory=list)
    lastSyncAt: datetime | None = None
    lastSyncStatus: str | None = None
    lastErrorCode: str | None = None
    #: When the channel's existing videos were last read back for style/RAG analysis.
    contentSyncedAt: datetime | None = None
    contentItemCount: int | None = None
    createdAt: datetime
    updatedAt: datetime


class ConnectionList(BaseModel):
    items: list[Connection]


class OAuthStartRequest(BaseModel):
    #: Optional email to prefill in Google's account chooser.
    loginHint: str | None = Field(default=None, max_length=320)
    #: Where the browser should land after the callback. Must be a path on the web app
    #: (`/projects/view/...`); the API validates it stays same-origin.
    redirectPath: str | None = Field(default=None, max_length=500)


class OAuthStartResponse(BaseModel):
    authorizationUrl: str
    state: str


class ConnectionSyncAccepted(BaseModel):
    connectionId: str
    status: str


class ContentItem(BaseModel):
    """One video already published on a connected channel, read back for style/RAG."""

    videoId: str
    title: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    publishedAt: datetime | None = None
    durationSeconds: int | None = None
    viewCount: int | None = None
    likeCount: int | None = None
    commentCount: int | None = None
    thumbnailUrl: str | None = None
    hasCustomThumbnail: bool | None = None
    language: str | None = None
    hasTranscript: bool = False


class ContentStyleSummary(BaseModel):
    """Aggregate patterns across a channel's published videos, for prompts and the UI."""

    videoCount: int = 0
    avgTitleWords: float = 0
    titleWithNumberPct: int = 0
    titleWithEmojiPct: int = 0
    avgDescriptionChars: int = 0
    descriptionWithHashtagPct: int = 0
    videosPerMonth: float = 0
    commonTitleOpeners: list[str] = Field(default_factory=list)
    topTags: list[str] = Field(default_factory=list)


class ChannelContentProfile(BaseModel):
    """A connected channel's read-back content plus aggregate style signals."""

    connectionId: str
    syncedAt: datetime | None = None
    itemCount: int = 0
    style: ContentStyleSummary = Field(default_factory=ContentStyleSummary)
    topVideos: list[ContentItem] = Field(default_factory=list)
    recentItems: list[ContentItem] = Field(default_factory=list)


class MetricValue(BaseModel):
    metric: str
    value: float


class BreakdownRow(BaseModel):
    label: str
    value: float


class AudienceBreakdown(BaseModel):
    dimension: str
    rows: list[BreakdownRow] = Field(default_factory=list)


class AudienceProfile(BaseModel):
    """YouTube Analytics signals for the connected channel (last `periodDays`)."""

    connectionId: str
    syncedAt: datetime | None = None
    periodDays: int = 28
    summary: list[MetricValue] = Field(default_factory=list)
    demographics: AudienceBreakdown | None = None
    trafficSources: AudienceBreakdown | None = None
    topCountries: AudienceBreakdown | None = None
    topVideos: list[ContentItem] = Field(default_factory=list)


class SeedYouTubeContentRequest(BaseModel):
    #: Seed channel slug, e.g. `lawrencesystems`, `psych2go`, `thehumanistreport`.
    channel: str = Field(default="lawrencesystems", max_length=64)


class SeedYouTubeContentResult(BaseModel):
    connectionId: str
    channel: str
    itemCount: int
    license: str = ""
    attribution: str = ""
