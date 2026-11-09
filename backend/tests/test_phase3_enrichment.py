import pandas as pd
import pytest
from ml.features.external_features import ExternalFeatureExtractor


def test_clean_oil_prices_continuous_interpolation(tmp_path):
    """
    Verify oil price loader generates continuous daily dates and forward-fills
    weekends and public market holidays.
    """
    raw_oil = pd.DataFrame([
        {"date": "2023-01-01", "dcoilwtico": None},    # Sunday holiday: NaN
        {"date": "2023-01-03", "dcoilwtico": 75.0},    # Tuesday: 75.0 (Mon missing)
        {"date": "2023-01-04", "dcoilwtico": 77.0},    # Wednesday: 77.0
    ])
    csv_file = tmp_path / "test_oil.csv"
    raw_oil.to_csv(csv_file, index=False)

    clean_oil = ExternalFeatureExtractor.load_clean_oil_prices(csv_file)

    # Must contain continuous dates 2023-01-01, 2023-01-02, 2023-01-03, 2023-01-04
    dates = list(clean_oil["date"])
    assert dates == ["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04"]
    # 2023-01-01 was NaN before 75.0, so backfilled to 75.0
    assert clean_oil.iloc[0]["oil_price"] == 75.0
    # 2023-01-02 was missing, so forward/back filled to 75.0
    assert clean_oil.iloc[1]["oil_price"] == 75.0
    assert clean_oil.iloc[2]["oil_price"] == 75.0
    assert clean_oil.iloc[3]["oil_price"] == 77.0


def test_clean_holidays_duplicate_resolution(tmp_path):
    """
    Verify that multiple holiday events on the same date do not cause row duplication
    and transferred holidays are properly handled.
    """
    raw_holidays = pd.DataFrame([
        # Two events on 2023-05-01: National holiday and Local celebration
        {"date": "2023-05-01", "type": "Holiday", "locale": "National", "description": "Día del Trabajo", "transferred": False},
        {"date": "2023-05-01", "type": "Event", "locale": "Local", "description": "Local Festival", "transferred": False},
        # Transferred holiday: should be excluded
        {"date": "2023-10-09", "type": "Holiday", "locale": "National", "description": "Moved Holiday", "transferred": True},
    ])
    csv_file = tmp_path / "test_holidays.csv"
    raw_holidays.to_csv(csv_file, index=False)

    clean_holidays = ExternalFeatureExtractor.load_clean_holidays(csv_file)

    # 2023-05-01 must appear exactly once
    assert len(clean_holidays[clean_holidays["date"] == "2023-05-01"]) == 1
    row_may1 = clean_holidays[clean_holidays["date"] == "2023-05-01"].iloc[0]
    assert row_may1["is_holiday"] == 1
    assert row_may1["is_national_holiday"] == 1

    # Transferred holiday on 2023-10-09 must not be present
    assert len(clean_holidays[clean_holidays["date"] == "2023-10-09"]) == 0


def test_enrich_dataset_row_cardinality(tmp_path):
    """
    Verify that merging external datasets preserves the exact input row count
    without Cartesian product expansion.
    """
    input_df = pd.DataFrame([
        {"date": "2023-01-02", "store_nbr": 1, "product_id": 10, "quantity_sold": 5.0},
        {"date": "2023-01-02", "store_nbr": 1, "product_id": 20, "quantity_sold": 8.0},
        {"date": "2023-01-03", "store_nbr": 1, "product_id": 10, "quantity_sold": 6.0},
    ])

    enriched = ExternalFeatureExtractor.enrich_dataset(
        input_df,
        include_transactions=False,
    )

    # Must preserve exactly 3 rows
    assert len(enriched) == len(input_df)
    assert "oil_price" in enriched.columns
    assert "is_holiday" in enriched.columns
    assert "store_type" in enriched.columns
    assert "store_cluster" in enriched.columns
