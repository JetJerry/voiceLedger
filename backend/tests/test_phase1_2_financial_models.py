import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import BigInteger, inspect
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql

from backend.app.models.merchant import Merchant
from backend.app.models.payment import Payment, PaymentStatus
from backend.app.models.payment_event import PaymentEvent, EventProcessingStatus


def test_payment_model_creation():
    """Verify canonical Payment model instantiates with UUID, BigInteger amount, and defaults."""
    merchant_id = uuid.uuid4()
    payment = Payment(
        merchant_id=merchant_id,
        provider="razorpay",
        provider_payment_id="pay_test_001",
        provider_order_id="order_test_001",
        amount_minor=50000,  # ₹500.00
        payment_method="upi",
        payer_reference="customer@okaxis",
    )
    assert isinstance(payment.id, uuid.UUID)
    assert payment.merchant_id == merchant_id
    assert payment.provider == "razorpay"
    assert payment.provider_payment_id == "pay_test_001"
    assert payment.provider_order_id == "order_test_001"
    assert payment.amount_minor == 50000
    assert payment.currency == "INR"
    assert payment.payment_method == "upi"
    assert payment.status == PaymentStatus.CREATED.value
    assert payment.payer_reference == "customer@okaxis"
    assert isinstance(payment.created_at, datetime)
    assert isinstance(payment.updated_at, datetime)

    repr_str = repr(payment)
    assert "pay_test_001" in repr_str
    assert "50000" in repr_str
    assert "INR" in repr_str


def test_integer_monetary_representation_and_rejections():
    """Verify that floating-point and negative amounts are strictly rejected."""
    merchant_id = uuid.uuid4()

    # 1. Prohibit floating point numbers (CRITICAL FINANCIAL RULE)
    with pytest.raises(TypeError, match="Financial amounts must use integer minor units"):
        Payment(
            merchant_id=merchant_id,
            provider="razorpay",
            provider_payment_id="pay_float_test",
            amount_minor=500.50,
        )

    # 2. Prohibit negative amounts
    with pytest.raises(ValueError, match="amount_minor cannot be negative"):
        Payment(
            merchant_id=merchant_id,
            provider="razorpay",
            provider_payment_id="pay_neg_test",
            amount_minor=-1000,
        )

    # 3. Prohibit non-integer string amounts
    with pytest.raises(TypeError, match="amount_minor must be an integer"):
        Payment(
            merchant_id=merchant_id,
            provider="razorpay",
            provider_payment_id="pay_str_test",
            amount_minor="50000",
        )

    # 4. Allow large integer minor units (e.g. 100 million paise = 10 lakh INR)
    valid_large_payment = Payment(
        merchant_id=merchant_id,
        provider="razorpay",
        provider_payment_id="pay_large_test",
        amount_minor=100_000_000,
    )
    assert valid_large_payment.amount_minor == 100_000_000


def test_postgresql_bigint_compilation():
    """Verify amount_minor compiles to PostgreSQL BIGINT."""
    table = Payment.__table__
    amount_col = table.c.amount_minor
    assert isinstance(amount_col.type, BigInteger)

    pg_dialect = postgresql.dialect()
    col_ddl = amount_col.type.compile(dialect=pg_dialect)
    assert col_ddl == "BIGINT"


def test_currency_constraints_and_length():
    """Verify currency validation and ISO 4217 length constraints."""
    merchant_id = uuid.uuid4()

    # Valid currency normalized to uppercase
    p = Payment(
        merchant_id=merchant_id,
        provider="razorpay",
        provider_payment_id="pay_curr_test",
        amount_minor=1000,
        currency="usd",
    )
    assert p.currency == "USD"

    # Invalid length raises ValueError
    with pytest.raises(ValueError, match="Currency must be a 3-character code"):
        Payment(
            merchant_id=merchant_id,
            provider="razorpay",
            provider_payment_id="pay_curr_inv1",
            amount_minor=1000,
            currency="US",
        )

    with pytest.raises(ValueError, match="Currency must be a 3-character code"):
        Payment(
            merchant_id=merchant_id,
            provider="razorpay",
            provider_payment_id="pay_curr_inv2",
            amount_minor=1000,
            currency="RUPEES",
        )


def test_valid_and_invalid_payment_states():
    """Verify payment status enforces canonical status enum and rejects invalid states."""
    merchant_id = uuid.uuid4()
    canonical_statuses = [
        PaymentStatus.CREATED,
        PaymentStatus.AUTHORIZED,
        PaymentStatus.CAPTURED,
        PaymentStatus.FAILED,
        PaymentStatus.REFUNDED,
        PaymentStatus.PARTIALLY_REFUNDED,
    ]

    for status_enum in canonical_statuses:
        p = Payment(
            merchant_id=merchant_id,
            provider="razorpay",
            provider_payment_id=f"pay_status_{status_enum.value}",
            amount_minor=1000,
            status=status_enum,
        )
        assert p.status == status_enum.value

    # Reject non-canonical status
    with pytest.raises(ValueError, match="Invalid payment status"):
        Payment(
            merchant_id=merchant_id,
            provider="razorpay",
            provider_payment_id="pay_invalid_status",
            amount_minor=1000,
            status="SUCCESS",  # Non-canonical state
        )


