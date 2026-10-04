"""Read a connected channel's existing videos and turn them into style signals / RAG context.

The YouTube connector lists a channel's published videos cheaply (uploads playlist -> videos.list).
This service persists a compact copy per video under the connection, pulls caption transcripts for a
capped number of them, reads YouTube Analytics for the audience profile, and retrieves the most
relevant past videos for a query so the draft writer can match the creator's established voice.

Everything lives under `users/{uid}/connections/{id}/contentItems`, so the existing recursive
project/account delete covers it.
"""

import logging
import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

import requests

from app.config import Settings
from app.connectors.base import CaptionTrack, ChannelVideo
from app.connectors.youtube import YouTubeConnector
from app.errors import BadRequestError
from app.providers.base import MediaPart
from app.schemas.connections import (
    AudienceBreakdown,
    AudienceProfile,
    BreakdownRow,
    ChannelContentProfile,
    ContentItem,
    ContentStyleSummary,
    MetricValue,
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
        hasTranscript=bool(data.get("transcript")),
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


def _srt_to_text(srt: str) -> str:
    """Flatten an SRT/VTT caption track to a single plain-text string."""
    lines: list[str] = []
    for raw in srt.replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        if not line or line.isdigit() or "-->" in line or line.upper() == "WEBVTT":
            continue
        lines.append(re.sub(r"<[^>]+>", "", line))
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def _pick_caption_track(
    tracks: list[CaptionTrack], language: str | None
) -> CaptionTrack | None:
    """Prefer a creator-uploaded track in the video's language, then English, then any."""
    if not tracks:
        return None
    prefix = language.lower()[:2] if language else ""

    def in_language(track: CaptionTrack) -> bool:
        return bool(prefix) and track.language.lower().startswith(prefix)

    def in_english(track: CaptionTrack) -> bool:
        return track.language.lower().startswith("en")

    manual = [track for track in tracks if not track.is_auto_synced]
    auto = [track for track in tracks if track.is_auto_synced]
    for pool in (manual, auto):
        for predicate in (in_language, in_english):
            for track in pool:
                if predicate(track):
                    return track
    return (manual or auto)[0]


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
        """Read the channel's published videos (and a capped set of transcripts) into Firestore."""
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
                    "hasCaptions": video.has_captions,
                    "updatedAt": now,
                },
            )

        transcripts = self._fetch_transcripts(
            owner_uid=owner_uid,
            connection_id=connection_id,
            videos=videos,
            tokens=tokens,
            connector=connector,
        )
        self.client.update_document(
            connection_path(owner_uid, connection_id),
            {
                "contentSyncedAt": now,
                "contentItemCount": len(videos),
                "contentTranscriptCount": transcripts,
                "updatedAt": now,
            },
        )
        return self.profile(owner_uid=owner_uid, connection_id=connection_id)

    def _fetch_transcripts(
        self,
        *,
        owner_uid: str,
        connection_id: str,
        videos: list[ChannelVideo],
        tokens: Any,
        connector: YouTubeConnector,
    ) -> int:
        """Download caption tracks for up to N videos that have captions and no stored transcript.

        `captions.download` costs 200 quota units each, so this is capped and skips videos that
        already have a transcript (re-syncs are then free).
        """
        fetched = 0
        for video in videos:
            if fetched >= self.settings.channel_transcript_max_videos:
                break
            if not video.has_captions:
                continue
            existing = self.client.get_document(
                content_item_path(owner_uid, connection_id, video.video_id)
            )
            if existing and existing.get("transcript"):
                continue
            try:
                tracks = connector.list_captions(tokens, video_id=video.video_id)
                track = _pick_caption_track(tracks, video.language)
                if track is None:
                    continue
                raw = connector.download_caption(
                    tokens, caption_id=track.caption_id, tfmt="srt"
                )
            except Exception:  # noqa: BLE001 - one bad video must not fail the sync
                logger.warning(
                    "content: transcript fetch failed for %s", video.video_id, exc_info=True
                )
                continue
            text = _srt_to_text(raw)[: self.settings.channel_transcript_max_chars]
            if not text:
                continue
            self.client.update_document(
                content_item_path(owner_uid, connection_id, video.video_id),
                {
                    "transcript": text,
                    "transcriptLanguage": track.language,
                    "updatedAt": datetime.now(UTC),
                },
            )
            fetched += 1
        return fetched

    # ------------------------------------------------------------------ audience

    def sync_audience(self, *, owner_uid: str, connection_id: str) -> AudienceProfile:
        """Read YouTube Analytics (summary, demographics, traffic, top videos) for the channel."""
        self.connections.get(owner_uid=owner_uid, connection_id=connection_id)
        tokens = self.connections.tokens_for_use(
            owner_uid=owner_uid, connection_id=connection_id
        )
        connector = self._connector()
        days = self.settings.channel_analytics_days
        end = datetime.now(UTC).date()
        start = end - timedelta(days=days)
        start_s, end_s = start.isoformat(), end.isoformat()

        profile = AudienceProfile(connectionId=connection_id, periodDays=days)
        summary = connector.query_analytics(
            tokens,
            metrics=(
                "views,estimatedMinutesWatched,averageViewDuration,"
                "subscribersGained,subscribersLost,likes,comments,shares"
            ),
            start_date=start_s,
            end_date=end_s,
        )
        if summary.rows:
            row = summary.rows[0]
            profile.summary = [
                MetricValue(metric=summary.headers[i], value=_float(row[i]))
                for i in range(len(summary.headers))
            ]

        profile.demographics = self._breakdown(
            connector, tokens, "ageGroup,gender", "viewerPercentage", start_s, end_s
        )
        profile.trafficSources = self._breakdown(
            connector, tokens, "insightTrafficSourceType", "views", start_s, end_s
        )
        profile.topCountries = self._breakdown(
            connector, tokens, "country", "views", start_s, end_s
        )

        top = connector.query_analytics(
            tokens,
            metrics="views",
            dimensions="video",
            start_date=start_s,
            end_date=end_s,
            sort="-views",
            max_results=5,
        )
        top_ids = [str(row[0]) for row in top.rows]
        items = {item.videoId: item for item in self.list_items(
            owner_uid=owner_uid, connection_id=connection_id, limit=200
        )}
        profile.topVideos = [items[vid] for vid in top_ids if vid in items]

        now = datetime.now(UTC)
        profile.syncedAt = now
        self.client.update_document(
            connection_path(owner_uid, connection_id),
            {
                "audienceSyncedAt": now,
                "audienceProfile": profile.model_dump(mode="json"),
                "updatedAt": now,
            },
        )
        return profile

    def _breakdown(
        self,
        connector: YouTubeConnector,
        tokens: Any,
        dimensions: str,
        metric: str,
        start_date: str,
        end_date: str,
    ) -> AudienceBreakdown:
        report = connector.query_analytics(
            tokens,
            metrics=metric,
            dimensions=dimensions,
            start_date=start_date,
            end_date=end_date,
        )
        rows = [
            BreakdownRow(
                label=" · ".join(str(part) for part in row[:-1]),
                value=_float(row[-1]),
            )
            for row in report.rows
        ]
        rows.sort(key=lambda row: row.value, reverse=True)
        return AudienceBreakdown(dimension=dimensions, rows=rows[:10])

    def audience(self, *, owner_uid: str, connection_id: str) -> AudienceProfile:
        self.connections.get(owner_uid=owner_uid, connection_id=connection_id)
        raw = self.client.get_document(connection_path(owner_uid, connection_id)) or {}
        stored = raw.get("audienceProfile")
        if not stored:
            return AudienceProfile(
                connectionId=connection_id,
                periodDays=self.settings.channel_analytics_days,
            )
        return AudienceProfile.model_validate(stored)

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

    def _transcript_excerpt(
        self, owner_uid: str, connection_id: str, video_id: str, limit: int = 600
    ) -> str | None:
        data = self.client.get_document(
            content_item_path(owner_uid, connection_id, video_id)
        )
        transcript = (data or {}).get("transcript")
        if not isinstance(transcript, str) or not transcript:
            return None
        return transcript[:limit]

    def creator_thumbnail_references(
        self, owner_uid: str, *, limit: int = 3
    ) -> list[MediaPart]:
        """Download a few of the creator's past thumbnails as image-model style references."""
        if limit <= 0:
            return []
        connection_id = self.primary_connection_id(owner_uid)
        if connection_id is None:
            return []
        items = self.list_items(
            owner_uid=owner_uid, connection_id=connection_id, limit=50
        )
        references: list[MediaPart] = []
        for item in items:
            if not item.thumbnailUrl:
                continue
            data = _download_image(item.thumbnailUrl)
            if data is None:
                continue
            references.append(
                MediaPart(
                    mime_type=_image_mime(item.thumbnailUrl),
                    data=data,
                    label=(
                        "A past thumbnail from this creator's channel — match its visual "
                        "style (colour, typography, composition), do not copy it"
                    ),
                )
            )
            if len(references) >= limit:
                break
        return references

    def build_context(
        self,
        *,
        owner_uid: str,
        connection_id: str,
        query: str,
        k: int = 5,
    ) -> dict[str, Any] | None:
        """Style summary + audience profile + the k most query-relevant past videos."""
        connection = self.connections.get(
            owner_uid=owner_uid, connection_id=connection_id
        )
        items = self.list_items(owner_uid=owner_uid, connection_id=connection_id, limit=200)
        if not items:
            return None
        examples: list[dict[str, Any]] = []
        for example in retrieve_examples(items, query, k=k):
            payload = example.model_dump(mode="json")
            excerpt = self._transcript_excerpt(owner_uid, connection_id, example.videoId)
            if excerpt:
                payload["transcriptExcerpt"] = excerpt
            examples.append(payload)
        context: dict[str, Any] = {
            "connectionId": connection_id,
            "connectionDisplayName": connection.displayName,
            "style": build_style_summary(items).model_dump(mode="json"),
            "examples": examples,
        }
        audience = self.audience(owner_uid=owner_uid, connection_id=connection_id)
        if audience.summary or audience.demographics:
            context["audience"] = {
                "periodDays": audience.periodDays,
                "summary": [metric.model_dump() for metric in audience.summary],
                "demographics": (
                    audience.demographics.model_dump() if audience.demographics else None
                ),
                "trafficSources": (
                    audience.trafficSources.model_dump()
                    if audience.trafficSources
                    else None
                ),
            }
        return context

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


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


_MAX_REFERENCE_BYTES = 5_000_000


def _download_image(url: str) -> bytes | None:
    """Fetch a public thumbnail URL (i.ytimg.com). Best-effort; never raises."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        return None
    data = response.content
    if not data or len(data) > _MAX_REFERENCE_BYTES:
        return None
    return data


def _image_mime(url: str) -> str:
    lowered = url.lower()
    if ".png" in lowered:
        return "image/png"
    if ".webp" in lowered:
        return "image/webp"
    return "image/jpeg"
