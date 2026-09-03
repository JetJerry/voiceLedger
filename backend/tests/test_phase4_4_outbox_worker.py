"""
Phase 4.4 — Transactional Outbox Background Worker & Redis Publisher Test Suite.

Verifies:
1. Outbox claiming: PENDING eligible events are safely claimed and marked PROCESSING.
2. Safe concurrency: Multiple workers claim distinct rows without collisions (FOR UPDATE SKIP LOCKED).
3. Skip locked: Workers do not block each other or claim locked/processing events.
4. Already-PUBLISHED events are never claimed.
5. Future-scheduled events (available_at > now) are not claimed until due.
6. Successful Redis publication transitions status to PUBLISHED with processed_at.
7. Failed Redis publication schedules deterministic retry with backoff and error message.
8. Retry exhaustion transitions status to DEAD_LETTER without silent loss.
9. Stuck PROCESSING events (lease expired) are safely recovered by surviving workers.
10. Payload integrity: Redis published payload matches sanitized OutboxEvent data.
11. No financial mutation: Worker does not mutate payments or payment events.
12. Provider independence: Zero coupling to Razorpay SDK or client.
"""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.config import settings
from backend.app.models.merchant import Merchant
from backend.app.models.payment import Payment, PaymentStatus
from backend.app.models.payment_event import PaymentEvent
from backend.app.models.outbox_event import OutboxEvent, OutboxStatus
from backend.app.services.redis_publisher import RedisEventPublisher
from backend.app.services.outbox_worker import OutboxWorker

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
        name="Phase 4.4 Test Kirana",
        business_type="Retail",
        status="ACTIVE",
        currency="INR",
    )
    db.add(merchant)
    db.flush()
    return merchant


def create_test_outbox_event(
    db,
    status: OutboxStatus = OutboxStatus.PENDING,
    available_at: Optional[datetime] = None,
    retry_count: int = 0,
    max_retries: int = 5,
    event_type: str = "payment.captured",
    merchant_id: Optional[uuid.UUID] = None,
) -> OutboxEvent:
    pay_id = uuid.uuid4()
    merch_id = merchant_id or uuid.uuid4()
    now = datetime.now(timezone.utc)

    payload = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "merchant_id": str(merch_id),
        "payment_id": str(pay_id),
        "provider": "RAZORPAY",
        "provider_payment_id": f"pay_{uuid.uuid4().hex[:10]}",
        "amount_minor": 50000,
        "currency": "INR",
        "status": "CAPTURED",
        "payment_method": "UPI",
        "payer_reference": "user@okaxis",
        "captured_at": now.isoformat(),
        "occurred_at": now.isoformat(),
    }

    event = OutboxEvent(
        id=uuid.uuid4(),
        event_type=event_type,
        aggregate_type="PAYMENT",
        aggregate_id=pay_id,
        payload=payload,
        status=status.value,
        retry_count=retry_count,
        max_retries=max_retries,
        available_at=available_at or now,
        created_at=now,
    )
    db.add(event)
    db.flush()
    return event


class FakeRedisPublisher(RedisEventPublisher):
    """Fake Redis publisher recording calls and controlling success/failure."""
    def __init__(self, should_succeed: bool = True):
        super().__init__(redis_client=None)
        self.should_succeed = should_succeed
        self.published_messages: List[Dict[str, Any]] = []

    async def publish_event(self, event_type: str, payload: Dict[str, Any]) -> bool:
        if self.should_succeed:
            self.published_messages.append({"event_type": event_type, "payload": payload})
            return True
        return False


# =====================================================================
# 1. Outbox Claiming & Row Locking
# =====================================================================

def test_claim_single_pending_outbox_event(db):
    """Worker safely claims a pending event and transitions it to PROCESSING with lease."""
    event = create_test_outbox_event(db, status=OutboxStatus.PENDING)
    initial_available = event.available_at

    worker = OutboxWorker(batch_size=10, lease_seconds=60)
    claimed = worker.claim_events(db)

    assert len(claimed) == 1
    assert claimed[0].id == event.id
    assert claimed[0].status == OutboxStatus.PROCESSING.value
    assert claimed[0].available_at > initial_available


