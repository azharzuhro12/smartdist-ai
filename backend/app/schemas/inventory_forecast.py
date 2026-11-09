from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SupplierSummary(BaseModel):
    """
    Summary of merchandise supplier, lead time, and purchasing constraints.
    """
    model_config = ConfigDict(from_attributes=True)

    supplier_id: Optional[int] = None
    supplier_code: Optional[str] = None
    supplier_name: Optional[str] = None
    lead_time_days: Optional[int] = None
    minimum_order_quantity: Optional[int] = None
    order_multiple: Optional[int] = None
    unit_cost: Optional[float] = None
    is_active: bool = True
    data_origin: str = "SYNTHETIC"


class InventoryRecordSummary(BaseModel):
    """
    Normalized inventory balance and warehouse allocation.
    """
    model_config = ConfigDict(from_attributes=True)

    inventory_id: Optional[int] = None
    product_id: int
    product_code: str
    product_name: str
    branch_id: int
    branch_name: str
    warehouse_id: Optional[int] = None
    warehouse_code: Optional[str] = None
    current_stock: Optional[int] = Field(None, ge=0, description="On-hand physical stock quantity")
    reserved_stock: Optional[int] = Field(None, ge=0, description="Allocated or reserved customer stock")
    available_stock: Optional[int] = Field(None, description="current_stock - reserved_stock")
    reorder_point: Optional[int] = None
    safety_stock: Optional[int] = None
    last_updated: Optional[datetime] = None
    data_origin: str = "SYNTHETIC"
    supplier: Optional[SupplierSummary] = None


class DailyForecastRecord(BaseModel):
    """
    Single-day forward demand prediction record.
    """
    model_config = ConfigDict(from_attributes=True)

    date: str
    product_id: int
    branch_id: int
    predicted_demand: float = Field(..., ge=0.0, description="Non-negative forecasted sales volume")
    horizon_step: int = Field(..., ge=1, le=30, description="Forecast step index (1..horizon)")
    model_name: str
    model_version: str
    forecast_timestamp: datetime


class ForecastResponse(BaseModel):
    """
    Response schema for product-branch demand forecast over a requested horizon.
    """
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    branch_id: int
    horizon_days: int
    model_name: str
    model_version: str
    status: str = Field(..., description="AVAILABLE, ZERO_DEMAND, or UNAVAILABLE")
    forecast_timestamp: datetime
    daily_forecasts: List[DailyForecastRecord]


class InventoryForecastSnapshot(BaseModel):
    """
    Integrated snapshot combining physical inventory balances with ML demand forecasts.
    """
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    product_code: str
    product_name: str
    branch_id: int
    branch_name: str
    warehouse_id: Optional[int] = None
    warehouse_code: Optional[str] = None
    current_stock: Optional[int] = None
    reserved_stock: Optional[int] = None
    available_stock: Optional[int] = None
    forecast_horizon_days: int
    total_forecast_demand: float = Field(..., description="Sum of predicted demand over the horizon")
    average_daily_demand: float = Field(..., description="Average predicted demand per day")
    peak_daily_demand: float = Field(..., description="Maximum predicted demand on a single day")
    daily_forecasts: List[DailyForecastRecord]
    supplier: Optional[SupplierSummary] = None
    supplier_lead_time_days: Optional[int] = None
    inventory_data_origin: str = "SYNTHETIC"
    sales_data_origin: str = "KAGGLE_PUBLIC"
    forecast_model_name: str
    forecast_model_version: str
    snapshot_timestamp: datetime
    validation_status: str = "PASS"


class ValidationResultItem(BaseModel):
    """
    Individual data quality and consistency check outcome.
    """
    model_config = ConfigDict(from_attributes=True)

    validation_name: str
    status: str = Field(..., description="PASS, WARNING, or FAIL")
    severity: str = Field(..., description="INFO, LOW, MEDIUM, HIGH, or CRITICAL")
    description: str
    product_id: Optional[int] = None
    branch_id: Optional[int] = None
    timestamp: datetime


class ValidationReportResponse(BaseModel):
    """
    Comprehensive report of integration data validation checks.
    """
    model_config = ConfigDict(from_attributes=True)

    total_validations: int
    passed_count: int
    warning_count: int
    failure_count: int
    overall_status: str = Field(..., description="PASS, WARNING, or FAIL")
    results: List[ValidationResultItem]
    evaluated_at: datetime


class ForecastSummaryItem(BaseModel):
    """
    Summary item for inventory paired with multi-horizon demand forecasts.
    """
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    product_name: str
    branch_id: int
    branch_name: str
    warehouse_id: Optional[int] = None
    current_stock: Optional[int] = None
    available_stock: Optional[int] = None
    total_forecast_demand_7d: Optional[float] = None
    total_forecast_demand_14d: Optional[float] = None
    total_forecast_demand_30d: Optional[float] = None
    supplier_lead_time_days: Optional[int] = None
    data_origin: str = "SYNTHETIC"


class ForecastSummaryResponse(BaseModel):
    """
    Paginated summary response for inventory forecast overview.
    """
    model_config = ConfigDict(from_attributes=True)

    items: List[ForecastSummaryItem]
    total: int
    page: int
    size: int
    pages: int
    generated_at: datetime
