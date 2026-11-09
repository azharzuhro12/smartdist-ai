# SmartDist AI — Phase 2 Final Audit & Phase 3 Readiness Assessment

- **Audit Date**: 2026-11-09
- **Auditor Role**: Senior Machine Learning Engineer, Data Engineer, and Software Architect
- **Target Project**: SmartDist AI (Intelligent Distribution & Retail Management System)
- **Scope**: Codebase audit, PostgreSQL state, Celery & Redis execution, ETL pipeline validation, data consistency, time-series readiness, and ML dependency verification.

---

## 1. Executive Summary

A comprehensive, evidence-based audit of SmartDist AI Phase 2 (Data Engineering & Pipeline Foundations) was conducted against the running Docker environment, PostgreSQL 16 database, Redis 7 broker, and Python test suite.

The system has successfully established a 3NF normalized relational schema, integrated the Kaggle Store Sales benchmark dataset, developed a streaming chunked ETL pipeline, and implemented a reproducible synthetic inventory generation engine with explicit data provenance.

All Phase 1 infrastructure (Docker Compose, PostgreSQL on host 5435, Redis on host 6380, FastAPI backend on host 8035, and Celery workers) remains operational and healthy. The test suite passes 100% of its 30 unit, integration, and API tests.

**Audit Readiness Conclusion**: **READY AFTER MINOR FIXES** (Minor fixes implemented and verified; operational guidelines for full-dataset ingestion established).

---

## 2. Verified Implementation Status

| Component | Target Location | Implemented Status | Verification Evidence | Finding |
|---|---|:---:|---|:---:|
| **PostgreSQL Schema** | `backend/app/models/business.py`, `backend/app/models/audit.py` | Complete | 10 normalized tables active in PostgreSQL with check constraints and composite indexes | **PASS** |
| **Alembic Migrations** | `backend/alembic/versions/` | Complete | Migration `29e5a9b3f957_create_phase2_business_schema` verified via upgrade/downgrade test | **PASS** |
| **Data Extraction** | `ml/pipelines/ingestion/extract.py` | Complete | `DataExtractor.extract_daily_sales_stream()` streams chunks without high memory consumption | **PASS** |
| **Quality Validation**| `ml/pipelines/validation/quality.py` | Complete | `DataQualityValidator` evaluates stores, sales, and inventory against domain rules | **PASS** |
| **Transformation** | `ml/pipelines/transformation/transform.py` | Complete | Maps stores to `Branch`, families to `Category`/`Product`, calculates financial amounts | **PASS** |
| **Data Loading** | `ml/pipelines/loading/load.py` | Complete | Batch upsert using `ON CONFLICT (sale_date, branch_id, product_id) DO UPDATE` | **PASS** |
| **Synthetic Generator**| `ml/pipelines/synthetic/inventory_generator.py` | Complete | Deterministic generation with fixed seed (`seed=42`); explicit `SYNTHETIC` tag | **PASS** |
| **Celery Tasks** | `backend/app/workers/tasks.py` | Complete | 4 tasks registered: `verify_infrastructure`, `import_sales_dataset`, `validate_dataset`, `generate_synthetic_inventory` | **PASS** |
| **REST API** | `backend/app/api/v1/endpoints/` | Complete | 10 endpoints verified via HTTP requests | **PASS** |
| **Automated Tests** | `backend/tests/` | Complete | 30 tests passing in Pytest across models, ETL, synthetic data, Celery, and APIs | **PASS** |

---

## 3. Actual Dataset Ingestion Statistics

Direct verification against the live PostgreSQL database (`smartdist_db`):

```sql
SELECT
    (SELECT COUNT(*) FROM branches) AS branches,
    (SELECT COUNT(*) FROM categories) AS categories,
    (SELECT COUNT(*) FROM products) AS products,
    (SELECT COUNT(*) FROM daily_sales) AS daily_sales,
    (SELECT COUNT(*) FROM warehouses) AS warehouses,
    (SELECT COUNT(*) FROM suppliers) AS suppliers,
    (SELECT COUNT(*) FROM inventory) AS inventory,
    (SELECT COUNT(*) FROM data_import_logs) AS import_logs,
    (SELECT COUNT(*) FROM data_quality_results) AS quality_results;
```

### Verified Live Counts
- **`branches`**: 54
- **`categories`**: 33
- **`products`**: 33
- **`daily_sales`**: 50,000
- **`warehouses`**: 4
- **`suppliers`**: 6
- **`inventory`**: 132 (33 products × 4 warehouses)
- **`data_import_logs`**: 3
- **`data_quality_results`**: 7
- **Total Physical Stock**: 32,220 units
- **Total Reserved Stock**: 5,020 units
- **Net Available Stock**: 27,200 units

