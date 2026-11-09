from fastapi import APIRouter
from backend.app.api.v1.endpoints import (
    anomalies,
    branches,
    data,
    health,
    inventory,
    products,
    sales,
    suppliers,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(data.router, prefix="/data", tags=["Data Engineering & ETL"])
api_router.include_router(products.router, prefix="/products", tags=["Products"])
api_router.include_router(branches.router, prefix="/branches", tags=["Branches"])
api_router.include_router(sales.router, prefix="/sales", tags=["Sales"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["Inventory"])
api_router.include_router(suppliers.router, prefix="/suppliers", tags=["Suppliers"])
api_router.include_router(anomalies.router, prefix="/anomalies", tags=["Anomaly Detection"])
