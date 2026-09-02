import uuid
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql

from backend.app.models.merchant import Merchant
from backend.app.models.device import Device
from backend.app.models.payment import Payment
from backend.app.models.voice_notification import VoiceNotification, VoiceNotificationStatus
from backend.app.models.audit_log import AuditLog
from backend.app.models.outbox_event import OutboxEvent, OutboxStatus


# ==============================================================================
# VoiceNotification Tests
# ==============================================================================

def test_voice_notification_model_creation():
    """1. Verify VoiceNotification creation with UUID, status, and attempt defaults."""
    merchant_id = uuid.uuid4()
    device_id = uuid.uuid4()
    payment_id = uuid.uuid4()

    notification = VoiceNotification(
        merchant_id=merchant_id,
        device_id=device_id,
        payment_id=payment_id,
        message="500 rupaye prapt hue",
    )
    assert isinstance(notification.id, uuid.UUID)
    assert notification.merchant_id == merchant_id
    assert notification.device_id == device_id
    assert notification.payment_id == payment_id
    assert notification.message == "500 rupaye prapt hue"
    assert notification.status == VoiceNotificationStatus.PENDING.value
    assert notification.attempt_count == 0
    assert isinstance(notification.created_at, datetime)
    assert notification.delivered_at is None
    assert notification.last_attempt_at is None
    assert notification.error_message is None


def test_voice_notification_required_fields():
    """2. Verify nullability constraints on VoiceNotification table columns."""
    table = VoiceNotification.__table__
    assert table.c.merchant_id.nullable is False
    assert table.c.device_id.nullable is False
    assert table.c.payment_id.nullable is False
    assert table.c.message.nullable is False
    assert table.c.status.nullable is False
    assert table.c.attempt_count.nullable is False
    assert table.c.created_at.nullable is False
    assert table.c.delivered_at.nullable is True
    assert table.c.error_message.nullable is True


def test_voice_notification_relationships():
    """3, 4, 5. Verify bidirectional relationships to Merchant, Device, and Payment."""
    merchant = Merchant(name="City Grocers")
    device = Device(device_name="Soundbox 1", merchant=merchant)
    payment = Payment(
        merchant=merchant,
        provider="razorpay",
        provider_payment_id="pay_notif_001",
        amount_minor=25000,
    )

    notification = VoiceNotification(
        merchant=merchant,
        device=device,
        payment=payment,
        message="250 rupees received",
    )

    assert notification.merchant is merchant
    assert notification.device is device
    assert notification.payment is payment

    assert notification in merchant.voice_notifications
    assert notification in device.voice_notifications
    assert notification in payment.voice_notifications


def test_voice_notification_status_validation():
    """6. Verify valid and invalid VoiceNotification statuses."""
    valid_statuses = [
        VoiceNotificationStatus.PENDING,
        VoiceNotificationStatus.QUEUED,
        VoiceNotificationStatus.DELIVERED,
        VoiceNotificationStatus.FAILED,
        VoiceNotificationStatus.CANCELLED,
    ]
    for st in valid_statuses:
        vn = VoiceNotification(
            merchant_id=uuid.uuid4(),
            device_id=uuid.uuid4(),
            payment_id=uuid.uuid4(),
            message="Test",
            status=st,
        )
        assert vn.status == st.value

    # Reject invalid status
    with pytest.raises(ValueError, match="Invalid voice notification status"):
        VoiceNotification(
            merchant_id=uuid.uuid4(),
            device_id=uuid.uuid4(),
            payment_id=uuid.uuid4(),
            message="Test",
            status="SUCCESS",
        )


def test_voice_notification_attempt_count_validation():
    """7. Verify non-negative attempt_count enforcement."""
    vn = VoiceNotification(
        merchant_id=uuid.uuid4(),
        device_id=uuid.uuid4(),
        payment_id=uuid.uuid4(),
        message="Test",
        attempt_count=3,
    )
    assert vn.attempt_count == 3

    # Reject negative attempt count
    with pytest.raises(ValueError, match="attempt_count must be a non-negative integer"):
        VoiceNotification(
            merchant_id=uuid.uuid4(),
            device_id=uuid.uuid4(),
            payment_id=uuid.uuid4(),
            message="Test",
            attempt_count=-1,
        )


