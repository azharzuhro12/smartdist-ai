# SmartDist AI — Demand Forecasting Inference Guide
## Operational Prediction Interface & Integration Manual

**Module**: `ml/inference/predictor.py`  
**Model Registry**: `ml/training/model_registry.py`  

---

## 1. Quick Start: Loading the Champion Model

```python
from ml.training.model_registry import ModelRegistry

# Initialize registry and load the champion LightGBM model
registry = ModelRegistry()
model = registry.load_model(model_name="lightgbm", version="v1")
metadata = registry.load_metadata(model_name="lightgbm", version="v1")

print(f"Loaded {metadata['model_name']} ({metadata['version']})")
print(f"Validation WAPE: {metadata['val_metrics']['wape']}%")
print(f"Test WAPE: {metadata['test_metrics']['wape']}%")
```

---

## 2. One-Step-Ahead Static Inference

When predicting on pre-engineered feature DataFrames (e.g. batch scoring):

```python
import pandas as pd
from ml.training.train import APPROVED_FEATURE_COLS

# Load feature dataset
features_df = pd.read_parquet("ml/data/processed/val_features.parquet")

# Predict demand
X = features_df[APPROVED_FEATURE_COLS]
predictions = model.predict(X)

# All predictions are non-negative
assert (predictions >= 0.0).all()
```

---

## 3. Recursive Multi-Step Forecasting (7-Day, 14-Day, 30-Day)

In production, future demand values are unobserved. Use `ForecastingPredictor` to recursively generate forward-looking forecasts:

```python
import pandas as pd
from ml.inference.predictor import ForecastingPredictor
from ml.training.model_registry import ModelRegistry

# 1. Load champion model
registry = ModelRegistry()
model = registry.load_model("lightgbm", version="v1")

# 2. Extract recent historical observations (at least 28 days of history up to T_0)
history_df = pd.read_parquet("ml/data/processed/train_features.parquet")
recent_history = history_df.sort_values(by="date").tail(35 * 1782)

# 3. Instantiate recursive predictor
predictor = ForecastingPredictor(model=model, history_df=recent_history)

# 4. Generate 7-day operational forecast
forecast_7d = predictor.predict_recursive(horizon_days=7)
print(forecast_7d.head())

# Output Columns:
# ['date', 'store_nbr', 'product_id', 'prediction', 'horizon_step']
```

---

## 4. Operational Invariant Guarantees

1. **Strict Zero Leakage**: The recursive predictor never reads actual future demand $y(T_0 + k)$. Lags at step $h$ are computed dynamically using generated predictions $\hat{y}$.
2. **Deterministic Calendars**: Day of week, weekend, and statutory holiday indicators are computed deterministically for each future date.
3. **Macroeconomic Forward-Fill**: Oil price is held constant from $T_0$, adhering to the production exogenous feature policy.
4. **Physical Feasibility**: Output is strictly non-negative ($\max(0, \hat{y})$).
