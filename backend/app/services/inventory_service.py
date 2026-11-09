from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
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
from backend.app.schemas.inventory_forecast import (
    InventoryRecordSummary,
    SupplierSummary,
)


class InventoryService:
    """
    Service responsible for retrieving and validating inventory levels,
    reserved quantities, available stock, and supplier purchasing constraints.
    """

    @classmethod
    def get_inventory_for_product_branch(
        cls,
        db: Session,
        product_id: int,
        branch_id: int,
        warehouse_id: Optional[int] = None,
    ) -> InventoryRecordSummary:
        """
        Retrieve integrated inventory balance and supplier constraints for a product and branch.
        """
        # 1. Validate Product and Branch exist
        product = db.get(Product, product_id)
        if not product:
            raise ValueError(f"Product ID {product_id} not found in database.")

        branch = db.get(Branch, branch_id)
        if not branch:
            raise ValueError(f"Branch ID {branch_id} not found in database.")

        # 2. Resolve Warehouse
        warehouse = None
        if warehouse_id is not None:
            warehouse = db.get(Warehouse, warehouse_id)
        else:
            # Query warehouse directly linked to this branch
            warehouse = db.execute(
                select(Warehouse).where(Warehouse.branch_id == branch_id)
            ).scalars().first()

        # 3. Query Inventory Record
        inventory = None
        if warehouse:
            inventory = db.execute(
                select(Inventory).where(
                    Inventory.product_id == product_id,
                    Inventory.warehouse_id == warehouse.id,
                )
            ).scalars().first()

        # 4. Resolve Stock Balances
        current_stock = None
        reserved_stock = None
        available_stock = None
        reorder_point = None
        safety_stock = None
        last_updated = None
        inv_data_origin = "SYNTHETIC"

        if inventory:
            # Validate physical stock non-negativity
            if inventory.stock_quantity < 0:
                raise ValueError(
                    f"Integrity violation: negative stock quantity ({inventory.stock_quantity}) "
                    f"for product {product_id} in warehouse {inventory.warehouse_id}."
                )

            # Validate reserved stock constraint
            if inventory.reserved_quantity < 0:
                raise ValueError(
                    f"Integrity violation: negative reserved quantity ({inventory.reserved_quantity}) "
                    f"for product {product_id} in warehouse {inventory.warehouse_id}."
                )

            if inventory.reserved_quantity > inventory.stock_quantity:
                logger.warning(
                    f"Reserved stock ({inventory.reserved_quantity}) exceeds current stock ({inventory.stock_quantity}) "
                    f"for product {product_id} in warehouse {inventory.warehouse_id}."
                )

            current_stock = inventory.stock_quantity
            reserved_stock = inventory.reserved_quantity
            # available_stock = current_stock - reserved_stock
            available_stock = current_stock - reserved_stock
            reorder_point = inventory.reorder_point
            safety_stock = inventory.safety_stock
            last_updated = inventory.last_updated
            inv_data_origin = inventory.data_origin

        # 5. Retrieve Supplier Information
        supplier_summary = cls.get_supplier_for_product(db, product_id)

        return InventoryRecordSummary(
            inventory_id=inventory.id if inventory else None,
            product_id=product.id,
            product_code=product.product_code,
            product_name=product.product_name,
            branch_id=branch.id,
            branch_name=branch.branch_name,
            warehouse_id=warehouse.id if warehouse else None,
            warehouse_code=warehouse.warehouse_code if warehouse else None,
            current_stock=current_stock,
            reserved_stock=reserved_stock,
            available_stock=available_stock,
            reorder_point=reorder_point,
            safety_stock=safety_stock,
            last_updated=last_updated,
            data_origin=inv_data_origin,
            supplier=supplier_summary,
        )

    @classmethod
    def get_supplier_for_product(
        cls,
        db: Session,
        product_id: int,
    ) -> Optional[SupplierSummary]:
        """
        Retrieve primary active supplier and purchasing terms for a product.
        Selects active supplier with lowest unit purchasing cost.
        """
        query = (
            select(ProductSupplier, Supplier)
            .join(Supplier, ProductSupplier.supplier_id == Supplier.id)
            .where(
                ProductSupplier.product_id == product_id,
                Supplier.is_active.is_(True),
            )
            .order_by(ProductSupplier.unit_cost.asc())
        )
        result = db.execute(query).first()
        if not result:
            return None

        ps, sup = result
        return SupplierSummary(
            supplier_id=sup.id,
            supplier_code=sup.supplier_code,
            supplier_name=sup.supplier_name,
            lead_time_days=sup.lead_time_days,
            minimum_order_quantity=ps.minimum_order_quantity or sup.minimum_order_quantity,
            order_multiple=None,
            unit_cost=float(ps.unit_cost),
            is_active=sup.is_active,
            data_origin=sup.data_origin,
        )

    @classmethod
    def list_inventory_summaries(
        cls,
        db: Session,
        page: int = 1,
        size: int = 50,
        branch_id: Optional[int] = None,
        product_id: Optional[int] = None,
    ) -> Tuple[List[InventoryRecordSummary], int]:
        """
        List inventory summaries with pagination, returning (items, total_count).
        """
        query = (
            select(Inventory, Product, Warehouse, Branch)
            .join(Product, Inventory.product_id == Product.id)
            .join(Warehouse, Inventory.warehouse_id == Warehouse.id)
            .outerjoin(Branch, Warehouse.branch_id == Branch.id)
        )

        if product_id is not None:
            query = query.where(Inventory.product_id == product_id)
        if branch_id is not None:
            query = query.where(Warehouse.branch_id == branch_id)

        from sqlalchemy import func
        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0

        rows = (
            db.execute(query.order_by(Inventory.id).offset((page - 1) * size).limit(size))
            .all()
        )

        summaries = []
        for inv, prod, wh, br in rows:
            sup_summary = cls.get_supplier_for_product(db, prod.id)
            summaries.append(
                InventoryRecordSummary(
                    inventory_id=inv.id,
                    product_id=prod.id,
                    product_code=prod.product_code,
                    product_name=prod.product_name,
                    branch_id=br.id if br else 0,
                    branch_name=br.branch_name if br else "Unlinked Facility",
                    warehouse_id=wh.id,
                    warehouse_code=wh.warehouse_code,
                    current_stock=inv.stock_quantity,
                    reserved_stock=inv.reserved_quantity,
                    available_stock=inv.stock_quantity - inv.reserved_quantity,
                    reorder_point=inv.reorder_point,
                    safety_stock=inv.safety_stock,
                    last_updated=inv.last_updated,
                    data_origin=inv.data_origin,
                    supplier=sup_summary,
                )
            )

        return summaries, total
