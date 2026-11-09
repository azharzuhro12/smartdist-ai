"""
SmartDist AI — Phase 3.3.1 Final Validation & Backtesting Correction Test Suite.

Covers:
1. Audit A: Parametric Safety Stock & Bias Treatment (10 scenarios + exact hand-calculated assertions).
2. Audit B: Inventory Backtesting Cost Accounting & Live Reconciliation.
3. Audit C: Strict Lookahead-Bias & Temporal Isolation Verification (4 mandatory mutation/timing tests).
"""

import math
import numpy as np
import pandas as pd
import pytest

from backend.app.models.business import DailySale
from backend.app.services.eoq_service import EOQService
from backend.app.services.safety_stock_service import SafetyStockService
from backend.app.services.simulation_service import InventorySimulationService
from ml.features.feature_pipeline import TimeSeriesFeaturePipeline
from ml.inference.predictor import ForecastingPredictor
from ml.training.model_registry import ModelRegistry


# ===========================================================================
# AUDIT A: Parametric Safety Stock & Bias Treatment (10 Scenarios)
# ===========================================================================


def _make_residual_df(residuals, store_nbr=1, product_id=1, family="AUTOMOTIVE"):
    """Helper to construct a synthetic validation residual DataFrame."""
    dates = [f"2013-11-{i + 1:02d}" for i in range(len(residuals))]
    return pd.DataFrame(
        {
            "date": dates,
            "store_nbr": [store_nbr] * len(residuals),
            "product_id": [product_id] * len(residuals),
            "family": [family] * len(residuals),
            "residual": residuals,
            "quantity_sold": [10.0] * len(residuals),
        }
    )


def test_audit_a1_zero_bias_independent_errors(db_session, monkeypatch):
    """
    Scenario 1: Zero bias (mu_e = 0) and zero autocorrelation (rho = 0).
    Verify parametric fallback produces SS = Z_alpha * sigma_e * sqrt(L).
    Construct an alternating 4-point series [+2, -2, -2, +2] which has:
      mean_bias = 0.0, sample std (ddof=1) = sqrt(16/3), lag-1 autocorr <= 0 (clamped to VIF=1.0).
    """
    res_vals = [2.0, -2.0, -2.0, 2.0, 2.0, -2.0, -2.0, 2.0]
    df = _make_residual_df(res_vals)
    monkeypatch.setattr(SafetyStockService, "_load_out_of_sample_residuals", classmethod(lambda cls: df))

    ss_res = SafetyStockService.calculate_safety_stock(
        db=db_session, product_id=1, branch_id=1, lead_time_days=5, service_level=0.95
    )

    expected_sigma = float(np.std(res_vals, ddof=1))
    expected_z = 1.6449
    expected_ss = expected_z * expected_sigma * math.sqrt(5.0)

    assert ss_res.method == "NORMAL_APPROXIMATION"
    assert ss_res.fallback_level == "PARAMETRIC"
    assert pytest.approx(ss_res.mean_bias, abs=1e-6) == 0.0
    assert pytest.approx(ss_res.forecast_error_std, abs=1e-4) == round(expected_sigma, 4)
    assert pytest.approx(ss_res.safety_stock, abs=1e-4) == round(expected_ss, 4)


