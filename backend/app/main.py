from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.app.api.v1.router import api_router
from backend.app.core.config import settings
from backend.app.core.logging import logger, setup_logging
from backend.app.core.redis import close_redis_pool
from backend.app.schemas.health import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown event handling.
    """
    setup_logging(log_level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)
    logger.info(
        f"Starting {settings.PROJECT_NAME} v{settings.PROJECT_VERSION} in {settings.ENVIRONMENT} mode."
    )
    yield
    logger.info(f"Shutting down {settings.PROJECT_NAME}...")
    close_redis_pool()
    logger.info("Shutdown completed successfully.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="Intelligent Distribution & Retail Management System - Core Backend API",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

# Configure CORS Middleware
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        f"Unhandled exception occurred processing {request.method} {request.url.path}: {str(exc)}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please contact the system administrator.",
        },
    )


# Root health endpoint
@app.get("/health", response_model=HealthResponse, tags=["Health"], summary="Root Health Check")
def root_health():
    """
    Basic health check verifying the application process is running and responsive.
    """
    return HealthResponse(
        status="healthy",
        app_name=settings.PROJECT_NAME,
        version=settings.PROJECT_VERSION,
        environment=settings.ENVIRONMENT,
        services={"app": "running"},
    )


# Mount Versioned API Routers
app.include_router(api_router, prefix=settings.API_V1_STR)
