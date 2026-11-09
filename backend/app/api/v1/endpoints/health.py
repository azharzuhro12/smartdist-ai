from fastapi import APIRouter
from backend.app.core.config import settings
from backend.app.core.redis import check_redis_connection
from backend.app.db.session import check_db_connection
from backend.app.schemas.health import HealthResponse
from backend.app.workers.celery_app import celery_app

router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="API v1 Health Check")
def health_check() -> HealthResponse:
    """
    Check API v1 and upstream infrastructure dependencies (PostgreSQL, Redis, Celery).
    """
    db_ok = check_db_connection()
    redis_ok = check_redis_connection()

    # Check Celery workers availability (non-blocking with short timeout)
    celery_status = "unavailable"
    try:
        if redis_ok:
            # Quick ping to active Celery workers
            inspect = celery_app.control.ping(timeout=0.2)
            if inspect and len(inspect) > 0:
                celery_status = f"active ({len(inspect)} workers)"
            else:
                celery_status = "no workers responding"
    except Exception:
        celery_status = "broker error"

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
            "celery": celery_status,
        },
    )
