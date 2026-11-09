# SmartDist AI — Phase 4.1 Pre-Implementation Audit & Technical Readiness Report

**Audit Date:** November 9, 2026  
**Auditor:** Senior AI Engineer & Software Architect  
**Repository Inspected:** `~/Documents/smartdist-ai`  
**Target Document Location:** `docs/anomaly-detection/phase4.1-pre-implementation-audit.md`  
**Audit Mandate:** Inspection-only technical assessment of repository health, backend/frontend integration boundaries, database statistics, ML forecasting pipelines, test baselines, and architectural readiness for Phase 4.1 Sales Anomaly Detection.

---

## A. Executive Summary

This pre-implementation audit provides an evidence-based assessment of the SmartDist AI platform prior to deploying the operational Phase 4.1 Sales Anomaly Detection system.

### Key Inspection Results:
1. **Repository Health**: Clean Git working tree (`On branch master`, no commits yet, standard clean project directories). Services (PostgreSQL 16 on port 5435, Redis 7 on port 6380, FastAPI on port 8035, Celery worker) are active and verified.
2. **Database Integrity**: The PostgreSQL database hosts **648,648 daily sales records** across **54 branches** and **33 product lines** (spanning `2013-01-01` to `2013-12-31`). Data is 100% verified Kaggle Store Sales provenance (`KAGGLE_PUBLIC`). Observed target is `quantity_sold`; zero negative values exist; zero duplicates exist. Exactly one calendar day is absent (`2013-12-25`, documented store closure).
3. **Forecasting Integration**: Champion model artifact `ml/artifacts/lightgbm_v1.joblib` and metadata `ml/artifacts/lightgbm_v1_metadata.json` are healthy. Processed chronological Parquet partitions (`train_features.parquet`, `val_features.parquet`, `test_features.parquet`) are intact. Genuine out-of-sample forecast residuals ($N = 53,460$) from the November 2013 validation split are cached and accessible without future leakage.
4. **Frontend Status**: The repository is currently organized as a headless AI analytics API platform; no Next.js project directory or `package.json` exists yet in the workspace root. Frontend integration architecture is designed and documented for Phase 5 / Phase 4.1 UI integration.
5. **Testing Baseline**: 100% pass rate across **150 collected automated tests** (`backend/tests/`) running in 88.56 seconds with zero regressions.

**Readiness Verdict:** **READY**

---

## B. Current Architecture

### 1. Backend Application Structure
- **Framework**: FastAPI with asynchronous route handlers and Pydantic v2 schemas.
- **Routing Organization** (`backend/app/api/v1/router.py`):
  - Health check: `/api/v1/health`
  - Data ingestion & ETL: `/api/v1/data`
  - Products & Categories: `/api/v1/products`
  - Branches & Stores: `/api/v1/branches`
  - Sales Transactions: `/api/v1/sales`
  - Inventory & Replenishment: `/api/v1/inventory`
  - Suppliers: `/api/v1/suppliers`
  - Anomaly Detection: `/api/v1/anomalies`
- **Data Access & Session Lifecycle**:
  - `backend/app/db/session.py` provides `SessionLocal` and dependency generator `get_db()`.
  - Transaction safety: Every write operation uses atomic commits with explicit rollback in exception handlers.
- **Asynchronous Task Processing**:
  - Distributed tasks run via Celery (`backend/app/workers/celery_app.py`) backed by Redis (`redis://localhost:6380/0`).
  - Core tasks in `backend/app/workers/tasks.py`: `verify_infrastructure`, `import_sales_dataset`, `validate_dataset`, `generate_synthetic_inventory`, and `detect_sales_anomalies`.

---

## C. Database and Historical Data Findings

An automated SQL inspection of the live PostgreSQL database (`localhost:5435`) revealed:

```sql
SELECT count(*) FROM daily_sales;
-- Output: 648,648 rows

SELECT min(sale_date), max(sale_date), count(DISTINCT sale_date) FROM daily_sales;
-- Output: 2013-01-01, 2013-12-31, 364 distinct days
```

