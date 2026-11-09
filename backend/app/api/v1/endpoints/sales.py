import math
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.models.business import DailySale
from backend.app.schemas.business import DailySaleResponse, PaginatedResponse

router = APIRouter()


@router.get("/daily", response_model=PaginatedResponse[DailySaleResponse], summary="List Daily Sales")
def list_daily_sales(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    branch_id: Optional[int] = Query(None, description="Filter by branch ID"),
    product_id: Optional[int] = Query(None, description="Filter by product ID"),
    start_date: Optional[date] = Query(None, description="Filter starting date YYYY-MM-DD"),
    end_date: Optional[date] = Query(None, description="Filter ending date YYYY-MM-DD"),
    db: Session = Depends(get_db),
) -> PaginatedResponse[DailySaleResponse]:
    """
    List daily sales transactions with pagination, branch, product, and temporal filters.
    """
    query = select(DailySale)
    if branch_id:
        query = query.where(DailySale.branch_id == branch_id)
    if product_id:
        query = query.where(DailySale.product_id == product_id)
    if start_date:
        query = query.where(DailySale.sale_date >= start_date)
    if end_date:
        query = query.where(DailySale.sale_date <= end_date)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    pages = math.ceil(total / size) if total > 0 else 1

    items = (
        db.execute(
            query.order_by(DailySale.sale_date.desc(), DailySale.id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        .scalars()
        .all()
    )

    return PaginatedResponse(
        items=list(items),
        total=total,
        page=page,
        size=size,
        pages=pages,
    )
