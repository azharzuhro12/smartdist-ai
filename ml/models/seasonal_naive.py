import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd
from ml.models.base import BaseForecaster


class SeasonalNaiveForecaster(BaseForecaster):
    """
    Seasonal Naive Baseline Forecaster.
    Forecasts demand for date T as the observed demand from T - 7 days:
        y_hat(store, product, T) = y(store, product, T - 7)

    Strictly isolates store and product combinations.
    Guarantees non-negative forecasts.
    """

    def __init__(
        self,
        seasonality: int = 7,
        feature_names: Optional[List[str]] = None,
        target_name: str = "quantity_sold",
    ) -> None:
        super().__init__(
            model_name="seasonal_naive",
            feature_names=feature_names or [f"lag_{seasonality}"],
            target_name=target_name,
        )
        self.seasonality = seasonality
        # Lookup table: {(store_nbr, product_id, date_str): target_value}
        self.history_: Dict[tuple, float] = {}
        # Latest observed fallback per (store_nbr, product_id)
        self.latest_observed_: Dict[tuple, float] = {}

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        val_X: Optional[pd.DataFrame] = None,
        val_y: Optional[pd.Series] = None,
        **kwargs: Any,
    ) -> "SeasonalNaiveForecaster":
        """
        Record historical demand per store-product series.
        """
        if "store_nbr" not in X.columns or "product_id" not in X.columns:
            raise ValueError("X must contain 'store_nbr' and 'product_id' columns.")

        self.history_.clear()
        self.latest_observed_.clear()

        df = X[["store_nbr", "product_id"]].copy()
        df["target"] = y.values
        if "date" in X.columns:
            df["date"] = X["date"].astype(str).values
        else:
            df["date"] = None

        # Build lookup table
        for row in df.itertuples(index=False):
            series_key = (row.store_nbr, row.product_id)
            if row.date is not None:
                self.history_[(row.store_nbr, row.product_id, row.date)] = float(row.target)
            self.latest_observed_[series_key] = float(row.target)

        self.is_fitted = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Generate predictions using T - seasonality observations.
        Prioritizes lag column if present in X; falls back to historical lookup table.
        """
        self._ensure_fitted()
        lag_col = f"lag_{self.seasonality}"

        if lag_col in X.columns:
            # If lag column exists in feature matrix, use it directly
            raw_preds = X[lag_col].to_numpy(dtype=float, copy=True)
            # If any NaNs remain in lag column, fill using fallback
            nan_mask = np.isnan(raw_preds)
            if nan_mask.any():
                for idx in np.where(nan_mask)[0]:
                    row = X.iloc[idx]
                    series_key = (row["store_nbr"], row["product_id"])
                    raw_preds[idx] = self.latest_observed_.get(series_key, 0.0)
        else:
            # Look up from history by date - seasonality
            if "date" not in X.columns:
                raise ValueError(f"X must contain '{lag_col}' or 'date' for SeasonalNaive prediction.")

            raw_preds = np.zeros(len(X), dtype=float)
            target_dates = pd.to_datetime(X["date"])
            lag_dates = (target_dates - pd.Timedelta(days=self.seasonality)).dt.strftime("%Y-%m-%d").values

            store_vals = X["store_nbr"].values
            product_vals = X["product_id"].values

            for i in range(len(X)):
                key = (store_vals[i], product_vals[i], lag_dates[i])
                if key in self.history_:
                    raw_preds[i] = self.history_[key]
                else:
                    # Fallback to latest observed for this series, or 0.0
                    series_key = (store_vals[i], product_vals[i])
                    raw_preds[i] = self.latest_observed_.get(series_key, 0.0)

        # Enforce non-negativity constraint
        return np.maximum(0.0, raw_preds)

    def save(self, filepath: Union[str, Path]) -> None:
        """
        Save baseline parameters and latest observed lookup to JSON.
        """
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "model_name": self.model_name,
            "seasonality": self.seasonality,
            "target_name": self.target_name,
            "feature_names": self.feature_names,
            "is_fitted": self.is_fitted,
            # Serialize string keys for JSON compatibility
            "latest_observed": {f"{k[0]}_{k[1]}": v for k, v in self.latest_observed_.items()},
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, filepath: Union[str, Path]) -> "SeasonalNaiveForecaster":
        """
        Load baseline forecaster from JSON file.
        """
        path = Path(filepath)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        model = cls(
            seasonality=data["seasonality"],
            feature_names=data["feature_names"],
            target_name=data["target_name"],
        )
        model.is_fitted = data["is_fitted"]
        model.latest_observed_ = {
            (int(k.split("_")[0]), int(k.split("_")[1])): v
            for k, v in data.get("latest_observed", {}).items()
        }
        return model