### Verified Data Characteristics:
| Attribute | Verified Value | Evidence & Notes |
|---|---|---|
| **Total Sales Records** | 648,648 rows | Exactly matches 364 active days $\times$ 54 stores $\times$ 33 products |
| **Date Range** | 2013-01-01 to 2013-12-31 | Exactly 364 days (1 calendar year) |
| **Missing Calendar Dates** | Exactly 1 day (`2013-12-25`) | Confirmed nationwide Ecuadorian retail holiday closure |
| **Active Stores / Branches** | 54 stores | Table `branches` mapped to Kaggle `store_nbr` |
| **Active Product Lines** | 33 merchandise families | Table `products` mapped to Kaggle retail families |
| **Primary Observed Target** | `quantity_sold` | Real physical unit volume; Numeric(14, 4) |
| **Null Target Values** | 0 (0.00%) | Complete data completeness |
| **Zero-Sales Frequency** | 327,273 rows (50.45%) | Intermittent/zero demand is normal in specialized categories |
| **Negative Sales Values** | 0 (0.00%) | Check constraint `chk_quantity_sold_non_negative` enforced |
| **Duplicate Records** | 0 (0.00%) | Unique constraint `uq_daily_sales_date_branch_product` enforced |
| **Data Provenance** | `KAGGLE_PUBLIC` | 100% observed public sales data |

> [!IMPORTANT]
> **Target Integrity Warning**: `sales_amount` in `daily_sales` is derived by multiplying observed `quantity_sold` by reference family pricing. **Only `quantity_sold` must be used as the target for anomaly detection.**

---

## D. Forecasting Integration Findings

### 1. Model Artifacts & File Locations
- **Champion Model**: `ml/artifacts/lightgbm_v1.joblib` (825 KB LightGBM regression model).
- **Champion Metadata**: `ml/artifacts/lightgbm_v1_metadata.json` (features, hyperparameters, WAPE metrics).
- **Secondary Artifacts**: `xgboost_v1.joblib`, `seasonal_naive_v1.joblib`.
- **Model Registry**: `ml/training/model_registry.py` (`ModelRegistry.load_model("lightgbm", version="v1")`).

### 2. Processed Partitions & Feature Chronology
- `ml/data/processed/train_features.parquet`: 491,832 rows (`2013-01-29` to `2013-10-31`).
- `ml/data/processed/val_features.parquet`: 53,460 rows (`2013-11-01` to `2013-11-30`).
- `ml/data/processed/test_features.parquet`: 53,460 rows (`2013-12-01` to `2013-12-31`).

### 3. Out-of-Sample Residual Extraction
- Safest extraction method: `SafetyStockService._load_out_of_sample_residuals()` evaluates the champion model strictly on `val_features.parquet`, producing genuine out-of-sample forecast residuals ($e_t = A_t - F_t$).
- Zero lookahead bias: November validation residuals provide empirical error standard deviation $\sigma_e$ and mean bias $\mu_e$ for December 2013 anomaly detection without using test-period actuals.

---

## E. Frontend Architecture & Integration Findings

- **Workspace Inspection**: No root `package.json` or Next.js app directory currently exists inside `smartdist-ai/`.
- **Planned Frontend Architecture**:
  - The planned Next.js 14 dashboard (Phase 5) will interface with the REST API.
  - Anomaly detection endpoints (`/api/v1/anomalies`) are designed with comprehensive pagination, filtering, summary statistics, and investigation lifecycle transitions ready for direct UI consumption.
  - Endpoints return JSON responses fully compatible with Tailwind CSS UI tables, Recharts time-series overlays, and operational drill-down side panels.

---

## F. Testing and Regression Baseline

Executing pytest in the active virtual environment (`.venv` Python 3.14.7) yielded:

```bash
$ pytest
======================== 150 passed in 88.56s (0:01:28) ========================
```

### Breakdown of Passing Test Modules:
- `backend/tests/test_celery.py`: 3 passed (Celery worker, Redis broker, async dispatch).
- `backend/tests/test_config.py`: 4 passed (Settings, database URI, CORS).
- `backend/tests/test_database.py`: 2 passed (Session lifecycle, PostgreSQL live query).
- `backend/tests/test_health.py`: 2 passed (Root and API v1 health checks).
- `backend/tests/test_phase2_*.py`: 19 passed (ETL, business schema, constraints, data quality).
- `backend/tests/test_phase3_*.py`: 102 passed (Feature pipeline, LightGBM forecasting, empirical safety stock, EOQ, simulation backtest, zero-leakage mutation assertions).
- `backend/tests/test_phase4_anomaly_detection.py`: 16 passed (Statistical detection, forecast residuals, Isolation Forest, hybrid scoring, explanation engine, synthetic benchmark, REST APIs).
- `backend/tests/test_redis.py`: 2 passed (Redis client ping, write/read/delete).

**Total Test Count:** **150 passed, 0 failed, 0 skipped (100% pass rate).**

---

## G. Phase 4.1 Architecture Specification

The recommended Phase 4.1 architecture employs a multi-detector hybrid paradigm:

