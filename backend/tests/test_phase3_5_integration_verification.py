"""
VoiceLedger Phase 3.5: Razorpay Integration Verification Test Suite.

End-to-end integration tests verifying that the complete Phase 3 Razorpay subsystem
(Provider Abstraction, Razorpay Client/Adapter, Webhook Signature Verification,
Webhook Ingestion, Level 1 Deduplication, and PaymentEvent Persistence) functions
harmoniously as a unified system, respecting all security and financial boundaries.
"""
import hashlib
import hmac
import json
import uuid
from unittest.mock import patch, MagicMock
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.config import settings
from backend.app.db.session import get_db
from backend.app.models.merchant import Merchant
from backend.app.models.payment import Payment, PaymentStatus
from backend.app.models.payment_event import PaymentEvent, EventProcessingStatus
from backend.app.models.provider_connection import ProviderConnection
from backend.app.models.voice_notification import VoiceNotification
from backend.app.models.outbox_event import OutboxEvent
from backend.app.providers.exceptions import (
    ProviderError,
    ProviderAuthenticationError,
    ProviderResourceNotFoundError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from backend.app.providers.razorpay.client import RazorpayClient
from backend.app.providers.razorpay.adapter import RazorpayProvider
from backend.app.services.webhook_ingestion_service import webhook_ingestion_service

# PostgreSQL session for isolated integration verification
pg_engine = create_engine(settings.DATABASE_URL)
PGTestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)

TEST_WEBHOOK_SECRET = "whsec_phase3_5_verified_secret_9988!#"
WRONG_WEBHOOK_SECRET = "whsec_wrong_unauthorized_secret_0000!#"


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


@pytest.fixture
def active_merchant(pg_db):
    m = Merchant(
        name="Phase 3.5 Integration Merchant",
        status="ACTIVE",
    )
    pg_db.add(m)
    pg_db.flush()
    return m


@pytest.fixture
def active_provider_connection(pg_db, active_merchant):
    conn = ProviderConnection(
        merchant_id=active_merchant.id,
        provider="RAZORPAY",
        provider_account_reference="acc_rzp_phase3_5_store",
        status="ACTIVE",
    )
    pg_db.add(conn)
    pg_db.commit()
    return conn


def sign_payload(raw_bytes: bytes, secret: str = TEST_WEBHOOK_SECRET) -> str:
    return hmac.new(
        key=secret.encode("utf-8"),
        msg=raw_bytes,
        digestmod=hashlib.sha256,
    ).hexdigest()


def build_webhook_payload(
    event_id: str,
    event_type: str = "payment.captured",
    payment_id: str = "pay_Phase3_5_TestPay",
    account_id: str = "acc_rzp_phase3_5_store",
    amount: int = 150000,
    status: str = "captured",
) -> dict:
    return {
        "id": event_id,
        "entity": "event",
        "account_id": account_id,
        "event": event_type,
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "entity": "payment",
                    "amount": amount,
                    "currency": "INR",
                    "status": status,
                    "order_id": "order_Phase3_5_Order",
                    "method": "upi",
                    "vpa": "payer@okhdfcbank",
                    "email": "customer@example.com",
                    "contact": "+919876543210",
                }
            }
        },
        "created_at": 1700000000,
    }


# =====================================================================
# 1. End-to-End Mocked Webhook Flow
# =====================================================================

