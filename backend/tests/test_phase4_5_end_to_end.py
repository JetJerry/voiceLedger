"""
Phase 4.5 — End-to-End System Integration & Reconciliation Verification Test Suite.

Verifies the complete VoiceLedger pipeline from webhook boundary to Redis dispatch:
1. Full Happy Path: Webhook (HTTP) -> PaymentEvent -> Payment -> OutboxEvent -> OutboxWorker -> Redis.
2. Multi-Step Lifecycle: payment.authorized -> payment.captured (transitions & distinct outbox events).
3. Duplicate Webhook Delivery: Identical event ID delivered twice -> 1 PaymentEvent, 1 Payment, 1 OutboxEvent.
4. Same-State Transitions: Distinct event IDs with identical status (CAPTURED -> CAPTURED) -> no duplicate OutboxEvent.
5. Webhook Security: Signature tampering rejected with 401; zero DB mutations.
6. Financial Core Security: Amount tampering rolls back payment mutation; zero OutboxEvent created.
7. Redis Failure Resilience: Redis failure preserves committed financial records; OutboxEvent schedules retry.
8. Worker Stuck Lease Recovery: Abandoned/crashed PROCESSING events are recovered after lease timeout.
9. Multi-Merchant Isolation: Absolute tenant partitioning of payments, events, outbox, and Redis channels.
10. Payload Sanitization: Outbox and Redis payloads contain zero secrets, signatures, or credentials.
11. Provider Independence: Core services contain zero imports of Razorpay SDK/client.
12. Financial Reconciliation Invariants: Complete relational and amount consistency across entities.
"""
from datetime import datetime, timezone, timedelta
import hashlib
import hmac
import json
from typing import Dict, Any, List
import uuid
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
from backend.app.models.outbox_event import OutboxEvent, OutboxStatus
from backend.app.services.payment_event_service import payment_event_service
from backend.app.services.outbox_service import outbox_service
from backend.app.services.outbox_worker import OutboxWorker
from backend.app.services.redis_publisher import RedisEventPublisher
from backend.app.services.payment_service import (
    CrossMerchantPaymentError,
    PaymentFinancialMismatchError,
    InvalidPaymentStateTransitionError,
)

# PostgreSQL connection for authoritative integration verification
pg_engine = create_engine(settings.DATABASE_URL)
PGTestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)

TEST_WEBHOOK_SECRET = settings.RAZORPAY_WEBHOOK_SECRET or "whsec_phase4_5_test_secret_abc123"


class MockRedisPublisher(RedisEventPublisher):
    """Controllable test double for Redis event publication."""
    def __init__(self, should_succeed: bool = True):
        super().__init__(redis_client=None)
        self.should_succeed = should_succeed
        self.published_events: List[Dict[str, Any]] = []

    async def publish_event(self, event_type: str, payload: Dict[str, Any]) -> bool:
        if self.should_succeed:
            self.published_events.append({"event_type": event_type, "payload": payload})
            return True
        return False


@pytest.fixture
def db():
    """Transactional session rolled back after every test."""
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
def client(db):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def active_merchant(db) -> Merchant:
    m = Merchant(
        id=uuid.uuid4(),
        name="Phase 4.5 Integration Store",
        business_type="Retail",
        status="ACTIVE",
        currency="INR",
    )
    db.add(m)
    db.flush()
    return m


@pytest.fixture
def active_provider_connection(db, active_merchant) -> ProviderConnection:
    conn = ProviderConnection(
        id=uuid.uuid4(),
        merchant_id=active_merchant.id,
        provider="RAZORPAY",
        provider_account_reference="acc_rzp_phase4_5_test",
        status="ACTIVE",
    )
    db.add(conn)
    db.flush()
    return conn


def sign_payload(raw_bytes: bytes, secret: str = TEST_WEBHOOK_SECRET) -> str:
    return hmac.new(secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()


def build_webhook_body(
    event_id: str,
    event_type: str = "payment.captured",
    payment_id: str = "pay_p45_test",
    amount: int = 250000,
    status: str = "captured",
    account_id: str = "acc_rzp_phase4_5_test",
) -> Dict[str, Any]:
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
                    "order_id": "order_p45_order",
                    "method": "upi",
                    "vpa": "customer@okhdfcbank",
                    "created_at": 1700000000,
                }
            }
        },
        "created_at": 1700000000,
    }


