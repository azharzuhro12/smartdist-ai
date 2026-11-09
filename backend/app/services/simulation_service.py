from datetime import date, datetime, timedelta, timezone
import math
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.core.logging import logger
from backend.app.models.business import Branch, DailySale, Product, Warehouse
from backend.app.schemas.inventory_optimization import (
    PolicySimulationComparison,
    SimulationMetrics,
)
from backend.app.services.eoq_service import EOQService
from backend.app.services.inventory_service import InventoryService
from backend.app.services.safety_stock_service import SafetyStockService


class InventorySimulationService:
    """
    Discrete-time inventory policy simulation engine.
    Compares baseline static reorder policy against the optimized SmartDist AI
    dynamic forecast, safety stock, and EOQ policy over historical demand without lookahead bias.
    """

    @classmethod
    def simulate_product_branch(
        cls,
        db: Session,
        product_id: int,
        branch_id: int,
        start_date: str = "2013-12-01",
        end_date: str = "2013-12-31",
        initial_stock: Optional[int] = None,
        service_level: float = 0.95,
        ordering_cost: float = EOQService.DEFAULT_ORDERING_COST,
        holding_cost_rate: float = EOQService.DEFAULT_HOLDING_COST_RATE,
        stockout_penalty_per_unit: Optional[float] = None,
    ) -> PolicySimulationComparison:
        """
        Run side-by-side historical simulation of Baseline vs. Optimized inventory management.
        """
        # 1. Resolve Master Product and Branch
        product = db.get(Product, product_id)
        if not product:
            raise ValueError(f"Product ID {product_id} not found.")

        branch = db.get(Branch, branch_id)
        if not branch:
            raise ValueError(f"Branch ID {branch_id} not found.")

        inv_summary = InventoryService.get_inventory_for_product_branch(db, product_id, branch_id)
        supplier = inv_summary.supplier
        lead_time = supplier.lead_time_days if supplier else 5
        moq = supplier.minimum_order_quantity if supplier else 20
        unit_cost = supplier.unit_cost if (supplier and supplier.unit_cost) else EOQService.FALLBACK_UNIT_COST
        unit_holding_cost_daily = (unit_cost * holding_cost_rate) / 365.0
        stockout_cost_unit = stockout_penalty_per_unit or (unit_cost * 0.5)

        # 2. Extract Actual Daily Demand Time-Series over Simulation Window
        sales_query = (
            select(DailySale.sale_date, DailySale.quantity_sold)
            .where(
                DailySale.product_id == product_id,
                DailySale.branch_id == branch_id,
                DailySale.sale_date >= start_date,
                DailySale.sale_date <= end_date,
            )
            .order_by(DailySale.sale_date.asc())
        )
        sales_records = db.execute(sales_query).all()
        if not sales_records:
            raise ValueError(f"No historical demand records found between {start_date} and {end_date}.")

        actual_dates = [str(r.sale_date) for r in sales_records]
        actual_demands = [float(r.quantity_sold) for r in sales_records]
        sim_days = len(actual_demands)

        # Starting inventory: use physical on-hand stock or realistic average
        start_inv = initial_stock if initial_stock is not None else (inv_summary.current_stock or 100)

        # 3. Simulate Policy 1: Static Baseline Policy
        # Static baseline: fixed reorder point = 20, fixed order batch = max(50, MOQ)
        baseline_rop = 20
        baseline_order_qty = max(50, moq)
        baseline_metrics, baseline_trajectory = cls._run_discrete_simulation(
            demand_sequence=actual_demands,
            initial_stock=start_inv,
            lead_time=lead_time,
            reorder_point=baseline_rop,
            order_quantity=baseline_order_qty,
            ordering_cost=ordering_cost,
            holding_cost_daily=unit_holding_cost_daily,
            stockout_cost_unit=stockout_cost_unit,
        )

        # 4. Simulate Policy 2: Optimized SmartDist AI Policy
        # Dynamic forecast-based ROP and constrained EOQ
        rop_res = SafetyStockService.calculate_reorder_point(
            db=db, product_id=product_id, branch_id=branch_id, service_level=service_level, lead_time_days=lead_time
        )
        eoq_res = EOQService.calculate_eoq(
            db=db, product_id=product_id, branch_id=branch_id, ordering_cost=ordering_cost, holding_cost_rate=holding_cost_rate
        )
        opt_rop = rop_res.reorder_point_rounded
        opt_order_qty = eoq_res.adjusted_order_quantity

        optimized_metrics, opt_trajectory = cls._run_discrete_simulation(
            demand_sequence=actual_demands,
            initial_stock=start_inv,
            lead_time=lead_time,
            reorder_point=opt_rop,
            order_quantity=opt_order_qty,
            ordering_cost=ordering_cost,
            holding_cost_daily=unit_holding_cost_daily,
            stockout_cost_unit=stockout_cost_unit,
        )

        # 5. Comparative Improvements
        fill_rate_imp = round(optimized_metrics.fill_rate_pct - baseline_metrics.fill_rate_pct, 2)
        if baseline_metrics.total_modeled_cost > 0:
            cost_red = round(
                ((baseline_metrics.total_modeled_cost - optimized_metrics.total_modeled_cost) / baseline_metrics.total_modeled_cost) * 100.0,
                2,
            )
        else:
            cost_red = 0.0

        stockout_days_red = baseline_metrics.stockout_days - optimized_metrics.stockout_days

        # Trajectory sample for charting (first 30 days)
        trajectory_sample = []
        for d_idx, d_str in enumerate(actual_dates):
            trajectory_sample.append({
                "day": d_idx + 1,
                "date": d_str,
                "demand": actual_demands[d_idx],
                "baseline_stock": baseline_trajectory[d_idx],
                "optimized_stock": opt_trajectory[d_idx],
            })

        return PolicySimulationComparison(
            simulation_days=sim_days,
            start_date=start_date,
            end_date=end_date,
            product_id=product_id,
            product_name=product.product_name,
            branch_id=branch_id,
            branch_name=branch.branch_name,
            baseline_policy=baseline_metrics,
            optimized_policy=optimized_metrics,
            fill_rate_improvement_pct=fill_rate_imp,
            cost_reduction_pct=cost_red,
            stockout_days_reduction=stockout_days_red,
            daily_trajectory=trajectory_sample,
            data_provenance="OBSERVED_SALES_AND_SYNTHETIC_SUPPLIER_CONSTRAINTS",
            simulated_assumptions_note=(
                f"Evaluated over {sim_days} active trading days. Ordering cost: ${ordering_cost:.2f}, "
                f"holding rate: {holding_cost_rate*100:.0f}%, unit purchase cost: ${unit_cost:.2f}. "
                "Lost sales model applied when stock reaches 0."
            ),
        )

    @classmethod
    def _run_discrete_simulation(
        cls,
        demand_sequence: List[float],
        initial_stock: int,
        lead_time: int,
        reorder_point: int,
        order_quantity: int,
        ordering_cost: float,
        holding_cost_daily: float,
        stockout_cost_unit: float,
    ) -> Tuple[SimulationMetrics, List[int]]:
        """
        Execute discrete daily inventory balance tracking.
        """
        current_stock = float(initial_stock)
        pipeline_orders: Dict[int, float] = {}  # {arrival_day: quantity}

        total_demand = 0.0
        total_fulfilled = 0.0
        total_lost_sales = 0.0
        stockout_events = 0
        stockout_days = 0
        orders_placed = 0

        inventory_levels: List[float] = []
        stock_trajectory: List[int] = []

        for day, demand in enumerate(demand_sequence, start=1):
            total_demand += demand

            # 1. Deliveries arrive at start of day
            if day in pipeline_orders:
                current_stock += pipeline_orders.pop(day)

            # 2. Satisfy demand from on-hand stock
            if current_stock >= demand:
                current_stock -= demand
                total_fulfilled += demand
            else:
                fulfilled = max(0.0, current_stock)
                unfulfilled = demand - fulfilled
                current_stock = 0.0
                total_fulfilled += fulfilled
                total_lost_sales += unfulfilled
                stockout_days += 1
                if unfulfilled > 0:
                    stockout_events += 1

            inventory_levels.append(current_stock)
            stock_trajectory.append(int(current_stock))

            # 3. Check inventory position and trigger reorder at end of day
            inbound_qty = sum(pipeline_orders.values())
            inventory_position = current_stock + inbound_qty

            if inventory_position <= reorder_point:
                arrival_day = day + lead_time
                pipeline_orders[arrival_day] = pipeline_orders.get(arrival_day, 0.0) + float(order_quantity)
                orders_placed += 1

        # Calculate Summary Metrics
        fill_rate = (total_fulfilled / total_demand * 100.0) if total_demand > 0 else 100.0
        avg_inv = float(np.mean(inventory_levels)) if inventory_levels else 0.0
        max_inv = int(max(inventory_levels)) if inventory_levels else 0
        turnover = (total_fulfilled * (365.0 / len(demand_sequence)) / avg_inv) if avg_inv > 0 else 0.0

        tot_order_cost = orders_placed * ordering_cost
        tot_holding_cost = sum(inventory_levels) * holding_cost_daily
        tot_stockout_cost = total_lost_sales * stockout_cost_unit
        total_cost = tot_order_cost + tot_holding_cost + tot_stockout_cost

        r_order_cost = round(tot_order_cost, 2)
        r_holding_cost = round(tot_holding_cost, 2)
        r_stockout_cost = round(tot_stockout_cost, 2)
        r_total_cost = round(r_order_cost + r_holding_cost + r_stockout_cost, 2)

        metrics = SimulationMetrics(
            total_demand=round(total_demand, 2),
            total_fulfilled_demand=round(total_fulfilled, 2),
            fill_rate_pct=round(fill_rate, 2),
            stockout_frequency=stockout_events,
            stockout_days=stockout_days,
            unfulfilled_demand_units=round(total_lost_sales, 2),
            average_inventory=round(avg_inv, 2),
            max_inventory=max_inv,
            inventory_turnover=round(turnover, 2),
            total_orders_placed=orders_placed,
            total_replenishment_quantity=int(orders_placed * order_quantity),
            total_ordering_cost=r_order_cost,
            total_holding_cost=r_holding_cost,
            total_stockout_cost=r_stockout_cost,
            total_modeled_cost=r_total_cost,
        )

        return metrics, stock_trajectory
