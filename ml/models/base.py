from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd


class BaseForecaster(ABC):
    """
    Abstract base class for demand forecasting models in SmartDist AI.
    Enforces standardized interfaces for training, multi-horizon evaluation,
    serialization, and non-negative prediction clipping.
    """

    def __init__(
        self,
        model_name: str,
        feature_names: Optional[List[str]] = None,
        target_name: str = "quantity_sold",
    ) -> None:
        self.model_name = model_name
        self.feature_names = feature_names or []
        self.target_name = target_name
        self.is_fitted = False

    @abstractmethod
    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        val_X: Optional[pd.DataFrame] = None,
        val_y: Optional[pd.Series] = None,
        **kwargs: Any,
    ) -> "BaseForecaster":
        """
        Fit model on training data. Optionally use validation data for early stopping.
        """
        pass

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Generate demand predictions. Guarantees non-negative outputs (clipped to 0.0).
        """
        pass

    @abstractmethod
    def save(self, filepath: Union[str, Path]) -> None:
        """
        Serialize model and metadata to disk.
        """
        pass

    @classmethod
    @abstractmethod
    def load(cls, filepath: Union[str, Path]) -> "BaseForecaster":
        """
        Load model artifact and metadata from disk.
        """
        pass

    def get_params(self) -> Dict[str, Any]:
        """
        Return dictionary of model configuration and hyperparameters.
        """
        return {
            "model_name": self.model_name,
            "feature_names": self.feature_names,
            "target_name": self.target_name,
            "is_fitted": self.is_fitted,
        }

    def _ensure_fitted(self) -> None:
        if not self.is_fitted:
            raise RuntimeError(f"Model {self.model_name} is not fitted yet. Call fit() first.")