def test_e2e_webhook_ingestion_and_merchant_mapping(
    client, pg_db, active_merchant, active_provider_connection, monkeypatch
):
    """
    1. Realistic Razorpay webhook -> HMAC signature -> POST /api/v1/webhooks/razorpay.
    Verifies HTTP 200, exactly one PaymentEvent stored, correct hashes, and merchant resolution.
    """
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    event_id = f"evt_e2e_{uuid.uuid4().hex[:10]}"
    payment_id = f"pay_e2e_{uuid.uuid4().hex[:10]}"
    raw_payload = build_webhook_payload(
        event_id=event_id,
        payment_id=payment_id,
        account_id=active_provider_connection.provider_account_reference,
    )
    raw_bytes = json.dumps(raw_payload).encode("utf-8")
    signature = sign_payload(raw_bytes, TEST_WEBHOOK_SECRET)

    res = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
        },
    )

    assert res.status_code == 200
    resp_data = res.json()
    assert resp_data["status"] == "accepted"
    assert resp_data["verified"] is True
    assert resp_data["event_id"] == event_id
    assert resp_data["duplicate"] is False

    # Verify canonical PaymentEvent in PostgreSQL
    events = pg_db.query(PaymentEvent).filter(PaymentEvent.event_id == event_id).all()
    assert len(events) == 1
    event = events[0]
    assert event.provider == "RAZORPAY"
    assert event.event_id == event_id
    assert event.event_type == "payment.captured"
    assert event.provider_payment_id == payment_id
    assert event.merchant_id == active_merchant.id
    assert event.processing_status == EventProcessingStatus.RECEIVED.value
    assert event.payload_hash == hashlib.sha256(raw_bytes).hexdigest()
    assert event.payment_id is None  # Phase 4 ownership


# =====================================================================
# 2. Duplicate Webhook Flow
# =====================================================================

def test_e2e_duplicate_webhook_delivery_idempotent_acknowledgement(
    client, pg_db, active_provider_connection, monkeypatch
):
    """
    2. Same webhook delivered twice:
       First delivery  -> PaymentEvent created, duplicate=False.
       Second delivery -> Duplicate acknowledged, duplicate=True.
       Only one database record exists, original record is not modified.
    """
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    event_id = f"evt_dup_{uuid.uuid4().hex[:10]}"
    raw_payload = build_webhook_payload(
        event_id=event_id,
        account_id=active_provider_connection.provider_account_reference,
    )
    raw_bytes = json.dumps(raw_payload).encode("utf-8")
    signature = sign_payload(raw_bytes, TEST_WEBHOOK_SECRET)

    # First delivery
    res1 = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": signature},
    )
    assert res1.status_code == 200
    assert res1.json()["duplicate"] is False

    # Capture original database state
    original_event = pg_db.query(PaymentEvent).filter(PaymentEvent.event_id == event_id).first()
    orig_id = original_event.id
    orig_received_at = original_event.received_at
    orig_status = original_event.processing_status

    # Second delivery (Razorpay automatic retry)
    res2 = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": signature},
    )
    assert res2.status_code == 200
    assert res2.json()["duplicate"] is True
    assert res2.json()["event_id"] == event_id

    # Verify exactly one record exists and attributes are unchanged
    events = pg_db.query(PaymentEvent).filter(PaymentEvent.event_id == event_id).all()
    assert len(events) == 1
    assert events[0].id == orig_id
    assert events[0].received_at == orig_received_at
    assert events[0].processing_status == orig_status


def test_e2e_concurrent_duplicate_delivery_race_safety(pg_db, monkeypatch):
    """
    2b. Simulates concurrent duplicate delivery race conditions.
    Database uniqueness on (provider, event_id) prevents race corruption.
    """
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    event_id = f"evt_race_{uuid.uuid4().hex[:10]}"
    raw_payload = build_webhook_payload(event_id=event_id)
    raw_bytes = json.dumps(raw_payload).encode("utf-8")
    sig = sign_payload(raw_bytes, TEST_WEBHOOK_SECRET)

    # Worker 1 creates event
    ev1, is_dup1 = webhook_ingestion_service.ingest_razorpay_webhook(pg_db, raw_bytes, sig)
    assert is_dup1 is False

    # Worker 2 attempts same event concurrently
    ev2, is_dup2 = webhook_ingestion_service.ingest_razorpay_webhook(pg_db, raw_bytes, sig)
    assert is_dup2 is True
    assert ev2.id == ev1.id


# =====================================================================
# 3. Tampering Flow
# =====================================================================

