"""
Phase 4.3 — Transactional Outbox Pattern & OutboxEvent Generation Test Suite.

Verifies:
1. Successful payment processing atomically creates Payment, links PaymentEvent, and creates OutboxEvent.
2. OutboxEvent is linked to the correct payment aggregate and contains correct canonical event_type.
3. OutboxEvent is committed together with Payment in the same transaction.
4. Failure during OutboxEvent creation rolls back the Payment mutation completely.
5. Already-PROCESSED PaymentEvent does not create another OutboxEvent upon reprocessing.
6. Duplicate/ignored event processing creates zero outbox records.
7. Sequential payment lifecycle transitions create appropriate distinct outbox events.
8. Same-state idempotent transitions (e.g. CAPTURED -> CAPTURED) do not create duplicate outbox events.
9. Cross-merchant processing cannot create an outbox event for another merchant.
10. Outbox payload contains strictly sanitized notification fields (zero credentials, secrets, signatures).
11. Provider independence is preserved across OutboxService and PaymentEventService.
12. Atomicity invariant: Payment + PaymentEvent + OutboxEvent commit or rollback together.
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import hashlib
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.config import settings
from backend.app.models.merchant import Merchant
from backend.app.models.payment import Payment, PaymentStatus
from backend.app.models.payment_event import PaymentEvent, EventProcessingStatus
from backend.app.models.outbox_event import OutboxEvent, OutboxStatus
from backend.app.providers.schemas import NormalizedPayment, PaymentMethodType
from backend.app.services.outbox_service import (
    outbox_service,
    OutboxService,
    MEANINGFUL_NOTIFICATION_STATUSES,
)
from backend.app.services.payment_event_service import (
    payment_event_service,
    PaymentEventService,
)
from backend.app.services.payment_service import (
    CrossMerchantPaymentError,
    PaymentFinancialMismatchError,
    InvalidPaymentStateTransitionError,
)

# Connect to authoritative PostgreSQL test database
pg_engine = create_engine(settings.DATABASE_URL)
PGTestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)


@pytest.fixture
def db():
    """Yield a transactional database session rolled back after every test."""
    connection = pg_engine.connect()
    transaction = connection.begin()
    session = PGTestSessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture
def active_merchant(db) -> Merchant:
    merchant = Merchant(
        id=uuid.uuid4(),
        name="Phase 4.3 Test Kirana",
        business_type="Retail",
        status="ACTIVE",
        currency="INR",
    )
    db.add(merchant)
    db.flush()
    return merchant


def make_payment_event(
    db,
    merchant_id: Optional[uuid.UUID],
    provider: str = "RAZORPAY",
    event_id: Optional[str] = None,
    provider_payment_id: Optional[str] = None,
    event_type: str = "payment.captured",
    processing_status: EventProcessingStatus = EventProcessingStatus.RECEIVED,
) -> PaymentEvent:
    evt_id = event_id or f"evt_p43_{uuid.uuid4().hex[:10]}"
    pay_id = provider_payment_id or f"pay_p43_{uuid.uuid4().hex[:10]}"
    payload_hash = hashlib.sha256(evt_id.encode("utf-8")).hexdigest()

    event = PaymentEvent(
        id=uuid.uuid4(),
        merchant_id=merchant_id,
        payment_id=None,
        provider=provider,
        event_id=evt_id,
        provider_payment_id=pay_id,
        event_type=event_type,
        payload_hash=payload_hash,
        processing_status=processing_status.value,
        received_at=datetime.now(timezone.utc),
    )
    db.add(event)
    db.flush()
    return event


def make_normalized_payment(
    provider_payment_id: str,
    amount_minor: int = 50000,
    status: PaymentStatus = PaymentStatus.CAPTURED,
    currency: str = "INR",
    provider: str = "RAZORPAY",
    payment_method: PaymentMethodType = PaymentMethodType.UPI,
    payer_reference: str = "customer@okaxis",
) -> NormalizedPayment:
    return NormalizedPayment(
        provider=provider,
        provider_payment_id=provider_payment_id,
        provider_order_id="order_p43_test",
        amount_minor=amount_minor,
        currency=currency,
        status=status,
        payment_method=payment_method,
        payer_reference=payer_reference,
        captured_at=datetime.now(timezone.utc) if status == PaymentStatus.CAPTURED else None,
        provider_created_at=datetime.now(timezone.utc),
    )


# =====================================================================
# 1. Successful Processing & Atomic Outbox Generation
# =====================================================================

def test_successful_payment_processing_creates_exactly_one_outbox_event(db, active_merchant):
    """Verify that processing a captured payment atomically generates an OutboxEvent."""
    event = make_payment_event(db=db, merchant_id=active_merchant.id)
    norm = make_normalized_payment(provider_payment_id=event.provider_payment_id, status=PaymentStatus.CAPTURED)

    result = payment_event_service.process_payment_event(
        db=db,
        event_id=event.id,
        normalized_payment=norm,
        auto_commit=False,
    )

    assert result.processing_status == EventProcessingStatus.PROCESSED
    assert result.is_created is True
    assert result.outbox_event_id is not None
    assert result.outbox_event is not None

    # Query outbox table directly
    outbox = db.query(OutboxEvent).filter(OutboxEvent.id == result.outbox_event_id).first()
    assert outbox is not None
    assert outbox.aggregate_type == "PAYMENT"
    assert outbox.aggregate_id == result.payment_id
    assert outbox.event_type == "payment.captured"
    assert outbox.status == OutboxStatus.PENDING.value
    assert outbox.retry_count == 0


def test_outbox_event_is_linked_to_correct_payment_and_merchant(db, active_merchant):
    """Verify the outbox event payload has correct identifiers and clean fields."""
    event = make_payment_event(db=db, merchant_id=active_merchant.id)
    norm = make_normalized_payment(
        provider_payment_id=event.provider_payment_id,
        amount_minor=75000,
        currency="INR",
        payer_reference="merchant.staff@upi",
    )

    result = payment_event_service.process_payment_event(
        db=db, event_id=event.id, normalized_payment=norm
    )

    outbox = db.query(OutboxEvent).filter(OutboxEvent.id == result.outbox_event_id).first()
    payload = outbox.payload

    assert payload["payment_id"] == str(result.payment_id)
    assert payload["merchant_id"] == str(active_merchant.id)
    assert payload["amount_minor"] == 75000
    assert payload["currency"] == "INR"
    assert payload["status"] == "CAPTURED"
    assert payload["payer_reference"] == "merchant.staff@upi"
    assert payload["event_id"] == str(event.id)
    assert payload["provider"] == "RAZORPAY"
    assert payload["provider_payment_id"] == event.provider_payment_id


# =====================================================================
# 2. Transaction Atomicity (Payment + PaymentEvent + OutboxEvent)
# =====================================================================

def test_atomicity_commit_persists_all_three_entities(db, active_merchant):
    """Payment, PaymentEvent, and OutboxEvent are all persisted when transaction commits."""
    event = make_payment_event(db=db, merchant_id=active_merchant.id)
    norm = make_normalized_payment(provider_payment_id=event.provider_payment_id)

    result = payment_event_service.process_payment_event(
        db=db, event_id=event.id, normalized_payment=norm, auto_commit=False
    )
    # Simulate outer transaction commit
    db.flush()

    # All three exist in session
    payment = db.query(Payment).filter(Payment.id == result.payment_id).first()
    ev = db.query(PaymentEvent).filter(PaymentEvent.id == event.id).first()
    ob = db.query(OutboxEvent).filter(OutboxEvent.id == result.outbox_event_id).first()

    assert payment is not None
    assert ev is not None
    assert ev.payment_id == payment.id
    assert ev.processing_status == "PROCESSED"
    assert ob is not None
    assert ob.aggregate_id == payment.id


def test_failure_during_outbox_rolls_back_payment_mutation(db, active_merchant):
    """If outbox event creation fails, the Payment mutation must be completely rolled back."""
    event = make_payment_event(db=db, merchant_id=active_merchant.id)
    norm = make_normalized_payment(provider_payment_id=event.provider_payment_id)

    # Subclass or mock OutboxService to simulate unexpected failure during outbox insertion
    class BrokenOutboxService(OutboxService):
        def create_payment_outbox_event(self, *args, **kwargs):
            raise RuntimeError("Simulated transient database error during outbox write")

    broken_service = PaymentEventService(
        payment_core=payment_event_service._payment_service,
        outbox_core=BrokenOutboxService(),
    )

    with pytest.raises(RuntimeError, match="Simulated transient database error"):
        broken_service.process_payment_event(
            db=db, event_id=event.id, normalized_payment=norm, raise_on_error=True
        )

    # Verify Payment was NOT created (rolled back)
    payment = db.query(Payment).filter(Payment.provider_payment_id == event.provider_payment_id).first()
    assert payment is None

    # Verify zero OutboxEvents exist
    outbox_count = db.query(OutboxEvent).count()
    assert outbox_count == 0

    # Verify event is marked FAILED and payment_id is None
    db.refresh(event)
    assert event.processing_status == EventProcessingStatus.FAILED.value
    assert event.payment_id is None
    assert event.error_code == "RuntimeError"


# =====================================================================
# 3. Idempotency & Duplicate Safety
# =====================================================================

def test_already_processed_event_does_not_create_another_outbox_event(db, active_merchant):
    """Reprocessing an already-PROCESSED PaymentEvent creates ZERO new OutboxEvents."""
    event = make_payment_event(db=db, merchant_id=active_merchant.id)
    norm = make_normalized_payment(provider_payment_id=event.provider_payment_id)

    # 1. First execution creates OutboxEvent
    res1 = payment_event_service.process_payment_event(
        db=db, event_id=event.id, normalized_payment=norm
    )
    assert res1.outbox_event_id is not None

    # 2. Second execution on identical event
    res2 = payment_event_service.process_payment_event(
        db=db, event_id=event.id, normalized_payment=norm
    )
    assert res2.is_duplicate is True
    assert res2.outbox_event_id is None

    # Total outbox events for this payment is strictly 1
    outbox_events = db.query(OutboxEvent).filter(OutboxEvent.aggregate_id == res1.payment_id).all()
    assert len(outbox_events) == 1


def test_duplicate_or_ignored_events_create_zero_outbox_records(db, active_merchant):
    """Events flagged DUPLICATE or IGNORED skip outbox generation."""
    for st in [EventProcessingStatus.DUPLICATE, EventProcessingStatus.IGNORED]:
        evt = make_payment_event(db=db, merchant_id=active_merchant.id, processing_status=st)
        res = payment_event_service.process_payment_event(
            db=db, event_id=evt.id, normalized_payment=make_normalized_payment(evt.provider_payment_id)
        )
        assert res.outbox_event_id is None

    assert db.query(OutboxEvent).count() == 0


def test_same_state_idempotent_repeat_creates_zero_duplicate_outbox_events(db, active_merchant):
    """Repeating the same status (e.g. CAPTURED -> CAPTURED) does NOT generate a duplicate outbox event."""
    pid = f"pay_same_state_{uuid.uuid4().hex[:8]}"

    # Event 1: First time CAPTURED
    evt1 = make_payment_event(db=db, merchant_id=active_merchant.id, provider_payment_id=pid)
    norm1 = make_normalized_payment(provider_payment_id=pid, status=PaymentStatus.CAPTURED)
    res1 = payment_event_service.process_payment_event(db=db, event_id=evt1.id, normalized_payment=norm1)
    assert res1.outbox_event_id is not None
    first_outbox_id = res1.outbox_event_id

    # Event 2: New event, but same status CAPTURED on already-CAPTURED payment
    evt2 = make_payment_event(db=db, merchant_id=active_merchant.id, provider_payment_id=pid)
    norm2 = make_normalized_payment(provider_payment_id=pid, status=PaymentStatus.CAPTURED)
    res2 = payment_event_service.process_payment_event(db=db, event_id=evt2.id, normalized_payment=norm2)

    # Safe repeat: Payment updated/linked, but NO duplicate outbox event
    assert res2.is_created is False
    assert res2.outbox_event_id is None
    assert evt2.payment_id == res1.payment_id

    # Strictly 1 outbox event exists for this payment
    events = db.query(OutboxEvent).filter(OutboxEvent.aggregate_id == res1.payment_id).all()
    assert len(events) == 1
    assert events[0].id == first_outbox_id


# =====================================================================
# 4. Lifecycle Progression & Event Semantics
# =====================================================================

def test_sequential_lifecycle_transitions_generate_distinct_outbox_events(db, active_merchant):
    """Legitimate lifecycle transitions (AUTHORIZED -> CAPTURED -> REFUNDED) create distinct outbox events."""
    pid = f"pay_lifecycle_{uuid.uuid4().hex[:8]}"

    # 1. payment.authorized
    evt1 = make_payment_event(db=db, merchant_id=active_merchant.id, provider_payment_id=pid, event_type="payment.authorized")
    norm1 = make_normalized_payment(provider_payment_id=pid, status=PaymentStatus.AUTHORIZED)
    res1 = payment_event_service.process_payment_event(db=db, event_id=evt1.id, normalized_payment=norm1)
    assert res1.outbox_event_id is not None
    ob1 = db.query(OutboxEvent).filter(OutboxEvent.id == res1.outbox_event_id).first()
    assert ob1.event_type == "payment.authorized"

    # 2. payment.captured
    evt2 = make_payment_event(db=db, merchant_id=active_merchant.id, provider_payment_id=pid, event_type="payment.captured")
    norm2 = make_normalized_payment(provider_payment_id=pid, status=PaymentStatus.CAPTURED)
    res2 = payment_event_service.process_payment_event(db=db, event_id=evt2.id, normalized_payment=norm2)
    assert res2.outbox_event_id is not None
    ob2 = db.query(OutboxEvent).filter(OutboxEvent.id == res2.outbox_event_id).first()
    assert ob2.event_type == "payment.captured"

    # 3. refund.processed
    evt3 = make_payment_event(db=db, merchant_id=active_merchant.id, provider_payment_id=pid, event_type="refund.processed")
    norm3 = make_normalized_payment(provider_payment_id=pid, status=PaymentStatus.REFUNDED)
    res3 = payment_event_service.process_payment_event(db=db, event_id=evt3.id, normalized_payment=norm3)
    assert res3.outbox_event_id is not None
    ob3 = db.query(OutboxEvent).filter(OutboxEvent.id == res3.outbox_event_id).first()
    assert ob3.event_type == "payment.refunded"

    # Total 3 distinct outbox events ordered by sequence
    all_ob = outbox_service.get_outbox_events_for_aggregate(db, "PAYMENT", res1.payment_id)
    assert len(all_ob) == 3
    assert [e.event_type for e in all_ob] == [
        "payment.authorized",
        "payment.captured",
        "payment.refunded",
    ]


def test_unnotified_statuses_do_not_generate_outbox_events(db, active_merchant):
    """Statuses like CREATED or FAILED do not create downstream outbox notification events."""
    pid = f"pay_created_{uuid.uuid4().hex[:8]}"

    # Payment initialized as CREATED
    evt = make_payment_event(db=db, merchant_id=active_merchant.id, provider_payment_id=pid, event_type="order.created")
    norm = make_normalized_payment(provider_payment_id=pid, status=PaymentStatus.CREATED)
    res = payment_event_service.process_payment_event(db=db, event_id=evt.id, normalized_payment=norm)

    assert res.processing_status == EventProcessingStatus.PROCESSED
    assert res.outbox_event_id is None
    assert db.query(OutboxEvent).count() == 0


# =====================================================================
# 5. Security: Tenant Isolation & Payload Sanitization
# =====================================================================

def test_cross_merchant_event_cannot_create_outbox_event(db, active_merchant):
    """An event for Merchant B targeting Merchant A's payment fails with zero outbox events."""
    merchant_b = Merchant(
        id=uuid.uuid4(),
        name="Merchant B",
        business_type="Retail",
        status="ACTIVE",
        currency="INR",
    )
    db.add(merchant_b)
    db.flush()

    pid = f"pay_x_merch_{uuid.uuid4().hex[:8]}"
    # Payment owned by active_merchant
    evt_a = make_payment_event(db=db, merchant_id=active_merchant.id, provider_payment_id=pid)
    norm_a = make_normalized_payment(provider_payment_id=pid, status=PaymentStatus.CAPTURED)
    payment_event_service.process_payment_event(db=db, event_id=evt_a.id, normalized_payment=norm_a)

    initial_outbox_count = db.query(OutboxEvent).count()

    # Merchant B tries to update this payment
    evt_b = make_payment_event(db=db, merchant_id=merchant_b.id, provider_payment_id=pid)
    norm_b = make_normalized_payment(provider_payment_id=pid, status=PaymentStatus.REFUNDED)

    with pytest.raises(CrossMerchantPaymentError):
        payment_event_service.process_payment_event(
            db=db, event_id=evt_b.id, normalized_payment=norm_b, raise_on_error=True
        )

    # Zero new outbox events created
    assert db.query(OutboxEvent).count() == initial_outbox_count


