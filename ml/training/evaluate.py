import argparse
from pathlib import Path
from typing import Optional
import pandas as pd
from backend.app.core.logging import logger
from ml.pipelines.common.constants import PROCESSED_DATA_DIR
from ml.training.evaluator import ModelEvaluator
from ml.training.model_registry import ModelRegistry
from ml.training.train import APPROVED_FEATURE_COLS, TARGET_COL


def run_detailed_evaluation(
    model_name: str = "lightgbm",
    version: str = "v1",
    partition: str = "test",
    data_dir: Path = PROCESSED_DATA_DIR,
) -> None:
    """
    Run detailed evaluation slicing by store and family for a registered model.
    """
    registry = ModelRegistry()
    model = registry.load_model(model_name, version=version)

    part_file = data_dir / f"{partition}_features.parquet"
    logger.info(f"Loading {partition} data from {part_file}...")
    df = pd.read_parquet(part_file)

    X = df[APPROVED_FEATURE_COLS]
    y_true = df[TARGET_COL]

    logger.info(f"Generating predictions with {model_name}...")
    preds = model.predict(X)
    df["prediction"] = preds

    # 1. Overall
    overall = ModelEvaluator.calculate_metrics(y_true.values, preds)
    logger.info(f"Overall Metrics ({model_name} on {partition}): {overall}")

    # 2. Slice by store
    store_metrics = ModelEvaluator.evaluate_by_group(df, group_col="store_nbr")
    print(f"\n--- Top 5 Best Performing Stores by WAPE ({model_name}) ---")
    print(store_metrics.head(5)[["store_nbr", "wape", "mae", "rmse", "rmsle", "mean_actual", "mean_predicted"]])
    print(f"\n--- Top 5 Worst Performing Stores by WAPE ({model_name}) ---")
    print(store_metrics.tail(5)[["store_nbr", "wape", "mae", "rmse", "rmsle", "mean_actual", "mean_predicted"]])

    # 3. Slice by family
    family_metrics = ModelEvaluator.evaluate_by_group(df, group_col="family")
    print(f"\n--- Top 5 Best Performing Product Families by WAPE ({model_name}) ---")
    print(family_metrics.head(5)[["family", "wape", "mae", "rmse", "rmsle", "mean_actual", "mean_predicted"]])
    print(f"\n--- Top 5 Worst Performing Product Families by WAPE ({model_name}) ---")
    print(family_metrics.tail(5)[["family", "wape", "mae", "rmse", "rmsle", "mean_actual", "mean_predicted"]])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Detailed Model Evaluation & Slicing")
    parser.add_argument("--model", type=str, default="lightgbm", help="Model name")
    parser.add_argument("--version", type=str, default="v1", help="Model version")
    parser.add_argument("--partition", type=str, default="test", help="Partition to evaluate (val/test)")
    args = parser.parse_args()

    run_detailed_evaluation(model_name=args.model, version=args.version, partition=args.partition)
