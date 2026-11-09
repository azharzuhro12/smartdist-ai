from fastapi.testclient import TestClient


def test_root_health_endpoint(client: TestClient):
    """Verify root GET /health returns HTTP 200 with valid metadata."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == "SmartDist AI"
    assert "version" in data
    assert "environment" in data
    assert "timestamp" in data
    assert data["services"] == {"app": "running"}


def test_api_v1_health_endpoint(client: TestClient):
    """Verify GET /api/v1/health returns HTTP 200 with services health breakdown."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded", "unhealthy"]
    assert data["app_name"] == "SmartDist AI"
    assert "services" in data
    assert "database" in data["services"]
    assert "redis" in data["services"]
    # Ensure no passwords or secret credentials leaked in output
    response_text = response.text.lower()
    assert "password" not in response_text
    assert "secret" not in response_text
