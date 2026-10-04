"""Read a connected channel's existing videos and turn them into style signals / RAG context.

The YouTube connector lists a channel's published videos cheaply (uploads playlist -> videos.list).
This service persists a compact copy per video under the connection, builds an aggregate style
summary, and retrieves the most relevant past videos for a query so the draft writer can match the
creator's established voice.

Everything lives under `users/{uid}/connections/{id}/contentItems`, so the existing recursive
project/account delete covers it.
"""

import logging
import re
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from app.config import Settings
from app.connectors.youtube import YouTubeConnector
from app.errors import BadRequestError
from app.schemas.connections import (
    ChannelContentProfile,
    ContentItem,
    ContentStyleSummary,
)
from app.services.connection_service import ConnectionService
from app.services.firestore_service import (
    FirestoreClient,
    connection_path,
    content_item_path,
    content_items_collection_path,
)

logger = logging.getLogger(__name__)

_WORD = re.compile(r"[A-Za-z0-9']+")
_HASHTAG = re.compile(r"#\w+")
_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\u2600-\u27BF\u2190-\u21FF\u2B00-\u2BFF]"
)
_STOPWORDS = frozenset(
    {
        "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "for", "with", "at", "by",
        "from", "is", "are", "was", "were", "be", "been", "this", "that", "these", "those", "it",
        "its", "as", "your", "you", "my", "i", "we", "our", "how", "what", "why", "when", "where",
        "who", "which", "do", "does", "did", "can", "will", "just", "so", "if", "then", "than",
        "too", "very", "about", "into", "over", "after", "before", "up", "down", "out", "off",
        "not", "no", "yes", "get", "got", "make", "made", "use", "using", "new", "one", "two",
    }
)


def _stem(token: str) -> str:
    """Very light suffix strip so `invest`/`invested`/`investing` collapse together."""
    for suffix in ("ing", "ed", "s"):
        if token.endswith(suffix) and len(token) >= len(suffix) + 3:
            return token[: -len(suffix)]
    return token


def _tokens(text: str) -> list[str]:
    return [
        _stem(token)
        for token in _WORD.findall(text.lower())
        if len(token) > 2 and token not in _STOPWORDS
    ]


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _to_content_item(video_id: str, data: dict[str, Any]) -> ContentItem:
    return ContentItem(
        videoId=video_id,
        title=str(data.get("title") or ""),
        description=str(data.get("description") or ""),
        tags=[str(tag) for tag in (data.get("tags") or [])],
        publishedAt=_parse_dt(data.get("publishedAt")),
        durationSeconds=data.get("durationSeconds"),
        viewCount=data.get("viewCount"),
        likeCount=data.get("likeCount"),
        commentCount=data.get("commentCount"),
        thumbnailUrl=data.get("thumbnailUrl"),
        hasCustomThumbnail=data.get("hasCustomThumbnail"),
        language=data.get("language"),
    )


def build_style_summary(items: list[ContentItem]) -> ContentStyleSummary:
    """Deterministic aggregate patterns across a channel's published videos."""
    if not items:
        return ContentStyleSummary()
    n = len(items)
    with_number = sum(1 for item in items if re.search(r"\d", item.title))
    with_emoji = sum(1 for item in items if _EMOJI.search(item.title))
    with_hashtag = sum(1 for item in items if _HASHTAG.search(item.description))
    openers = Counter(
        _WORD.findall(item.title)[0].lower()
        for item in items
        if _WORD.findall(item.title)
    )
    tags = Counter(tag.lower() for item in items for tag in item.tags)
    dates = sorted(item.publishedAt for item in items if item.publishedAt)
    videos_per_month = 0.0
    if len(dates) >= 2:
        span_days = max(1, (dates[-1] - dates[0]).days)
        videos_per_month = round(len(dates) / (span_days / 30.44), 1)
    return ContentStyleSummary(
        videoCount=n,
        avgTitleWords=round(sum(len(item.title.split()) for item in items) / n, 1),
        titleWithNumberPct=round(100 * with_number / n),
        titleWithEmojiPct=round(100 * with_emoji / n),
        avgDescriptionChars=round(sum(len(item.description) for item in items) / n),
        descriptionWithHashtagPct=round(100 * with_hashtag / n),
        videosPerMonth=videos_per_month,
        commonTitleOpeners=[word for word, _ in openers.most_common(5)],
        topTags=[tag for tag, _ in tags.most_common(12)],
    )


def retrieve_examples(
    items: list[ContentItem], query: str, *, k: int = 5
) -> list[ContentItem]:
    """Lexical retrieval: rank past videos by token overlap with the query (title weighted)."""
    query_tokens = set(_tokens(query))
    if not query_tokens:
        return items[:k]

    def score(item: ContentItem) -> float:
        return (
            3.0 * len(query_tokens & set(_tokens(item.title)))
            + 2.0 * len(query_tokens & set(_tokens(" ".join(item.tags))))
            + 1.0 * len(query_tokens & set(_tokens(item.description)))
        )

    scored = sorted(
        ((score(item), item) for item in items),
        key=lambda pair: pair[0],
        reverse=True,
    )
    positive = [item for value, item in scored if value > 0]
    return (positive or [item for _, item in scored])[:k]