def test_audit_a2_positive_residual_bias_underforecasting(db_session, monkeypatch):
    """
    Scenario 2: Positive residual bias (mu_e > 0, systematic under-forecasting).
    Adding constant positive bias +3.0/day to residuals must increase parametric safety stock
    by exactly L * mu_e = 5 * 3.0 = 15.0 units while leaving sigma_e unchanged.
    """
    base_vals = [2.0, -2.0, -2.0, 2.0, 2.0, -2.0, -2.0, 2.0]
    pos_bias_vals = [v + 3.0 for v in base_vals]

    monkeypatch.setattr(
        SafetyStockService,
        "_load_out_of_sample_residuals",
        classmethod(lambda cls: _make_residual_df(base_vals)),
    )
    ss_zero = SafetyStockService.calculate_safety_stock(
        db=db_session, product_id=1, branch_id=1, lead_time_days=5, service_level=0.95
    )

    monkeypatch.setattr(
        SafetyStockService,
        "_load_out_of_sample_residuals",
        classmethod(lambda cls: _make_residual_df(pos_bias_vals)),
    )
    ss_pos = SafetyStockService.calculate_safety_stock(
        db=db_session, product_id=1, branch_id=1, lead_time_days=5, service_level=0.95
    )

    assert ss_pos.method == "NORMAL_APPROXIMATION"
    assert pytest.approx(ss_pos.mean_bias, abs=1e-4) == 3.0
    assert pytest.approx(ss_pos.forecast_error_std, abs=1e-4) == ss_zero.forecast_error_std
    assert pytest.approx(ss_pos.safety_stock - ss_zero.safety_stock, abs=1e-3) == 5.0 * 3.0


def test_audit_a3_negative_residual_bias_overforecasting(db_session, monkeypatch):
    """
    Scenario 3: Negative residual bias (mu_e < 0, systematic over-forecasting).
    Negative bias reduces parametric quantile by L * |mu_e| and clamps safety stock at 0.0
    when L * mu_e + Z_alpha * sqrt(Var(E_L)) < 0.
    """
    base_vals = [2.0, -2.0, -2.0, 2.0, 2.0, -2.0, -2.0, 2.0]
    mild_neg_vals = [v - 1.0 for v in base_vals]
    strong_neg_vals = [v - 10.0 for v in base_vals]

    monkeypatch.setattr(
        SafetyStockService,
        "_load_out_of_sample_residuals",
        classmethod(lambda cls: _make_residual_df(base_vals)),
    )
    ss_zero = SafetyStockService.calculate_safety_stock(
        db=db_session, product_id=1, branch_id=1, lead_time_days=5, service_level=0.95
    )

    monkeypatch.setattr(
        SafetyStockService,
        "_load_out_of_sample_residuals",
        classmethod(lambda cls: _make_residual_df(mild_neg_vals)),
    )
    ss_mild_neg = SafetyStockService.calculate_safety_stock(
        db=db_session, product_id=1, branch_id=1, lead_time_days=5, service_level=0.95
    )

    monkeypatch.setattr(
        SafetyStockService,
        "_load_out_of_sample_residuals",
        classmethod(lambda cls: _make_residual_df(strong_neg_vals)),
    )
    ss_strong_neg = SafetyStockService.calculate_safety_stock(
        db=db_session, product_id=1, branch_id=1, lead_time_days=5, service_level=0.95
    )

    # Mild negative bias (-1.0/day over 5 days = -5.0) reduces SS by 5.0
    assert pytest.approx(ss_zero.safety_stock - ss_mild_neg.safety_stock, abs=1e-3) == 5.0
    # Strong negative bias (-10.0/day over 5 days = -50.0) clamps SS at 0.0
    assert ss_strong_neg.safety_stock == 0.0
    assert ss_strong_neg.safety_stock_rounded == 0
    assert ss_strong_neg.lead_time_error_quantile < 0.0


def test_audit_a4_positive_autocorrelation_exact_formula():
    """
    Scenario 4 & Hand-Calculated Verification:
    Verify exact AR(1) variance formula over all lags k = 1 .. L-1:
        Var(E_L) = sigma_e^2 * (L + 2 * sum_{k=1}^{L-1} (L - k) * rho^k)
    For L = 7, rho = 0.5:
        sum_{k=1}^6 (7 - k) * (0.5)^k
          = 6*(0.5) + 5*(0.25) + 4*(0.125) + 3*(0.0625) + 2*(0.03125) + 1*(0.015625)
          = 3.0 + 1.25 + 0.5 + 0.1875 + 0.0625 + 0.015625
          = 5.015625
        Var(E_7) / sigma_e^2 = 7 + 2 * 5.015625 = 17.03125
        VIF(7, 0.5) = 17.03125 / 7 = 2.433035714...
    """
    vif = SafetyStockService._calculate_variance_inflation(lead_time_days=7, rho=0.5)
    expected_vif = (7.0 + 2.0 * 5.015625) / 7.0
    assert pytest.approx(vif, abs=1e-9) == expected_vif