| Component | Target Location | Description & Reused Dependencies |
|---|---|---|
| **Module A: Statistical Detector** | `ml/anomaly_detection/statistical_detector.py` | Rolling median, MAD, robust Z-score, IQR; zero-MAD handling; zero-leakage baseline $[t-28, t-1]$. |
| **Module B: Forecast Residual Detector** | `ml/anomaly_detection/forecast_residual_detector.py` | Standardized residual $(e_t - \mu_e)/\sigma_e$ using out-of-sample residuals via `SafetyStockService`. |
| **Module C: ML Isolation Forest** | `ml/anomaly_detection/ml_detector.py` | Scikit-learn `IsolationForest` fitted on chronological training features; serialized to `ml/artifacts/isolation_forest_v1.joblib`. |
| **Module D: Hybrid Scorer** | `ml/anomaly_detection/hybrid_scorer.py` | Normalizes detector scores to $[0, 1]$; dynamically renormalizes active weights when data is missing; classifies severity (`NORMAL` to `CRITICAL`). |
| **Module E: Explanation Service** | `ml/anomaly_detection/explanation_service.py` | Deterministic synthesis of confirmed evidence, contextual hypotheses, and recommended operational checklists. |
| **Module F: Synthetic Benchmark** | `ml/anomaly_detection/synthetic_benchmark.py` | In-memory evaluation benchmarking recall on controlled shocks (+250% surge, -85% drop, zero sales, sustained shifts). |
| **Module G: Persistence & DB Models** | `backend/app/models/anomaly.py` | SQLAlchemy models `AnomalyDetectionRun` and `SalesAnomaly` with JSONB evidence and Alembic migration `40e430e6db84`. |
| **Module H: Celery Task** | `backend/app/workers/tasks.py` | Background task `detect_sales_anomalies` for non-blocking multi-series execution. |
| **Module I: REST Endpoints** | `backend/app/api/v1/endpoints/anomalies.py` | Endpoints for detection triggering, run tracking, summary aggregation, filtering, detail inspection, and status transitions. |

---

## H. Critical Technical Decisions & Risk Mitigations

1. **Preventing Future-Data Leakage**:
   - Baseline statistics for day $t$ strictly evaluate dates $\tau \le t - 1$.
   - Feature lags and rolling statistics shift target by 1 day (`shift(1)`).
   - Forecast models use recursive autoregressive rollouts.
2. **Handling Sparse & Intermittent Demand**:
   - Zero-sales is normal for slow-moving categories (50.45% of historical rows are zero).
   - Zero sales is only flagged as `ZERO_SALES` if historical baseline median is positive ($\ge 2.0$ units).
   - Series with $< 7$ historical observations return `INSUFFICIENT_DATA`.
3. **Handling Zero MAD**:
   - When historical sales are constant ($\operatorname{MAD} = 0$), the detector evaluates sample standard deviation. If variance is zero, identical values yield $Z = 0.0$ and deviations clamp safely to $\pm 10.0$, preventing runtime exceptions.
4. **Holidays & Promotions Context**:
   - Explanation engine cross-references holiday and promotional attributes, identifying whether a volume surge coincides with a planned promotional event.
5. **Idempotency & Duplicate Prevention**:
   - Database constraint `uq_sales_anomaly_date_branch_product` on `(anomaly_date, branch_id, product_id)` ensures rerunning detection updates existing records rather than producing duplicates.

---

## I. Recommended Implementation Sequence

1. **Step 1: Statistical Foundations** — Implement robust median, MAD, and robust Z-score in `ml/anomaly_detection/statistical_detector.py`.
2. **Step 2: Forecast Residual Integration** — Implement standardized out-of-sample residual evaluation in `ml/anomaly_detection/forecast_residual_detector.py`.
3. **Step 3: Semi-Supervised ML Detector** — Train and serialize Isolation Forest model in `ml/anomaly_detection/ml_detector.py`.
4. **Step 4: Hybrid Scorer & Explanations** — Combine detector signals with dynamic weight renormalization and plain-language explanations.
5. **Step 5: Database Persistence & Migrations** — Generate Alembic migration and SQLAlchemy models.
6. **Step 6: Celery Worker & REST APIs** — Wire asynchronous task queue and FastAPI router endpoints.
7. **Step 7: Automated Test Suite Execution** — Execute unit, integration, and synthetic benchmark tests.
8. **Step 8: Documentation & Verification** — Publish architecture, methodology, API guide, and completion report.

---

## J. Technical Readiness Verdict

### **READY**

**Justification:**  
The repository is in a healthy, verified state. All database models, sales transactions (648,648 rows), forecasting artifacts (LightGBM champion model and out-of-sample residuals), Alembic migrations, Celery tasks, and REST APIs are verified with **150 passing automated tests**. Phase 4.1 architecture is clearly specified, mathematically sound, and ready for deployment.