def test_payment_idempotency_unique_constraint():
    """Verify unique constraint and index on (provider, provider_payment_id)."""
    table = Payment.__table__
    unique_col_sets = [
        set(c.name for c in uq.columns)
        for uq in table.constraints
        if hasattr(uq, "columns") and uq.name != "payments_pkey"
    ]
    assert {"provider", "provider_payment_id"} in unique_col_sets

    indexes = [set(c.name for c in idx.columns) for idx in table.indexes]
    assert {"provider", "provider_payment_id"} in indexes
    assert {"merchant_id", "created_at"} in indexes
    assert {"merchant_id", "status", "created_at"} in indexes


def test_payment_event_model_creation():
    """Verify PaymentEvent instantiates with event metadata, payload hash, and defaults."""
    event = PaymentEvent(
        provider="razorpay",
        event_id="event_rzp_987654",
        provider_payment_id="pay_test_001",
        event_type="payment.captured",
        payload_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    assert isinstance(event.id, uuid.UUID)
    assert event.provider == "razorpay"
    assert event.event_id == "event_rzp_987654"
    assert event.provider_payment_id == "pay_test_001"
    assert event.event_type == "payment.captured"
    assert event.payload_hash == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert event.processing_status == EventProcessingStatus.RECEIVED.value
    assert isinstance(event.received_at, datetime)
    assert event.processed_at is None

    repr_str = repr(event)
    assert "event_rzp_987654" in repr_str
    assert "payment.captured" in repr_str


def test_payment_event_to_payment_relationship():
    """Verify bidirectional relationship between Payment and PaymentEvent."""
    merchant_id = uuid.uuid4()
    payment = Payment(
        merchant_id=merchant_id,
        provider="razorpay",
        provider_payment_id="pay_rel_001",
        amount_minor=15000,
    )
    event = PaymentEvent(
        provider="razorpay",
        event_id="evt_rel_001",
        event_type="payment.captured",
        payload_hash="hash001",
    )

    payment.events.append(event)
    assert event in payment.events
    assert event.payment is payment


def test_payment_event_to_merchant_relationship():
    """Verify bidirectional relationship between Merchant and PaymentEvent."""
    merchant = Merchant(name="Apex Store")
    event = PaymentEvent(
        provider="razorpay",
        event_id="evt_merch_001",
        event_type="payment.captured",
        payload_hash="hash002",
        merchant=merchant,
    )
    assert event.merchant is merchant
    assert event in merchant.payment_events


def test_provider_event_uniqueness_and_idempotency_constraints():
    """Verify provider event idempotency constraint on (provider, event_id)."""
    table = PaymentEvent.__table__
    unique_col_sets = [
        set(c.name for c in uq.columns)
        for uq in table.constraints
        if hasattr(uq, "columns") and uq.name != "payment_events_pkey"
    ]
    assert {"provider", "event_id"} in unique_col_sets

    indexes = [set(c.name for c in idx.columns) for idx in table.indexes]
    assert {"provider", "event_type", "received_at"} in indexes
    assert {"provider", "payload_hash"} in indexes


def test_required_fields_and_nullability():
    """Verify critical non-null constraints on financial models."""
    p_table = Payment.__table__
    assert p_table.c.merchant_id.nullable is False
    assert p_table.c.provider.nullable is False
    assert p_table.c.provider_payment_id.nullable is False
    assert p_table.c.amount_minor.nullable is False
    assert p_table.c.currency.nullable is False
    assert p_table.c.status.nullable is False
    assert p_table.c.created_at.nullable is False

    pe_table = PaymentEvent.__table__
    assert pe_table.c.provider.nullable is False
    assert pe_table.c.event_type.nullable is False
    assert pe_table.c.payload_hash.nullable is False
    assert pe_table.c.processing_status.nullable is False
    assert pe_table.c.received_at.nullable is False


def test_postgresql_ddl_compilation():
    """Verify DDL compiles cleanly with PostgreSQL dialect with all checks and constraints."""
    pg_dialect = postgresql.dialect()

    payment_ddl = str(CreateTable(Payment.__table__).compile(dialect=pg_dialect))
    assert "amount_minor BIGINT NOT NULL" in payment_ddl
    assert "CHECK (amount_minor >= 0)" in payment_ddl
    assert "CHECK (length(currency) = 3)" in payment_ddl
    assert "UNIQUE (provider, provider_payment_id)" in payment_ddl
    assert "REFERENCES merchants (id) ON DELETE RESTRICT" in payment_ddl

    event_ddl = str(CreateTable(PaymentEvent.__table__).compile(dialect=pg_dialect))
    assert "payload_hash VARCHAR(64) NOT NULL" in event_ddl
    assert "UNIQUE (provider, event_id)" in event_ddl
    assert "REFERENCES merchants (id) ON DELETE SET NULL" in event_ddl
    assert "REFERENCES payments (id) ON DELETE SET NULL" in event_ddl


def test_no_legacy_payment_mapper_conflict():
    """Verify exactly ONE canonical Payment model exists and maps cleanly in SQLAlchemy."""
    from backend.app.models import Payment as ExportedPayment
    assert ExportedPayment is Payment
    assert ExportedPayment.__table__.name == "payments"
    assert "amount_minor" in ExportedPayment.__table__.columns