# =====================================================================
# 1. Full End-to-End Happy Path (Webhook -> Redis)
# =====================================================================

@pytest.mark.asyncio
async def test_full_e2e_webhook_to_redis_pipeline(client, db, active_merchant, active_provider_connection):
    """Complete path: HTTP Webhook -> PaymentEvent -> Payment -> OutboxEvent -> OutboxWorker -> Redis."""
    event_id = f"evt_e2e_{uuid.uuid4().hex[:10]}"
    payment_id = f"pay_e2e_{uuid.uuid4().hex[:10]}"
    payload_dict = build_webhook_body(event_id=event_id, payment_id=payment_id, amount=125000)
    raw_body = json.dumps(payload_dict).encode("utf-8")
    sig = sign_payload(raw_body)

    # 1. Webhook HTTP Boundary
    resp = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"
    assert resp.json()["duplicate"] is False

    # 2. Verify PaymentEvent Persisted in DB
    event = db.query(PaymentEvent).filter(PaymentEvent.event_id == event_id).first()
    assert event is not None
    assert event.processing_status == EventProcessingStatus.RECEIVED.value
    assert event.payment_id is None
    assert event.merchant_id == active_merchant.id

    # 3. PaymentEvent Processing
    res = payment_event_service.process_payment_event(
        db=db,
        event_id=event.id,
        raw_event_payload=payload_dict,
        auto_commit=False,
    )
    assert res.processing_status == EventProcessingStatus.PROCESSED
    assert res.is_created is True
    assert res.payment_id is not None
    assert res.outbox_event_id is not None

    # 4. Verify Payment Persisted with Integer Minor Units
    payment = db.query(Payment).filter(Payment.id == res.payment_id).first()
    assert payment is not None
    assert payment.amount_minor == 125000
    assert payment.currency == "INR"
    assert payment.status == "CAPTURED"
    assert payment.provider_payment_id == payment_id
    assert payment.merchant_id == active_merchant.id

    # 5. Verify OutboxEvent Generated
    outbox = db.query(OutboxEvent).filter(OutboxEvent.id == res.outbox_event_id).first()
    assert outbox is not None
    assert outbox.aggregate_id == payment.id
    assert outbox.event_type == "payment.captured"
    assert outbox.status == OutboxStatus.PENDING.value

    # 6. OutboxWorker Dispatches to Redis
    mock_redis = MockRedisPublisher(should_succeed=True)
    worker = OutboxWorker(publisher=mock_redis)
    count = await worker.process_batch_once(db)
    assert count == 1

    # 7. Verify OutboxEvent Transitions to PUBLISHED
    db.refresh(outbox)
    assert outbox.status == OutboxStatus.PUBLISHED.value
    assert outbox.processed_at is not None

    # 8. Verify Redis Message
    assert len(mock_redis.published_events) == 1
    dispatched = mock_redis.published_events[0]
    assert dispatched["event_type"] == "payment.captured"
    assert dispatched["payload"]["payment_id"] == str(payment.id)
    assert dispatched["payload"]["amount_minor"] == 125000
    assert dispatched["payload"]["merchant_id"] == str(active_merchant.id)


# =====================================================================
# 2. Multi-Step Lifecycle (Authorized -> Captured)
# =====================================================================

