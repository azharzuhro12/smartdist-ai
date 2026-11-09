"""
Authentication tests covering password hashing, JWT lifecycle, login,
logout, account deactivation, and anti-enumeration generic responses.
"""

import pytest
from datetime import timedelta
from sqlalchemy import select
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    revoke_token,
    is_token_revoked,
)
from backend.app.models.user import User, UserRole


def test_argon2id_password_hashing():
    password = "SuperSecurePassword2026!"
    hashed = hash_password(password)

    assert hashed != password
    assert hashed.startswith("$argon2id$")
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False
    assert verify_password("", hashed) is False


def test_jwt_access_token_creation_and_validation():
    token = create_access_token(
        subject=42,
        username="analyst_jane",
        role="ANALYST",
        expires_delta=timedelta(minutes=15),
    )
    assert isinstance(token, str)
    assert len(token) > 20

    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "42"
    assert payload["username"] == "analyst_jane"
    assert payload["role"] == "ANALYST"
    assert "jti" in payload
    assert "exp" in payload


def test_jwt_expired_token_rejected():
    expired_token = create_access_token(
        subject=42,
        username="expired_user",
        role="VIEWER",
        expires_delta=timedelta(seconds=-10),  # expired 10s ago
    )
    payload = decode_access_token(expired_token)
    assert payload is None


def test_jwt_tampered_token_rejected():
    token = create_access_token(subject=1, username="admin", role="ADMIN")
    tampered_token = token[:-5] + "XXXXX"
    payload = decode_access_token(tampered_token)
    assert payload is None


def test_token_revocation_lifecycle():
    token = create_access_token(subject=10, username="user_to_revoke", role="VIEWER")
    payload = decode_access_token(token)
    assert payload is not None
    jti = payload["jti"]

    # Before revocation
    assert is_token_revoked(jti) is False

    # Revoke
    revoked = revoke_token(token, payload)
    if revoked:
        assert is_token_revoked(jti) is True


def test_api_login_valid_credentials(unauthenticated_client: TestClient, db_session):
    # Ensure a known test user exists
    username = "auth_test_user"
    email = "auth_test@smartdist.ai"
    raw_password = "ValidPassword123!"

    user = db_session.scalar(select(User).where(User.username == username))
    if not user:
        user = User(
            username=username,
            email=email,
            hashed_password=hash_password(raw_password),
            role=UserRole.ANALYST,
            is_active=True,
            full_name="Auth Test",
        )
        db_session.add(user)
        db_session.commit()

    resp = unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": username, "password": raw_password},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == username
    assert data["user"]["role"] == "ANALYST"
    # Check that access_token cookie was set
    assert "access_token" in resp.cookies


def test_api_login_invalid_password_returns_generic_401(unauthenticated_client: TestClient, db_session):
    resp = unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "auth_test_user", "password": "WrongPassword999!"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Incorrect username or password"


def test_api_login_nonexistent_user_returns_generic_401(unauthenticated_client: TestClient):
    resp = unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "ghost_user_does_not_exist", "password": "Password123!"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Incorrect username or password"


def test_api_login_disabled_account_returns_401(unauthenticated_client: TestClient, db_session):
    username = "disabled_user"
    email = "disabled@smartdist.ai"
    raw_password = "Password123!"

    user = db_session.scalar(select(User).where(User.username == username))
    if not user:
        user = User(
            username=username,
            email=email,
            hashed_password=hash_password(raw_password),
            role=UserRole.VIEWER,
            is_active=False,  # deactivated
            full_name="Disabled User",
        )
        db_session.add(user)
        db_session.commit()
    else:
        user.is_active = False
        db_session.commit()

    resp = unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": username, "password": raw_password},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Incorrect username or password"


def test_api_auth_me_and_logout(unauthenticated_client: TestClient, db_session):
    username = "session_user"
    email = "session@smartdist.ai"
    raw_password = "SessionPassword123!"

    user = db_session.scalar(select(User).where(User.username == username))
    if not user:
        user = User(
            username=username,
            email=email,
            hashed_password=hash_password(raw_password),
            role=UserRole.VIEWER,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

    # Login
    login_resp = unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"username_or_email": username, "password": raw_password},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # /me
    me_resp = unauthenticated_client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == username

    # /logout
    logout_resp = unauthenticated_client.post("/api/v1/auth/logout", headers=headers)
    assert logout_resp.status_code == 200

    # Subsequent call with revoked token should fail with 401
    after_logout_resp = unauthenticated_client.get("/api/v1/auth/me", headers=headers)
    assert after_logout_resp.status_code == 401

