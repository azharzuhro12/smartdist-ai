import enum
from typing import List, Optional
from datetime import datetime, date, timezone
from decimal import Decimal
from sqlalchemy import (
    String,
    Numeric,
    Integer,
    ForeignKey,
    DateTime,
    Date,
    Enum,
    Boolean,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base
from backend.app.models.base import TimestampMixin


class TransactionStatus(str, enum.Enum):
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class TransactionChannel(str, enum.Enum):
    IN_STORE = "IN_STORE"
    ONLINE = "ONLINE"
    B2B_WHOLESALE = "B2B_WHOLESALE"


class PaymentMethod(str, enum.Enum):
    CASH = "CASH"
    CREDIT_CARD = "CREDIT_CARD"
    DEBIT_CARD = "DEBIT_CARD"
    DIGITAL_WALLET = "DIGITAL_WALLET"
    BANK_TRANSFER = "BANK_TRANSFER"


class Transaction(Base, TimestampMixin):
    """
    Sales transactions (POS, eCommerce, Wholesale orders).
    """
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    location_id: Mapped[int] = mapped_column(Integer, ForeignKey("locations.id", ondelete="RESTRICT"), index=True, nullable=False)
    transaction_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
        nullable=False,
    )

    channel: Mapped[TransactionChannel] = mapped_column(
        Enum(TransactionChannel, name="transaction_channel_enum"),
        default=TransactionChannel.IN_STORE,
        nullable=False,
        index=True,
    )
    status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus, name="transaction_status_enum"),
        default=TransactionStatus.COMPLETED,
        nullable=False,
        index=True,
    )
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method_enum"),
        default=PaymentMethod.CASH,
        nullable=False,
    )

    subtotal_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    customer_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    # Relationships
    location: Mapped["Location"] = relationship("Location", back_populates="transactions")
    items: Mapped[List["TransactionItem"]] = relationship("TransactionItem", back_populates="transaction", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_tx_date_location_status", "transaction_date", "location_id", "status"),
    )


class TransactionItem(Base, TimestampMixin):
    """
    Line items within a sales transaction.
    """
    __tablename__ = "transaction_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[int] = mapped_column(Integer, ForeignKey("transactions.id", ondelete="CASCADE"), index=True, nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), index=True, nullable=False)

    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    # Relationships
    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="items")
    product: Mapped["Product"] = relationship("Product", back_populates="transaction_items")

    __table_args__ = (
        Index("ix_txitem_product_tx", "product_id", "transaction_id"),
    )


class DailySalesSummary(Base, TimestampMixin):
    """
    Aggregated daily sales per product and location, pre-computed for fast analytical queries and ML forecasting features.
    """
    __tablename__ = "daily_sales_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    location_id: Mapped[int] = mapped_column(Integer, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False)

    total_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_revenue: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    total_margin: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    transaction_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Monday, 6=Sunday
    is_weekend: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="daily_summaries")
    location: Mapped["Location"] = relationship("Location", back_populates="daily_summaries")

    __table_args__ = (
        UniqueConstraint("date", "product_id", "location_id", name="uq_daily_product_location_date"),
        Index("ix_daily_sales_date_product_location", "date", "product_id", "location_id"),
    )
