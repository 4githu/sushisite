"""Streaming-safe, metadata-only request timing and a cheap liveness endpoint."""
import logging
import time

from starlette.responses import JSONResponse

logger = logging.getLogger("uvicorn.error")


class RuntimeHealthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        if scope["path"] == "/api/healthz" and scope["method"] in {"GET", "HEAD"}:
            response = JSONResponse({"status": "ok"}, headers={"Cache-Control": "no-store"})
            return await response(scope, receive, send)
        started = time.perf_counter()

        async def timed_send(message):
            if message["type"] == "http.response.start":
                elapsed_ms = (time.perf_counter() - started) * 1000
                headers = list(message.get("headers", []))
                headers.append((b"server-timing", f"app;dur={elapsed_ms:.1f}".encode()))
                message = {**message, "headers": headers}
                if elapsed_ms >= 1000 or message["status"] >= 500:
                    # Route templates omit identifiers. Never log query strings, cookies or bodies.
                    route = getattr(scope.get("route"), "path", "<unmatched>")
                    logger.warning("request_timing method=%s route=%s status=%s ttfb_ms=%.1f",
                                   scope["method"], route, message["status"], elapsed_ms)
            await send(message)

        await self.app(scope, receive, timed_send)
