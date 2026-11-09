# ETL Pipeline Architecture

## 1. Overview

The SmartDist AI ETL pipeline extracts raw retail datasets, enforces data quality rules, transforms columns into normalized domain entities, and batch-loads records into PostgreSQL with full audit tracking.

```
+-------------------------------------------------------------+
|                     1. Extraction Stage                     |
|  - DataExtractor.extract_stores()                           |
|  - DataExtractor.extract_categories_and_products()          |
|  - DataExtractor.extract_daily_sales_stream(chunk_size)     |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|                     2. Validation Stage                     |
|  - DataQualityValidator.validate_stores_data()              |
|  - DataQualityValidator.validate_sales_chunk()              |
|  - Persists metrics to data_quality_results                 |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|                   3. Transformation Stage                   |
|  - Map store_nbr to Branch entities                         |
|  - Map family to Category & Product master SKUs             |
|  - Parse dates, compute monetary sales_amount               |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|                      4. Loading Stage                       |
|  - DataLoader.load_branches()                               |
|  - DataLoader.load_categories_and_products()                |
|  - DataLoader.load_daily_sales_batch() (ON CONFLICT DO UPDATE)|
|  - SyntheticInventoryGenerator.generate_*()                 |
|  - Updates data_import_logs status and execution metrics    |
+-------------------------------------------------------------+
```

## 2. Chunked Streaming for High Volumes

`train.csv` contains over 3 million rows (116 MB). To maintain predictable memory usage, `DataExtractor.extract_daily_sales_stream` uses a generator pattern reading chunks of configurable sizes (default: 25,000–50,000 rows). Chunks are validated and batch-inserted within individual transaction boundaries.

## 3. Idempotent Upserts

The loader utilizes PostgreSQL `ON CONFLICT DO UPDATE` based on the unique composite constraint `(sale_date, branch_id, product_id)`. Re-running the pipeline on overlapping periods updates sales values without producing duplicate records.

## 4. Background Execution via Celery

Long-running ingestion runs in the background using Celery task `backend.app.workers.tasks.import_sales_dataset`. Clients invoke `POST /api/v1/data/import`, receive a `task_id`, and monitor progress through `GET /api/v1/data/import/{task_id}` without blocking HTTP connections.
