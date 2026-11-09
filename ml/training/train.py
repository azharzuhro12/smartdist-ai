import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
import pandas as pd
from backend.app.core.logging import logger
from ml.inference.predictor import ForecastingPredictor
from ml.models.lightgbm_model import LightGBMForecaster
from ml.models.seasonal_naive import SeasonalNaiveForecaster
from ml.models.xgboost_model import XGBoostForecaster
from ml.pipelines.common.constants import PROCESSED_DATA_DIR
from ml.training.evaluator import ModelEvaluator
from ml.training.model_registry import ModelRegistry

# Approved feature set excluding contemporaneous transactions and revenue estimates
APPROVED_FEATURE_COLS = [
    "store_nbr",
    "product_id",
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
    "store_type",
    "store_cluster",
    "oil_price",
    "is_holiday",
    "is_national_holiday",
    "is_work_day",
    "holiday_type",
    "promotion_quantity",
    "lag_1",
    "lag_7",
    "lag_14",
    "lag_28",
    "rolling_mean_7",
    "rolling_std_7",
    "rolling_mean_14",
    "rolling_std_14",
    "rolling_mean_28",
    "rolling_std_28",
]

TARGET_COL = "quantity_sold"


def load_partitions(
    data_dir: Path = PROCESSED_DATA_DIR,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Load train, validation, and test Parquet partitions.
    """
    train_path = data_dir / "train_features.parquet"
    val_path = data_dir / "val_features.parquet"
    test_path = data_dir / "test_features.parquet"

    logger.info("Loading parquet partitions from disk...")
    train_df = pd.read_parquet(train_path)
    val_df = pd.read_parquet(val_path)
    test_df = pd.read_parquet(test_path)

    logger.info(
        f"Loaded partitions: Train={len(train_df)} rows, "
        f"Val={len(val_df)} rows, Test={len(test_df)} rows"
    )
    return train_df, val_df, test_df


def train_and_evaluate_all(
    data_dir: Path = PROCESSED_DATA_DIR,
    save_artifacts: bool = True,
) -> Dict[str, Any]:
    """
    Execute end-to-end training and evaluation:
        1. Seasonal Naive baseline
        2. LightGBM
        3. XGBoost
        4. Validation comparison & Champion selection
        5. Test partition evaluation
        6. Multi-horizon recursive evaluation (7, 14, 30 days)
    """
    registry = ModelRegistry()
    train_df, val_df, test_df = load_partitions(data_dir)

    train_dates = (train_df["date"].min(), train_df["date"].max())
    val_dates = (val_df["date"].min(), val_df["date"].max())
    test_dates = (test_df["date"].min(), test_df["date"].max())

    X_train = train_df[APPROVED_FEATURE_COLS]
    y_train = train_df[TARGET_COL]

    X_val = val_df[APPROVED_FEATURE_COLS]
    y_val = val_df[TARGET_COL]

    X_test = test_df[APPROVED_FEATURE_COLS]
    y_test = test_df[TARGET_COL]

    results = {
        "validation_comparison": {},
        "test_evaluation": {},
        "horizon_evaluation": {},
        "champion_model": None,
    }

    # -------------------------------------------------------------
    # 1. Seasonal Naive Baseline
    # -------------------------------------------------------------
    logger.info("=== Training Seasonal Naive Baseline ===")
    snaive = SeasonalNaiveForecaster(seasonality=7, feature_names=["lag_7"])
    # Pass train_df with date for history lookup
    snaive.fit(train_df[["store_nbr", "product_id", "date"]], y_train)

    val_preds_snaive = snaive.predict(val_df)
    snaive_val_metrics = ModelEvaluator.calculate_metrics(y_val.values, val_preds_snaive)
    results["validation_comparison"]["seasonal_naive"] = snaive_val_metrics
    logger.info(f"Seasonal Naive Val Metrics: {snaive_val_metrics}")

    if save_artifacts:
        registry.save_model(
            snaive,
            version="v1",
            val_metrics=snaive_val_metrics,
            train_date_range=train_dates,
            val_date_range=val_dates,
        )

    # -------------------------------------------------------------
    # 2. LightGBM Forecaster
    # -------------------------------------------------------------
    logger.info("=== Training LightGBM Forecaster ===")
    lgbm = LightGBMForecaster(
        feature_names=APPROVED_FEATURE_COLS,
        n_estimators=400,
        learning_rate=0.05,
        num_leaves=63,
        random_state=42,
    )
    lgbm.fit(X_train, y_train, val_X=X_val, val_y=y_val, early_stopping_rounds=30)

    val_preds_lgbm = lgbm.predict(X_val)
    lgbm_val_metrics = ModelEvaluator.calculate_metrics(y_val.values, val_preds_lgbm)
    results["validation_comparison"]["lightgbm"] = lgbm_val_metrics
    logger.info(f"LightGBM Val Metrics: {lgbm_val_metrics}")

    if save_artifacts:
        registry.save_model(
            lgbm,
            version="v1",
            val_metrics=lgbm_val_metrics,
            train_date_range=train_dates,
            val_date_range=val_dates,
        )

    # -------------------------------------------------------------
    # 3. XGBoost Forecaster
    # -------------------------------------------------------------
    logger.info("=== Training XGBoost Forecaster ===")
    xgb = XGBoostForecaster(
        feature_names=APPROVED_FEATURE_COLS,
        n_estimators=400,
        learning_rate=0.05,
        max_depth=6,
        random_state=42,
    )
    xgb.fit(X_train, y_train, val_X=X_val, val_y=y_val, early_stopping_rounds=30)

    val_preds_xgb = xgb.predict(X_val)
    xgb_val_metrics = ModelEvaluator.calculate_metrics(y_val.values, val_preds_xgb)
    results["validation_comparison"]["xgboost"] = xgb_val_metrics
    logger.info(f"XGBoost Val Metrics: {xgb_val_metrics}")

    if save_artifacts:
        registry.save_model(
            xgb,
            version="v1",
            val_metrics=xgb_val_metrics,
            train_date_range=train_dates,
            val_date_range=val_dates,
        )

    # -------------------------------------------------------------
    # 4. Model Selection (Validation Comparison)
    # -------------------------------------------------------------
    # Compare candidate ML models on validation WAPE & RMSE
    candidates = {
        "seasonal_naive": (snaive, snaive_val_metrics),
        "lightgbm": (lgbm, lgbm_val_metrics),
        "xgboost": (xgb, xgb_val_metrics),
    }

    # Best ML model based on lowest validation WAPE
    champion_name = min(
        ["lightgbm", "xgboost"],
        key=lambda m: candidates[m][1]["wape"],
    )
    champion_model, champion_val_metrics = candidates[champion_name]
    results["champion_model"] = champion_name
    logger.info(f"Selected Champion Model: {champion_name} (Val WAPE: {champion_val_metrics['wape']}%)")

    # -------------------------------------------------------------
    # 5. Untouched Test Partition Evaluation
    # -------------------------------------------------------------
    logger.info(f"=== Evaluating Champion Model ({champion_name}) on Untouched Test Partition ===")
    test_preds_champ = champion_model.predict(X_test)
    test_metrics_champ = ModelEvaluator.calculate_metrics(y_test.values, test_preds_champ)
    results["test_evaluation"][champion_name] = test_metrics_champ

    # Also evaluate baseline on test for comparison
    test_preds_snaive = snaive.predict(test_df)
    test_metrics_snaive = ModelEvaluator.calculate_metrics(y_test.values, test_preds_snaive)
    results["test_evaluation"]["seasonal_naive"] = test_metrics_snaive

    logger.info(f"Champion Test Metrics: {test_metrics_champ}")
    logger.info(f"Baseline Test Metrics: {test_metrics_snaive}")

    # -------------------------------------------------------------
    # 6. Multi-Horizon Recursive Forecasting Evaluation
    # -------------------------------------------------------------
    logger.info("=== Running Multi-Horizon Recursive Evaluation (7, 14, 30 days) ===")
    # History for recursive predictor is the last 35 days of validation partition
    recent_history = val_df.sort_values(by="date").tail(35 * 1782).copy()
    predictor = ForecastingPredictor(model=champion_model, history_df=recent_history)

    horizon_metrics = predictor.evaluate_multi_horizon(
        actual_future_df=test_df,
        horizons=[7, 14, 30],
    )
    results["horizon_evaluation"] = horizon_metrics
    logger.info(f"Multi-Horizon Metrics: {json.dumps(horizon_metrics, indent=2)}")

    # Update metadata with test metrics
    if save_artifacts:
        registry.save_model(
            champion_model,
            version="v1",
            val_metrics=champion_val_metrics,
            test_metrics=test_metrics_champ,
            train_date_range=train_dates,
            val_date_range=val_dates,
            test_date_range=test_dates,
            extra_metadata={
                "is_champion": True,
                "multi_horizon_evaluation": horizon_metrics,
            },
        )

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SmartDist AI Demand Forecasting Model Training")
    parser.add_argument("--save", action="store_true", default=True, help="Save trained model artifacts")
    args = parser.parse_args()

    res = train_and_evaluate_all(save_artifacts=args.save)
    print("\n================ TRAINING SUMMARY ================")
    print("Validation Metrics:")
    for m_name, m_dict in res["validation_comparison"].items():
        print(f"  {m_name:15s} -> WAPE: {m_dict['wape']:6.2f}%, RMSE: {m_dict['rmse']:8.2f}, MAE: {m_dict['mae']:8.2f}, RMSLE: {m_dict['rmsle']:6.4f}")
    print(f"\nChampion Model: {res['champion_model']}")
    print("Test Metrics (Untouched Partition):")
    for m_name, m_dict in res["test_evaluation"].items():
        print(f"  {m_name:15s} -> WAPE: {m_dict['wape']:6.2f}%, RMSE: {m_dict['rmse']:8.2f}, MAE: {m_dict['mae']:8.2f}, RMSLE: {m_dict['rmsle']:6.4f}")
    print("\nRecursive Multi-Horizon Evaluation (Champion):")
    for h_name, h_dict in res["horizon_evaluation"].items():
        print(f"  {h_name:15s} -> WAPE: {h_dict['wape']:6.2f}%, RMSE: {h_dict['rmse']:8.2f}, MAE: {h_dict['mae']:8.2f}, RMSLE: {h_dict['rmsle']:6.4f}")
    print("==================================================")
