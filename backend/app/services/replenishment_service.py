from datetime import datetime, timezone
import math
from typing import Optional
from sqlalchemy.orm import Session
from backend.app.core.logging import logger
from backend.app.schemas.inventory_optimization import (
    EOQResult,
    ReorderPointResult,
    ReplenishmentDecisionEnum,
    ReplenishmentRecommendation,
    RiskCategoryEnum,
    StockoutRiskResult,
)
from backend.app.services.eoq_service import EOQService
from backend.app.services.inventory_service import InventoryService
from backend.app.services.safety_stock_service import SafetyStockService
from backend.app.services.stockout_risk_service import StockoutRiskService


class ReplenishmentService:
    """
    Explainable inventory replenishment decision engine synthesizing inventory position,
    dynamic reorder thresholds, simulated stockout risk, and constrained EOQ batching.
    """

    @classmethod
    def generate_recommendation(
        cls,
        db: Session,
        product_id: int,
        branch_id: int,
        service_level: float = 0.95,
        ordering_cost: float = EOQService.DEFAULT_ORDERING_COST,
        holding_cost_rate: float = EOQService.DEFAULT_HOLDING_COST_RATE,
        order_multiple: Optional[int] = None,
    ) -> ReplenishmentRecommendation:
        """
        Produce actionable replenishment recommendation with full mathematical transparency.
        """
        now_utc = datetime.now(timezone.utc)

        # 1. Retrieve Current Inventory & Master Details
        inv = InventoryService.get_inventory_for_product_branch(db, product_id, branch_id)
        supplier = inv.supplier
        lead_time = supplier.lead_time_days if supplier else 7
        avail = inv.available_stock

        # 2. Compute Reorder Point and Safety Stock
        rop_res = SafetyStockService.calculate_reorder_point(
            db=db,
            product_id=product_id,
            branch_id=branch_id,
            service_level=service_level,
            lead_time_days=lead_time,
        )

        # 3. Compute Simulated Stockout Risk
        risk_res = StockoutRiskService.estimate_stockout_risk(
            db=db,
            product_id=product_id,
            branch_id=branch_id,
            lead_time_days=lead_time,
        )

        # 4. Compute Constrained EOQ
        eoq_res = EOQService.calculate_eoq(
            db=db,
            product_id=product_id,
            branch_id=branch_id,
            ordering_cost=ordering_cost,
            holding_cost_rate=holding_cost_rate,
            order_multiple=order_multiple,
        )

        # 5. Synthesize Decision & Order Quantity
        if avail is None:
            decision = ReplenishmentDecisionEnum.INSUFFICIENT_DATA
            urgency = "NONE"
            rec_qty = 0
            explanation = (
                f"Cannot evaluate replenishment for product '{inv.product_name}' at branch '{inv.branch_name}' "
                "because no active physical inventory balance was found."
            )
        elif avail <= rop_res.safety_stock:
            decision = ReplenishmentDecisionEnum.URGENT_REORDER
            urgency = "CRITICAL" if risk_res.risk_category == RiskCategoryEnum.CRITICAL else "HIGH"
            # Target Order-Up-To Level: ROP + Q*
            target_level = rop_res.reorder_point + eoq_res.adjusted_order_quantity
            deficit = max(0.0, target_level - avail)
            rec_qty = max(eoq_res.adjusted_order_quantity, int(math.ceil(deficit)))
            # Enforce MOQ
            if eoq_res.minimum_order_quantity and rec_qty < eoq_res.minimum_order_quantity:
                rec_qty = eoq_res.minimum_order_quantity
            # Enforce Multiple
            if eoq_res.order_multiple and eoq_res.order_multiple > 1:
                rec_qty = int(math.ceil(rec_qty / eoq_res.order_multiple) * eoq_res.order_multiple)

            explanation = (
                f"URGENT: Available stock ({avail} units) has breached the safety stock threshold "
                f"({int(math.ceil(rop_res.safety_stock))} units). Simulated stockout risk is {risk_res.stockout_probability*100:.1f}% "
                f"({risk_res.risk_category.value}). Immediate purchase order of {rec_qty} units is strongly recommended."
            )
        elif avail <= rop_res.reorder_point:
            decision = ReplenishmentDecisionEnum.REORDER
            urgency = "MEDIUM" if risk_res.risk_category in [RiskCategoryEnum.LOW, RiskCategoryEnum.MEDIUM] else "HIGH"
            target_level = rop_res.reorder_point + eoq_res.adjusted_order_quantity
            deficit = max(0.0, target_level - avail)
            rec_qty = max(eoq_res.adjusted_order_quantity, int(math.ceil(deficit)))
            if eoq_res.minimum_order_quantity and rec_qty < eoq_res.minimum_order_quantity:
                rec_qty = eoq_res.minimum_order_quantity
            if eoq_res.order_multiple and eoq_res.order_multiple > 1:
                rec_qty = int(math.ceil(rec_qty / eoq_res.order_multiple) * eoq_res.order_multiple)

            explanation = (
                f"REORDER ADVISORY: Available stock ({avail} units) is at or below the dynamic reorder point "
                f"({rop_res.reorder_point_rounded} units). Expected lead-time demand is {rop_res.expected_lead_time_demand:.1f} units. "
                f"Reorder batch of {rec_qty} units recommended (adjusted for EOQ and supplier MOQ={eoq_res.minimum_order_quantity})."
            )
        else:
            decision = ReplenishmentDecisionEnum.NO_ACTION
            urgency = "NONE"
            rec_qty = 0
            explanation = (
                f"HEALTHY: Available stock ({avail} units) comfortably exceeds the dynamic reorder point "
                f"({rop_res.reorder_point_rounded} units). Expected lead-time demand is {rop_res.expected_lead_time_demand:.1f} units "
                f"with safety buffer of {int(math.ceil(rop_res.safety_stock))} units. Stockout risk is {risk_res.stockout_probability*100:.1f}% ({risk_res.risk_category.value})."
            )

        # Estimated purchase order cost
        unit_cost = supplier.unit_cost if (supplier and supplier.unit_cost) else EOQService.FALLBACK_UNIT_COST
        estimated_cost = round(float(rec_qty * unit_cost), 2) if rec_qty > 0 else 0.0

        return ReplenishmentRecommendation(
            product_id=inv.product_id,
            product_name=inv.product_name,
            branch_id=inv.branch_id,
            branch_name=inv.branch_name,
            current_stock=inv.current_stock,
            reserved_stock=inv.reserved_stock,
            available_stock=inv.available_stock,
            reorder_point=rop_res.reorder_point,
            safety_stock=rop_res.safety_stock,
            expected_lead_time_demand=rop_res.expected_lead_time_demand,
            stockout_probability=risk_res.stockout_probability,
            risk_category=risk_res.risk_category,
            calculated_eoq=eoq_res.calculated_eoq,
            recommended_order_quantity=rec_qty,
            decision=decision,
            urgency_level=urgency,
            explanation=explanation,
            supplier_id=supplier.supplier_id if supplier else None,
            supplier_name=supplier.supplier_name if supplier else None,
            supplier_lead_time_days=lead_time,
            estimated_purchase_cost=estimated_cost,
            generated_at=now_utc,
        )