### Ingestion Performance & Scalability
- **Streaming Pipeline**: `DataExtractor.extract_daily_sales_stream()` chunking (25,000 rows/chunk) prevents memory spikes.
- **Idempotency**: Running an ingestion test over existing date ranges (`max_sales_rows=1000`) confirmed `count_before = 50,000` and `count_after = 50,000` with 0 duplicates created.
- **Full Dataset Sizing**: `train.csv` contains **3,000,888 rows**. Streaming all rows via the existing batch loader requires approximately 35–45 minutes over SQLAlchemy ORM batches.
  - **Celery Timeout Consideration**: Celery's default `task_time_limit` is set to 300s (5 minutes) and `task_soft_time_limit` to 240s (4 minutes). Attempting to ingest all 3M rows in a single Celery task without date slicing will trigger a timeout exception.
  - **Finding**: **WARNING** (Addressed via ingestion strategy recommendations).

---

## 4. Data Consistency Findings

### Discrepancy Investigation
In the initial Phase 2 run, the execution report stated:
- `records_processed`: 50,087
- `records_inserted`: 50,262
- Difference: **+175 records inserted beyond records processed**

### Root Cause Analysis (`backend/app/services/etl_service.py`)
Investigation of the accumulation logic revealed:
1. **Source rows processed**:
   - `stores_df`: 54 rows
   - `families`: 33 distinct strings
   - `sales_stream`: 50,000 rows
   - Sum = `54 + 33 + 50,000 = 50,087`
2. **Database entities inserted**:
   - `branches`: 54
   - `categories`: 33
   - `products`: 33 (each family created 1 Category AND 1 Product SKU: 33 + 33 = 66 entities from 33 source strings, net +33)
   - `daily_sales`: 50,000
   - `warehouses`: 4
   - `suppliers`: 6
   - `inventory`: 132
   - Sum = `54 + 66 + 50,000 + 4 + 6 + 132 = 50,262`

`total_processed` counted raw input source lines, while `total_inserted` counted total normalized rows written across 7 distinct database tables. Furthermore, synthetic entities (142 rows) were added to `total_inserted` without incrementing `total_processed`.

### Resolution Implemented
`ETLService.execute_pipeline()` now accurately increments `total_processed` for all evaluated entities and returns a detailed `breakdown` dictionary:
- `source_stores_processed`
- `branches_loaded`
- `categories_loaded`
- `products_loaded`
- `sales_rows_processed`
- `sales_rows_upserted`
- `sales_rows_rejected`
- `synthetic_warehouses`
- `synthetic_suppliers`
- `synthetic_inventory_records`
- **Finding**: **PASS** (Resolved).

---

## 5. Sales Amount Calculation Findings

### Analysis of `daily_sales.sales_amount`
- In the Kaggle dataset (`train.csv`), the column is `sales`, representing **units/quantity sold** (including fractional units for goods weighed in kilograms).
- In `ml/pipelines/transformation/transform.py`:
  - `quantity_sold = Decimal(str(round(float(row["sales"]), 4)))`
  - `sales_amount = (quantity_sold * unit_price).quantize(Decimal("0.01"))`
  - `unit_price` is obtained from `FAMILY_PRICE_REFERENCE`.

### Risk Assessment
Because the table's `data_origin` is labeled `'KAGGLE_PUBLIC'`, consumers or downstream ML engineers might incorrectly assume `sales_amount` represents an observed POS transactional dollar amount rather than a derived financial estimate.

### Resolution Implemented
1. **Model Property**: Added `@property def is_amount_estimated(self) -> bool: return True` to `DailySale` in [backend/app/models/business.py](../../backend/app/models/business.py).
2. **API Schema**: Added `is_amount_estimated: bool = Field(default=True)` and explicit field descriptions to `DailySaleResponse` in [backend/app/schemas/business.py](../../backend/app/schemas/business.py).
3. **Machine Learning Guideline**: For Phase 3 forecasting, models must predict `quantity_sold` (the ground truth volume from the source dataset) rather than `sales_amount`.
- **Finding**: **PASS** (Resolved without breaking schema or API contracts).

---

## 6. Time-Series Data Readiness Assessment

### Current Temporal Profile in PostgreSQL
- **Minimum Date**: `2013-01-01`
- **Maximum Date**: `2013-01-29`
- **Distinct Dates**: 29 days
- **Daily Combinations**: 54 stores × 33 product families = 1,782 series per full day.
  - Dates `2013-01-01` through `2013-01-28`: exactly 1,782 records per day.
  - Date `2013-01-29`: 104 records (incomplete day due to `max_sales_rows=50000` cap).
- **Duplicate `(sale_date, branch_id, product_id)` tuples**: 0.

### Readiness for Time-Series Modeling
- **Assessment**: 29 days is **insufficient** for training production time-series models (e.g. LightGBM, XGBoost) that require 7-day, 14-day, 28-day lags, rolling statistical windows (e.g., 30-day SMA), and annual seasonality (365-day cycles).
- **Full History Available**: Raw `train.csv` contains 1,684 days (2013-01-01 to 2017-08-15) with 3,000,888 rows.
- **Recommended Ingestion Strategy for Phase 3**:
  1. For initial baseline model development: Ingest at least 1 full calendar year (e.g., 2016 or 2013–2014, ~650,000 rows).
  2. For final production models: Ingest full 4.5-year history using chunked yearly stages or the bulk ingestion script.
