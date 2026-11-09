from typing import List, Optional
from decimal import Decimal
from sqlalchemy import String, Numeric, Integer, ForeignKey, Text, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base
from backend.app.models.base import TimestampMixin


class Category(Base, TimestampMixin):
    """
    Product Category hierarchy.
    """
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    parent: Mapped[Optional["Category"]] = relationship("Category", remote_side=[id], back_populates="subcategories")
    subcategories: Mapped[List["Category"]] = relationship("Category", back_populates="parent")
    products: Mapped[List["Product"]] = relationship("Product", back_populates="category")


class Supplier(Base, TimestampMixin):
    """
    Product Suppliers and Vendors.
    """
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    contact_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    reliability_score: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("0.95"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    products: Mapped[List["Product"]] = relationship("Product", back_populates="supplier")


class Product(Base, TimestampMixin):
    """
    Master Product Catalog.
    """
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("categories.id", ondelete="RESTRICT"), index=True, nullable=False)
    supplier_id: Mapped[int] = mapped_column(Integer, ForeignKey("suppliers.id", ondelete="RESTRICT"), index=True, nullable=False)

    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    weight_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 3), nullable=True)

    # Inventory planning parameters
    reorder_point: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    safety_stock: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    category: Mapped["Category"] = relationship("Category", back_populates="products")
    supplier: Mapped["Supplier"] = relationship("Supplier", back_populates="products")
    inventories: Mapped[List["Inventory"]] = relationship("Inventory", back_populates="product", cascade="all, delete-orphan")
    transaction_items: Mapped[List["TransactionItem"]] = relationship("TransactionItem", back_populates="product")
    stock_movements: Mapped[List["StockMovement"]] = relationship("StockMovement", back_populates="product")
    daily_summaries: Mapped[List["DailySalesSummary"]] = relationship("DailySalesSummary", back_populates="product")

    __table_args__ = (
        Index("ix_products_category_supplier", "category_id", "supplier_id"),
    )
