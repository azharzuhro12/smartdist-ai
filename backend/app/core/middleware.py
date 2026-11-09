"""
Production middleware for SmartDist AI:
1. Request ID / Correlation ID tracking across log events.
2. CSRF and Origin protection on cookie-authenticated mutating requests.
"""

import time
import uuid
from contextvars import ContextVar
from typing import Optional
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.core.csrf import verify_csrf_and_origin
from backend.app.core.logging import logger

# ContextVar storing request_id for the current task context
correlation_id_ctx: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def get_current_request_id() -> Optional[str]:
    """Returns the correlation/request ID for the active request context."""
    return correlation_id_ctx.get()


class ObservabilityAndSecurityMiddleware(BaseHTTPMiddleware):
    """
    Combined production middleware handling:
    1. X-Request-ID propagation
    2. CSRF and Origin validation
    3. Request latency logging without exposing sensitive payload details
    """

    async def dispatch(self, request: Request, call_next):
        # 1. Establish Request / Correlation ID
        request_id = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        token = correlation_id_ctx.set(request_id)

        start_time = time.perf_counter()

        # 2. Enforce CSRF & Origin validation on cookie-authenticated mutating requests
        try:
            verify_csrf_and_origin(request)
        except HTTPException as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.warning(
                f"[{request_id}] CSRF/Origin validation rejected {request.method} {request.url.path}: {exc.detail} ({duration_ms}ms)"
            )
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": "Forbidden",
                    "message": exc.detail,
                    "request_id": request_id,
                },
                headers={"X-Request-ID": request_id},
            )

        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            # Attach correlation ID to response headers
            response.headers["X-Request-ID"] = request_id

            # Log request outcome (omit passwords, query params with tokens)
            if request.url.path not in ["/health", "/api/v1/health"]:
                logger.info(
                    f"[{request_id}] {request.method} {request.url.path} -> {response.status_code} ({duration_ms}ms)"
                )

            return response

        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                f"[{request_id}] Unhandled error processing {request.method} {request.url.path}: {str(exc)} ({duration_ms}ms)",
                exc_info=True,
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Internal Server Error",
                    "message": "An unexpected server error occurred. Please contact the administrator.",
                    "request_id": request_id,
                },
                headers={"X-Request-ID": request_id},
            )
        finally:
            correlation_id_ctx.reset(token)

