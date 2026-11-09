"""
Phase 3.3 Automated Tests: Intelligent Inventory Optimization, Stockout Risk & Replenishment Decision Engine.
Tests all analytical algorithms, services, simulation engine, and REST API endpoints.
"""

import math
from datetime import datetime, timezone
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas.inventory_optimization import (
    EOQResult,
    InventoryDecisionResult,
    LeadTimeDemandResult,
    OptimizationSummaryResponse,
    PolicySimulationComparison,
    ReorderPointResult,
    ReplenishmentRecommendation,
    RiskCategoryEnum,
    SafetyStockResult,
    SimulationMetrics,
    StockoutRiskResult,
)
from backend.app.services.decision_engine import UnifiedInventoryDecisionEngine
from backend.app.services.eoq_service import EOQService
from backend.app.services.replenishment_service import ReplenishmentService
from backend.app.services.safety_stock_service import SafetyStockService
from backend.app.services.simulation_service import InventorySimulationService
from backend.app.services.stockout_risk_service import StockoutRiskService


@pytest.fixture
def client():
    return TestClient(app)


# ===========================================================================
# 1. Module A: Safety Stock & Dynamic Reorder Point Tests
# ===========================================================================

def test_lead_time_demand_calculation(db_session):
    """Test cumulative lead-time demand calculation over supplier lead time."""
    ltd = SafetyStockService.calculate_lead_time_demand(
        db=db_session, product_id=1, branch_id=1, lead_time_days=5
    )
    assert isinstance(ltd, LeadTimeDemandResult)
    assert ltd.lead_time_days == 5
    assert ltd.expected_lead_time_demand >= 0.0
    assert len(ltd.daily_lead_time_forecast) == 5
    assert ltd.status == "AVAILABLE"
    assert round(sum(ltd.daily_lead_time_forecast), 4) == ltd.expected_lead_time_demand


def test_lead_time_demand_invalid_horizon(db_session):
    """Lead time > 30 days should raise ValueError."""
    with pytest.raises(ValueError, match="exceeds maximum supported forecasting horizon"):
        SafetyStockService.calculate_lead_time_demand(
            db=db_session, product_id=1, branch_id=1, lead_time_days=45
        )


def test_safety_stock_empirical_and_fallback(db_session):
    """Test empirical quantile safety stock calculation."""
    ss_95 = SafetyStockService.calculate_safety_stock(
        db=db_session, product_id=1, branch_id=1, lead_time_days=5, service_level=0.95
    )
    assert isinstance(ss_95, SafetyStockResult)
    assert ss_95.service_level == 0.95
    assert ss_95.safety_stock >= 0.0
    assert ss_95.safety_stock_rounded >= 0
    assert ss_95.method in ["EMPIRICAL_QUANTILE", "NORMAL_APPROXIMATION"]


def test_safety_stock_service_level_scaling(db_session):
    """Higher service level must yield higher or equal safety stock buffer."""
    ss_90 = SafetyStockService.calculate_safety_stock(
        db=db_session, product_id=1, branch_id=1, lead_time_days=5, service_level=0.90
    )
    ss_95 = SafetyStockService.calculate_safety_stock(
        db=db_session, product_id=1, branch_id=1, lead_time_days=5, service_level=0.95
    )
    ss_99 = SafetyStockService.calculate_safety_stock(
        db=db_session, product_id=1, branch_id=1, lead_time_days=5, service_level=0.99
    )
    assert ss_90.safety_stock <= ss_95.safety_stock <= ss_99.safety_stock


def test_reorder_point_calculation(db_session):
    """Test dynamic reorder point formula ROP = d_L + SS and status categorizations."""
    rop_res = SafetyStockService.calculate_reorder_point(
        db=db_session, product_id=1, branch_id=1, service_level=0.95, lead_time_days=5
    )
    assert isinstance(rop_res, ReorderPointResult)
    assert rop_res.reorder_point == round(
        rop_res.expected_lead_time_demand + rop_res.safety_stock, 4
    )
    assert rop_res.reorder_point_rounded == int(math.ceil(rop_res.reorder_point))
    assert rop_res.reorder_status in ["HEALTHY", "REORDER_NOW", "URGENT_REORDER", "INSUFFICIENT_DATA"]


