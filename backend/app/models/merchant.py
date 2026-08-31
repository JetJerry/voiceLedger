from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from backend.app.db.base import Base


class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    business_type = Column(String(100), default="Kirana & Retail", nullable=True)  # e.g. Cafe, Stationery, Apparel
    phone = Column(String(20), nullable=True)
    username = Column(String(100), unique=True, nullable=True, index=True)
    password = Column(String(255), default="shop123", nullable=True)
    currency = Column(String(10), default="INR", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_current_active = Column(Boolean, default=False, nullable=False)  # Terminal context
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    products = relationship("Product", back_populates="merchant", cascade="all, delete-orphan")
    customers = relationship("Customer", back_populates="merchant", cascade="all, delete-orphan")
    sales = relationship("Sale", back_populates="merchant", cascade="all, delete-orphan")
