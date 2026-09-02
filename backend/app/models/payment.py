import enum
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    String,
    BigInteger,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from backend.app.db.base import Base


class PaymentStatus(str, enum.Enum):
    """Canonical payment statuses for VoiceLedger ledger transactions."""
    CREATED = "CREATED"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"


class Payment(Base):
    """
    Authoritative financial ledger record for a payment.
    Enforces integer minor units (paise for INR), strict idempotency on
    (provider, provider_payment_id), and immutable provider association.
    """
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("merchants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    provider_payment_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    provider_order_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    amount_minor: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="INR",
        nullable=False,
    )
    payment_method: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default=PaymentStatus.CREATED.value,
        nullable=False,
        index=True,
    )
    payer_reference: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    provider_created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    captured_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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
    merchant: Mapped["Merchant"] = relationship(
        "Merchant",
        back_populates="payments",
    )
    events: Mapped[List["PaymentEvent"]] = relationship(
        "PaymentEvent",
        back_populates="payment",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        # Primary financial idempotency constraint
        UniqueConstraint("provider", "provider_payment_id", name="uq_payments_provider_payment_id"),
        # Strict financial non-negative amount constraint
        CheckConstraint("amount_minor >= 0", name="ck_payments_amount_minor_non_negative"),
        # Currency code ISO 4217 length constraint (3 characters)
        CheckConstraint("length(currency) = 3", name="ck_payments_currency_length"),
        # Canonical status constraint
        CheckConstraint(
            "status IN ('CREATED', 'AUTHORIZED', 'CAPTURED', 'FAILED', 'REFUNDED', 'PARTIALLY_REFUNDED')",
            name="ck_payments_status_valid",
        ),
        # Performance indexes for merchant queries
        Index("ix_payments_merchant_created_at", "merchant_id", "created_at"),
        Index("ix_payments_merchant_status_created_at", "merchant_id", "status", "created_at"),
        Index("ix_payments_provider_payment_id", "provider", "provider_payment_id"),
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("id", uuid.uuid4())
        kwargs.setdefault("currency", "INR")
        kwargs.setdefault("status", PaymentStatus.CREATED.value)
        kwargs.setdefault("created_at", datetime.now(timezone.utc))
        kwargs.setdefault("updated_at", datetime.now(timezone.utc))

        # Financial validation for amount_minor
        if "amount_minor" in kwargs:
            val = kwargs["amount_minor"]
            self._validate_amount_minor(val)

        # Status validation
        if "status" in kwargs:
            status_val = kwargs["status"]
            if isinstance(status_val, PaymentStatus):
                kwargs["status"] = status_val.value
            elif status_val not in [s.value for s in PaymentStatus]:
                raise ValueError(f"Invalid payment status: {status_val}")

        # Currency validation
        if "currency" in kwargs:
            curr_val = kwargs["currency"]
            if not isinstance(curr_val, str) or len(curr_val) != 3:
                raise ValueError(f"Currency must be a 3-character code, received: {curr_val}")
            kwargs["currency"] = curr_val.upper()

        super().__init__(**kwargs)

    @staticmethod
    def _validate_amount_minor(val) -> int:
        if isinstance(val, float):
            raise TypeError(
                f"Financial amounts must use integer minor units (paise). "
                f"Floating-point values are prohibited. Received float: {val}"
            )
        if not isinstance(val, int):
            raise TypeError(f"amount_minor must be an integer, received: {type(val).__name__}")
        if val < 0:
            raise ValueError(f"amount_minor cannot be negative, received: {val}")
        return val

    @validates("amount_minor")
    def validate_amount_minor(self, key, value):
        return self._validate_amount_minor(value)

    @validates("currency")
    def validate_currency(self, key, value):
        if not isinstance(value, str) or len(value) != 3:
            raise ValueError(f"Currency must be a 3-character code, received: {value}")
        return value.upper()

    @validates("status")
    def validate_status(self, key, value):
        status_str = value.value if isinstance(value, PaymentStatus) else value
        if status_str not in [s.value for s in PaymentStatus]:
            raise ValueError(f"Invalid payment status: {status_str}")
        return status_str

    def __repr__(self) -> str:
        return (
            f"<Payment id={self.id} merchant_id={self.merchant_id} "
            f"provider={self.provider} provider_payment_id={self.provider_payment_id} "
            f"amount_minor={self.amount_minor} currency={self.currency} status={self.status}>"
        )
