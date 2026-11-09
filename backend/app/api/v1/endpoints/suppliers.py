import math
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.models.business import Supplier
from backend.app.schemas.business import PaginatedResponse, SupplierResponse

router = APIRouter()


@router.get("", response_model=PaginatedResponse[SupplierResponse], summary="List Suppliers")
def list_suppliers(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedResponse[SupplierResponse]:
    """
    List merchandise suppliers and distribution partners.
    """
    query = select(Supplier)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    pages = math.ceil(total / size) if total > 0 else 1

    items = db.execute(query.order_by(Supplier.id).offset((page - 1) * size).limit(size)).scalars().all()

    return PaginatedResponse(
        items=list(items),
        total=total,
        page=page,
        size=size,
        pages=pages,
    )
