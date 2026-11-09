"""
Role-Based Access Control (RBAC) tests.
Verifies permission boundaries across ADMIN, ANALYST, and VIEWER roles,
unauthenticated rejection (401), and forbidden access (403).
"""

import pytest
from sqlalchemy import select
from fastapi.testclient import TestClient

from backend.app.core.security import create_access_token, hash_password
from backend.app.models.user import User, UserRole
from backend.app.models.anomaly import SalesAnomaly


@pytest.fixture
def test_users(db_session):
    """Creates a trio of test users representing each role."""
    roles_map = {}
    for role in [UserRole.ADMIN, UserRole.ANALYST, UserRole.VIEWER]:
        uname = f"rbac_user_{role.value.lower()}"
        user = db_session.scalar(select(User).where(User.username == uname))
        if not user:
            user = User(
                username=uname,
                email=f"{uname}@smartdist.ai",
                hashed_password=hash_password("Password123!"),
                role=role,
                is_active=True,
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)
        roles_map[role.value] = user
    return roles_map


def auth_header_for_user(user: User) -> dict:
    token = create_access_token(
        subject=user.id,
        username=user.username,
        role=user.role.value,
    )
    return {"Authorization": f"Bearer {token}"}


def test_unauthenticated_request_blocked(unauthenticated_client: TestClient):
    resp = unauthenticated_client.get("/api/v1/users")
    assert resp.status_code == 401

    resp_sales = unauthenticated_client.get("/api/v1/sales/daily")
    assert resp_sales.status_code == 401


def test_admin_access_user_management(unauthenticated_client: TestClient, test_users):
    admin_header = auth_header_for_user(test_users["ADMIN"])
    resp = unauthenticated_client.get("/api/v1/users", headers=admin_header)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_analyst_cannot_access_user_management(unauthenticated_client: TestClient, test_users):
    analyst_header = auth_header_for_user(test_users["ANALYST"])
    resp = unauthenticated_client.get("/api/v1/users", headers=analyst_header)
    assert resp.status_code == 403
    assert "Forbidden" in resp.json()["detail"]


def test_viewer_cannot_access_user_management(unauthenticated_client: TestClient, test_users):
    viewer_header = auth_header_for_user(test_users["VIEWER"])
    resp = unauthenticated_client.get("/api/v1/users", headers=viewer_header)
    assert resp.status_code == 403
    assert "Forbidden" in resp.json()["detail"]


def test_viewer_can_read_business_data(unauthenticated_client: TestClient, test_users):
    viewer_header = auth_header_for_user(test_users["VIEWER"])
    resp = unauthenticated_client.get("/api/v1/sales/daily", headers=viewer_header)
    assert resp.status_code == 200

    resp_inv = unauthenticated_client.get("/api/v1/inventory/optimization-summary", headers=viewer_header)
    assert resp_inv.status_code == 200


def test_viewer_cannot_modify_anomaly_status(unauthenticated_client: TestClient, test_users, db_session):
    # Find or create a test anomaly
    anomaly = db_session.scalar(select(SalesAnomaly))
    if not anomaly:
        pytest.skip("No sales anomaly available in database to test modification.")

    viewer_header = auth_header_for_user(test_users["VIEWER"])
    resp = unauthenticated_client.patch(
        f"/api/v1/anomalies/{anomaly.id}/status",
        headers=viewer_header,
        json={"status": "INVESTIGATING", "resolution_note": "Attempt by viewer"},
    )
    assert resp.status_code == 403
    assert "Forbidden" in resp.json()["detail"]


def test_analyst_can_modify_anomaly_status(unauthenticated_client: TestClient, test_users, db_session):
    anomaly = db_session.scalar(select(SalesAnomaly))
    if not anomaly:
        pytest.skip("No sales anomaly available in database to test modification.")

    analyst_header = auth_header_for_user(test_users["ANALYST"])
    resp = unauthenticated_client.patch(
        f"/api/v1/anomalies/{anomaly.id}/status",
        headers=analyst_header,
        json={"status": "INVESTIGATING", "resolution_note": "Analyst triage note"},
    )
    assert resp.status_code == 200
    assert resp.json()["investigation_status"] == "INVESTIGATING"


def test_viewer_cannot_execute_sql(unauthenticated_client: TestClient, test_users):
    viewer_header = auth_header_for_user(test_users["VIEWER"])
    resp = unauthenticated_client.post(
        "/api/v1/assistant/sql",
        headers=viewer_header,
        json={"query": "What are the top 5 products?"},
    )
    assert resp.status_code == 403


def test_analyst_can_execute_sql(unauthenticated_client: TestClient, test_users):
    analyst_header = auth_header_for_user(test_users["ANALYST"])
    resp = unauthenticated_client.post(
        "/api/v1/assistant/sql",
        headers=analyst_header,
        json={"query": "What are the top 5 products?"},
    )
    assert resp.status_code == 200
    assert "sql" in resp.json()
