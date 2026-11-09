import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.app.api.deps import require_admin, require_analyst
from backend.app.models.user import User
from backend.app.db.session import get_db
from backend.app.models.anomaly import AnomalyDetectionRun, SalesAnomaly
from backend.app.schemas.anomaly import (
    AnomalyDetectRequest,
    AnomalyItemResponse,
    AnomalyListResponse,
    AnomalyRunStatusResponse,
    AnomalyStatusUpdateRequest,
    AnomalySummaryResponse,
)
from backend.app.services.anomaly_service import AnomalyDetectionService

router = APIRouter()


@router.post(
    "/detect",
    response_model=AnomalyRunStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Sales Anomaly Detection",
    description="Run multi-detector anomaly evaluation over historical sales. Supports synchronous or asynchronous (Celery) mode.",
)
def detect_anomalies(
    payload: AnomalyDetectRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if payload.start_date > payload.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"start_date ({payload.start_date}) cannot be greater than end_date ({payload.end_date}).",
        )

    if payload.async_mode:
        from backend.app.workers.tasks import detect_sales_anomalies
        task = detect_sales_anomalies.delay(
            start_date=payload.start_date,
            end_date=payload.end_date,
            branch_id=payload.branch_id,
            product_id=payload.product_id,
            sensitivity=payload.sensitivity,
            weights=payload.weights,
        )
        return AnomalyRunStatusResponse(
            id=0,
            status=f"PENDING_CELERY_TASK_{task.id}",
            started_at=func.now(),
            detection_window_start=payload.start_date,
            detection_window_end=payload.end_date,
            total_observations=0,
            anomalies_detected=0,
            model_version="v1",
        )

    try:
        run = AnomalyDetectionService.execute_detection_run(
            db=db,
            start_date=payload.start_date,
            end_date=payload.end_date,
            branch_id=payload.branch_id,
            product_id=payload.product_id,
            sensitivity=payload.sensitivity,
            custom_weights=payload.weights,
        )
        return AnomalyRunStatusResponse(
            id=run.id,
            status=run.status,
            started_at=run.started_at,
            completed_at=run.completed_at,
            detection_window_start=run.detection_window_start,
            detection_window_end=run.detection_window_end,
            total_observations=run.total_observations,
            anomalies_detected=run.anomalies_detected,
            model_version=run.model_version,
            error_message=run.error_message,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Anomaly detection execution failed: {str(e)}",
        )


@router.get(
    "/runs/{run_id}",
    response_model=AnomalyRunStatusResponse,
    summary="Get Anomaly Detection Run Status",
)
def get_run_status(
    run_id: int,
    db: Session = Depends(get_db),
):
    run = db.get(AnomalyDetectionRun, run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Anomaly detection run {run_id} not found.",
        )
    return AnomalyRunStatusResponse(
        id=run.id,
        status=run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        detection_window_start=run.detection_window_start,
        detection_window_end=run.detection_window_end,
        total_observations=run.total_observations,
        anomalies_detected=run.anomalies_detected,
        model_version=run.model_version,
        error_message=run.error_message,
    )


@router.get(
    "/summary",
    response_model=AnomalySummaryResponse,
    summary="Get Network Anomaly Summary",
    description="Aggregate metrics on anomaly counts, severity breakdown, and date trends.",
)
def get_anomaly_summary(
    db: Session = Depends(get_db),
):
    summary_data = AnomalyDetectionService.get_summary(db)
    return AnomalySummaryResponse(**summary_data)


