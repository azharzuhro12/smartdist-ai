"""
Demand Forecasting Tool for SmartDist AI Assistant.
Integrates with ForecastIntegrationService to deliver multi-step recursive forecasts.
"""

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.app.db.session import SessionLocal
from backend.app.services.forecast_service import ForecastIntegrationService


class ForecastTool:
    """Tool for querying recursive demand forecasts across horizons."""

    name = "demand_forecasting"
    description = "Generates multi-step recursive demand forecasts (7, 14, 30 days) using trained LightGBM models."

    def __init__(self, service: Optional[ForecastIntegrationService] = None):
        self.service = service or ForecastIntegrationService()

    def get_forecast(
        self,
        product_id: int,
        branch_id: int,
        horizon_days: int = 7,
        forecast_start_date: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Queries demand forecast for a given product and branch."""
        active_db = db or SessionLocal()
        close = db is None
        try:
            res = self.service.get_forecast(
                db=active_db,
                product_id=product_id,
                branch_id=branch_id,
                horizon_days=horizon_days,
                forecast_start_date=forecast_start_date,
            )
            return res.model_dump()
        finally:
            if close:
                active_db.close()

