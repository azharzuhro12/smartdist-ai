"""
Safe SQL Executor for SmartDist AI.
Executes pre-validated read-only queries with strict timeout, row limits, and connection scoping.
"""

import time
from decimal import Decimal
from datetime import date, datetime
from typing import Dict, List, Any, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import ResourceClosedError

from backend.app.db.session import SessionLocal, ReadOnlySessionLocal
from ai_assistant.sql_agent.sql_validator import SQLValidator


class SQLExecutionError(Exception):
    """Raised when an SQL query fails during database execution."""
    pass


def serialize_value(val: Any) -> Any:
    """Helper to ensure all database values serialize cleanly to JSON."""
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (date, datetime)):
        return val.isoformat()
    return val


def determine_provenance(sql: str) -> str:
    """Determines data provenance based on queried tables."""
    sql_lower = sql.lower()
    if "daily_sales" in sql_lower:
        return "KAGGLE_PUBLIC (Ecuadorian Grocery Sales 2013)"
    elif "sales_anomalies" in sql_lower or "anomaly_detection_runs" in sql_lower:
        return "MODEL_GENERATED (Phase 4.1 Anomaly Detection Ensemble)"
    elif "inventory" in sql_lower:
        return "SYNTHETIC (Phase 2 Enterprise Stock Baseline)"
    else:
        return "ENTERPRISE_DB (Master Business Entities)"


class SafeSQLExecutor:
    """Safely executes validated SELECT queries with timeouts and read-only transactions."""

    def __init__(self, validator: Optional[SQLValidator] = None, timeout_ms: int = 5000):
        self.validator = validator or SQLValidator()
        self.timeout_ms = timeout_ms

    def execute_query(self, raw_sql: str, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Validates, sanitizes, and executes a read-only SQL query.
        Returns execution result dictionary.
        """
        # 1. Validate query
        sanitized_sql = self.validator.validate_and_sanitize(raw_sql)

        # 2. Execute within managed session
        start_time = time.perf_counter()
        close_session = False
        if db is not None:
            session = db
        else:
            try:
                session = ReadOnlySessionLocal()
            except Exception:
                session = SessionLocal()
            close_session = True

        try:
            # Set statement timeout and engine-level read-only transaction mode for safety
            session.execute(text(f"SET LOCAL statement_timeout = '{self.timeout_ms}ms'"))
            session.execute(text("SET LOCAL transaction_read_only = on"))
            
            result_proxy = session.execute(text(sanitized_sql))
            try:
                columns = list(result_proxy.keys())
                raw_rows = result_proxy.fetchall()
            except ResourceClosedError:
                columns = []
                raw_rows = []

            # Format rows
            rows = []
            for row in raw_rows:
                row_dict = {}
                for idx, col_name in enumerate(columns):
                    row_dict[col_name] = serialize_value(row[idx])
                rows.append(row_dict)

            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            provenance = determine_provenance(sanitized_sql)

            return {
                "success": True,
                "sql": sanitized_sql,
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "execution_time_ms": elapsed_ms,
                "provenance": provenance,
            }

        except Exception as e:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            raise SQLExecutionError(f"Database execution failed: {str(e)}") from e

        finally:
            try:
                session.rollback()
            except Exception:
                pass
            if close_session:
                session.close()

