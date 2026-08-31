from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from backend.app.db.base import Base


class Product(Base):
    """
    Open catalog item — shopkeepers can add ANY item of any category.
    Not limited to a fixed menu; works for kirana, cafe, hardware, clothing, etc.
    """
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    price = Column(Float, nullable=False, default=0.0)
    category = Column(String(100), nullable=True, default="General")
    description = Column(Text, nullable=True)          # Optional item description
    unit = Column(String(50), nullable=True)            # e.g. "kg", "piece", "plate", "glass", "packet"
    is_active = Column(Boolean, default=True, nullable=False)  # Soft delete / hide items
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    merchant = relationship("Merchant", back_populates="products")
    sale_items = relationship("SaleItem", back_populates="product")
