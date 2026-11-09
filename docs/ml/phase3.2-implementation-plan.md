# SmartDist AI — Phase 3.2 Implementation Plan
## Demand Forecasting Models & Production Evaluation Architecture

**Author**: Senior Machine Learning Engineer  
**Date**: November 9, 2026  
**Status**: APPROVED FOR IMPLEMENTATION  
**Target Target**: `quantity_sold` (Continuous daily sales volume)

---

## 1. Executive Summary & Verification of Existing Foundation

The objective of Phase 3.2 is to build, evaluate, compare, and serialize production-grade demand forecasting models for SmartDist AI on historical sales records.

### 1.1 Inspection of Processed Data Artifacts
The training-ready Parquet partitions in `ml/data/processed/` were audited directly:

| Partition | Date Range | Distinct Days | Total Rows | File Size | Nulls | Infs |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Train** | `2013-01-29` to `2013-10-31` | 276 days | 491,832 | 14.1 MB | 0 | 0 |
| **Validation** | `2013-11-01` to `2013-11-30` | 30 days | 53,460 | 1.7 MB | 0 | 0 |
| **Test** | `2013-12-01` to `2013-12-31` | 30 days* | 53,460 | 1.7 MB | 0 | 0 |
| **Total** | `2013-01-29` to `2013-12-31` | 336 active days | 598,752 | 17.5 MB | 0 | 0 |

*\*Note on Test set: Ecuador stores were closed on Christmas Day (`2013-12-25`), resulting in exactly 30 active days (30 × 1,782 = 53,460 rows).*

### 1.2 Target & Feature Auditing
- **Forecasting Target**: `quantity_sold` (float64).
  - Mean: 208.91 (Train), 231.14 (Validation), 295.61 (Test).
  - Zero-demand frequency: ~31.3% of series-days contain 0.0 sales.
  - Constraint: `sales_amount` is an estimated revenue metric derived from reference pricing; it is **strictly excluded** from ML training and evaluation.
- **Feature Set Audit**:
  - Total columns: 34 (1 date, 2 series IDs, 1 family name, 1 target `quantity_sold`, 29 predictor features).
  - Lags: `lag_1`, `lag_7`, `lag_14`, `lag_28` computed within isolated `(store_nbr, product_id)` series.
  - Rolling Features: `rolling_mean_W`, `rolling_std_W` ($W \in \{7, 14, 28\}$) computed with a strict 1-day lag shift before the window, eliminating contemporaneous leakage ($y_T$ cannot leak into features at time $T$).
  - Calendar Features: Year, month, day, day_of_week, day_of_month, week_of_year, quarter, is_weekend, is_month_start, is_month_end.
  - External Features: `oil_price`, `is_holiday`, `is_national_holiday`, `is_work_day`, `holiday_type`, `transactions`, `promotion_quantity`, `store_type`, `store_cluster`.

---

## 2. Proposed Architecture for Phase 3.2

```
ml/
├── models/
│   ├── __init__.py
│   ├── base.py                   # BaseForecaster abstract interface
│   ├── seasonal_naive.py         # Seasonal Naive baseline (T-7)
│   ├── lightgbm_model.py         # LightGBM Regressor with early stopping
│   └── xgboost_model.py          # XGBoost Regressor with early stopping
├── training/
│   ├── __init__.py
│   ├── evaluator.py              # MAE, RMSE, WAPE, RMSLE with zero checks
│   ├── model_registry.py         # Metadata, serialization, model loader
│   └── train.py                  # CLI and orchestration for model training
├── inference/
│   ├── __init__.py
│   └── predictor.py              # Recursive multi-step forecaster (7, 14, 30 days)
└── artifacts/
    ├── .gitkeep
    └── ...                       # Serialized models & metadata (.joblib, .json)
```

### 2.1 Model Specifications
1. **Seasonal Naive Baseline**:
   - Forecasts $\hat{y}_T = y_{T-7}$ per `(store_nbr, product_id)` pair.
   - Fallback: If $T-7$ is unobserved, use the latest observed value or 0.0.
   - Non-negative guarantee: $\max(0, \hat{y})$.
