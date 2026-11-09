import math
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.models.business import Product
from backend.app.schemas.business import PaginatedResponse, ProductResponse

router = APIRouter()


@router.get("", response_model=PaginatedResponse[ProductResponse], summary="List Products")
def list_products(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    search: Optional[str] = Query(None, description="Search product name or SKU"),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ProductResponse]:
    """
    List master product catalog with pagination, search, and category filtering.
    """
    query = select(Product)
    if category_id:
        query = query.where(Product.category_id == category_id)
    if search:
        search_fmt = f"%{search.strip()}%"
        query = query.where(Product.product_name.ilike(search_fmt) | Product.product_code.ilike(search_fmt))

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    pages = math.ceil(total / size) if total > 0 else 1

    items = db.execute(query.order_by(Product.id).offset((page - 1) * size).limit(size)).scalars().all()

    return PaginatedResponse(
        items=list(items),
        total=total,
        page=page,
        size=size,
        pages=pages,
    )