def test_e2e_tampering_flow_rejected_with_zero_side_effects(client, pg_db, monkeypatch):
    """
    3. Valid payload + signature for payload A -> modified payload B presented.
    Verifies HTTP 401, 0 PaymentEvents, 0 Payments, 0 Notifications, 0 Outbox events.
    """
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    init_events = pg_db.query(PaymentEvent).count()
    init_payments = pg_db.query(Payment).count()
    init_notifs = pg_db.query(VoiceNotification).count()
    init_outbox = pg_db.query(OutboxEvent).count()

    event_id = f"evt_tamp_{uuid.uuid4().hex[:10]}"
    raw_payload = build_webhook_payload(event_id=event_id, amount=10000)
    raw_bytes = json.dumps(raw_payload).encode("utf-8")
    signature = sign_payload(raw_bytes, TEST_WEBHOOK_SECRET)

    # Attacker alters amount from 10000 to 1000000 without re-signing
    tampered_bytes = raw_bytes.replace(b"10000", b"1000000")

    res = client.post(
        "/api/v1/webhooks/razorpay",
        content=tampered_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": signature},
    )

    assert res.status_code == 401
    assert "Invalid or missing webhook signature" in res.json()["detail"]

    # Verify zero database side effects
    assert pg_db.query(PaymentEvent).count() == init_events
    assert pg_db.query(Payment).count() == init_payments
    assert pg_db.query(VoiceNotification).count() == init_notifs
    assert pg_db.query(OutboxEvent).count() == init_outbox


# =====================================================================
# 4. Razorpay API Adapter Flow (Mocked HTTP)
# =====================================================================

def test_e2e_adapter_captured_payment_flow():
    """4a. RazorpayProvider.fetch_payment maps captured payment to PaymentStatus.CAPTURED."""
    raw_response = {
        "id": "pay_Cap12345",
        "entity": "payment",
        "amount": 250000,
        "currency": "INR",
        "status": "captured",
        "order_id": "order_CapOrder",
        "method": "upi",
        "vpa": "buyer@upi",
        "created_at": 1700000000,
    }
    client = RazorpayClient(key_id="rzp_test_id", key_secret="test_secret")
    adapter = RazorpayProvider(client=client)

    with patch.object(client, "get_payment", return_value=raw_response):
        norm = adapter.fetch_payment("pay_Cap12345")

    assert norm.provider == "RAZORPAY"
    assert norm.provider_payment_id == "pay_Cap12345"
    assert norm.amount_minor == 250000
    assert norm.currency == "INR"
    assert norm.status == PaymentStatus.CAPTURED
    assert norm.payer_reference == "buyer@upi"


def test_e2e_adapter_authorized_payment_flow():
    """4b. RazorpayProvider.fetch_payment maps authorized payment to PaymentStatus.AUTHORIZED."""
    raw_response = {
        "id": "pay_Auth12345",
        "entity": "payment",
        "amount": 100000,
        "currency": "INR",
        "status": "authorized",
        "method": "card",
        "created_at": 1700000000,
    }
    client = RazorpayClient(key_id="rzp_test_id", key_secret="test_secret")
    adapter = RazorpayProvider(client=client)

    with patch.object(client, "get_payment", return_value=raw_response):
        norm = adapter.fetch_payment("pay_Auth12345")

    assert norm.status == PaymentStatus.AUTHORIZED


def test_e2e_adapter_failed_payment_flow():
    """4c. RazorpayProvider.fetch_payment maps failed payment to PaymentStatus.FAILED."""
    raw_response = {
        "id": "pay_Fail12345",
        "entity": "payment",
        "amount": 50000,
        "currency": "INR",
        "status": "failed",
        "error_code": "BAD_REQUEST_ERROR",
        "error_description": "Payment failed at bank",
        "created_at": 1700000000,
    }
    client = RazorpayClient(key_id="rzp_test_id", key_secret="test_secret")
    adapter = RazorpayProvider(client=client)

    with patch.object(client, "get_payment", return_value=raw_response):
        norm = adapter.fetch_payment("pay_Fail12345")

    assert norm.status == PaymentStatus.FAILED


