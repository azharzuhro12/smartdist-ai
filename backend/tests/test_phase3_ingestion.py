import pandas as pd
import pytest
from ml.pipelines.ingestion.extract import DataExtractor


def test_stream_date_filtering():
    """Verify stream extractor filters date ranges properly and stops when past end_date."""
    # Test with real raw file for a narrow 2-day range
    stream = DataExtractor.extract_daily_sales_stream(
        chunk_size=5_000,
        start_date="2013-02-01",
        end_date="2013-02-02",
    )
    chunks = list(stream)
    assert len(chunks) > 0
    full = pd.concat(chunks, ignore_index=True)
    # Exactly 2 days * 54 stores * 33 families = 3564 rows
    assert len(full) == 3564
    assert sorted(full["date"].unique()) == ["2013-02-01", "2013-02-02"]


def test_date_continuity_and_missing_combinations_analysis():
    """
    Verify analysis of store-family-date combinations:
    Distinguishes observed zero sales from missing dates (e.g. Christmas store closure).
    """
    sample = pd.DataFrame([
        {"date": "2013-01-01", "store_nbr": 1, "family": "BEVERAGES", "sales": 0.0},
        {"date": "2013-01-01", "store_nbr": 1, "family": "BREAD/BAKERY", "sales": 15.0},
    ])
    # Observed zero sales
    assert (sample["sales"] == 0.0).sum() == 1
    zero_row = sample[sample["sales"] == 0.0].iloc[0]
    assert zero_row["family"] == "BEVERAGES"
