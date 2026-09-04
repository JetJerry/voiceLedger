"""
Canonical Sale & Order Models for VoiceLedger.

Connects merchant store sales with canonical Payment records and tracks
outstanding credit balances, multi-item line orders, and payment links.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, BigInteger, Integer, Text, DateTime, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.app.db.base import Base


class Sale(Base):
    """
    Authoritative order and sale transaction record for a merchant.
    Strictly isolated by merchant_id UUID.
    """
    __tablename__ = "sales"

    id = Column(String(50), primary_key=True, default=lambda: f"sale_{uuid.uuid4().hex[:10]}")
    merchant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("merchants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_name = Column(String(255), nullable=True, index=True)
    customer_phone = Column(String(50), nullable=True)

    total_amount_minor = Column(BigInteger, nullable=False, default=0)
    received_amount_minor = Column(BigInteger, nullable=False, default=0)
    outstanding_amount_minor = Column(BigInteger, nullable=False, default=0)

    # Status: PENDING, PARTIAL, PAID, FAILED, CANCELLED
    status = Column(String(50), nullable=False, default="PENDING", index=True)

    # Canonical payment linkage
    payment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Payment provider link metadata
    razorpay_order_id = Column(String(100), nullable=True, index=True)
    razorpay_payment_link_id = Column(String(100), nullable=True, index=True)
    razorpay_payment_link_url = Column(String(500), nullable=True)

    raw_voice_transcript = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    merchant = relationship("Merchant", backref="sales")
    payment = relationship("Payment", backref="sales")
    items = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_sales_merchant_status", "merchant_id", "status"),
        Index("ix_sales_merchant_created", "merchant_id", "created_at"),
    )

    @property
    def total_amount(self) -> float:
        return round(self.total_amount_minor / 100.0, 2)

    @total_amount.setter
    def total_amount(self, val: float) -> None:
        self.total_amount_minor = int(round(val * 100))

    @property
    def received_amount(self) -> float:
        return round(self.received_amount_minor / 100.0, 2)

    @received_amount.setter
    def received_amount(self, val: float) -> None:
        self.received_amount_minor = int(round(val * 100))

    @property
    def outstanding_amount(self) -> float:
        return round(self.outstanding_amount_minor / 100.0, 2)

    @outstanding_amount.setter
    def outstanding_amount(self, val: float) -> None:
        self.outstanding_amount_minor = int(round(val * 100))


class SaleItem(Base):
    """
    Individual line item within a sale.
    """
    __tablename__ = "sale_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sale_id = Column(
        String(50),
        ForeignKey("sales.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    product_name = Column(String(255), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price_minor = Column(BigInteger, nullable=False, default=0)
    subtotal_minor = Column(BigInteger, nullable=False, default=0)

    # Relationships
    sale = relationship("Sale", back_populates="items")
    product = relationship("Product", back_populates="sale_items")

    @property
    def unit_price(self) -> float:
        return round(self.unit_price_minor / 100.0, 2)

    @unit_price.setter
    def unit_price(self, val: float) -> None:
        self.unit_price_minor = int(round(val * 100))

    @property
    def subtotal(self) -> float:
        return round(self.subtotal_minor / 100.0, 2)

    @subtotal.setter
    def subtotal(self, val: float) -> None:
        self.subtotal_minor = int(round(val * 100))