def test_audit_a5_negative_autocorrelation_clamped_and_unclamped(db_session, monkeypatch):
    """
    Scenario 5: Negative autocorrelation policy verification.
    - Default operational policy (clamp_negative=True): clamps VIF to 1.0 so noisy negative
      sample autocorrelation never reduces safety stock below the i.i.d. baseline.
    - Analytical mode (clamp_negative=False): computes exact AR(1) VIF < 1.0.
      For L = 3, rho = -0.5:
        L + 2 * ((2)*(-0.5) + (1)*(0.25)) = 3 + 2 * (-1.0 + 0.25) = 3 - 1.5 = 1.5
        VIF = 1.5 / 3 = 0.5.
    """
    assert SafetyStockService._calculate_variance_inflation(lead_time_days=3, rho=-0.5, clamp_negative=True) == 1.0
    assert (
        pytest.approx(
            SafetyStockService._calculate_variance_inflation(lead_time_days=3, rho=-0.5, clamp_negative=False),
            abs=1e-9,
        )
        == 0.5
    )

    # Verify via calculate_safety_stock with alternating negative-autocorrelated residuals
    neg_rho_vals = [3.0, -3.0, 3.0, -3.0, 3.0, -3.0, 3.0, -3.0]
    monkeypatch.setattr(
        SafetyStockService,
        "_load_out_of_sample_residuals",
        classmethod(lambda cls: _make_residual_df(neg_rho_vals)),
    )
    ss_clamped = SafetyStockService.calculate_safety_stock(
        db=db_session, product_id=1, branch_id=1, lead_time_days=5, service_level=0.95, clamp_negative_autocorr=True
    )
    ss_unclamped = SafetyStockService.calculate_safety_stock(
        db=db_session, product_id=1, branch_id=1, lead_time_days=5, service_level=0.95, clamp_negative_autocorr=False
    )
    assert ss_clamped.autocorrelation_lag1 < 0.0
    assert ss_clamped.safety_stock > ss_unclamped.safety_stock


@pytest.mark.parametrize("lead_time", [1, 5, 7, 14, 30])
def test_audit_a6_multi_lead_times_parametric_and_empirical(db_session, monkeypatch, lead_time):
    """
    Scenario 6: Verify lead times L = 1, 5, 7, 14, 30 both on live empirical data
    and under parametric fallback with hand-calculable inputs.
    """
    # 1. Live validation data
    live_res = SafetyStockService.calculate_safety_stock(
        db=db_session, product_id=1, branch_id=1, lead_time_days=lead_time, service_level=0.95
    )
    assert live_res.lead_time_days == lead_time
    assert live_res.safety_stock >= 0.0

    # 2. Controlled parametric fallback (8 daily points -> fewer than 20 windows for L >= 1)
    vals = [1.0, 2.0, 1.5, 2.5, 1.2, 2.8, 1.8, 2.2]
    monkeypatch.setattr(
        SafetyStockService,
        "_load_out_of_sample_residuals",
        classmethod(lambda cls: _make_residual_df(vals)),
    )
    param_res = SafetyStockService.calculate_safety_stock(
        db=db_session, product_id=1, branch_id=1, lead_time_days=lead_time, service_level=0.95
    )
    assert param_res.method == "NORMAL_APPROXIMATION"
    assert param_res.fallback_level == "PARAMETRIC"

    mu_e = float(np.mean(vals))
    sigma_e = float(np.std(vals, ddof=1))
    rho = float(pd.Series(vals).autocorr(lag=1))
    vif = SafetyStockService._calculate_variance_inflation(lead_time, rho)
    expected_q = lead_time * mu_e + 1.6449 * sigma_e * math.sqrt(lead_time * vif)
    assert pytest.approx(param_res.safety_stock, abs=1e-4) == round(max(0.0, expected_q), 4)


