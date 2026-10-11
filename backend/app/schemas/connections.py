"""Connected social accounts.

A *connection* is one external account the creator has authorized: for YouTube that is one
channel under one Google account. The creator can connect several (several Gmail accounts, or
several brand channels under one Google account) and pick which one a publish targets.

Tokens are never part of this public schema. They live encrypted in `connectionSecrets` and are
only read by the OAuth service.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ConnectionPlatform(StrEnum):
    youtube = "youtube"
    medium = "medium"
    substack = "substack"
    reddit = "reddit"


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
    #: Public profile/publication URL (Medium profile, Substack publication, Reddit user).
    profileUrl: str | None = None
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


class MediumConnectRequest(BaseModel):
    #: A pre-2025 integration token. Medium stopped issuing new ones in January
    #: 2025, so this only works for creators who already hold one.
    token: str = Field(min_length=10, max_length=500)


class SubstackConnectRequest(BaseModel):
    #: The `substack.sid` session cookie. A bare value, a `substack.sid=…` pair,
    #: or the whole cookie header (devtools → Copy all) all work.
    sid: str = Field(min_length=1, max_length=4000)
    #: Publication subdomain; omit to auto-detect. Only needed when the account
    #: has more than one publication.
    subdomain: str | None = Field(default=None, max_length=200)


class CrosspostRequest(BaseModel):
    #: Target platform: `medium`, `substack`, or `reddit`.
    platform: str = Field(max_length=40)
    #: Connection to post from (must belong to the platform).
    connectionId: str = Field(max_length=200)
    title: str = Field(min_length=1, max_length=300)
    #: Markdown body. Medium posts it as markdown; Substack converts a subset
    #: (headings, bold, italic, links, quotes) to its TipTap document; Reddit
    #: posts it as text.
    body: str = Field(min_length=1, max_length=60000)
    #: Per-platform options:
    #: - medium: `publishStatus` (draft | public | unlisted, default draft),
    #:   `canonicalUrl`, `tags` (up to 3).
    #: - substack: `subtitle`, `mode` (draft | publish | schedule, default
    #:   draft), `audience` (everyone | subscribers_only | paid_subscribers_only),
    #:   `send` (email subscribers on publish, default true),
    #:   `scheduleAt` (ISO-8601 UTC, required for schedule mode).
    #: - reddit: `subreddit` (default `u/{username}` — your own profile),
    #:   `kind` (self | link, default self), `url` (required for link),
    #:   `sendReplies`, `nsfw`, `spoiler`.
    options: dict[str, Any] = Field(default_factory=dict)


class CrosspostResult(BaseModel):
    platform: str
    connectionId: str
    #: Medium post id, Reddit thing id, or Substack draft id.
    externalId: str
    #: Canonical URL, or the Substack draft dashboard URL for drafts.
    url: str
    #: `draft` (Medium/Substack draft), `published` (live), `scheduled`.
    status: str
    title: str


class SyncCrosspostRequest(BaseModel):
    """Push the current title/body into the linked platform draft.

    The connection comes from the stored link (recorded when the draft was
    posted), so only platform + content are sent. Today only Substack drafts
    (`draft`/`scheduled`) are updatable.
    """

    platform: str = Field(max_length=40)
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=60000)


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
