import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.merchant import Merchant
    from backend.app.models.payment import Payment


class EventProcessingStatus(str, enum.Enum):
    """Processing statuses for incoming provider payment events."""
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"
    DUPLICATE = "DUPLICATE"
    IGNORED = "IGNORED"


class PaymentEvent(Base):
    """
    Immutable audit record of a payment event received from a payment provider (e.g. Razorpay).
    Contains normalized event metadata, SHA-256 payload fingerprint, and processing state.
    Raw secrets and sensitive credentials are never stored.
    """
    __tablename__ = "payment_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    merchant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("merchants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    payment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    event_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    provider_payment_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    payload_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    processing_status: Mapped[str] = mapped_column(
        String(50),
        default=EventProcessingStatus.RECEIVED.value,
        nullable=False,
        index=True,
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_code: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Relationships
    merchant: Mapped[Optional["Merchant"]] = relationship(
        "Merchant",
        back_populates="payment_events",
    )
    payment: Mapped[Optional["Payment"]] = relationship(
        "Payment",
        back_populates="events",
    )

    __table_args__ = (
        # Level 1 Idempotency: Unique provider event identifier constraint
        UniqueConstraint("provider", "event_id", name="uq_payment_events_provider_event_id"),
        # Processing status check constraint
        CheckConstraint(
            "processing_status IN ('RECEIVED', 'PROCESSING', 'PROCESSED', 'FAILED', 'DUPLICATE', 'IGNORED')",
            name="ck_payment_events_status_valid",
        ),
        # Audit query and deduplication indexes
        Index("ix_payment_events_provider_type_received", "provider", "event_type", "received_at"),
        Index("ix_payment_events_payload_hash", "provider", "payload_hash"),
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("id", uuid.uuid4())
        kwargs.setdefault("processing_status", EventProcessingStatus.RECEIVED.value)
        kwargs.setdefault("received_at", datetime.now(timezone.utc))

        if "processing_status" in kwargs:
            status_val = kwargs["processing_status"]
            if isinstance(status_val, EventProcessingStatus):
                kwargs["processing_status"] = status_val.value
            elif status_val not in [s.value for s in EventProcessingStatus]:
                raise ValueError(f"Invalid processing status: {status_val}")

        super().__init__(**kwargs)

    @validates("processing_status")
    def validate_processing_status(self, key, value):
        status_str = value.value if isinstance(value, EventProcessingStatus) else value
        if status_str not in [s.value for s in EventProcessingStatus]:
            raise ValueError(f"Invalid processing status: {status_str}")
        return status_str

    def __repr__(self) -> str:
        return (
            f"<PaymentEvent id={self.id} provider={self.provider} "
            f"event_id={self.event_id} event_type={self.event_type} "
            f"status={self.processing_status} received_at={self.received_at}>"
        )
