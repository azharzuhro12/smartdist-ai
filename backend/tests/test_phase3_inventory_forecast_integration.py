from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.models.business import Branch, Inventory, Product, ProductSupplier, Supplier, Warehouse
from backend.app.schemas.inventory_forecast import (
    DailyForecastRecord,
    ForecastResponse,
    InventoryForecastSnapshot,
    InventoryRecordSummary,
    SupplierSummary,
)
from backend.app.services.forecast_service import ForecastIntegrationService
from backend.app.services.integration_validator import IntegrationValidator
from backend.app.services.inventory_service import InventoryService
from backend.app.services.snapshot_service import InventoryForecastSnapshotService


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. Inventory Integration Tests
# ---------------------------------------------------------------------------

def test_inventory_service_available_stock_calculation(db_session):
    # Retrieve product 1 and branch 1 which has warehouse 1
    inv = InventoryService.get_inventory_for_product_branch(db_session, product_id=1, branch_id=1)
    assert inv.product_id == 1
    assert inv.branch_id == 1
    assert inv.current_stock is not None
    assert inv.reserved_stock is not None
    assert inv.available_stock == inv.current_stock - inv.reserved_stock
    assert inv.supplier is not None
    assert inv.supplier.lead_time_days is not None


def test_inventory_service_missing_inventory_record(db_session):
    # Branch 2 has no direct warehouse in current synthetic setup
    inv = InventoryService.get_inventory_for_product_branch(db_session, product_id=1, branch_id=2)
    assert inv.product_id == 1
    assert inv.branch_id == 2
    assert inv.current_stock is None
    assert inv.available_stock is None
    assert inv.inventory_id is None


def test_inventory_service_missing_product(db_session):
    with pytest.raises(ValueError, match="Product ID 999999 not found"):
        InventoryService.get_inventory_for_product_branch(db_session, product_id=999999, branch_id=1)


def test_inventory_service_missing_branch(db_session):
    with pytest.raises(ValueError, match="Branch ID 999999 not found"):
        InventoryService.get_inventory_for_product_branch(db_session, product_id=1, branch_id=999999)


def test_inventory_service_missing_supplier(db_session):
    import uuid
    unique_code = f"PRD-TEST-{uuid.uuid4().hex[:8]}"
    # Create product without supplier
    p = Product(
        product_code=unique_code,
        product_name="Test Product No Supplier",
        category_id=1,
        source_family="AUTOMOTIVE",
        unit_of_measure="UNIT",
        is_active=True,
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)

    try:
        sup = InventoryService.get_supplier_for_product(db_session, p.id)
        assert sup is None
    finally:
        db_session.delete(p)
        db_session.commit()


# ---------------------------------------------------------------------------
# 2. Forecast Integration Tests
# ---------------------------------------------------------------------------

def test_forecast_integration_service_horizons(db_session):
    for h in [7, 14, 30]:
        fc = ForecastIntegrationService.get_forecast(db_session, product_id=1, branch_id=1, horizon_days=h)
        assert fc.status == "AVAILABLE"
        assert fc.horizon_days == h
        assert len(fc.daily_forecasts) == h
        assert fc.model_name == "lightgbm"
        assert fc.model_version == "v1"
        assert all(f.predicted_demand >= 0.0 for f in fc.daily_forecasts)


def test_forecast_integration_invalid_horizon(db_session):
    with pytest.raises(ValueError, match="Unsupported forecast horizon: 45"):
        ForecastIntegrationService.get_forecast(db_session, product_id=1, branch_id=1, horizon_days=45)


def test_forecast_integration_unobserved_series(db_session):
    # Query non-existent series in training history
    with patch.object(ForecastIntegrationService, "_get_series_history", return_value=pd.DataFrame()):
        fc = ForecastIntegrationService.get_forecast(db_session, product_id=1, branch_id=1, horizon_days=7)
        assert fc.status == "UNAVAILABLE"
        assert len(fc.daily_forecasts) == 0


def test_forecast_integration_nan_inf_detection(db_session):
    # Mock predictor returning NaN
    mock_df = pd.DataFrame([
        {"date": "2013-11-01", "store_nbr": 1, "product_id": 1, "prediction": float("nan"), "horizon_step": 1}
    ])
    with patch("backend.app.services.forecast_service.ForecastingPredictor") as MockPred:
        instance = MockPred.return_value
        instance.predict_recursive.return_value = mock_df
        with pytest.raises(ValueError, match="Prediction contains NaN values"):
            ForecastIntegrationService.get_forecast(db_session, product_id=1, branch_id=1, horizon_days=7)


# ---------------------------------------------------------------------------
# 3. Snapshot Service Tests
# ---------------------------------------------------------------------------

