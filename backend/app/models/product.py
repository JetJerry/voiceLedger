"""
Canonical Product Model for VoiceLedger Store & Catalog.

Maintains tenant isolation (scoped to merchant_id UUID) and represents
monetary prices strictly as integer minor units (price_minor).
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, BigInteger, Integer, Boolean, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from backend.app.db.base import Base


class Product(Base):
    """
    Authoritative catalog item for a merchant's store.
    Supports dynamic categories, custom units, stock inventory tracking,
    and open JSONB attributes (e.g. brand, size, expiry).
    """
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("merchants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False, index=True)
    price_minor = Column(BigInteger, nullable=False, default=0)
    category = Column(String(100), nullable=False, default="General", index=True)
    description = Column(Text, nullable=True)
    unit = Column(String(50), nullable=True, default="piece")
    stock_quantity = Column(Integer, nullable=False, default=0)
    track_inventory = Column(Boolean, nullable=False, default=False)
    attributes = Column(JSONB, nullable=False, default=dict)
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    merchant = relationship("Merchant", backref="products")
    sale_items = relationship("SaleItem", back_populates="product")

    __table_args__ = (
        Index("ix_products_merchant_name", "merchant_id", "name"),
        Index("ix_products_merchant_category", "merchant_id", "category"),
        Index("ix_products_merchant_active", "merchant_id", "is_active"),
    )

    @property
    def price(self) -> float:
        """Helper property to access price in major currency units (INR rupees)."""
        return round(self.price_minor / 100.0, 2)

    @price.setter
    def price(self, value: float) -> None:
        """Helper setter to convert major currency units to minor units (paise)."""
        self.price_minor = int(round(value * 100))
