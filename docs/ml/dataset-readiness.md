# Machine Learning Dataset Readiness

## 1. Executive Summary

Phase 3.1 has verified and generated training-ready feature datasets stored in columnar Parquet format under `ml/data/processed/`.

## 2. Processed Artifact Inventory

| Artifact Path | Format | Row Count | Memory / Disk Size | Description |
|---|---|---|---|---|
| `ml/data/processed/train_features.parquet` | Parquet (Snappy) | 491,832 | 14 MB | Training partition ($T \le \text{2013-10-31}$) |
| `ml/data/processed/val_features.parquet` | Parquet (Snappy) | 53,460 | 1.7 MB | Validation partition ($\text{2013-11-01} \dots \text{2013-11-30}$) |
| `ml/data/processed/test_features.parquet` | Parquet (Snappy) | 53,460 | 1.7 MB | Holdout test partition ($\text{2013-12-01} \dots \text{2013-12-31}$) |

## 3. Data Integrity & Schema Compliance

- **Target Column**: `quantity_sold` (Continuous float).
- **Synthetic Data Isolation**: 0 synthetic inventory or supplier records in the training/validation/test datasets.
- **NaN Profile**: 0 missing values across all 30 engineered feature columns after initial lag warmup drop ($T \ge 29$).
- **Bitwise Reproducibility**: Tested and verified by [`test_dataset_builder_reproducibility`](file:///home/zarr/Documents/smartdist-ai/backend/tests/test_phase3_builder.py#L48-L58).

## 4. Transition Criteria to Phase 3.2 (Model Training)

1. [x] 1-year historical baseline loaded in PostgreSQL (648,648 rows).
2. [x] Calendar, external, lag, and shifted rolling features implemented.
3. [x] Zero future leakage demonstrated through unit tests.
4. [x] Chronological non-overlapping data splits generated.
5. [x] Full test suite passing (42 tests).
6. [x] LightGBM, XGBoost, Scikit-learn compatibility verified.