def test_voice_notification_timestamps():
    """8. Verify delivery and attempt timestamps."""
    now = datetime.now(timezone.utc)
    vn = VoiceNotification(
        merchant_id=uuid.uuid4(),
        device_id=uuid.uuid4(),
        payment_id=uuid.uuid4(),
        message="Test",
        status=VoiceNotificationStatus.DELIVERED,
        delivered_at=now,
        last_attempt_at=now,
    )
    assert vn.delivered_at == now
    assert vn.last_attempt_at == now


def test_voice_notification_postgresql_ddl_compilation():
    """9. Verify PostgreSQL DDL compilation with foreign keys and check constraints."""
    pg_dialect = postgresql.dialect()
    ddl = str(CreateTable(VoiceNotification.__table__).compile(dialect=pg_dialect))
    assert "CREATE TABLE voice_notifications" in ddl
    assert "UUID" in ddl
    assert "REFERENCES merchants (id) ON DELETE CASCADE" in ddl
    assert "REFERENCES devices (id) ON DELETE CASCADE" in ddl
    assert "REFERENCES payments (id) ON DELETE CASCADE" in ddl
    assert "CHECK (attempt_count >= 0)" in ddl
    assert "CHECK (status IN ('PENDING', 'QUEUED', 'DELIVERED', 'FAILED', 'CANCELLED'))" in ddl


def test_voice_notification_not_financial_truth():
    """10. Verify that VoiceNotification has NO fields that define payment state or financial ledger data."""
    vn_columns = set(VoiceNotification.__table__.columns.keys())
    prohibited_financial_fields = {
        "amount",
        "amount_minor",
        "currency",
        "payment_status",
        "captured_at",
        "payer_reference",
        "provider_payment_id",
    }
    overlap = vn_columns.intersection(prohibited_financial_fields)
    assert len(overlap) == 0, f"VoiceNotification illegally contains financial ledger fields: {overlap}"


# ==============================================================================
# AuditLog Tests
# ==============================================================================

def test_audit_log_model_creation():
    """11. Verify AuditLog creation with UUID, actor, action, and JSONB metadata."""
    merchant_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    resource_id = uuid.uuid4()

    audit = AuditLog(
        merchant_id=merchant_id,
        actor_type="USER",
        actor_id=actor_id,
        action="DEVICE_PAIRED",
        resource_type="DEVICE",
        resource_id=resource_id,
        metadata_={"device_name": "Front Soundbox", "pairing_mode": "manual"},
        ip_address="192.168.1.50",
    )
    assert isinstance(audit.id, uuid.UUID)
    assert audit.merchant_id == merchant_id
    assert audit.actor_type == "USER"
    assert audit.actor_id == actor_id
    assert audit.action == "DEVICE_PAIRED"
    assert audit.resource_type == "DEVICE"
    assert audit.resource_id == resource_id
    assert audit.metadata_["device_name"] == "Front Soundbox"
    assert audit.ip_address == "192.168.1.50"
    assert isinstance(audit.created_at, datetime)


def test_audit_log_nullable_fields():
    """12. Verify nullable merchant_id and resource_id for system/admin events."""
    audit = AuditLog(
        merchant_id=None,  # System-wide or unauthenticated action
        actor_type="SYSTEM",
        action="SERVER_STARTUP",
        resource_type="APPLICATION",
    )
    assert audit.merchant_id is None
    assert audit.actor_id is None
    assert audit.resource_id is None
    assert audit.ip_address is None

    table = AuditLog.__table__
    assert table.c.merchant_id.nullable is True
    assert table.c.actor_id.nullable is True
    assert table.c.resource_id.nullable is True
    assert table.c.ip_address.nullable is True
    assert table.c.action.nullable is False
    assert table.c.actor_type.nullable is False
    assert table.c.resource_type.nullable is False


