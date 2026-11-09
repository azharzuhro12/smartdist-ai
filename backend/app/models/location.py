import enum
from typing import List, Optional
from decimal import Decimal
from sqlalchemy import String, Numeric, Integer, Enum, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base
from backend.app.models.base import TimestampMixin


class LocationType(str, enum.Enum):
    WAREHOUSE = "WAREHOUSE"
    DISTRIBUTION_CENTER = "DISTRIBUTION_CENTER"
    RETAIL_STORE = "RETAIL_STORE"


class Location(Base, TimestampMixin):
    """
    Supply chain physical locations (Distribution Centers, Warehouses, Retail Stores).
    """
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    location_type: Mapped[LocationType] = mapped_column(
        Enum(LocationType, name="location_type_enum"),
        default=LocationType.RETAIL_STORE,
        nullable=False,
        index=True,
    )
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    country: Mapped[str] = mapped_column(String(100), default="ID", nullable=False)

    capacity_sqm: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    inventories: Mapped[List["Inventory"]] = relationship("Inventory", back_populates="location", cascade="all, delete-orphan")
    transactions: Mapped[List["Transaction"]] = relationship("Transaction", back_populates="location")
    daily_summaries: Mapped[List["DailySalesSummary"]] = relationship("DailySalesSummary", back_populates="location")
