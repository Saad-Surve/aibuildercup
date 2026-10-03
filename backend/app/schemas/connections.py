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