2. **LightGBM Forecaster**:
   - Objective: `regression` (L2 loss) or `huber` / `tweedie`.
   - Native categorical feature support for `store_type`, `holiday_type`, `store_cluster`, `product_id`, `family`.
   - Validation-based early stopping (e.g. 50 rounds) on `val_features.parquet`.
   - Seed: 42.
3. **XGBoost Forecaster**:
   - Objective: `reg:squarederror`.
   - Explicit encoding of categorical features (categorical dtype support or label/ordinal encoding).
   - Validation-based early stopping on `val_features.parquet`.
   - Seed: 42.

---

## 3. Metric Definitions & Production Evaluation

1. **Mean Absolute Error (MAE)**:
   $$\text{MAE} = \frac{1}{N} \sum_{i=1}^{N} |y_i - \hat{y}_i|$$
2. **Root Mean Squared Error (RMSE)**:
   $$\text{RMSE} = \sqrt{\frac{1}{N} \sum_{i=1}^{N} (y_i - \hat{y}_i)^2}$$
3. **Weighted Absolute Percentage Error (WAPE)**:
   $$\text{WAPE} = \frac{\sum_{i=1}^{N} |y_i - \hat{y}_i|}{\sum_{i=1}^{N} |y_i|} \times 100$$
   *Zero-denominator safety*: If $\sum |y_i| = 0$, return `0.0` if $\sum |\hat{y}_i| = 0$, else return `float('nan')` with explicit reporting.
4. **Root Mean Squared Logarithmic Error (RMSLE)**:
   $$\text{RMSLE} = \sqrt{\frac{1}{N} \sum_{i=1}^{N} \left(\ln(1 + \max(0, \hat{y}_i)) - \ln(1 + y_i)\right)^2}$$
   *Safety*: Clip negative predictions $\hat{y}_i < 0$ to $0.0$. Never alter true observed target $y_i$.

---

## 4. Multi-Horizon Recursive Forecasting Protocol

Forecasting horizons: **7-day**, **14-day**, and **30-day**.

- **One-Step-Ahead (Static Lag) Evaluation**: Uses historical observed actuals at each step. Valid for validating model fit on historical datasets, but optimistic for multi-day deployment.
- **Recursive Multi-Step Forecasting (True Deployment)**:
  - Step 1 ($t = T+1$): Uses actual historical lags. Generates $\hat{y}_{T+1}$.
  - Step 2 ($t = T+2$): Computes `lag_1` using $\hat{y}_{T+1}$. Updates rolling statistics dynamically.
  - Step $h$ ($t = T+h$): All lags within the forecast window ($< h$) utilize generated predictions.
  - **Leakage Prevention**: Strictly prevents looking up future true actual values $y_{T+k}$ during recursion.

---

## 5. Potential Risks & Engineering Mitigations

1. **Contemporaneous Feature Leakage (`transactions`)**:
   - *Risk*: `transactions` represents daily store foot traffic on date $T$. At inference time for date $T+1 \dots T+30$, actual foot traffic is unknown.
   - *Mitigation*: Exclude raw contemporaneous `transactions` from inference feature policy or lag it by $\ge 1$ day. (Detailed in Feature Availability Audit).
2. **Oil Price Future Unavailability**:
   - *Risk*: Future crude oil prices for next 30 days are unknown at time $T$.
   - *Mitigation*: Forward-fill from the last known trading day ($T_0$).
3. **Extreme Zero Inflation**:
   - *Risk*: Standard linear models or unconstrained regressors produce negative numbers.
   - *Mitigation*: Enforce non-negative post-prediction clipping ($\max(0, \hat{y})$) across all models.
4. **Data Isolation**:
   - *Risk*: Training on validation data or tuning on test data.
   - *Mitigation*: Strictly tune and select model on `val_features.parquet`. Evaluate on `test_features.parquet` exactly once.