def test_audit_log_jsonb_and_inet_compilation():
    """13, 14. Verify JSONB metadata and INET IP address types compile to PostgreSQL."""
    table = AuditLog.__table__
    pg_dialect = postgresql.dialect()

    metadata_type = table.c.metadata.type.compile(dialect=pg_dialect)
    assert metadata_type == "JSONB"

    ip_type = table.c.ip_address.type.compile(dialect=pg_dialect)
    assert ip_type == "INET"


def test_audit_log_merchant_relationship():
    """15. Verify relationship between Merchant and AuditLog."""
    merchant = Merchant(name="Central Mart")
    audit = AuditLog(
        merchant=merchant,
        actor_type="ADMIN",
        action="MERCHANT_ACTIVATED",
        resource_type="MERCHANT",
    )
    assert audit.merchant is merchant
    assert audit in merchant.audit_logs


def test_audit_log_sensitive_metadata_rejection():
    """16. Verify that sensitive credentials/tokens are strictly rejected from audit metadata."""
    with pytest.raises(ValueError, match="Prohibited sensitive keys detected"):
        AuditLog(
            actor_type="USER",
            action="LOGIN_FAILED",
            resource_type="SESSION",
            metadata_={"user_email": "test@example.com", "password": "PlainTextPassword123"},
        )

    with pytest.raises(ValueError, match="Prohibited sensitive keys detected"):
        AuditLog(
            actor_type="WEBHOOK",
            action="SIGNATURE_VERIFIED",
            resource_type="WEBHOOK",
            metadata_={"webhook_secret": "whsec_supersecret"},
        )


def test_audit_log_sanitized_repr():
    """17. Verify AuditLog __repr__ omits metadata to avoid log exposure."""
    audit = AuditLog(
        actor_type="USER",
        action="DEVICE_RENAMED",
        resource_type="DEVICE",
        metadata_={"old_name": "Old", "new_name": "New"},
    )
    repr_str = repr(audit)
    assert "DEVICE_RENAMED" in repr_str
    assert "old_name" not in repr_str
    assert "New" not in repr_str


def test_audit_log_postgresql_ddl_compilation():
    """18. Verify clean PostgreSQL DDL compilation for AuditLog table."""
    pg_dialect = postgresql.dialect()
    ddl = str(CreateTable(AuditLog.__table__).compile(dialect=pg_dialect))
    assert "CREATE TABLE audit_logs" in ddl
    assert "metadata JSONB NOT NULL" in ddl
    assert "ip_address INET" in ddl
    assert "REFERENCES merchants (id) ON DELETE SET NULL" in ddl


# ==============================================================================
# OutboxEvent Tests
# ==============================================================================

def test_outbox_event_model_creation():
    """19, 20, 21, 22. Verify OutboxEvent creation with aggregate identity and JSONB payload."""
    payment_id = uuid.uuid4()
    payload_data = {
        "payment_id": str(payment_id),
        "amount_minor": 50000,
        "currency": "INR",
        "provider": "razorpay",
    }

    event = OutboxEvent(
        event_type="payment.captured",
        aggregate_type="PAYMENT",
        aggregate_id=payment_id,
        payload=payload_data,
    )
    assert isinstance(event.id, uuid.UUID)
    assert event.event_type == "payment.captured"
    assert event.aggregate_type == "PAYMENT"
    assert event.aggregate_id == payment_id
    assert event.payload == payload_data
    assert event.status == OutboxStatus.PENDING.value
    assert event.retry_count == 0
    assert event.max_retries == 5
    assert isinstance(event.available_at, datetime)
    assert isinstance(event.created_at, datetime)
    assert event.processed_at is None
    assert event.error_message is None


