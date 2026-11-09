from datetime import datetime, timezone
from typing import Dict, Literal
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        ..., description="Overall health status of the application"
    )
    app_name: str = Field(..., description="Application name")
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Current running environment")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Current UTC timestamp",
    )
    services: Dict[str, str] = Field(
        default_factory=dict,
        description="Health status of external services (db, redis)",
    )
