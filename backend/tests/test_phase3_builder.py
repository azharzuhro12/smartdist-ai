import pandas as pd
import pytest
from ml.datasets.dataset_builder import DatasetBuilder


def test_dataset_builder_feature_generation_and_target():
    """
    Verify DatasetBuilder builds all expected feature columns, maintains quantity_sold as
    the target, and does not produce NaNs in final output.
    """
    dates = pd.date_range("2023-01-01", periods=60, freq="D").strftime("%Y-%m-%d")
    records = []
    for d in dates:
        for store in [1, 2]:
            for prod in [10, 20]:
                records.append({
                    "date": d,
                    "store_nbr": store,
                    "product_id": prod,
                    "family": "BEVERAGES" if prod == 10 else "DAIRY",
                    "quantity_sold": 25.0,
                    "promotion_quantity": 0,
                })
    df = pd.DataFrame(records)

    features_df = DatasetBuilder.build_feature_dataset(df, drop_na_lags=True)

    # 1. Target column must be quantity_sold
    assert DatasetBuilder.TARGET_COLUMN == "quantity_sold"
    assert "quantity_sold" in features_df.columns

    # 2. Key feature columns must exist
    for col in DatasetBuilder.FEATURE_COLUMNS:
        assert col in features_df.columns, f"Missing feature column: {col}"

    # 3. No sales_amount as forecasting target
    assert "sales_amount" not in DatasetBuilder.FEATURE_COLUMNS

    # 4. No NaNs after dropping initial lag warmup
    assert not features_df[DatasetBuilder.FEATURE_COLUMNS].isnull().any().any()


def test_dataset_builder_reproducibility():
    """Verify building features on identical input yields deterministic, bitwise identical output."""
    dates = pd.date_range("2023-01-01", periods=40, freq="D").strftime("%Y-%m-%d")
    records = [{"date": d, "store_nbr": 1, "product_id": 1, "quantity_sold": float(idx % 10), "promotion_quantity": 0} for idx, d in enumerate(dates)]
    df = pd.DataFrame(records)

    run1 = DatasetBuilder.build_feature_dataset(df, drop_na_lags=True)
    run2 = DatasetBuilder.build_feature_dataset(df, drop_na_lags=True)

    pd.testing.assert_frame_equal(run1, run2)