def test_audit_a7_empirical_quantile_does_not_double_count_bias(db_session, monkeypatch):
    """
    Scenario 7: Verify that empirical quantile safety stock uses Q_alpha(E_L) directly
    and does NOT add L * mu_e a second time.
    """
    # 25 daily observations with positive mean bias (+5.0)
    vals = [5.0 + float(i % 3) for i in range(25)]
    monkeypatch.setattr(
        SafetyStockService,
        "_load_out_of_sample_residuals",
        classmethod(lambda cls: _make_residual_df(vals)),
    )
    L = 5
    res = SafetyStockService.calculate_safety_stock(
        db=db_session, product_id=1, branch_id=1, lead_time_days=L, service_level=0.95
    )

    rolling_sums = pd.Series(vals).rolling(L).sum().dropna().to_numpy()
    expected_empirical_q = float(np.percentile(rolling_sums, 95.0))
    mu_e = float(np.mean(vals))

    assert res.method == "EMPIRICAL_QUANTILE"
    assert res.fallback_level == "SERIES"
    assert pytest.approx(res.safety_stock, abs=1e-4) == round(expected_empirical_q, 4)
    # Must NOT equal expected_empirical_q + L * mu_e
    assert res.safety_stock != round(expected_empirical_q + L * mu_e, 4)


def test_audit_a8_parametric_hand_calculated_exact_verification(db_session, monkeypatch):
    """
    Scenario 8: Hand-calculated verification of parametric safety stock formula:
      Construct a 10-day series where we know exact sample mean_bias, sigma_e, and lag-1 rho.
      Verify:
        Var(E_L) = sigma_e^2 * (L + 2 * sum_{k=1}^{L-1} (L - k) * rho^k)
        Q_alpha(E_L) = L * mu_e + Z_alpha * sqrt(Var(E_L))
        SS = max(0, Q_alpha(E_L))
    """
    vals = [1.0, 2.0, 3.0, 4.0, 3.0, 2.0, 3.0, 4.0, 5.0, 3.0]
    monkeypatch.setattr(
        SafetyStockService,
        "_load_out_of_sample_residuals",
        classmethod(lambda cls: _make_residual_df(vals)),
    )
    L = 5
    res = SafetyStockService.calculate_safety_stock(
        db=db_session, product_id=1, branch_id=1, lead_time_days=L, service_level=0.95
    )

    mu_e = float(np.mean(vals))  # 3.0
    sigma_e = float(np.std(vals, ddof=1))
    rho = float(pd.Series(vals).autocorr(lag=1))
    autocorr_sum = sum((L - k) * (rho ** k) for k in range(1, L))
    var_e_L = (sigma_e ** 2) * (L + 2.0 * autocorr_sum)
    expected_q = L * mu_e + 1.6449 * math.sqrt(var_e_L)

    assert res.method == "NORMAL_APPROXIMATION"
    assert res.fallback_level == "PARAMETRIC"
    assert pytest.approx(res.mean_bias, abs=1e-4) == round(mu_e, 4)
    assert pytest.approx(res.forecast_error_std, abs=1e-4) == round(sigma_e, 4)
    assert pytest.approx(res.autocorrelation_lag1, abs=1e-4) == round(rho, 4)
    assert pytest.approx(res.safety_stock, abs=1e-4) == round(expected_q, 4)


