from datetime import datetime, timezone
import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from backend.app.core.logging import logger
from backend.app.db.session import get_db
from backend.app.models.business import Branch, Inventory, Product
from backend.app.schemas.business import (
    InventoryResponse,
    PaginatedResponse,
    SyntheticGenerationRequest,
    SyntheticGenerationResponse,
)
from backend.app.schemas.inventory_forecast import (
    ForecastResponse,
    ForecastSummaryResponse,
    InventoryForecastSnapshot,
    ValidationReportResponse,
)
from backend.app.schemas.inventory_optimization import (
    EOQResult,
    InventoryDecisionResult,
    OptimizationSummaryResponse,
    PolicySimulationComparison,
    ReorderPointResult,
    ReplenishmentRecommendation,
    SafetyStockResult,
    StockoutRiskResult,
)
from backend.app.services.decision_engine import UnifiedInventoryDecisionEngine
from backend.app.services.eoq_service import EOQService
from backend.app.services.forecast_service import ForecastIntegrationService
from backend.app.services.integration_validator import IntegrationValidator
from backend.app.services.inventory_service import InventoryService
from backend.app.services.replenishment_service import ReplenishmentService
from backend.app.services.safety_stock_service import SafetyStockService
from backend.app.services.simulation_service import InventorySimulationService
from backend.app.services.snapshot_service import InventoryForecastSnapshotService
from backend.app.services.stockout_risk_service import StockoutRiskService
from backend.app.workers.tasks import generate_synthetic_inventory

router = APIRouter()


# ---------------------------------------------------------------------------
# Request Schemas for Endpoints
# ---------------------------------------------------------------------------

class SimulationRunRequest(BaseModel):
    product_id: int
    branch_id: int
    start_date: str = "2013-12-01"
    end_date: str = "2013-12-31"
    initial_stock: Optional[int] = None
    service_level: float = Field(0.95, ge=0.5, le=0.999)
    ordering_cost: float = Field(50.0, ge=0.0)
    holding_cost_rate: float = Field(0.20, gt=0.0, le=1.0)
    stockout_penalty_per_unit: Optional[float] = None


# ---------------------------------------------------------------------------
# Core Inventory Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=PaginatedResponse[InventoryResponse], summary="List Inventory Balances")
def list_inventory(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    product_id: Optional[int] = Query(None, description="Filter by product ID"),
    warehouse_id: Optional[int] = Query(None, description="Filter by warehouse ID"),
    db: Session = Depends(get_db),
) -> PaginatedResponse[InventoryResponse]:
    """
    List physical and reserved stock balances across regional warehouses.
    """
    query = select(Inventory)
    if product_id:
        query = query.where(Inventory.product_id == product_id)
    if warehouse_id:
        query = query.where(Inventory.warehouse_id == warehouse_id)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    pages = math.ceil(total / size) if total > 0 else 1

    items = db.execute(query.order_by(Inventory.id).offset((page - 1) * size).limit(size)).scalars().all()

    return PaginatedResponse(
        items=list(items),
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.post(
    "/generate-synthetic",
    response_model=SyntheticGenerationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger Synthetic Inventory Generation",
)
def trigger_synthetic_inventory_generation(
    request: SyntheticGenerationRequest,
) -> SyntheticGenerationResponse:
    """
    Dispatch background task to generate or replenish reproducible synthetic inventory and supplier data.
    """
    logger.info(f"Triggering synthetic inventory generation with seed={request.seed}")
    task = generate_synthetic_inventory.delay(seed=request.seed)
    return SyntheticGenerationResponse(
        message="Synthetic inventory generation dispatched successfully.",
        task_id=task.id,
        seed=request.seed,
    )


# ---------------------------------------------------------------------------
# Integration & Summary Overview Endpoints (Static Paths first)
# ---------------------------------------------------------------------------

@router.get(
    "/forecast-summary",
    response_model=ForecastSummaryResponse,
    summary="List Inventory & Multi-Horizon Forecast Overview",
)
def get_inventory_forecast_summary(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    branch_id: Optional[int] = Query(None, description="Filter by branch ID"),
    product_id: Optional[int] = Query(None, description="Filter by product ID"),
    db: Session = Depends(get_db),
) -> ForecastSummaryResponse:
    """
    Retrieve overview linking inventory balances with 7-day, 14-day, and 30-day demand forecasts.
    """
    items, total = InventoryForecastSnapshotService.get_forecast_summary(
        db=db, page=page, size=size, branch_id=branch_id, product_id=product_id
    )
    pages = math.ceil(total / size) if total > 0 else 1
    return ForecastSummaryResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages,
        generated_at=datetime.now(timezone.utc),
    )


