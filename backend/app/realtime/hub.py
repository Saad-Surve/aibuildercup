"""In-process realtime event hub for WebSocket clients.

Connections register per (ownerUid, projectId) with an asyncio queue; job/analysis
writes call `publish` to fan progress events out to every subscribed socket.

This is correct for the current deploy shape: workers run in-process (FastAPI
BackgroundTasks) and Cloud Run holds `--max-instances 1`, so the socket and the
writer share one event loop. If the service ever scales past one instance, this
module is the single place to swap the in-memory fan-out for Firestore snapshots
or Pub/Sub pull.

Publishing is fire-and-forget and never raises: a realtime miss must never fail a
real write. If a queue overruns, that queue is dropped and the client reconnects
(the snapshot on subscribe makes reconnect self-healing).
"""

import asyncio
import json
import logging

log = logging.getLogger(__name__)

# Per-connection queue depth. A queue that falls this far behind is dropped.
_MAX_QUEUE_DEPTH = 256


def json_ready(data: dict) -> dict:
    """Round-trip a payload through JSON so a stray datetime/enum cannot break a send."""
    return json.loads(json.dumps(data, default=str))


class EventHub:
    """Fan-out of realtime events to subscribed WebSocket connections."""

    def __init__(self) -> None:
        # (owner_uid, project_id) -> the socket queues subscribed to that project.
        self._subscribers: dict[tuple[str, str], list[asyncio.Queue[dict]]] = {}
        # The loop the sockets live on, captured on first connect so a publish
        # from a worker thread can still deliver safely.
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def queues_for(self, owner_uid: str, project_id: str) -> list[asyncio.Queue[dict]]:
        return self._subscribers.get((owner_uid, project_id), [])

    def has_subscribers(self, owner_uid: str, project_id: str) -> bool:
        """True when at least one socket is watching this project.

        Callers use this to skip building expensive event payloads (extra
        Firestore reads) when nobody is listening.
        """
        return bool(self.queues_for(owner_uid, project_id))

    def subscribe(self, owner_uid: str, project_id: str, queue: asyncio.Queue[dict]) -> None:
        """Start delivering events for a project to a socket queue."""
        queues = self._subscribers.setdefault((owner_uid, project_id), [])
        if queue not in queues:  # a resubscribe must not duplicate deliveries
            queues.append(queue)

    def unsubscribe(self, queue: asyncio.Queue[dict]) -> None:
        """Remove one queue from every project it subscribed to."""
        stale: list[tuple[str, str]] = []
        for key, queues in self._subscribers.items():
            if queue in queues:
                queues.remove(queue)
                if not queues:
                    stale.append(key)
        for key in stale:
            self._subscribers.pop(key, None)

    def _deliver(self, queue: asyncio.Queue[dict], data: dict) -> bool:
        """Put one event on a queue, from the loop or a worker thread."""
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self._loop or self._loop is None:
            queue.put_nowait(data)
        else:
            # Called off the socket's loop (sync worker/threadpool path).
            self._loop.call_soon_threadsafe(queue.put_nowait, data)
        return True

    def publish(self, owner_uid: str, project_id: str, data: dict) -> int:
        """Queue an event for every subscriber of one project.

        Fire-and-forget: never raises, never back-pressures the writer. Returns
        the number of queues the event was delivered to (0 is normal — publish
        happens whether or not anyone is watching).
        """
        queues = self.queues_for(owner_uid, project_id)
        delivered = 0
        for queue in list(queues):
            try:
                self._deliver(queue, data)
                delivered += 1
            except asyncio.QueueFull:
                # The socket cannot keep up; drop it so the client resyncs via
                # a fresh snapshot on reconnect instead of drifting silently.
                log.warning("realtime queue overrun, dropping socket: project=%s", project_id)
                self.unsubscribe(queue)
        return delivered

    def publish_json(self, owner_uid: str, project_id: str, data: dict) -> int:
        """Like publish, but ensures the payload is JSON-serializable first."""
        return self.publish(owner_uid, project_id, json_ready(data))


_hub: EventHub | None = None


def get_hub() -> EventHub:
    """Process-wide hub instance (one per Cloud Run container)."""
    global _hub
    if _hub is None:
        _hub = EventHub()
    return _hub