def test_outbox_payload_is_strictly_sanitized(db, active_merchant):
    """Verify that outbox payload contains zero credentials, secrets, or raw signatures."""
    event = make_payment_event(db=db, merchant_id=active_merchant.id)
    norm = make_normalized_payment(provider_payment_id=event.provider_payment_id)

    result = payment_event_service.process_payment_event(db=db, event_id=event.id, normalized_payment=norm)
    outbox = db.query(OutboxEvent).filter(OutboxEvent.id == result.outbox_event_id).first()
    payload = outbox.payload

    forbidden_terms = [
        "secret",
        "key_secret",
        "webhook_secret",
        "password",
        "access_token",
        "refresh_token",
        "signature",
        "x-razorpay-signature",
    ]

    for term in forbidden_terms:
        assert term not in payload
        for key, val in payload.items():
            assert term not in str(key).lower()
            if isinstance(val, str):
                assert term not in val.lower()


# =====================================================================
# 6. Provider Independence
# =====================================================================

def test_outbox_service_and_payment_event_service_zero_provider_coupling():
    """Verify zero direct coupling to Razorpay in outbox_service and payment_event_service."""
    import inspect
    import backend.app.services.outbox_service as ob_mod
    import backend.app.services.payment_event_service as pe_mod

    ob_src = inspect.getsource(ob_mod)
    pe_src = inspect.getsource(pe_mod)

    for src in [ob_src, pe_src]:
        assert "RazorpayClient" not in src
        assert "RazorpayProvider" not in src
        assert "RazorpayWebhookVerifier" not in src
        assert "from backend.app.providers.razorpay" not in src