def test_audit_a9_insufficient_sample_size_returns_insufficient_data(db_session, monkeypatch):
    """
    Scenario 9: Fewer than 2 finite daily residuals returns INSUFFICIENT_DATA,
    never silently falling back to global RMSE.
    """
    single_point_df = _make_residual_df([4.5])
    monkeypatch.setattr(
        SafetyStockService,
        "_load_out_of_sample_residuals",
        classmethod(lambda cls: single_point_df),
    )

    res = SafetyStockService.calculate_safety_stock(
        db=db_session, product_id=1, branch_id=1, lead_time_days=5, service_level=0.95
    )
    assert res.method == "INSUFFICIENT_DATA"
    assert res.fallback_level == "INSUFFICIENT_DATA"
    assert res.safety_stock == 0.0
    assert res.safety_stock_rounded == 0
    assert not hasattr(SafetyStockService, "_cached_global_rmse")


def test_audit_a10_non_finite_nan_inf_residual_handling(db_session, monkeypatch):
    """
    Scenario 10: Non-finite residual values (NaN, +inf, -inf) are stripped cleanly
    without corrupting mean_bias, sigma_e, autocorrelation, or safety stock.
    """
    clean_vals = [1.0, 2.0, 3.0, 2.0, 1.0, 2.0, 3.0, 2.0]
    dirty_vals = [1.0, np.nan, 2.0, np.inf, 3.0, -np.inf, 2.0, 1.0, 2.0, 3.0, 2.0]

    monkeypatch.setattr(
        SafetyStockService,
        "_load_out_of_sample_residuals",
        classmethod(lambda cls: _make_residual_df(clean_vals)),
    )
    res_clean = SafetyStockService.calculate_safety_stock(
        db=db_session, product_id=1, branch_id=1, lead_time_days=5, service_level=0.95
    )

    monkeypatch.setattr(
        SafetyStockService,
        "_load_out_of_sample_residuals",
        classmethod(lambda cls: _make_residual_df(dirty_vals)),
    )
    res_dirty = SafetyStockService.calculate_safety_stock(
        db=db_session, product_id=1, branch_id=1, lead_time_days=5, service_level=0.95
    )

    assert np.isfinite(res_dirty.safety_stock)
    assert res_dirty.safety_stock == res_clean.safety_stock
    assert res_dirty.mean_bias == res_clean.mean_bias
    assert res_dirty.forecast_error_std == res_clean.forecast_error_std


# ===========================================================================
# AUDIT B: Inventory Backtesting Cost Accounting & Reconciliation
# ===========================================================================


def test_audit_b_cost_accounting_and_holding_cost_time_basis():
    """
    Verify exact holding cost, ordering cost, stockout penalty, and total replenishment
    quantity formulas on a deterministic trajectory:
      - Unit cost c = $16.56, annual holding rate h = 0.20 -> H_annual = $3.312/unit/yr
      - H_daily = $3.312 / 365 = $0.0090739726.../unit/day
      - Ordering cost S = $50.00/order
      - Stockout penalty = $8.28/unit (50% of unit cost)
    """
    unit_cost = 16.56
    holding_rate = 0.20
    h_daily = (unit_cost * holding_rate) / 365.0
    s_order = 50.0
    p_stockout = unit_cost * 0.50

    demands = [10.0, 15.0, 20.0, 10.0, 5.0]  # Total demand = 60.0 over T = 5 days
    initial_stock = 30
    lead_time = 2
    rop = 20
    order_qty = 40

    metrics, trajectory = InventorySimulationService._run_discrete_simulation(
        demand_sequence=demands,
        initial_stock=initial_stock,
        lead_time=lead_time,
        reorder_point=rop,
        order_quantity=order_qty,
        ordering_cost=s_order,
        holding_cost_daily=h_daily,
        stockout_cost_unit=p_stockout,
    )

    # Trace day-by-day manually:
    # Day 1: start=30, demand=10 -> end=20. IP=20 <= 20 -> Order #1 (40 units, arrives Day 3).
    # Day 2: start=20, demand=15 -> end=5. IP=5+40=45 > 20 -> No order.
    # Day 3: start=5+40=45, demand=20 -> end=25. IP=25 > 20 -> No order.
    # Day 4: start=25, demand=10 -> end=15. IP=15 <= 20 -> Order #2 (40 units, arrives Day 6).
    # Day 5: start=15, demand=5 -> end=10. IP=10+40=50 > 20 -> No order.
    assert trajectory == [20, 5, 25, 15, 10]
    assert metrics.total_demand == 60.0
    assert metrics.total_fulfilled_demand == 60.0
    assert metrics.unfulfilled_demand_units == 0.0
    assert metrics.fill_rate_pct == 100.0
    assert metrics.total_orders_placed == 2
    assert metrics.total_replenishment_quantity == 80
    assert metrics.average_inventory == 15.0  # sum([20, 5, 25, 15, 10]) / 5 = 75 / 5 = 15.0

    expected_holding = round(75.0 * h_daily, 2)  # 75 * (3.312 / 365) = 0.6805 -> $0.68
    expected_ordering = round(2 * s_order, 2)    # $100.00
    expected_stockout = 0.0
    expected_total = round(expected_holding + expected_ordering + expected_stockout, 2)

    assert metrics.total_holding_cost == expected_holding
    assert metrics.total_ordering_cost == expected_ordering
    assert metrics.total_stockout_cost == expected_stockout
    assert metrics.total_modeled_cost == expected_total


