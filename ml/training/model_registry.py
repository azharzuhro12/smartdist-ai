from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import joblib
from backend.app.core.logging import logger
from ml.models.base import BaseForecaster
from ml.pipelines.common.constants import PROJECT_ROOT

ARTIFACTS_DIR = PROJECT_ROOT / "ml" / "artifacts"


class ModelRegistry:
    """
    Manages persistence, metadata tracking, versioning, and loading
    of trained demand forecasting models.
    """

    def __init__(self, artifacts_dir: Optional[Path] = None) -> None:
        self.artifacts_dir = artifacts_dir or ARTIFACTS_DIR
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def save_model(
        self,
        model: BaseForecaster,
        version: str = "v1",
        val_metrics: Optional[Dict[str, float]] = None,
        test_metrics: Optional[Dict[str, float]] = None,
        train_date_range: Optional[tuple] = None,
        val_date_range: Optional[tuple] = None,
        test_date_range: Optional[tuple] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """
        Serialize model and companion metadata JSON.
        """
        model_name = model.model_name
        artifact_filename = f"{model_name}_{version}.joblib"
        metadata_filename = f"{model_name}_{version}_metadata.json"

        artifact_path = self.artifacts_dir / artifact_filename
        metadata_path = self.artifacts_dir / metadata_filename

        # 1. Save model binary
        model.save(artifact_path)

        # 2. Extract library versions
        lib_versions = {}
        for lib in ["lightgbm", "xgboost", "sklearn", "pandas", "numpy"]:
            try:
                mod = __import__(lib)
                lib_versions[lib] = getattr(mod, "__version__", "unknown")
            except ImportError:
                lib_versions[lib] = "not_installed"

        # 3. Assemble metadata
        meta = {
            "model_name": model_name,
            "version": version,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "target_name": model.target_name,
            "feature_names": model.feature_names,
            "hyperparameters": model.get_params(),
            "train_date_range": list(train_date_range) if train_date_range else None,
            "val_date_range": list(val_date_range) if val_date_range else None,
            "test_date_range": list(test_date_range) if test_date_range else None,
            "val_metrics": val_metrics or {},
            "test_metrics": test_metrics or {},
            "library_versions": lib_versions,
        }
        if extra_metadata:
            meta.update(extra_metadata)

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        logger.info(f"Registered model {model_name} ({version}) at {artifact_path}")
        return artifact_path

    def load_model(
        self,
        model_name: str,
        version: str = "v1",
        model_cls: Optional[Any] = None,
    ) -> BaseForecaster:
        """
        Load trained model by name and version.
        """
        artifact_filename = f"{model_name}_{version}.joblib"
        artifact_path = self.artifacts_dir / artifact_filename

        if not artifact_path.exists():
            # Check for JSON artifact (e.g. seasonal naive)
            json_filename = f"{model_name}_{version}.json"
            json_path = self.artifacts_dir / json_filename
            if json_path.exists():
                artifact_path = json_path
            else:
                raise FileNotFoundError(f"Model artifact not found: {artifact_path}")

        if model_cls is not None:
            return model_cls.load(artifact_path)

        # Dynamic dispatch based on model_name
        if model_name == "seasonal_naive":
            from ml.models.seasonal_naive import SeasonalNaiveForecaster
            return SeasonalNaiveForecaster.load(artifact_path)
        elif model_name == "lightgbm":
            from ml.models.lightgbm_model import LightGBMForecaster
            return LightGBMForecaster.load(artifact_path)
        elif model_name == "xgboost":
            from ml.models.xgboost_model import XGBoostForecaster
            return XGBoostForecaster.load(artifact_path)
        else:
            return joblib.load(artifact_path)

    def load_metadata(self, model_name: str, version: str = "v1") -> Dict[str, Any]:
        """
        Load metadata JSON for a registered model.
        """
        metadata_filename = f"{model_name}_{version}_metadata.json"
        metadata_path = self.artifacts_dir / metadata_filename
        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata file not found: {metadata_path}")
        with open(metadata_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_models(self) -> List[Dict[str, Any]]:
        """
        List all saved models with summary metadata.
        """
        models = []
        for meta_file in sorted(self.artifacts_dir.glob("*_metadata.json")):
            with open(meta_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                models.append({
                    "model_name": data.get("model_name"),
                    "version": data.get("version"),
                    "saved_at": data.get("saved_at"),
                    "val_metrics": data.get("val_metrics"),
                    "test_metrics": data.get("test_metrics"),
                })
        return models
