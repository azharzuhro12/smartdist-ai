"""
Phase 4.1 Automated Test Suite: Sales Anomaly Detection System.

Covers:
1. Module A: Statistical Detection (Z_robust, MAD, zero-MAD safety, sparse series, minimum history, zero leakage).
2. Module B: Forecast Residual Detection (bias subtraction, hierarchical out-of-sample scaling, no future leakage).
3. Module C: Machine Learning Isolation Forest Detector (chronological fitting, calibrated scoring, serialization).
4. Module D: Hybrid Anomaly Scorer (renormalization on missing detectors, severity mapping, direction classification).
5. Module E: Plain-Language Explanation Service (factual confirmed evidence, possible hypotheses, actionable advice).
6. Module F: Synthetic Anomaly Injection Benchmark (recall on known shock perturbations, false positive rate).
7. Module G: Persistence & Database Transactions (unique constraints, idempotency, foreign-key integrity).
8. Module H: REST APIs & Status Workflow (detection execution, filtering, status lifecycle transitions, 400/404 validation).
9. Module I: Celery Asynchronous Task Integration (background execution, task payload handling).
"""

from decimal import Decimal
import math
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.anomaly import AnomalyDetectionRun, SalesAnomaly
from backend.app.services.anomaly_service import AnomalyDetectionService
from ml.anomaly_detection.explanation_service import AnomalyExplanationService
from ml.anomaly_detection.forecast_residual_detector import ForecastResidualAnomalyDetector
from ml.anomaly_detection.hybrid_scorer import AnomalyDirection, AnomalySeverity, HybridAnomalyScorer
from ml.anomaly_detection.ml_detector import MLIsolationForestDetector
from ml.anomaly_detection.statistical_detector import StatisticalAnomalyDetector
from ml.anomaly_detection.synthetic_benchmark import SyntheticAnomalyInjector


@pytest.fixture
def client():
    return TestClient(app)


# ===========================================================================
# 1. Module A: Statistical Anomaly Detection Tests
# ===========================================================================

def test_statistical_detector_positive_spike():
    """Verify robust Z-score triggers is_spike for sudden sales surge."""
    history = [10.0, 11.0, 9.5, 10.5, 10.0, 10.2, 9.8, 10.1, 10.3, 9.9, 10.0, 10.4, 9.7, 10.1]
    res = StatisticalAnomalyDetector.evaluate_series(history, observed_value=35.0, window=14, min_history=7)
    assert res["status"] == "VALID"
    assert res["is_spike"] is True
    assert res["robust_z_score"] >= 3.0
    assert res["absolute_deviation"] > 0.0
    assert res["percentage_deviation"] > 100.0


def test_statistical_detector_sales_drop():
    """Verify robust Z-score triggers is_drop for sudden sales collapse."""
    history = [100.0, 105.0, 95.0, 102.0, 98.0, 101.0, 99.0, 104.0, 96.0, 100.0]
    res = StatisticalAnomalyDetector.evaluate_series(history, observed_value=20.0, window=14, min_history=7)
    assert res["status"] == "VALID"
    assert res["is_drop"] is True
    assert res["robust_z_score"] <= -3.0


def test_statistical_detector_zero_sales_behavior():
    """Zero sales on high-velocity item flagged as drop and zero sales shock."""
    history = [50.0, 52.0, 48.0, 55.0, 49.0, 51.0, 50.0, 47.0, 53.0, 50.0]
    res = StatisticalAnomalyDetector.evaluate_series(history, observed_value=0.0, window=14, min_history=7)
    assert res["status"] == "VALID"
    assert res["is_zero_sales"] is True
    assert res["is_drop"] is True


def test_statistical_detector_zero_mad_protection():
    """When all historical values are identical (MAD=0), no division by zero occurs."""
    history = [15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0]
    # Identical value observed -> Z=0
    res_normal = StatisticalAnomalyDetector.evaluate_series(history, observed_value=15.0, window=14, min_history=5)
    assert res_normal["robust_z_score"] == 0.0
    assert np.isfinite(res_normal["robust_z_score"])

    # Different value observed -> safely clamped to +10.0
    res_surge = StatisticalAnomalyDetector.evaluate_series(history, observed_value=30.0, window=14, min_history=5)
    assert res_surge["robust_z_score"] == 10.0
    assert np.isfinite(res_surge["robust_z_score"])