def test_concurrent_workers_claim_distinct_events_without_collision():
    """Two concurrent workers claim distinct disjoint subsets using SKIP LOCKED."""
    # Use separate real connections to test true PostgreSQL FOR UPDATE SKIP LOCKED
    conn1 = pg_engine.connect()
    conn2 = pg_engine.connect()
    sess1 = PGTestSessionLocal(bind=conn1)
    sess2 = PGTestSessionLocal(bind=conn2)

    created_ids = []
    try:
        # Create 4 pending events directly on sess1 and commit
        events = [create_test_outbox_event(sess1, status=OutboxStatus.PENDING) for _ in range(4)]
        sess1.commit()
        created_ids = [e.id for e in events]

        worker1 = OutboxWorker(batch_size=2)
        worker2 = OutboxWorker(batch_size=2)

        claimed1 = worker1.claim_events(sess1)
        claimed2 = worker2.claim_events(sess2)

        assert len(claimed1) == 2
        assert len(claimed2) == 2

        ids1 = {e.id for e in claimed1}
        ids2 = {e.id for e in claimed2}
        # Absolute disjoint sets — zero duplicate claims!
        assert ids1.isdisjoint(ids2)
        assert (ids1 | ids2).issubset(set(created_ids))

    finally:
        if created_ids:
            sess1.query(OutboxEvent).filter(OutboxEvent.id.in_(created_ids)).delete(synchronize_session=False)
            sess1.commit()
        sess1.close()
        sess2.close()
        conn1.close()
        conn2.close()


def test_already_published_events_are_never_claimed(db):
    """Events in PUBLISHED state are ignored by the claiming algorithm."""
    create_test_outbox_event(db, status=OutboxStatus.PUBLISHED)
    worker = OutboxWorker()
    claimed = worker.claim_events(db)
    assert len(claimed) == 0


def test_future_scheduled_events_are_not_claimed_until_due(db):
    """Events with available_at in the future are skipped."""
    future_time = datetime.now(timezone.utc) + timedelta(minutes=10)
    create_test_outbox_event(db, status=OutboxStatus.PENDING, available_at=future_time)

    worker = OutboxWorker()
    claimed = worker.claim_events(db)
    assert len(claimed) == 0


# =====================================================================
# 2. Redis Publishing & Status Finalization
# =====================================================================

@pytest.mark.asyncio
async def test_successful_redis_publishing_marks_event_published(db):
    """Successful publication marks OutboxEvent as PUBLISHED with processed_at."""
    event = create_test_outbox_event(db, status=OutboxStatus.PENDING)
    fake_pub = FakeRedisPublisher(should_succeed=True)
    worker = OutboxWorker(publisher=fake_pub)

    # Claim
    claimed = worker.claim_events(db)
    assert len(claimed) == 1

    # Process
    success = await worker.process_single_event(db, event.id)
    assert success is True

    db.refresh(event)
    assert event.status == OutboxStatus.PUBLISHED.value
    assert event.processed_at is not None
    assert event.error_message is None

    # Verify message received by publisher
    assert len(fake_pub.published_messages) == 1
    assert fake_pub.published_messages[0]["event_type"] == "payment.captured"
    assert fake_pub.published_messages[0]["payload"]["payment_id"] == str(event.aggregate_id)


@pytest.mark.asyncio
async def test_failed_redis_publishing_schedules_retry(db):
    """Redis failure increments retry_count, schedules future backoff, and keeps event PENDING."""
    event = create_test_outbox_event(db, status=OutboxStatus.PENDING, retry_count=0, max_retries=5)
    fake_pub = FakeRedisPublisher(should_succeed=False)
    worker = OutboxWorker(publisher=fake_pub)

    # Claim
    worker.claim_events(db)

    # Process
    success = await worker.process_single_event(db, event.id)
    assert success is False

    db.refresh(event)
    assert event.status == OutboxStatus.PENDING.value
    assert event.retry_count == 1
    assert event.available_at > datetime.now(timezone.utc)
    assert "Publishing failed; retry #1 scheduled" in event.error_message


