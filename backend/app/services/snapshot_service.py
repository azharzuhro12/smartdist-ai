from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.core.logging import logger
from backend.app.models.business import Branch, Inventory, Product, Warehouse
from backend.app.schemas.inventory_forecast import (
    ForecastSummaryItem,
    InventoryForecastSnapshot,
    InventoryRecordSummary,
)
from backend.app.services.forecast_service import ForecastIntegrationService
from backend.app.services.inventory_service import InventoryService


class InventoryForecastSnapshotService:
    """
    Combines physical inventory levels, supplier lead times, and forward demand forecasts
    into an integrated snapshot for inventory optimization and operational monitoring.
    """

    @classmethod
    def get_snapshot(
        cls,
        db: Session,
        product_id: int,
        branch_id: int,
        horizon_days: int = 7,
    ) -> InventoryForecastSnapshot:
        """
        Generate integrated snapshot for a single product and branch.
        """
        now_utc = datetime.now(timezone.utc)

        # 1. Retrieve Inventory and Supplier Information
        inv_summary = InventoryService.get_inventory_for_product_branch(
            db=db, product_id=product_id, branch_id=branch_id
        )

        # 2. Retrieve Forward Demand Forecast
        forecast_resp = ForecastIntegrationService.get_forecast(
            db=db, product_id=product_id, branch_id=branch_id, horizon_days=horizon_days
        )

        # 3. Calculate Aggregate Demand Metrics
        daily_preds = [f.predicted_demand for f in forecast_resp.daily_forecasts]
        if daily_preds:
            total_forecast = float(sum(daily_preds))
            avg_daily = float(total_forecast / len(daily_preds))
            peak_daily = float(max(daily_preds))
        else:
            total_forecast = 0.0
            avg_daily = 0.0
            peak_daily = 0.0

        # Determine validation status of the snapshot
        val_status = "PASS"
        if inv_summary.current_stock is None:
            val_status = "WARNING"
        elif forecast_resp.status == "UNAVAILABLE":
            val_status = "WARNING"

        return InventoryForecastSnapshot(
            product_id=inv_summary.product_id,
            product_code=inv_summary.product_code,
            product_name=inv_summary.product_name,
            branch_id=inv_summary.branch_id,
            branch_name=inv_summary.branch_name,
            warehouse_id=inv_summary.warehouse_id,
            warehouse_code=inv_summary.warehouse_code,
            current_stock=inv_summary.current_stock,
            reserved_stock=inv_summary.reserved_stock,
            available_stock=inv_summary.available_stock,
            forecast_horizon_days=horizon_days,
            total_forecast_demand=round(total_forecast, 4),
            average_daily_demand=round(avg_daily, 4),
            peak_daily_demand=round(peak_daily, 4),
            daily_forecasts=forecast_resp.daily_forecasts,
            supplier=inv_summary.supplier,
            supplier_lead_time_days=inv_summary.supplier.lead_time_days if inv_summary.supplier else None,
            inventory_data_origin=inv_summary.data_origin,
            sales_data_origin="KAGGLE_PUBLIC",
            forecast_model_name=forecast_resp.model_name,
            forecast_model_version=forecast_resp.model_version,
            snapshot_timestamp=now_utc,
            validation_status=val_status,
        )

    @classmethod
    def get_forecast_summary(
        cls,
        db: Session,
        page: int = 1,
        size: int = 20,
        branch_id: Optional[int] = None,
        product_id: Optional[int] = None,
    ) -> Tuple[List[ForecastSummaryItem], int]:
        """
        Produce paginated overview linking inventory balances with multi-horizon demand forecasts.
        """
        # Load inventory rows
        inv_summaries, total = InventoryService.list_inventory_summaries(
            db=db, page=page, size=size, branch_id=branch_id, product_id=product_id
        )

        items: List[ForecastSummaryItem] = []
        for inv in inv_summaries:
            # Query 7d, 14d, 30d forecast totals (efficiently generated via single 30d run)
            try:
                fc = ForecastIntegrationService.get_forecast(
                    db=db, product_id=inv.product_id, branch_id=inv.branch_id, horizon_days=30
                )
                daily = [f.predicted_demand for f in fc.daily_forecasts]
                tot_7d = round(sum(daily[:7]), 2) if len(daily) >= 7 else None
                tot_14d = round(sum(daily[:14]), 2) if len(daily) >= 14 else None
                tot_30d = round(sum(daily[:30]), 2) if len(daily) >= 30 else None
            except Exception as e:
                logger.warning(f"Error fetching summary forecast for ({inv.product_id}, {inv.branch_id}): {e}")
                tot_7d, tot_14d, tot_30d = None, None, None

            items.append(
                ForecastSummaryItem(
                    product_id=inv.product_id,
                    product_name=inv.product_name,
                    branch_id=inv.branch_id,
                    branch_name=inv.branch_name,
                    warehouse_id=inv.warehouse_id,
                    current_stock=inv.current_stock,
                    available_stock=inv.available_stock,
                    total_forecast_demand_7d=tot_7d,
                    total_forecast_demand_14d=tot_14d,
                    total_forecast_demand_30d=tot_30d,
                    supplier_lead_time_days=inv.supplier.lead_time_days if inv.supplier else None,
                    data_origin=inv.data_origin,
                )
            )

        return items, total
