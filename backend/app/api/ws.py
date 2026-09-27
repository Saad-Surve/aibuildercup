"""`GET /api/ws` — the realtime WebSocket (contracts/events.md, openapi.yaml).

One socket per browser session. The client sends `{"type": "subscribe.project",
"projectId"}` frames; the server verifies ownership, sends a full snapshot, and
then forwards events published by job/project/analysis write paths (see
`app/realtime/hub.py`).

Auth: browsers cannot set an `Authorization` header on a WebSocket upgrade, so
the Firebase ID token travels as `?token=`. It is verified exactly like HTTP
bearer auth; the socket is accepted and immediately closed with 4401 on failure.
"""

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.auth.firebase import verify_id_token
from app.realtime import EventHub, get_hub
from app.services.firestore_service import get_firestore_client
from app.services.job_service import JobService
from app.services.project_service import ProjectService

log = logging.getLogger(__name__)

router = APIRouter(tags=["realtime"])

# Server sends an application-level ping after this much outbound silence.
WS_PING_INTERVAL_SECONDS = 30.0

# Bounded socket lifetime. Cloud Run caps request duration, and Firebase ID tokens
# expire hourly, so the client is expected to reconnect (with a fresh token).
_WS_OPEN_TIMEOUT_SECONDS = 50 * 60

# Close code for a rejected token: "Unauthorized" in the private-use range.
_WS_DENY_CODE = 4401


def _dumps(data: dict) -> str:
    return json.dumps(data, separators=(",", ":"), default=str)


async def _authenticate(socket: WebSocket) -> str | None:
    """Verify the `?token=` query param; return the uid, or None after closing.

    The upgrade is accepted and immediately closed with code 4401 rather than
    sending an HTTP 401 denial: Starlette's denial response does not mark the
    handshake complete, which makes uvicorn log a spurious error on every
    rejected attempt. No data is ever sent to an unauthenticated socket — it is
    closed before any subscription can be registered. The client reconnects with
    a freshly minted token.
    """
    token = socket.query_params.get("token", "")
    if token:
        try:
            decoded = verify_id_token(token)
        except Exception:  # noqa: BLE001 — any verification failure is a denial
            decoded = None
        if decoded is not None:
            return str(decoded["uid"])
    await socket.accept()
    try:
        await socket.close(code=_WS_DENY_CODE, reason="Unauthorized")
    except RuntimeError:
        pass  # already closed
    return None


async def _handle_subscribe(
    socket: WebSocket,
    hub: EventHub,
    owner_uid: str,
    queue: asyncio.Queue[dict],
    message: dict,
    jobs: JobService,
    projects: ProjectService,
) -> None:
    """Verify ownership, send the snapshot, then register the queue.

    The snapshot is sent BEFORE registering so there is no window in which an
    event could be emitted after the read but before the subscription, and no
    event can arrive before the client has its baseline.
    """
    project_id = message.get("projectId")
    if not isinstance(project_id, str) or not project_id:
        await socket.send_text(
            _dumps(
                {
                    "type": "error",
                    "code": "BAD_REQUEST",
                    "message": "subscribe.project needs projectId",
                }
            )
        )
        return

    try:
        project = projects.get(owner_uid=owner_uid, project_id=project_id)
    except Exception:  # noqa: BLE001 — not-owned and not-found are the same denial
        await socket.send_text(
            _dumps({"type": "error", "code": "NOT_FOUND", "message": "Project not found"})
        )
        return

    job_frame: dict[str, Any] | None
    try:
        job = jobs.latest_for_project(owner_uid=owner_uid, project_id=project_id)
        job_frame = (
            {
                "jobId": job.jobId,
                "type": job.type.value,
                "status": job.status.value,
                "progress": job.progress.model_dump() if job.progress else None,
                "error": job.error,
            }
            if job is not None
            else None
        )
    except Exception:  # noqa: BLE001 — a snapshot without the job is still useful
        job_frame = None

    snapshot = {
        "type": "snapshot.project",
        "projectId": project.projectId,
        "status": project.status.value,
        "progress": project.progress.model_dump() if project.progress else None,
        "job": job_frame,
    }
    await socket.send_text(_dumps(snapshot))
    hub.subscribe(owner_uid, project_id, queue)


