from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import joblib
import numpy as np
import pandas as pd
from backend.app.core.logging import logger
from ml.models.base import BaseForecaster


class XGBoostForecaster(BaseForecaster):
    """
    XGBoost Regressor for multi-series demand forecasting.
    Uses histogram-based tree method with native categorical support,
    validation early stopping, and non-negative prediction clipping.
    """

    DEFAULT_CATEGORICAL_COLS = ["store_type", "holiday_type", "store_cluster", "product_id"]

    DEFAULT_PARAMS = {
        "objective": "reg:squarederror",
        "eval_metric": "rmse",
        "n_estimators": 400,
        "learning_rate": 0.05,
        "max_depth": 6,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "random_state": 42,
        "n_jobs": -1,
        "enable_categorical": True,
        "tree_method": "hist",
    }

    def __init__(
        self,
        feature_names: Optional[List[str]] = None,
        categorical_features: Optional[List[str]] = None,
        target_name: str = "quantity_sold",
        **params: Any,
    ) -> None:
        super().__init__(
            model_name="xgboost",
            feature_names=feature_names,
            target_name=target_name,
        )
        self.params = {**self.DEFAULT_PARAMS, **params}
        self.categorical_features = categorical_features or [
            c for c in self.DEFAULT_CATEGORICAL_COLS if self.feature_names and c in self.feature_names
        ]
        self.model_: Optional[Any] = None
        self.best_iteration_: Optional[int] = None

    def _prepare_features(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Extract approved features and enforce categorical types.
        """
        if self.feature_names:
            cols = [c for c in self.feature_names if c in X.columns]
            df = X[cols].copy()
        else:
            df = X.copy()

        for cat_col in self.categorical_features:
            if cat_col in df.columns:
                df[cat_col] = df[cat_col].astype("category")

        return df

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        val_X: Optional[pd.DataFrame] = None,
        val_y: Optional[pd.Series] = None,
        early_stopping_rounds: int = 30,
        **kwargs: Any,
    ) -> "XGBoostForecaster":
        """
        Fit XGBoost regressor with optional validation early stopping.
        """
        import xgboost as xgb

        if not self.feature_names:
            self.feature_names = [c for c in X.columns if c not in [self.target_name, "date", "family"]]
            self.categorical_features = [
                c for c in self.DEFAULT_CATEGORICAL_COLS if c in self.feature_names
            ]

        X_train = self._prepare_features(X)

        fit_params = {}
        model_params = {**self.params}
        if early_stopping_rounds > 0 and val_X is not None and val_y is not None:
            model_params["early_stopping_rounds"] = early_stopping_rounds

        self.model_ = xgb.XGBRegressor(**model_params)

        if val_X is not None and val_y is not None:
            X_val = self._prepare_features(val_X)
            fit_params["eval_set"] = [(X_val, val_y)]
            fit_params["verbose"] = False

        self.model_.fit(X_train, y, **fit_params)
        self.best_iteration_ = getattr(self.model_, "best_iteration", None)
        self.is_fitted = True
        logger.info(f"Fitted XGBoost with {len(self.feature_names)} features. Best iteration: {self.best_iteration_}")
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict demand and clip to non-negative values.
        """
        self._ensure_fitted()
        X_pred = self._prepare_features(X)
        raw_preds = self.model_.predict(X_pred)
        return np.maximum(0.0, raw_preds)

    def save(self, filepath: Union[str, Path]) -> None:
        """
        Serialize model object and metadata via joblib.
        """
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": self.model_,
            "feature_names": self.feature_names,
            "categorical_features": self.categorical_features,
            "params": self.params,
            "best_iteration": self.best_iteration_,
            "is_fitted": self.is_fitted,
            "target_name": self.target_name,
        }
        joblib.dump(payload, path)

    @classmethod
    def load(cls, filepath: Union[str, Path]) -> "XGBoostForecaster":
        """
        Load serialized XGBoost forecaster from disk.
        """
        path = Path(filepath)
        payload = joblib.load(path)
        forecaster = cls(
            feature_names=payload["feature_names"],
            categorical_features=payload["categorical_features"],
            target_name=payload["target_name"],
            **payload["params"],
        )
        forecaster.model_ = payload["model"]
        forecaster.best_iteration_ = payload.get("best_iteration")
        forecaster.is_fitted = payload["is_fitted"]
        return forecaster
