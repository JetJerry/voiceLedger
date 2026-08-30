from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.app.db.base import Base


class RecoveryAction(Base):
    __tablename__ = "recovery_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sale_id = Column(String(50), ForeignKey("sales.id"), nullable=False, index=True)
    
    # action_type: payment_link_resend, whatsapp_reminder, voice_followup
    action_type = Column(String(50), nullable=False)
    # status: INITIATED, SENT, DELIVERED, FAILED
    status = Column(String(50), nullable=False, default="INITIATED")
    channel = Column(String(50), default="whatsapp", nullable=False)
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    sale = relationship("Sale", back_populates="recovery_actions")
