# Data Flow Architecture

This document describes how operational and analytical data flows between ingestion sources, processing workers, relational storage, and API clients.

```mermaid
flowchart TD
    RawCSV["Raw CSV Files\n(stores.csv, train.csv)"] -->|Chunked Stream| Extractor["DataExtractor\n(Pandas Stream)"]
    Extractor --> Validator["DataQualityValidator\n(Constraint Checks)"]
    
    Validator -->|Quality Metrics| DQTable[("PostgreSQL\ndata_quality_results")]
    Validator -->|Clean Data| Transformer["DataTransformer\n(Domain Mapping)"]
    
    Transformer --> Loader["DataLoader\n(Batch Upsert)"]
    Loader --> LogTable[("PostgreSQL\ndata_import_logs")]
    Loader --> DBTables[("PostgreSQL\nbranches, products,\ndaily_sales")]
    
    SynGen["SyntheticInventoryGenerator\n(Seed=42)"] --> DBInv[("PostgreSQL\nwarehouses, suppliers,\ninventory")]

    FastAPI["FastAPI REST Endpoints\n(/api/v1/data, /sales, /inventory)"] -->|Query| DBTables
    FastAPI -->|Query| DBInv
    FastAPI -->|Dispatch Task| CeleryBroker["Redis Broker\n(Port 6380)"]
    CeleryBroker --> CeleryWorker["Celery Worker\n(ETL Background Execution)"]
    CeleryWorker --> Loader
```

## Data Lifecycle

1. **Extraction**: Raw files in `ml/data/raw` are streamed without memory spikes.
2. **Quality Verification**: Each batch is validated against referential and domain rules before touching persistent storage.
3. **Audit Tracking**: Import execution timestamps, processed rows, and rejected counts are recorded.
4. **Consumption**: Downstream analytical endpoints read indexed tables with sub-millisecond retrieval speeds.
