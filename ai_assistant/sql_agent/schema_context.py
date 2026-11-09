"""
Schema context, table allowlist, and column definitions for SmartDist AI Safe Text-to-SQL.
Strictly verified against actual PostgreSQL 16 schema.
"""

from typing import Dict, List, Set, Any

# Strict table allowlist for Safe Text-to-SQL
ALLOWED_TABLES: Set[str] = {
    "daily_sales",
    "products",
    "categories",
    "branches",
    "warehouses",
    "suppliers",
    "product_suppliers",
    "inventory",
    "sales_anomalies",
    "anomaly_detection_runs",
}

# Column allowlist per table matching exact database columns
ALLOWED_COLUMNS: Dict[str, Set[str]] = {
    "daily_sales": {
        "id", "sale_date", "branch_id", "product_id", "quantity_sold", "sales_amount",
        "promotion_quantity", "source_dataset", "data_origin", "created_at", "updated_at"
    },
    "products": {
        "id", "product_code", "product_name", "category_id", "source_family",
        "unit_of_measure", "is_active", "data_origin", "created_at", "updated_at"
    },
    "categories": {
        "id", "category_code", "category_name", "description", "created_at", "updated_at"
    },
    "branches": {
        "id", "branch_code", "branch_name", "city", "state", "source_store_number",
        "store_type", "cluster", "data_origin", "created_at", "updated_at"
    },
    "warehouses": {
        "id", "warehouse_code", "warehouse_name", "branch_id", "location",
        "data_origin", "created_at", "updated_at"
    },
    "suppliers": {
        "id", "supplier_code", "supplier_name", "lead_time_days",
        "minimum_order_quantity", "is_active", "data_origin", "created_at", "updated_at"
    },
    "product_suppliers": {
        "id", "product_id", "supplier_id", "unit_cost", "minimum_order_quantity",
        "created_at", "updated_at"
    },
    "inventory": {
        "id", "product_id", "warehouse_id", "stock_quantity", "reserved_quantity",
        "reorder_point", "safety_stock", "last_updated", "data_origin", "created_at", "updated_at"
    },
    "sales_anomalies": {
        "id", "detection_run_id", "anomaly_date", "branch_id", "product_id",
        "observed_quantity", "expected_quantity", "deviation", "percentage_deviation",
        "anomaly_score", "severity", "direction", "detector_evidence", "explanation",
        "recommended_actions", "investigation_status", "resolution_note", "data_provenance",
        "created_at", "updated_at"
    },
    "anomaly_detection_runs": {
        "id", "started_at", "completed_at", "status", "detection_window_start",
        "detection_window_end", "branch_id", "product_id", "detector_configuration",
        "model_version", "total_observations", "anomalies_detected", "data_provenance",
        "error_message", "created_at", "updated_at"
    },
}

SCHEMA_PROMPT = """
You are a PostgreSQL expert for SmartDist AI (Intelligent Retail & Distribution Management System).
Generate a safe, read-only PostgreSQL query based on the following verified database schema:

TABLE daily_sales:
  id (INTEGER, PK)
  sale_date (DATE) - Transaction date (2013-01-01 to 2013-12-31)
  branch_id (INTEGER, FK -> branches.id)
  product_id (INTEGER, FK -> products.id)
  quantity_sold (NUMERIC) - True observed physical demand (ALWAYS use for sales volume)
  sales_amount (NUMERIC) - Reference-price estimated revenue (quantity_sold * price)
  promotion_quantity (NUMERIC) - Number of promotional items

TABLE products:
  id (INTEGER, PK)
  product_code (VARCHAR)
  product_name (VARCHAR) - Product family name (e.g. GROCERY I, BEVERAGES, PRODUCE, DAIRY)
  category_id (INTEGER, FK -> categories.id)
  source_family (VARCHAR)
  unit_of_measure (VARCHAR)
  is_active (BOOLEAN)

TABLE categories:
  id (INTEGER, PK)
  category_code (VARCHAR)
  category_name (VARCHAR)
  description (VARCHAR)

TABLE branches:
  id (INTEGER, PK)
  branch_code (VARCHAR)
  branch_name (VARCHAR) - Store name (e.g. Store 1, Store 44)
  city (VARCHAR) - Store city (e.g. Quito, Guayaquil, Cuenca)
  state (VARCHAR) - Store province
  source_store_number (INTEGER)
  store_type (VARCHAR) - Store type (A, B, C, D, E)
  cluster (INTEGER) - Store cluster (1 to 17)

TABLE warehouses:
  id (INTEGER, PK)
  warehouse_code (VARCHAR)
  warehouse_name (VARCHAR)
  branch_id (INTEGER, FK -> branches.id)
  location (VARCHAR)

TABLE suppliers:
  id (INTEGER, PK)
  supplier_code (VARCHAR)
  supplier_name (VARCHAR)
  lead_time_days (INTEGER) - Supplier lead time in days
  minimum_order_quantity (INTEGER) - Supplier MOQ
  is_active (BOOLEAN)

TABLE product_suppliers:
  id (INTEGER, PK)
  product_id (INTEGER, FK -> products.id)
  supplier_id (INTEGER, FK -> suppliers.id)
  unit_cost (NUMERIC) - Purchase cost per unit
  minimum_order_quantity (INTEGER)

TABLE inventory:
  id (INTEGER, PK)
  product_id (INTEGER, FK -> products.id)
  warehouse_id (INTEGER, FK -> warehouses.id)
  stock_quantity (NUMERIC) - Current physical stock on hand
  reserved_quantity (NUMERIC) - Stock reserved for orders
  reorder_point (NUMERIC) - Threshold triggering replenishment order
  safety_stock (NUMERIC) - Buffer stock to protect against demand/lead-time variability

TABLE sales_anomalies:
  id (INTEGER, PK)
  detection_run_id (INTEGER, FK -> anomaly_detection_runs.id)
  anomaly_date (DATE)
  branch_id (INTEGER, FK -> branches.id)
  product_id (INTEGER, FK -> products.id)
  observed_quantity (NUMERIC) - Actual sales quantity
  expected_quantity (NUMERIC) - Expected baseline / forecast quantity
  deviation (NUMERIC)
  percentage_deviation (NUMERIC)
  anomaly_score (NUMERIC) - Composite severity score between 0.0 and 1.0
  severity (VARCHAR) - 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
  direction (VARCHAR) - 'SPIKE', 'DROP'
  explanation (TEXT)
  recommended_actions (TEXT)
  investigation_status (VARCHAR) - 'DETECTED', 'INVESTIGATING', 'CONFIRMED', 'FALSE_POSITIVE', 'RESOLVED'

IMPORTANT RULES:
1. ONLY write SELECT statements.
2. ALWAYS use quantity_sold for physical sales volume calculations (never sales_amount).
3. DO NOT use semicolons or multiple statements.
4. DO NOT query any tables not listed above.
5. ALWAYS specify an appropriate LIMIT (maximum 100).
"""


def get_schema_summary() -> Dict[str, Any]:
    """Returns structured schema summary for system context."""
    return {
        "allowed_tables": sorted(list(ALLOWED_TABLES)),
        "table_columns": {tbl: sorted(list(cols)) for tbl, cols in ALLOWED_COLUMNS.items()},
        "default_limit": 50,
        "max_limit": 100,
    }
