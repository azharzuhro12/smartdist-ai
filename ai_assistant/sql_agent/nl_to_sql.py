"""
Natural Language to SQL translator for SmartDist AI.
Translates domain queries to SQL using rule-based/pattern mapping with LLM-readiness,
and executes via SafeSQLExecutor.
"""

import re
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from ai_assistant.sql_agent.sql_validator import SQLValidator
from ai_assistant.sql_agent.sql_executor import SafeSQLExecutor


class NLToSQLAgent:
    """Translates natural language questions to safe SQL queries and executes them."""

    def __init__(self, executor: Optional[SafeSQLExecutor] = None):
        self.executor = executor or SafeSQLExecutor()
        self.validator = self.executor.validator

    def generate_sql(self, question: str) -> str:
        """
        Translates a natural language question into an SQL query.
        Uses robust semantic pattern recognition for distribution & retail analytics.
        """
        q = question.lower().strip()

        # Pattern 1: Top selling products (by volume or revenue)
        if "top" in q and ("product" in q or "family" in q or "item" in q or "selling" in q):
            limit = 10
            limit_match = re.search(r"\btop\s+(\d+)\b", q)
            if limit_match:
                limit = min(int(limit_match.group(1)), 50)

            if "revenue" in q or "amount" in q or "dollar" in q:
                return (
                    f"SELECT p.id, p.product_name, c.category_name, "
                    f"ROUND(SUM(s.sales_amount)::numeric, 2) AS total_estimated_revenue, "
                    f"ROUND(SUM(s.quantity_sold)::numeric, 2) AS total_quantity_sold, "
                    f"ROUND(SUM(s.quantity_sold)::numeric, 2) AS total_units_sold "
                    f"FROM daily_sales s "
                    f"JOIN products p ON s.product_id = p.id "
                    f"LEFT JOIN categories c ON p.category_id = c.id "
                    f"GROUP BY p.id, p.product_name, c.category_name "
                    f"ORDER BY total_estimated_revenue DESC "
                    f"LIMIT {limit}"
                )
            else:
                return (
                    f"SELECT p.id, p.product_name, c.category_name, "
                    f"ROUND(SUM(s.quantity_sold)::numeric, 2) AS total_quantity_sold, "
                    f"ROUND(SUM(s.sales_amount)::numeric, 2) AS total_estimated_revenue "
                    f"FROM daily_sales s "
                    f"JOIN products p ON s.product_id = p.id "
                    f"LEFT JOIN categories c ON p.category_id = c.id "
                    f"GROUP BY p.id, p.product_name, c.category_name "
                    f"ORDER BY total_quantity_sold DESC "
                    f"LIMIT {limit}"
                )

        # Pattern 2: Sales by branch / store rankings
        if ("branch" in q or "store" in q) and ("sales" in q or "rank" in q or "volume" in q or "performance" in q):
            return (
                "SELECT b.id, b.branch_name, b.city, b.state, b.store_type, "
                "ROUND(SUM(s.quantity_sold)::numeric, 2) AS total_quantity_sold, "
                "ROUND(SUM(s.sales_amount)::numeric, 2) AS total_estimated_revenue "
                "FROM daily_sales s "
                "JOIN branches b ON s.branch_id = b.id "
                "GROUP BY b.id, b.branch_name, b.city, b.state, b.store_type "
                "ORDER BY total_quantity_sold DESC "
                "LIMIT 54"
            )

        # Pattern 3: Low stock / stockout risk / inventory shortage
        if ("low stock" in q or "shortage" in q or "out of stock" in q or "stockout" in q or 
            ("inventory" in q and ("risk" in q or "level" in q or "reorder" in q or "below" in q))):
            return (
                "SELECT p.product_name, w.warehouse_name, "
                "i.stock_quantity, i.reserved_quantity, i.safety_stock, i.reorder_point, "
                "ROUND((i.reorder_point - i.stock_quantity)::numeric, 2) AS deficit "
                "FROM inventory i "
                "JOIN products p ON i.product_id = p.id "
                "JOIN warehouses w ON i.warehouse_id = w.id "
                "WHERE i.stock_quantity <= i.reorder_point "
                "ORDER BY deficit DESC "
                "LIMIT 50"
            )

        # Pattern 4: Sales anomalies (critical, spike, drop, recent)
        if "anomal" in q:
            status_filter = ""
            if "critical" in q:
                status_filter = "WHERE a.severity = 'CRITICAL'"
            elif "spike" in q:
                status_filter = "WHERE a.direction = 'SPIKE'"
            elif "drop" in q:
                status_filter = "WHERE a.direction = 'DROP'"
            elif "unresolved" in q or "detected" in q or "new" in q:
                status_filter = "WHERE a.investigation_status IN ('NEW', 'INVESTIGATING')"

            return (
                f"SELECT a.id, a.anomaly_date, b.branch_name, p.product_name, "
                f"a.direction, ROUND(a.observed_quantity::numeric, 2) AS observed_qty, "
                f"ROUND(a.expected_quantity::numeric, 2) AS expected_qty, "
                f"ROUND(a.anomaly_score::numeric, 4) AS anomaly_score, a.severity, "
                f"a.investigation_status, a.explanation "
                f"FROM sales_anomalies a "
                f"JOIN branches b ON a.branch_id = b.id "
                f"JOIN products p ON a.product_id = p.id "
                f"{status_filter} "
                f"ORDER BY a.anomaly_score DESC, a.anomaly_date DESC "
                f"LIMIT 30"
            )

        # Pattern 5: Suppliers and lead times
        if "supplier" in q or "vendor" in q or "lead time" in q:
            return (
                "SELECT s.id, s.supplier_name, s.supplier_code, "
                "s.lead_time_days, s.minimum_order_quantity "
                "FROM suppliers s "
                "ORDER BY s.lead_time_days DESC "
                "LIMIT 25"
            )

        # Pattern 6: Category sales breakdown
        if "category" in q and ("sales" in q or "performance" in q or "volume" in q or "breakdown" in q):
            return (
                "SELECT c.id, c.category_name, "
                "ROUND(SUM(s.quantity_sold)::numeric, 2) AS total_quantity_sold, "
                "ROUND(SUM(s.sales_amount)::numeric, 2) AS total_estimated_revenue "
                "FROM daily_sales s "
                "JOIN products p ON s.product_id = p.id "
                "JOIN categories c ON p.category_id = c.id "
                "GROUP BY c.id, c.category_name "
                "ORDER BY total_quantity_sold DESC "
                "LIMIT 20"
            )

        # Pattern 7: Warehouse inventory overview
        if "warehouse" in q and ("inventory" in q or "capacity" in q or "stock" in q):
            return (
                "SELECT w.id, w.warehouse_name, w.warehouse_code, "
                "COALESCE(SUM(i.stock_quantity), 0) AS total_units_in_stock, "
                "COALESCE(SUM(i.reserved_quantity), 0) AS total_units_reserved "
                "FROM warehouses w "
                "LEFT JOIN inventory i ON w.id = i.warehouse_id "
                "GROUP BY w.id, w.warehouse_name, w.warehouse_code "
                "ORDER BY total_units_in_stock DESC "
                "LIMIT 25"
            )

        # Default fallback: recent sales overview
        return (
            "SELECT s.sale_date, b.branch_name, p.product_name, "
            "s.quantity_sold, s.sales_amount, s.promotion_quantity "
            "FROM daily_sales s "
            "JOIN branches b ON s.branch_id = b.id "
            "JOIN products p ON s.product_id = p.id "
            "ORDER BY s.sale_date DESC, s.quantity_sold DESC "
            "LIMIT 25"
        )

    def query(self, natural_language: str, db: Optional[Session] = None) -> Dict[str, Any]:
        """Translates natural language to SQL, validates it, and executes it."""
        # Check if the query is a direct SQL string or raw injection attempt
        nl_clean = natural_language.strip()
        nl_upper = nl_clean.upper()
        raw_sql_triggers = ["SELECT ", "DROP ", "DELETE ", "INSERT ", "UPDATE ", "TRUNCATE ", "ALTER ", "--", "/*", ";"]
        
        if any(trigger in nl_upper for trigger in raw_sql_triggers):
            # Validate directly as SQL (this will reject attacks like DROP, DELETE, comments, etc.)
            sanitized_sql = self.validator.validate_and_sanitize(nl_clean)
            result = self.executor.execute_query(sanitized_sql, db=db)
            result["natural_language_query"] = natural_language
            return result

        generated_sql = self.generate_sql(natural_language)
        result = self.executor.execute_query(generated_sql, db=db)
        result["natural_language_query"] = natural_language
        return result
