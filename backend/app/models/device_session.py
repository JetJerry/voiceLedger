import enum
import uuid
from datetime import datetime, timezone
from typing import Optional
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


class DeviceSessionStatus(str, enum.Enum):
    """Active connectivity and validity states for an authenticated device session."""
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class DeviceSession(Base):
    """
    Authenticated realtime session record for a VoiceLedger device (e.g. active WebSocket connection).
    Inherits its tenant merchant scope exclusively through its parent Device relationship.
    Stores SHA-256 session token hashes; never stores plaintext tokens or passwords.
    """
    __tablename__ = "device_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Cryptographic SHA-256 hash of the session token. Plaintext tokens are NEVER stored.
    session_token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default=DeviceSessionStatus.CONNECTED.value,
        nullable=False,
        index=True,
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),  # Supports standard IPv4 and IPv6 string notations
        nullable=True,
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    device: Mapped["Device"] = relationship(
        "Device",
        back_populates="sessions",
    )

    __table_args__ = (
        UniqueConstraint("session_token_hash", name="uq_device_sessions_token_hash"),
        CheckConstraint(
            "status IN ('CONNECTED', 'DISCONNECTED', 'EXPIRED', 'REVOKED')",
            name="ck_device_sessions_status_valid",
        ),
        Index("ix_device_sessions_device_status", "device_id", "status"),
        Index("ix_device_sessions_expires_at", "expires_at"),
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("id", uuid.uuid4())
        kwargs.setdefault("status", DeviceSessionStatus.CONNECTED.value)
        kwargs.setdefault("created_at", datetime.now(timezone.utc))
        kwargs.setdefault("last_activity_at", datetime.now(timezone.utc))

        if "status" in kwargs:
            status_val = kwargs["status"]
            if isinstance(status_val, DeviceSessionStatus):
                kwargs["status"] = status_val.value
            elif status_val not in [s.value for s in DeviceSessionStatus]:
                raise ValueError(f"Invalid session status: {status_val}")

        super().__init__(**kwargs)

    @validates("status")
    def validate_status(self, key, value):
        status_str = value.value if isinstance(value, DeviceSessionStatus) else value
        if status_str not in [s.value for s in DeviceSessionStatus]:
            raise ValueError(f"Invalid session status: {status_str}")
        return status_str

    @property
    def is_expired(self) -> bool:
        """Check whether the session has reached its expiry timestamp."""
        now = datetime.now(timezone.utc)
        return now >= self.expires_at or self.status == DeviceSessionStatus.EXPIRED.value

    @property
    def is_active(self) -> bool:
        """Check whether the session is currently active and not revoked/expired."""
        return self.status == DeviceSessionStatus.CONNECTED.value and not self.is_expired and self.revoked_at is None

    def __repr__(self) -> str:
        # Never leak session_token_hash in string representations
        return (
            f"<DeviceSession id={self.id} device_id={self.device_id} "
            f"status={self.status} expires_at={self.expires_at}>"
        )
