import math
from typing import List, Optional
from celery.result import AsyncResult
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from backend.app.core.logging import logger
from backend.app.db.session import get_db
from backend.app.models.audit import DataQualityResult
from backend.app.schemas.business import (
    DataQualityItemResponse,
    DataSummaryResponse,
    ImportRequest,
    ImportResponse,
    TaskStatusResponse,
)
from backend.app.services.etl_service import ETLService
from backend.app.workers.tasks import import_sales_dataset

router = APIRouter()


@router.get("/summary", response_model=DataSummaryResponse, summary="Get Data Engineering Summary")
def get_data_summary(db: Session = Depends(get_db)) -> DataSummaryResponse:
    """
    Returns high-level statistics across all stored retail, catalog, sales, and inventory data.
    """
    stats = ETLService.get_summary(db)
    return DataSummaryResponse(**stats)


@router.get("/quality", response_model=List[DataQualityItemResponse], summary="Get Data Quality Reports")
def get_data_quality_reports(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> List[DataQualityItemResponse]:
    """
    Fetch historical execution reports for dataset quality and constraint checks.
    """
    stmt = select(DataQualityResult).order_by(desc(DataQualityResult.executed_at)).limit(limit)
    results = db.execute(stmt).scalars().all()
    return list(results)


@router.post("/import", response_model=ImportResponse, status_code=status.HTTP_202_ACCEPTED, summary="Trigger Data Ingestion")
def trigger_data_import(
    request: ImportRequest,
) -> ImportResponse:
    """
    Triggers the asynchronous ETL ingestion pipeline for stores, catalog, sales, and synthetic inventory.
    """
    logger.info(f"Triggering asynchronous dataset ingestion task: {request}")
    task = import_sales_dataset.delay(
        max_sales_rows=request.max_sales_rows,
        start_date=request.start_date,
        end_date=request.end_date,
    )
    return ImportResponse(
        message="Data import task dispatched successfully.",
        task_id=task.id,
        status="PENDING",
    )


@router.get("/import/{task_id}", response_model=TaskStatusResponse, summary="Check Import Task Status")
def get_import_task_status(task_id: str) -> TaskStatusResponse:
    """
    Check the current status and payload result of a dispatched background ETL task.
    """
    async_res = AsyncResult(task_id)
    result_data = None
    if async_res.ready():
        result_data = async_res.result

    return TaskStatusResponse(
        task_id=task_id,
        status=async_res.status,
        result=result_data,
    )
