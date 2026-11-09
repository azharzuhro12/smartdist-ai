# SmartDist AI — Demand Forecasting Model Training
## Training Methodology, Hyperparameters & Pipeline Orchestration

**Author**: Senior Machine Learning Engineer  
**Date**: November 9, 2026  
**Status**: VERIFIED & REPRODUCIBLE  

---

## 1. Training Setup & Hardware Configuration

- **Environment**: Linux x86_64, Python 3.14.7.
- **Compute**: Multi-threaded CPU parallelization (`n_jobs=-1`).
- **Dependencies**: Scikit-Learn 1.9.1, LightGBM 4.7.0, XGBoost 3.4.1, Joblib 1.6.0.
- **Random Seed**: `42` (Enforced across all stochastic components for 100% reproducibility).

---

## 2. Partition Strategy

The time-series dataset is split chronologically into non-overlapping partitions:

| Partition | Date Range | Duration | Series Count | Total Samples | Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Train** | `2013-01-29` to `2013-10-31` | 276 days | 1,782 | 491,832 | Model parameter estimation |
| **Validation** | `2013-11-01` to `2013-11-30` | 30 days | 1,782 | 53,460 | Early stopping & model selection |
| **Test** | `2013-12-01` to `2013-12-31` | 30 days | 1,782 | 53,460 | Final unbiased evaluation |

*Note*: The first 28 days of January 2013 were dropped during feature engineering to initialize `lag_28` and `rolling_mean_28`.

---

## 3. Approved Feature Matrix (28 Features)

Contemporaneous store foot-traffic (`transactions`) was **strictly excluded** due to unobservability at forecast time.

```python
APPROVED_FEATURE_COLS = [
    # Static Entity Identifiers
    "store_nbr", "product_id", "store_type", "store_cluster",
    # Calendar Attributes
    "year", "month", "day", "day_of_week", "day_of_month",
    "week_of_year", "quarter", "is_weekend", "is_month_start", "is_month_end",
    # Scheduled External Predictors
    "oil_price", "is_holiday", "is_national_holiday", "is_work_day",
    "holiday_type", "promotion_quantity",
    # Autoregressive Lags
    "lag_1", "lag_7", "lag_14", "lag_28",
    # Shifted Rolling Statistics
    "rolling_mean_7", "rolling_std_7",
    "rolling_mean_14", "rolling_std_14",
    "rolling_mean_28", "rolling_std_28",
]
```

---

## 4. Model Hyperparameters

### 4.1 Seasonal Naive Baseline
- `seasonality`: 7 days.
- Lookback rule: $\hat{y}_{t} = y_{t - 7}$.
- Fallback: Latest observed series demand or 0.0.

### 4.2 LightGBM Forecaster
- `objective`: `regression` (L2 loss).
- `metric`: `rmse`.
- `n_estimators`: 400.
- `learning_rate`: 0.05.
- `num_leaves`: 63.
- `subsample`: 0.8.
- `colsample_bytree`: 0.8.
- `early_stopping_rounds`: 30 (evaluated on validation set).
- `categorical_features`: `["store_type", "holiday_type", "store_cluster", "product_id"]`.

### 4.3 XGBoost Forecaster
- `objective`: `reg:squarederror`.
- `eval_metric`: `rmse`.
- `n_estimators`: 400.
- `learning_rate`: 0.05.
- `max_depth`: 6.
- `subsample`: 0.8.
- `colsample_bytree`: 0.8.
- `tree_method`: `hist`.
- `enable_categorical`: `True`.
- `early_stopping_rounds`: 30.

---

## 5. Execution Command

The pipeline is triggered via:
```bash
source .venv/bin/activate
PYTHONPATH=. python3 ml/training/train.py --save
```
Training the full suite (Seasonal Naive, LightGBM, XGBoost, Validation Comparison, Test Evaluation, and Multi-Horizon Recursion) executes in approximately **35 seconds**.
