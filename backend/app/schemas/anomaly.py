from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from ml.anomaly_detection.hybrid_scorer import AnomalyDirection, AnomalySeverity


class AnomalyDetectRequest(BaseModel):
    """
    Request payload to trigger an anomaly detection run.
    """
    model_config = ConfigDict(from_attributes=True)

    start_date: str = Field(..., description="Start date of detection window (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date of detection window (YYYY-MM-DD)")
    branch_id: Optional[int] = Field(None, description="Optional specific branch ID filter")
    product_id: Optional[int] = Field(None, description="Optional specific product ID filter")
    sensitivity: float = Field(1.0, ge=0.5, le=2.0, description="Multiplier for anomaly score thresholds")
    weights: Optional[Dict[str, float]] = Field(None, description="Custom weights for statistical, forecast, and ml detectors")
    async_mode: bool = Field(False, description="Whether to execute as an asynchronous Celery background task")


class AnomalyItemResponse(BaseModel):
    """
    Detailed detected anomaly representation.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    detection_run_id: Optional[int] = None
    anomaly_date: str
    branch_id: int
    branch_name: Optional[str] = None
    product_id: int
    product_name: Optional[str] = None
    category_name: Optional[str] = None
    observed_quantity: float
    expected_quantity: float
    deviation: float
    percentage_deviation: float
    anomaly_score: float
    severity: str
    direction: str
    detector_evidence: Dict[str, Any]
    explanation: str
    recommended_actions: List[str]
    investigation_status: str
    resolution_note: Optional[str] = None
    data_provenance: str
    created_at: datetime


class AnomalyListResponse(BaseModel):
    """
    Paginated list of detected anomalies.
    """
    model_config = ConfigDict(from_attributes=True)

    items: List[AnomalyItemResponse]
    total: int
    page: int
    size: int
    pages: int


class AnomalySummaryResponse(BaseModel):
    """
    High-level aggregate summary of anomalies across network.
    """
    model_config = ConfigDict(from_attributes=True)

    total_anomalies: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    spikes_count: int
    drops_count: int
    zero_sales_count: int
    forecast_deviations_count: int
    affected_branches_count: int
    affected_products_count: int
    status_breakdown: Dict[str, int]
    severity_breakdown: Dict[str, int]
    date_trend: List[Dict[str, Any]]
    data_provenance: str = "KAGGLE_PUBLIC"
    generated_at: datetime


class AnomalyStatusUpdateRequest(BaseModel):
    """
    Request to update operational investigation status.
    """
    status: str = Field(..., description="NEW, INVESTIGATING, CONFIRMED, FALSE_POSITIVE, RESOLVED")
    resolution_note: Optional[str] = Field(None, description="Optional operational investigation or resolution note")


class AnomalyRunStatusResponse(BaseModel):
    """
    Status of an anomaly detection batch run.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    detection_window_start: Optional[str] = None
    detection_window_end: Optional[str] = None
    total_observations: int
    anomalies_detected: int
    model_version: str
    error_message: Optional[str] = None
