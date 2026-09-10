"""
backend/middleware.py
=====================
ASGI middleware for:
- Unique X-Request-ID tracing
- X-Process-Time performance calculation (in milliseconds)
- In-memory rate limiting with HTTP 429 response
- Structured access logging
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Callable, Set

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config import get_settings
from backend.rate_limit import get_client_ip, rate_limiter

log = logging.getLogger("mercury.access")
settings = get_settings()

RATE_LIMIT_EXEMPT_PATHS: Set[str] = {
    "/",
    "/health",
    "/api/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
}


def is_rate_limit_exempt(path: str) -> bool:
    """Checks if request path should bypass rate limiting."""
    clean_path = path.rstrip("/") if path != "/" else "/"
    return clean_path in RATE_LIMIT_EXEMPT_PATHS or path.startswith("/docs") or path.startswith("/redoc")


class RequestTracingAndSecurityMiddleware(BaseHTTPMiddleware):
    """
    Core ASGI middleware that attaches X-Request-ID and X-Process-Time headers,
    applies rate limiting, and emits structured access logs.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        # 1. Resolve or generate request tracing ID
        incoming_req_id = request.headers.get("x-request-id")
        request_id = incoming_req_id.strip() if incoming_req_id else str(uuid.uuid4())
        request.state.request_id = request_id

        client_ip = get_client_ip(request)
        start_time = time.perf_counter()

        # 2. Rate Limiting Check
        req_settings = get_settings()
        if req_settings.rate_limit_enabled and not is_rate_limit_exempt(request.url.path):
            allowed, remaining, retry_after = rate_limiter.is_allowed(
                client_ip,
                limit=req_settings.rate_limit_requests_per_minute,
            )
            if not allowed:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                log.warning(
                    "Rate limit exceeded for %s on %s (request_id=%s)",
                    client_ip,
                    request.url.path,
                    request_id,
                )
                headers = {
                    "Retry-After": str(retry_after),
                    "X-Request-ID": request_id,
                    "X-Process-Time": f"{elapsed_ms:.2f}ms",
                    "X-RateLimit-Limit": str(req_settings.rate_limit_requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                }
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Rate limit exceeded. Too many requests. Please retry after specified seconds.",
                        "retry_after": retry_after,
                        "request_id": request_id,
                    },
                    headers=headers,
                )

        # 3. Process Request and Handle Unhandled Exceptions
        try:
            response = await call_next(request)
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            log.exception(
                "Unhandled error processing %s %s (request_id=%s): %s",
                request.method,
                request.url.path,
                request_id,
                exc,
            )
            headers = {
                "X-Request-ID": request_id,
                "X-Process-Time": f"{elapsed_ms:.2f}ms",
            }
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "request_id": request_id,
                },
                headers=headers,
            )

        # 4. Attach Diagnostic Headers
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{elapsed_ms:.2f}ms"

        # 5. Emit Structured Access Log
        log.info(
            '%s - "%s %s" %d [%.2fms] (req_id=%s)',
            client_ip,
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request_id,
        )

        return response
