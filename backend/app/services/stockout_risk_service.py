import random
from typing import List, Optional
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from backend.app.core.logging import logger
from backend.app.schemas.inventory_optimization import (
    RiskCategoryEnum,
    StockoutRiskResult,
)
from backend.app.services.inventory_service import InventoryService
from backend.app.services.safety_stock_service import SafetyStockService


class StockoutRiskService:
    """
    Explainable stockout risk engine that simulates forward demand scenarios
    using out-of-sample forecast uncertainty to estimate the empirical probability
    that available stock will be depleted before supplier replenishment arrives.
    """

    DEFAULT_SIMULATION_COUNT = 1000
    RANDOM_SEED = 42

    @classmethod
    def estimate_stockout_risk(
        cls,
        db: Session,
        product_id: int,
        branch_id: int,
        lead_time_days: Optional[int] = None,
        simulation_scenarios: int = DEFAULT_SIMULATION_COUNT,
        random_seed: int = RANDOM_SEED,
        incoming_orders: Optional[dict] = None,
    ) -> StockoutRiskResult:
        """
        Estimate stockout probability and risk severity via Monte Carlo contiguous block bootstrap.
        Defines stockout strictly based on unfulfilled demand (shortage > 0).
        """
        warnings: List[str] = []

        # 1. Retrieve Current Inventory
        inv = InventoryService.get_inventory_for_product_branch(db, product_id, branch_id)
        if inv.available_stock is None:
            warnings.append("No active inventory balance found. Stockout probability is undefined.")
            return StockoutRiskResult(
                product_id=product_id,
                branch_id=branch_id,
                available_stock=0,
                lead_time_days=lead_time_days or 7,
                expected_demand=0.0,
                stockout_probability=1.0,
                risk_category=RiskCategoryEnum.CRITICAL,
                expected_stockout_day=1.0,
                scenarios_evaluated=0,
                stockout_scenarios_count=0,
                methodology="INSUFFICIENT_DATA_FALLBACK",
                sampling_strategy="NONE",
                total_shortage_simulated=0.0,
                data_quality_warnings=warnings,
            )

        available_stock = inv.available_stock

        # 2. Retrieve Lead-Time Forecast
        ltd_result = SafetyStockService.calculate_lead_time_demand(
            db=db, product_id=product_id, branch_id=branch_id, lead_time_days=lead_time_days
        )
        L = ltd_result.lead_time_days
        daily_forecasts = ltd_result.daily_lead_time_forecast

        if ltd_result.status == "UNAVAILABLE" or not daily_forecasts:
            warnings.append("Forecast unavailable. Stockout risk cannot be evaluated.")
            return StockoutRiskResult(
                product_id=product_id,
                branch_id=branch_id,
                available_stock=available_stock,
                lead_time_days=L,
                expected_demand=0.0,
                stockout_probability=0.0,
                risk_category=RiskCategoryEnum.LOW,
                expected_stockout_day=None,
                scenarios_evaluated=0,
                stockout_scenarios_count=0,
                methodology="UNAVAILABLE_FORECAST",
                sampling_strategy="NONE",
                total_shortage_simulated=0.0,
                data_quality_warnings=warnings,
            )

        # 3. Retrieve Residual Distribution & Construct Contiguous L-day Blocks
        residuals_df = SafetyStockService._load_out_of_sample_residuals()
        rng = np.random.RandomState(random_seed)
        store_nbr = inv.branch_id  # branch mapping to store_nbr

        candidate_blocks: List[np.ndarray] = []
        sampling_strategy = "CONTIGUOUS_BLOCK_BOOTSTRAP"
        sigma_e = 10.0
        rho = 0.35

        if not residuals_df.empty:
            # 3a. Extract contiguous blocks from specific series
            s_df = residuals_df[(residuals_df["store_nbr"] == store_nbr) & (residuals_df["product_id"] == product_id)].sort_values("date")
            if len(s_df) >= L:
                s_errs = s_df["residual"].dropna().to_numpy(dtype=float)
                for start_idx in range(len(s_errs) - L + 1):
                    candidate_blocks.append(s_errs[start_idx : start_idx + L])

            # 3b. If series has fewer than 20 candidate blocks, pool from product across stores
            if len(candidate_blocks) < 20:
                p_df = residuals_df[residuals_df["product_id"] == product_id]
                for _, s_group in p_df.groupby("store_nbr"):
                    p_errs = s_group.sort_values("date")["residual"].dropna().to_numpy(dtype=float)
                    if len(p_errs) >= L:
                        for start_idx in range(len(p_errs) - L + 1):
                            candidate_blocks.append(p_errs[start_idx : start_idx + L])

            # Statistical parameters for AR(1) fallback if blocks empty
            p_res = residuals_df[residuals_df["product_id"] == product_id]["residual"].dropna().to_numpy(dtype=float)
            if len(p_res) > 1:
                sigma_e = float(np.std(p_res, ddof=1))
                if len(p_res) > 2:
                    rho_calc = pd.Series(p_res).autocorr(1)
                    rho = 0.0 if np.isnan(rho_calc) else float(rho_calc)

        if not candidate_blocks:
            sampling_strategy = "AR1_PARAMETRIC_BOOTSTRAP"

        # 4. Monte Carlo Scenario Generation (Strict Shortage Definition)
        stockout_count = 0
        stockout_days: List[float] = []
        total_shortage_sum = 0.0

        for _ in range(simulation_scenarios):
            remaining_stock = float(available_stock)
            total_scenario_shortage = 0.0
            first_shortage_day = None

            # Sample L-day error sequence
            if candidate_blocks:
                block_idx = int(rng.randint(0, len(candidate_blocks)))
                error_sequence = candidate_blocks[block_idx]
            else:
                # AR(1) autoregressive noise fallback
                noise = rng.normal(0.0, sigma_e, size=L)
                error_sequence = np.zeros(L, dtype=float)
                prev = 0.0
                for d_i in range(L):
                    error_sequence[d_i] = rho * prev + np.sqrt(max(0.0, 1.0 - rho**2)) * noise[d_i]
                    prev = error_sequence[d_i]

            for day_idx in range(1, L + 1):
                # Arriving replenishment at start of day
                if incoming_orders and day_idx in incoming_orders:
                    remaining_stock += float(incoming_orders[day_idx])

                point_fc = daily_forecasts[day_idx - 1]
                sampled_error = float(error_sequence[day_idx - 1])
                simulated_day_demand = max(0.0, point_fc + sampled_error)

                # Shortage occurs only when demand strictly exceeds available stock
                shortage = max(0.0, simulated_day_demand - remaining_stock)
                remaining_stock = max(0.0, remaining_stock - simulated_day_demand)

                if shortage > 0.0:
                    total_scenario_shortage += shortage
                    if first_shortage_day is None:
                        first_shortage_day = float(day_idx)

            if total_scenario_shortage > 0.0:
                stockout_count += 1
                if first_shortage_day is not None:
                    stockout_days.append(first_shortage_day)
            total_shortage_sum += total_scenario_shortage

        stockout_prob = round(float(stockout_count / simulation_scenarios), 4)
        avg_stockout_day = round(float(np.mean(stockout_days)), 2) if stockout_days else None
        avg_shortage = round(float(total_shortage_sum / simulation_scenarios), 2)

        # 5. Risk Categorization
        if stockout_prob < 0.10:
            category = RiskCategoryEnum.LOW
        elif stockout_prob < 0.30:
            category = RiskCategoryEnum.MEDIUM
        elif stockout_prob < 0.60:
            category = RiskCategoryEnum.HIGH
        else:
            category = RiskCategoryEnum.CRITICAL

        return StockoutRiskResult(
            product_id=product_id,
            branch_id=branch_id,
            available_stock=available_stock,
            lead_time_days=L,
            expected_demand=ltd_result.expected_lead_time_demand,
            stockout_probability=stockout_prob,
            risk_category=category,
            expected_stockout_day=avg_stockout_day,
            scenarios_evaluated=simulation_scenarios,
            stockout_scenarios_count=stockout_count,
            methodology="MONTE_CARLO_RESIDUAL_BOOTSTRAP",
            sampling_strategy=sampling_strategy,
            total_shortage_simulated=avg_shortage,
            data_quality_warnings=warnings,
        )