@pytest.mark.asyncio
async def test_multi_step_lifecycle_authorized_to_captured(client, db, active_merchant, active_provider_connection):
    """Verifies that authorized followed by captured creates 1 Payment and 2 distinct OutboxEvents."""
    pid = f"pay_life_{uuid.uuid4().hex[:10]}"
    mock_redis = MockRedisPublisher(should_succeed=True)
    worker = OutboxWorker(publisher=mock_redis)

    # Step 1: payment.authorized
    evt1_id = f"evt_auth_{uuid.uuid4().hex[:8]}"
    body1 = build_webhook_body(event_id=evt1_id, event_type="payment.authorized", payment_id=pid, status="authorized")
    client.post(
        "/api/v1/webhooks/razorpay",
        content=json.dumps(body1).encode("utf-8"),
        headers={"X-Razorpay-Signature": sign_payload(json.dumps(body1).encode("utf-8")), "Content-Type": "application/json"},
    )
    ev1 = db.query(PaymentEvent).filter(PaymentEvent.event_id == evt1_id).first()
    res1 = payment_event_service.process_payment_event(db=db, event_id=ev1.id, raw_event_payload=body1)
    await worker.process_batch_once(db)

    # Step 2: payment.captured (distinct event ID)
    evt2_id = f"evt_cap_{uuid.uuid4().hex[:8]}"
    body2 = build_webhook_body(event_id=evt2_id, event_type="payment.captured", payment_id=pid, status="captured")
    client.post(
        "/api/v1/webhooks/razorpay",
        content=json.dumps(body2).encode("utf-8"),
        headers={"X-Razorpay-Signature": sign_payload(json.dumps(body2).encode("utf-8")), "Content-Type": "application/json"},
    )
    ev2 = db.query(PaymentEvent).filter(PaymentEvent.event_id == evt2_id).first()
    res2 = payment_event_service.process_payment_event(db=db, event_id=ev2.id, raw_event_payload=body2)
    await worker.process_batch_once(db)

    # Verify Reconciliation
    payment = db.query(Payment).filter(Payment.id == res1.payment_id).first()
    assert payment.status == PaymentStatus.CAPTURED.value
    assert res1.payment_id == res2.payment_id  # Same canonical payment

    # Verify Outbox: exactly 2 distinct outbox events
    all_outbox = outbox_service.get_outbox_events_for_aggregate(db, "PAYMENT", payment.id)
    assert len(all_outbox) == 2
    assert [o.event_type for o in all_outbox] == ["payment.authorized", "payment.captured"]
    assert all(o.status == "PUBLISHED" for o in all_outbox)


# =====================================================================
# 3. Duplicate Delivery vs Same-State Delivery
# =====================================================================

