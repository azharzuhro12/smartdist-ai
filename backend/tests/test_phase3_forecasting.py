import math
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from ml.inference.predictor import ForecastingPredictor
from ml.models.base import BaseForecaster
from ml.models.lightgbm_model import LightGBMForecaster
from ml.models.seasonal_naive import SeasonalNaiveForecaster
from ml.models.xgboost_model import XGBoostForecaster
from ml.training.evaluator import ModelEvaluator
from ml.training.model_registry import ModelRegistry


@pytest.fixture
def synthetic_series_data():
    """
    Small synthetic panel fixture covering 2 stores, 2 products over 21 days.
    """
    dates = pd.date_range("2023-01-01", periods=21, freq="D").strftime("%Y-%m-%d")
    records = []
    for d in dates:
        for s in [1, 2]:
            for p in [101, 102]:
                # Distinct synthetic demand pattern per series
                base = 10.0 * s + (p - 100)
                dow = pd.to_datetime(d).dayofweek
                # Demand with weekly seasonality
                qty = float(base + dow * 2.0)
                records.append({
                    "date": d,
                    "store_nbr": s,
                    "product_id": p,
                    "family": f"FAM_{p}",
                    "quantity_sold": qty,
                    "store_type": "A" if s == 1 else "B",
                    "store_cluster": s,
                    "oil_price": 75.0,
                    "is_holiday": 0,
                    "is_national_holiday": 0,
                    "is_work_day": 1,
                    "holiday_type": "None",
                    "promotion_quantity": 0,
                    "year": 2023,
                    "month": 1,
                    "day": int(d.split("-")[2]),
                    "day_of_week": dow,
                    "day_of_month": int(d.split("-")[2]),
                    "week_of_year": 1,
                    "quarter": 1,
                    "is_weekend": 1 if dow >= 5 else 0,
                    "is_month_start": 1 if d.endswith("-01") else 0,
                    "is_month_end": 0,
                    "lag_1": qty - 2.0 if dow > 0 else qty + 10.0,
                    "lag_7": qty,
                    "lag_14": qty,
                    "lag_28": qty,
                    "rolling_mean_7": qty,
                    "rolling_std_7": 1.5,
                    "rolling_mean_14": qty,
                    "rolling_std_14": 1.8,
                    "rolling_mean_28": qty,
                    "rolling_std_28": 2.0,
                })
    return pd.DataFrame(records)


# 1. Seasonal Naive Correctness
def test_seasonal_naive_correctness(synthetic_series_data):
    train_df = synthetic_series_data[synthetic_series_data["date"] <= "2023-01-14"]
    test_df = synthetic_series_data[synthetic_series_data["date"] > "2023-01-14"].copy()

    model = SeasonalNaiveForecaster(seasonality=7)
    model.fit(train_df[["store_nbr", "product_id", "date"]], train_df["quantity_sold"])

    # Predict using history lookup (drop lag_7 column to force history lookup)
    test_df_no_lag = test_df.drop(columns=["lag_7"])
    preds = model.predict(test_df_no_lag)

    assert len(preds) == len(test_df)
    # Check that for date 2023-01-15 (T), prediction matches date 2023-01-08 (T-7)
    sample_test = test_df_no_lag[(test_df_no_lag["date"] == "2023-01-15") & (test_df_no_lag["store_nbr"] == 1) & (test_df_no_lag["product_id"] == 101)]
    sample_pred = model.predict(sample_test)

    expected_row = train_df[(train_df["date"] == "2023-01-08") & (train_df["store_nbr"] == 1) & (train_df["product_id"] == 101)]
    assert sample_pred[0] == pytest.approx(expected_row["quantity_sold"].iloc[0])


# 2. Store-Product Grouping Isolation
def test_store_product_grouping_isolation():
    # Two distinct series with completely different demand
    history = pd.DataFrame([
        {"date": "2023-01-01", "store_nbr": 1, "product_id": 10, "quantity_sold": 5.0},
        {"date": "2023-01-01", "store_nbr": 2, "product_id": 20, "quantity_sold": 500.0},
    ])
    model = SeasonalNaiveForecaster(seasonality=7)
    model.fit(history[["store_nbr", "product_id", "date"]], history["quantity_sold"])

    target = pd.DataFrame([
        {"date": "2023-01-08", "store_nbr": 1, "product_id": 10},
        {"date": "2023-01-08", "store_nbr": 2, "product_id": 20},
    ])
    preds = model.predict(target)
    assert preds[0] == 5.0
    assert preds[1] == 500.0


