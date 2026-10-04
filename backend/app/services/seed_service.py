"""Seed a creator's account with CC-BY channel content for the demo.

The creator-content features (style/RAG, transcripts, thumbnail references) are built from a
connected YouTube channel. A fresh account has little content, so for the demo we load a compact,
pre-built JSON (see `backend/scripts/upload_youtube_seed.py`) from `seed/youtube/<slug>.json` in the
media bucket and write it as a synthetic "demo" connection plus its content items. Draft generation
then uses it as creator context.

Everything lives under `users/{uid}/connections/{id}`, so the recursive account delete covers it.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.config import Settings
from app.errors import NotFoundError
from app.schemas.connections import (
    SeedYouTubeContentResult,
)
from app.services.firestore_service import (
    FirestoreClient,
    connection_path,
    content_item_path,
)
from app.services.storage_service import StorageClient

logger = logging.getLogger(__name__)

_SEED_PREFIX = "seed/youtube"


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


class SeedService:
    def __init__(
        self,
        client: FirestoreClient,
        *,
        storage: StorageClient,
        settings: Settings,
    ) -> None:
        self.client = client
        self.storage = storage
        self.settings = settings

    def seed_youtube_content(
        self,
        *,
        owner_uid: str,
        channel: str = "psych2go",
        limit: int | None = None,
    ) -> SeedYouTubeContentResult:
        """Load one CC-BY seed channel into a synthetic demo connection for this user."""
        slug = channel.strip().lower()
        object_path = f"{_SEED_PREFIX}/{slug}.json"
        if not self.storage.object_exists(object_path):
            raise NotFoundError(
                f"No seed data for '{slug}'.",
                details={"channel": slug},
            )
        payload = json.loads(self.storage.download_text(object_path))
        items = list(payload.get("items") or [])
        cap = limit or self.settings.seed_content_max_items
        if cap:
            items = items[:cap]

        connection_id = f"seed-{slug}"
        now = datetime.now(UTC)
        self.client.set_document(
            connection_path(owner_uid, connection_id),
            {
                "ownerUid": owner_uid,
                "platform": "youtube",
                "accountType": "channel",
                "displayName": f"{payload.get('channel') or slug} (CC-BY demo)",
                "externalAccountId": f"seed:{slug}",
                "externalHandle": None,
                "avatarUrl": None,
                "subscriberCount": None,
                "videoCount": len(items),
                "status": "connected",
                "scopes": [],
                "lastSyncAt": None,
                "lastSyncStatus": "succeeded",
                "lastErrorCode": None,
                "contentSyncedAt": now,
                "contentItemCount": len(items),
                "seedSource": payload.get("source"),
                "seedLicense": payload.get("license"),
                "seedAttribution": payload.get("attribution"),
                "createdAt": now,
                "updatedAt": now,
            },
        )
        written = 0
        for item in items:
            video_id = str(item.get("videoId") or "").strip()
            if not video_id:
                continue
            transcript = str(item.get("transcript") or "").strip()
            self.client.set_document(
                content_item_path(owner_uid, connection_id, video_id),
                {
                    "ownerUid": owner_uid,
                    "connectionId": connection_id,
                    "videoId": video_id,
                    "title": item.get("title") or "",
                    "description": item.get("description") or "",
                    "tags": list(item.get("tags") or []),
                    "publishedAt": _parse_dt(item.get("publishedAt")),
                    "durationSeconds": item.get("durationSeconds"),
                    "viewCount": item.get("viewCount"),
                    "likeCount": item.get("likeCount"),
                    "commentCount": item.get("commentCount"),
                    "thumbnailUrl": item.get("thumbnailUrl"),
                    "hasCustomThumbnail": None,
                    "language": item.get("language"),
                    "hasCaptions": bool(transcript),
                    "transcript": transcript or None,
                    "updatedAt": now,
                },
            )
            written += 1
        self.client.update_document(
            connection_path(owner_uid, connection_id),
            {"contentItemCount": written, "updatedAt": now},
        )
        logger.info("seed: loaded %s videos for %s from %s", written, owner_uid, object_path)
        return SeedYouTubeContentResult(
            connectionId=connection_id,
            channel=str(payload.get("channel") or slug),
            itemCount=written,
            license=str(payload.get("license") or ""),
            attribution=str(payload.get("attribution") or ""),
        )
