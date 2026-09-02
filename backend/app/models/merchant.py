import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.merchant_user import MerchantUser
    from backend.app.models.provider_connection import ProviderConnection
    from backend.app.models.payment import Payment
    from backend.app.models.payment_event import PaymentEvent
    from backend.app.models.device import Device
    from backend.app.models.voice_notification import VoiceNotification
    from backend.app.models.audit_log import AuditLog


class Merchant(Base):
    """
    Merchant entity representing an onboarded merchant organization or store in VoiceLedger.
    All payments, devices, and provider connections belong to a merchant (tenant isolation).
    """
    __tablename__ = "merchants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    business_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="ACTIVE",
        nullable=False,
        index=True,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="INR",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user_memberships: Mapped[List["MerchantUser"]] = relationship(
        "MerchantUser",
        back_populates="merchant",
        cascade="all, delete-orphan",
    )
    provider_connections: Mapped[List["ProviderConnection"]] = relationship(
        "ProviderConnection",
        back_populates="merchant",
        cascade="all, delete-orphan",
    )
    payments: Mapped[List["Payment"]] = relationship(
        "Payment",
        back_populates="merchant",
    )
    payment_events: Mapped[List["PaymentEvent"]] = relationship(
        "PaymentEvent",
        back_populates="merchant",
    )
    devices: Mapped[List["Device"]] = relationship(
        "Device",
        back_populates="merchant",
        cascade="all, delete-orphan",
    )
    voice_notifications: Mapped[List["VoiceNotification"]] = relationship(
        "VoiceNotification",
        back_populates="merchant",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="merchant",
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("id", uuid.uuid4())
        kwargs.setdefault("status", "ACTIVE")
        kwargs.setdefault("currency", "INR")
        kwargs.setdefault("created_at", datetime.now(timezone.utc))
        kwargs.setdefault("updated_at", datetime.now(timezone.utc))
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return f"<Merchant id={self.id} name={self.name} status={self.status}>"
