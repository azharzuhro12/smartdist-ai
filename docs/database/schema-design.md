# Database Schema Design Decisions

## 1. Architectural Principles

The database schema for SmartDist AI adheres to 3NF normalization, explicit referential integrity, and rigorous constraint validation.

### Strict Numeric Precision for Financials and Quantities
- Floating-point data types (`FLOAT`, `REAL`) suffer from binary representation rounding errors and must never be used for financials or inventory accounting.
- **`daily_sales.quantity_sold`**: `NUMERIC(14, 4)` supports fractional units (e.g. fresh meat, bulk produce weighed in kilograms).
- **`daily_sales.sales_amount`**: `NUMERIC(14, 2)` preserves exact monetary precision.
- **`product_suppliers.unit_cost`**: `NUMERIC(12, 2)` guarantees exact purchasing cost representation.

### Data Origin Labeling (`data_origin`)
- SmartDist AI combines public benchmark datasets (Kaggle Store Sales) with synthetic supply chain and inventory records.
- To prevent data poisoning and maintain analytical transparency, every row in `branches`, `products`, `daily_sales`, `warehouses`, `suppliers`, and `inventory` carries an explicit `data_origin` field:
  - `KAGGLE_PUBLIC`: Sourced directly from public competition datasets.
  - `SYNTHETIC`: Generated deterministically by the synthetic data generator.

## 2. Table-by-Table Specification

### `categories`
Defines merchandise hierarchies. Each distinct product family from the Kaggle dataset maps to a unique category with code prefix `CAT-`.

### `products`
Master catalog items. In the public dataset, sales are tracked at the family level. Each family is modeled as a standard SKU (`PRD-<FAMILY>`), preserving its `source_family` link for time-series modeling.

### `branches`
Physical store locations. Mapped from `stores.csv` (`store_nbr` -> `source_store_number`). Stores retain city, state, store type, and cluster attributes.

### `warehouses`
Regional distribution centers and fulfillment facilities. Mapped to strategic metropolitan hubs (e.g., Northern DC in Quito, Coastal Hub in Guayaquil).

### `suppliers` & `product_suppliers`
Vendor catalog with lead times, minimum order quantities (MOQ), and unit procurement costs. Supports inventory replenishment calculations.

### `inventory`
Warehouse stock balances. Enforces strict check constraints:
- `chk_stock_quantity_non_negative`: `stock_quantity >= 0`
- `chk_reserved_quantity_non_negative`: `reserved_quantity >= 0`
- `chk_reserved_le_stock`: `reserved_quantity <= stock_quantity`
- `chk_reorder_point_non_negative`: `reorder_point >= 0`
- `chk_safety_stock_non_negative`: `safety_stock >= 0`

### `daily_sales`
Daily aggregated sales records per branch and product. Indexed on `(sale_date, branch_id)` and `(sale_date, product_id)` with a unique constraint on `(sale_date, branch_id, product_id)` to ensure idempotent re-ingestion.

### `data_import_logs` & `data_quality_results`
Comprehensive audit trail capturing batch execution durations, record counts, rejection totals, and rule-level validation status.