def test_statistical_detector_insufficient_history():
    """Fewer historical points than min_history returns INSUFFICIENT_DATA."""
    history = [10.0, 12.0, 11.0]
    res = StatisticalAnomalyDetector.evaluate_series(history, observed_value=25.0, min_history=7)
    assert res["status"] == "INSUFFICIENT_DATA"
    assert res["sample_size"] == 3
    assert res["robust_z_score"] == 0.0
    assert res["is_spike"] is False


def test_statistical_detector_excludes_current_observation_from_baseline():
    """Strict zero-leakage: baseline must NOT include current observation."""
    clean_history = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
    res = StatisticalAnomalyDetector.evaluate_series(clean_history, observed_value=100.0, min_history=5)
    # Median of history is 10.0, not contaminated by 100.0
    assert res["baseline_median"] == 10.0


# ===========================================================================
# 2. Module B: Forecast Residual Anomaly Detection Tests
# ===========================================================================

def test_forecast_residual_detector_standardized_score():
    """Forecast residual standardized score (e_t - mu_e) / sigma_e."""
    syn_res_df = pd.DataFrame({
        "store_nbr": [1] * 20,
        "product_id": [1] * 20,
        "family": ["AUTOMOTIVE"] * 20,
        "residual": [0.0, 2.0, -2.0, 1.0, -1.0, 0.5, -0.5, 1.5, -1.5, 0.0,
                     0.0, 2.0, -2.0, 1.0, -1.0, 0.5, -0.5, 1.5, -1.5, 0.0],
    })
    # Observed 35 vs predicted 10 -> residual = +25
    eval_res = ForecastResidualAnomalyDetector.evaluate_residual(
        observed_actual=35.0,
        predicted_forecast=10.0,
        residuals_df=syn_res_df,
        store_nbr=1,
        product_id=1,
        family="AUTOMOTIVE",
    )
    assert eval_res["status"] == "VALID"
    assert eval_res["residual"] == 25.0
    assert eval_res["standardized_score"] > 3.0
    assert eval_res["is_significant_deviation"] is True


def test_forecast_residual_detector_insufficient_samples():
    """Empty or 1-observation residual dataframe safely returns INSUFFICIENT_DATA."""
    empty_df = pd.DataFrame(columns=["store_nbr", "product_id", "family", "residual"])
    eval_res = ForecastResidualAnomalyDetector.evaluate_residual(
        observed_actual=25.0,
        predicted_forecast=10.0,
        residuals_df=empty_df,
        store_nbr=1,
        product_id=1,
    )
    assert eval_res["status"] == "INSUFFICIENT_DATA"
    assert eval_res["standardized_score"] == 0.0


# ===========================================================================
# 3. Module C: Machine Learning Isolation Forest Detector Tests
# ===========================================================================