# ===========================================================================
# 2. Module B: Stockout Risk Analysis Tests
# ===========================================================================

def test_stockout_risk_monte_carlo(db_session):
    """Test Monte Carlo simulation reproducible risk estimation."""
    risk1 = StockoutRiskService.estimate_stockout_risk(
        db=db_session, product_id=1, branch_id=1, lead_time_days=5, simulation_scenarios=200, random_seed=42
    )
    assert isinstance(risk1, StockoutRiskResult)
    assert 0.0 <= risk1.stockout_probability <= 1.0
    assert risk1.risk_category in [RiskCategoryEnum.LOW, RiskCategoryEnum.MEDIUM, RiskCategoryEnum.HIGH, RiskCategoryEnum.CRITICAL]
    assert risk1.scenarios_evaluated == 200

    # Test seed reproducibility
    risk2 = StockoutRiskService.estimate_stockout_risk(
        db=db_session, product_id=1, branch_id=1, lead_time_days=5, simulation_scenarios=200, random_seed=42
    )
    assert risk1.stockout_probability == risk2.stockout_probability
    assert risk1.risk_category == risk2.risk_category


# ===========================================================================
# 3. Module C: EOQ & Replenishment Tests
# ===========================================================================

def test_eoq_calculation_with_supplier_constraints(db_session):
    """Test EOQ calculation enforcing supplier MOQ and packaging multiples."""
    eoq = EOQService.calculate_eoq(
        db=db_session, product_id=1, branch_id=1, ordering_cost=50.0, holding_cost_rate=0.20
    )
    assert isinstance(eoq, EOQResult)
    assert eoq.calculated_eoq >= 0.0
    assert eoq.adjusted_order_quantity >= (eoq.minimum_order_quantity or 1)
    if eoq.order_multiple and eoq.order_multiple > 1:
        assert eoq.adjusted_order_quantity % eoq.order_multiple == 0
    assert eoq.holding_cost_unit >= 0.0


def test_eoq_invalid_parameters(db_session):
    """Negative ordering cost or invalid holding rate should raise ValueError."""
    with pytest.raises(ValueError, match="Ordering cost must be non-negative"):
        EOQService.calculate_eoq(db_session, 1, 1, ordering_cost=-10.0)

    with pytest.raises(ValueError, match="Holding cost rate must be in"):
        EOQService.calculate_eoq(db_session, 1, 1, holding_cost_rate=1.5)


