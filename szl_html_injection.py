"""Lossless, bounded ASGI HTML injection for the existing landing binder.
SPDX-License-Identifier: Apache-2.0

Replace the existing _install_landing_honest_bind middleware registration with
this middleware; do not register both. Test inside the canonical production image.
No change is made when the body is compressed, signed/digested, partial, oversized,
not root HTML, HEAD, or does not contain the closing body marker.
"""
from __future__ import annotations
from typing import Any, Awaitable, Callable

Message = dict[str, Any]
Send = Callable[[Message], Awaitable[None]]

class LandingInjectionMiddleware:
    def __init__(self, app: Callable[..., Awaitable[None]], max_bytes: int = 2_000_000, max_chunks: int = 1024):
        if type(max_bytes) is not int or not 1 <= max_bytes <= 2_000_000:
            raise ValueError("bounded byte limit required")
        if type(max_chunks) is not int or not 1 <= max_chunks <= 4096:
            raise ValueError("bounded chunk limit required")
        self.app, self.max_bytes, self.max_chunks = app, max_bytes, max_chunks
        self.marker = b"landing-honest-bind.js"
        self.tag = b'<script src="/static/landing-honest-bind.js" defer data-szl-honest-bind="1"></script>'

    async def __call__(self, scope: Message, receive: Callable, send: Send) -> None:
        if scope.get("type") != "http" or scope.get("method") != "GET" or scope.get("path") != "/":
            await self.app(scope, receive, send)
            return
        start: Message | None = None
        pending: list[Message] = []
        size = 0
        passthrough = False

        async def flush() -> None:
            nonlocal start
            if start is not None:
                await send(start)
                start = None
            for item in pending:
                await send(item)
            pending.clear()

        async def wrapped(message: Message) -> None:
            nonlocal start, size, passthrough
            if passthrough:
                await send(message)
                return
            if message["type"] == "http.response.start":
                headers = [(k.lower(), v) for k, v in message.get("headers", [])]
                values: dict[bytes, list[bytes]] = {}
                for key, value in headers:
                    values.setdefault(key, []).append(value)
                types = values.get(b"content-type", [])
                encodings = values.get(b"content-encoding", [])
                can_rewrite = (message.get("status") == 200 and len(types) == 1 and
                    types[0].split(b";")[0].strip().lower() == b"text/html" and
                    (not encodings or encodings == [b"identity"]) and
                    not any(k in values for k in (b"content-range", b"digest", b"content-digest", b"signature", b"signature-input", b"content-md5")))
                lengths = values.get(b"content-length", [])
                if lengths:
                    try:
                        can_rewrite = can_rewrite and len(lengths) == 1 and 0 <= int(lengths[0]) <= self.max_bytes
                    except ValueError:
                        can_rewrite = False
                if not can_rewrite:
                    passthrough = True
                    await send(message)
                else:
                    start = {**message, "headers": list(message.get("headers", []))}
                return
            if message["type"] != "http.response.body" or start is None:
                await flush()
                passthrough = True
                await send(message)
                return
            raw = message.get("body", b"")
            if type(raw) is not bytes:
                raise TypeError("ASGI body must be bytes")
            # Account before buffering. On overflow, replay every byte and header,
            # then forward subsequent chunks unchanged. NEVER break/drop a stream.
            if size + len(raw) > self.max_bytes or len(pending) >= self.max_chunks:
                await flush()
                passthrough = True
                await send(message)
                return
            pending.append(dict(message))
            size += len(raw)
            if message.get("more_body", False):
                return
            body = b"".join(m.get("body", b"") for m in pending)
            if self.marker in body or b"</body>" not in body:
                await flush()
                passthrough = True
                return
            rewritten = body.replace(b"</body>", self.tag + b"</body>", 1)
            # Strip validators for the OLD entity; no new validator is invented.
            old = start
            headers = [(k, v) for k, v in old.get("headers", []) if k.lower() not in
                       {b"content-length", b"etag", b"last-modified"}]
            headers.append((b"content-length", str(len(rewritten)).encode("ascii")))
            start = None
            pending.clear()
            passthrough = True
            await send({**old, "headers": headers})
            await send({**message, "body": rewritten, "more_body": False})

        await self.app(scope, receive, wrapped)
