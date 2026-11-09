from datetime import datetime, timezone
import math
from typing import List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.core.logging import logger
from backend.app.models.business import Branch, Inventory, Product, Warehouse
from backend.app.schemas.inventory_optimization import (
    InventoryDecisionResult,
    OptimizationSummaryItem,
    OptimizationSummaryResponse,
    ReplenishmentDecisionEnum,
    RiskCategoryEnum,
)
from backend.app.services.eoq_service import EOQService
from backend.app.services.inventory_service import InventoryService
from backend.app.services.replenishment_service import ReplenishmentService
from backend.app.services.safety_stock_service import SafetyStockService
from backend.app.services.stockout_risk_service import StockoutRiskService


class UnifiedInventoryDecisionEngine:
    """
    Unified operational decision engine coordinating demand forecasting,
    safety stock determination, dynamic ROP, Monte Carlo stockout risk analysis,
    and constrained EOQ replenishment recommendations.
    """

    @classmethod
    def evaluate_product_branch(
        cls,
        db: Session,
        product_id: int,
        branch_id: int,
        service_level: float = 0.95,
        ordering_cost: float = EOQService.DEFAULT_ORDERING_COST,
        holding_cost_rate: float = EOQService.DEFAULT_HOLDING_COST_RATE,
        order_multiple: Optional[int] = None,
    ) -> InventoryDecisionResult:
        """
        Execute full unified decision flow for a specific product and branch.
        """
        now_utc = datetime.now(timezone.utc)
        warnings: List[str] = []

        # 1. Retrieve Inventory Balance
        inv = InventoryService.get_inventory_for_product_branch(db, product_id, branch_id)
        supplier = inv.supplier
        lead_time = supplier.lead_time_days if supplier else 7

        if inv.current_stock is None:
            warnings.append("No active inventory balance found. Evaluation uses unassigned storefront defaults.")

        # 2. Expected Lead-Time Demand
        ltd_res = SafetyStockService.calculate_lead_time_demand(
            db=db, product_id=product_id, branch_id=branch_id, lead_time_days=lead_time
        )
        if ltd_res.status == "UNAVAILABLE":
            warnings.append("Forward demand forecast unavailable for this product-branch pair.")

        # 3. Safety Stock
        ss_res = SafetyStockService.calculate_safety_stock(
            db=db, product_id=product_id, branch_id=branch_id, lead_time_days=lead_time, service_level=service_level
        )

        # 4. Reorder Point
        rop_res = SafetyStockService.calculate_reorder_point(
            db=db, product_id=product_id, branch_id=branch_id, service_level=service_level, lead_time_days=lead_time
        )

        # 5. Stockout Risk
        risk_res = StockoutRiskService.estimate_stockout_risk(
            db=db, product_id=product_id, branch_id=branch_id, lead_time_days=lead_time
        )
        if risk_res.data_quality_warnings:
            warnings.extend(risk_res.data_quality_warnings)

        # 6. Constrained EOQ
        eoq_res = EOQService.calculate_eoq(
            db=db,
            product_id=product_id,
            branch_id=branch_id,
            ordering_cost=ordering_cost,
            holding_cost_rate=holding_cost_rate,
            order_multiple=order_multiple,
        )

        # 7. Replenishment Recommendation
        rec = ReplenishmentService.generate_recommendation(
            db=db,
            product_id=product_id,
            branch_id=branch_id,
            service_level=service_level,
            ordering_cost=ordering_cost,
            holding_cost_rate=holding_cost_rate,
            order_multiple=order_multiple,
        )

        provenance = {
            "sales_demand": "KAGGLE_PUBLIC",
            "inventory_balances": inv.data_origin,
            "supplier_constraints": supplier.data_origin if supplier else "SYNTHETIC",
            "forecast_model": "lightgbm_v1",
        }

        return InventoryDecisionResult(
            product_id=inv.product_id,
            product_name=inv.product_name,
            branch_id=inv.branch_id,
            branch_name=inv.branch_name,
            warehouse_id=inv.warehouse_id,
            current_stock=inv.current_stock,
            reserved_stock=inv.reserved_stock,
            available_stock=inv.available_stock,
            lead_time_demand=ltd_res,
            safety_stock=ss_res,
            reorder_point=rop_res,
            stockout_risk=risk_res,
            eoq=eoq_res,
            recommendation=rec,
            data_provenance=provenance,
            data_quality_warnings=warnings,
            decision_timestamp=now_utc,
        )

    @classmethod
    def get_optimization_summary(
        cls,
        db: Session,
        page: int = 1,
        size: int = 20,
        branch_id: Optional[int] = None,
        product_id: Optional[int] = None,
        service_level: float = 0.95,
    ) -> OptimizationSummaryResponse:
        """
        Network-wide summary aggregating reorder decisions and risk categories across products and branches.
        """
        now_utc = datetime.now(timezone.utc)
        inv_summaries, total = InventoryService.list_inventory_summaries(
            db=db, page=page, size=size, branch_id=branch_id, product_id=product_id
        )

        items: List[OptimizationSummaryItem] = []
        reorder_count = 0
        critical_count = 0

        for inv in inv_summaries:
            try:
                rec = ReplenishmentService.generate_recommendation(
                    db=db, product_id=inv.product_id, branch_id=inv.branch_id, service_level=service_level
                )
                if rec.decision in [ReplenishmentDecisionEnum.REORDER, ReplenishmentDecisionEnum.URGENT_REORDER]:
                    reorder_count += 1
                if rec.risk_category == RiskCategoryEnum.CRITICAL:
                    critical_count += 1

                items.append(
                    OptimizationSummaryItem(
                        product_id=inv.product_id,
                        product_name=inv.product_name,
                        branch_id=inv.branch_id,
                        branch_name=inv.branch_name,
                        available_stock=inv.available_stock,
                        reorder_point=rec.reorder_point,
                        safety_stock=rec.safety_stock,
                        expected_lead_time_demand=rec.expected_lead_time_demand,
                        stockout_probability=rec.stockout_probability,
                        risk_category=rec.risk_category,
                        recommended_order_quantity=rec.recommended_order_quantity,
                        decision=rec.decision,
                    )
                )
            except Exception as e:
                logger.warning(f"Error computing decision summary for ({inv.product_id}, {inv.branch_id}): {e}")

        pages = math.ceil(total / size) if total > 0 else 1

        return OptimizationSummaryResponse(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=pages,
            total_reorder_required=reorder_count,
            critical_risk_count=critical_count,
            generated_at=now_utc,
        )
