"""Read-only channel retention, with a hard request bound and no implicit SDK retries."""

import math
import time
from typing import Any

import requests

from app.errors import AppError
from app.providers.base import ChannelRetention, VideoRetention

MAX_VIDEOS = 40
MAX_REQUESTS = 43
DEADLINE_SECONDS = 180
ANALYTICS_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"
_DATA_URL = "https://www.googleapis.com/youtube/v3/"
_ANALYTICS_URL = "https://youtubeanalytics.googleapis.com/v2/reports"


class RetentionReadError(AppError):
    status_code = 502


class YouTubeAnalyticsProvider:
    def collect(
        self,
        *,
        access_token: str,
        channel_id: str,
        uploads_playlist_id: str,
        start_date: str,
        end_date: str,
    ) -> ChannelRetention:
        """One playlist page, one metadata batch, one views report, <=40 retention reports.

        Channel IDs are explicit, so a token that can act as several brand channels cannot
        silently calibrate the default channel. Metadata is checked against that channel.
        A fresh session uses requests' default zero retries; redirects are disabled.
        """
        calls = 0
        deadline = time.monotonic() + DEADLINE_SECONDS
        with requests.Session() as session:
            session.headers["Authorization"] = f"Bearer {access_token}"

            def get(url: str, params: dict[str, Any]) -> dict[str, Any]:
                nonlocal calls
                remaining = deadline - time.monotonic()
                if calls >= MAX_REQUESTS or remaining <= 0:
                    raise RetentionReadError(
                        "The bounded YouTube read timed out. Try again after the cooldown.",
                        code="CALIBRATION_LIMIT",
                        details={"apiRequests": calls},
                    )
                calls += 1
                try:
                    response = session.get(
                        url, params=params, timeout=min(10, remaining), allow_redirects=False
                    )
                    if not response.ok or response.is_redirect:
                        try:
                            reasons = {
                                error.get("reason")
                                for error in (response.json().get("error") or {}).get("errors", [])
                            }
                        except (ValueError, AttributeError, TypeError):
                            reasons = set()
                        if reasons & {"quotaExceeded", "rateLimitExceeded", "dailyLimitExceeded"}:
                            reason = "YouTube's read quota is exhausted. Try after the cooldown."
                        elif response.status_code in (401, 403):
                            reason = (
                                "YouTube denied access. Reconnect this channel and grant "
                                "YouTube Analytics access."
                            )
                        else:
                            reason = (
                                "YouTube could not return retention data. Try after the cooldown."
                            )
                        raise RetentionReadError(
                            reason,
                            code="YOUTUBE_RETENTION_ERROR",
                            details={"apiRequests": calls, "status": response.status_code},
                        )
                    body = response.json()
                    if not isinstance(body, dict):
                        raise ValueError("Expected report object")
                    return body
                except (requests.RequestException, ValueError) as exc:
                    raise RetentionReadError(
                        "YouTube retention could not be read. Try again after the cooldown.",
                        code="YOUTUBE_RETENTION_ERROR",
                        details={"apiRequests": calls},
                    ) from exc

            playlist = get(
                _DATA_URL + "playlistItems",
                {
                    "part": "contentDetails",
                    "playlistId": uploads_playlist_id,
                    "maxResults": MAX_VIDEOS,
                },
            )
            ids = list(
                dict.fromkeys(
                    str(item["contentDetails"]["videoId"])
                    for item in playlist.get("items", [])
                    if (item.get("contentDetails") or {}).get("videoId")
                )
            )[:MAX_VIDEOS]
            if not ids:
                return ChannelRetention((), 0, calls)
            metadata = get(
                _DATA_URL + "videos",
                {"part": "snippet,contentDetails", "id": ",".join(ids)},
            )
            # Reuse the connector's ISO duration parser, with no SDK calls here.
            from app.connectors.youtube import _iso_duration_seconds

            durations = {
                str(item["id"]): _iso_duration_seconds(
                    (item.get("contentDetails") or {}).get("duration")
                )
                for item in metadata.get("items", [])
                if str(item.get("id")) in ids
                and (item.get("snippet") or {}).get("channelId") == channel_id
            }
            if not durations:
                return ChannelRetention((), len(ids), calls)
            common = {"ids": f"channel=={channel_id}", "startDate": start_date, "endDate": end_date}
            views_report = get(
                _ANALYTICS_URL,
                {
                    **common,
                    "dimensions": "video",
                    "metrics": "views",
                    "filters": "video==" + ",".join(durations),
                    "maxResults": MAX_VIDEOS,
                },
            )
            views = {
                str(row.get("video")): int(row.get("views") or 0) for row in _rows(views_report)
            }
            videos: list[VideoRetention] = []
            for video_id, duration in durations.items():
                count = views.get(video_id, 0)
                if not duration:
                    continue
                report = get(
                    _ANALYTICS_URL,
                    {
                        **common,
                        "dimensions": "elapsedVideoTimeRatio",
                        "metrics": "audienceWatchRatio",
                        "filters": f"video=={video_id}",
                    },
                )
                points: list[tuple[float, float]] = []
                for row in _rows(report):
                    try:
                        x = float(row["elapsedVideoTimeRatio"])
                        y = float(row["audienceWatchRatio"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    if math.isfinite(x) and math.isfinite(y) and 0 <= x <= 1 and y >= 0:
                        points.append((x, y))
                videos.append(VideoRetention(duration, count, tuple(points)))
            return ChannelRetention(tuple(videos), len(ids), calls)


def _rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    names = [str(header.get("name") or "") for header in report.get("columnHeaders", [])]
    return [
        dict(zip(names, row, strict=True))
        for row in report.get("rows", [])
        if len(row) == len(names)
    ]
