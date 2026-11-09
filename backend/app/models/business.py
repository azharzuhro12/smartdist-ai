from typing import List, Optional
from decimal import Decimal
from datetime import date, datetime, timezone
from sqlalchemy import (
    String,
    Numeric,
    Integer,
    BigInteger,
    ForeignKey,
    Text,
    Boolean,
    Date,
    DateTime,
    UniqueConstraint,
    CheckConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base
from backend.app.models.base import TimestampMixin


class Category(Base, TimestampMixin):
    """
    Product categories matching or extending retail merchandise families.
    """
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    category_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    products: Mapped[List["Product"]] = relationship("Product", back_populates="category")


class Product(Base, TimestampMixin):
    """
    Master product catalog.
    """
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("categories.id", ondelete="RESTRICT"), index=True, nullable=False)
    source_family: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    unit_of_measure: Mapped[str] = mapped_column(String(20), default="UNIT", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    data_origin: Mapped[str] = mapped_column(String(50), default="KAGGLE_PUBLIC", nullable=False)

    # Relationships
    category: Mapped["Category"] = relationship("Category", back_populates="products")
    daily_sales: Mapped[List["DailySale"]] = relationship("DailySale", back_populates="product")
    inventories: Mapped[List["Inventory"]] = relationship("Inventory", back_populates="product")
    product_suppliers: Mapped[List["ProductSupplier"]] = relationship("ProductSupplier", back_populates="product")


class Branch(Base, TimestampMixin):
    """
    Retail branches and retail stores mapped from the Kaggle dataset.
    """
    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    branch_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    branch_name: Mapped[str] = mapped_column(String(150), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_store_number: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    store_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    cluster: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    data_origin: Mapped[str] = mapped_column(String(50), default="KAGGLE_PUBLIC", nullable=False)

    # Relationships
    warehouses: Mapped[List["Warehouse"]] = relationship("Warehouse", back_populates="branch")
    daily_sales: Mapped[List["DailySale"]] = relationship("DailySale", back_populates="branch")


class Warehouse(Base, TimestampMixin):
    """
    Regional distribution centers and warehouse facilities.
    """
    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    warehouse_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    warehouse_name: Mapped[str] = mapped_column(String(150), nullable=False)
    branch_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    data_origin: Mapped[str] = mapped_column(String(50), default="SYNTHETIC", nullable=False)

    # Relationships
    branch: Mapped[Optional["Branch"]] = relationship("Branch", back_populates="warehouses")
    inventories: Mapped[List["Inventory"]] = relationship("Inventory", back_populates="warehouse")


class Supplier(Base, TimestampMixin):
    """
    Merchandise suppliers and distribution partners.
    """
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    supplier_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    supplier_name: Mapped[str] = mapped_column(String(150), nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    minimum_order_quantity: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    data_origin: Mapped[str] = mapped_column(String(50), default="SYNTHETIC", nullable=False)

    # Relationships
    product_suppliers: Mapped[List["ProductSupplier"]] = relationship("ProductSupplier", back_populates="supplier")


class ProductSupplier(Base, TimestampMixin):
    """
    Association between products and suppliers including cost and MOQ.
    """
    __tablename__ = "product_suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    supplier_id: Mapped[int] = mapped_column(Integer, ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False, index=True)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    minimum_order_quantity: Mapped[int] = mapped_column(Integer, default=10, nullable=False)

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="product_suppliers")
    supplier: Mapped["Supplier"] = relationship("Supplier", back_populates="product_suppliers")

    __table_args__ = (
        UniqueConstraint("product_id", "supplier_id", name="uq_product_supplier"),
        CheckConstraint("unit_cost >= 0", name="chk_unit_cost_non_negative"),
        CheckConstraint("minimum_order_quantity >= 1", name="chk_supplier_moq_positive"),
    )


class Inventory(Base, TimestampMixin):
    """
    Current stock level, reserved quantity, and inventory replenishment thresholds.
    """
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(Integer, ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False, index=True)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reserved_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reorder_point: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    safety_stock: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    data_origin: Mapped[str] = mapped_column(String(50), default="SYNTHETIC", nullable=False)

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="inventories")
    warehouse: Mapped["Warehouse"] = relationship("Warehouse", back_populates="inventories")

    __table_args__ = (
        UniqueConstraint("product_id", "warehouse_id", name="uq_inventory_product_warehouse"),
        CheckConstraint("stock_quantity >= 0", name="chk_stock_quantity_non_negative"),
        CheckConstraint("reserved_quantity >= 0", name="chk_reserved_quantity_non_negative"),
        CheckConstraint("reserved_quantity <= stock_quantity", name="chk_reserved_le_stock"),
        CheckConstraint("reorder_point >= 0", name="chk_reorder_point_non_negative"),
        CheckConstraint("safety_stock >= 0", name="chk_safety_stock_non_negative"),
    )

    @property
    def available_quantity(self) -> int:
        return max(0, self.stock_quantity - self.reserved_quantity)


class DailySale(Base, TimestampMixin):
    """
    Daily aggregated sales by date, branch, and product, directly reflecting public sales records.
    """
    __tablename__ = "daily_sales"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sale_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    branch_id: Mapped[int] = mapped_column(Integer, ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    quantity_sold: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=Decimal("0.0"), nullable=False)
    sales_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    promotion_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_dataset: Mapped[str] = mapped_column(String(100), default="store-sales-time-series-forecasting", nullable=False)
    data_origin: Mapped[str] = mapped_column(String(50), default="KAGGLE_PUBLIC", nullable=False)

    # Relationships
    branch: Mapped["Branch"] = relationship("Branch", back_populates="daily_sales")
    product: Mapped["Product"] = relationship("Product", back_populates="daily_sales")

    @property
    def is_amount_estimated(self) -> bool:
        """
        Flag indicating that sales_amount is derived from observed quantity_sold
        multiplied by estimated family unit pricing, rather than an observed POS total.
        """
        return True

    __table_args__ = (
        UniqueConstraint("sale_date", "branch_id", "product_id", name="uq_daily_sales_date_branch_product"),
        CheckConstraint("quantity_sold >= 0", name="chk_quantity_sold_non_negative"),
        CheckConstraint("sales_amount >= 0", name="chk_sales_amount_non_negative"),
        CheckConstraint("promotion_quantity >= 0", name="chk_promotion_quantity_non_negative"),
        Index("ix_daily_sales_date_branch", "sale_date", "branch_id"),
        Index("ix_daily_sales_date_product", "sale_date", "product_id"),
    )