@router.get(
    "",
    response_model=AnomalyListResponse,
    summary="List Detected Anomalies",
    description="Query detected sales anomalies with multi-criteria filtering and pagination.",
)
def list_anomalies(
    branch_id: Optional[int] = Query(None, description="Filter by branch ID"),
    product_id: Optional[int] = Query(None, description="Filter by product ID"),
    severity: Optional[str] = Query(None, description="NORMAL, LOW, MEDIUM, HIGH, CRITICAL"),
    direction: Optional[str] = Query(None, description="SPIKE, DROP, ZERO_SALES, FORECAST_DEVIATION"),
    status: Optional[str] = Query(None, description="NEW, INVESTIGATING, CONFIRMED, FALSE_POSITIVE, RESOLVED"),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = select(SalesAnomaly)

    if branch_id:
        query = query.where(SalesAnomaly.branch_id == branch_id)
    if product_id:
        query = query.where(SalesAnomaly.product_id == product_id)
    if severity:
        query = query.where(SalesAnomaly.severity == severity.upper())
    if direction:
        query = query.where(SalesAnomaly.direction == direction.upper())
    if status:
        query = query.where(SalesAnomaly.investigation_status == status.upper())
    if start_date:
        query = query.where(SalesAnomaly.anomaly_date >= start_date)
    if end_date:
        query = query.where(SalesAnomaly.anomaly_date <= end_date)

    # Total count
    total_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(total_query) or 0

    # Paginated results ordered by date desc, severity score desc
    query = query.order_by(SalesAnomaly.anomaly_date.desc(), SalesAnomaly.anomaly_score.desc())
    query = query.offset((page - 1) * size).limit(size)
    records = db.execute(query).scalars().all()

    items = []
    for r in records:
        items.append(
            AnomalyItemResponse(
                id=r.id,
                detection_run_id=r.detection_run_id,
                anomaly_date=r.anomaly_date,
                branch_id=r.branch_id,
                branch_name=r.branch.branch_name if r.branch else None,
                product_id=r.product_id,
                product_name=r.product.product_name if r.product else None,
                category_name=r.product.category.category_name if (r.product and r.product.category) else None,
                observed_quantity=float(r.observed_quantity),
                expected_quantity=float(r.expected_quantity),
                deviation=float(r.deviation),
                percentage_deviation=float(r.percentage_deviation),
                anomaly_score=float(r.anomaly_score),
                severity=r.severity,
                direction=r.direction,
                detector_evidence=r.detector_evidence,
                explanation=r.explanation,
                recommended_actions=r.recommended_actions,
                investigation_status=r.investigation_status,
                resolution_note=r.resolution_note,
                data_provenance=r.data_provenance,
                created_at=r.created_at,
            )
        )

    pages = math.ceil(total / size) if total > 0 else 0
    return AnomalyListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get(
    "/{anomaly_id}",
    response_model=AnomalyItemResponse,
    summary="Get Anomaly Details",
)
def get_anomaly_detail(
    anomaly_id: int,
    db: Session = Depends(get_db),
):
    r = db.get(SalesAnomaly, anomaly_id)
    if not r:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sales anomaly with ID {anomaly_id} not found.",
        )
    return AnomalyItemResponse(
        id=r.id,
        detection_run_id=r.detection_run_id,
        anomaly_date=r.anomaly_date,
        branch_id=r.branch_id,
        branch_name=r.branch.branch_name if r.branch else None,
        product_id=r.product_id,
        product_name=r.product.product_name if r.product else None,
        category_name=r.product.category.category_name if (r.product and r.product.category) else None,
        observed_quantity=float(r.observed_quantity),
        expected_quantity=float(r.expected_quantity),
        deviation=float(r.deviation),
        percentage_deviation=float(r.percentage_deviation),
        anomaly_score=float(r.anomaly_score),
        severity=r.severity,
        direction=r.direction,
        detector_evidence=r.detector_evidence,
        explanation=r.explanation,
        recommended_actions=r.recommended_actions,
        investigation_status=r.investigation_status,
        resolution_note=r.resolution_note,
        data_provenance=r.data_provenance,
        created_at=r.created_at,
    )


@router.patch(
    "/{anomaly_id}/status",
    response_model=AnomalyItemResponse,
    summary="Update Investigation Workflow Status",
    description="Transitions anomaly through operational lifecycle: NEW -> INVESTIGATING -> CONFIRMED / FALSE_POSITIVE -> RESOLVED",
)
def update_anomaly_status(
    anomaly_id: int,
    payload: AnomalyStatusUpdateRequest,
    db: Session = Depends(get_db),
    analyst: User = Depends(require_analyst),
):
    valid_statuses = {"NEW", "INVESTIGATING", "CONFIRMED", "FALSE_POSITIVE", "RESOLVED"}
    target_status = payload.status.upper()
    if target_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid investigation status: '{payload.status}'. Allowed: {sorted(list(valid_statuses))}",
        )

    anomaly = db.get(SalesAnomaly, anomaly_id)
    if not anomaly:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sales anomaly {anomaly_id} not found.",
        )

    anomaly.investigation_status = target_status
    if payload.resolution_note is not None:
        anomaly.resolution_note = payload.resolution_note

    db.commit()
    db.refresh(anomaly)

    return AnomalyItemResponse(
        id=anomaly.id,
        detection_run_id=anomaly.detection_run_id,
        anomaly_date=anomaly.anomaly_date,
        branch_id=anomaly.branch_id,
        branch_name=anomaly.branch.branch_name if anomaly.branch else None,
        product_id=anomaly.product_id,
        product_name=anomaly.product.product_name if anomaly.product else None,
        category_name=anomaly.product.category.category_name if (anomaly.product and anomaly.product.category) else None,
        observed_quantity=float(anomaly.observed_quantity),
        expected_quantity=float(anomaly.expected_quantity),
        deviation=float(anomaly.deviation),
        percentage_deviation=float(anomaly.percentage_deviation),
        anomaly_score=float(anomaly.anomaly_score),
        severity=anomaly.severity,
        direction=anomaly.direction,
        detector_evidence=anomaly.detector_evidence,
        explanation=anomaly.explanation,
        recommended_actions=anomaly.recommended_actions,
        investigation_status=anomaly.investigation_status,
        resolution_note=anomaly.resolution_note,
        data_provenance=anomaly.data_provenance,
        created_at=anomaly.created_at,
    )