def test_snapshot_service_aggregation(db_session):
    snapshot = InventoryForecastSnapshotService.get_snapshot(db_session, product_id=1, branch_id=1, horizon_days=7)
    assert snapshot.product_id == 1
    assert snapshot.branch_id == 1
    assert snapshot.forecast_horizon_days == 7
    assert len(snapshot.daily_forecasts) == 7

    # Verify mathematical aggregation: total = sum(daily), avg = total / days, peak = max(daily)
    expected_total = sum(f.predicted_demand for f in snapshot.daily_forecasts)
    expected_avg = expected_total / 7.0
    expected_peak = max(f.predicted_demand for f in snapshot.daily_forecasts)

    assert snapshot.total_forecast_demand == pytest.approx(expected_total, rel=1e-3)
    assert snapshot.average_daily_demand == pytest.approx(expected_avg, rel=1e-3)
    assert snapshot.peak_daily_demand == pytest.approx(expected_peak, rel=1e-3)
    assert snapshot.validation_status == "PASS"


def test_snapshot_service_missing_inventory_handling(db_session):
    # Branch 2 has no warehouse
    snapshot = InventoryForecastSnapshotService.get_snapshot(db_session, product_id=1, branch_id=2, horizon_days=7)
    assert snapshot.current_stock is None
    assert snapshot.available_stock is None
    assert snapshot.validation_status == "WARNING"


# ---------------------------------------------------------------------------
# 4. Integration Validator Tests
# ---------------------------------------------------------------------------

def test_validator_detects_missing_inventory():
    snapshot = InventoryForecastSnapshot(
        product_id=1,
        product_code="PRD-1",
        product_name="Product 1",
        branch_id=2,
        branch_name="Branch 2",
        current_stock=None,
        reserved_stock=None,
        available_stock=None,
        forecast_horizon_days=7,
        total_forecast_demand=10.0,
        average_daily_demand=1.43,
        peak_daily_demand=2.0,
        daily_forecasts=[],
        forecast_model_name="lightgbm",
        forecast_model_version="v1",
        snapshot_timestamp=datetime.now(timezone.utc),
    )
    results = IntegrationValidator.validate_snapshot(snapshot)
    check_names = {r.validation_name: r.status for r in results}
    assert check_names["inventory_record_existence"] == "WARNING"
    assert check_names["forecast_availability"] == "WARNING"


def test_validator_detects_negative_stock():
    snapshot = InventoryForecastSnapshot(
        product_id=1,
        product_code="PRD-1",
        product_name="Product 1",
        branch_id=1,
        branch_name="Branch 1",
        current_stock=-5,
        reserved_stock=0,
        available_stock=-5,
        forecast_horizon_days=7,
        total_forecast_demand=10.0,
        average_daily_demand=1.43,
        peak_daily_demand=2.0,
        daily_forecasts=[],
        forecast_model_name="lightgbm",
        forecast_model_version="v1",
        snapshot_timestamp=datetime.now(timezone.utc),
    )
    results = IntegrationValidator.validate_snapshot(snapshot)
    check_names = {r.validation_name: r.status for r in results}
    assert check_names["physical_stock_non_negative"] == "FAIL"


def test_validator_system_wide_report(db_session):
    report = IntegrationValidator.run_system_wide_validation(db_session, sample_limit=5)
    assert report.total_validations > 0
    assert report.overall_status in ["PASS", "WARNING", "FAIL"]
    assert len(report.results) == report.total_validations


# ---------------------------------------------------------------------------
# 5. API Endpoints Tests
# ---------------------------------------------------------------------------

def test_api_get_forecast_summary(client):
    response = client.get("/api/v1/inventory/forecast-summary?page=1&size=5")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) <= 5
    if data["items"]:
        item = data["items"][0]
        assert "product_id" in item
        assert "branch_id" in item
        assert "current_stock" in item


def test_api_get_product_branch_forecast_success(client):
    response = client.get("/api/v1/inventory/1/1/forecast?horizon_days=7")
    assert response.status_code == 200
    data = response.json()
    assert data["product_id"] == 1
    assert data["branch_id"] == 1
    assert data["horizon_days"] == 7
    assert data["status"] == "AVAILABLE"
    assert len(data["daily_forecasts"]) == 7


def test_api_get_product_branch_forecast_invalid_horizon(client):
    response = client.get("/api/v1/inventory/1/1/forecast?horizon_days=25")
    assert response.status_code == 400
    assert "Invalid forecast horizon" in response.json()["detail"]


def test_api_get_product_branch_forecast_not_found(client):
    response = client.get("/api/v1/inventory/999999/1/forecast?horizon_days=7")
    assert response.status_code == 404
    assert "Product with ID 999999 not found" in response.json()["detail"]


def test_api_get_product_branch_snapshot_success(client):
    response = client.get("/api/v1/inventory/1/1/snapshot?horizon_days=7")
    assert response.status_code == 200
    data = response.json()
    assert data["product_id"] == 1
    assert data["branch_id"] == 1
    assert data["forecast_horizon_days"] == 7
    assert data["total_forecast_demand"] > 0
    assert data["average_daily_demand"] > 0
    assert data["peak_daily_demand"] >= data["average_daily_demand"]
    assert data["forecast_model_name"] == "lightgbm"
    assert data["validation_status"] == "PASS"


def test_api_validate_integration(client):
    response = client.post("/api/v1/inventory/validate-integration?sample_limit=5")
    assert response.status_code == 200
    data = response.json()
    assert "total_validations" in data
    assert "overall_status" in data
    assert "results" in data
    assert data["total_validations"] > 0