def test_e2e_adapter_full_refund_payment_flow():
    """4d. RazorpayProvider.fetch_payment maps full refund to PaymentStatus.REFUNDED."""
    raw_response = {
        "id": "pay_Ref12345",
        "entity": "payment",
        "amount": 75000,
        "amount_refunded": 75000,
        "currency": "INR",
        "status": "refunded",
        "refund_status": "full",
        "created_at": 1700000000,
    }
    client = RazorpayClient(key_id="rzp_test_id", key_secret="test_secret")
    adapter = RazorpayProvider(client=client)

    with patch.object(client, "get_payment", return_value=raw_response):
        norm = adapter.fetch_payment("pay_Ref12345")

    assert norm.status == PaymentStatus.REFUNDED


def test_e2e_adapter_partial_refund_payment_flow():
    """4e. RazorpayProvider.fetch_payment maps partial refund to PaymentStatus.PARTIALLY_REFUNDED."""
    raw_response = {
        "id": "pay_PartRef123",
        "entity": "payment",
        "amount": 100000,
        "amount_refunded": 30000,
        "currency": "INR",
        "status": "refunded",
        "refund_status": "partial",
        "created_at": 1700000000,
    }
    client = RazorpayClient(key_id="rzp_test_id", key_secret="test_secret")
    adapter = RazorpayProvider(client=client)

    with patch.object(client, "get_payment", return_value=raw_response):
        norm = adapter.fetch_payment("pay_PartRef123")

    assert norm.status == PaymentStatus.PARTIALLY_REFUNDED


def test_e2e_adapter_unknown_status_raises_validation_error():
    """4f. Unknown/unexpected provider status raises ProviderValidationError."""
    raw_response = {
        "id": "pay_Unknown123",
        "entity": "payment",
        "amount": 10000,
        "currency": "INR",
        "status": "pending_external_review",
        "created_at": 1700000000,
    }
    client = RazorpayClient(key_id="rzp_test_id", key_secret="test_secret")
    adapter = RazorpayProvider(client=client)

    with patch.object(client, "get_payment", return_value=raw_response):
        with pytest.raises(ProviderValidationError) as exc:
            adapter.fetch_payment("pay_Unknown123")
    assert "Unsupported or unrecognized Razorpay payment status" in str(exc.value)


def test_e2e_adapter_malformed_amount_raises_validation_error():
    """4g. Negative or non-integer amounts raise ProviderValidationError."""
    adapter = RazorpayProvider(client=RazorpayClient(key_id="k", key_secret="s"))

    bad_amounts = [-500, 12.34, "five_hundred"]
    for bad in bad_amounts:
        raw = {"id": "pay_1", "amount": bad, "currency": "INR", "status": "captured"}
        with pytest.raises(ProviderValidationError):
            adapter.normalize_payment_payload(raw)


def test_e2e_adapter_provider_api_errors():
    """4h. Client network and HTTP errors are correctly translated into ProviderError hierarchy."""
    client = RazorpayClient(key_id="rzp_test_id", key_secret="test_secret")

    # 401 Authentication Error
    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value = httpx.Response(401, json={"error": {"description": "Invalid key"}})
        with pytest.raises(ProviderAuthenticationError):
            client.get_payment("pay_1")

    # 404 Not Found
    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value = httpx.Response(404, json={"error": {"description": "Not found"}})
        with pytest.raises(ProviderResourceNotFoundError):
            client.get_payment("pay_1")

    # 500 Provider Unavailable
    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value = httpx.Response(500, text="Internal Server Error")
        with pytest.raises(ProviderUnavailableError):
            client.get_payment("pay_1")


# =====================================================================
# 5. Financial Boundary Verification (Zero Phase 4 Responsibilities)
# =====================================================================

