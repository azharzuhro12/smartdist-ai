from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.db.base import Base
from backend.app.models.base import TimestampMixin


class DataImportLog(Base, TimestampMixin):
    """
    Audit log tracking dataset ETL ingestion executions, processed volumes, and errors.
    """
    __tablename__ = "data_import_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_file: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    dataset_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    records_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_inserted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_rejected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="STARTED", nullable=False, index=True)
    error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class DataQualityResult(Base, TimestampMixin):
    """
    Execution records of automated data quality and integrity validations.
    """
    __tablename__ = "data_quality_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    validation_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    total_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # PASSED, WARNING, FAILED
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