# 3. Model Input Schema
def test_model_input_schema_conversion(synthetic_series_data):
    features = ["store_nbr", "product_id", "day_of_week", "store_type", "lag_1", "lag_7"]
    model = LightGBMForecaster(feature_names=features, n_estimators=5, max_depth=3)

    X = synthetic_series_data[features]
    y = synthetic_series_data["quantity_sold"]
    model.fit(X, y)

    assert model.is_fitted
    prepared = model._prepare_features(X)
    assert prepared["store_type"].dtype.name == "category"


# 4. Missing Feature Handling
def test_missing_feature_handling():
    model = SeasonalNaiveForecaster(seasonality=7)
    # Series with unknown store
    history = pd.DataFrame([{"date": "2023-01-01", "store_nbr": 1, "product_id": 10, "quantity_sold": 42.0}])
    model.fit(history[["store_nbr", "product_id", "date"]], history["quantity_sold"])

    # Query unseen series
    unseen = pd.DataFrame([{"date": "2023-01-08", "store_nbr": 99, "product_id": 999}])
    preds = model.predict(unseen)
    # Fallback to 0.0 safely without crashing
    assert preds[0] == 0.0


# 5. Prediction Output Shape
def test_prediction_output_shape(synthetic_series_data):
    features = ["store_nbr", "product_id", "day_of_week", "lag_1", "lag_7"]
    model = LightGBMForecaster(feature_names=features, n_estimators=5)
    model.fit(synthetic_series_data[features], synthetic_series_data["quantity_sold"])

    sample = synthetic_series_data[features].iloc[:13]
    preds = model.predict(sample)
    assert isinstance(preds, np.ndarray)
    assert preds.shape == (13,)


# 6. Non-Negative Predictions
def test_non_negative_predictions():
    # Evaluator and models must clip negative numbers to 0.0
    y_true = np.array([10.0, 20.0, 30.0])
    raw_negative_preds = np.array([-5.0, 15.0, -25.0])

    metrics = ModelEvaluator.calculate_metrics(y_true, raw_negative_preds)
    assert metrics["negative_preds_count"] == 2
    # Clipped preds become [0.0, 15.0, 0.0]
    # Abs errors: |10-0| + |20-15| + |30-0| = 10 + 5 + 30 = 45 -> MAE = 15.0
    assert metrics["mae"] == 15.0


# 7. Metric Correctness
def test_metric_correctness():
    y_true = np.array([10.0, 20.0, 30.0, 40.0])
    y_pred = np.array([12.0, 18.0, 33.0, 36.0])

    m = ModelEvaluator.calculate_metrics(y_true, y_pred)

    # MAE = (|2| + |2| + |3| + |4|) / 4 = 11 / 4 = 2.75
    assert m["mae"] == 2.75
    # RMSE = sqrt((4 + 4 + 9 + 16) / 4) = sqrt(33 / 4) = sqrt(8.25) ≈ 2.8723
    assert m["rmse"] == pytest.approx(math.sqrt(8.25), rel=1e-3)
    # WAPE = 11 / 100 * 100 = 11.0%
    assert m["wape"] == 11.0


# 8. WAPE Zero-Denominator Behavior
def test_wape_zero_denominator_behavior():
    # Case 1: Both true and predicted are all zeros -> 0.0% error
    all_zero_true = np.array([0.0, 0.0, 0.0])
    all_zero_pred = np.array([0.0, 0.0, 0.0])
    m1 = ModelEvaluator.calculate_metrics(all_zero_true, all_zero_pred)
    assert m1["wape"] == 0.0

    # Case 2: True is zero, predicted is non-zero -> NaN reported safely without ZeroDivisionError
    non_zero_pred = np.array([5.0, 10.0, 0.0])
    m2 = ModelEvaluator.calculate_metrics(all_zero_true, non_zero_pred)
    assert math.isnan(m2["wape"])