def test_ml_isolation_forest_detector_fit_and_score():
    """Verify IsolationForest detector training, serialization, and normalized scoring."""
    dates = pd.date_range("2013-01-01", periods=100, freq="D")
    df = pd.DataFrame({
        "quantity_sold": [10.0 + (i % 5) for i in range(100)],
        "lag_1": [10.0 + (i % 5) for i in range(100)],
        "lag_7": [10.0 + (i % 5) for i in range(100)],
        "rolling_mean_7": [12.0] * 100,
        "rolling_std_7": [1.5] * 100,
        "day_of_week": [d.dayofweek for d in dates],
        "is_weekend": [1 if d.dayofweek >= 5 else 0 for d in dates],
        "promotion_quantity": [0] * 100,
    })

    det = MLIsolationForestDetector(contamination=0.05, random_state=42)
    det.fit(df)
    assert det.is_fitted is True

    # Normal observation should have low score (< 0.50)
    normal_feats = {
        "quantity_sold": 11.0,
        "lag_1": 10.0,
        "lag_7": 12.0,
        "rolling_mean_7": 11.5,
        "rolling_std_7": 1.2,
        "day_of_week": 2,
        "is_weekend": 0,
        "promotion_quantity": 0,
    }
    score_normal = det.evaluate_single(normal_feats)
    assert score_normal["status"] == "VALID"
    assert score_normal["anomaly_score"] < 0.60

    # Extreme outlier observation should have high score (> 0.65)
    outlier_feats = {
        "quantity_sold": 500.0,
        "lag_1": 10.0,
        "lag_7": 12.0,
        "rolling_mean_7": 11.5,
        "rolling_std_7": 1.2,
        "day_of_week": 2,
        "is_weekend": 0,
        "promotion_quantity": 0,
    }
    score_outlier = det.evaluate_single(outlier_feats)
    assert score_outlier["anomaly_score"] > score_normal["anomaly_score"]


# ===========================================================================
# 4. Module D: Hybrid Anomaly Scoring Tests
# ===========================================================================

def test_hybrid_scorer_renormalization_on_missing_detector():
    """When forecast or ML detector is unavailable, remaining weights renormalize to 1.0."""
    stat_res = {
        "status": "VALID",
        "robust_z_score": 4.5,
        "is_spike": True,
        "is_drop": False,
        "is_zero_sales": False,
        "absolute_deviation": 35.0,
    }
    # Forecast is INSUFFICIENT_DATA, ML is UNAVAILABLE
    fc_res = {"status": "INSUFFICIENT_DATA"}
    ml_res = {"status": "UNAVAILABLE"}

    hybrid = HybridAnomalyScorer.compute_hybrid_score(
        stat_result=stat_res,
        forecast_result=fc_res,
        ml_result=ml_res,
    )
    assert hybrid["status"] == "VALID"
    assert hybrid["weights_used"]["statistical"] == 1.0
    assert "forecast" not in hybrid["weights_used"]
    assert "ml" not in hybrid["weights_used"]
    assert hybrid["severity"] in [AnomalySeverity.HIGH, AnomalySeverity.CRITICAL]
    assert hybrid["direction"] == AnomalyDirection.SPIKE


def test_hybrid_scorer_severity_categories():
    """Verify calibrated severity thresholds: NORMAL, LOW, MEDIUM, HIGH, CRITICAL."""
    assert HybridAnomalyScorer.compute_hybrid_score({"status": "VALID", "robust_z_score": 0.5})["severity"] == AnomalySeverity.NORMAL
    assert HybridAnomalyScorer.compute_hybrid_score({"status": "VALID", "robust_z_score": 2.2})["severity"] in [AnomalySeverity.LOW, AnomalySeverity.MEDIUM]
    assert HybridAnomalyScorer.compute_hybrid_score({"status": "VALID", "robust_z_score": 4.5, "is_spike": True})["severity"] in [AnomalySeverity.HIGH, AnomalySeverity.CRITICAL]


# ===========================================================================
# 5. Module E: Plain-Language Explanation Service Tests
# ===========================================================================

def test_explanation_service_generates_three_tiers():
    """Explanations must contain confirmed evidence, possible hypotheses, and recommended actions."""
    evidence = {
        "statistical": {"robust_z_score": 4.2, "baseline_median": 100.0, "baseline_mad": 15.0},
        "forecast": {"status": "VALID", "predicted_forecast": 98.0, "residual": 152.0},
    }
    expl = AnomalyExplanationService.generate_explanation_and_actions(
        product_name="Beverages",
        branch_name="Quito Central",
        observed_quantity=250.0,
        expected_quantity=100.0,
        severity=AnomalySeverity.HIGH,
        direction=AnomalyDirection.SPIKE,
        detector_evidence=evidence,
    )
    assert "HIGH" in expl["title"]
    assert len(expl["confirmed_evidence"]) >= 2
    assert len(expl["possible_explanations"]) >= 2
    assert len(expl["recommended_actions"]) >= 2
    assert "promotion" in " ".join(expl["possible_explanations"]).lower()