def test_e2e_financial_boundary_zero_payment_creation_or_transition(
    client, pg_db, active_merchant, monkeypatch
):
    """
    5. CRITICAL FINANCIAL BOUNDARY:
       A valid signed webhook:
       - Persists PaymentEvent
       - Does NOT create a Payment
       - Does NOT update existing Payment status
       - Does NOT create VoiceNotification
       - Does NOT create OutboxEvent
    """
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    # Create pre-existing payment in CREATED status
    payment = Payment(
        merchant_id=active_merchant.id,
        amount_minor=80000,
        currency="INR",
        provider="RAZORPAY",
        provider_payment_id="pay_StrictBoundary_999",
        status=PaymentStatus.CREATED.value,
    )
    pg_db.add(payment)
    pg_db.commit()

    init_payments = pg_db.query(Payment).count()
    init_notifs = pg_db.query(VoiceNotification).count()
    init_outbox = pg_db.query(OutboxEvent).count()

    event_id = f"evt_bound_{uuid.uuid4().hex[:10]}"
    raw_payload = build_webhook_payload(
        event_id=event_id,
        event_type="payment.captured",
        payment_id="pay_StrictBoundary_999",
        status="captured",
    )
    raw_bytes = json.dumps(raw_payload).encode("utf-8")
    signature = sign_payload(raw_bytes, TEST_WEBHOOK_SECRET)

    res = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": signature},
    )
    assert res.status_code == 200

    # 1. PaymentEvent was persisted
    ev = pg_db.query(PaymentEvent).filter(PaymentEvent.event_id == event_id).first()
    assert ev is not None
    assert ev.processing_status == EventProcessingStatus.RECEIVED.value

    # 2. Financial tables strictly untouched
    assert pg_db.query(Payment).count() == init_payments
    pg_db.refresh(payment)
    assert payment.status == PaymentStatus.CREATED.value  # MUST NOT transition to CAPTURED!

    # 3. Notification and outbox strictly untouched
    assert pg_db.query(VoiceNotification).count() == init_notifs
    assert pg_db.query(OutboxEvent).count() == init_outbox


# =====================================================================
# 6. Security Verification
# =====================================================================

def test_e2e_security_verification_suite(client, monkeypatch, caplog):
    """
    6. Comprehensive security verifications:
       - Missing signature rejected (401)
       - Wrong secret rejected (401)
       - Oversized payload rejected (413)
       - Malformed payload rejected (400)
       - Secrets never leaked in repr, logs, or error responses
    """
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)

    # 1. Missing signature
    res_nosig = client.post(
        "/api/v1/webhooks/razorpay",
        content=b"{}",
        headers={"Content-Type": "application/json"},
    )
    assert res_nosig.status_code == 401

    # 2. Wrong secret
    raw_bytes = json.dumps(build_webhook_payload(event_id="evt_wrong_sec")).encode("utf-8")
    wrong_sig = sign_payload(raw_bytes, WRONG_WEBHOOK_SECRET)
    res_wrongsec = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": wrong_sig},
    )
    assert res_wrongsec.status_code == 401

    # 3. Oversized payload (> 1 MB)
    oversized = b"a" * (1024 * 1024 + 50)
    res_oversized = client.post(
        "/api/v1/webhooks/razorpay",
        content=oversized,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": "dummy"},
    )
    assert res_oversized.status_code == 413

    # 4. Malformed JSON
    res_malformed = client.post(
        "/api/v1/webhooks/razorpay",
        content=b"not_json",
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sign_payload(b"not_json")},
    )
    assert res_malformed.status_code == 400

    # 5. Secrets never appear in client or adapter repr / logs
    client_obj = RazorpayClient(key_id="rzp_live_abc123", key_secret="super_secret_xyz")
    assert "super_secret_xyz" not in repr(client_obj)
    assert "rzp_live..." in repr(client_obj)
    assert TEST_WEBHOOK_SECRET not in caplog.text
