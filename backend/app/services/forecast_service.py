from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from backend.app.core.logging import logger
from backend.app.models.business import Branch, Product
from backend.app.schemas.inventory_forecast import DailyForecastRecord, ForecastResponse
from ml.inference.predictor import ForecastingPredictor
from ml.pipelines.common.constants import PROCESSED_DATA_DIR
from ml.training.model_registry import ModelRegistry


class ForecastIntegrationService:
    """
    Service responsible for retrieving validated multi-horizon demand forecasts
    from the production LightGBM champion model artifact without lookahead leakage.
    """

    _cached_model = None
    _cached_metadata: Optional[Dict] = None
    _cached_history: Optional[pd.DataFrame] = None

    @classmethod
    def _get_model_and_metadata(cls):
        """
        Lazily load and cache the champion forecasting model and metadata.
        """
        if cls._cached_model is None:
            registry = ModelRegistry()
            cls._cached_model = registry.load_model(model_name="lightgbm", version="v1")
            cls._cached_metadata = registry.load_metadata(model_name="lightgbm", version="v1")
            logger.info("Loaded champion LightGBM model artifact into memory.")
        return cls._cached_model, cls._cached_metadata

    @classmethod
    def _get_series_history(
        cls,
        store_nbr: int,
        product_id: int,
        data_dir: Path = PROCESSED_DATA_DIR,
        max_cutoff_date: Optional[str] = "2013-10-31",
    ) -> pd.DataFrame:
        """
        Extract recent historical observations (last 35 days) for the given series.
        Strictly enforces date <= max_cutoff_date to prevent lookahead leakage.
        """
        # Load from processed feature dataset (train history <= 2013-10-31)
        if cls._cached_history is None:
            train_path = data_dir / "train_features.parquet"
            if train_path.exists():
                cls._cached_history = pd.read_parquet(train_path)
            else:
                raise FileNotFoundError(f"Processed feature dataset not found: {train_path}")

        df = cls._cached_history
        series_history = df[(df["store_nbr"] == store_nbr) & (df["product_id"] == product_id)]
        if max_cutoff_date is not None and not series_history.empty:
            series_history = series_history[series_history["date"].astype(str) <= str(max_cutoff_date)]
        if series_history.empty:
            return pd.DataFrame()

        # Take last 35 days of history for rolling/lag feature initialization
        return series_history.sort_values(by="date").tail(35).copy()

    @classmethod
    def get_forecast(
        cls,
        db: Session,
        product_id: int,
        branch_id: int,
        horizon_days: int = 7,
        forecast_start_date: Optional[str] = None,
    ) -> ForecastResponse:
        """
        Generate recursive demand forecast for a specific product and branch.
        """
        if horizon_days not in [7, 14, 30]:
            raise ValueError(f"Unsupported forecast horizon: {horizon_days}. Allowed: 7, 14, 30.")

        # 1. Resolve Product and Branch
        product = db.get(Product, product_id)
        if not product:
            raise ValueError(f"Product ID {product_id} not found in database.")

        branch = db.get(Branch, branch_id)
        if not branch:
            raise ValueError(f"Branch ID {branch_id} not found in database.")

        store_nbr = branch.source_store_number
        model, metadata = cls._get_model_and_metadata()
        now_utc = datetime.now(timezone.utc)

        # 2. Retrieve Series History (strictly bounded prior to forecast_start_date if specified)
        cutoff_str = "2013-10-31"
        if forecast_start_date is not None:
            cutoff_dt = pd.to_datetime(forecast_start_date) - pd.Timedelta(days=1)
            cutoff_str = cutoff_dt.strftime("%Y-%m-%d")

        history_df = cls._get_series_history(
            store_nbr=store_nbr, product_id=product.id, max_cutoff_date=cutoff_str
        )
        if history_df.empty:
            logger.warning(
                f"No historical sales series found for store_nbr={store_nbr}, product_id={product_id}. "
                f"Reporting UNAVAILABLE forecast."
            )
            return ForecastResponse(
                product_id=product.id,
                branch_id=branch.id,
                horizon_days=horizon_days,
                model_name=metadata.get("model_name", "lightgbm"),
                model_version=metadata.get("version", "v1"),
                status="UNAVAILABLE",
                forecast_timestamp=now_utc,
                daily_forecasts=[],
            )

        # 3. Instantiate Predictor and Run Recursive Forecast
        predictor = ForecastingPredictor(model=model, history_df=history_df, as_of_date=cutoff_str)
        forecast_df = predictor.predict_recursive(horizon_days=horizon_days)

        # Filter strictly for the requested product and store
        sub = forecast_df[
            (forecast_df["store_nbr"] == store_nbr) & (forecast_df["product_id"] == product.id)
        ].sort_values(by="horizon_step").reset_index(drop=True)

        if sub.empty:
            return ForecastResponse(
                product_id=product.id,
                branch_id=branch.id,
                horizon_days=horizon_days,
                model_name=metadata.get("model_name", "lightgbm"),
                model_version=metadata.get("version", "v1"),
                status="UNAVAILABLE",
                forecast_timestamp=now_utc,
                daily_forecasts=[],
            )

        # 4. Validate Predictions (NaN, Inf, Invalid Negatives)
        raw_preds = sub["prediction"].to_numpy(dtype=float)
        if np.isnan(raw_preds).any():
            raise ValueError(f"Prediction contains NaN values for product={product_id}, branch={branch_id}.")
        if np.isinf(raw_preds).any():
            raise ValueError(f"Prediction contains infinite values for product={product_id}, branch={branch_id}.")

        # Enforce non-negativity clipping
        clipped_preds = np.maximum(0.0, raw_preds)

        # Distinguish genuine zero demand from unavailable
        all_zeros = bool(np.all(clipped_preds == 0.0))
        status_label = "ZERO_DEMAND" if all_zeros else "AVAILABLE"

        daily_records: List[DailyForecastRecord] = []
        for i, row in sub.iterrows():
            daily_records.append(
                DailyForecastRecord(
                    date=str(row["date"]),
                    product_id=product.id,
                    branch_id=branch.id,
                    predicted_demand=round(float(clipped_preds[i]), 4),
                    horizon_step=int(row["horizon_step"]),
                    model_name=metadata.get("model_name", "lightgbm"),
                    model_version=metadata.get("version", "v1"),
                    forecast_timestamp=now_utc,
                )
            )

        return ForecastResponse(
            product_id=product.id,
            branch_id=branch.id,
            horizon_days=horizon_days,
            model_name=metadata.get("model_name", "lightgbm"),
            model_version=metadata.get("version", "v1"),
            status=status_label,
            forecast_timestamp=now_utc,
            daily_forecasts=daily_records,
        )
