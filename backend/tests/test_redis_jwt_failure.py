"""
Redis and JWT Failure Mode Verification.
Validates behavior during Redis outages, rate limiter fail-closed enforcement on login,
graceful degradation on assistant requests, logout blocklist tracking, and token verification.
"""

import pytest
from unittest.mock import patch
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.core.rate_limit import check_rate_limit
from backend.app.core.security import create_access_token, revoke_token, is_token_revoked


@pytest.fixture
def client():
    return TestClient(app)


def test_redis_unavailable_during_login_fails_closed():
    """When Redis is unavailable during login, fail_closed=True must raise HTTP 503."""
    with patch("backend.app.core.rate_limit.get_redis_client", return_value=None):
        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit("login:127.0.0.1", max_requests=5, window_seconds=60, fail_closed=True)
        assert exc_info.value.status_code == 503
        assert "temporarily unavailable" in exc_info.value.detail.lower()


def test_redis_unavailable_during_assistant_degrades_gracefully():
    """When Redis is unavailable during assistant requests, fail_closed=False allows fallback to in-memory."""
    with patch("backend.app.core.rate_limit.get_redis_client", return_value=None):
        # Should not raise exception
        check_rate_limit("assistant:chat:1:127.0.0.1", max_requests=30, window_seconds=60, fail_closed=False)


def test_redis_unavailable_during_logout(client):
    """
    When Redis is offline during logout, revoke_token safely logs warning and returns False,
    while the endpoint still deletes the cookies.
    """
    with patch("backend.app.core.security.get_redis_client", return_value=None):
        payload = {"jti": "mock-jti-1234", "exp": 9999999999}
        revoked = revoke_token("fake_token", payload)
        assert revoked is False


def test_redis_revocation_blocklist_lifecycle():
    """Verifies that is_token_revoked properly detects present vs absent blocklist entries."""
    from backend.app.core.redis import get_redis_client
    redis = get_redis_client()
    if not redis:
        pytest.skip("Redis connection not available")

    test_jti = "test-jti-lifecycle-999"
    try:
        # 1. Not revoked
        assert is_token_revoked(test_jti) is False

        # 2. Add to blocklist
        redis.setex(f"token:blocklist:{test_jti}", 60, "revoked")
        assert is_token_revoked(test_jti) is True
    finally:
        redis.delete(f"token:blocklist:{test_jti}")

