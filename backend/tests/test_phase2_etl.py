import pandas as pd
from backend.app.db.session import SessionLocal
from backend.app.models.business import Branch
from ml.pipelines.ingestion.extract import DataExtractor
from ml.pipelines.loading.load import DataLoader
from ml.pipelines.transformation.transform import DataTransformer


def test_extract_stores():
    """Verify DataExtractor extracts stores DataFrame with expected columns."""
    df = DataExtractor.extract_stores()
    assert not df.empty
    assert "store_nbr" in df.columns
    assert "city" in df.columns
    assert len(df) == 54


def test_transform_and_idempotent_load_branches():
    """Verify transforming stores and loading branches is idempotent."""
    df = DataExtractor.extract_stores()
    transformed = DataTransformer.transform_stores_to_branches(df)
    assert len(transformed) == 54
    assert transformed[0]["branch_code"].startswith("BR-")
    assert transformed[0]["data_origin"] == "KAGGLE_PUBLIC"

    db = SessionLocal()
    try:
        # Re-running load_branches should not duplicate records
        count_before = len(db.query(Branch).all())
        DataLoader.load_branches(db, transformed)
        count_after = len(db.query(Branch).all())
        assert count_after == count_before
    finally:
        db.close()


def test_transform_families_to_categories_and_products():
    """Verify family string transformation builds properly categorized products."""
    sample_families = ["BEVERAGES", "BREAD/BAKERY", "CLEANING"]
    cats, prods = DataTransformer.transform_families_to_categories_and_products(sample_families)
    assert len(cats) == 3
    assert len(prods) == 3
    assert cats[1]["category_code"] == "CAT-BREAD_BAKERY"
    assert prods[1]["product_code"] == "PRD-BREAD_BAKERY"
