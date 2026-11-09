import pandas as pd
from backend.app.db.session import SessionLocal
from backend.app.models.audit import DataQualityResult
from ml.pipelines.validation.quality import DataQualityValidator


def test_validate_stores_data():
    """Verify quality validation identifies missing or duplicate store records."""
    # Create test DataFrame with 1 valid row, 1 duplicate, and 1 non-positive store_nbr
    test_df = pd.DataFrame([
        {"store_nbr": 1, "city": "Quito", "state": "Pichincha", "type": "A", "cluster": 1},
        {"store_nbr": 1, "city": "Quito", "state": "Pichincha", "type": "A", "cluster": 1},
        {"store_nbr": -5, "city": "Guayaquil", "state": "Guayas", "type": "B", "cluster": 2},
    ])
    valid_df, summary = DataQualityValidator.validate_stores_data(test_df)
    assert summary["total_records"] == 3
    assert summary["failed_records"] == 3  # Both duplicates and the negative number rejected
    assert summary["duplicate_records"] == 2
    assert summary["validation_status"] == "FAILED"


def test_validate_sales_chunk():
    """Verify quality validation filters invalid sales dates and unmapped store numbers."""
    valid_branch_ids = {1, 2}
    valid_product_map = {"BEVERAGES": 10}

    chunk_df = pd.DataFrame([
        {"date": "2013-01-01", "store_nbr": 1, "family": "BEVERAGES", "sales": 50.0, "onpromotion": 0},
        {"date": "not-a-date", "store_nbr": 1, "family": "BEVERAGES", "sales": 10.0, "onpromotion": 0},
        {"date": "2013-01-01", "store_nbr": 999, "family": "BEVERAGES", "sales": 10.0, "onpromotion": 0},
        {"date": "2013-01-01", "store_nbr": 1, "family": "UNKNOWN_FAMILY", "sales": 10.0, "onpromotion": 0},
    ])

    valid_df, summary = DataQualityValidator.validate_sales_chunk(
        chunk_df, valid_branch_ids, valid_product_map
    )
    assert summary["total_records"] == 4
    assert summary["valid_records"] == 1
    assert summary["failed_records"] == 3
    assert summary["validation_status"] == "WARNING"


def test_save_quality_result():
    """Verify persisting validation summary records in PostgreSQL."""
    db = SessionLocal()
    try:
        summary = {
            "validation_name": "pytest_quality_check",
            "total_records": 100,
            "failed_records": 0,
            "validation_status": "PASSED",
        }
        res = DataQualityValidator.save_quality_result(db, "test_dataset", summary)
        assert res.id is not None
        assert res.validation_status == "PASSED"
    finally:
        db.close()
