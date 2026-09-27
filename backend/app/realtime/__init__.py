"""Realtime event fan-out for WebSocket clients.

`hub.publish(...)` is called from job/project/analysis write paths; the websocket
endpoint consumes per-connection queues. See `hub.py` for the dispatch model.
"""

from app.realtime.hub import EventHub, get_hub

__all__ = ["EventHub", "get_hub"]
