from backend.app.db.session import SessionLocal
from backend.app.models.business import Inventory, Supplier, Warehouse
from ml.pipelines.synthetic.inventory_generator import SyntheticInventoryGenerator


def test_synthetic_inventory_generator_reproducibility():
    """Verify synthetic inventory generator produces deterministic results with identical seeds."""
    gen1 = SyntheticInventoryGenerator(seed=42)
    gen2 = SyntheticInventoryGenerator(seed=42)

    val1 = [gen1.rng.randint(10, 100) for _ in range(5)]
    val2 = [gen2.rng.randint(10, 100) for _ in range(5)]
    assert val1 == val2


def test_synthetic_data_integrity_and_origin():
    """Verify generated synthetic records contain explicit origin labels and non-negative counts."""
    db = SessionLocal()
    try:
        warehouses = db.query(Warehouse).all()
        for wh in warehouses:
            assert wh.data_origin == "SYNTHETIC"

        suppliers = db.query(Supplier).all()
        for sup in suppliers:
            assert sup.data_origin == "SYNTHETIC"
            assert sup.lead_time_days > 0
            assert sup.minimum_order_quantity >= 1

        inventories = db.query(Inventory).all()
        for inv in inventories:
            assert inv.data_origin == "SYNTHETIC"
            assert inv.stock_quantity >= 0
            assert inv.reserved_quantity <= inv.stock_quantity
            assert inv.reorder_point >= 0
            assert inv.safety_stock >= 0
    finally:
        db.close()