@router.get(
    "/optimization-summary",
    response_model=OptimizationSummaryResponse,
    summary="List Optimization and Reorder Status Across Network",
)
def get_optimization_summary(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    branch_id: Optional[int] = Query(None, description="Filter by branch ID"),
    product_id: Optional[int] = Query(None, description="Filter by product ID"),
    service_level: float = Query(0.95, ge=0.5, le=0.999),
    db: Session = Depends(get_db),
) -> OptimizationSummaryResponse:
    """
    Network-wide overview showing reorder decisions, stockout risk severity, and proposed order batches.
    """
    return UnifiedInventoryDecisionEngine.get_optimization_summary(
        db=db,
        page=page,
        size=size,
        branch_id=branch_id,
        product_id=product_id,
        service_level=service_level,
    )


@router.post(
    "/simulations",
    response_model=PolicySimulationComparison,
    summary="Simulate and Compare Baseline vs. Optimized Policy",
)
def run_inventory_simulation(
    request: SimulationRunRequest,
    db: Session = Depends(get_db),
) -> PolicySimulationComparison:
    """
    Simulate daily inventory trajectory over historical demand comparing baseline static vs optimized dynamic policy.
    """
    try:
        return InventorySimulationService.simulate_product_branch(
            db=db,
            product_id=request.product_id,
            branch_id=request.branch_id,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_stock=request.initial_stock,
            service_level=request.service_level,
            ordering_cost=request.ordering_cost,
            holding_cost_rate=request.holding_cost_rate,
            stockout_penalty_per_unit=request.stockout_penalty_per_unit,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error during simulation run: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Simulation run failed.")


@router.post(
    "/validate-integration",
    response_model=ValidationReportResponse,
    summary="Run Integration Data Quality & Consistency Validation",
)
def validate_integration(
    product_id: Optional[int] = Query(None, description="Optional product ID to validate"),
    branch_id: Optional[int] = Query(None, description="Optional branch ID to validate"),
    sample_limit: int = Query(50, ge=1, le=200, description="Max products to validate when unscoped"),
    db: Session = Depends(get_db),
) -> ValidationReportResponse:
    """
    Run data consistency, stock integrity, supplier lead time, and forecast validity checks.
    """
    report = IntegrationValidator.run_system_wide_validation(
        db=db,
        sample_limit=sample_limit,
        product_id=product_id,
        branch_id=branch_id,
    )
    return report


# ---------------------------------------------------------------------------
# Specific Product & Branch Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/{product_id}/{branch_id}/forecast",
    response_model=ForecastResponse,
    summary="Get Demand Forecast for Product and Branch",
)
def get_product_branch_forecast(
    product_id: int,
    branch_id: int,
    horizon_days: int = Query(7, description="Forecast horizon in days (7, 14, 30)"),
    db: Session = Depends(get_db),
) -> ForecastResponse:
    """
    Retrieve recursive demand forecast records for a specific product and branch.
    """
    if horizon_days not in [7, 14, 30]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid forecast horizon: {horizon_days}. Allowed horizons: 7, 14, 30.",
        )
    _validate_entities_exist(db, product_id, branch_id)
    try:
        return ForecastIntegrationService.get_forecast(db=db, product_id=product_id, branch_id=branch_id, horizon_days=horizon_days)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/{product_id}/{branch_id}/snapshot",
    response_model=InventoryForecastSnapshot,
    summary="Get Integrated Inventory and Forecast Snapshot",
)
def get_product_branch_snapshot(
    product_id: int,
    branch_id: int,
    horizon_days: int = Query(7, description="Forecast horizon in days (7, 14, 30)"),
    db: Session = Depends(get_db),
) -> InventoryForecastSnapshot:
    """
    Retrieve integrated snapshot combining physical inventory, supplier lead time, and forward demand forecast metrics.
    """
    if horizon_days not in [7, 14, 30]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid forecast horizon: {horizon_days}. Allowed horizons: 7, 14, 30.",
        )
    _validate_entities_exist(db, product_id, branch_id)
    try:
        return InventoryForecastSnapshotService.get_snapshot(db=db, product_id=product_id, branch_id=branch_id, horizon_days=horizon_days)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/{product_id}/{branch_id}/safety-stock",
    response_model=SafetyStockResult,
    summary="Calculate Safety Stock Buffer",
)
def get_product_branch_safety_stock(
    product_id: int,
    branch_id: int,
    service_level: float = Query(0.95, ge=0.5, le=0.999),
    lead_time_days: Optional[int] = Query(None, ge=1, le=30),
    db: Session = Depends(get_db),
) -> SafetyStockResult:
    """
    Calculate safety stock buffer based on out-of-sample forecast error uncertainty.
    """
    _validate_entities_exist(db, product_id, branch_id)
    try:
        if lead_time_days is None:
            inv = InventoryService.get_inventory_for_product_branch(db, product_id, branch_id)
            lead_time_days = inv.supplier.lead_time_days if inv.supplier else 7
        return SafetyStockService.calculate_safety_stock(
            db=db, product_id=product_id, branch_id=branch_id, lead_time_days=lead_time_days, service_level=service_level
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/{product_id}/{branch_id}/reorder-point",
    response_model=ReorderPointResult,
    summary="Calculate Dynamic Reorder Point",
)
def get_product_branch_reorder_point(
    product_id: int,
    branch_id: int,
    service_level: float = Query(0.95, ge=0.5, le=0.999),
    lead_time_days: Optional[int] = Query(None, ge=1, le=30),
    db: Session = Depends(get_db),
) -> ReorderPointResult:
    """
    Calculate dynamic reorder point (expected lead-time demand + safety stock).
    """
    _validate_entities_exist(db, product_id, branch_id)
    try:
        return SafetyStockService.calculate_reorder_point(
            db=db, product_id=product_id, branch_id=branch_id, service_level=service_level, lead_time_days=lead_time_days
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/{product_id}/{branch_id}/stockout-risk",
    response_model=StockoutRiskResult,
    summary="Estimate Stockout Risk via Monte Carlo Simulation",
)
def get_product_branch_stockout_risk(
    product_id: int,
    branch_id: int,
    lead_time_days: Optional[int] = Query(None, ge=1, le=30),
    db: Session = Depends(get_db),
) -> StockoutRiskResult:
    """
    Simulate stockout probability and classify risk category before replenishment arrives.
    """
    _validate_entities_exist(db, product_id, branch_id)
    try:
        return StockoutRiskService.estimate_stockout_risk(
            db=db, product_id=product_id, branch_id=branch_id, lead_time_days=lead_time_days
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/{product_id}/{branch_id}/eoq",
    response_model=EOQResult,
    summary="Calculate Economic Order Quantity with Supplier Constraints",
)
def get_product_branch_eoq(
    product_id: int,
    branch_id: int,
    ordering_cost: float = Query(EOQService.DEFAULT_ORDERING_COST, ge=0.0),
    holding_cost_rate: float = Query(EOQService.DEFAULT_HOLDING_COST_RATE, gt=0.0, le=1.0),
    order_multiple: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
) -> EOQResult:
    """
    Compute optimal unconstrained EOQ and constrained batch size meeting MOQ and packaging multiples.
    """
    _validate_entities_exist(db, product_id, branch_id)
    try:
        return EOQService.calculate_eoq(
            db=db,
            product_id=product_id,
            branch_id=branch_id,
            ordering_cost=ordering_cost,
            holding_cost_rate=holding_cost_rate,
            order_multiple=order_multiple,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/{product_id}/{branch_id}/replenishment",
    response_model=ReplenishmentRecommendation,
    summary="Generate Replenishment Recommendation",
)
def get_product_branch_replenishment(
    product_id: int,
    branch_id: int,
    service_level: float = Query(0.95, ge=0.5, le=0.999),
    ordering_cost: float = Query(EOQService.DEFAULT_ORDERING_COST, ge=0.0),
    holding_cost_rate: float = Query(EOQService.DEFAULT_HOLDING_COST_RATE, gt=0.0, le=1.0),
    order_multiple: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
) -> ReplenishmentRecommendation:
    """
    Produce explainable replenishment recommendation combining inventory position, ROP, risk, and EOQ.
    """
    _validate_entities_exist(db, product_id, branch_id)
    try:
        return ReplenishmentService.generate_recommendation(
            db=db,
            product_id=product_id,
            branch_id=branch_id,
            service_level=service_level,
            ordering_cost=ordering_cost,
            holding_cost_rate=holding_cost_rate,
            order_multiple=order_multiple,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/{product_id}/{branch_id}/decision",
    response_model=InventoryDecisionResult,
    summary="Get Unified Inventory Decision Object",
)
def get_product_branch_unified_decision(
    product_id: int,
    branch_id: int,
    service_level: float = Query(0.95, ge=0.5, le=0.999),
    ordering_cost: float = Query(EOQService.DEFAULT_ORDERING_COST, ge=0.0),
    holding_cost_rate: float = Query(EOQService.DEFAULT_HOLDING_COST_RATE, gt=0.0, le=1.0),
    order_multiple: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
) -> InventoryDecisionResult:
    """
    Execute full unified decision flow synthesizing forecasting, safety stock, ROP, stockout risk, and constrained EOQ.
    """
    _validate_entities_exist(db, product_id, branch_id)
    try:
        return UnifiedInventoryDecisionEngine.evaluate_product_branch(
            db=db,
            product_id=product_id,
            branch_id=branch_id,
            service_level=service_level,
            ordering_cost=ordering_cost,
            holding_cost_rate=holding_cost_rate,
            order_multiple=order_multiple,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/{product_id}/{branch_id}/simulation",
    response_model=PolicySimulationComparison,
    summary="Simulate and Compare Policy for Product-Branch",
)
def get_product_branch_simulation(
    product_id: int,
    branch_id: int,
    start_date: str = Query("2013-12-01"),
    end_date: str = Query("2013-12-31"),
    initial_stock: Optional[int] = Query(None),
    service_level: float = Query(0.95, ge=0.5, le=0.999),
    ordering_cost: float = Query(EOQService.DEFAULT_ORDERING_COST, ge=0.0),
    holding_cost_rate: float = Query(EOQService.DEFAULT_HOLDING_COST_RATE, gt=0.0, le=1.0),
    stockout_penalty_per_unit: Optional[float] = Query(None),
    db: Session = Depends(get_db),
) -> PolicySimulationComparison:
    """
    Simulate daily inventory trajectory over historical demand comparing baseline static vs optimized dynamic policy.
    """
    _validate_entities_exist(db, product_id, branch_id)
    try:
        return InventorySimulationService.simulate_product_branch(
            db=db,
            product_id=product_id,
            branch_id=branch_id,
            start_date=start_date,
            end_date=end_date,
            initial_stock=initial_stock,
            service_level=service_level,
            ordering_cost=ordering_cost,
            holding_cost_rate=holding_cost_rate,
            stockout_penalty_per_unit=stockout_penalty_per_unit,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error during simulation run: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Simulation run failed.")


def _validate_entities_exist(db: Session, product_id: int, branch_id: int) -> None:
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with ID {product_id} not found.")
    branch = db.get(Branch, branch_id)
    if not branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Branch with ID {branch_id} not found.")
