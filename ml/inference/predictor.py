from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd
from backend.app.core.logging import logger
from ml.features.calendar_features import CalendarFeatureExtractor
from ml.features.external_features import ExternalFeatureExtractor
from ml.models.base import BaseForecaster
from ml.training.evaluator import ModelEvaluator


class ForecastingPredictor:
    """
    Production inference engine supporting recursive multi-step demand forecasting
    across 7-day, 14-day, and 30-day operational horizons.
    Strictly guarantees zero future-target leakage by updating autoregressive lags
    and rolling statistics using generated predictions rather than unobserved actuals.
    """

    def __init__(
        self,
        model: BaseForecaster,
        history_df: pd.DataFrame,
        external_extractor: Optional[ExternalFeatureExtractor] = None,
        as_of_date: Optional[Union[str, date, datetime]] = None,
    ) -> None:
        self.model = model
        self.history_df = history_df.copy()
        self.history_df["date"] = pd.to_datetime(self.history_df["date"])
        if as_of_date is not None:
            cutoff_dt = pd.to_datetime(as_of_date)
            self.history_df = self.history_df[self.history_df["date"] <= cutoff_dt].copy()
            if self.history_df.empty:
                raise ValueError(f"No historical rows found on or before as_of_date={as_of_date}.")
        self.external_extractor = external_extractor or ExternalFeatureExtractor()

        # Extract latest observed date T_0 from history
        self.t_zero = self.history_df["date"].max()
        self.t_zero_str = self.t_zero.strftime("%Y-%m-%d")

        # Static series lookup (store_nbr, product_id, family, store_type, store_cluster)
        meta_cols = ["store_nbr", "product_id"]
        for opt_col in ["family", "store_type", "store_cluster"]:
            if opt_col in self.history_df.columns:
                meta_cols.append(opt_col)
        self.series_metadata = (
            self.history_df[meta_cols]
            .drop_duplicates(subset=["store_nbr", "product_id"])
            .reset_index(drop=True)
        )

        # Baseline oil price at T_0 (forward-fill policy)
        if "oil_price" in self.history_df.columns:
            last_oil = self.history_df[self.history_df["date"] == self.t_zero]["oil_price"].dropna()
            self.last_oil_price = float(last_oil.iloc[0]) if not last_oil.empty else 95.0
        else:
            self.last_oil_price = 95.0

        # Load clean holidays calendar
        try:
            self.holidays_df = self.external_extractor.load_clean_holidays()
        except Exception as e:
            logger.warning(f"Could not load holidays from raw file: {e}. Using empty holiday lookup.")
            self.holidays_df = pd.DataFrame(columns=["date", "is_holiday", "is_national_holiday", "is_work_day", "holiday_type"])

    def predict_recursive(
        self,
        horizon_days: int = 7,
        future_promotions: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Generate recursive multi-step forecasts for horizon_days (e.g. 7, 14, 30 days).
        Predictions at step h update autoregressive lags for step h + 1.
        """
        if horizon_days <= 0:
            raise ValueError("horizon_days must be positive.")

        # Combined sales buffer: starts with historical actuals
        # Maps (store_nbr, product_id, date_str) -> quantity
        series_buffer: Dict[tuple, float] = {}
        for row in self.history_df.itertuples(index=False):
            d_str = row.date.strftime("%Y-%m-%d")
            series_buffer[(row.store_nbr, row.product_id, d_str)] = float(row.quantity_sold)

        all_predictions: List[pd.DataFrame] = []

        for step in range(1, horizon_days + 1):
            target_date = self.t_zero + timedelta(days=step)
            target_date_str = target_date.strftime("%Y-%m-%d")

            # 1. Base panel for target_date with static metadata
            step_df = self.series_metadata.copy()
            step_df["date"] = target_date_str

            # 2. Add calendar attributes
            step_df = CalendarFeatureExtractor.add_calendar_features(step_df, date_col="date")

            # 3. Add holiday attributes
            if not self.holidays_df.empty:
                step_df = pd.merge(step_df, self.holidays_df, on="date", how="left")
                step_df["is_holiday"] = step_df["is_holiday"].fillna(0).astype("int8")
                step_df["is_national_holiday"] = step_df["is_national_holiday"].fillna(0).astype("int8")
                step_df["is_work_day"] = step_df["is_work_day"].fillna(0).astype("int8")
                step_df["holiday_type"] = step_df["holiday_type"].fillna("None")
            else:
                step_df["is_holiday"] = 0
                step_df["is_national_holiday"] = 0
                step_df["is_work_day"] = 1
                step_df["holiday_type"] = "None"

            # 4. Oil price: forward-filled from T_0
            step_df["oil_price"] = self.last_oil_price

            # 5. Promotions: merge planned schedule or default to 0
            if future_promotions is not None and not future_promotions.empty:
                step_df = pd.merge(step_df, future_promotions, on=["date", "store_nbr", "product_id"], how="left")
                step_df["promotion_quantity"] = step_df["promotion_quantity"].fillna(0).astype(int)
            else:
                step_df["promotion_quantity"] = 0

            # 6. Compute autoregressive lags and rolling features from series_buffer
            # Lags: 1, 7, 14, 28
            lags = [1, 7, 14, 28]
            rolling_windows = [7, 14, 28]

            for lag in lags:
                lag_date_str = (target_date - timedelta(days=lag)).strftime("%Y-%m-%d")
                step_df[f"lag_{lag}"] = [
                    series_buffer.get((s, p, lag_date_str), 0.0)
                    for s, p in zip(step_df["store_nbr"], step_df["product_id"])
                ]

            for window in rolling_windows:
                # Rolling window over past window days: [target_date - window, target_date - 1]
                window_date_strs = [
                    (target_date - timedelta(days=d)).strftime("%Y-%m-%d")
                    for d in range(1, window + 1)
                ]

                means = []
                stds = []
                for s, p in zip(step_df["store_nbr"], step_df["product_id"]):
                    vals = [series_buffer.get((s, p, d_str), 0.0) for d_str in window_date_strs]
                    means.append(float(np.mean(vals)))
                    stds.append(float(np.std(vals)))

                step_df[f"rolling_mean_{window}"] = means
                step_df[f"rolling_std_{window}"] = stds

            # 7. Model prediction
            preds = self.model.predict(step_df)
            step_df["prediction"] = preds
            step_df["horizon_step"] = step

            # 8. Update series_buffer with newly generated predictions for subsequent steps
            for s, p, pred_val in zip(step_df["store_nbr"], step_df["product_id"], preds):
                series_buffer[(s, p, target_date_str)] = float(pred_val)

            all_predictions.append(step_df[["date", "store_nbr", "product_id", "prediction", "horizon_step"]])

        result_df = pd.concat(all_predictions, ignore_index=True)
        logger.info(f"Generated {len(result_df)} recursive predictions across {horizon_days} days.")
        return result_df

    def evaluate_multi_horizon(
        self,
        actual_future_df: pd.DataFrame,
        horizons: List[int] = [7, 14, 30],
    ) -> Dict[str, Dict[str, float]]:
        """
        Evaluate recursive forecasting accuracy across multiple operational horizons (7, 14, 30 days)
        against actual observed test data.
        """
        max_h = max(horizons)
        forecast_df = self.predict_recursive(horizon_days=max_h)

        # Merge predictions with actual test values
        eval_df = actual_future_df.copy()
        eval_df["date"] = eval_df["date"].astype(str)
        merged = pd.merge(
            forecast_df,
            eval_df[["date", "store_nbr", "product_id", "quantity_sold"]],
            on=["date", "store_nbr", "product_id"],
            how="inner",
        )

        results = {}
        for h in horizons:
            sub = merged[merged["horizon_step"] <= h]
            metrics = ModelEvaluator.calculate_metrics(sub["quantity_sold"].values, sub["prediction"].values)
            results[f"horizon_{h}d"] = metrics

        return results
