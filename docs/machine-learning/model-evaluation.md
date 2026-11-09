# SmartDist AI — Demand Forecasting Model Evaluation
## Comprehensive Performance Evaluation, Error Distributions & Slices

**Module**: `ml/training/evaluator.py`  
**Evaluation Partitions**: Validation (Nov 2013) & Test (Dec 2013)  
**Target Variable**: `quantity_sold` (Continuous daily sales units)

---

## 1. Overall Model Comparison on Validation Partition

The validation partition (`2013-11-01` to `2013-11-30`, 53,460 series-days) served as the benchmark for model comparison and champion selection:

| Model | WAPE (%) | RMSE | MAE | RMSLE | Negative Preds | Zero Demand Pct |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Seasonal Naive** | 17.67% | 310.00 | 40.83 | 0.4103 | 0 | 49.56% |
| **LightGBM** | **13.09%** | **219.56** | **30.25** | 0.5598 | 0 | 49.56% |
| **XGBoost** | 13.26% | 218.25 | 30.65 | 0.5434 | 0 | 49.56% |

### Key Observations:
- **Model Lift**: LightGBM reduced WAPE from 17.67% to 13.09% (a **25.9% relative error reduction** over Seasonal Naive).
- **Variance Reduction**: LightGBM lowered RMSE by 90.44 units (219.56 vs 310.00), demonstrating substantially better mitigation of large demand spikes.
- **LightGBM vs XGBoost**: LightGBM achieved the lowest overall WAPE (13.09% vs 13.26%) with faster training convergence (8.4s vs 16.2s).

---

## 2. Final Evaluation on Untouched Test Partition

The test partition (`2013-12-01` to `2013-12-31`, 53,460 series-days) represents the high-volume holiday peak shopping season in Ecuador retail:

| Model | WAPE (%) | RMSE | MAE | RMSLE | Mean Actual | Mean Predicted |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Seasonal Naive Baseline** | 27.48% | 410.90 | 81.24 | 0.5254 | 295.61 | 284.12 |
| **LightGBM (Champion)** | **21.55%** | **318.42** | **63.69** | 0.6304 | 295.61 | 265.56 |

### Performance Analysis:
- In December, overall consumer demand surged from an average of 231 units/day to 295.6 units/day.
- Despite the sharp holiday demand shock, LightGBM maintained an error rate **5.93 percentage points lower** than Seasonal Naive (21.55% vs 27.48%).
- RMSE was reduced by 92.48 units (318.42 vs 410.90).

---

## 3. Recursive Multi-Horizon Evaluation (Champion Model)

Operational evaluation using `ForecastingPredictor` where predictions $\hat{y}$ dynamically update autoregressive lags for subsequent forecast days:

| Forecast Horizon | Forecast Window | Total Predictions | WAPE (%) | RMSE | MAE | RMSLE |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **7-Day Forecast** | Day 1 to 7 | 12,474 | **13.87%** | 222.95 | 37.79 | 0.6062 |
| **14-Day Forecast** | Day 1 to 14 | 24,948 | **16.72%** | 244.10 | 44.52 | 0.6712 |
| **30-Day Forecast** | Day 1 to 30 | 51,678 | **26.12%** | 376.59 | 77.32 | 1.0112 |

### Recursive Dynamics:
- **7-Day Accuracy (13.87% WAPE)**: High precision suitable for immediate store inventory reordering and stock replenishment.
- **14-Day Accuracy (16.72% WAPE)**: Solid operational reliability for distribution center allocation.
- **30-Day Accuracy (26.12% WAPE)**: Noticeable error compounding as predictions recursively feed back into rolling statistics over 4 weeks, reflecting real-world uncertainty in long-range retail demand.

---

## 4. Performance Slices

### 4.1 Top Performing Product Families
High-velocity staple items exhibit strong predictability:
- **CLEANING**: 14.83% WAPE (Mean actual: 1,064.8 units/day)
- **DELI**: 15.33% WAPE (Mean actual: 239.8 units/day)
- **BREAD/BAKERY**: 15.77% WAPE (Mean actual: 371.2 units/day)
- **DAIRY**: 15.96% WAPE (Mean actual: 717.0 units/day)
- **BEVERAGES**: 16.11% WAPE (Mean actual: 1,386.5 units/day)

### 4.2 Top Performing Branches
- **Store 27**: 15.79% WAPE
- **Store 54**: 15.98% WAPE
- **Store 10**: 16.56% WAPE
- **Store 3**: 16.73% WAPE
- **Store 6**: 16.97% WAPE

### 4.3 Zero-Demand / Inactive Series Handling
In 2013, stores 22, 29, 42, 52, 53 had not yet opened, and categories like `LADIESWEAR` and `PET SUPPLIES` had 0.0 sales. The system safely returns `NaN` for WAPE without throwing zero-division exceptions.