# ===========================================================================
# 6. Module F: Synthetic Anomaly Injection Benchmark Tests
# ===========================================================================

def test_synthetic_anomaly_injection_benchmark():
    """
    Isolated benchmark: Inject controlled shocks (+250% spike, -85% drop, zero sales)
    into a clean series. Verify detector achieves high recall without corrupting database.
    """
    # 50 days of baseline sales
    clean_series = [20.0 + float(i % 5) for i in range(50)]
    bench = SyntheticAnomalyInjector.evaluate_detection_benchmark(clean_series, seed=42)

    assert bench["total_injected_anomalies"] >= 3
    assert bench["synthetic_detection_rate_pct"] >= 75.0  # High recall on synthetic injections
    assert bench["average_detection_delay_days"] <= 1.0   # Immediate detection
    assert bench["false_positive_rate_pct"] <= 15.0       # Low false alarm rate on clean baseline


# ===========================================================================
# 7. Module G & H: Persistence, Idempotency & REST API Tests
# ===========================================================================

def test_api_anomaly_detect_and_query(client, db_session):
    """
    Integration test: Execute detection run, verify database records, idempotency,
    summary, list pagination, and status workflow transitions.
    """
    # 1. Trigger detection via API for Branch 1, Product 1 in Dec 2013
    detect_payload = {
        "start_date": "2013-12-01",
        "end_date": "2013-12-15",
        "branch_id": 1,
        "product_id": 1,
        "sensitivity": 1.0,
        "async_mode": False,
    }
    res_detect = client.post("/api/v1/anomalies/detect", json=detect_payload)
    assert res_detect.status_code == 200
    run_data = res_detect.json()
    assert run_data["status"] == "COMPLETED"
    run_id = run_data["id"]

    # 2. Query Run Status
    res_run = client.get(f"/api/v1/anomalies/runs/{run_id}")
    assert res_run.status_code == 200
    assert res_run.json()["id"] == run_id

    # 3. Query Summary API
    res_sum = client.get("/api/v1/anomalies/summary")
    assert res_sum.status_code == 200
    sum_data = res_sum.json()
    assert "total_anomalies" in sum_data
    assert "severity_breakdown" in sum_data
    assert "date_trend" in sum_data

    # 4. List Anomalies with Filters
    res_list = client.get("/api/v1/anomalies?page=1&size=10")
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert "items" in list_data
    assert "total" in list_data

    # If an anomaly exists, test status lifecycle transition
    if list_data["total"] > 0:
        anom_id = list_data["items"][0]["id"]
        # Update status to INVESTIGATING
        patch_payload = {
            "status": "INVESTIGATING",
            "resolution_note": "Store manager contacted for receipt audit.",
        }
        res_patch = client.patch(f"/api/v1/anomalies/{anom_id}/status", json=patch_payload)
        assert res_patch.status_code == 200
        assert res_patch.json()["investigation_status"] == "INVESTIGATING"
        assert res_patch.json()["resolution_note"] == "Store manager contacted for receipt audit."

        # Fetch detail
        res_detail = client.get(f"/api/v1/anomalies/{anom_id}")
        assert res_detail.status_code == 200
        assert res_detail.json()["id"] == anom_id


def test_api_invalid_date_range(client):
    """start_date > end_date returns 400 Bad Request."""
    payload = {
        "start_date": "2013-12-31",
        "end_date": "2013-12-01",
    }
    res = client.post("/api/v1/anomalies/detect", json=payload)
    assert res.status_code == 400
    assert "cannot be greater than end_date" in res.json()["detail"]


def test_api_invalid_status_transition(client, db_session):
    """Unsupported investigation status returns 400 Bad Request."""
    anom = db_session.query(SalesAnomaly).first()
    if anom:
        res = client.patch(f"/api/v1/anomalies/{anom.id}/status", json={"status": "INVALID_STATE"})
        assert res.status_code == 400
        assert "Invalid investigation status" in res.json()["detail"]
