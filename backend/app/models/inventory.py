import enum
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import Integer, ForeignKey, Enum, String, DateTime, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base
from backend.app.models.base import TimestampMixin


class MovementType(str, enum.Enum):
    INBOUND = "INBOUND"          # Receiving from supplier
    OUTBOUND = "OUTBOUND"        # Customer sales fulfillment
    TRANSFER = "TRANSFER"        # Inter-warehouse transfer
    ADJUSTMENT = "ADJUSTMENT"    # Stock count discrepancy adjustment
    RETURN = "RETURN"            # Customer return to stock


class Inventory(Base, TimestampMixin):
    """
    Current inventory stock balance by product and location.
    """
    __tablename__ = "inventories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    location_id: Mapped[int] = mapped_column(Integer, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False)

    current_stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reserved_stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    min_stock_level: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    max_stock_level: Mapped[int] = mapped_column(Integer, default=500, nullable=False)

    last_replenished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="inventories")
    location: Mapped["Location"] = relationship("Location", back_populates="inventories")

    __table_args__ = (
        UniqueConstraint("product_id", "location_id", name="uq_product_location_inventory"),
        Index("ix_inventory_product_location", "product_id", "location_id"),
    )

    @property
    def available_stock(self) -> int:
        return max(0, self.current_stock - self.reserved_stock)


class StockMovement(Base, TimestampMixin):
    """
    Ledger of inventory movements (inbound, outbound, transfers, audits).
    """
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    source_location_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("locations.id", ondelete="RESTRICT"), nullable=True)
    destination_location_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("locations.id", ondelete="RESTRICT"), nullable=True)

    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    movement_type: Mapped[MovementType] = mapped_column(
        Enum(MovementType, name="movement_type_enum"),
        nullable=False,
        index=True,
    )
    reference_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="stock_movements")
    source_location: Mapped[Optional["Location"]] = relationship("Location", foreign_keys=[source_location_id])
    destination_location: Mapped[Optional["Location"]] = relationship("Location", foreign_keys=[destination_location_id])

    __table_args__ = (
        Index("ix_movements_timestamp_type", "created_at", "movement_type"),
    )
