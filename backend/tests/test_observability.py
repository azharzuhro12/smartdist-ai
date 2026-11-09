import pytest
from fastapi.testclient import TestClient
from backend.app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_observability_middleware_generates_request_id(client):
    """Requests without X-Request-ID should have a UUID generated and returned in headers."""
    response = client.get("/health")
    assert response.status_code == 200
    assert "x-request-id" in response.headers
    request_id = response.headers["x-request-id"]
    assert len(request_id) > 10


def test_observability_middleware_propagates_incoming_request_id(client):
    """Requests with incoming X-Request-ID should preserve and return the exact ID."""
    custom_id = "test-custom-tracking-id-998877"
    response = client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("x-request-id") == custom_id


def test_deep_health_endpoint_response_structure(client):
    """API v1 health check returns deep multi-service status (database, redis, celery)."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "services" in data
    assert "database" in data["services"]
    assert "redis" in data["services"]
    assert "celery" in data["services"]

