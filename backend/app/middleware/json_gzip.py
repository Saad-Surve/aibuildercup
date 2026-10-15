"""Compress complete JSON responses; never buffer streaming bodies or WebSockets."""

import gzip

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class JsonGZipMiddleware:
    def __init__(self, app: ASGIApp, minimum_size: int = 1024) -> None:
        self.app = app
        self.minimum_size = minimum_size

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or "gzip" not in Headers(scope=scope).get("accept-encoding", ""):
            await self.app(scope, receive, send)
            return
        start: Message | None = None
        passthrough = False

        async def send_json(message: Message) -> None:
            nonlocal start, passthrough
            if message["type"] == "http.response.start":
                start = message
                return
            if message["type"] != "http.response.body" or passthrough or start is None:
                await send(message)
                return
            headers = MutableHeaders(scope=start)
            body = message.get("body", b"")
            # First body frame decides. A stream passes through immediately, unchanged.
            if (
                not message.get("more_body", False)
                and headers.get("content-type", "").startswith("application/json")
                and "content-encoding" not in headers
                and len(body) >= self.minimum_size
            ):
                compressed = gzip.compress(body, compresslevel=5)
                headers["content-encoding"] = "gzip"
                headers["content-length"] = str(len(compressed))
                headers.add_vary_header("Accept-Encoding")
                message = {**message, "body": compressed}
            passthrough = True
            await send(start)
            await send(message)

        await self.app(scope, receive, send_json)
