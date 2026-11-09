import pytest
from unittest.mock import patch
from fastapi import HTTPException
from backend.app.core.rate_limit import check_rate_limit


def test_rate_limiter_fail_closed_raises_503():
    """
    When fail_closed=True (e.g. for authentication endpoints),
    if Redis client is unavailable or raises an exception, the system must fail closed
    with HTTP 503 instead of allowing unbounded attempts.
    """
    with patch("backend.app.core.rate_limit.get_redis_client", return_value=None):
        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit(
                key="login:192.168.1.100",
                max_requests=5,
                window_seconds=60,
                fail_closed=True,
            )
        assert exc_info.value.status_code == 503
        assert "temporarily unavailable" in exc_info.value.detail.lower()


def test_rate_limiter_fail_open_for_non_sensitive():
    """
    When fail_closed=False (for non-security-critical public read endpoints),
    a Redis failure falls back gracefully to in-memory limiting without raising 503.
    """
    with patch("backend.app.core.rate_limit.get_redis_client", return_value=None):
        # Should execute cleanly without raising HTTPException
        check_rate_limit(
            key="public_test_key_failopen",
            max_requests=10,
            window_seconds=60,
            fail_closed=False,
        )
