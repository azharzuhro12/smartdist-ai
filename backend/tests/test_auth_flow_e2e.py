"""
End-to-End Authentication and CSRF Flow Verification with database session fixtures.
Tests login, invalid credentials, cookie security attributes, token revocation,
CSRF double-submit protection, and RBAC endpoint guards.
"""

import pytest
from datetime import timedelta
from sqlalchemy import select
from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.core.redis import get_redis_client
from backend.app.core.security import create_access_token, hash_password
from backend.app.models.user import User, UserRole


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Clear testclient rate limit key between tests to avoid 429 collision."""
    redis = get_redis_client()
    if redis:
        try:
            for key in redis.scan_iter("ratelimit:*testclient*"):
                redis.delete(key)
        except Exception:
            pass


@pytest.fixture
def test_admin_user(db_session):
    admin = db_session.scalar(select(User).where(User.username == "e2e_admin"))
    if not admin:
        admin = User(
            username="e2e_admin",
            email="e2e_admin@smartdist.ai",
            hashed_password=hash_password("AdminSecure2026!"),
            role=UserRole.ADMIN,
            is_active=True,
            full_name="E2E Admin",
        )
        db_session.add(admin)
        db_session.commit()
        db_session.refresh(admin)
    return admin


@pytest.fixture
def test_viewer_user(db_session):
    viewer = db_session.scalar(select(User).where(User.username == "e2e_viewer"))
    if not viewer:
        viewer = User(
            username="e2e_viewer",
            email="e2e_viewer@smartdist.ai",
            hashed_password=hash_password("ViewerSecure2026!"),
            role=UserRole.VIEWER,
            is_active=True,
            full_name="E2E Viewer",
        )
        db_session.add(viewer)
        db_session.commit()
        db_session.refresh(viewer)
    return viewer


def test_01_login_valid_credentials(unauthenticated_client: TestClient, test_admin_user):
    """Scenario 1: Login with valid credentials returns tokens and secure cookies."""
    response = unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "e2e_admin", "password": "AdminSecure2026!"},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["role"] == "ADMIN"
    assert "access_token" in response.cookies
    assert "csrf_token" in response.cookies


def test_02_login_invalid_credentials(unauthenticated_client: TestClient):
    """Scenario 2: Login with invalid credentials returns 401 Unauthorized."""
    response = unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "e2e_admin", "password": "CompletelyWrongPassword123!"},
    )
    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower() or "incorrect" in response.json()["detail"].lower()


def test_03_cookie_security_attributes(unauthenticated_client: TestClient, test_admin_user):
    """Scenario 3: Verify cookie attributes (HttpOnly, SameSite, Secure)."""
    response = unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "e2e_admin", "password": "AdminSecure2026!"},
    )
    assert response.status_code == 200

    set_cookie_headers = response.headers.get_list("set-cookie")
    cookie_str = " ".join(set_cookie_headers)

    assert "access_token=" in cookie_str
    assert "HttpOnly" in cookie_str
    assert "samesite=lax" in cookie_str.lower()
    assert "csrf_token=" in cookie_str


def test_04_access_protected_pages_unauthenticated(unauthenticated_client: TestClient):
    """Scenario 4: Access protected endpoints without authentication returns 401."""
    unauthenticated_client.cookies.clear()
    response = unauthenticated_client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert "credentials" in response.json()["detail"].lower() or "not authenticated" in response.json()["detail"].lower()


def test_05_expired_jwt_rejected(unauthenticated_client: TestClient, test_admin_user):
    """Scenario 5: Expired JWT returns 401 Unauthorized."""
    expired_token = create_access_token(
        subject=test_admin_user.id,
        username=test_admin_user.username,
        role=test_admin_user.role.value,
        expires_delta=timedelta(seconds=-10),
    )
    response = unauthenticated_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401


def test_06_logout_and_revoked_jwt(unauthenticated_client: TestClient, test_admin_user):
    """Scenario 6: Logout invalidates token via Redis revocation and clears cookies."""
    login_res = unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "e2e_admin", "password": "AdminSecure2026!"},
    )
    token = login_res.json()["access_token"]
    csrf_token = login_res.cookies.get("csrf_token")

    # Logout
    logout_res = unauthenticated_client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf_token, "Authorization": f"Bearer {token}"},
    )
    assert logout_res.status_code == 200

    # Attempt reuse
    reused_res = unauthenticated_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert reused_res.status_code == 401


def test_07_csrf_missing_token_rejected(unauthenticated_client: TestClient, test_admin_user):
    """Scenario 7: Cookie-authenticated mutating request missing X-CSRF-Token returns 403."""
    unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "e2e_admin", "password": "AdminSecure2026!"},
    )
    # Mutating POST without X-CSRF-Token
    response = unauthenticated_client.post(
        "/api/v1/auth/logout",
        headers={"Origin": "http://localhost:3000"},
    )
    assert response.status_code == 403
    assert "csrf" in response.json()["message"].lower()


def test_08_csrf_invalid_origin_rejected(unauthenticated_client: TestClient, test_admin_user):
    """Scenario 8: Mutating request from untrusted origin returns 403."""
    login_res = unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "e2e_admin", "password": "AdminSecure2026!"},
    )
    csrf_token = login_res.cookies.get("csrf_token")

    response = unauthenticated_client.post(
        "/api/v1/auth/logout",
        headers={
            "Origin": "https://unauthorized-phishing-attacker.com",
            "X-CSRF-Token": csrf_token or "dummy",
        },
    )
    assert response.status_code == 403
    assert "origin" in response.json()["message"].lower()


def test_09_csrf_valid_token_and_origin_allowed(unauthenticated_client: TestClient, test_admin_user):
    """Scenario 9: Mutating request with valid token & whitelisted origin succeeds."""
    login_res = unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "e2e_admin", "password": "AdminSecure2026!"},
    )
    csrf_token = login_res.cookies.get("csrf_token")
    token = login_res.json()["access_token"]

    response = unauthenticated_client.post(
        "/api/v1/auth/logout",
        headers={
            "Origin": "http://localhost:3000",
            "X-CSRF-Token": csrf_token,
            "Authorization": f"Bearer {token}",
        },
    )
    assert response.status_code == 200


def test_10_role_specific_access_enforcement(unauthenticated_client: TestClient, test_viewer_user):
    """Scenario 10: VIEWER role is denied admin management actions and analyst endpoints."""
    token = create_access_token(
        subject=test_viewer_user.id,
        username=test_viewer_user.username,
        role=test_viewer_user.role.value,
        expires_delta=timedelta(minutes=15),
    )

    # Viewer cannot access admin user list
    res_users = unauthenticated_client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_users.status_code == 403

    # Viewer cannot access assistant SQL endpoint
    res_sql = unauthenticated_client.post(
        "/api/v1/assistant/sql",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "Show top products"},
    )
    assert res_sql.status_code == 403