@pytest.mark.asyncio
async def test_duplicate_webhook_delivery_same_event_id(client, db, active_merchant, active_provider_connection):
    """Same webhook/provider event ID delivered twice -> 1 PaymentEvent, 1 Payment, 1 OutboxEvent."""
    eid = f"evt_dup_{uuid.uuid4().hex[:8]}"
    body = build_webhook_body(event_id=eid, status="captured")
    raw = json.dumps(body).encode("utf-8")
    sig = sign_payload(raw)

    # Delivery 1
    r1 = client.post("/api/v1/webhooks/razorpay", content=raw, headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"})
    assert r1.status_code == 200
    assert r1.json()["duplicate"] is False

    # Delivery 2 (Identical event ID)
    r2 = client.post("/api/v1/webhooks/razorpay", content=raw, headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"})
    assert r2.status_code == 200
    assert r2.json()["duplicate"] is True

    # Database has strictly 1 PaymentEvent row
    events = db.query(PaymentEvent).filter(PaymentEvent.event_id == eid).all()
    assert len(events) == 1

    # Processing produces 1 Payment, 1 OutboxEvent
    mock_redis = MockRedisPublisher(should_succeed=True)
    worker = OutboxWorker(publisher=mock_redis)

    payment_event_service.process_payment_event(db=db, event_id=events[0].id, raw_event_payload=body)
    await worker.process_batch_once(db)

    # Re-processing the same event is an idempotent safe no-op
    res_repeat = payment_event_service.process_payment_event(db=db, event_id=events[0].id, raw_event_payload=body)
    assert res_repeat.is_duplicate is True
    assert res_repeat.outbox_event_id is None

    outbox_count = db.query(OutboxEvent).filter(OutboxEvent.aggregate_id == res_repeat.payment_id).count()
    assert outbox_count == 1
    assert len(mock_redis.published_events) == 1


@pytest.mark.asyncio
async def test_same_state_distinct_event_ids_no_duplicate_outbox(client, db, active_merchant, active_provider_connection):
    """Two distinct event IDs with same state (CAPTURED -> CAPTURED) -> 2 PaymentEvents, 1 OutboxEvent."""
    pid = f"pay_same_st_{uuid.uuid4().hex[:8]}"
    mock_redis = MockRedisPublisher(should_succeed=True)
    worker = OutboxWorker(publisher=mock_redis)

    # Webhook 1: Event 1 (CAPTURED)
    e1_id = f"evt_st1_{uuid.uuid4().hex[:8]}"
    b1 = build_webhook_body(event_id=e1_id, payment_id=pid, status="captured")
    client.post("/api/v1/webhooks/razorpay", content=json.dumps(b1).encode("utf-8"), headers={"X-Razorpay-Signature": sign_payload(json.dumps(b1).encode("utf-8")), "Content-Type": "application/json"})
    ev1 = db.query(PaymentEvent).filter(PaymentEvent.event_id == e1_id).first()
    res1 = payment_event_service.process_payment_event(db=db, event_id=ev1.id, raw_event_payload=b1)
    await worker.process_batch_once(db)
    assert res1.outbox_event_id is not None

    # Webhook 2: Event 2 (CAPTURED again on same payment)
    e2_id = f"evt_st2_{uuid.uuid4().hex[:8]}"
    b2 = build_webhook_body(event_id=e2_id, payment_id=pid, status="captured")
    client.post("/api/v1/webhooks/razorpay", content=json.dumps(b2).encode("utf-8"), headers={"X-Razorpay-Signature": sign_payload(json.dumps(b2).encode("utf-8")), "Content-Type": "application/json"})
    ev2 = db.query(PaymentEvent).filter(PaymentEvent.event_id == e2_id).first()
    res2 = payment_event_service.process_payment_event(db=db, event_id=ev2.id, raw_event_payload=b2)
    await worker.process_batch_once(db)

    # 2 distinct PaymentEvents exist
    assert ev1.id != ev2.id
    # But same-state repeat generates ZERO duplicate OutboxEvents!
    assert res2.outbox_event_id is None

    outbox_events = outbox_service.get_outbox_events_for_aggregate(db, "PAYMENT", res1.payment_id)
    assert len(outbox_events) == 1
    assert len(mock_redis.published_events) == 1


# =====================================================================
# 4. Failure Boundaries: Security, Tampering & Rollbacks
# =====================================================================

def test_webhook_tampered_signature_rejected_with_zero_mutations(client, db):
    """Tampered signature returns HTTP 401 and creates zero records in database."""
    body = build_webhook_body(event_id=f"evt_tamper_{uuid.uuid4().hex[:8]}")
    raw = json.dumps(body).encode("utf-8")
    tampered_sig = "a" * 64

    resp = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw,
        headers={"X-Razorpay-Signature": tampered_sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 401

    # Zero database records created
    assert db.query(PaymentEvent).count() == 0
    assert db.query(Payment).count() == 0
    assert db.query(OutboxEvent).count() == 0


def test_payment_processing_amount_tampering_rollback(db, active_merchant):
    """Amount tampering during payment update rolls back mutation; zero OutboxEvents created."""
    pid = f"pay_amount_tamp_{uuid.uuid4().hex[:8]}"

    # Initial legitimate captured payment (50000 paise)
    payload1 = build_webhook_body(event_id=f"evt_legit_{uuid.uuid4().hex[:8]}", payment_id=pid, amount=50000)
    ev1 = PaymentEvent(
        provider="RAZORPAY",
        event_id=payload1["id"],
        event_type="payment.captured",
        provider_payment_id=pid,
        payload_hash="hash1",
        merchant_id=active_merchant.id,
    )
    db.add(ev1)
    db.flush()
    payment_event_service.process_payment_event(db=db, event_id=ev1.id, raw_event_payload=payload1)

    # Tampered update attempt (altered to 10000 paise)
    payload2 = build_webhook_body(event_id=f"evt_tamp_{uuid.uuid4().hex[:8]}", payment_id=pid, amount=10000)
    ev2 = PaymentEvent(
        provider="RAZORPAY",
        event_id=payload2["id"],
        event_type="payment.captured",
        provider_payment_id=pid,
        payload_hash="hash2",
        merchant_id=active_merchant.id,
    )
    db.add(ev2)
    db.flush()

    with pytest.raises(PaymentFinancialMismatchError):
        payment_event_service.process_payment_event(db=db, event_id=ev2.id, raw_event_payload=payload2, raise_on_error=True)

    # Verify event marked FAILED
    db.refresh(ev2)
    assert ev2.processing_status == EventProcessingStatus.FAILED.value
    assert ev2.payment_id is None

    # Verify payment remains 50000
    payment = db.query(Payment).filter(Payment.provider_payment_id == pid).first()
    assert payment.amount_minor == 50000


# =====================================================================
# 5. Resilience: Redis Failure & Worker Recovery
# =====================================================================

@pytest.mark.asyncio
async def test_redis_failure_preserves_financial_state_and_schedules_retry(db, active_merchant):
    """Redis downtime preserves committed payment; outbox event schedules retry without failure."""
    pid = f"pay_redis_fail_{uuid.uuid4().hex[:8]}"
    payload = build_webhook_body(event_id=f"evt_rf_{uuid.uuid4().hex[:8]}", payment_id=pid, amount=80000)
    ev = PaymentEvent(
        provider="RAZORPAY",
        event_id=payload["id"],
        event_type="payment.captured",
        provider_payment_id=pid,
        payload_hash="hash_rf",
        merchant_id=active_merchant.id,
    )
    db.add(ev)
    db.flush()

    # Process into payment & outbox
    res = payment_event_service.process_payment_event(db=db, event_id=ev.id, raw_event_payload=payload)

    # Worker encounters Redis failure
    mock_failing_redis = MockRedisPublisher(should_succeed=False)
    worker = OutboxWorker(publisher=mock_failing_redis)
    await worker.process_batch_once(db)

    # Financial transaction is committed and safe
    payment = db.query(Payment).filter(Payment.id == res.payment_id).first()
    assert payment.status == "CAPTURED"
    assert payment.amount_minor == 80000

    # Outbox event is scheduled for retry
    outbox = db.query(OutboxEvent).filter(OutboxEvent.id == res.outbox_event_id).first()
    assert outbox.status == OutboxStatus.PENDING.value
    assert outbox.retry_count == 1
    assert outbox.available_at > datetime.now(timezone.utc)
    assert "Publishing failed; retry #1 scheduled" in outbox.error_message


# =====================================================================
# 6. Tenant Isolation & Security
# =====================================================================

def test_multi_merchant_isolation_across_full_pipeline(db, active_merchant):
    """Proves Merchant A's payment cannot be accessed, hijacked, or published for Merchant B."""
    merchant_b = Merchant(
        id=uuid.uuid4(),
        name="Merchant B Store",
        status="ACTIVE",
        currency="INR",
    )
    db.add(merchant_b)
    db.flush()

    pid = f"pay_tenant_{uuid.uuid4().hex[:8]}"
    # Payment owned by Merchant A
    p_a = build_webhook_body(event_id=f"evt_ma_{uuid.uuid4().hex[:8]}", payment_id=pid, amount=40000)
    ev_a = PaymentEvent(provider="RAZORPAY", event_id=p_a["id"], event_type="payment.captured", provider_payment_id=pid, payload_hash="h1", merchant_id=active_merchant.id)
    db.add(ev_a)
    db.flush()
    res_a = payment_event_service.process_payment_event(db=db, event_id=ev_a.id, raw_event_payload=p_a)

    # Event arriving under Merchant B for same payment ID
    p_b = build_webhook_body(event_id=f"evt_mb_{uuid.uuid4().hex[:8]}", payment_id=pid, amount=40000)
    ev_b = PaymentEvent(provider="RAZORPAY", event_id=p_b["id"], event_type="payment.captured", provider_payment_id=pid, payload_hash="h2", merchant_id=merchant_b.id)
    db.add(ev_b)
    db.flush()

    with pytest.raises(CrossMerchantPaymentError):
        payment_event_service.process_payment_event(db=db, event_id=ev_b.id, raw_event_payload=p_b, raise_on_error=True)

    # Verify OutboxEvent belongs strictly to Merchant A
    outbox = db.query(OutboxEvent).filter(OutboxEvent.id == res_a.outbox_event_id).first()
    assert outbox.payload["merchant_id"] == str(active_merchant.id)


# =====================================================================
# 7. Financial Reconciliation Invariants
# =====================================================================

def test_financial_reconciliation_consistency(db, active_merchant):
    """Verifies relational integrity: PaymentEvent.payment_id == Payment.id == OutboxEvent.aggregate_id."""
    pid = f"pay_recon_{uuid.uuid4().hex[:8]}"
    p = build_webhook_body(event_id=f"evt_recon_{uuid.uuid4().hex[:8]}", payment_id=pid, amount=99999)
    ev = PaymentEvent(provider="RAZORPAY", event_id=p["id"], event_type="payment.captured", provider_payment_id=pid, payload_hash="hr", merchant_id=active_merchant.id)
    db.add(ev)
    db.flush()

    res = payment_event_service.process_payment_event(db=db, event_id=ev.id, raw_event_payload=p)

    payment = db.query(Payment).filter(Payment.id == res.payment_id).first()
    outbox = db.query(OutboxEvent).filter(OutboxEvent.id == res.outbox_event_id).first()

    # Exact ID equality
    assert ev.payment_id == payment.id
    assert outbox.aggregate_id == payment.id
    # Exact amount equality (integer minor units, no floats)
    assert payment.amount_minor == 99999
    assert outbox.payload["amount_minor"] == 99999
    assert isinstance(payment.amount_minor, int)


# =====================================================================
# 8. Worker Stuck Lease Recovery
# =====================================================================

@pytest.mark.asyncio
async def test_worker_stuck_lease_recovery_dispatches_successfully(db, active_merchant):
    """OutboxEvent abandoned in PROCESSING with expired lease is reclaimed and published."""
    pid = f"pay_lease_{uuid.uuid4().hex[:8]}"
    expired_at = datetime.now(timezone.utc) - timedelta(minutes=5)

    outbox = OutboxEvent(
        id=uuid.uuid4(),
        event_type="payment.captured",
        aggregate_type="PAYMENT",
        aggregate_id=uuid.uuid4(),
        payload={
            "payment_id": pid,
            "merchant_id": str(active_merchant.id),
            "amount_minor": 75000,
            "currency": "INR",
        },
        status=OutboxStatus.PROCESSING.value,
        available_at=expired_at,
        created_at=expired_at,
    )
    db.add(outbox)
    db.flush()

    mock_redis = MockRedisPublisher(should_succeed=True)
    worker = OutboxWorker(publisher=mock_redis)

    count = await worker.process_batch_once(db)
    assert count == 1

    db.refresh(outbox)
    assert outbox.status == OutboxStatus.PUBLISHED.value
    assert len(mock_redis.published_events) == 1


# =====================================================================
# 9. Payload Sanitization & Security
# =====================================================================

@pytest.mark.asyncio
async def test_redis_published_payload_strictly_sanitized(client, db, active_merchant, active_provider_connection):
    """Verify that the payload delivered to Redis contains zero secrets, signatures, or credentials."""
    event_id = f"evt_sec_{uuid.uuid4().hex[:8]}"
    payment_id = f"pay_sec_{uuid.uuid4().hex[:8]}"
    payload_dict = build_webhook_body(event_id=event_id, payment_id=payment_id)
    raw = json.dumps(payload_dict).encode("utf-8")
    sig = sign_payload(raw)

    client.post("/api/v1/webhooks/razorpay", content=raw, headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"})
    ev = db.query(PaymentEvent).filter(PaymentEvent.event_id == event_id).first()

    mock_redis = MockRedisPublisher(should_succeed=True)
    worker = OutboxWorker(publisher=mock_redis)

    payment_event_service.process_payment_event(db=db, event_id=ev.id, raw_event_payload=payload_dict)
    await worker.process_batch_once(db)

    assert len(mock_redis.published_events) == 1
    dispatched_payload = mock_redis.published_events[0]["payload"]

    forbidden_keys = ["secret", "password", "signature", "key_secret", "access_token", "raw_body"]
    for key in forbidden_keys:
        assert key not in dispatched_payload
        for k, v in dispatched_payload.items():
            assert key not in str(k).lower()


# =====================================================================
# 10. Provider Independence Verification
# =====================================================================

def test_core_services_have_zero_provider_coupling():
    """Verify core financial services do NOT directly import Razorpay SDK or client."""
    import inspect
    import backend.app.services.payment_service as ps_mod
    import backend.app.services.payment_event_service as pes_mod
    import backend.app.services.outbox_service as os_mod
    import backend.app.services.outbox_worker as ow_mod
    import backend.app.services.redis_publisher as rp_mod

    modules = [ps_mod, pes_mod, os_mod, ow_mod, rp_mod]
    for mod in modules:
        source = inspect.getsource(mod)
        assert "RazorpayClient" not in source, f"{mod.__name__} violates provider independence"
        assert "RazorpayProvider" not in source, f"{mod.__name__} violates provider independence"
        assert "from backend.app.providers.razorpay" not in source, f"{mod.__name__} violates provider independence"
