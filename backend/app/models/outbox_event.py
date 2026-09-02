import enum
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import (
    String,
    Integer,
    DateTime,
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, validates

from backend.app.db.base import Base


class OutboxStatus(str, enum.Enum):
    """Lifecycle processing states for transactional outbox events."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    DEAD_LETTER = "DEAD_LETTER"


class OutboxEvent(Base):
    """
    Transactional Outbox model ensuring reliable, at-least-once event publication.

    TRANSACTIONAL OUTBOX PATTERN:
    1. Financial state changes (Payment, PaymentEvent) and an OutboxEvent are committed in the SAME
       ACID database transaction.
    2. An asynchronous background worker polls pending outbox events and dispatches them to Redis /
       WebSocket / notification pipelines.
    3. The worker updates outbox status to PUBLISHED upon successful acknowledgment, or increments
       retry_count and calculates backoff for available_at upon failure.
    4. Worker concurrency is safely managed via PostgreSQL:
       `SELECT * FROM outbox_events WHERE status = 'PENDING' AND available_at <= NOW() ... FOR UPDATE SKIP LOCKED`
    """
    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    aggregate_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    aggregate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    payload: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default=OutboxStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
    )
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint("retry_count >= 0", name="ck_outbox_events_retry_count_positive"),
        CheckConstraint("max_retries >= 0", name="ck_outbox_events_max_retries_positive"),
        CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'PUBLISHED', 'FAILED', 'DEAD_LETTER')",
            name="ck_outbox_events_status_valid",
        ),
        # Optimal composite index for high-throughput worker polling and row locking
        Index("ix_outbox_events_worker_claim", "status", "available_at", "created_at"),
        # Index for aggregate event tracing
        Index("ix_outbox_events_aggregate", "aggregate_type", "aggregate_id"),
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("id", uuid.uuid4())
        kwargs.setdefault("status", OutboxStatus.PENDING.value)
        kwargs.setdefault("retry_count", 0)
        kwargs.setdefault("max_retries", 5)
        kwargs.setdefault("created_at", datetime.now(timezone.utc))
        kwargs.setdefault("available_at", datetime.now(timezone.utc))

        if "retry_count" in kwargs:
            val = kwargs["retry_count"]
            if not isinstance(val, int) or val < 0:
                raise ValueError(f"retry_count must be a non-negative integer, received: {val}")

        if "status" in kwargs:
            status_val = kwargs["status"]
            if isinstance(status_val, OutboxStatus):
                kwargs["status"] = status_val.value
            elif status_val not in [s.value for s in OutboxStatus]:
                raise ValueError(f"Invalid outbox status: {status_val}")

        super().__init__(**kwargs)

    @validates("status")
    def validate_status(self, key, value):
        status_str = value.value if isinstance(value, OutboxStatus) else value
        if status_str not in [s.value for s in OutboxStatus]:
            raise ValueError(f"Invalid outbox status: {status_str}")
        return status_str

    @validates("retry_count")
    def validate_retry_count(self, key, value):
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"retry_count must be a non-negative integer, received: {value}")
        return value

    def __repr__(self) -> str:
        return (
            f"<OutboxEvent id={self.id} type={self.event_type} "
            f"aggregate={self.aggregate_type}:{self.aggregate_id} "
            f"status={self.status} retries={self.retry_count}/{self.max_retries}>"
        )
