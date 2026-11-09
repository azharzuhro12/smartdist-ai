"""
API Contract and Integration Tests for Frontend-Backend Alignment.
Verifies the exact routes and schemas consumed by the Next.js frontend:
1. Forecast endpoint: /api/v1/inventory/{product_id}/{branch_id}/forecast?horizon_days={horizon}
2. Optimization summary endpoint: /api/v1/inventory/optimization-summary?page={page}&size={size}
3. Anomaly status update: PATCH /api/v1/anomalies/{id}/status with {"status": "..."}
"""

import pytest
from fastapi.testclient import TestClient


def test_forecast_api_contract(client: TestClient):
    """Verify forecast route matches frontend expectations."""
    # Using known product 1 and branch 1
    response = client.get("/api/v1/inventory/1/1/forecast?horizon_days=7")
    assert response.status_code == 200, f"Forecast endpoint failed: {response.text}"
    
    data = response.json()
    assert "product_id" in data
    assert "branch_id" in data
    assert "horizon_days" in data
    assert "daily_forecasts" in data
    assert data["horizon_days"] == 7
    assert isinstance(data["daily_forecasts"], list)
    assert len(data["daily_forecasts"]) > 0
    
    first = data["daily_forecasts"][0]
    assert "date" in first
    assert "predicted_demand" in first
    assert "horizon_step" in first
    assert isinstance(first["predicted_demand"], (int, float))


def test_optimization_summary_api_contract(client: TestClient):
    """Verify optimization-summary route matches frontend expectations."""
    response = client.get("/api/v1/inventory/optimization-summary?page=1&size=5&service_level=0.95")
    assert response.status_code == 200, f"Optimization summary failed: {response.text}"
    
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "size" in data
    assert data["page"] == 1
    assert data["size"] == 5
    assert isinstance(data["items"], list)
    
    if len(data["items"]) > 0:
        item = data["items"][0]
        # Check required fields used in frontend Dashboard & Inventory Decision Engine
        assert "product_id" in item
        assert "branch_id" in item
        assert "reorder_point" in item
        assert "safety_stock" in item
        assert "decision" in item
        assert "recommended_order_quantity" in item
        assert "stockout_probability" in item


def test_anomaly_status_patch_api_contract(client: TestClient):
    """Verify anomaly status update route, pagination query params, and all 5 supported statuses."""
    list_resp = client.get("/api/v1/anomalies?page=1&size=1")
    assert list_resp.status_code == 200, f"Failed to list anomalies: {list_resp.text}"
    anomaly_envelope = list_resp.json()
    assert "items" in anomaly_envelope
    assert anomaly_envelope["size"] == 1
    anomalies = anomaly_envelope["items"]
    assert len(anomalies) == 1, "Expected 1 anomaly with size=1"
    anomaly_id = anomalies[0]["id"]
    original_status = anomalies[0]["investigation_status"]

    # Verify all 5 statuses supported by backend and frontend
    for target_status in ["INVESTIGATING", "CONFIRMED", "FALSE_POSITIVE", "RESOLVED", "NEW"]:
        patch_payload = {
            "status": target_status,
            "resolution_note": f"Contract verification: {target_status}",
        }
        patch_resp = client.patch(f"/api/v1/anomalies/{anomaly_id}/status", json=patch_payload)
        assert patch_resp.status_code == 200, f"Failed to patch {target_status}: {patch_resp.text}"
        patch_data = patch_resp.json()
        assert patch_data["investigation_status"] == target_status

    # Verify invalid status value is rejected with 400 Bad Request
    bad_resp = client.patch(
        f"/api/v1/anomalies/{anomaly_id}/status",
        json={"status": "INVALID_STATUS"},
    )
    assert bad_resp.status_code == 400

    # Verify legacy payload key {"investigation_status": ...} is rejected with 422
    legacy_resp = client.patch(
        f"/api/v1/anomalies/{anomaly_id}/status",
        json={"investigation_status": "INVESTIGATING"},
    )
    assert legacy_resp.status_code == 422

    # Restore original status
    client.patch(
        f"/api/v1/anomalies/{anomaly_id}/status",
        json={"status": original_status, "resolution_note": "Restored after contract test"},
    )

