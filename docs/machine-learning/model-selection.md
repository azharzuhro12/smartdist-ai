# SmartDist AI — Demand Forecasting Model Selection
## Champion Model Selection, Decision Criteria & Trade-Off Analysis

**Selected Champion**: `LightGBMForecaster` (`v1`)  
**Artifact Path**: `ml/artifacts/lightgbm_v1.joblib`  
**Decision Metric**: Weighted Absolute Percentage Error (WAPE) on Validation Set

---

## 1. Selection Criteria Framework

In retail distribution and demand forecasting, the model selection framework prioritizes:
1. **Weighted Absolute Percentage Error (WAPE)**:
   - Evaluates total aggregate volume error relative to total sales volume.
   - Robust against zero-sales artifacts (unlike MAPE which divides by individual zero targets).
2. **Root Mean Squared Error (RMSE)**:
   - Penalizes large outlier forecast errors that trigger catastrophic warehouse stockouts or massive overstock.
3. **Inference Latency & Operational Simplicity**:
   - Production requirement to generate forecasts for 1,782 series across multi-step horizons in seconds.
4. **Zero-Negative Constraint**:
   - Zero physical demand cannot be negative.

---

## 2. Validation Candidate Comparison

| Evaluation Dimension | Seasonal Naive Baseline | XGBoost Regressor | LightGBM Regressor (Champion) |
| :--- | :--- | :--- | :--- |
| **Validation WAPE** | 17.67% | 13.26% | **13.09% (Winner)** |
| **Validation RMSE** | 310.00 | **218.25** | 219.56 |
| **Validation MAE** | 40.83 | 30.65 | **30.25 (Winner)** |
| **Validation RMSLE** | **0.4103** | 0.5434 | 0.5598 |
| **Training Duration** | < 1 sec | 16.2 sec | **8.4 sec (Winner)** |
| **Native Categoricals** | N/A | Supported (hist) | **Native & Optimized** |
| **Memory Footprint** | ~33 KB | ~1.0 MB | **~800 KB** |

---

## 3. Justification for LightGBM Selection

1. **Lowest Aggregate Volume Error**: LightGBM achieved the lowest WAPE (13.09%) on the validation set, providing superior total demand precision across the retail network.
2. **2x Faster Training & Inference**: LightGBM trained in 8.4 seconds compared to 16.2 seconds for XGBoost while achieving comparable or superior accuracy.
3. **Native Categorical Splits**: LightGBM finds optimal splits for high-cardinality store and category groupings without needing dense one-hot encoding matrices.
4. **Generalization on Untouched Test Set**: On the December 2013 test set, LightGBM maintained a 21.55% WAPE, outperforming the Seasonal Naive baseline (27.48%) by **5.93 percentage points**.

---

## 4. Known Model Limitations

1. **Single Historical Year Context (2013)**:
   - The initial model was trained on 10 months of historical data (January to October 2013).
   - As a consequence, **annual seasonality** (e.g., year-over-year Easter, Mother's Day, and Christmas shifts) cannot be fully learned from single-year data alone.
2. **Recursive Error Accumulation at 30 Days**:
   - While 7-day WAPE is outstanding (13.87%), 30-day recursive WAPE climbs to 26.12%. Long-range replenishment should incorporate safety stock buffers.
3. **Macroeconomic Sensitivity**:
   - Oil price was forward-filled from the forecast cutoff date $T_0$. Rapid crude oil shocks will introduce exogenous deviations not captured by constant forward-fill.
