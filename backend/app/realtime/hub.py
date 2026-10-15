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
from threading import RLock

log = logging.getLogger(__name__)

# Per-connection queue depth. A queue that falls this far behind is dropped.
DISCONNECT_FRAME = {"type": "_disconnect"}


def json_ready(data: dict) -> dict:
    """Round-trip a payload through JSON so a stray datetime/enum cannot break a send."""
    return json.loads(json.dumps(data, default=str))


class EventHub:
    """Fan-out of realtime events to subscribed WebSocket connections."""

    def __init__(self) -> None:
        # (owner_uid, project_id) -> the socket queues subscribed to that project.
        self._subscribers: dict[tuple[str, str], list[asyncio.Queue[dict]]] = {}
        self._owners: dict[str, list[asyncio.Queue[dict]]] = {}
        # The loop the sockets live on, captured on first connect so a publish
        # from a worker thread can still deliver safely.
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = RLock()

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def queues_for(self, owner_uid: str, project_id: str) -> list[asyncio.Queue[dict]]:
        with self._lock:
            return list(self._subscribers.get((owner_uid, project_id), []))

    def has_subscribers(self, owner_uid: str, project_id: str) -> bool:
        """True when at least one socket is watching this project.

        Callers use this to skip building expensive event payloads (extra
        Firestore reads) when nobody is listening.
        """
        with self._lock:
            return bool(self._subscribers.get((owner_uid, project_id)))

    def subscribe_owner(self, owner_uid: str, queue: asyncio.Queue[dict]) -> None:
        with self._lock:
            queues = self._owners.setdefault(owner_uid, [])
            if queue not in queues:
                queues.append(queue)

    def unsubscribe_owner(self, owner_uid: str, queue: asyncio.Queue[dict]) -> None:
        with self._lock:
            queues = self._owners.get(owner_uid, [])
            if queue in queues:
                queues.remove(queue)
            if not queues:
                self._owners.pop(owner_uid, None)

    def subscribe(self, owner_uid: str, project_id: str, queue: asyncio.Queue[dict]) -> None:
        """Start delivering events for a project to a socket queue."""
        with self._lock:
            queues = self._subscribers.setdefault((owner_uid, project_id), [])
            if queue not in queues:
                queues.append(queue)

    def unsubscribe(
        self, queue: asyncio.Queue[dict], *, project: tuple[str, str] | None = None
    ) -> None:
        """Remove one queue from every project it subscribed to."""
        with self._lock:
            if project is None:
                for owner_uid in list(self._owners):
                    self.unsubscribe_owner(owner_uid, queue)
            keys = [project] if project is not None else list(self._subscribers)
            for key in keys:
                queues = self._subscribers.get(key, [])
                if queue in queues:
                    queues.remove(queue)
                if not queues:
                    self._subscribers.pop(key, None)

    def _enqueue(self, queue: asyncio.Queue[dict], data: dict) -> None:
        """Runs on the socket loop, including the overflow handling."""
        try:
            queue.put_nowait(data)
        except asyncio.QueueFull:
            self.unsubscribe(queue)
            # Wake the writer with a close signal; just removing subscriptions
            # would leave a healthy-looking socket receiving only keepalives.
            while not queue.empty():
                queue.get_nowait()
            queue.put_nowait(DISCONNECT_FRAME)
            log.warning("realtime queue overrun; closing slow socket")

    def _deliver(self, queue: asyncio.Queue[dict], data: dict) -> bool:
        """Put one event on a queue, from the loop or a worker thread."""
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self._loop or self._loop is None:
            self._enqueue(queue, data)
        else:
            # Called off the socket's loop (sync worker/threadpool path).
            self._loop.call_soon_threadsafe(self._enqueue, queue, data)
        return True

    def publish(self, owner_uid: str, project_id: str, data: dict) -> int:
        """Queue an event for every subscriber of one project.

        Fire-and-forget: never raises, never back-pressures the writer. Returns
        the number of queues the event was delivered to (0 is normal — publish
        happens whether or not anyone is watching).
        """
        with self._lock:
            queues = list(
                dict.fromkeys(
                    [*self.queues_for(owner_uid, project_id), *self._owners.get(owner_uid, [])]
                )
            )
        delivered = 0
        for queue in list(queues):
            try:
                self._deliver(queue, data)
                delivered += 1
            except RuntimeError:
                # The socket loop may already have stopped during shutdown.
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
