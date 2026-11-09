import random
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.core.logging import logger
from backend.app.models.business import (
    Branch,
    Inventory,
    Product,
    ProductSupplier,
    Supplier,
    Warehouse,
)
from ml.pipelines.common.constants import (
    DATA_ORIGIN_SYNTHETIC,
    DEFAULT_FAMILY_PRICING,
    FAMILY_PRICE_REFERENCE,
)


class SyntheticInventoryGenerator:
    """
    Generates reproducible synthetic warehouses, suppliers, product costs, and inventory
    stock levels to complement the public sales dataset.
    """

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)

    def generate_warehouses(self, db: Session) -> List[Warehouse]:
        """
        Create strategic regional distribution warehouses mapped to primary branches.
        """
        # Check existing warehouses
        existing = db.execute(select(Warehouse)).scalars().all()
        if existing:
            logger.info(f"Using {len(existing)} existing warehouses.")
            return list(existing)

        branches = db.execute(select(Branch)).scalars().all()
        branch_map = {b.source_store_number: b for b in branches}

        warehouse_configs = [
            {"code": "WH-NORTH-01", "name": "Northern Regional DC (Quito)", "store_nbr": 1, "city": "Quito"},
            {"code": "WH-COAST-01", "name": "Coastal Distribution Hub (Guayaquil)", "store_nbr": 24, "city": "Guayaquil"},
            {"code": "WH-SOUTH-01", "name": "Southern Logistics Center (Cuenca)", "store_nbr": 37, "city": "Cuenca"},
            {"code": "WH-CENTRAL-01", "name": "Central Transit Warehouse (Ambato)", "store_nbr": 50, "city": "Ambato"},
        ]

        warehouses = []
        for cfg in warehouse_configs:
            branch = branch_map.get(cfg["store_nbr"])
            wh = Warehouse(
                warehouse_code=cfg["code"],
                warehouse_name=cfg["name"],
                branch_id=branch.id if branch else None,
                location=f"{cfg['city']} Industrial Logistics Park, Zone {self.rng.randint(1, 5)}",
                data_origin=DATA_ORIGIN_SYNTHETIC,
            )
            db.add(wh)
            warehouses.append(wh)

        db.commit()
        for wh in warehouses:
            db.refresh(wh)
        logger.info(f"Generated {len(warehouses)} synthetic warehouses.")
        return warehouses

    def generate_suppliers(self, db: Session) -> List[Supplier]:
        """
        Generate synthetic merchandise suppliers with varied lead times and MOQs.
        """
        existing = db.execute(select(Supplier)).scalars().all()
        if existing:
            logger.info(f"Using {len(existing)} existing suppliers.")
            return list(existing)

        supplier_templates = [
            {"code": "SUP-GLO-001", "name": "Apex Global Food & Beverage", "lead_time": 5, "moq": 100},
            {"code": "SUP-AGR-002", "name": "Andean Fresh Produce Cooperative", "lead_time": 3, "moq": 50},
            {"code": "SUP-IND-003", "name": "Continental Home & Hardware Ltd", "lead_time": 14, "moq": 25},
            {"code": "SUP-TEX-004", "name": "Pacific Apparel & Textiles Group", "lead_time": 21, "moq": 40},
            {"code": "SUP-ELE-005", "name": "OmniTech Consumer Electronics", "lead_time": 10, "moq": 15},
            {"code": "SUP-CHM-006", "name": "Sanitas Personal & Health Care Corp", "lead_time": 7, "moq": 60},
        ]

        suppliers = []
        for s in supplier_templates:
            supplier = Supplier(
                supplier_code=s["code"],
                supplier_name=s["name"],
                lead_time_days=s["lead_time"],
                minimum_order_quantity=s["moq"],
                is_active=True,
                data_origin=DATA_ORIGIN_SYNTHETIC,
            )
            db.add(supplier)
            suppliers.append(supplier)

        db.commit()
        for s in suppliers:
            db.refresh(s)
        logger.info(f"Generated {len(suppliers)} synthetic suppliers.")
        return suppliers

    def generate_product_suppliers_and_inventory(
        self, db: Session, warehouses: List[Warehouse], suppliers: List[Supplier]
    ) -> Dict[str, int]:
        """
        Assign suppliers to products and generate warehouse inventory balances.
        """
        products = db.execute(select(Product)).scalars().all()
        if not products:
            logger.warning("No products found in database. Ingest products before generating inventory.")
            return {"suppliers_linked": 0, "inventory_records": 0}

        now_utc = datetime.now(timezone.utc)
        inventory_records_created = 0
        product_suppliers_created = 0

        # Existing inventory cache to prevent duplicate inserts
        existing_inv = set(
            db.execute(select(Inventory.product_id, Inventory.warehouse_id)).all()
        )
        existing_ps = set(
            db.execute(select(ProductSupplier.product_id, ProductSupplier.supplier_id)).all()
        )

        for prod in products:
            # 1. Assign 1-2 suppliers per product
            pricing = FAMILY_PRICE_REFERENCE.get(prod.source_family, DEFAULT_FAMILY_PRICING)
            assigned_suppliers = self.rng.sample(suppliers, k=min(2, len(suppliers)))

            for sup in assigned_suppliers:
                if (prod.id, sup.id) not in existing_ps:
                    # Cost jitter +/- 10%
                    cost_factor = Decimal(str(round(self.rng.uniform(0.90, 1.10), 2)))
                    unit_cost = (pricing["unit_cost"] * cost_factor).quantize(Decimal("0.01"))
                    ps = ProductSupplier(
                        product_id=prod.id,
                        supplier_id=sup.id,
                        unit_cost=unit_cost,
                        minimum_order_quantity=sup.minimum_order_quantity,
                    )
                    db.add(ps)
                    product_suppliers_created += 1

            # 2. Assign inventory across warehouses
            for wh in warehouses:
                if (prod.id, wh.id) in existing_inv:
                    continue

                # Realistic inventory distribution
                safety_stock = self.rng.randint(20, 80)
                reorder_point = safety_stock + self.rng.randint(30, 120)
                stock_quantity = self.rng.randint(reorder_point - 10, reorder_point + 250)
                # Reserved is a realistic subset of stock
                reserved_quantity = min(stock_quantity, self.rng.randint(0, int(stock_quantity * 0.3)))

                inv = Inventory(
                    product_id=prod.id,
                    warehouse_id=wh.id,
                    stock_quantity=stock_quantity,
                    reserved_quantity=reserved_quantity,
                    reorder_point=reorder_point,
                    safety_stock=safety_stock,
                    last_updated=now_utc,
                    data_origin=DATA_ORIGIN_SYNTHETIC,
                )
                db.add(inv)
                inventory_records_created += 1

        db.commit()
        logger.info(
            f"Synthetic data generation complete: {product_suppliers_created} product-supplier mappings, {inventory_records_created} inventory records."
        )
        return {
            "suppliers_linked": product_suppliers_created,
            "inventory_records": inventory_records_created,
        }
