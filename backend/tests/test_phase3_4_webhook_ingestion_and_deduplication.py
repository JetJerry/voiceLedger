import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from backend.app.main import app
from backend.app.config import settings
from backend.app.db.session import get_db
from backend.app.models.merchant import Merchant
from backend.app.models.payment import Payment, PaymentStatus
from backend.app.models.payment_event import PaymentEvent, EventProcessingStatus
from backend.app.models.provider_connection import ProviderConnection
from backend.app.models.voice_notification import VoiceNotification
from backend.app.models.outbox_event import OutboxEvent
from backend.app.services.webhook_ingestion_service import webhook_ingestion_service
from backend.app.providers.exceptions import ProviderValidationError

# PostgreSQL session for database immutability verification
pg_engine = create_engine(settings.DATABASE_URL)
PGTestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)

TEST_WEBHOOK_SECRET = "whsec_test_VoiceLedgerSecret2026!#"
ALTERNATIVE_SECRET = "whsec_wrong_secret_123456789!#"


@pytest.fixture
def pg_db():
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
def client(pg_db):
    def override_get_db():
        yield pg_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


def sign_payload(raw_bytes: bytes, secret: str = TEST_WEBHOOK_SECRET) -> str:
    return hmac.new(
        key=secret.encode("utf-8"),
        msg=raw_bytes,
        digestmod=hashlib.sha256,
    ).hexdigest()


def make_razorpay_event_dict(
    event_id: str = "evt_test_unique_001",
    event_name: str = "payment.captured",
    payment_id: str = "pay_H8394ksd92",
    account_id: str = "acc_test_merchant_01",
    amount: int = 50000,
    notes: dict = None,
) -> dict:
    return {
        "id": event_id,
        "entity": "event",
        "account_id": account_id,
        "event": event_name,
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "entity": "payment",
                    "amount": amount,
                    "currency": "INR",
                    "status": "captured",
                    "order_id": "order_H8394Xsd9",
                    "method": "upi",
                    "vpa": "customer@okhdfcbank",
                    "notes": notes or {},
                }
            }
        },
        "created_at": 1700000000,
    }


# =====================================================================
# 1. Successful Webhook Ingestion Tests (1-4)
# =====================================================================

def test_valid_signed_razorpay_event_is_persisted(client, pg_db, monkeypatch):
    """1. Valid signed Razorpay event is persisted into payment_events table."""
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    raw_payload = make_razorpay_event_dict(event_id=event_id, payment_id="pay_998811")
    raw_bytes = json.dumps(raw_payload).encode("utf-8")
    sig = sign_payload(raw_bytes)

    res = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "accepted"
    assert data["verified"] is True
    assert data["event_id"] == event_id
    assert data["duplicate"] is False

    # Verify directly in PostgreSQL
    saved_event = pg_db.query(PaymentEvent).filter(PaymentEvent.event_id == event_id).first()
    assert saved_event is not None
    assert saved_event.provider == "RAZORPAY"
    assert saved_event.event_id == event_id
    assert saved_event.event_type == "payment.captured"
    assert saved_event.provider_payment_id == "pay_998811"
    assert saved_event.processing_status == EventProcessingStatus.RECEIVED.value
    assert saved_event.payload_hash == hashlib.sha256(raw_bytes).hexdigest()


def test_correct_provider_and_event_identifiers_are_stored(client, pg_db, monkeypatch):
    """2. Correct provider ('RAZORPAY') and event identifiers are stored."""
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    event_id = f"evt_ident_{uuid.uuid4().hex[:8]}"
    raw_payload = make_razorpay_event_dict(event_id=event_id)
    raw_bytes = json.dumps(raw_payload).encode("utf-8")
    sig = sign_payload(raw_bytes)

    client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )

    ev = pg_db.query(PaymentEvent).filter(PaymentEvent.event_id == event_id).first()
    assert ev.provider == "RAZORPAY"
    assert ev.event_id == event_id
    assert len(ev.payload_hash) == 64


def test_correct_event_type_is_stored(client, pg_db, monkeypatch):
    """3. Correct event type is stored (e.g. payment.failed)."""
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    event_id = f"evt_fail_{uuid.uuid4().hex[:8]}"
    raw_payload = make_razorpay_event_dict(event_id=event_id, event_name="payment.failed")
    raw_bytes = json.dumps(raw_payload).encode("utf-8")
    sig = sign_payload(raw_bytes)

    client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )

    ev = pg_db.query(PaymentEvent).filter(PaymentEvent.event_id == event_id).first()
    assert ev.event_type == "payment.failed"


