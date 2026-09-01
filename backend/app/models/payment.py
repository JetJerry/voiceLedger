from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from backend.app.db.base import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sale_id = Column(String(50), ForeignKey("sales.id"), nullable=True, index=True)
    
    razorpay_payment_id = Column(String(100), unique=True, index=True, nullable=False)
    razorpay_order_id = Column(String(100), nullable=True, index=True)
    razorpay_payment_link_id = Column(String(100), nullable=True, index=True)
    
    amount = Column(Float, nullable=False)  # in INR (converted from paise)
    currency = Column(String(10), default="INR", nullable=False)
    status = Column(String(50), nullable=False)  # captured, authorized, failed, refunded
    method = Column(String(50), nullable=True)  # upi, card, netbanking, wallet
    
    vpa = Column(String(100), nullable=True)  # UPI ID
    email = Column(String(255), nullable=True)
    contact = Column(String(50), nullable=True)
    
    error_code = Column(String(100), nullable=True)
    error_description = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    sale = relationship("Sale", back_populates="payments")


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(150), unique=True, index=True, nullable=False)
    event_type = Column(String(100), nullable=False, index=True)
    payload = Column(Text, nullable=False)
    processed = Column(Boolean, default=False, nullable=False)
    status = Column(String(50), default="RECEIVED", nullable=True)  # PROCESSED, SIGNATURE_FAILED, RECONCILIATION_FAILED, DUPLICATE
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    processed_at = Column(DateTime, nullable=True)
