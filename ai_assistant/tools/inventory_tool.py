"""
Inventory Optimization Tool for SmartDist AI Assistant.
Integrates with UnifiedInventoryDecisionEngine for ROP, SS, EOQ, and replenishment decisions.
"""

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.app.db.session import SessionLocal
from backend.app.services.decision_engine import UnifiedInventoryDecisionEngine


class InventoryOptimizationTool:
    """Tool for stockout risk analysis and replenishment decisions."""

    name = "inventory_optimization"
    description = "Computes safety stock, reorder point, EOQ, stockout probability, and replenishment orders."

    def __init__(self, service: Optional[UnifiedInventoryDecisionEngine] = None):
        self.service = service or UnifiedInventoryDecisionEngine()

    def evaluate_item(
        self,
        product_id: int,
        branch_id: int,
        service_level: float = 0.95,
        ordering_cost: float = 50.0,
        holding_cost_rate: float = 0.2,
        order_multiple: Optional[int] = None,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Evaluates inventory decision for a specific product and branch."""
        active_db = db or SessionLocal()
        close = db is None
        try:
            res = self.service.evaluate_product_branch(
                db=active_db,
                product_id=product_id,
                branch_id=branch_id,
                service_level=service_level,
                ordering_cost=ordering_cost,
                holding_cost_rate=holding_cost_rate,
                order_multiple=order_multiple,
            )
            return res.model_dump()
        finally:
            if close:
                active_db.close()

    def get_summary(
        self,
        page: int = 1,
        size: int = 20,
        branch_id: Optional[int] = None,
        product_id: Optional[int] = None,
        service_level: float = 0.95,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Gets batch inventory optimization summary."""
        active_db = db or SessionLocal()
        close = db is None
        try:
            res = self.service.get_optimization_summary(
                db=active_db,
                page=page,
                size=size,
                branch_id=branch_id,
                product_id=product_id,
                service_level=service_level,
            )
            return res.model_dump()
        finally:
            if close:
                active_db.close()

