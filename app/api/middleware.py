"""Request correlation middleware.

Assigns (or propagates) an X-Request-ID per request, binds it to the
logging contextvar so every log line downstream is correlated, echoes it
back in the response header, and logs one structured access line with
total latency. Pure ASGI-adjacent concern — no business logic.
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.utils.logging import get_logger, request_id_var

logger = get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Binds a request ID to context and measures wall-clock latency."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        request_id_var.set(request_id)

        start = time.perf_counter()
        response = await call_next(request)
        latency_ms = (time.perf_counter() - start) * 1000

        response.headers[REQUEST_ID_HEADER] = request_id
        for header, value in _SECURITY_HEADERS.items():
            response.headers[header] = value
        logger.info(
            "request completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "latency_ms": round(latency_ms, 2),
            },
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window per-IP rate limiter for the expensive LLM endpoints.

    In-memory by design: correct for a single process, and the interface
    (middleware) stays identical when a Redis-backed limiter replaces it
    for multi-instance deployments. Disabled when limit == 0.
    """

    LIMITED_PATHS = ("/triage", "/debug")
    WINDOW_SECONDS = 60.0

    def __init__(self, app: object, requests_per_minute: int) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._limit = requests_per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if self._limit <= 0 or request.url.path not in self.LIMITED_PATHS:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = self._hits[client_ip]
        while window and now - window[0] > self.WINDOW_SECONDS:
            window.popleft()
        if len(window) >= self._limit:
            logger.warning("rate limit exceeded", extra={"client_ip": client_ip, "path": request.url.path})
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limited",
                    "request_id": request_id_var.get(),
                    "detail": "Too many requests. Please slow down.",
                },
                headers={"Retry-After": "60"},
            )
        window.append(now)
        return await call_next(request)
