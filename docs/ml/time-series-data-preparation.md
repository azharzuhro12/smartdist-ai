# Time-Series Data Preparation & Historical Ingestion

## 1. Overview & Dataset Profile

SmartDist AI utilizes the benchmark **Kaggle Store Sales — Time Series Forecasting** dataset (`train.csv`), spanning from **2013-01-01** to **2017-08-15** (1,684 active days across 4.5 years).

### Dimensions & Granularity
- **Store Branches**: 54 physical retail stores across Ecuador.
- **Product Families**: 33 merchandise families.
- **Daily Combinations**: $54 \times 33 = 1,782$ individual store-product time-series per day.
- **Total Dataset Size**: 3,000,888 rows (~117 MB).

## 2. Missing Combinations & Zero Sales Analysis

In time-series retail forecasting, conflating missing observations with zero sales introduces severe model bias. Through empirical validation across the entire 3,000,888 rows, we established:

1. **Observed Zero Sales (939,130 records = 31.30%)**:
   - Store was open, records exist in `train.csv`, but `sales == 0.0`.
   - Preserved as true zeroes (`quantity_sold = 0.0`) representing non-demand or uncarried inventory for that day.
2. **Missing Source Records (Exactly 4 calendar days)**:
   - Calendar days between `2013-01-01` and `2017-08-15`: 1,688 days.
   - Distinct dates in `train.csv`: 1,684 days.
   - Missing dates: `['2013-12-25', '2014-12-25', '2015-12-25', '2016-12-25']`.
   - **Root Cause**: Christmas Day closures across all Ecuadorian retail stores.
3. **Daily Row Uniformity**:
   - For all 1,684 recorded dates, exactly 1,782 records exist per day ($54 \times 33$). There are **zero** partial days or missing store-family combinations in raw observations.

## 3. Staged Historical Ingestion Architecture

Attempting to ingest 3,000,888 rows in a single synchronous Celery task exceeds the Celery soft time limit (`task_soft_time_limit = 240s`).

We designed a resumable, staged ingestion architecture:

```
[Raw train.csv (117MB)]
         |
         v
[DataExtractor.extract_daily_sales_stream(chunk_size=25,000)]
         |
         v (Chronological filter: start_date <= date <= end_date)
[DataQualityValidator.validate_sales_chunk()]
         |
         v (Clean validated rows)
[DataTransformer.transform_sales_chunk()]
         |
         v (Batches of 5,000 rows)
[DataLoader.load_daily_sales_batch(ON CONFLICT DO UPDATE)]
         |
         v
[PostgreSQL daily_sales]
```

### CLI Ingestion Commands (`scripts/ingest_historical_data.py`)

```bash
# Ingest full historical baseline year (2013)
./scripts/ingest_historical_data.py --year 2013

# Ingest specific calendar interval
./scripts/ingest_historical_data.py --start-date 2013-07-01 --end-date 2013-12-31

# Progressive quarterly ingestion of entire 4.5-year history
./scripts/ingest_historical_data.py --all
```

### Measured Ingestion Speeds
- **50,000 rows**: ~12 seconds.
- **2013-H1 (322,542 rows)**: 241 seconds (~4.0 minutes).
- **2013-H2 (326,106 rows)**: 267 seconds (~4.4 minutes).
- **Full Year 2013 (648,648 rows)**: Loaded in PostgreSQL with 100% data integrity and zero duplicates.
