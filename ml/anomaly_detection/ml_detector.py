import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from backend.app.core.logging import logger
from ml.pipelines.common.constants import PROJECT_ROOT, PROCESSED_DATA_DIR
ML_ARTIFACTS_DIR = PROJECT_ROOT / "ml" / "artifacts"


class MLIsolationForestDetector:
    """
    Machine Learning Anomaly Detector using Isolation Forest.
    Trained strictly on historical observations (Train partition <= 2013-10-31).
    Features include contemporaneous & lag sales, rolling statistics, calendar indicators, and promotion flag.
    Returns normalized anomaly score in [0.0, 1.0] where 1.0 indicates extreme outlier.
    """

    DEFAULT_CONTAMINATION = 0.02
    RANDOM_SEED = 42

    FEATURE_COLS = [
        "quantity_sold",
        "lag_1",
        "lag_7",
        "rolling_mean_7",
        "rolling_std_7",
        "day_of_week",
        "is_weekend",
        "promotion_quantity",
    ]

    def __init__(
        self,
        contamination: float = DEFAULT_CONTAMINATION,
        random_state: int = RANDOM_SEED,
        model: Optional[IsolationForest] = None,
    ):
        self.contamination = contamination
        self.random_state = random_state
        self.model = model or IsolationForest(
            n_estimators=100,
            contamination=self.contamination,
            random_state=self.random_state,
            n_jobs=-1,
        )
        self.is_fitted = model is not None

    def fit(self, X: pd.DataFrame) -> "MLIsolationForestDetector":
        """
        Fit IsolationForest strictly on historical training features.
        """
        features_subset = self._prepare_features(X)
        if features_subset.empty:
            raise ValueError("Training feature set is empty.")
        self.model.fit(features_subset)
        self.is_fitted = True
        return self

    def score(self, X: pd.DataFrame) -> np.ndarray:
        """
        Score observations. IsolationForest decision_function outputs:
            positive for inliers, negative for outliers.
        We convert and calibrate this to [0.0, 1.0] where higher = more anomalous:
            normalized_score = 1.0 / (1.0 + exp(8.0 * score_raw))
        """
        if not self.is_fitted:
            raise ValueError("Model is not fitted. Call fit() or load_model() first.")
        features_subset = self._prepare_features(X)
        if features_subset.empty:
            return np.zeros(0, dtype=float)

        raw_scores = self.model.decision_function(features_subset)
        # Logistic sigmoid scaling centered around threshold 0.0
        # raw_scores typically range from -0.3 (extreme anomaly) to +0.25 (typical normal)
        scaled_scores = 1.0 / (1.0 + np.exp(10.0 * raw_scores))
        return np.clip(scaled_scores, 0.0, 1.0)

    def evaluate_single(
        self,
        features_dict: Dict[str, Any],
    ) -> Dict[str, Union[float, int, str, bool]]:
        """
        Evaluate a single observation provided as a feature dictionary.
        """
        if not self.is_fitted:
            return {
                "detector": "ISOLATION_FOREST",
                "status": "UNAVAILABLE",
                "anomaly_score": 0.0,
                "is_ml_anomaly": False,
            }
        df = pd.DataFrame([features_dict])
        score = float(self.score(df)[0])
        return {
            "detector": "ISOLATION_FOREST",
            "status": "VALID",
            "anomaly_score": round(score, 4),
            "is_ml_anomaly": score >= 0.70,
        }

    def _prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter and impute standard features for IsolationForest."""
        sub = pd.DataFrame()
        for col in self.FEATURE_COLS:
            if col in df.columns:
                sub[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
            else:
                sub[col] = 0.0
        return sub

    def save_model(self, file_path: Optional[Path] = None) -> Path:
        """Serialize model artifact to disk."""
        target_path = file_path or (ML_ARTIFACTS_DIR / "isolation_forest_v1.joblib")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, target_path)
        logger.info(f"Saved IsolationForest model artifact to {target_path}")
        return target_path

    @classmethod
    def load_model(cls, file_path: Optional[Path] = None) -> "MLIsolationForestDetector":
        """Load serialized model artifact from disk."""
        target_path = file_path or (ML_ARTIFACTS_DIR / "isolation_forest_v1.joblib")
        if not target_path.exists():
            logger.warning(f"IsolationForest artifact {target_path} not found.")
            return cls(model=None)
        model = joblib.load(target_path)
        detector = cls(model=model)
        detector.is_fitted = True
        return detector
