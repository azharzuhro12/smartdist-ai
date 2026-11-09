"""
Distributed Redis-backed rate limiting with thread-safe in-memory fallback.
Supports trusted proxy IP resolution and fail-closed security policy for sensitive endpoints.
"""

import time
from collections import defaultdict
from threading import Lock
from typing import Dict, List, Optional, Tuple
from fastapi import Request, HTTPException, status

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.core.redis import get_redis_client


class InMemoryRateLimiter:
    """Thread-safe sliding window rate limiter for local in-memory fallback."""

    def __init__(self):
        self._requests: Dict[str, List[float]] = defaultdict(list)
        self._lock = Lock()

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int]:
        now = time.time()
        cutoff = now - window_seconds
        with self._lock:
            timestamps = self._requests[key]
            # Prune old timestamps
            self._requests[key] = [t for t in timestamps if t > cutoff]
            current_count = len(self._requests[key])

            if current_count >= max_requests:
                oldest = self._requests[key][0]
                retry_after = max(1, int(oldest + window_seconds - now))
                return False, retry_after

            self._requests[key].append(now)
            return True, 0


_memory_limiter = InMemoryRateLimiter()


def get_client_ip(request: Request, trusted_proxies: Optional[List[str]] = None) -> str:
    """
    Safely resolves client IP.
    By default, uses direct client connection host to prevent X-Forwarded-For spoofing.
    If behind verified trusted proxies, extracts the rightmost untrusted IP from X-Forwarded-For.
    """
    direct_ip = request.client.host if request.client else "127.0.0.1"

    if trusted_proxies and direct_ip in trusted_proxies:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For: client, proxy1, proxy2
            ips = [ip.strip() for ip in forwarded_for.split(",") if ip.strip()]
            if ips:
                return ips[0]

    return direct_ip


def check_rate_limit(
    key: str,
    max_requests: int,
    window_seconds: int = 60,
    fail_closed: bool = False,
) -> None:
    """
    Checks rate limit using Redis, with fallback to in-memory limiter.
    Raises HTTPException 429 if the rate limit is exceeded.
    """
    redis_client = get_redis_client()
    allowed = True
    retry_after = 1

    if redis_client:
        try:
            redis_key = f"ratelimit:{key}"
            pipe = redis_client.pipeline()
            now = time.time()
            cutoff = now - window_seconds

            # Clean expired and add current timestamp in a sorted set
            pipe.zremrangebyscore(redis_key, 0, cutoff)
            pipe.zcard(redis_key)
            pipe.zadd(redis_key, {str(now): now})
            pipe.expire(redis_key, window_seconds + 5)
            results = pipe.execute()

            request_count = results[1]
            if request_count >= max_requests:
                allowed = False
                retry_after = window_seconds
        except Exception as exc:
            if fail_closed:
                logger.error(f"Redis rate limiter failed for sensitive endpoint ({key}): {exc}. Enforcing fail-closed policy.")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication service temporarily unavailable: security rate limiter storage offline.",
                )
            logger.warning(f"Redis rate limiter failed: {exc}. Falling back to in-memory.")
            allowed, retry_after = _memory_limiter.is_allowed(key, max_requests, window_seconds)
    else:
        if fail_closed:
            logger.error(f"Redis client unavailable for sensitive endpoint ({key}). Enforcing fail-closed policy.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service temporarily unavailable: security rate limiter storage offline.",
            )
        # Fallback to in-memory sliding window for non-sensitive operations
        allowed, retry_after = _memory_limiter.is_allowed(key, max_requests, window_seconds)

    if not allowed:
        logger.warning(f"Rate limit exceeded for {key}: max {max_requests}/{window_seconds}s")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. Please wait {retry_after} seconds before retrying.",
            headers={"Retry-After": str(retry_after)},
        )

