# Time-Series Feature Engineering

## 1. Feature Architecture Overview

The SmartDist AI time-series feature engineering pipeline is implemented in `ml/features/`:

```
ml/features/
  ├── __init__.py
  ├── calendar_features.py     # Temporal and calendar features
  ├── external_features.py     # Oil prices, holidays, transactions, store metadata
  ├── lag_features.py          # Autoregressive historical lags
  ├── rolling_features.py      # Shifted rolling statistical aggregations
  └── feature_pipeline.py      # End-to-end transformation coordinator
```

## 2. Complete Feature Catalog (30 Features)

| Category | Feature Name | Type | Description |
|---|---|---|---|
| **Identifiers** | `store_nbr` | Categorical / int | Retail branch source store number (1..54) |
| | `product_id` | Categorical / int | Master product ID (1..33) |
| **Calendar** | `year` | int32 | Year (e.g. 2013) |
| | `month` | int8 | Calendar month (1..12) |
| | `day` | int8 | Day of month (1..31) |
| | `day_of_week` | int8 | Day of week (0=Monday, 6=Sunday) |
| | `day_of_month` | int8 | Day of month |
| | `week_of_year` | int8 | ISO calendar week number (1..53) |
| | `quarter` | int8 | Calendar quarter (1..4) |
| | `is_weekend` | int8 | Binary indicator (1 if Saturday or Sunday, else 0) |
| | `is_month_start`| int8 | Binary indicator (1 if day == 1, else 0) |
| | `is_month_end` | int8 | Binary indicator (1 if final calendar day of month, else 0) |
| **External** | `oil_price` | float64 | Continuous crude oil price (WTI) with weekend/holiday forward-fill |
| | `transactions` | int32 | Daily customer transaction volume for that store |
| | `is_holiday` | int8 | Binary indicator for non-transferred holiday/event |
| | `is_national_holiday` | int8 | Binary indicator for national-level holidays |
| | `is_work_day` | int8 | Binary indicator for work-day status |
| | `holiday_type` | category | Event type ('Holiday', 'Event', 'Bridge', 'None') |
| | `store_type` | category | Store classification ('A', 'B', 'C', 'D', 'E') |
| | `store_cluster`| int64 | Geographical / demographic store cluster (1..17) |
| | `promotion_quantity` | int32 | Item promotional volume on that date |
| **Lags** | `lag_1` | float64 | Sales quantity on day $T - 1$ |
| | `lag_7` | float64 | Sales quantity on day $T - 7$ (same day previous week) |
| | `lag_14` | float64 | Sales quantity on day $T - 14$ (2-week seasonal lag) |
| | `lag_28` | float64 | Sales quantity on day $T - 28$ (4-week monthly cycle lag) |
| **Rolling** | `rolling_mean_7` | float64 | 7-day rolling mean of $T-7 \dots T-1$ |
| | `rolling_std_7` | float64 | 7-day rolling std of $T-7 \dots T-1$ |
| | `rolling_mean_14`| float64 | 14-day rolling mean of $T-14 \dots T-1$ |
| | `rolling_std_14`| float64 | 14-day rolling std of $T-14 \dots T-1$ |
| | `rolling_mean_28`| float64 | 28-day rolling mean of $T-28 \dots T-1$ |
| | `rolling_std_28`| float64 | 28-day rolling std of $T-28 \dots T-1$ |

**Target Column**: `quantity_sold` (`float64`). Never use `sales_amount` as the modeling target.

## 3. Strict Leakage Prevention Mechanics

### The Rolling Leakage Hazard
Calculating rolling statistics on an unshifted target introduces instantaneous leakage:
$$\text{rolling\_mean}_W(T) = \frac{1}{W} \sum_{i=0}^{W-1} y_{T - i}$$
If $i=0$ is included, $y_T$ (the target to be predicted) directly contaminates the feature!

### Enforced Shifted Rolling Implementation
In `RollingFeatureExtractor.add_rolling_features`:
```python
# Target shifted by 1 before any rolling window computation
res["_target_shifted_1"] = res.groupby(group_cols)["quantity_sold"].shift(1)

# Rolling window strictly aggregates T-W through T-1
res["rolling_mean_W"] = (
    res.groupby(group_cols)["_target_shifted_1"]
    .rolling(window=W, min_periods=min(3, W))
    .mean()
)
```

Verified by unit test [`test_rolling_features_zero_future_leakage`](../../backend/tests/test_phase3_features.py#L65-L125):
When target $y_T$ on day 10 is mutated from $10.0$ to $999,999.0$, `rolling_mean_7` on day 10 remains exactly $10.0$ with zero variation.
