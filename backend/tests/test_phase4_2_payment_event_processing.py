"""
Phase 4.2 — PaymentEvent Processing & Payment Core Integration Test Suite.

Verifies:
1. Successful event-to-payment processing pipeline (PaymentEvent -> PaymentService -> Payment).
2. Event linking: PaymentEvent.payment_id correctly linked to the resulting Payment.
3. Event status lifecycle: transitions from RECEIVED to PROCESSED with processed_at timestamp.
4. Transaction atomicity: failures roll back Payment mutations and leave PaymentEvent unlinked.
5. Idempotent processing: repeated processing of the same PaymentEvent is a safe no-op.
6. Multi-event state transitions: sequential events legally transition Payment (e.g. CREATED -> CAPTURED -> REFUNDED).
7. Tenant isolation: event cannot modify or hijack another merchant's Payment.
8. Unresolved merchant handling: events without merchant_id fail gracefully without creating rogue payments.
9. Provider independence: zero direct coupling to Razorpay SDK or client.
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
from backend.app.providers.base import PaymentProvider, register_provider
from backend.app.providers.schemas import NormalizedPayment, NormalizedPaymentEvent, PaymentMethodType
from backend.app.services.payment_event_service import (
    payment_event_service,
    PaymentEventService,
    PaymentEventNotFoundError,
    UnresolvedMerchantEventError,
    NonPaymentEventError,
)
from backend.app.services.payment_service import (
    CrossMerchantPaymentError,
    InvalidPaymentStateTransitionError,
    PaymentFinancialMismatchError,
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
        name="Phase 4.2 Test Kirana",
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
    evt_id = event_id or f"evt_p42_{uuid.uuid4().hex[:10]}"
    pay_id = provider_payment_id or f"pay_p42_{uuid.uuid4().hex[:10]}"
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
    payer_reference: str = "user@okhdfcbank",
) -> NormalizedPayment:
    return NormalizedPayment(
        provider=provider,
        provider_payment_id=provider_payment_id,
        provider_order_id="order_p42_test",
        amount_minor=amount_minor,
        currency=currency,
        status=status,
        payment_method=payment_method,
        payer_reference=payer_reference,
        captured_at=datetime.now(timezone.utc) if status == PaymentStatus.CAPTURED else None,
        provider_created_at=datetime.now(timezone.utc),
    )


# =====================================================================
# 1. Successful Processing & Event-to-Payment Linking
# =====================================================================

def test_process_payment_event_success_creates_payment_and_links(db, active_merchant):
    """Verify that a verified PaymentEvent creates a Payment and links payment_id."""
    event = make_payment_event(db=db, merchant_id=active_merchant.id)
    norm_payment = make_normalized_payment(
        provider_payment_id=event.provider_payment_id,
        amount_minor=20000,
        status=PaymentStatus.CAPTURED,
    )

    result = payment_event_service.process_payment_event(
        db=db,
        event_id=event.id,
        normalized_payment=norm_payment,
        auto_commit=False,
    )

    assert result.processing_status == EventProcessingStatus.PROCESSED
    assert result.is_created is True
    assert result.payment_id is not None
    assert event.payment_id == result.payment_id
    assert event.processing_status == EventProcessingStatus.PROCESSED.value
    assert event.processed_at is not None
    assert event.error_code is None

    # Verify created Payment
    payment = db.query(Payment).filter(Payment.id == result.payment_id).first()
    assert payment is not None
    assert payment.merchant_id == active_merchant.id
    assert payment.amount_minor == 20000
    assert payment.status == PaymentStatus.CAPTURED.value
    assert payment.provider_payment_id == event.provider_payment_id


def test_process_payment_event_from_raw_payload(db, active_merchant):
    """Verify normalizing from raw webhook payload via provider adapter."""
    pid = f"pay_raw_{uuid.uuid4().hex[:10]}"
    event = make_payment_event(db=db, merchant_id=active_merchant.id, provider_payment_id=pid)

    raw_payload = {
        "entity": "event",
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": pid,
                    "amount": 35000,
                    "currency": "INR",
                    "status": "captured",
                    "method": "upi",
                    "vpa": "merchant@icici",
                    "created_at": 1700000000,
                }
            }
        },
    }

    result = payment_event_service.process_payment_event(
        db=db,
        event_id=event.id,
        raw_event_payload=raw_payload,
        auto_commit=False,
    )

    assert result.processing_status == EventProcessingStatus.PROCESSED
    assert result.is_created is True
    assert event.payment_id is not None

    payment = db.query(Payment).filter(Payment.id == result.payment_id).first()
    assert payment.amount_minor == 35000
    assert payment.status == PaymentStatus.CAPTURED.value
    assert payment.payment_method == "UPI"


# =====================================================================
# 2. Sequential Events & State Transitions
# =====================================================================

def test_sequential_events_transition_payment(db, active_merchant):
    """Verify that sequential events transition the payment: CREATED -> CAPTURED -> REFUNDED."""
    pid = f"pay_seq_{uuid.uuid4().hex[:10]}"

    # Event 1: Payment Authorized/Created
    evt1 = make_payment_event(db=db, merchant_id=active_merchant.id, provider_payment_id=pid, event_type="payment.authorized")
    norm1 = make_normalized_payment(provider_payment_id=pid, status=PaymentStatus.AUTHORIZED)
    res1 = payment_event_service.process_payment_event(db=db, event_id=evt1.id, normalized_payment=norm1)
    assert res1.is_created is True
    payment_id = res1.payment_id

    # Event 2: Payment Captured
    evt2 = make_payment_event(db=db, merchant_id=active_merchant.id, provider_payment_id=pid, event_type="payment.captured")
    norm2 = make_normalized_payment(provider_payment_id=pid, status=PaymentStatus.CAPTURED)
    res2 = payment_event_service.process_payment_event(db=db, event_id=evt2.id, normalized_payment=norm2)
    assert res2.is_created is False
    assert res2.payment_id == payment_id
    assert evt2.payment_id == payment_id

    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    assert payment.status == PaymentStatus.CAPTURED.value

    # Event 3: Payment Refunded
    evt3 = make_payment_event(db=db, merchant_id=active_merchant.id, provider_payment_id=pid, event_type="refund.processed")
    norm3 = make_normalized_payment(provider_payment_id=pid, status=PaymentStatus.REFUNDED)
    res3 = payment_event_service.process_payment_event(db=db, event_id=evt3.id, normalized_payment=norm3)
    assert res3.is_created is False
    assert res3.payment_id == payment_id
    assert evt3.payment_id == payment_id

    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    assert payment.status == PaymentStatus.REFUNDED.value


# =====================================================================
# 3. Idempotent Processing (Level 2)
# =====================================================================

def test_idempotent_reprocessing_of_same_event_is_safe_noop(db, active_merchant):
    """Reprocessing an already PROCESSED PaymentEvent returns duplicate=True and preserves payment."""
    event = make_payment_event(db=db, merchant_id=active_merchant.id)
    norm_payment = make_normalized_payment(provider_payment_id=event.provider_payment_id)

    # First execution
    res1 = payment_event_service.process_payment_event(
        db=db, event_id=event.id, normalized_payment=norm_payment
    )
    assert res1.is_created is True
    assert res1.is_duplicate is False

    # Second execution on identical event
    res2 = payment_event_service.process_payment_event(
        db=db, event_id=event.id, normalized_payment=norm_payment
    )
    assert res2.is_duplicate is True
    assert res2.payment_id == res1.payment_id
    assert res2.processing_status == EventProcessingStatus.PROCESSED

    # Exactly 1 Payment in database
    count = db.query(Payment).filter(Payment.provider_payment_id == event.provider_payment_id).count()
    assert count == 1


def test_processing_duplicate_or_ignored_event_skips_cleanly(db, active_merchant):
    """Events marked DUPLICATE or IGNORED skip processing without creating payments."""
    for st in [EventProcessingStatus.DUPLICATE, EventProcessingStatus.IGNORED]:
        evt = make_payment_event(db=db, merchant_id=active_merchant.id, processing_status=st)
        res = payment_event_service.process_payment_event(
            db=db, event_id=evt.id, normalized_payment=make_normalized_payment(evt.provider_payment_id)
        )
        assert res.is_duplicate is True
        assert res.payment_id is None


# =====================================================================
# 4. Atomic Transaction Boundary & Failure Handling
# =====================================================================

def test_atomic_rollback_on_illegal_state_transition(db, active_merchant):
    """Verify that an illegal state transition rolls back payment mutations and marks event FAILED."""
    pid = f"pay_fail_tx_{uuid.uuid4().hex[:10]}"

    # 1. Setup payment as REFUNDED
    evt1 = make_payment_event(db=db, merchant_id=active_merchant.id, provider_payment_id=pid)
    norm1 = make_normalized_payment(provider_payment_id=pid, status=PaymentStatus.CAPTURED)
    res1 = payment_event_service.process_payment_event(db=db, event_id=evt1.id, normalized_payment=norm1)
    norm_ref = make_normalized_payment(provider_payment_id=pid, status=PaymentStatus.REFUNDED)
    evt_ref = make_payment_event(db=db, merchant_id=active_merchant.id, provider_payment_id=pid)
    payment_event_service.process_payment_event(db=db, event_id=evt_ref.id, normalized_payment=norm_ref)

    # Verify payment is currently REFUNDED
    payment = db.query(Payment).filter(Payment.id == res1.payment_id).first()
    assert payment.status == PaymentStatus.REFUNDED.value

    # 2. Try illegal transition: REFUNDED -> CAPTURED
    evt_illegal = make_payment_event(db=db, merchant_id=active_merchant.id, provider_payment_id=pid)
    norm_cap = make_normalized_payment(provider_payment_id=pid, status=PaymentStatus.CAPTURED)

    with pytest.raises(InvalidPaymentStateTransitionError):
        payment_event_service.process_payment_event(
            db=db,
            event_id=evt_illegal.id,
            normalized_payment=norm_cap,
            raise_on_error=True,
        )

    # 3. Verify Payment status did NOT change and is still REFUNDED
    db.refresh(payment)
    assert payment.status == PaymentStatus.REFUNDED.value

    # 4. Verify illegal event is marked FAILED and unlinked
    db.refresh(evt_illegal)
    assert evt_illegal.processing_status == EventProcessingStatus.FAILED.value
    assert evt_illegal.payment_id is None
    assert evt_illegal.error_code == "InvalidPaymentStateTransitionError"
    assert "Illegal payment status transition" in evt_illegal.error_message


def test_atomic_rollback_on_amount_tampering(db, active_merchant):
    """Verify that amount tampering attempt fails atomically and marks event FAILED."""
    pid = f"pay_tamper_{uuid.uuid4().hex[:10]}"
    evt1 = make_payment_event(db=db, merchant_id=active_merchant.id, provider_payment_id=pid)
    norm1 = make_normalized_payment(provider_payment_id=pid, amount_minor=50000, status=PaymentStatus.CAPTURED)
    res1 = payment_event_service.process_payment_event(db=db, event_id=evt1.id, normalized_payment=norm1)

    # Incoming event with different amount
    evt2 = make_payment_event(db=db, merchant_id=active_merchant.id, provider_payment_id=pid)
    norm2 = make_normalized_payment(provider_payment_id=pid, amount_minor=10000, status=PaymentStatus.CAPTURED)

    with pytest.raises(PaymentFinancialMismatchError):
        payment_event_service.process_payment_event(
            db=db, event_id=evt2.id, normalized_payment=norm2, raise_on_error=True
        )

    db.refresh(evt2)
    assert evt2.processing_status == EventProcessingStatus.FAILED.value
    assert evt2.payment_id is None
    assert evt2.error_code == "PaymentFinancialMismatchError"


# =====================================================================
# 5. Tenant Isolation & Unresolved Merchant Safety
# =====================================================================

def test_unresolved_merchant_fails_gracefully_without_payment_creation(db):
    """Events without an active merchant_id fail gracefully with zero payments created."""
    evt = make_payment_event(db=db, merchant_id=None)
    norm = make_normalized_payment(provider_payment_id=evt.provider_payment_id)

    with pytest.raises(UnresolvedMerchantEventError):
        payment_event_service.process_payment_event(
            db=db, event_id=evt.id, normalized_payment=norm, raise_on_error=True
        )

    db.refresh(evt)
    assert evt.processing_status == EventProcessingStatus.FAILED.value
    assert evt.error_code == "UNRESOLVED_MERCHANT"
    assert evt.payment_id is None

    # Zero payments created
    count = db.query(Payment).filter(Payment.provider_payment_id == evt.provider_payment_id).count()
    assert count == 0


def test_cross_merchant_event_hijack_prevention(db, active_merchant):
    """An event for Merchant B cannot alter an existing Payment belonging to Merchant A."""
    merchant_b = Merchant(
        id=uuid.uuid4(),
        name="Merchant B Store",
        business_type="Retail",
        status="ACTIVE",
        currency="INR",
    )
    db.add(merchant_b)
    db.flush()

    pid = f"pay_cross_{uuid.uuid4().hex[:10]}"
    # Payment created under active_merchant (Merchant A)
    evt_a = make_payment_event(db=db, merchant_id=active_merchant.id, provider_payment_id=pid)
    norm_a = make_normalized_payment(provider_payment_id=pid, status=PaymentStatus.CREATED)
    res_a = payment_event_service.process_payment_event(db=db, event_id=evt_a.id, normalized_payment=norm_a)

    # Event arriving for Merchant B with same provider_payment_id
    evt_b = make_payment_event(db=db, merchant_id=merchant_b.id, provider_payment_id=pid)
    norm_b = make_normalized_payment(provider_payment_id=pid, status=PaymentStatus.CAPTURED)

    with pytest.raises(CrossMerchantPaymentError):
        payment_event_service.process_payment_event(
            db=db, event_id=evt_b.id, normalized_payment=norm_b, raise_on_error=True
        )

    db.refresh(evt_b)
    assert evt_b.processing_status == EventProcessingStatus.FAILED.value
    assert evt_b.payment_id is None


# =====================================================================
# 6. Provider Independence & Pluggability
# =====================================================================

def test_payment_event_service_has_zero_razorpay_coupling():
    """Verify PaymentEventService does NOT import Razorpay SDK or client."""
    import inspect
    import backend.app.services.payment_event_service as mod

    source = inspect.getsource(mod)
    assert "RazorpayClient" not in source
    assert "RazorpayProvider" not in source
    assert "LegacyBase" not in source
    assert "legacy.py" not in source


def test_custom_registered_provider_processes_events(db, active_merchant):
    """Verify a pluggable custom provider can be registered and processed seamlessly."""
    class MockBankProvider(PaymentProvider):
        @property
        def provider_name(self) -> str:
            return "MOCKBANK"

        def fetch_payment(self, provider_payment_id: str) -> NormalizedPayment:
            return make_normalized_payment(
                provider_payment_id=provider_payment_id,
                amount_minor=9999,
                provider="MOCKBANK",
                status=PaymentStatus.CAPTURED,
            )

        def verify_payment_status(self, provider_payment_id: str) -> NormalizedPayment:
            return self.fetch_payment(provider_payment_id)

        def normalize_payment_payload(self, raw_payload: dict) -> NormalizedPayment:
            return self.fetch_payment("mock_id")

        def normalize_event_payload(self, raw_payload: dict, raw_payload_bytes=None) -> NormalizedPaymentEvent:
            pass

    register_provider(MockBankProvider())

    pid = f"mock_{uuid.uuid4().hex[:8]}"
    evt = make_payment_event(db=db, merchant_id=active_merchant.id, provider="MOCKBANK", provider_payment_id=pid)

    # Process without passing normalized_payment -> triggers provider.fetch_payment()
    result = payment_event_service.process_payment_event(
        db=db,
        event_id=evt.id,
        auto_commit=False,
    )

    assert result.processing_status == EventProcessingStatus.PROCESSED
    payment = db.query(Payment).filter(Payment.id == result.payment_id).first()
    assert payment.provider == "MOCKBANK"
    assert payment.amount_minor == 9999
