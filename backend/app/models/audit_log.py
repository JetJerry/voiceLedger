import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from backend.app.db.base import Base

PROHIBITED_METADATA_KEYS = {
    "password",
    "secret",
    "jwt",
    "token",
    "access_token",
    "refresh_token",
    "webhook_secret",
    "private_key",
    "cvv",
    "pan",
    "api_key",
}


class AuditLog(Base):
    """
    Immutable, append-only security and operational audit trail for VoiceLedger.
    Records administrative, merchant, device, authentication, and financial state transitions.

    SECURITY INVARIANT:
    Never store passwords, tokens, private keys, cardholder data, or API secrets in metadata.
    """
    __tablename__ = "audit_logs"

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
    actor_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    metadata_: Mapped[Dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        INET,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Relationships
    merchant: Mapped[Optional["Merchant"]] = relationship(
        "Merchant",
        back_populates="audit_logs",
    )

    __table_args__ = (
        Index("ix_audit_logs_merchant_created_at", "merchant_id", "created_at"),
        Index("ix_audit_logs_action_created_at", "action", "created_at"),
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("id", uuid.uuid4())
        kwargs.setdefault("created_at", datetime.now(timezone.utc))
        kwargs.setdefault("metadata_", {})

        if "metadata_" in kwargs and isinstance(kwargs["metadata_"], dict):
            self._validate_metadata(kwargs["metadata_"])

        super().__init__(**kwargs)

    @staticmethod
    def _validate_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(meta, dict):
            raise TypeError(f"metadata must be a dictionary, received: {type(meta).__name__}")
        lowered_keys = {k.lower() for k in meta.keys()}
        prohibited_found = lowered_keys.intersection(PROHIBITED_METADATA_KEYS)
        if prohibited_found:
            raise ValueError(
                f"Prohibited sensitive keys detected in audit metadata: {prohibited_found}. "
                f"Never store credentials, secrets, or tokens in audit logs."
            )
        return meta

    @validates("metadata_")
    def validate_metadata(self, key, value):
        return self._validate_metadata(value)

    def __repr__(self) -> str:
        # Strictly omit metadata contents from string representations to avoid log leakage
        return (
            f"<AuditLog id={self.id} actor_type={self.actor_type} "
            f"action={self.action} resource={self.resource_type} "
            f"created_at={self.created_at}>"
        )