def test_outbox_event_status_validation():
    """23. Verify canonical OutboxStatus states and rejection of invalid values."""
    valid_statuses = [
        OutboxStatus.PENDING,
        OutboxStatus.PROCESSING,
        OutboxStatus.PUBLISHED,
        OutboxStatus.FAILED,
        OutboxStatus.DEAD_LETTER,
    ]
    for st in valid_statuses:
        evt = OutboxEvent(
            event_type="test.event",
            aggregate_type="TEST",
            aggregate_id=uuid.uuid4(),
            payload={},
            status=st,
        )
        assert evt.status == st.value

    with pytest.raises(ValueError, match="Invalid outbox status"):
        OutboxEvent(
            event_type="test.event",
            aggregate_type="TEST",
            aggregate_id=uuid.uuid4(),
            payload={},
            status="COMPLETED",
        )


def test_outbox_event_retry_tracking():
    """24. Verify retry_count tracking and non-negative constraints."""
    evt = OutboxEvent(
        event_type="test.retry",
        aggregate_type="TEST",
        aggregate_id=uuid.uuid4(),
        payload={},
        retry_count=2,
        max_retries=10,
    )
    assert evt.retry_count == 2
    assert evt.max_retries == 10

    with pytest.raises(ValueError, match="retry_count must be a non-negative integer"):
        OutboxEvent(
            event_type="test.retry",
            aggregate_type="TEST",
            aggregate_id=uuid.uuid4(),
            payload={},
            retry_count=-1,
        )


def test_outbox_event_availability_and_processed_timestamps():
    """25, 26. Verify delayed available_at for backoff and processed_at timestamps."""
    now = datetime.now(timezone.utc)
    future_retry = now + timedelta(minutes=2)

    evt = OutboxEvent(
        event_type="test.backoff",
        aggregate_type="TEST",
        aggregate_id=uuid.uuid4(),
        payload={},
        status=OutboxStatus.PENDING,
        available_at=future_retry,
    )
    assert evt.available_at == future_retry
    assert evt.processed_at is None

    # Simulate worker completion
    evt.status = OutboxStatus.PUBLISHED.value
    evt.processed_at = datetime.now(timezone.utc)
    assert evt.status == OutboxStatus.PUBLISHED.value
    assert evt.processed_at is not None


def test_outbox_event_worker_indexes():
    """27. Verify composite worker claim index for high-throughput row locking."""
    table = OutboxEvent.__table__
    index_cols = [
        [c.name for c in idx.columns]
        for idx in table.indexes
    ]
    # Worker claim index: (status, available_at, created_at)
    assert ["status", "available_at", "created_at"] in index_cols
    # Aggregate lookup index: (aggregate_type, aggregate_id)
    assert ["aggregate_type", "aggregate_id"] in index_cols


def test_outbox_event_postgresql_ddl_compilation():
    """28. Verify clean PostgreSQL DDL compilation for OutboxEvent table."""
    pg_dialect = postgresql.dialect()
    ddl = str(CreateTable(OutboxEvent.__table__).compile(dialect=pg_dialect))
    assert "CREATE TABLE outbox_events" in ddl
    assert "payload JSONB NOT NULL" in ddl
    assert "CHECK (retry_count >= 0)" in ddl
    assert "CHECK (max_retries >= 0)" in ddl
    assert "CHECK (status IN ('PENDING', 'PROCESSING', 'PUBLISHED', 'FAILED', 'DEAD_LETTER'))" in ddl


def test_outbox_event_at_least_once_semantics():
    """29. Verify outbox model supports at-least-once delivery semantics via retry and error tracking."""
    event = OutboxEvent(
        event_type="payment.captured",
        aggregate_type="PAYMENT",
        aggregate_id=uuid.uuid4(),
        payload={"amount_minor": 1000},
        status=OutboxStatus.FAILED,
        retry_count=1,
        max_retries=5,
        error_message="Redis connection timeout",
    )
    assert event.status == OutboxStatus.FAILED.value
    assert event.retry_count == 1
    assert event.error_message == "Redis connection timeout"
    # Event remains un-processed (processed_at is None) until successfully published
    assert event.processed_at is None