def test_audit_b_live_december_2013_backtest_reconciliation(db_session):
    """
    Independently recalculate and verify all backtest metrics from raw daily trajectory
    outputs for December 2013 across:
      1. Product 1, Branch 1 (default initial_stock=None -> 210 units)
      2. Product 22, Branch 1 (Lingerie, default initial_stock=None -> 206 units)
      3. Product 4, Branch 1 (Beverages, default initial_stock=None -> 222 units)
    """
    for pid, bid in [(1, 1), (22, 1), (4, 1)]:
        comp = InventorySimulationService.simulate_product_branch(
            db=db_session,
            product_id=pid,
            branch_id=bid,
            start_date="2013-12-01",
            end_date="2013-12-31",
            service_level=0.95,
        )
        traj = comp.daily_trajectory
        assert len(traj) == comp.simulation_days == 30  # 30 active trading days in Dec 2013

        total_dem = sum(d["demand"] for d in traj)
        base_stocks = [d["baseline_stock"] for d in traj]
        opt_stocks = [d["optimized_stock"] for d in traj]

        for policy, stocks in [(comp.baseline_policy, base_stocks), (comp.optimized_policy, opt_stocks)]:
            assert pytest.approx(policy.total_demand, abs=1e-2) == round(total_dem, 2)
            assert pytest.approx(
                policy.total_fulfilled_demand + policy.unfulfilled_demand_units, abs=1e-2
            ) == policy.total_demand
            expected_fill = (policy.total_fulfilled_demand / policy.total_demand * 100.0) if policy.total_demand > 0 else 100.0
            assert pytest.approx(policy.fill_rate_pct, abs=1e-2) == round(expected_fill, 2)
            assert pytest.approx(policy.average_inventory, abs=1e-2) == round(float(np.mean(stocks)), 2)
            assert policy.max_inventory == int(max(stocks))
            assert policy.total_modeled_cost == round(
                policy.total_ordering_cost + policy.total_holding_cost + policy.total_stockout_cost, 2
            )


# ===========================================================================
# AUDIT C: Strict Lookahead-Bias Verification (4 Mandatory Tests)
# ===========================================================================


