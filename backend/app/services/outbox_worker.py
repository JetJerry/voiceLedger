"""
VoiceLedger Transactional Outbox Background Worker.

Polls, claims, and processes pending OutboxEvent records from PostgreSQL using
safe row-locking (FOR UPDATE SKIP LOCKED) and publishes them to the Redis event bus.

Invariants:
1. PostgreSQL is the financial source of truth. Redis is strictly a downstream transport.
2. Safe Concurrency: Multiple workers concurrently claim distinct rows using
   PostgreSQL `FOR UPDATE SKIP LOCKED`.
3. Decoupled Transactions: DB row-locks are committed and released BEFORE performing
   Redis network I/O.
4. Bounded Deterministic Retries: Exponential backoff on failure; transitions to
   DEAD_LETTER after max_retries is reached.
5. Stuck Lease Recovery: If a worker crashes mid-processing, the expired lease allows
   surviving workers to recover the event.
6. Zero Financial Mutations: This worker never creates, updates, or mutates Payments or Ledgers.
"""
import asyncio
from datetime import datetime, timezone, timedelta
import logging
from typing import Optional, List, Callable
import uuid

from sqlalchemy import or_, and_
from sqlalchemy.orm import Session

from backend.app.models.outbox_event import OutboxEvent, OutboxStatus
from backend.app.services.redis_publisher import redis_event_publisher, RedisEventPublisher

logger = logging.getLogger("voiceledger.outbox.worker")


class OutboxWorker:
    """
    Background worker that claims and dispatches OutboxEvent records to Redis.
    """

    def __init__(
        self,
        publisher: Optional[RedisEventPublisher] = None,
        batch_size: int = 10,
        lease_seconds: int = 60,
        max_backoff_seconds: int = 300,
    ):
        self._publisher = publisher or redis_event_publisher
        self._batch_size = max(1, batch_size)
        self._lease_seconds = max(5, lease_seconds)
        self._max_backoff_seconds = max(10, max_backoff_seconds)

    def claim_events(self, db: Session) -> List[OutboxEvent]:
        """
        Phase A: Claim a batch of eligible outbox events in a single DB transaction.

        Uses PostgreSQL `FOR UPDATE SKIP LOCKED` to prevent concurrent workers from
        colliding on the same rows.
        Eligible rows:
        1. PENDING and available_at <= now
        2. PROCESSING and available_at <= now (stuck lease recovery)

        Immediately marks claimed events as PROCESSING with an extended lease,
        commits the transaction, and releases row locks.
        """
        now = datetime.now(timezone.utc)
        try:
            claimed_events = (
                db.query(OutboxEvent)
                .filter(
                    or_(
                        and_(
                            OutboxEvent.status == OutboxStatus.PENDING.value,
                            OutboxEvent.available_at <= now,
                        ),
                        and_(
                            OutboxEvent.status == OutboxStatus.PROCESSING.value,
                            OutboxEvent.available_at <= now,
                        ),
                    )
                )
                .order_by(OutboxEvent.created_at.asc())
                .limit(self._batch_size)
                .with_for_update(skip_locked=True)
                .all()
            )

            if not claimed_events:
                return []

            lease_expiry = now + timedelta(seconds=self._lease_seconds)
            for event in claimed_events:
                event.status = OutboxStatus.PROCESSING.value
                event.available_at = lease_expiry

            db.commit()
            for event in claimed_events:
                db.refresh(event)

            logger.info(
                "Claimed %d outbox event(s) for processing (lease until %s)",
                len(claimed_events),
                lease_expiry.isoformat(),
            )
            return claimed_events

        except Exception as exc:
            db.rollback()
            logger.error("Error during outbox event claim: %s", exc)
            return []

    async def process_single_event(
        self,
        db: Session,
        event_id: uuid.UUID,
    ) -> bool:
        """
        Process a single claimed OutboxEvent:
        Phase B: Publish to Redis outside the DB transaction.
        Phase C: Finalize event status in PostgreSQL (PUBLISHED or scheduled retry / DEAD_LETTER).
        """
        event = db.query(OutboxEvent).filter(OutboxEvent.id == event_id).first()
        if not event:
            logger.warning("OutboxEvent %s not found during processing", event_id)
            return False

        if event.status != OutboxStatus.PROCESSING.value:
            logger.info(
                "OutboxEvent %s status is '%s' (not PROCESSING); skipping",
                event.id,
                event.status,
            )
            return False

        # Phase B: Publish outside the database transaction
        success = await self._publisher.publish_event(
            event_type=event.event_type,
            payload=event.payload,
        )

        # Phase C: Finalize status in DB
        now = datetime.now(timezone.utc)
        try:
            if success:
                event.status = OutboxStatus.PUBLISHED.value
                event.processed_at = now
                event.error_message = None
                logger.info(
                    "OutboxEvent %s marked PUBLISHED (payment_id=%s)",
                    event.id,
                    event.aggregate_id,
                )
            else:
                event.retry_count += 1
                if event.retry_count >= event.max_retries:
                    event.status = OutboxStatus.DEAD_LETTER.value
                    event.processed_at = now
                    event.error_message = "Publishing failed: max retries exceeded"
                    logger.error(
                        "OutboxEvent %s exceeded max retries (%d/%d) -> DEAD_LETTER",
                        event.id,
                        event.retry_count,
                        event.max_retries,
                    )
                else:
                    event.status = OutboxStatus.PENDING.value
                    backoff_sec = min(self._max_backoff_seconds, 2 ** event.retry_count)
                    event.available_at = now + timedelta(seconds=backoff_sec)
                    event.error_message = f"Publishing failed; retry #{event.retry_count} scheduled"
                    logger.warning(
                        "OutboxEvent %s publish failed; scheduled retry #%d in %ds",
                        event.id,
                        event.retry_count,
                        backoff_sec,
                    )

            db.commit()
            db.refresh(event)
            return success

        except Exception as exc:
            db.rollback()
            logger.error("Failed to finalize outbox event %s in database: %s", event_id, exc)
            return False

    async def process_batch_once(self, db: Session) -> int:
        """
        Execute one poll-and-process cycle:
        1. Claim a batch of eligible events.
        2. Publish each event to Redis and finalize status.
        Returns the number of events claimed.
        """
        claimed = self.claim_events(db)
        if not claimed:
            return 0

        for event in claimed:
            await self.process_single_event(db, event.id)

        return len(claimed)

    async def run_loop(
        self,
        db_session_factory: Callable[[], Session],
        poll_interval_seconds: float = 1.0,
        stop_event: Optional[asyncio.Event] = None,
    ) -> None:
        """
        Continuous background execution loop.
        Polls for pending outbox events at poll_interval_seconds until stop_event is set.
        """
        logger.info("Starting OutboxWorker loop (poll interval=%.1fs)...", poll_interval_seconds)
        while stop_event is None or not stop_event.is_set():
            try:
                session = db_session_factory()
                try:
                    processed_count = await self.process_batch_once(session)
                    # If queue was idle, sleep for poll interval
                    if processed_count == 0:
                        await asyncio.sleep(poll_interval_seconds)
                finally:
                    session.close()

            except asyncio.CancelledError:
                logger.info("OutboxWorker loop cancelled")
                break
            except Exception as exc:
                logger.error("Unexpected error in OutboxWorker loop: %s", exc)
                await asyncio.sleep(poll_interval_seconds)

        logger.info("OutboxWorker loop stopped gracefully")


# Global singleton worker instance
outbox_worker = OutboxWorker()
