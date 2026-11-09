from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import (
    String,
    Numeric,
    Integer,
    BigInteger,
    ForeignKey,
    Text,
    Date,
    DateTime,
    UniqueConstraint,
    CheckConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base
from backend.app.models.base import TimestampMixin


class AnomalyDetectionRun(Base, TimestampMixin):
    """
    Log of executed anomaly detection batch runs.
    """
    __tablename__ = "anomaly_detection_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="RUNNING", nullable=False, index=True)
    detection_window_start: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    detection_window_end: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    branch_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    product_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True)
    detector_configuration: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    model_version: Mapped[str] = mapped_column(String(50), default="v1", nullable=False)
    total_observations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    anomalies_detected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    data_provenance: Mapped[str] = mapped_column(String(50), default="KAGGLE_PUBLIC", nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    anomalies: Mapped[List["SalesAnomaly"]] = relationship("SalesAnomaly", back_populates="run", cascade="all, delete-orphan")


class SalesAnomaly(Base, TimestampMixin):
    """
    Detected sales anomalies across branches and products with complete detector evidence.
    """
    __tablename__ = "sales_anomalies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    detection_run_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("anomaly_detection_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    anomaly_date: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    branch_id: Mapped[int] = mapped_column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    observed_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    expected_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    deviation: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    percentage_deviation: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.0"), nullable=False)
    anomaly_score: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # NORMAL, LOW, MEDIUM, HIGH, CRITICAL
    direction: Mapped[str] = mapped_column(String(30), nullable=False, index=True) # SPIKE, DROP, ZERO_SALES, FORECAST_DEVIATION, etc.
    detector_evidence: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_actions: Mapped[List[str]] = mapped_column(JSONB, nullable=False)
    investigation_status: Mapped[str] = mapped_column(String(30), default="NEW", nullable=False, index=True) # NEW, INVESTIGATING, CONFIRMED, FALSE_POSITIVE, RESOLVED
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    data_provenance: Mapped[str] = mapped_column(String(50), default="KAGGLE_PUBLIC", nullable=False)

    # Relationships
    run: Mapped[Optional["AnomalyDetectionRun"]] = relationship("AnomalyDetectionRun", back_populates="anomalies")
    branch: Mapped["Branch"] = relationship("Branch")
    product: Mapped["Product"] = relationship("Product")

    __table_args__ = (
        UniqueConstraint("anomaly_date", "branch_id", "product_id", name="uq_sales_anomaly_date_branch_product"),
        Index("ix_sales_anomalies_date_branch", "anomaly_date", "branch_id"),
        Index("ix_sales_anomalies_severity_status", "severity", "investigation_status"),
    )