class ChannelContentService:
    def __init__(
        self,
        client: FirestoreClient,
        *,
        connections: ConnectionService,
        connector_factory: Any | None = None,
        settings: Settings,
    ) -> None:
        self.client = client
        self.connections = connections
        self.settings = settings
        self._connector_factory = connector_factory

    def _connector(self) -> YouTubeConnector:
        if self._connector_factory is not None:
            return self._connector_factory()
        return YouTubeConnector(
            client_id=self.settings.google_oauth_client_id or "",
            client_secret=self.settings.google_oauth_client_secret or "",
        )

    # ------------------------------------------------------------------ sync

    def sync(self, *, owner_uid: str, connection_id: str) -> ChannelContentProfile:
        """Read the channel's published videos back into `contentItems`."""
        connection = self.connections.get(owner_uid=owner_uid, connection_id=connection_id)
        tokens = self.connections.tokens_for_use(
            owner_uid=owner_uid, connection_id=connection_id
        )
        connector = self._connector()

        uploads = connection.uploadsPlaylistId
        if not uploads:
            channel = connector.refresh_channel(tokens, connection.externalAccountId)
            uploads = channel.uploads_playlist_id
            if uploads:
                self.client.update_document(
                    connection_path(owner_uid, connection_id),
                    {"uploadsPlaylistId": uploads},
                )
        if not uploads:
            raise BadRequestError(
                "This channel's uploads playlist is unavailable.",
                code="CHANNEL_CONTENT_UNAVAILABLE",
            )

        videos = connector.list_videos(
            tokens,
            uploads_playlist_id=uploads,
            max_videos=self.settings.channel_content_max_videos,
        )
        now = datetime.now(UTC)
        for video in videos:
            self.client.set_document(
                content_item_path(owner_uid, connection_id, video.video_id),
                {
                    "ownerUid": owner_uid,
                    "connectionId": connection_id,
                    "videoId": video.video_id,
                    "title": video.title,
                    "description": video.description,
                    "tags": list(video.tags),
                    "publishedAt": _parse_dt(video.published_at),
                    "durationSeconds": video.duration_seconds,
                    "viewCount": video.view_count,
                    "likeCount": video.like_count,
                    "commentCount": video.comment_count,
                    "thumbnailUrl": video.thumbnail_url,
                    "hasCustomThumbnail": video.has_custom_thumbnail,
                    "language": video.language,
                    "updatedAt": now,
                },
            )
        self.client.update_document(
            connection_path(owner_uid, connection_id),
            {
                "contentSyncedAt": now,
                "contentItemCount": len(videos),
                "updatedAt": now,
            },
        )
        return self.profile(owner_uid=owner_uid, connection_id=connection_id)

    # ------------------------------------------------------------------ reads

    def list_items(
        self, *, owner_uid: str, connection_id: str, limit: int = 200
    ) -> list[ContentItem]:
        self.connections.get(owner_uid=owner_uid, connection_id=connection_id)
        rows = self.client.query_collection(
            content_items_collection_path(owner_uid, connection_id),
            filters=[],
            order_by=[("publishedAt", "DESCENDING")],
            limit=limit,
            offset=0,
        )
        return [
            _to_content_item(video_id, data)
            for video_id, data in rows
            if data.get("ownerUid") == owner_uid
        ]

    def profile(self, *, owner_uid: str, connection_id: str) -> ChannelContentProfile:
        connection = self.connections.get(owner_uid=owner_uid, connection_id=connection_id)
        items = self.list_items(owner_uid=owner_uid, connection_id=connection_id)
        top = sorted(items, key=lambda item: item.viewCount or 0, reverse=True)[:5]
        return ChannelContentProfile(
            connectionId=connection_id,
            syncedAt=connection.contentSyncedAt,
            itemCount=connection.contentItemCount or len(items),
            style=build_style_summary(items),
            topVideos=top,
            recentItems=items[:20],
        )

    # ------------------------------------------------------------------ RAG

    def primary_connection_id(self, owner_uid: str) -> str | None:
        """The connection whose content was synced most recently, if any."""
        candidates = [
            connection
            for connection in self.connections.list(owner_uid=owner_uid)
            if connection.contentSyncedAt is not None
        ]
        if not candidates:
            return None
        candidates.sort(
            key=lambda connection: (
                connection.contentSyncedAt.timestamp()
                if connection.contentSyncedAt
                else 0.0
            ),
            reverse=True,
        )
        return candidates[0].connectionId

    def build_context(
        self,
        *,
        owner_uid: str,
        connection_id: str,
        query: str,
        k: int = 5,
    ) -> dict[str, Any] | None:
        """Style summary + the k most query-relevant past videos, for the writer prompt."""
        items = self.list_items(owner_uid=owner_uid, connection_id=connection_id, limit=200)
        if not items:
            return None
        examples = retrieve_examples(items, query, k=k)
        return {
            "style": build_style_summary(items).model_dump(mode="json"),
            "examples": [example.model_dump(mode="json") for example in examples],
        }

    def build_context_for_user(
        self, owner_uid: str, *, query: str, k: int = 5
    ) -> dict[str, Any] | None:
        """Best-effort creator context for the user's most recently synced channel."""
        try:
            connection_id = self.primary_connection_id(owner_uid)
            if connection_id is None:
                return None
            return self.build_context(
                owner_uid=owner_uid,
                connection_id=connection_id,
                query=query,
                k=k,
            )
        except Exception:  # noqa: BLE001 - context is an enhancement, never a blocker
            logger.warning("content: could not build creator context", exc_info=True)
            return None
