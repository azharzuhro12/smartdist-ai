# Data Quality & Validation Rules

## 1. Quality Dimensions Enforced

SmartDist AI validates incoming data across five quality dimensions:
1. **Completeness**: Critical columns cannot contain null or whitespace-only values.
2. **Conformity**: Dates must adhere to ISO 8601 (`YYYY-MM-DD`). Numbers must match physical realities.
3. **Uniqueness**: Composite business keys cannot duplicate.
4. **Integrity**: Foreign key relationships must resolve to existing primary keys.
5. **Consistency**: Physical constraints must hold across interrelated fields (e.g., `reserved_quantity <= stock_quantity`).

## 2. Table Validation Rules

### Store & Branch Data (`validate_stores_data`)
- `store_nbr` must be a positive integer (`> 0`).
- `city` and `state` must not be null or blank.
- Duplicate `store_nbr` values trigger record rejection.

### Daily Sales Data (`validate_sales_chunk`)
- `date` must parse into a valid `datetime.date`.
- `sales` (quantity) must be non-negative (`>= 0`).
- `onpromotion` must be non-negative (`>= 0`).
- `store_nbr` must exist in `branches.source_store_number`.
- `family` must exist in `products.source_family`.
- Composite uniqueness on `(date, store_nbr, family)`.

### Inventory Data (`validate_inventory_data`)
- `stock_quantity >= 0`.
- `reserved_quantity >= 0`.
- `reserved_quantity <= stock_quantity`.
- `reorder_point >= 0`.
- `safety_stock >= 0`.

## 3. Reporting & Audit Tracking

All quality validations generate structured summaries persisted in `data_quality_results`:
- `total_records`: Input records inspected.
- `valid_records`: Records passing all checks.
- `failed_records`: Records rejected due to validation failure.
- `validation_status`: `PASSED` (0 errors), `WARNING` (acceptable partial rejections), or `FAILED` (fatal batch failure).
- `details`: JSON payload containing specific issue messages and breakdown counts.
