import enum
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    String,
    Text,
    DateTime,
    ForeignKey,
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from backend.app.db.base import Base


class DeviceStatus(str, enum.Enum):
    """Lifecycle and connectivity states for VoiceLedger devices."""
    PAIRING = "PAIRING"
    ACTIVE = "ACTIVE"
    OFFLINE = "OFFLINE"
    DISABLED = "DISABLED"
    REVOKED = "REVOKED"


class DeviceType(str, enum.Enum):
    """Supported physical and application hardware types for voice notification."""
    SOUNDBOX = "SOUNDBOX"
    ANDROID_APP = "ANDROID_APP"
    POS_TERMINAL = "POS_TERMINAL"
    OTHER = "OTHER"


class Device(Base):
    """
    Device entity representing an authenticated voice notification output terminal
    (e.g., dedicated merchant soundbox or Android cashier companion app).

    CRITICAL ARCHITECTURAL PRINCIPLE:
    The device is an OUTPUT endpoint ONLY. It is NOT a financial source of truth.
    It cannot confirm, modify, or originate financial transactions.
    """
    __tablename__ = "devices"

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
    device_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    device_type: Mapped[str] = mapped_column(
        String(50),
        default=DeviceType.SOUNDBOX.value,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default=DeviceStatus.PAIRING.value,
        nullable=False,
        index=True,
    )
    # Cryptographic identity: Public key only. Private keys are NEVER stored in PostgreSQL.
    public_key: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    # Token-based auth fallback: SHA-256 hash of credential token. Plaintext secrets are NEVER stored.
    device_token_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(
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
        back_populates="devices",
    )
    sessions: Mapped[List["DeviceSession"]] = relationship(
        "DeviceSession",
        back_populates="device",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('PAIRING', 'ACTIVE', 'OFFLINE', 'DISABLED', 'REVOKED')",
            name="ck_devices_status_valid",
        ),
        CheckConstraint(
            "device_type IN ('SOUNDBOX', 'ANDROID_APP', 'POS_TERMINAL', 'OTHER')",
            name="ck_devices_type_valid",
        ),
        Index("ix_devices_merchant_status", "merchant_id", "status"),
        Index("ix_devices_merchant_name", "merchant_id", "device_name"),
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("id", uuid.uuid4())
        kwargs.setdefault("device_type", DeviceType.SOUNDBOX.value)
        kwargs.setdefault("status", DeviceStatus.PAIRING.value)
        kwargs.setdefault("created_at", datetime.now(timezone.utc))
        kwargs.setdefault("updated_at", datetime.now(timezone.utc))

        if "status" in kwargs:
            status_val = kwargs["status"]
            if isinstance(status_val, DeviceStatus):
                kwargs["status"] = status_val.value
            elif status_val not in [s.value for s in DeviceStatus]:
                raise ValueError(f"Invalid device status: {status_val}")

        if "device_type" in kwargs:
            type_val = kwargs["device_type"]
            if isinstance(type_val, DeviceType):
                kwargs["device_type"] = type_val.value
            elif type_val not in [t.value for t in DeviceType]:
                raise ValueError(f"Invalid device type: {type_val}")

        super().__init__(**kwargs)

    @validates("status")
    def validate_status(self, key, value):
        status_str = value.value if isinstance(value, DeviceStatus) else value
        if status_str not in [s.value for s in DeviceStatus]:
            raise ValueError(f"Invalid device status: {status_str}")
        return status_str

    @validates("device_type")
    def validate_device_type(self, key, value):
        type_str = value.value if isinstance(value, DeviceType) else value
        if type_str not in [t.value for t in DeviceType]:
            raise ValueError(f"Invalid device type: {type_str}")
        return type_str

    def __repr__(self) -> str:
        # Strictly omit public_key and device_token_hash from string representations
        return (
            f"<Device id={self.id} merchant_id={self.merchant_id} "
            f"name='{self.device_name}' type={self.device_type} status={self.status}>"
        )
