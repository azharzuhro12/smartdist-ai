from decimal import Decimal
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from backend.app.db.session import SessionLocal
from backend.app.models.business import (
    Branch,
    Category,
    DailySale,
    Inventory,
    Product,
    ProductSupplier,
    Supplier,
    Warehouse,
)


def test_business_models_read():
    """Verify stored business models can be queried and relationships navigate properly."""
    db = SessionLocal()
    try:
        # Check Branch
        branch = db.execute(select(Branch)).scalars().first()
        assert branch is not None
        assert branch.source_store_number > 0
        assert branch.data_origin == "KAGGLE_PUBLIC"

        # Check Category and Product
        product = db.execute(select(Product)).scalars().first()
        assert product is not None
        assert product.category is not None
        assert product.category.category_code.startswith("CAT-")

        # Check Inventory
        inv = db.execute(select(Inventory)).scalars().first()
        if inv:
            assert inv.stock_quantity >= 0
            assert inv.reserved_quantity <= inv.stock_quantity
            assert inv.data_origin == "SYNTHETIC"
            assert inv.available_quantity == inv.stock_quantity - inv.reserved_quantity

        # Check DailySale
        sale = db.execute(select(DailySale)).scalars().first()
        if sale:
            assert sale.quantity_sold >= Decimal("0.0")
            assert sale.sales_amount >= Decimal("0.0")
            assert sale.branch is not None
            assert sale.product is not None
    finally:
        db.close()


def test_inventory_check_constraints():
    """Verify database check constraints reject invalid inventory states (e.g. reserved > stock)."""
    db = SessionLocal()
    try:
        product = db.execute(select(Product)).scalars().first()
        warehouse = db.execute(select(Warehouse)).scalars().first()
        if not product or not warehouse:
            pytest.skip("Prerequisite product or warehouse not loaded yet.")

        # Attempt to insert inventory with reserved_quantity > stock_quantity
        invalid_inv = Inventory(
            product_id=product.id,
            warehouse_id=warehouse.id,
            stock_quantity=10,
            reserved_quantity=50,  # Violates chk_reserved_le_stock
            reorder_point=20,
            safety_stock=10,
            data_origin="TEST",
        )
        db.add(invalid_inv)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()
