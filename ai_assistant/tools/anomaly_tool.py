"""
Anomaly Detection Tool for SmartDist AI Assistant.
Integrates with AnomalyDetectionService and queries sales_anomalies.
"""

from typing import Dict, Any, List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.app.db.session import SessionLocal
from backend.app.services.anomaly_service import AnomalyDetectionService


class AnomalyDetectionTool:
    """Tool for querying and explaining sales anomalies."""

    name = "anomaly_detection"
    description = "Retrieves sales anomaly runs, high-severity spikes/drops, root cause explanations, and triage status."

    def __init__(self, service: Optional[AnomalyDetectionService] = None):
        self.service = service or AnomalyDetectionService()

    def get_summary(self, db: Optional[Session] = None) -> Dict[str, Any]:
        """Returns anomaly detection health and count summary."""
        active_db = db or SessionLocal()
        close = db is None
        try:
            return self.service.get_summary(db=active_db)
        finally:
            if close:
                active_db.close()

    def get_recent_anomalies(
        self,
        severity: Optional[str] = None,
        limit: int = 10,
        db: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        """Queries recent detected anomalies with root cause explanations."""
        active_db = db or SessionLocal()
        close = db is None
        try:
            where_clause = ""
            params: Dict[str, Any] = {"limit": limit}
            if severity:
                where_clause = "WHERE a.severity = :severity"
                params["severity"] = severity.upper()

            query = text(f"""
                SELECT a.id, a.anomaly_date, b.branch_name, p.product_name,
                       a.direction, a.observed_quantity, a.expected_quantity,
                       a.deviation, a.anomaly_score, a.severity,
                       a.investigation_status, a.explanation, a.recommended_actions
                FROM sales_anomalies a
                JOIN branches b ON a.branch_id = b.id
                JOIN products p ON a.product_id = p.id
                {where_clause}
                ORDER BY a.anomaly_score DESC, a.anomaly_date DESC
                LIMIT :limit
            """)
            result = active_db.execute(query, params)
            return [
                {
                    "anomaly_id": r[0],
                    "date": str(r[1]),
                    "branch_name": r[2],
                    "product_name": r[3],
                    "direction": r[4],
                    "observed_qty": float(r[5]) if r[5] is not None else 0.0,
                    "expected_qty": float(r[6]) if r[6] is not None else 0.0,
                    "deviation": float(r[7]) if r[7] is not None else 0.0,
                    "anomaly_score": float(r[8]) if r[8] is not None else 0.0,
                    "severity": r[9],
                    "status": r[10],
                    "explanation": r[11],
                    "recommended_actions": r[12],
                }
                for r in result.fetchall()
            ]
        finally:
            if close:
                active_db.close()