# 9. RMSLE Correctness
def test_rmsle_correctness():
    y_true = np.array([0.0, 1.0, 2.0])
    y_pred = np.array([0.0, 1.0, 2.0])
    m_perfect = ModelEvaluator.calculate_metrics(y_true, y_pred)
    assert m_perfect["rmsle"] == 0.0

    y_perturbed = np.array([1.0, 2.0, 3.0])
    m = ModelEvaluator.calculate_metrics(y_true, y_perturbed)
    # log1p(y_true) = [0, ln(2), ln(3)]
    # log1p(y_pred) = [ln(2), ln(3), ln(4)]
    # diffs = [ln(2)-0, ln(3)-ln(2), ln(4)-ln(3)] = [ln(2), ln(1.5), ln(4/3)]
    diffs = np.array([math.log(2), math.log(1.5), math.log(4 / 3)])
    expected_rmsle = math.sqrt(np.mean(diffs ** 2))
    assert m["rmsle"] == pytest.approx(expected_rmsle, rel=1e-3)


# 10. Train/Validation/Test Isolation
def test_train_val_test_isolation(synthetic_series_data):
    from ml.validation.time_series_split import TimeSeriesSplitter

    train, val, test = TimeSeriesSplitter.split_by_dates(
        synthetic_series_data, train_end="2023-01-10", val_end="2023-01-15"
    )

    assert train["date"].max() <= "2023-01-10"
    assert val["date"].min() > "2023-01-10"
    assert val["date"].max() <= "2023-01-15"
    assert test["date"].min() > "2023-01-15"

    # Zero overlap across date partitions
    train_dates = set(train["date"].unique())
    val_dates = set(val["date"].unique())
    test_dates = set(test["date"].unique())

    assert train_dates.isdisjoint(val_dates)
    assert train_dates.isdisjoint(test_dates)
    assert val_dates.isdisjoint(test_dates)


# 11. Model Save and Reload
def test_model_save_and_reload(tmp_path, synthetic_series_data):
    features = ["store_nbr", "product_id", "day_of_week", "lag_1", "lag_7"]
    model = LightGBMForecaster(feature_names=features, n_estimators=10)
    X = synthetic_series_data[features]
    y = synthetic_series_data["quantity_sold"]
    model.fit(X, y)

    preds_before = model.predict(X.iloc[:10])

    save_path = tmp_path / "test_lgbm.joblib"
    model.save(save_path)

    loaded = LightGBMForecaster.load(save_path)
    preds_after = loaded.predict(X.iloc[:10])

    np.testing.assert_allclose(preds_before, preds_after)


# 12. Reproducibility
def test_model_reproducibility(synthetic_series_data):
    features = ["store_nbr", "product_id", "day_of_week", "lag_1", "lag_7"]
    X = synthetic_series_data[features]
    y = synthetic_series_data["quantity_sold"]

    model1 = LightGBMForecaster(feature_names=features, n_estimators=15, random_state=42)
    model1.fit(X, y)
    p1 = model1.predict(X.iloc[:20])

    model2 = LightGBMForecaster(feature_names=features, n_estimators=15, random_state=42)
    model2.fit(X, y)
    p2 = model2.predict(X.iloc[:20])

    np.testing.assert_allclose(p1, p2)


# 13. Recursive Forecasting Without Future-Target Leakage
def test_recursive_forecasting_no_future_leakage(synthetic_series_data):
    # Split into history (days 1-14) and future evaluation (days 15-21)
    history = synthetic_series_data[synthetic_series_data["date"] <= "2023-01-14"].copy()

    # Train a baseline model
    model = SeasonalNaiveForecaster(seasonality=7)
    model.fit(history[["store_nbr", "product_id", "date"]], history["quantity_sold"])

    predictor = ForecastingPredictor(model=model, history_df=history)
    forecast_df = predictor.predict_recursive(horizon_days=7)

    assert len(forecast_df) == 7 * 4  # 7 days * 2 stores * 2 products = 28
    assert "prediction" in forecast_df.columns
    # Ensure all predictions are non-negative
    assert (forecast_df["prediction"] >= 0.0).all()
    # Ensure dates strictly follow T_0
    assert forecast_df["date"].min() == "2023-01-15"
    assert forecast_df["date"].max() == "2023-01-21"
