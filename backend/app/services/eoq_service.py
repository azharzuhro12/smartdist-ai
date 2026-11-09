import math
from typing import Optional
from sqlalchemy.orm import Session
from backend.app.core.logging import logger
from backend.app.schemas.inventory_optimization import EOQResult
from backend.app.services.forecast_service import ForecastIntegrationService
from backend.app.services.inventory_service import InventoryService


class EOQService:
    """
    Economic Order Quantity (EOQ) calculation service enforcing supplier MOQ,
    packaging multiples, and annual inventory carrying cost constraints.
    """

    DEFAULT_ORDERING_COST = 50.0        # Default administrative procurement cost ($/order)
    DEFAULT_HOLDING_COST_RATE = 0.20    # Default annual holding cost rate (20% of unit cost)
    FALLBACK_UNIT_COST = 10.0           # Baseline fallback unit cost

    @classmethod
    def calculate_eoq(
        cls,
        db: Session,
        product_id: int,
        branch_id: int,
        ordering_cost: float = DEFAULT_ORDERING_COST,
        holding_cost_rate: float = DEFAULT_HOLDING_COST_RATE,
        order_multiple: Optional[int] = None,
    ) -> EOQResult:
        """
        Calculate unconstrained EOQ and apply supplier minimum order quantity (MOQ)
        and batch order multiple adjustments.
        """
        if ordering_cost < 0:
            raise ValueError(f"Ordering cost must be non-negative. Received: {ordering_cost}.")
        if not (0.0 < holding_cost_rate <= 1.0):
            raise ValueError(f"Holding cost rate must be in (0.0, 1.0]. Received: {holding_cost_rate}.")

        # 1. Retrieve Supplier Procurement Terms & Unit Cost
        inv = InventoryService.get_inventory_for_product_branch(db, product_id, branch_id)
        supplier = inv.supplier

        unit_cost = supplier.unit_cost if (supplier and supplier.unit_cost and supplier.unit_cost > 0) else cls.FALLBACK_UNIT_COST
        moq = supplier.minimum_order_quantity if (supplier and supplier.minimum_order_quantity) else 1
        multiple = order_multiple or (supplier.order_multiple if supplier else None) or 1

        holding_cost_unit = round(unit_cost * holding_cost_rate, 4)

        # 2. Estimate Annual Demand (D = average daily forecast * 365)
        try:
            fc = ForecastIntegrationService.get_forecast(db, product_id, branch_id, horizon_days=30)
            daily_forecasts = [r.predicted_demand for r in fc.daily_forecasts]
            if daily_forecasts:
                avg_daily = sum(daily_forecasts) / len(daily_forecasts)
            else:
                avg_daily = 0.0
        except Exception as e:
            logger.warning(f"Could not retrieve forecast for EOQ annual demand: {e}. Setting D=0.")
            avg_daily = 0.0

        annual_demand = round(avg_daily * 365.0, 2)

        # 3. Calculate Classic EOQ: sqrt((2 * D * S) / H)
        if annual_demand <= 0.0 or ordering_cost <= 0.0 or holding_cost_unit <= 0.0:
            calculated_eoq = 0.0
            adjusted_qty = 0
            adjustment_reason = "Zero or invalid demand/cost parameters; EOQ is zero."
        else:
            raw_eoq = math.sqrt((2.0 * annual_demand * ordering_cost) / holding_cost_unit)
            calculated_eoq = round(raw_eoq, 2)

            # 4. Apply Supplier MOQ & Order Multiple Constraints
            # Quantity must be at least MOQ
            target_qty = max(raw_eoq, float(moq))

            # Round up to nearest packaging multiple
            if multiple > 1:
                adjusted_qty = int(math.ceil(target_qty / multiple) * multiple)
            else:
                adjusted_qty = int(math.ceil(target_qty))

            # Document adjustment rationale
            reasons = []
            if raw_eoq < moq:
                reasons.append(f"EOQ ({calculated_eoq}) was below supplier MOQ ({moq}); bumped to MOQ.")
            if multiple > 1 and adjusted_qty != int(math.ceil(target_qty)):
                reasons.append(f"Adjusted to nearest multiple of {multiple}.")
            if not reasons:
                reasons.append("Optimal unconstrained EOQ satisfied supplier constraints.")
            adjustment_reason = " ".join(reasons)

        unit_cost_origin = supplier.data_origin if (supplier and hasattr(supplier, "data_origin")) else "SYNTHETIC_SUPPLIER_DATABASE"

        return EOQResult(
            annual_demand=annual_demand,
            ordering_cost=ordering_cost,
            holding_cost_rate=holding_cost_rate,
            unit_cost=unit_cost,
            holding_cost_unit=holding_cost_unit,
            calculated_eoq=calculated_eoq,
            minimum_order_quantity=moq,
            order_multiple=multiple if multiple > 1 else None,
            adjusted_order_quantity=adjusted_qty,
            adjustment_reason=adjustment_reason,
            annual_demand_methodology="30_DAY_FORECAST_ANNUALIZED_RUN_RATE",
            data_provenance={
                "unit_cost": unit_cost_origin,
                "ordering_cost": "CONFIGURABLE_PLANNING_ASSUMPTION",
                "holding_cost_rate": "CONFIGURABLE_PLANNING_ASSUMPTION",
                "annual_demand": "ANNUALIZED_30D_MODEL_FORECAST",
            },
        )
