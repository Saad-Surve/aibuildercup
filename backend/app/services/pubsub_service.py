"""Pub/Sub access layer.

Feature code never imports `google.cloud.pubsub_v1` directly. It depends on the narrow
`PubSubClient` protocol so tests can record publishes without a network call.
"""

import json
import logging
from functools import lru_cache
from typing import Any, Protocol, runtime_checkable

from app.config import get_settings

logger = logging.getLogger(__name__)

# Best-effort cap so a hung publish cannot stall a worker indefinitely.
_PUBLISH_TIMEOUT_SECONDS = 10


@runtime_checkable
class PubSubClient(Protocol):
    def publish(self, *, topic: str, event: dict[str, Any]) -> str: ...


class GooglePubSubClient:
    """Real publisher. `topic` is the short name from `app.events.TOPIC_BY_EVENT`."""

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id

    def publish(self, *, topic: str, event: dict[str, Any]) -> str:
        from google.cloud import pubsub_v1  # type: ignore[attr-defined]

        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(self.project_id, topic)
        data = json.dumps(event).encode("utf-8")
        future = publisher.publish(topic_path, data=data, eventType=event.get("type", ""))
        message_id = future.result(timeout=_PUBLISH_TIMEOUT_SECONDS)
        logger.info("published %s to %s (%s)", event.get("type"), topic, message_id)
        return message_id


@lru_cache
def get_pubsub_client() -> PubSubClient:
    return GooglePubSubClient(get_settings().project_id)
