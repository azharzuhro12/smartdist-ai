# SmartDist AI: Intelligent Distribution & Retail Management System

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D.svg)](https://redis.io/)
[![Celery](https://img.shields.io/badge/Celery-5.4+-37814A.svg)](https://docs.celeryq.dev/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://www.docker.com/)

SmartDist AI is an enterprise-grade, AI-powered distribution and retail analytics platform engineered to optimize supply chain decisions, forecast sales demand, mitigate stockout risks, and empower stakeholders through natural language business intelligence.

---

## 1. Project Overview

In fast-paced distribution and retail supply chains, inventory miscalculations result in either costly excess stock (working capital lockup) or critical stockouts (lost revenue and churn). **SmartDist AI** addresses these challenges by uniting modern data engineering, machine learning forecasting, real-time transaction processing, and autonomous conversational agents within a modular, production-ready system architecture.

---

## 2. Business Problems Addressed

- **Stockout Vulnerability & Lost Sales**: Inaccurate demand estimation leads to depleted warehouse inventory during peak sales cycles.
- **Overstocking & Carrying Costs**: Stagnant inventory ties up working capital, increases warehousing expenses, and risks product expiration.
- **Supply Chain Blindspots**: Siloed data across POS terminals, regional distribution centers, and supplier logs obscures timely decision-making.
- **Transaction Anomalies & Shrinkage**: Undetected irregular sales spikes or abrupt drops indicate billing discrepancies, fraud, or supply disruption.
- **Inaccessible Analytics**: Store managers and operations leads often lack SQL expertise to extract operational insights on demand.

---

## 3. Main Features Planned

1. **Demand Forecasting Engine**: High-accuracy time-series forecasting (XGBoost, LightGBM) accounting for seasonality, promotion effects, and store-level trends.
2. **Dynamic Inventory Optimization**: Safety stock recommendations, reorder point calculators, and economic order quantity (EOQ) optimization.
3. **Real-time Anomaly Detection**: Unsupervised detection of anomalous transaction volumes, sudden sales velocity drop-offs, and store anomalies.
4. **AI Business Assistant (RAG & Text-to-SQL)**: Secure, natural language interface enabling executives to query inventory levels, sales velocity, and supplier KPIs with strict SQL validation.
5. **Operational Analytics Dashboard**: Next.js & Tailwind CSS dashboard featuring interactive visualizations of forecasts, inventory risk tiers, and alerts.

---

## 4. Technology Stack

### Backend & Core Services
- **Language**: Python 3.12+ / 3.14 compatible
- **API Framework**: FastAPI (asynchronous endpoints, OpenAPI schema generation, dependency injection)
- **Data Validation & Settings**: Pydantic v2 & Pydantic-Settings
- **ORM & Database Toolkit**: SQLAlchemy 2.x
- **Database Migrations**: Alembic

### Infrastructure & Distributed Computing
- **Relational Database**: PostgreSQL 16
- **Cache & Message Broker**: Redis 7 Alpine
- **Asynchronous Task Queue**: Celery 5.4+
- **Containerization**: Docker & Docker Compose (multi-stage builds, non-root system users, container health checks)

### Testing & Code Quality
- **Data Engineering**: Pandas 2.2+, NumPy
- **Testing Engine**: Pytest & pytest-asyncio
- **HTTP Client**: HTTPX & Starlette TestClient
- **Logging**: Structured JSON logging for production observability

---

## 5. Architecture Overview

SmartDist AI adopts a **modular monolithic architecture** designed for clean domain separation, high testability, and operational simplicity:

```
                      +------------------------------------+
                      |     Clients (Next.js / CLI / API)  |
                      +-----------------+------------------+
                                        | HTTP / JSON
                                        v
                      +------------------------------------+
                      |          FastAPI Gateway           |
                      |  - Structured Logging & CORS       |
                      |  - Pydantic Validation             |
                      |  - Versioned Routes (/api/v1)      |
                      +--------+------------------+--------+
                               |                  |
           Database Sessions   |                  | Task Dispatch
            (SQLAlchemy 2.x)   v                  v (Redis Broker)
                      +-----------------+  +-----------------+
                      |   PostgreSQL    |  |     Redis 7     |
                      |   Relational    |  |  Cache & Broker |
                      |     Storage     |  +--------+--------+
                      +-----------------+           |
                                                    v
                                           +-----------------+
                                           |  Celery Workers |
                                           | Background Tasks|
                                           +-----------------+
```

---

## 6. Repository Structure

```
smartdist-ai/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── endpoints/
│   │   │       │   ├── __init__.py
│   │   │       │   └── health.py
│   │   │       ├── __init__.py
│   │   │       └── router.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   ├── logging.py
│   │   │   └── redis.py
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   └── session.py
│   │   ├── models/
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   └── health.py
│   │   ├── services/
│   │   ├── workers/
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py
│   │   │   └── tasks.py
│   │   └── main.py
│   │
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_celery.py
│   │   ├── test_config.py
│   │   ├── test_database.py
│   │   ├── test_health.py
│   │   └── test_redis.py
│   ├── alembic/
│   │   ├── versions/
│   │   ├── env.py
│   │   └── script.py.mako
│   ├── alembic.ini
│   └── requirements.txt
│
├── ml/
│   ├── data/ (raw, processed, features)
│   ├── forecasting/
│   ├── inventory/
│   ├── anomaly_detection/
│   ├── evaluation/
│   └── pipelines/
│
├── ai_assistant/
│   ├── rag/
│   ├── sql_agent/
│   └── prompts/
│
├── infrastructure/
│   ├── docker/
│   │   └── Dockerfile.backend
│   └── redis/
│       └── redis.conf
│
├── docs/
│   ├── architecture/
│   ├── database/
│   └── model_evaluation/
│
├── scripts/
├── docker-compose.yml
├── pytest.ini
├── .env.example
├── .gitignore
└── README.md
```

---

## 7. Prerequisites

- **Docker**: Engine version 24.0+ or compatible
- **Docker Compose**: v2.20+
- **Python**: 3.12+ (Python 3.14 compatible)
- **Make / Bash shell**

---

## 8. Installation Instructions

### 1. Clone & Setup Workspace
```bash
git clone <repository_url>
cd smartdist-ai
```

### 2. Configure Python Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
```

---

## 9. Environment Configuration

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Review and adjust variables as needed:
| Parameter | Default | Description |
|---|---|---|
| `ENVIRONMENT` | `development` | Deployment tier (`development`, `staging`, `production`) |
| `DEBUG` | `true` | Enable debug logs and hot reload |
| `POSTGRES_SERVER` | `localhost` | PostgreSQL host |
| `POSTGRES_PORT` | `5435` | PostgreSQL host port (mapped to 5432 internally) |
| `POSTGRES_DB` | `smartdist_db` | Application database name |
| `POSTGRES_USER` | `smartdist_user` | Database user account |
| `POSTGRES_PASSWORD` | `smartdist_secure_password` | Database user password |
| `REDIS_HOST` | `localhost` | Redis host |
| `REDIS_PORT` | `6380` | Redis host port (mapped to 6379 internally) |
| `REDIS_PASSWORD` | `smartdist_redis_pass` | Redis auth secret |
| `HOST_BACKEND_PORT` | `8035` | Host port for FastAPI backend |

> **Security Note**: Never commit `.env` to source control. `.gitignore` is preconfigured to prevent secret leaks.

---

## 10. Docker Commands

### Start All Services (Detached mode with rebuild)
```bash
docker compose up -d --build
```

### Check Service Status & Health
```bash
docker compose ps
```

### View Aggregated Logs
```bash
docker compose logs -f
```

### View Specific Service Logs
```bash
docker compose logs -f backend
docker compose logs -f celery_worker
```

### Stop All Services
```bash
docker compose down
```

### Stop Services & Remove Persistent Volumes (Data Reset)
```bash
docker compose down -v
```

---

## 11. Backend Startup Commands (Local Development)

If running directly on the host using the local virtual environment:

```bash
# Activate environment
source .venv/bin/activate

# Start FastAPI server
uvicorn backend.app.main:app --host 0.0.0.0 --port 8035 --reload

# Start Celery Worker
celery -A backend.app.workers.celery_app.celery_app worker --loglevel=info
```

### Interactive API Documentation
- Swagger UI: `http://localhost:8035/api/v1/docs`
- ReDoc: `http://localhost:8035/api/v1/redoc`
- OpenAPI JSON Schema: `http://localhost:8035/api/v1/openapi.json`

---

## 12. Database Migrations (Alembic)

```bash
# Check current migration revision
alembic -c backend/alembic.ini current

# Generate an autogenerated revision
alembic -c backend/alembic.ini revision --autogenerate -m "create_initial_schema"

# Apply all pending migrations
alembic -c backend/alembic.ini upgrade head

# Rollback one migration revision
alembic -c backend/alembic.ini downgrade -1
```

---

## 13. Testing Commands

Run the comprehensive Pytest suite:

```bash
source .venv/bin/activate
pytest -v
```

The test suite covers:
- **Application Initialization & Lifespan**: Startup/teardown handler behavior
- **Configuration & Environment**: Pydantic Settings parsing, URI formatting, CORS parsing
- **Health Endpoints**: Root `/health` and `/api/v1/health` with service status validation
- **Database Connectivity**: Live PostgreSQL connection validation via `SELECT 1`
- **Redis Connectivity**: Live Redis PING, write, read, and delete operations
- **Celery Execution**: Task configuration, direct execution, and asynchronous live worker round-trip

---

## 14. Current Implementation Status & Roadmap

### Phase 1: Project Initialization & Infrastructure Foundation (COMPLETED)
- [x] Target directory structure established.
- [x] Python virtual environment configured with pinned, bounded dependencies.
- [x] FastAPI modular architecture implemented (`main.py`, `api/v1`, structured logging, CORS).
- [x] PostgreSQL 16 service configured in Docker Compose with health checks and persistent storage.
- [x] SQLAlchemy 2.x engine, connection pool, and session dependency injection built.
- [x] Redis 7 Alpine configured with authentication, persistence, and connection pooling.
- [x] Celery worker configured with Redis broker/backend and verification task.
- [x] Alembic migration environment initialized and dynamically connected to app settings.
- [x] Docker Compose multi-service topology operational (`postgres`, `redis`, `backend`, `celery_worker`).
- [x] Pytest suite passes 100% of tests.
- [x] Security controls verified (no secrets in source, non-root Docker user, `.gitignore`).

### Phase 2: Data Engineering & Pipeline Foundations (COMPLETED)
- [x] Established normalized PostgreSQL business schema (`categories`, `products`, `branches`, `warehouses`, `suppliers`, `product_suppliers`, `inventory`, `daily_sales`, `data_import_logs`, `data_quality_results`).
- [x] Generated and applied transactional Alembic schema migrations.
- [x] Downloaded and integrated public Kaggle Store Sales benchmark dataset (`stores.csv`, `train.csv`).
- [x] Developed robust chunked ETL pipeline (`extract.py`, `transform.py`, `load.py`).
- [x] Implemented explicit data quality validation framework with metric persistence (`quality.py`).
- [x] Developed reproducible synthetic inventory and supplier generator with fixed seed (`inventory_generator.py`).
- [x] Distinctly labeled synthetic and public data via `data_origin` (`KAGGLE_PUBLIC` vs `SYNTHETIC`).
- [x] Integrated background ETL tasks with Celery (`import_sales_dataset`, `validate_dataset`, `generate_synthetic_inventory`).
- [x] Implemented versioned REST API endpoints for catalog, sales, branches, inventory, and pipeline monitoring.
- [x] Pytest suite expanded to 30 tests covering models, ETL, validation, synthetic data, Celery, and APIs.
- [x] Published complete architecture and schema documentation in `docs/`.

### Phase 3.1: Historical Data Preparation & Time-Series Feature Engineering (COMPLETED)
- [x] Staged historical ingestion workflow implemented (`scripts/ingest_historical_data.py`).
- [x] 1-year continuous historical baseline (648,648 rows) loaded in PostgreSQL without duplicates.
- [x] Analysis of zero sales (31.30%) vs missing records (Christmas Day closures) documented.
- [x] External datasets integrated (`oil.csv` continuous interpolation, `holidays_events.csv` deduplication, `transactions.csv`, store metadata).
- [x] Modular feature pipeline implemented (`calendar_features.py`, `external_features.py`, `lag_features.py`, `rolling_features.py`).
- [x] Zero future leakage verified through shifted rolling aggregations and unit test proof.
- [x] Chronological, non-overlapping train/validation/test splitting implemented (`time_series_split.py`).
- [x] Training-ready feature dataset builder implemented (`dataset_builder.py`) producing Parquet artifacts in `ml/data/processed/`.
- [x] Pytest suite expanded to 42 tests passing with 100% success rate.
- [x] Documentation completed under `docs/ml/`.

### Phase 3.2: Demand Forecasting Models & Production Evaluation (COMPLETED)
- [x] Feature availability audit conducted and strict zero-leakage forecasting policy established (`docs/ml/feature-availability-audit.md`).
- [x] Unobserved contemporaneous foot-traffic (`transactions`) excluded from feature matrix.
- [x] Seasonal Naive baseline implemented with weekly lookback ($T-7$) and store-product isolation (`ml/models/seasonal_naive.py`).
- [x] Global LightGBM forecaster implemented with native categorical splits and early stopping (`ml/models/lightgbm_model.py`).
- [x] Global XGBoost forecaster implemented with histogram tree method and early stopping (`ml/models/xgboost_model.py`).
- [x] Standardized evaluation suite implemented (`ModelEvaluator`) with zero-safe WAPE, RMSLE, RMSE, and MAE.
- [x] Model comparison conducted on validation set: LightGBM selected as champion (13.09% WAPE vs 17.67% Seasonal Naive).
- [x] Untouched test set evaluated on holiday demand surge: LightGBM achieved 21.55% WAPE (vs 27.48% baseline).
- [x] Recursive multi-step prediction engine implemented (`ForecastingPredictor`) for 7-day (13.87% WAPE), 14-day (16.72% WAPE), and 30-day (26.12% WAPE) horizons.
- [x] Model registry and artifact persistence implemented (`ml/training/model_registry.py`).
- [x] Pytest suite expanded to 55 tests passing with 100% success rate.
- [x] Documentation completed under `docs/ml/`.

### Phase 3.3: Intelligent Inventory Optimization, Stockout Risk & Replenishment Decision Engine (COMPLETED)
- [x] **Inventory & Forecast Integration**: Unified available stock calculations ($I_{\text{physical}} - I_{\text{reserved}}$) with multi-horizon LightGBM recursive forecasts (`InventoryService`, `ForecastIntegrationService`).
- [x] **Module A: Safety Stock & Dynamic Reorder Point**: Lead-time cumulative demand ($d_L = \sum_{t=1}^L \hat{y}_t$), genuine out-of-sample forecast error quantification, empirical quantile safety stock ($SS = \max(0, \text{Quantile}(e_L, \alpha))$), normal approximation fallback, and dynamic $ROP = d_L + SS$ (`SafetyStockService`).
- [x] **Module B: Stockout Risk Engine**: Monte Carlo residual bootstrap forward simulation ($M = 1,000$ scenarios), stockout probability estimation, severity classification (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), and expected stockout calendar day calculation (`StockoutRiskService`).
- [x] **Module C: Constrained EOQ & Replenishment**: Classical Wilson EOQ balancing inventory carrying cost ($H = c \cdot h_{\text{rate}}$) against procurement cost ($S = \$50.00$), supplier minimum order quantity ($MOQ$) and integer packaging multiples enforcement, order-up-to target stock ($S_{\text{target}} = ROP + Q^*$), and explainable natural-language recommendations (`EOQService`, `ReplenishmentService`).
- [x] **Module D: Discrete Inventory Policy Simulation**: Daily discrete-time backtester strictly respecting conservation laws and zero lookahead bias; historical backtest on December 2013 data comparing baseline static vs optimized dynamic policy (`InventorySimulationService`).
- [x] **Module E: Unified Inventory Decision Engine**: End-to-end orchestration returning structured `InventoryDecisionResult` objects and network-wide paginated summary (`UnifiedInventoryDecisionEngine`).
- [x] **REST API Inventory Endpoints**: Full suite of endpoints deployed under `/api/v1/inventory` (`/safety-stock`, `/reorder-point`, `/stockout-risk`, `/eoq`, `/replenishment`, `/decision`, `/optimization-summary`, `/simulations`).
- [x] **Automated Test Suite**: 97 tests passing with 100% success rate across backend and ML subsystems.
- [x] **Comprehensive Documentation**: Architectural audit, complete mathematical derivations, and worked numerical examples published in `docs/inventory/`.

### Phase 4.1: Sales Anomaly Detection System (COMPLETED)
- [x] **Module A: Robust Statistical Anomaly Detection**: Rolling baseline evaluation using Median Absolute Deviation (MAD), robust Z-score ($Z_{\text{robust}} = \frac{0.6745(x_t - \operatorname{med}(X))}{\operatorname{MAD}(X)}$), Interquartile Range (IQR), zero-MAD division safeguards, and strict historical exclusion ($X \subset [t-28, t-1]$) (`StatisticalAnomalyDetector`).
- [x] **Module B: Forecast Residual Anomaly Detection**: Standardized forecast deviation ($Z_{\text{forecast}} = \frac{(A_t - F_t) - \mu_e}{\sigma_e}$) normalized by empirical out-of-sample error dispersion from the November 2013 validation set with hierarchical fallback (`ForecastResidualAnomalyDetector`).
- [x] **Module C: ML Isolation Forest Detector**: Trained on chronological training features ($\le \text{2013-10-31}$) across 8 temporal and contextual features; serialized artifact saved to `ml/artifacts/isolation_forest_v1.joblib` (`MLIsolationForestDetector`).
- [x] **Module D: Hybrid Anomaly Scorer**: Dynamic weight renormalization on missing/sparse detector evidence, severity classification (`NORMAL`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), and directional classification (`SPIKE`, `DROP`, `ZERO_SALES`, `FORECAST_DEVIATION`, `TREND_SHIFT`) (`HybridAnomalyScorer`).
- [x] **Module E: Contextual Business Explanation Service**: Multi-tier plain-language explanation synthesis separating confirmed numerical evidence, contextual operational hypotheses, and prioritized audit actions (`AnomalyExplanationService`).
- [x] **Module F: Synthetic Evaluation Benchmark**: Isolated in-memory evaluation benchmark on controlled shock perturbations (+250% surge, -85% drop, zero sales, sustained shifts) with 100.0% recall on injected shocks and 6.25% false alarm rate on clean historical baselines (`SyntheticAnomalyInjector`).
- [x] **Module G & H: Persistence, Celery & REST APIs**: Created tables `anomaly_detection_runs` and `sales_anomalies` via Alembic migration (`40e430e6db84`), implemented idempotent Celery background task `detect_sales_anomalies`, and exposed 6 REST endpoints under `/api/v1/anomalies`.
- [x] **Automated Test Suite**: 150 automated tests passing with 100% success rate across backend and ML subsystems.
- [x] **Comprehensive Documentation**: Architectural guide, mathematical methodology, synthetic benchmark evaluation, REST API guide, and formal completion report published under `docs/anomaly-detection/`.

### Phase 4.2: GenAI Executive Business Assistant & Conversational Agent (PLANNED)
- [ ] RAG pipeline for inventory documents, supply chain contracts, and SOPs.
- [ ] Natural Language to SQL analytics agent with strict security boundaries and schema sandboxing.