def test_audit_c1_future_target_mutation_invariance():
    """
    Leakage Test 1 (Future-target mutation test):
    Modify quantity_sold after cutoff date t ('2013-10-31').
    Verify:
      (a) Engineered lag and rolling features at all dates <= t are bitwise identical.
      (b) Recursive multi-step forecasts generated from cutoff t ('2013-10-31') are bitwise identical.
    """
    dates = pd.date_range("2013-09-15", "2013-11-15", freq="D").strftime("%Y-%m-%d")
    cutoff = "2013-10-31"

    base_records = []
    mutated_records = []
    for idx, d in enumerate(dates):
        qty = float(20 + (idx % 7) * 3)
        mut_qty = qty if d <= cutoff else qty * 100.0 + 9999.0  # Massive future target mutation
        row_base = {
            "date": d,
            "store_nbr": 1,
            "product_id": 1,
            "family": "AUTOMOTIVE",
            "store_type": "D",
            "store_cluster": 13,
            "quantity_sold": qty,
            "promotion_quantity": 0,
            "oil_price": 95.0,
            "transactions": 1500,
        }
        row_mut = dict(row_base, quantity_sold=mut_qty)
        base_records.append(row_base)
        mutated_records.append(row_mut)

    df_base = pd.DataFrame(base_records)
    df_mut = pd.DataFrame(mutated_records)

    pipeline = TimeSeriesFeaturePipeline(drop_na_lags=True)
    feat_base = pipeline.transform(df_base)
    feat_mut = pipeline.transform(df_mut)

    # All feature rows on or before cutoff must be bitwise identical
    feat_base_pre = feat_base[feat_base["date"] <= cutoff].reset_index(drop=True)
    feat_mut_pre = feat_mut[feat_mut["date"] <= cutoff].reset_index(drop=True)
    pd.testing.assert_frame_equal(feat_base_pre, feat_mut_pre)

    # Recursive forecasts starting after cutoff must be bitwise identical
    model = ModelRegistry().load_model("lightgbm", version="v1")
    pred_base = ForecastingPredictor(model=model, history_df=df_base, as_of_date=cutoff).predict_recursive(horizon_days=7)
    pred_mut = ForecastingPredictor(model=model, history_df=df_mut, as_of_date=cutoff).predict_recursive(horizon_days=7)
    pd.testing.assert_frame_equal(pred_base, pred_mut)


def test_audit_c2_future_external_data_mutation_invariance():
    """
    Leakage Test 2 (Future-external-data mutation test):
    Modify future external variables (oil_price, promotion_quantity, transactions) after cutoff date t.
    Verify features at dates <= t and forecasts generated from cutoff t are bitwise unchanged.
    """
    dates = pd.date_range("2013-09-15", "2013-11-15", freq="D").strftime("%Y-%m-%d")
    cutoff = "2013-10-31"

    base_records = []
    mutated_records = []
    for idx, d in enumerate(dates):
        is_future = d > cutoff
        row_base = {
            "date": d,
            "store_nbr": 1,
            "product_id": 1,
            "family": "AUTOMOTIVE",
            "store_type": "D",
            "store_cluster": 13,
            "quantity_sold": float(15 + (idx % 5)),
            "promotion_quantity": 0,
            "oil_price": 95.0,
            "transactions": 1500,
        }
        row_mut = dict(
            row_base,
            oil_price=500.0 if is_future else 95.0,
            promotion_quantity=999 if is_future else 0,
            transactions=99999 if is_future else 1500,
        )
        base_records.append(row_base)
        mutated_records.append(row_mut)

    df_base = pd.DataFrame(base_records)
    df_mut = pd.DataFrame(mutated_records)

    pipeline = TimeSeriesFeaturePipeline(drop_na_lags=True)
    feat_base = pipeline.transform(df_base)
    feat_mut = pipeline.transform(df_mut)

    feat_base_pre = feat_base[feat_base["date"] <= cutoff].reset_index(drop=True)
    feat_mut_pre = feat_mut[feat_mut["date"] <= cutoff].reset_index(drop=True)
    pd.testing.assert_frame_equal(feat_base_pre, feat_mut_pre)

    model = ModelRegistry().load_model("lightgbm", version="v1")
    pred_base = ForecastingPredictor(model=model, history_df=df_base, as_of_date=cutoff).predict_recursive(horizon_days=7)
    pred_mut = ForecastingPredictor(model=model, history_df=df_mut, as_of_date=cutoff).predict_recursive(horizon_days=7)
    pd.testing.assert_frame_equal(pred_base, pred_mut)


