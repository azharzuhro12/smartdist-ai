import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.config import settings
from backend.app.core.csrf import generate_csrf_token


@pytest.fixture
def client():
    return TestClient(app)


def test_cors_preflight_allowed_origin(client):
    """Allowed origin preflight request must receive CORS headers."""
    allowed = settings.CORS_ORIGINS[0] if isinstance(settings.CORS_ORIGINS, list) else "http://localhost:3000"
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": allowed,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == allowed


def test_cors_disallowed_origin(client):
    """Disallowed foreign origin must not receive Access-Control-Allow-Origin header matching foreign site."""
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "https://malicious-attacker-site.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.headers.get("access-control-allow-origin") != "https://malicious-attacker-site.com"


def test_csrf_cookie_missing_header_rejected(client):
    """
    If access_token cookie is present (cookie-authenticated mutating request),
    submitting without X-CSRF-Token or mismatch must be rejected with 403.
    """
    client.cookies.set("access_token", "fake_cookie_token")
    client.cookies.set("csrf_token", "valid_csrf_token_secret")

    response = client.post(
        "/api/v1/auth/logout",
        headers={"Origin": "http://localhost:3000"},
        # Missing X-CSRF-Token header
    )
    assert response.status_code == 403
    data = response.json()
    assert "CSRF" in data["message"] or data["error"] == "Forbidden"


def test_csrf_cookie_with_matching_header_allowed(client):
    """
    Cookie-authenticated mutating request with matching X-CSRF-Token header passes CSRF verification.
    """
    token = generate_csrf_token()
    client.cookies.set("csrf_token", token)

    response = client.post(
        "/api/v1/auth/logout",
        headers={
            "Origin": "http://localhost:3000",
            "X-CSRF-Token": token,
        },
    )
    # Passed CSRF check (may return 200 or 401 depending on valid JWT auth)
    assert response.status_code != 403


def test_csrf_safe_methods_exempt(client):
    """GET requests must never be blocked by CSRF validation."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200