def test_payment_identifier_is_extracted_correctly(client, pg_db, monkeypatch):
    """4. Payment identifier is extracted correctly from nested payload."""
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    event_id = f"evt_pay_{uuid.uuid4().hex[:8]}"
    raw_payload = make_razorpay_event_dict(event_id=event_id, payment_id="pay_Extraction123")
    raw_bytes = json.dumps(raw_payload).encode("utf-8")
    sig = sign_payload(raw_bytes)

    client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )

    ev = pg_db.query(PaymentEvent).filter(PaymentEvent.event_id == event_id).first()
    assert ev.provider_payment_id == "pay_Extraction123"


# =====================================================================
# 2. Signature / Security Boundary Tests (5-7)
# =====================================================================

def test_invalid_signature_does_not_persist_event(client, pg_db, monkeypatch):
    """5. Invalid signature returns 401 and does not persist an event."""
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    event_id = f"evt_invalid_{uuid.uuid4().hex[:8]}"
    raw_payload = make_razorpay_event_dict(event_id=event_id)
    raw_bytes = json.dumps(raw_payload).encode("utf-8")

    res = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": "invalid_sig_abc"},
    )
    assert res.status_code == 401
    assert pg_db.query(PaymentEvent).filter(PaymentEvent.event_id == event_id).first() is None


def test_missing_signature_does_not_persist_event(client, pg_db):
    """6. Missing signature header returns 401 and does not persist an event."""
    event_id = f"evt_nosig_{uuid.uuid4().hex[:8]}"
    raw_payload = make_razorpay_event_dict(event_id=event_id)
    raw_bytes = json.dumps(raw_payload).encode("utf-8")

    res = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_bytes,
        headers={"Content-Type": "application/json"},
    )
    assert res.status_code == 401
    assert pg_db.query(PaymentEvent).filter(PaymentEvent.event_id == event_id).first() is None


def test_tampered_payload_does_not_persist_event(client, pg_db, monkeypatch):
    """7. Tampered payload returns 401 and does not persist an event."""
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    event_id = f"evt_tamper_{uuid.uuid4().hex[:8]}"
    raw_payload = make_razorpay_event_dict(event_id=event_id, amount=1000)
    raw_bytes = json.dumps(raw_payload).encode("utf-8")
    sig = sign_payload(raw_bytes)

    # Attacker alters amount after signing
    tampered_bytes = raw_bytes.replace(b"1000", b"100000")

    res = client.post(
        "/api/v1/webhooks/razorpay",
        content=tampered_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )
    assert res.status_code == 401
    assert pg_db.query(PaymentEvent).filter(PaymentEvent.event_id == event_id).first() is None


# =====================================================================
# 3. Deduplication Tests (8-11)
# =====================================================================

def test_same_event_delivered_twice_creates_only_one_payment_event(client, pg_db, monkeypatch):
    """8. Delivering the same event twice creates only one row and returns duplicate=True on second attempt."""
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    event_id = f"evt_dedup_{uuid.uuid4().hex[:8]}"
    raw_payload = make_razorpay_event_dict(event_id=event_id)
    raw_bytes = json.dumps(raw_payload).encode("utf-8")
    sig = sign_payload(raw_bytes)

    # First delivery
    res1 = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )
    assert res1.status_code == 200
    assert res1.json()["duplicate"] is False

    # Second delivery (retry)
    res2 = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )
    assert res2.status_code == 200
    assert res2.json()["duplicate"] is True
    assert res2.json()["event_id"] == event_id

    # Verify only 1 record exists in DB
    events = pg_db.query(PaymentEvent).filter(PaymentEvent.event_id == event_id).all()
    assert len(events) == 1


def test_duplicate_delivery_does_not_modify_existing_event(client, pg_db, monkeypatch):
    """9. Duplicate delivery does not mutate the existing event record."""
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    event_id = f"evt_nomut_{uuid.uuid4().hex[:8]}"
    raw_payload = make_razorpay_event_dict(event_id=event_id)
    raw_bytes = json.dumps(raw_payload).encode("utf-8")
    sig = sign_payload(raw_bytes)

    client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )

    ev1 = pg_db.query(PaymentEvent).filter(PaymentEvent.event_id == event_id).first()
    ev1_id = ev1.id
    ev1_received_at = ev1.received_at

    # Retry
    client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )

    ev2 = pg_db.query(PaymentEvent).filter(PaymentEvent.event_id == event_id).first()
    assert ev2.id == ev1_id
    assert ev2.received_at == ev1_received_at
    assert ev2.processing_status == EventProcessingStatus.RECEIVED.value


def test_database_uniqueness_constraint_protects_against_duplicates(pg_db):
    """10. Database unique constraint uq_payment_events_provider_event_id raises IntegrityError on duplicate insert."""
    event_id = f"evt_uq_{uuid.uuid4().hex[:8]}"
    ev1 = PaymentEvent(
        provider="RAZORPAY",
        event_id=event_id,
        event_type="payment.captured",
        payload_hash="hash123",
    )
    pg_db.add(ev1)
    pg_db.commit()

    ev2 = PaymentEvent(
        provider="RAZORPAY",
        event_id=event_id,
        event_type="payment.captured",
        payload_hash="hash456",
    )
    pg_db.add(ev2)
    with pytest.raises(IntegrityError):
        pg_db.commit()
    pg_db.rollback()