- **Finding**: **WARNING** (Expected at Phase 2 boundary; full raw data is ready for staged ingestion).

---

## 7. Python and ML Dependency Compatibility

### Python Version Profile
- **Host / Local Environment**: Python 3.14.7 (`.venv`)
- **Docker Backend Container**: Python 3.12-slim (`smartdist_backend`, `smartdist_celery_worker`)

### Package Wheel Availability Test (Python 3.14)
A pip dependency resolution test was executed in the Python 3.14 environment:
```bash
pip install --dry-run scikit-learn xgboost lightgbm
```
**Results**:
- `scikit-learn`: Version 1.9.1 (`cp314-manylinux`) — **Available**
- `scipy`: Version 1.18.1 (`cp314-manylinux`) — **Available**
- `xgboost`: Version 3.4.1 (`py3-none-manylinux`) — **Available**
- `lightgbm`: Version 4.7.0 (`py3-none-manylinux`) — **Available**
- `pandas`: Version 3.1.1 (`cp314-manylinux`) — **Installed & Verified**
- `numpy`: Version 2.5.4 (`cp314-manylinux`) — **Installed & Verified**

### Compatibility Assessment
- **Local Host Compatibility**: All target Phase 3 ML dependencies have pre-built wheels for Python 3.14.
- **Container Environment Compatibility**: Docker uses `python:3.12-slim`, which is the industry LTS standard for ML workloads with 100% stable binary wheel support.
- **Finding**: **PASS**.

---

## 8. Synthetic Data Provenance Assessment

Inspection of all tables in PostgreSQL confirms strict isolation of synthetic records:

| Table | Total Rows | `KAGGLE_PUBLIC` Rows | `SYNTHETIC` Rows | Provenance Isolation |
|---|:---:|:---:|:---:|:---:|
| `branches` | 54 | 54 (100%) | 0 | Strict |
| `products` | 33 | 33 (100%) | 0 | Strict |
| `daily_sales` | 50,000 | 50,000 (100%) | 0 | Strict (with `is_amount_estimated=True`) |
| `warehouses` | 4 | 0 | 4 (100%) | Strict |
| `suppliers` | 6 | 0 | 6 (100%) | Strict |
| `inventory` | 132 | 0 | 132 (100%) | Strict |

All synthetic inventory satisfies:
- `stock_quantity >= 0`
- `reserved_quantity <= stock_quantity`
- `safety_stock <= reorder_point`
- Deterministic seed reproduction (`seed=42`)
- **Finding**: **PASS**.

---

## 9. Architecture Risks & Mitigations

| Risk Area | Description | Severity | Mitigation Strategy |
|---|---|:---:|---|
| **Celery Long ETL Timeout** | Ingesting all 3M rows in a single Celery task exceeds 4-minute soft limit. | Medium | Stage ingestion by year (e.g. 2013, 2014) or run full load via dedicated CLI script. |
| **Stream Filtering Efficiency** | Date-filtered streams previously continued scanning past `end_date`. | Low | Added early break optimization in `extract_daily_sales_stream()` when `chunk['date'].min() > end_date`. |
| **Target Variable Ambiguity** | Modeling on derived `sales_amount` instead of observed `quantity_sold`. | Medium | Formalized in schema and ML guidelines: forecasting models must train on `quantity_sold`. |

---

## 10. Required Fixes Completed Before Phase 3

The following backward-compatible improvements were implemented and verified during this audit:

1. **Estimated Sales Flag Added**:
   - Added `is_amount_estimated` property to [DailySale](../../backend/app/models/business.py#L194-L203).
   - Added `is_amount_estimated: bool = True` field with OpenAPI descriptions to [DailySaleResponse](../../backend/app/schemas/business.py#L107-L119).
2. **Stream Early-Exit Optimization**:
   - Added chronological break condition in [DataExtractor.extract_daily_sales_stream](../../ml/pipelines/ingestion/extract.py#L76-L83) when `chunk["date"].min() > end_date`.
3. **Disambiguated ETL Accounting**:
   - Updated [ETLService.execute_pipeline](../../backend/app/services/etl_service.py#L128-L165) to include a structured `breakdown` dictionary distinguishing raw processed rows from multi-table inserts.

---

## 11. Final Phase 3 Readiness Decision

### Decision: **READY FOR PHASE 3**

**Justification**:
1. All minor ambiguities identified in the audit have been corrected and tested.
2. The Pytest suite passes 30/30 tests (100% pass rate).
3. Database schemas, constraints, and audit logs are verified on live PostgreSQL 16.
4. Redis 7 and Celery workers are operational and executing background tasks.
5. All target ML dependencies (LightGBM, XGBoost, Scikit-learn) have verified binary wheel support.
6. The data engineering foundation is stable, documented, and ready for Feature Engineering and Machine Learning Demand Forecasting.
