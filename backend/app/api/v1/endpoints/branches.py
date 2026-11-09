import math
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.models.business import Branch
from backend.app.schemas.business import BranchResponse, PaginatedResponse

router = APIRouter()


@router.get("", response_model=PaginatedResponse[BranchResponse], summary="List Retail Branches")
def list_branches(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    city: Optional[str] = Query(None, description="Filter by city name"),
    state: Optional[str] = Query(None, description="Filter by state name"),
    db: Session = Depends(get_db),
) -> PaginatedResponse[BranchResponse]:
    """
    List retail branch stores with pagination and location filters.
    """
    query = select(Branch)
    if city:
        query = query.where(Branch.city.ilike(f"%{city.strip()}%"))
    if state:
        query = query.where(Branch.state.ilike(f"%{state.strip()}%"))

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    pages = math.ceil(total / size) if total > 0 else 1

    items = db.execute(query.order_by(Branch.source_store_number).offset((page - 1) * size).limit(size)).scalars().all()

    return PaginatedResponse(
        items=list(items),
        total=total,
        page=page,
        size=size,
        pages=pages,
    )