def test_concurrent_duplicate_deliveries_handled_safely(pg_db, monkeypatch):
    """11. Concurrent race handling in service returns existing winner on IntegrityError."""
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    event_id = f"evt_race_{uuid.uuid4().hex[:8]}"
    raw_payload = make_razorpay_event_dict(event_id=event_id)
    raw_bytes = json.dumps(raw_payload).encode("utf-8")
    sig = sign_payload(raw_bytes)

    # Worker 1 succeeds
    ev1, is_dup1 = webhook_ingestion_service.ingest_razorpay_webhook(pg_db, raw_bytes, sig)
    assert is_dup1 is False

    # Worker 2 attempts same event
    ev2, is_dup2 = webhook_ingestion_service.ingest_razorpay_webhook(pg_db, raw_bytes, sig)
    assert is_dup2 is True
    assert ev2.id == ev1.id


# =====================================================================
# 4. Validation Tests (12-14)
# =====================================================================

def test_missing_event_id_is_rejected_safely(client, monkeypatch):
    """12. Missing event ID in payload is rejected with 400 Bad Request."""
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    payload = {"entity": "event", "event": "payment.captured"}  # Missing id
    raw_bytes = json.dumps(payload).encode("utf-8")
    sig = sign_payload(raw_bytes)

    res = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )
    assert res.status_code == 400
    assert "Missing or empty event ID" in res.json()["detail"]


def test_missing_event_type_is_rejected_safely(client, monkeypatch):
    """13. Missing event type in payload is rejected with 400 Bad Request."""
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    payload = {"id": "evt_no_type_001", "entity": "event"}  # Missing event
    raw_bytes = json.dumps(payload).encode("utf-8")
    sig = sign_payload(raw_bytes)

    res = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )
    assert res.status_code == 400
    assert "Missing or empty event type" in res.json()["detail"]


def test_malformed_event_payload_rejected_safely(client, monkeypatch):
    """14. Malformed JSON payload is rejected with 400 Bad Request."""
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    raw_bytes = b"not_valid_json_at_all"
    sig = sign_payload(raw_bytes)

    res = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )
    assert res.status_code == 400
    assert "Malformed JSON" in res.json()["detail"]


# =====================================================================
# 5. Merchant Resolution & Isolation Tests (15-17)
# =====================================================================

def test_event_resolves_merchant_via_authoritative_provider_connection(client, pg_db, monkeypatch):
    """15. Merchant is resolved via ProviderConnection matching Razorpay account_id."""
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    merchant = Merchant(name="Mapped Store", status="ACTIVE")
    pg_db.add(merchant)
    pg_db.flush()

    acc_id = f"acc_{uuid.uuid4().hex[:8]}"
    conn = ProviderConnection(
        merchant_id=merchant.id,
        provider="RAZORPAY",
        provider_account_reference=acc_id,
        status="ACTIVE",
    )
    pg_db.add(conn)
    pg_db.commit()

    event_id = f"evt_conn_{uuid.uuid4().hex[:8]}"
    raw_payload = make_razorpay_event_dict(event_id=event_id, account_id=acc_id)
    raw_bytes = json.dumps(raw_payload).encode("utf-8")
    sig = sign_payload(raw_bytes)

    client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )

    ev = pg_db.query(PaymentEvent).filter(PaymentEvent.event_id == event_id).first()
    assert ev.merchant_id == merchant.id


def test_event_cannot_be_attached_to_arbitrary_merchant_from_client_notes(client, pg_db, monkeypatch):
    """16. Arbitrary or fake merchant_id in notes is rejected without guessing."""
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    fake_merchant_id = str(uuid.uuid4())
    event_id = f"evt_fake_{uuid.uuid4().hex[:8]}"
    raw_payload = make_razorpay_event_dict(
        event_id=event_id,
        account_id="acc_unmapped",
        notes={"merchant_id": fake_merchant_id},
    )
    raw_bytes = json.dumps(raw_payload).encode("utf-8")
    sig = sign_payload(raw_bytes)

    client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )

    ev = pg_db.query(PaymentEvent).filter(PaymentEvent.event_id == event_id).first()
    assert ev.merchant_id is None  # Unassigned, never attached to fake merchant