def test_audit_c3_test_period_isolation_invariance(db_session):
    """
    Leakage Test 3 (Test-period isolation test):
    Modify December 2013 test actuals in the database transaction (rolled back after check).
    Verify that calibrated policy parameters (Safety Stock, Reorder Point, EOQ) do NOT change,
    while only the December simulation demand fulfillment changes.
    """
    ss_before = SafetyStockService.calculate_safety_stock(
        db=db_session, product_id=1, branch_id=1, lead_time_days=5, service_level=0.95
    )
    rop_before = SafetyStockService.calculate_reorder_point(
        db=db_session, product_id=1, branch_id=1, service_level=0.95, lead_time_days=5
    )
    eoq_before = EOQService.calculate_eoq(db=db_session, product_id=1, branch_id=1)

    # Temporarily mutate a December 2013 daily_sales record inside an uncommitted transaction block
    dec_sale = (
        db_session.query(DailySale)
        .filter(
            DailySale.product_id == 1,
            DailySale.branch_id == 1,
            DailySale.sale_date == "2013-12-15",
        )
        .first()
    )
    orig_qty = dec_sale.quantity_sold
    try:
        dec_sale.quantity_sold = float(orig_qty) + 500.0
        db_session.flush()

        ss_after = SafetyStockService.calculate_safety_stock(
            db=db_session, product_id=1, branch_id=1, lead_time_days=5, service_level=0.95
        )
        rop_after = SafetyStockService.calculate_reorder_point(
            db=db_session, product_id=1, branch_id=1, service_level=0.95, lead_time_days=5
        )
        eoq_after = EOQService.calculate_eoq(db=db_session, product_id=1, branch_id=1)
        sim_after = InventorySimulationService.simulate_product_branch(
            db=db_session, product_id=1, branch_id=1, start_date="2013-12-01", end_date="2013-12-31"
        )

        # Calibrated policy parameters must be 100% invariant to December actuals
        assert ss_after.safety_stock == ss_before.safety_stock
        assert rop_after.reorder_point == rop_before.reorder_point
        assert rop_after.expected_lead_time_demand == rop_before.expected_lead_time_demand
        assert eoq_after.calculated_eoq == eoq_before.calculated_eoq
        assert eoq_after.adjusted_order_quantity == eoq_before.adjusted_order_quantity

        # Simulation demand reflects the +500 mutation in December
        assert sim_after.baseline_policy.total_demand == 57.0 + 500.0
    finally:
        db_session.rollback()


def test_audit_c4_order_arrival_timing_strict_lead_time():
    """
    Leakage Test 4 (Order-arrival timing test):
    Verify an order placed at the end of day t with lead time L = 3 does NOT increase
    available inventory on days t, t+1, or t+2, and arrives strictly at the start of day t+3.
    """
    # Day 1 demand drops stock from 15 to 10 (<= ROP=10), triggering order of 50 units at end of Day 1.
    # With L = 3, order must arrive at start of Day 1 + 3 = Day 4.
    demands = [5.0, 4.0, 4.0, 4.0, 4.0]
    metrics, trajectory = InventorySimulationService._run_discrete_simulation(
        demand_sequence=demands,
        initial_stock=15,
        lead_time=3,
        reorder_point=10,
        order_quantity=50,
        ordering_cost=25.0,
        holding_cost_daily=0.01,
        stockout_cost_unit=5.0,
    )

    # Day 1: 15 - 5 = 10 (order triggered at end of Day 1 for arrival on Day 4)
    # Day 2: 10 - 4 = 6  (order NOT arrived yet)
    # Day 3: 6 - 4 = 2   (order NOT arrived yet)
    # Day 4: 2 + 50 (arrived!) - 4 = 48
    # Day 5: 48 - 4 = 44
    assert trajectory == [10, 6, 2, 48, 44]
    assert metrics.total_orders_placed == 1
    assert metrics.total_replenishment_quantity == 50
    assert metrics.stockout_days == 0
