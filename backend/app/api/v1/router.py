from fastapi import APIRouter, Depends
from backend.app.api.deps import require_viewer
from backend.app.api.v1.endpoints import (
    anomalies,
    assistant,
    auth,
    branches,
    data,
    health,
    inventory,
    products,
    sales,
    suppliers,
    users,
)

api_router = APIRouter()

# Public / Authentication Endpoints
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# Administrative User Management (ADMIN only)
api_router.include_router(users.router, prefix="/users", tags=["User Administration"])

# Protected Business Domain Endpoints (Requires at least VIEWER role)
api_router.include_router(data.router, prefix="/data", tags=["Data Engineering & ETL"], dependencies=[Depends(require_viewer)])
api_router.include_router(products.router, prefix="/products", tags=["Products"], dependencies=[Depends(require_viewer)])
api_router.include_router(branches.router, prefix="/branches", tags=["Branches"], dependencies=[Depends(require_viewer)])
api_router.include_router(sales.router, prefix="/sales", tags=["Sales"], dependencies=[Depends(require_viewer)])
api_router.include_router(inventory.router, prefix="/inventory", tags=["Inventory"], dependencies=[Depends(require_viewer)])
api_router.include_router(suppliers.router, prefix="/suppliers", tags=["Suppliers"], dependencies=[Depends(require_viewer)])
api_router.include_router(anomalies.router, prefix="/anomalies", tags=["Anomaly Detection"], dependencies=[Depends(require_viewer)])
api_router.include_router(assistant.router, prefix="/assistant", tags=["AI Business Assistant"], dependencies=[Depends(require_viewer)])
