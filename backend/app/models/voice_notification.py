import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    String,
    Text,
    Integer,
    DateTime,
    ForeignKey,
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.merchant import Merchant
    from backend.app.models.device import Device
    from backend.app.models.payment import Payment


class VoiceNotificationStatus(str, enum.Enum):
    """Delivery lifecycle states for real-time soundbox/device voice announcements."""
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class VoiceNotification(Base):
    """
    Delivery record for a voice/speech announcement dispatched to a merchant's soundbox or app.

    CRITICAL FINANCIAL & ARCHITECTURAL RULES:
    1. A voice notification represents a delivery attempt/result ONLY. It is NOT financial truth.
    2. Voice notification status must NEVER alter, determine, or confirm payment status.
    3. Even if voice delivery fails, the underlying payment ledger state remains intact.
    4. Cross-merchant isolation: A notification must only link a Merchant, Device, and Payment
       belonging to the SAME tenant. Service-layer validation must enforce this invariant prior
       to persistence.
    """
    __tablename__ = "voice_notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("merchants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default=VoiceNotificationStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Relationships
    merchant: Mapped["Merchant"] = relationship(
        "Merchant",
        back_populates="voice_notifications",
    )
    device: Mapped["Device"] = relationship(
        "Device",
        back_populates="voice_notifications",
    )
    payment: Mapped["Payment"] = relationship(
        "Payment",
        back_populates="voice_notifications",
    )

    __table_args__ = (
        CheckConstraint("attempt_count >= 0", name="ck_voice_notifications_attempt_count_positive"),
        CheckConstraint(
            "status IN ('PENDING', 'QUEUED', 'DELIVERED', 'FAILED', 'CANCELLED')",
            name="ck_voice_notifications_status_valid",
        ),
        # Indexes for device history and merchant delivery status monitoring
        Index("ix_voice_notifications_device_created_at", "device_id", "created_at"),
        Index("ix_voice_notifications_merchant_status", "merchant_id", "status"),
        Index("ix_voice_notifications_payment_id", "payment_id"),
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("id", uuid.uuid4())
        kwargs.setdefault("status", VoiceNotificationStatus.PENDING.value)
        kwargs.setdefault("attempt_count", 0)
        kwargs.setdefault("created_at", datetime.now(timezone.utc))

        if "attempt_count" in kwargs:
            val = kwargs["attempt_count"]
            if not isinstance(val, int) or val < 0:
                raise ValueError(f"attempt_count must be a non-negative integer, received: {val}")

        if "status" in kwargs:
            status_val = kwargs["status"]
            if isinstance(status_val, VoiceNotificationStatus):
                kwargs["status"] = status_val.value
            elif status_val not in [s.value for s in VoiceNotificationStatus]:
                raise ValueError(f"Invalid voice notification status: {status_val}")

        super().__init__(**kwargs)

    @validates("status")
    def validate_status(self, key, value):
        status_str = value.value if isinstance(value, VoiceNotificationStatus) else value
        if status_str not in [s.value for s in VoiceNotificationStatus]:
            raise ValueError(f"Invalid voice notification status: {status_str}")
        return status_str

    @validates("attempt_count")
    def validate_attempt_count(self, key, value):
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"attempt_count must be a non-negative integer, received: {value}")
        return value

    def __repr__(self) -> str:
        return (
            f"<VoiceNotification id={self.id} merchant_id={self.merchant_id} "
            f"device_id={self.device_id} payment_id={self.payment_id} "
            f"status={self.status} attempts={self.attempt_count}>"
        )
