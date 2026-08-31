from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.app.db.base import Base


class MerchantProfile(Base):
    __tablename__ = "merchant_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id"), nullable=False, unique=True, index=True)
    # JSON stored as text for broad DB compatibility (SQLite)
    config_json = Column(Text, nullable=False, default='{}')
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    merchant = relationship("Merchant", backref="profile")