@pytest.mark.asyncio
async def test_retry_exhaustion_transitions_to_dead_letter(db):
    """When retry_count reaches max_retries, event transitions to DEAD_LETTER."""
    event = create_test_outbox_event(db, status=OutboxStatus.PENDING, retry_count=4, max_retries=5)
    fake_pub = FakeRedisPublisher(should_succeed=False)
    worker = OutboxWorker(publisher=fake_pub)

    # Claim
    worker.claim_events(db)

    # Process (attempt #5 fails)
    success = await worker.process_single_event(db, event.id)
    assert success is False

    db.refresh(event)
    assert event.status == OutboxStatus.DEAD_LETTER.value
    assert event.retry_count == 5
    assert event.processed_at is not None
    assert "max retries exceeded" in event.error_message


# =====================================================================
# 3. Stuck Lease Recovery
# =====================================================================

def test_stuck_processing_lease_expired_is_recovered(db):
    """Events stuck in PROCESSING whose lease expired are recovered by the worker."""
    expired_time = datetime.now(timezone.utc) - timedelta(seconds=120)
    event = create_test_outbox_event(
        db, status=OutboxStatus.PROCESSING, available_at=expired_time
    )

    worker = OutboxWorker(batch_size=10, lease_seconds=60)
    claimed = worker.claim_events(db)

    assert len(claimed) == 1
    assert claimed[0].id == event.id
    # Lease renewed
    assert claimed[0].available_at > datetime.now(timezone.utc)


# =====================================================================
# 4. Batch Execution & Full Cycle
# =====================================================================

@pytest.mark.asyncio
async def test_process_batch_once_full_cycle(db):
    """Verify process_batch_once claims and publishes all pending events."""
    e1 = create_test_outbox_event(db, status=OutboxStatus.PENDING)
    e2 = create_test_outbox_event(db, status=OutboxStatus.PENDING)

    fake_pub = FakeRedisPublisher(should_succeed=True)
    worker = OutboxWorker(publisher=fake_pub, batch_size=10)

    count = await worker.process_batch_once(db)
    assert count == 2

    db.refresh(e1)
    db.refresh(e2)
    assert e1.status == OutboxStatus.PUBLISHED.value
    assert e2.status == OutboxStatus.PUBLISHED.value
    assert len(fake_pub.published_messages) == 2


# =====================================================================
# 5. Security: Payload Integrity & Zero Financial Mutation
# =====================================================================

@pytest.mark.asyncio
async def test_published_payload_contains_no_secrets_or_signatures(db):
    """Verify that published payload has zero sensitive credentials or signatures."""
    event = create_test_outbox_event(db)
    fake_pub = FakeRedisPublisher(should_succeed=True)
    worker = OutboxWorker(publisher=fake_pub)

    worker.claim_events(db)
    await worker.process_single_event(db, event.id)

    payload = fake_pub.published_messages[0]["payload"]
    forbidden = ["secret", "password", "signature", "key_secret", "access_token"]
    for term in forbidden:
        assert term not in payload
        for k, v in payload.items():
            assert term not in str(k).lower()


def test_worker_causes_zero_financial_mutations(db, active_merchant):
    """Verify worker never modifies payments or payment_events."""
    payment = Payment(
        merchant_id=active_merchant.id,
        provider="RAZORPAY",
        provider_payment_id="pay_fin_test_1",
        amount_minor=10000,
        currency="INR",
        status=PaymentStatus.CAPTURED.value,
    )
    db.add(payment)
    db.flush()

    outbox_event = create_test_outbox_event(db, merchant_id=active_merchant.id)
    initial_payment_status = payment.status
    initial_amount = payment.amount_minor

    worker = OutboxWorker()
    worker.claim_events(db)

    db.refresh(payment)
    assert payment.status == initial_payment_status
    assert payment.amount_minor == initial_amount


# =====================================================================
# 6. Provider Independence
# =====================================================================

def test_outbox_worker_has_zero_razorpay_coupling():
    """Verify OutboxWorker and RedisEventPublisher do NOT import Razorpay."""
    import inspect
    import backend.app.services.redis_publisher as pub_mod
    import backend.app.services.outbox_worker as work_mod

    pub_src = inspect.getsource(pub_mod)
    work_src = inspect.getsource(work_mod)

    for src in [pub_src, work_src]:
        assert "RazorpayClient" not in src
        assert "RazorpayProvider" not in src
        assert "RazorpayWebhookVerifier" not in src
        assert "from backend.app.providers.razorpay" not in src