def test_replenishment_recommendation(db_session):
    """Test synthesis of inventory position, ROP, risk, and constrained EOQ into actionable advice."""
    rec = ReplenishmentService.generate_recommendation(
        db=db_session, product_id=1, branch_id=1, service_level=0.95
    )
    assert isinstance(rec, ReplenishmentRecommendation)
    assert rec.decision in ["NO_ACTION", "REORDER", "URGENT_REORDER"]
    assert rec.urgency_level in ["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
    assert len(rec.explanation) > 0


# ===========================================================================
# 4. Module D: Discrete Inventory Policy Simulation Tests
# ===========================================================================

def test_discrete_simulation_internal_balance():
    """Verify inventory balance equation and delivery arrival in discrete simulation."""
    demands = [10.0, 10.0, 10.0, 10.0, 10.0]
    metrics, trajectory = InventorySimulationService._run_discrete_simulation(
        demand_sequence=demands,
        initial_stock=25,
        lead_time=2,
        reorder_point=15,
        order_quantity=30,
        ordering_cost=20.0,
        holding_cost_daily=0.05,
        stockout_cost_unit=5.0,
    )
    assert isinstance(metrics, SimulationMetrics)
    assert len(trajectory) == 5
    assert metrics.fill_rate_pct > 0.0
    assert metrics.total_modeled_cost == round(
        metrics.total_ordering_cost + metrics.total_holding_cost + metrics.total_stockout_cost, 2
    )


def test_policy_simulation_comparison(db_session):
    """Test side-by-side historical simulation of Baseline vs Optimized policy over December 2013."""
    comp = InventorySimulationService.simulate_product_branch(
        db=db_session,
        product_id=1,
        branch_id=1,
        start_date="2013-12-01",
        end_date="2013-12-31",
    )
    assert isinstance(comp, PolicySimulationComparison)
    assert comp.simulation_days > 0
    assert comp.baseline_policy.fill_rate_pct <= 100.0
    assert comp.optimized_policy.fill_rate_pct <= 100.0
    assert len(comp.daily_trajectory) == comp.simulation_days


# ===========================================================================
# 5. Module E: Unified Decision Engine Tests
# ===========================================================================

def test_unified_decision_engine_evaluation(db_session):
    """Test unified decision engine returning complete decision object."""
    engine = UnifiedInventoryDecisionEngine()
    result = engine.evaluate_product_branch(db_session, product_id=1, branch_id=1)
    assert isinstance(result, InventoryDecisionResult)
    assert result.product_id == 1
    assert result.branch_id == 1
    assert result.reorder_point.reorder_point >= result.safety_stock.safety_stock
    assert result.stockout_risk.risk_category in [RiskCategoryEnum.LOW, RiskCategoryEnum.MEDIUM, RiskCategoryEnum.HIGH, RiskCategoryEnum.CRITICAL]
    assert result.recommendation.decision in ["NO_ACTION", "REORDER", "URGENT_REORDER"]


def test_unified_decision_engine_network_summary(db_session):
    """Test network-wide inventory optimization summary."""
    engine = UnifiedInventoryDecisionEngine()
    summary = engine.get_optimization_summary(db_session, page=1, size=5)
    assert isinstance(summary, OptimizationSummaryResponse)
    assert summary.total > 0
    assert len(summary.items) > 0
    assert summary.total_reorder_required >= 0
    assert summary.critical_risk_count >= 0


# ===========================================================================
# 6. REST API Endpoints Tests
# ===========================================================================

def test_api_safety_stock(client):
    res = client.get("/api/v1/inventory/1/1/safety-stock?service_level=0.95")
    assert res.status_code == 200
    data = res.json()
    assert data["service_level"] == 0.95
    assert data["safety_stock"] >= 0.0


def test_api_reorder_point(client):
    res = client.get("/api/v1/inventory/1/1/reorder-point")
    assert res.status_code == 200
    data = res.json()
    assert "reorder_point" in data
    assert "reorder_status" in data


def test_api_stockout_risk(client):
    res = client.get("/api/v1/inventory/1/1/stockout-risk")
    assert res.status_code == 200
    data = res.json()
    assert 0.0 <= data["stockout_probability"] <= 1.0
    assert "risk_category" in data


def test_api_eoq(client):
    res = client.get("/api/v1/inventory/1/1/eoq")
    assert res.status_code == 200
    data = res.json()
    assert "calculated_eoq" in data
    assert "adjusted_order_quantity" in data


def test_api_replenishment(client):
    res = client.get("/api/v1/inventory/1/1/replenishment")
    assert res.status_code == 200
    data = res.json()
    assert data["decision"] in ["NO_ACTION", "REORDER", "URGENT_REORDER"]


def test_api_decision(client):
    res = client.get("/api/v1/inventory/1/1/decision")
    assert res.status_code == 200
    data = res.json()
    assert data["product_id"] == 1
    assert data["branch_id"] == 1
    assert data["recommendation"]["decision"] in ["NO_ACTION", "REORDER", "URGENT_REORDER"]


def test_api_optimization_summary(client):
    res = client.get("/api/v1/inventory/optimization-summary?page=1&size=5")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] > 0
    assert len(data["items"]) > 0
    assert "total_reorder_required" in data


def test_api_simulations_get(client):
    res = client.get("/api/v1/inventory/1/1/simulation?start_date=2013-12-01&end_date=2013-12-31")
    assert res.status_code == 200
    data = res.json()
    assert "baseline_policy" in data
    assert "optimized_policy" in data
    assert "fill_rate_improvement_pct" in data


def test_api_simulations_post(client):
    payload = {
        "product_id": 1,
        "branch_id": 1,
        "start_date": "2013-12-01",
        "end_date": "2013-12-31",
        "service_level": 0.95,
        "ordering_cost": 50.0,
        "holding_cost_rate": 0.20,
    }
    res = client.post("/api/v1/inventory/simulations", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "baseline_policy" in data
    assert "optimized_policy" in data
    assert "fill_rate_improvement_pct" in data
