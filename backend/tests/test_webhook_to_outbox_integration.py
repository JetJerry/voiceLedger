"""
Focused Integration Test: Razorpay Webhook -> PaymentEvent -> Payment -> OutboxEvent.

Verifies:
1. Live Webhook Ingestion & Atomic Processing: Webhook POST creates PaymentEvent (PROCESSED),
   Payment (CAPTURED), and OutboxEvent (PENDING).
2. Level 1 & Level 2 Deduplication: Redelivered webhook returns duplicate=True without duplicate records.
3. Tenant Isolation & Unresolved Merchant Safety: Unknown account_id preserves audit record without creating payment.
"""
import hashlib
import hmac
import json
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.config import settings
from backend.app.models.merchant import Merchant
from backend.app.models.provider_connection import ProviderConnection
from backend.app.models.payment import Payment, PaymentStatus
from backend.app.models.payment_event import PaymentEvent, EventProcessingStatus
from backend.app.models.outbox_event import OutboxEvent, OutboxStatus

pg_engine = create_engine(settings.DATABASE_URL)
PGTestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)

TEST_WEBHOOK_SECRET = settings.RAZORPAY_WEBHOOK_SECRET or "whsec_integration_test_2026"


@pytest.fixture
def db():
    """Transactional session rolled back cleanly after each test."""
    conn = pg_engine.connect()
    trans = conn.begin()
    session = PGTestSessionLocal(bind=conn)
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()


@pytest.fixture
def client(db):
    """FastAPI TestClient with overridden get_db to share transaction."""
    from backend.app.db.session import get_db

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def test_merchant(db) -> Merchant:
    m = Merchant(
        id=uuid.uuid4(),
        name=f"Test Merchant {uuid.uuid4().hex[:6]}",
        business_type="Retail",
        status="ACTIVE",
        currency="INR",
    )
    db.add(m)
    db.flush()
    return m


@pytest.fixture
def test_provider_connection(db, test_merchant) -> ProviderConnection:
    conn = ProviderConnection(
        id=uuid.uuid4(),
        merchant_id=test_merchant.id,
        provider="RAZORPAY",
        provider_account_reference=f"acc_rzp_{uuid.uuid4().hex[:8]}",
        status="ACTIVE",
    )
    db.add(conn)
    db.flush()
    return conn


def sign_payload(raw_bytes: bytes, secret: str = TEST_WEBHOOK_SECRET) -> str:
    return hmac.new(secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()


def make_webhook_payload(event_id: str, payment_id: str, account_id: str, amount_minor: int = 50000) -> dict:
    return {
        "id": event_id,
        "entity": "event",
        "account_id": account_id,
        "event": "payment.captured",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "entity": "payment",
                    "amount": amount_minor,
                    "currency": "INR",
                    "status": "captured",
                    "method": "upi",
                    "vpa": "customer@upi",
                    "created_at": 1725450000,
                }
            }
        },
        "created_at": 1725450000,
    }


def test_webhook_creates_payment_and_outbox_event_atomically(
    client, db, test_merchant, test_provider_connection, monkeypatch
):
    """1. Webhook POST atomically creates PaymentEvent, Payment, and OutboxEvent."""
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    event_id = f"evt_flow_{uuid.uuid4().hex[:8]}"
    payment_id = f"pay_flow_{uuid.uuid4().hex[:8]}"
    payload = make_webhook_payload(
        event_id=event_id,
        payment_id=payment_id,
        account_id=test_provider_connection.provider_account_reference,
        amount_minor=75000,
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = sign_payload(raw_body)

    resp = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "accepted"
    assert data["verified"] is True
    assert data["duplicate"] is False

    # 1. Assert PaymentEvent is persisted and transitioned to PROCESSED
    event = db.query(PaymentEvent).filter(PaymentEvent.event_id == event_id).first()
    assert event is not None
    assert event.merchant_id == test_merchant.id
    assert event.processing_status == EventProcessingStatus.PROCESSED.value
    assert event.payment_id is not None
    assert event.processed_at is not None

    # 2. Assert canonical Payment record is created
    payment = db.query(Payment).filter(Payment.id == event.payment_id).first()
    assert payment is not None
    assert payment.merchant_id == test_merchant.id
    assert payment.provider_payment_id == payment_id
    assert payment.status == PaymentStatus.CAPTURED.value
    assert payment.amount_minor == 75000
    assert payment.currency == "INR"

    # 3. Assert OutboxEvent is created with status PENDING
    outbox = db.query(OutboxEvent).filter(OutboxEvent.aggregate_id == payment.id).first()
    assert outbox is not None
    assert outbox.event_type == "payment.captured"
    assert outbox.status == OutboxStatus.PENDING.value
    assert outbox.payload["amount_minor"] == 75000
    assert outbox.payload["merchant_id"] == str(test_merchant.id)


def test_duplicate_webhook_does_not_create_duplicate_payment_or_outbox(
    client, db, test_merchant, test_provider_connection, monkeypatch
):
    """2. Same webhook delivered twice returns duplicate=True without second Payment or OutboxEvent."""
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    event_id = f"evt_dup_{uuid.uuid4().hex[:8]}"
    payment_id = f"pay_dup_{uuid.uuid4().hex[:8]}"
    payload = make_webhook_payload(
        event_id=event_id,
        payment_id=payment_id,
        account_id=test_provider_connection.provider_account_reference,
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = sign_payload(raw_body)

    # First delivery
    resp1 = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"},
    )
    assert resp1.status_code == 200
    assert resp1.json()["duplicate"] is False

    # Second delivery (duplicate event_id)
    resp2 = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["duplicate"] is True

    # Assert exactly ONE PaymentEvent, ONE Payment, and ONE OutboxEvent exist
    events = db.query(PaymentEvent).filter(PaymentEvent.event_id == event_id).all()
    assert len(events) == 1

    payments = db.query(Payment).filter(Payment.provider_payment_id == payment_id).all()
    assert len(payments) == 1

    outbox_events = db.query(OutboxEvent).filter(OutboxEvent.aggregate_id == payments[0].id).all()
    assert len(outbox_events) == 1


def test_unresolved_merchant_saves_received_event_without_payment(
    client, db, test_merchant, monkeypatch
):
    """3. Webhook with unknown account_id saves PaymentEvent(RECEIVED) with merchant_id=None and creates NO Payment."""
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    event_id = f"evt_unres_{uuid.uuid4().hex[:8]}"
    payment_id = f"pay_unres_{uuid.uuid4().hex[:8]}"
    payload = make_webhook_payload(
        event_id=event_id,
        payment_id=payment_id,
        account_id="acc_nonexistent_unknown_store",
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = sign_payload(raw_body)

    resp = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["duplicate"] is False

    # Assert PaymentEvent is persisted as RECEIVED with merchant_id=None
    event = db.query(PaymentEvent).filter(PaymentEvent.event_id == event_id).first()
    assert event is not None
    assert event.merchant_id is None
    assert event.processing_status == EventProcessingStatus.RECEIVED.value
    assert event.payment_id is None

    # Assert NO Payment and NO OutboxEvent were created
    payment = db.query(Payment).filter(Payment.provider_payment_id == payment_id).first()
    assert payment is None

    outbox = db.query(OutboxEvent).all()
    matching_outbox = [o for o in outbox if o.payload.get("provider_payment_id") == payment_id]
    assert len(matching_outbox) == 0
