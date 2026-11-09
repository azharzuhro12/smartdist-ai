"""
Sales Analytics Tool for SmartDist AI Assistant.
Queries historical sales observations from PostgreSQL daily_sales.
"""

from typing import Dict, Any, List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.app.db.session import SessionLocal


class SalesAnalyticsTool:
    """Tool for querying and analyzing sales transactions."""

    name = "sales_analytics"
    description = "Provides historical sales data, sales volume rankings, revenue estimates, and trend analytics."

    def __init__(self, db: Optional[Session] = None):
        self.db = db

    def get_top_products(self, limit: int = 5, db: Optional[Session] = None) -> List[Dict[str, Any]]:
        """Returns top products by sales volume."""
        active_db = db or self.db or SessionLocal()
        close = db is None and self.db is None
        try:
            query = text("""
                SELECT p.id, p.product_name, c.category_name,
                       ROUND(SUM(s.quantity_sold)::numeric, 2) AS total_units_sold,
                       ROUND(SUM(s.sales_amount)::numeric, 2) AS estimated_revenue
                FROM daily_sales s
                JOIN products p ON s.product_id = p.id
                LEFT JOIN categories c ON p.category_id = c.id
                GROUP BY p.id, p.product_name, c.category_name
                ORDER BY total_units_sold DESC
                LIMIT :limit
            """)
            result = active_db.execute(query, {"limit": limit})
            return [
                {
                    "product_id": r[0],
                    "product_name": r[1],
                    "category": r[2],
                    "units_sold": float(r[3]),
                    "revenue": float(r[4]),
                }
                for r in result.fetchall()
            ]
        finally:
            if close:
                active_db.close()

    def get_branch_performance(self, limit: int = 10, db: Optional[Session] = None) -> List[Dict[str, Any]]:
        """Returns top performing store branches by volume."""
        active_db = db or self.db or SessionLocal()
        close = db is None and self.db is None
        try:
            query = text("""
                SELECT b.id, b.branch_name, b.city, b.state, b.store_type,
                       ROUND(SUM(s.quantity_sold)::numeric, 2) AS total_units_sold,
                       ROUND(SUM(s.sales_amount)::numeric, 2) AS estimated_revenue
                FROM daily_sales s
                JOIN branches b ON s.branch_id = b.id
                GROUP BY b.id, b.branch_name, b.city, b.state, b.store_type
                ORDER BY total_units_sold DESC
                LIMIT :limit
            """)
            result = active_db.execute(query, {"limit": limit})
            return [
                {
                    "branch_id": r[0],
                    "branch_name": r[1],
                    "city": r[2],
                    "state": r[3],
                    "type": r[4],
                    "units_sold": float(r[5]),
                    "revenue": float(r[6]),
                }
                for r in result.fetchall()
            ]
        finally:
            if close:
                active_db.close()

