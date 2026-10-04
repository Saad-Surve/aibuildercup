"""YouTube Data API v3 connector.

Wraps `googleapiclient` so no feature code imports the Google SDK. Handles channel lookup,
resumable video upload, thumbnail set, and caption upload.

Quota notes (the demo stays well under the defaults):
- `videos.insert` has its own bucket of 100 uploads/day (cost 1 each), separate from the shared
  10,000 units/day pool.
- `thumbnails.set` costs 50 units and `captions.insert` costs 400 units, from the shared pool.

Uploaded videos start as `private` until the OAuth client passes YouTube's API audit; an
unverified client's uploads are locked private regardless of the requested privacy status.
"""

import io
import logging
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.connectors.base import ChannelInfo, ChannelVideo, ConnectorError, UploadedVideo
from app.services.oauth_service import OAuthTokenSet

logger = logging.getLogger(__name__)

YOUTUBE_API_SERVICE = "youtube"
YOUTUBE_API_VERSION = "v3"
#: 8 MiB chunks keep each resumable request small enough to retry cheaply.
_UPLOAD_CHUNK_BYTES = 8 * 1024 * 1024
_MAX_UPLOAD_ROUNDS = 6


class YouTubeConnector:
    """YouTube Data API client built from an `OAuthTokenSet`."""

    def __init__(self, *, client_id: str, client_secret: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret

    # ------------------------------------------------------------------ helpers

    def _credentials(self, tokens: OAuthTokenSet) -> Any:
        from google.oauth2.credentials import Credentials

        return Credentials(
            token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=list(tokens.scopes) or None,
        )

    def _service(self, tokens: OAuthTokenSet) -> Any:
        from googleapiclient.discovery import build

        return build(
            YOUTUBE_API_SERVICE,
            YOUTUBE_API_VERSION,
            credentials=self._credentials(tokens),
            cache_discovery=False,
        )

    # ------------------------------------------------------------------ channels

    def list_channels(self, tokens: OAuthTokenSet) -> list[ChannelInfo]:
        """Every channel the authorized Google account can act as."""
        service = self._service(tokens)
        try:
            response = (
                service.channels()
                .list(part="snippet,statistics,contentDetails", mine=True, maxResults=50)
                .execute()
            )
        except Exception as exc:  # noqa: BLE001 - normalised below
            raise self._translate(exc, "Could not read the YouTube channels.") from exc
        return [self._channel_from(item) for item in response.get("items") or []]

    def refresh_channel(self, tokens: OAuthTokenSet, channel_id: str) -> ChannelInfo:
        service = self._service(tokens)
        try:
            response = (
                service.channels()
                .list(part="snippet,statistics,contentDetails", id=channel_id)
                .execute()
            )
        except Exception as exc:  # noqa: BLE001
            raise self._translate(exc, "Could not read the channel.") from exc
        items = response.get("items") or []
        if not items:
            raise ConnectorError("The channel is no longer available.", code="CHANNEL_NOT_FOUND")
        return self._channel_from(items[0])

    # ------------------------------------------------------------------ read-back

    def list_videos(
        self,
        tokens: OAuthTokenSet,
        *,
        uploads_playlist_id: str,
        max_videos: int = 50,
    ) -> list[ChannelVideo]:
        """Read a channel's published videos for style/RAG analysis.

        Two cheap calls per page: `playlistItems.list` (1 unit/page of 50) for the ids, then
        `videos.list` (1 unit per 50 ids) for metadata. Never `search.list` (100 units).
        """
        service = self._service(tokens)
        video_ids: list[str] = []
        page_token: str | None = None
        try:
            while len(video_ids) < max_videos:
                response = (
                    service.playlistItems()
                    .list(
                        part="contentDetails",
                        playlistId=uploads_playlist_id,
                        maxResults=min(50, max_videos - len(video_ids)),
                        pageToken=page_token,
                    )
                    .execute()
                )
                for item in response.get("items") or []:
                    video_id = (item.get("contentDetails") or {}).get("videoId")
                    if video_id:
                        video_ids.append(str(video_id))
                page_token = response.get("nextPageToken")
                if not page_token:
                    break

            videos: list[ChannelVideo] = []
            for start in range(0, len(video_ids), 50):
                batch = video_ids[start : start + 50]
                response = (
                    service.videos()
                    .list(
                        part="snippet,contentDetails,statistics,status",
                        id=",".join(batch),
                    )
                    .execute()
                )
                videos.extend(
                    self._video_from(item) for item in response.get("items") or []
                )
            return videos
        except Exception as exc:  # noqa: BLE001 - normalised below
            raise self._translate(exc, "Could not read the channel's videos.") from exc

    def revoke(self, tokens: OAuthTokenSet) -> None:
        """No channel-level revoke endpoint; the OAuth service revokes the token itself."""
        return None

    # ------------------------------------------------------------------ uploads

    def upload_video(
        self,
        tokens: OAuthTokenSet,
        *,
        path: Path,
        title: str,
        description: str,
        tags: list[str],
        category_id: str,
        privacy_status: str,
        made_for_kids: bool,
        notify_subscribers: bool,
        publish_at: str | None = None,
        on_progress: Callable[[int], None] | None = None,
        mime_type: str = "video/mp4",
    ) -> UploadedVideo:
        from googleapiclient.http import MediaFileUpload

        snippet: dict[str, Any] = {
            "title": title,
            "description": description,
            "categoryId": category_id,
        }
        if tags:
            snippet["tags"] = tags
        status: dict[str, Any] = {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": made_for_kids,
        }
        if publish_at:
            # YouTube only accepts a scheduled publish time on a private video.
            status["privacyStatus"] = "private"
            status["publishAt"] = publish_at

        media = MediaFileUpload(
            str(path), mimetype=mime_type, chunksize=_UPLOAD_CHUNK_BYTES, resumable=True
        )
        request = (
            self._service(tokens)
            .videos()
            .insert(
                part="snippet,status",
                body={"snippet": snippet, "status": status},
                media_body=media,
                notifySubscribers=notify_subscribers,
            )
        )

        response: dict[str, Any] | None = None
        last_status: Any = None
        rounds = 0
        while response is None:
            try:
                last_status, response = request.next_chunk()
            except Exception as exc:  # noqa: BLE001
                error = self._translate(exc, "The upload to YouTube failed.")
                # A transient network error mid-upload is safe to retry: `next_chunk`
                # resumes from the last acknowledged byte.
                if error.retryable and rounds < _MAX_UPLOAD_ROUNDS:
                    rounds += 1
                    time.sleep(min(2**rounds, 20))
                    continue
                raise error from exc
            rounds = 0
            if on_progress is not None and last_status is not None:
                try:
                    on_progress(max(0, min(100, int(last_status.progress() * 100))))
                except Exception:  # noqa: BLE001 - progress must never fail the upload
                    logger.debug("youtube: progress callback failed", exc_info=True)

        if response is None:  # pragma: no cover - loop only exits with a response
            raise ConnectorError("YouTube did not return the uploaded video.")
        video_id = str(response.get("id") or "")
        if not video_id:
            raise ConnectorError("YouTube accepted the upload without a video id.")
        return UploadedVideo(
            video_id=video_id,
            title=str((response.get("snippet") or {}).get("title") or title),
            privacy_status=(response.get("status") or {}).get("privacyStatus"),
        )

    def set_thumbnail(
        self,
        tokens: OAuthTokenSet,
        *,
        video_id: str,
        path: Path,
        mime_type: str = "image/png",
    ) -> None:
        from googleapiclient.http import MediaFileUpload

        media = MediaFileUpload(str(path), mimetype=mime_type, resumable=False)
        try:
            (
                self._service(tokens)
                .thumbnails()
                .set(videoId=video_id, media_body=media)
                .execute()
            )
        except Exception as exc:  # noqa: BLE001
            raise self._translate(exc, "YouTube rejected the thumbnail.") from exc

    def upload_caption(
        self,
        tokens: OAuthTokenSet,
        *,
        video_id: str,
        content: str,
        language: str,
        name: str,
    ) -> str | None:
        """Upload an SRT/VTT caption track. Returns the caption id when YouTube reports one."""
        from googleapiclient.http import MediaIoBaseUpload

        media = MediaIoBaseUpload(
            io.BytesIO(content.encode("utf-8")),
            mimetype="application/octet-stream",
            resumable=False,
        )
        try:
            response = (
                self._service(tokens)
                .captions()
                .insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "videoId": video_id,
                            "language": language,
                            "name": name,
                        }
                    },
                    media_body=media,
                )
                .execute()
            )
        except Exception as exc:  # noqa: BLE001
            raise self._translate(exc, "YouTube rejected the caption track.") from exc
        return response.get("id")

    # ------------------------------------------------------------------ parsing

    @staticmethod
    def _channel_from(item: dict[str, Any]) -> ChannelInfo:
        snippet = item.get("snippet") or {}
        statistics = item.get("statistics") or {}
        content_details = item.get("contentDetails") or {}
        related = content_details.get("relatedPlaylists") or {}
        thumbnails = snippet.get("thumbnails") or {}
        default_thumb = thumbnails.get("default") or thumbnails.get("medium") or {}
        return ChannelInfo(
            channel_id=str(item.get("id") or ""),
            title=str(snippet.get("title") or "YouTube channel"),
            handle=snippet.get("customUrl"),
            thumbnail_url=default_thumb.get("url"),
            subscriber_count=_int_or_none(statistics.get("subscriberCount")),
            video_count=_int_or_none(statistics.get("videoCount")),
            uploads_playlist_id=related.get("uploads"),
        )

    @staticmethod
    def _video_from(item: dict[str, Any]) -> ChannelVideo:
        snippet = item.get("snippet") or {}
        content = item.get("contentDetails") or {}
        statistics = item.get("statistics") or {}
        thumbnails = snippet.get("thumbnails") or {}
        best = (
            thumbnails.get("maxres")
            or thumbnails.get("standard")
            or thumbnails.get("high")
            or thumbnails.get("medium")
            or thumbnails.get("default")
            or {}
        )
        return ChannelVideo(
            video_id=str(item.get("id") or ""),
            title=str(snippet.get("title") or ""),
            description=str(snippet.get("description") or ""),
            tags=tuple(str(tag) for tag in (snippet.get("tags") or [])),
            published_at=snippet.get("publishedAt"),
            duration_seconds=_iso_duration_seconds(content.get("duration")),
            view_count=_int_or_none(statistics.get("viewCount")),
            like_count=_int_or_none(statistics.get("likeCount")),
            comment_count=_int_or_none(statistics.get("commentCount")),
            thumbnail_url=best.get("url"),
            has_custom_thumbnail=content.get("hasCustomThumbnail"),
            language=snippet.get("defaultAudioLanguage") or snippet.get("defaultLanguage"),
        )

    @staticmethod
    def _translate(exc: Exception, message: str) -> ConnectorError:
        """Turn a `googleapiclient` HttpError into a typed `ConnectorError`."""
        status = None
        reason = None
        response = getattr(exc, "resp", None)
        if response is not None:
            status = getattr(response, "status", None)
        content = getattr(exc, "content", None)
        if content:
            try:
                import json

                body = json.loads(content)
                error = (body.get("error") or {}).get("errors") or [{}]
                reason = error[0].get("reason") or (body.get("error") or {}).get("status")
                message = error[0].get("message") or message
            except Exception:  # noqa: BLE001 - keep the caller's message
                pass
        retryable = status in (500, 502, 503, 504) or reason in (
            "quotaExceeded",
            "rateLimitExceeded",
            "backendError",
        )
        code = "QUOTA_EXCEEDED" if reason == "quotaExceeded" else "YOUTUBE_API_ERROR"
        if reason in ("forbidden", "youtubeSignupRequired") or status == 403:
            code = "YOUTUBE_FORBIDDEN"
        return ConnectorError(
            message,
            code=code,
            retryable=retryable,
            details={"status": status, "reason": reason},
        )


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


_DURATION = re.compile(
    r"^P(?:(?P<days>\d+)D)?"
    r"(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
)


def _iso_duration_seconds(value: Any) -> int | None:
    """Parse an ISO 8601 duration (`PT1H2M3S`) into seconds."""
    if not value:
        return None
    match = _DURATION.match(str(value))
    if match is None:
        return None
    return (
        int(match.group("days") or 0) * 86400
        + int(match.group("hours") or 0) * 3600
        + int(match.group("minutes") or 0) * 60
        + int(match.group("seconds") or 0)
    )