async def _reader(
    socket: WebSocket,
    hub: EventHub,
    queue: asyncio.Queue[dict],
    owner_uid: str,
    jobs: JobService,
    projects: ProjectService,
) -> None:
    """Client → server loop: subscribe frames, pings, and clean disconnects."""
    while True:
        try:
            raw = await socket.receive_text()
        except WebSocketDisconnect:
            hub.unsubscribe(queue)
            return
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            await socket.send_text(
                _dumps(
                    {
                        "type": "error",
                        "code": "BAD_REQUEST",
                        "message": "Frames must be JSON objects",
                    }
                )
            )
            continue
        if not isinstance(message, dict):
            continue

        kind = message.get("type")
        if kind == "subscribe.project":
            await _handle_subscribe(
                socket, hub, owner_uid, queue, message, jobs, projects
            )
        elif kind == "ping":
            await socket.send_text(_dumps({"type": "pong"}))
        elif kind == "pong":
            continue  # answer to a server ping
        else:
            await socket.send_text(
                _dumps(
                    {
                        "type": "error",
                        "code": "BAD_REQUEST",
                        "message": f"Unknown frame type {kind!r}",
                    }
                )
            )


async def _writer(socket: WebSocket, hub: EventHub, queue: asyncio.Queue[dict]) -> None:
    """Server → client loop: drain the queue, ping when idle, close when due."""
    loop = asyncio.get_running_loop()
    connection_deadline = loop.time() + _WS_OPEN_TIMEOUT_SECONDS
    while True:
        remaining = connection_deadline - loop.time()
        if remaining <= 0:
            hub.unsubscribe(queue)
            try:
                await socket.close(code=1001)  # going away; client reconnects
            except RuntimeError:
                pass
            return
        try:
            data = await asyncio.wait_for(
                queue.get(), timeout=min(remaining, WS_PING_INTERVAL_SECONDS)
            )
        except TimeoutError:
            # Idle for the ping interval: keep intermediaries from reaping us.
            try:
                await socket.send_text(_dumps({"type": "ping"}))
            except (WebSocketDisconnect, RuntimeError):
                hub.unsubscribe(queue)
                return
            continue
        try:
            await socket.send_text(_dumps(data))
        except (WebSocketDisconnect, RuntimeError):
            hub.unsubscribe(queue)
            return


@router.websocket("/ws")
async def ws_endpoint(socket: WebSocket) -> None:
    """The realtime socket. Auth: ?token=<firebaseIdToken>."""
    hub = get_hub()
    hub.bind_loop(asyncio.get_running_loop())

    owner_uid = await _authenticate(socket)
    if owner_uid is None:
        return  # rejected: accepted, then closed with 4401

    queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=256)
    client = get_firestore_client()
    jobs = JobService(client)
    projects = ProjectService(client)

    reader = asyncio.create_task(_reader(socket, hub, queue, owner_uid, jobs, projects))
    writer = asyncio.create_task(_writer(socket, hub, queue))

    try:
        done, pending = await asyncio.wait({reader, writer}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        hub.unsubscribe(queue)
        try:
            await socket.close()
        except RuntimeError:
            pass  # already closed by the reader/writer
        for task in done:
            exc = task.exception()
            if exc is not None and not isinstance(exc, (WebSocketDisconnect, RuntimeError)):
                log.warning("websocket %s: handler error: %r", owner_uid, exc)
    except Exception as exc:  # noqa: BLE001 — always clean up the hub
        log.warning("websocket %s: outer error: %r", owner_uid, exc)
        reader.cancel()
        writer.cancel()
        hub.unsubscribe(queue)
        try:
            await socket.close()
        except RuntimeError:
            pass
