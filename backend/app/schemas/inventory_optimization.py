from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ServiceLevelEnum(float, Enum):
    LEVEL_90 = 0.90
    LEVEL_95 = 0.95
    LEVEL_98 = 0.98
    LEVEL_99 = 0.99


class RiskCategoryEnum(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ReplenishmentDecisionEnum(str, Enum):
    NO_ACTION = "NO_ACTION"
    REORDER = "REORDER"
    URGENT_REORDER = "URGENT_REORDER"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class LeadTimeDemandResult(BaseModel):
    """
    Cumulative forecasted sales demand during the supplier lead-time replenishment window.
    """
    model_config = ConfigDict(from_attributes=True)

    lead_time_days: int = Field(..., ge=1, description="Supplier lead time in days")
    expected_lead_time_demand: float = Field(..., ge=0.0, description="Sum of daily forecasts over lead time")
    daily_lead_time_forecast: List[float] = Field(default_factory=list)
    forecast_start_date: Optional[str] = None
    forecast_end_date: Optional[str] = None
    status: str = "AVAILABLE"


class SafetyStockResult(BaseModel):
    """
    Calculated safety stock buffer based on forecast error distribution and target service level.
    """
    model_config = ConfigDict(from_attributes=True)

    service_level: float = Field(..., ge=0.5, le=0.999, description="Target cycle service level")
    safety_stock: float = Field(..., ge=0.0, description="Recommended buffer stock in units")
    safety_stock_rounded: int = Field(..., ge=0, description="Ceiling integer buffer stock")
    method: str = Field(..., description="EMPIRICAL_QUANTILE, NORMAL_APPROXIMATION, or INSUFFICIENT_DATA")
    fallback_level: Optional[str] = Field("SERIES", description="Hierarchy level: SERIES, PRODUCT_POOLED, FAMILY_POOLED, PARAMETRIC, INSUFFICIENT_DATA")
    forecast_error_std: Optional[float] = None
    mean_bias: Optional[float] = Field(None, description="Average forecast error residual (actual - forecast)")
    autocorrelation_lag1: Optional[float] = Field(None, description="Lag-1 autocorrelation of residuals")
    lead_time_days: Optional[int] = None
    lead_time_error_quantile: Optional[float] = None
    sample_size: int = Field(0, description="Cumulative error observations evaluated")
    confidence_note: str = ""
    data_provenance: str = "OBSERVED_OUT_OF_SAMPLE_VALIDATION"


class ReorderPointResult(BaseModel):
    """
    Dynamic reorder point threshold combining lead-time demand and safety stock buffer.
    """
    model_config = ConfigDict(from_attributes=True)

    expected_lead_time_demand: float
    safety_stock: float
    reorder_point: float
    reorder_point_rounded: int
    current_available_stock: Optional[int] = None
    reorder_status: str = Field(..., description="REORDER_NOW, URGENT_REORDER, HEALTHY, INSUFFICIENT_DATA")


class StockoutRiskResult(BaseModel):
    """
    Monte Carlo simulated probability and severity of exhausting stock before replenishment arrives.
    """
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    branch_id: int
    available_stock: int
    lead_time_days: int
    expected_demand: float
    stockout_probability: float = Field(..., ge=0.0, le=1.0, description="Probability of stockout before replenishment")
    risk_category: RiskCategoryEnum
    expected_stockout_day: Optional[float] = Field(None, description="Average estimated day stockout occurs")
    scenarios_evaluated: int = Field(1000, description="Number of Monte Carlo scenarios simulated")
    stockout_scenarios_count: int
    methodology: str = "MONTE_CARLO_RESIDUAL_BOOTSTRAP"
    sampling_strategy: str = "CONTIGUOUS_BLOCK_BOOTSTRAP"
    total_shortage_simulated: Optional[float] = None
    data_quality_warnings: List[str] = Field(default_factory=list)


class EOQResult(BaseModel):
    """
    Economic Order Quantity and supplier constraint packaging adjustments.
    """
    model_config = ConfigDict(from_attributes=True)

    annual_demand: float = Field(..., ge=0.0, description="Annualized forecasted demand rate")
    ordering_cost: float = Field(..., ge=0.0, description="Procurement administrative cost per PO")
    holding_cost_rate: float = Field(..., ge=0.0, le=1.0, description="Annual inventory carrying cost percentage")
    unit_cost: float = Field(..., ge=0.0, description="Unit purchase cost from supplier")
    holding_cost_unit: float = Field(..., ge=0.0, description="Annual holding cost per unit (unit_cost * rate)")
    calculated_eoq: float = Field(..., ge=0.0, description="Theoretical unconstrained EOQ")
    minimum_order_quantity: Optional[int] = None
    order_multiple: Optional[int] = None
    adjusted_order_quantity: int = Field(..., ge=0, description="Final batch size meeting MOQ and packaging multiples")
    adjustment_reason: str = ""
    annual_demand_methodology: str = "30_DAY_FORECAST_ANNUALIZED_RUN_RATE"
    data_provenance: Dict[str, str] = Field(default_factory=lambda: {
        "unit_cost": "SYNTHETIC_SUPPLIER_DATABASE",
        "ordering_cost": "USER_CONFIGURED_DEFAULT",
        "holding_cost_rate": "USER_CONFIGURED_DEFAULT",
    })


class ReplenishmentRecommendation(BaseModel):
    """
    Actionable replenishment proposal with transparent justification.
    """
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    product_name: str
    branch_id: int
    branch_name: str
    current_stock: Optional[int] = None
    reserved_stock: Optional[int] = None
    available_stock: Optional[int] = None
    reorder_point: float
    safety_stock: float
    expected_lead_time_demand: float
    stockout_probability: float
    risk_category: RiskCategoryEnum
    calculated_eoq: float
    recommended_order_quantity: int
    decision: ReplenishmentDecisionEnum
    urgency_level: str = "NONE"
    explanation: str
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    supplier_lead_time_days: Optional[int] = None
    estimated_purchase_cost: Optional[float] = None
    generated_at: datetime


class InventoryDecisionResult(BaseModel):
    """
    Unified end-to-end decision object combining all Phase 3.3 modules.
    """
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    product_name: str
    branch_id: int
    branch_name: str
    warehouse_id: Optional[int] = None
    current_stock: Optional[int] = None
    reserved_stock: Optional[int] = None
    available_stock: Optional[int] = None
    lead_time_demand: LeadTimeDemandResult
    safety_stock: SafetyStockResult
    reorder_point: ReorderPointResult
    stockout_risk: StockoutRiskResult
    eoq: EOQResult
    recommendation: ReplenishmentRecommendation
    data_provenance: Dict[str, str] = Field(default_factory=dict)
    data_quality_warnings: List[str] = Field(default_factory=list)
    decision_timestamp: datetime


class SimulationMetrics(BaseModel):
    """
    Performance metrics recorded during inventory policy historical backtesting.
    """
    model_config = ConfigDict(from_attributes=True)

    total_demand: Optional[float] = Field(None, description="Total customer demand volume")
    total_fulfilled_demand: Optional[float] = Field(None, description="Total demand fulfilled from stock")
    fill_rate_pct: float = Field(..., description="Percentage of customer demand fulfilled immediately")
    stockout_frequency: int = Field(..., description="Count of stockout occurrences")
    stockout_days: int = Field(..., description="Count of days with unsatisfied positive demand")
    unfulfilled_demand_units: float = Field(..., description="Total unfulfilled volume lost")
    average_inventory: float = Field(..., description="Mean daily physical on-hand inventory")
    max_inventory: int = Field(..., description="Peak warehouse storage required")
    inventory_turnover: float = Field(..., description="Annualized inventory turnover ratio")
    total_orders_placed: int = Field(..., description="Number of replenishment purchase orders issued")
    total_replenishment_quantity: int = Field(0, description="Total replenishment units ordered across all purchase orders")
    total_ordering_cost: float = Field(..., description="Modeled procurement administrative cost")
    total_holding_cost: float = Field(..., description="Modeled inventory carrying cost")
    total_stockout_cost: float = Field(..., description="Estimated cost of lost sales/shortages")
    total_modeled_cost: float = Field(..., description="Sum of ordering, holding, and stockout costs")


class PolicySimulationComparison(BaseModel):
    """
    Comparative evaluation between baseline inventory management and the optimized SmartDist AI policy.
    """
    model_config = ConfigDict(from_attributes=True)

    simulation_days: int
    start_date: str
    end_date: str
    product_id: int
    product_name: str
    branch_id: int
    branch_name: str
    baseline_policy: SimulationMetrics
    optimized_policy: SimulationMetrics
    fill_rate_improvement_pct: float
    cost_reduction_pct: float
    stockout_days_reduction: int
    daily_trajectory: Optional[List[Dict[str, Any]]] = None
    data_provenance: str = "HISTORICAL_SALES_AND_SYNTHETIC_INVENTORY"
    simulated_assumptions_note: str


class OptimizationSummaryItem(BaseModel):
    """
    Overview row for inventory optimization dashboard.
    """
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    product_name: str
    branch_id: int
    branch_name: str
    available_stock: Optional[int] = None
    reorder_point: float
    safety_stock: float
    expected_lead_time_demand: float
    stockout_probability: float
    risk_category: RiskCategoryEnum
    recommended_order_quantity: int
    decision: ReplenishmentDecisionEnum


class OptimizationSummaryResponse(BaseModel):
    """
    Paginated response for network-wide inventory optimization status.
    """
    model_config = ConfigDict(from_attributes=True)

    items: List[OptimizationSummaryItem]
    total: int
    page: int
    size: int
    pages: int
    total_reorder_required: int
    critical_risk_count: int
    generated_at: datetime
