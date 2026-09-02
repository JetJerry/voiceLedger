"""
Legacy Prototype Models — Preserved for backward compatibility and isolated from
the canonical VoiceLedger financial architecture.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text
)
from sqlalchemy.orm import declarative_base, relationship

LegacyBase = declarative_base()


class LegacyMerchant(LegacyBase):
    __tablename__ = "merchants"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    business_type = Column(String(100), default="Kirana & Retail", nullable=True)
    phone = Column(String(20), nullable=True)
    username = Column(String(100), unique=True, nullable=True, index=True)
    password = Column(String(255), default="shop123", nullable=True)
    currency = Column(String(10), default="INR", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_current_active = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    products = relationship("Product", back_populates="merchant", cascade="all, delete-orphan")
    customers = relationship("Customer", back_populates="merchant", cascade="all, delete-orphan")
    sales = relationship("Sale", back_populates="merchant", cascade="all, delete-orphan")
    profile = relationship("MerchantProfile", back_populates="merchant", uselist=False, cascade="all, delete-orphan")


class Customer(LegacyBase):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    merchant = relationship("LegacyMerchant", back_populates="customers")
    sales = relationship("Sale", back_populates="customer")


class Product(LegacyBase):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    price = Column(Float, nullable=False, default=0.0)
    category = Column(String(100), nullable=True, default="General")
    description = Column(Text, nullable=True)
    unit = Column(String(50), nullable=True)
    attributes = Column(Text, nullable=True, default="{}")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    merchant = relationship("LegacyMerchant", back_populates="products")
    sale_items = relationship("SaleItem", back_populates="product")


class Sale(LegacyBase):
    __tablename__ = "sales"

    id = Column(String(50), primary_key=True, default=lambda: f"sale_{uuid.uuid4().hex[:10]}")
    merchant_id = Column(Integer, ForeignKey("merchants.id"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    customer_name = Column(String(255), nullable=True, index=True)

    total_amount = Column(Float, nullable=False, default=0.0)
    received_amount = Column(Float, nullable=False, default=0.0)
    outstanding_amount = Column(Float, nullable=False, default=0.0)
    status = Column(String(50), nullable=False, default="PENDING", index=True)

    razorpay_payment_link_id = Column(String(100), nullable=True, index=True)
    razorpay_payment_link_url = Column(String(500), nullable=True)

    raw_voice_transcript = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    merchant = relationship("LegacyMerchant", back_populates="sales")
    customer = relationship("Customer", back_populates="sales")
    items = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="sale")
    recovery_actions = relationship("RecoveryAction", back_populates="sale", cascade="all, delete-orphan")


class SaleItem(LegacyBase):
    __tablename__ = "sale_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sale_id = Column(String(50), ForeignKey("sales.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    product_name = Column(String(255), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Float, nullable=False, default=0.0)
    subtotal = Column(Float, nullable=False, default=0.0)

    sale = relationship("Sale", back_populates="items")
    product = relationship("Product", back_populates="sale_items")


class Payment(LegacyBase):
    __tablename__ = "legacy_payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sale_id = Column(String(50), ForeignKey("sales.id"), nullable=True, index=True)

    razorpay_payment_id = Column(String(100), unique=True, index=True, nullable=False)
    razorpay_order_id = Column(String(100), nullable=True, index=True)
    razorpay_payment_link_id = Column(String(100), nullable=True, index=True)

    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="INR", nullable=False)
    status = Column(String(50), nullable=False)
    method = Column(String(50), nullable=True)

    vpa = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)
    contact = Column(String(50), nullable=True)

    error_code = Column(String(100), nullable=True)
    error_description = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    sale = relationship("Sale", back_populates="payments")


class WebhookEvent(LegacyBase):
    __tablename__ = "legacy_webhook_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(150), unique=True, index=True, nullable=False)
    event_type = Column(String(100), nullable=False, index=True)
    payload = Column(Text, nullable=False)
    processed = Column(Boolean, default=False, nullable=False)
    status = Column(String(50), default="RECEIVED", nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    processed_at = Column(DateTime, nullable=True)


class RecoveryAction(LegacyBase):
    __tablename__ = "recovery_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sale_id = Column(String(50), ForeignKey("sales.id"), nullable=False, index=True)
    action_type = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False, default="INITIATED")
    channel = Column(String(50), default="whatsapp", nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    sale = relationship("Sale", back_populates="recovery_actions")


class MerchantProfile(LegacyBase):
    __tablename__ = "merchant_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id"), nullable=False, unique=True, index=True)
    config_json = Column(Text, nullable=False, default='{}')
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    merchant = relationship("LegacyMerchant", back_populates="profile")
