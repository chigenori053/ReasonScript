"""Request-origin guard for the local Playground backend.

The backend reads and writes files on behalf of the local IDE, so it must only
be reachable from local IDE pages. Browsers attach an ``Origin`` header to every
cross-origin request and to every same-origin non-GET request, which also
covers DNS-rebinding pages. Requests that carry a non-local ``Origin`` are
rejected before routing. Non-browser clients (CLI, tests) send no ``Origin``
and are already limited to the loopback interface by the bind address.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Awaitable, Callable

LOCAL_ORIGIN_REGEX = (
    r"^(?:https?|tauri)://(?:localhost|127\.0\.0\.1|\[::1\]|tauri\.localhost)(?::\d+)?$"
)
EXTRA_ORIGINS_ENV = "REASONSCRIPT_PLAYGROUND_ALLOWED_ORIGINS"

_LOCAL_ORIGIN = re.compile(LOCAL_ORIGIN_REGEX)


def allowed_extra_origins() -> frozenset[str]:
    raw = os.environ.get(EXTRA_ORIGINS_ENV, "")
    return frozenset(item.strip().rstrip("/") for item in raw.split(",") if item.strip())


def is_allowed_origin(origin: str | None) -> bool:
    if origin is None:
        return True
    return bool(_LOCAL_ORIGIN.match(origin)) or origin.rstrip("/") in allowed_extra_origins()


class LocalOriginGuard:
    """ASGI middleware that rejects HTTP requests from non-local origins."""

    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") == "http":
            origin = None
            for name, value in scope.get("headers", []):
                if name == b"origin":
                    origin = value.decode("latin-1")
                    break
            if not is_allowed_origin(origin):
                body = json.dumps({
                    "ok": False,
                    "errors": [{"type": "Forbidden", "message": "request origin is not allowed"}],
                }).encode("utf-8")
                await send({
                    "type": "http.response.start",
                    "status": 403,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode("ascii")),
                    ],
                })
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)
