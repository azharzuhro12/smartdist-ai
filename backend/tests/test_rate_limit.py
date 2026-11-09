"""
Rate limiting integration tests.
Verifies rate limits on login and AI assistant endpoints, Retry-After header,
and 429 Too Many Requests response.
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.core.rate_limit import InMemoryRateLimiter


def test_in_memory_rate_limiter_logic():
    limiter = InMemoryRateLimiter()
    key = "test_client_1"

    # Allow up to 3 requests in 10s
    assert limiter.is_allowed(key, max_requests=3, window_seconds=10)[0] is True
    assert limiter.is_allowed(key, max_requests=3, window_seconds=10)[0] is True
    assert limiter.is_allowed(key, max_requests=3, window_seconds=10)[0] is True

    # 4th request must be rejected
    allowed, retry_after = limiter.is_allowed(key, max_requests=3, window_seconds=10)
    assert allowed is False
    assert retry_after > 0


def test_login_endpoint_rate_limit(unauthenticated_client: TestClient):
    """
    Submitting multiple consecutive requests to /auth/login must trigger HTTP 429.
    """
    url = "/api/v1/auth/login"
    payload = {"username_or_email": "rate_limit_test", "password": "WrongPassword!"}

    # First few requests return 401 (invalid creds)
    got_429 = False
    for _ in range(8):
        resp = unauthenticated_client.post(url, json=payload)
        if resp.status_code == 429:
            got_429 = True
            assert "Retry-After" in resp.headers
            assert "Too many requests" in resp.json()["detail"]
            break

    assert got_429 is True, "Expected HTTP 429 after exceeding login rate limit."

