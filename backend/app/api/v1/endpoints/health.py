from fastapi import APIRouter
from backend.app.core.config import settings
from backend.app.core.redis import check_redis_connection
from backend.app.db.session import check_db_connection
from backend.app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="API v1 Health Check")
def health_check() -> HealthResponse:
    """
    Check API v1 and upstream infrastructure dependencies (PostgreSQL, Redis).
    """
    db_ok = check_db_connection()
    redis_ok = check_redis_connection()

    if db_ok and redis_ok:
        overall_status = "healthy"
    elif db_ok or redis_ok:
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"

    return HealthResponse(
        status=overall_status,
        app_name=settings.PROJECT_NAME,
        version=settings.PROJECT_VERSION,
        environment=settings.ENVIRONMENT,
        services={
            "database": "connected" if db_ok else "disconnected",
            "redis": "connected" if redis_ok else "disconnected",
        },
    )
