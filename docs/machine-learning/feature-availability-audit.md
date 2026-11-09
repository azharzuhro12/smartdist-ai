# SmartDist AI — Feature Availability & Leakage Audit
## Forecasting Feature Policy & Operational Inference Protocol

**Author**: Senior Machine Learning Engineer & MLOps Specialist  
**Phase**: 3.2 Demand Forecasting Model Development  
**Audited Datasets**: `ml/data/processed/*.parquet`  
**Target Variable**: `quantity_sold` (Continuous daily sales units)

---

## 1. Feature Classification Framework

In operational demand forecasting, a model cannot condition on future information that has not yet materialized at the forecast decision point $T_0$. Every feature generated in the Phase 3.1 feature engineering pipeline is classified into one of three distinct categories:

### Category A: Known in Advance (Deterministic & Exogenous)
These features are known with 100% certainty for any forecast horizon $h \in [1, 30]$:
1. **Calendar Attributes**:
   - `year`, `month`, `day`, `day_of_week`, `day_of_month`, `week_of_year`, `quarter`, `is_weekend`, `is_month_start`, `is_month_end`.
   - *Availability*: Exact calendar calculations for any future timestamp $T_0 + h$.
2. **Store Static Metadata**:
   - `store_nbr`, `store_type`, `store_cluster`.
   - *Availability*: Fixed physical business attributes known in advance.
3. **Product Static Metadata**:
   - `product_id`, `family`.
   - *Availability*: Master catalog attributes known in advance.
4. **Official Holiday & Event Calendars**:
   - `is_holiday`, `is_national_holiday`, `is_work_day`, `holiday_type`.
   - *Availability*: Statutory public holidays and planned national events scheduled and published months in advance.

---

### Category B: Historically Observed (Autoregressive & Endogenous)
These features are derived strictly from past sales demand observed up to cut-off date $T_0$:
1. **Lag Features**:
   - `lag_1`: Demand at $t - 1$.
   - `lag_7`: Demand at $t - 7$.
   - `lag_14`: Demand at $t - 14$.
   - `lag_28`: Demand at $t - 28$.
2. **Rolling Statistics**:
   - `rolling_mean_7`, `rolling_std_7`: Mean and standard deviation over $[t-7, t-1]$.
   - `rolling_mean_14`, `rolling_std_14`: Mean and standard deviation over $[t-14, t-1]$.
   - `rolling_mean_28`, `rolling_std_28`: Mean and standard deviation over $[t-28, t-1]$.

#### Operational Multi-Horizon Availability Matrix for Category B
| Horizon $h$ | Target Date | `lag_1` Status | `lag_7` Status | `lag_14` Status | `lag_28` Status | Rolling Windows |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Day 1** ($T_0 + 1$) | Directly observed $y(T_0)$ | Directly observed | Directly observed | Directly observed | Directly observed | Directly observed |
| **Day 7** ($T_0 + 7$) | Predicted $\hat{y}(T_0 + 6)$ | Directly observed $y(T_0)$ | Directly observed | Directly observed | Recursive hybrid |
| **Day 14** ($T_0 + 14$) | Predicted $\hat{y}(T_0 + 13)$ | Predicted $\hat{y}(T_0 + 7)$ | Directly observed $y(T_0)$ | Directly observed | Recursive hybrid |
| **Day 30** ($T_0 + 30$) | Predicted $\hat{y}(T_0 + 29)$ | Predicted $\hat{y}(T_0 + 23)$ | Predicted $\hat{y}(T_0 + 16)$ | Predicted $\hat{y}(T_0 + 2)$ | Fully recursive |

*Policy Rule*: For multi-step recursive forecasting ($h > 1$), all Category B features are dynamically computed using previously generated model predictions $\hat{y}$. **Actual future target values $y(T_0 + k)$ are never looked up.**

---

### Category C: Potentially Unavailable at Forecast Time (Operational Risk)
Features that represent contemporaneous events occurring on day $t$ that are not known in advance:

#### 1. Daily Customer Transactions (`transactions`)
- **Nature**: Count of customer foot traffic entering store on day $t$.
- **Audit Finding**: In `train.csv` / `transactions.csv`, transactions are recorded simultaneously with sales. At the time of forecasting sales for next week, store foot traffic is not known. Conditioning on actual same-day transactions is a **severe contemporaneous target leakage**.
- **Forecasting Feature Policy**:
  - `transactions` **must be excluded** from the feature set used by the production forecasting model.
  - Baseline models, LightGBM, and XGBoost in Phase 3.2 will exclude contemporaneous `transactions`.

#### 2. Promotional Schedule (`promotion_quantity`)
- **Nature**: Number of SKUs on promotion on date $t$.
- **Audit Finding**: In retail distribution, circular promotions and marketing campaigns are typically planned 1 to 4 weeks in advance. However, unplanned spot promotions occur.
- **Forecasting Feature Policy**:
  - If a retailer provides planned promotion schedules, `promotion_quantity` is valid.
  - If not planned, it must be assumed 0.0 or forward-filled.
  - In Phase 3.2, `promotion_quantity` is retained as an exogenous feature, with the assumption that promotional schedules are pre-planned by merchandising.

#### 3. Crude Oil Price (`oil_price`)
- **Nature**: Daily WTI spot crude oil price (macroeconomic indicator for Ecuador economy).
- **Audit Finding**: Future oil prices for $T_0 + 1 \dots T_0 + 30$ are unknown market variables.
- **Interpolation & Leakage Analysis**:
  - In historical preprocessing (`ExternalFeatureExtractor`), weekends and holidays were filled using `ffill().bfill()`.
  - *Risk*: A global backward-fill (`bfill()`) across the entire series would leak future prices into earlier dates.
  - *Verification*: In `ExternalFeatureExtractor`, `bfill()` only affects the initial missing weekend (e.g. `2013-01-01` when markets were closed for New Year's Day, backfilled from `2013-01-02`).
  - *Production Inference Rule*: At forecast time $T_0$, future oil prices are unknown. The operational policy is **constant forward-fill** from the last known trading day ($P(T_0 + h) = P(T_0)$). No future oil prices are queried.

---

## 2. Approved Production Feature Set

The following 28 features are approved for Phase 3.2 model training, validation, and inference:

```python
APPROVED_FEATURES = [
    # Static Entity Identifiers / Meta
    "store_nbr",
    "product_id",
    "store_type",
    "store_cluster",
    
    # Deterministic Calendar Features
    "year",
    "month",
    "day",
    "day_of_week",
    "day_of_month",
    "week_of_year",
    "quarter",
    "is_weekend",
    "is_month_start",
    "is_month_end",
    
    # Pre-scheduled Exogenous Calendars
    "is_holiday",
    "is_national_holiday",
    "is_work_day",
    "holiday_type",
    "promotion_quantity",
    "oil_price",  # Forward-filled from T_0
    
    # Autoregressive Lags (Recursive during multi-step)
    "lag_1",
    "lag_7",
    "lag_14",
    "lag_28",
    
    # Shifted Rolling Statistics (Recursive during multi-step)
    "rolling_mean_7",
    "rolling_std_7",
    "rolling_mean_14",
    "rolling_std_14",
    "rolling_mean_28",
    "rolling_std_28",
]
```

**Explicitly Excluded Feature**:
- `transactions` (Contemporaneous leakage).
- `sales_amount` (Derived revenue estimate, not observed sales demand).

---

## 3. Strict Zero-Leakage Implementation Checklist

- [x] Lags computed per isolated `(store_nbr, product_id)` group.
- [x] Rolling windows computed over target shifted by 1 day ($T-1$).
- [x] Train partition strictly strictly ends at `2013-10-31`.
- [x] Validation partition strictly runs `2013-11-01` to `2013-11-30`.
- [x] Test partition strictly runs `2013-12-01` to `2013-12-31`.
- [x] Multi-step recursive forecasting replaces true target with predicted target $\hat{y}$.
- [x] Contemporaneous unobserved foot-traffic `transactions` excluded from predictor matrix.