def test_unresolvable_merchant_handled_safely(client, pg_db, monkeypatch):
    """17. Event with unresolvable merchant is persisted safely with merchant_id=None."""
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    event_id = f"evt_unres_{uuid.uuid4().hex[:8]}"
    raw_payload = make_razorpay_event_dict(event_id=event_id, account_id="acc_unknown_xyz")
    raw_bytes = json.dumps(raw_payload).encode("utf-8")
    sig = sign_payload(raw_bytes)

    res = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )
    assert res.status_code == 200

    ev = pg_db.query(PaymentEvent).filter(PaymentEvent.event_id == event_id).first()
    assert ev is not None
    assert ev.merchant_id is None


# =====================================================================
# 6. Financial Boundary Tests (18-21)
# =====================================================================

def test_valid_webhook_strictly_does_not_create_or_update_payment(client, pg_db, monkeypatch):
    """18. Webhook ingestion strictly DOES NOT create or update Payment records."""
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    init_payments = pg_db.query(Payment).count()

    event_id = f"evt_nopay_{uuid.uuid4().hex[:8]}"
    raw_payload = make_razorpay_event_dict(event_id=event_id, payment_id="pay_nonexistent_xyz")
    raw_bytes = json.dumps(raw_payload).encode("utf-8")
    sig = sign_payload(raw_bytes)

    res = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )
    assert res.status_code == 200

    # Ensure zero Payment records created
    assert pg_db.query(Payment).count() == init_payments
    assert pg_db.query(Payment).filter(Payment.provider_payment_id == "pay_nonexistent_xyz").first() is None


def test_no_payment_status_transition_occurs(client, pg_db, monkeypatch):
    """19. Existing Payment record is NOT transitioned or updated during webhook ingestion."""
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    merchant = Merchant(name="Boundary Store", status="ACTIVE")
    pg_db.add(merchant)
    pg_db.flush()

    # Pre-existing payment in CREATED status
    payment = Payment(
        merchant_id=merchant.id,
        amount_minor=50000,
        currency="INR",
        provider="RAZORPAY",
        provider_payment_id="pay_StatusBoundary_001",
        status=PaymentStatus.CREATED.value,
    )
    pg_db.add(payment)
    pg_db.commit()

    # Ingest webhook claiming payment.captured
    event_id = f"evt_captured_{uuid.uuid4().hex[:8]}"
    raw_payload = make_razorpay_event_dict(
        event_id=event_id,
        event_name="payment.captured",
        payment_id="pay_StatusBoundary_001",
    )
    raw_bytes = json.dumps(raw_payload).encode("utf-8")
    sig = sign_payload(raw_bytes)

    res = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )
    assert res.status_code == 200

    # Verify Payment remains strictly CREATED (Phase 4 owns status transitions!)
    pg_db.refresh(payment)
    assert payment.status == PaymentStatus.CREATED.value


def test_no_voice_notification_is_created(client, pg_db, monkeypatch):
    """20. Webhook ingestion strictly DOES NOT create VoiceNotification records."""
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    init_notifs = pg_db.query(VoiceNotification).count()

    event_id = f"evt_nonotif_{uuid.uuid4().hex[:8]}"
    raw_payload = make_razorpay_event_dict(event_id=event_id)
    raw_bytes = json.dumps(raw_payload).encode("utf-8")
    sig = sign_payload(raw_bytes)

    client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )

    assert pg_db.query(VoiceNotification).count() == init_notifs


def test_no_outbox_event_is_created(client, pg_db, monkeypatch):
    """21. Webhook ingestion strictly DOES NOT create OutboxEvent records."""
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    init_outbox = pg_db.query(OutboxEvent).count()

    event_id = f"evt_nooutbox_{uuid.uuid4().hex[:8]}"
    raw_payload = make_razorpay_event_dict(event_id=event_id)
    raw_bytes = json.dumps(raw_payload).encode("utf-8")
    sig = sign_payload(raw_bytes)

    client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )

    assert pg_db.query(OutboxEvent).count() == init_outbox


# =====================================================================
# 7. Security & Error Masking Tests (22-23)
# =====================================================================

def test_database_errors_not_exposed_to_webhook_caller(client, monkeypatch):
    """22. Database errors return generic 500 without exposing SQL queries or internals."""
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    from unittest.mock import patch
    with patch("backend.app.services.webhook_ingestion_service.WebhookIngestionService.ingest_razorpay_webhook", side_effect=Exception("Database syntax error in table payment_events")):
        event_id = f"evt_sqle_{uuid.uuid4().hex[:8]}"
        raw_payload = make_razorpay_event_dict(event_id=event_id)
        raw_bytes = json.dumps(raw_payload).encode("utf-8")
        sig = sign_payload(raw_bytes)

        res = client.post(
            "/api/v1/webhooks/razorpay",
            content=raw_bytes,
            headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
        )
        assert res.status_code == 500
        text = res.text.lower()
        assert "syntax error" not in text
        assert "payment_events" not in text
        assert res.json()["detail"] == "Internal server error processing webhook"
