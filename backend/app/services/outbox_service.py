"""
VoiceLedger Transactional Outbox Service.

Implements the Transactional Outbox Pattern to ensure reliable, at-least-once
event publication for downstream consumers (Redis, WebSocket, Soundbox, TTS)
strictly coupled within the Payment Core database transaction.

Key Invariants:
1. Atomicity: OutboxEvent is created in the same transaction as the financial state change
   (Payment + PaymentEvent + OutboxEvent).
2. Sanitization: Payloads contain strictly normalized payment notification fields.
   Zero API credentials, secrets, access tokens, webhook signatures, or raw vendor wire blobs.
3. Meaningful Event Generation: Only meaningful payment lifecycle changes (CAPTURED,
   AUTHORIZED, REFUNDED, PARTIALLY_REFUNDED) generate outbox events. Idle, failed, or
   same-state idempotent transitions generate zero outbox events.
4. Composability: auto_commit=False by default to allow caller/worker to commit the outer transaction.
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import uuid

from sqlalchemy.orm import Session

from backend.app.models.payment import Payment, PaymentStatus
from backend.app.models.outbox_event import OutboxEvent, OutboxStatus
from backend.app.core.logging import logger


# Mapping of meaningful payment statuses to canonical outbox event types
MEANINGFUL_NOTIFICATION_STATUSES: Dict[PaymentStatus, str] = {
    PaymentStatus.CAPTURED: "payment.captured",
    PaymentStatus.AUTHORIZED: "payment.authorized",
    PaymentStatus.REFUNDED: "payment.refunded",
    PaymentStatus.PARTIALLY_REFUNDED: "payment.partially_refunded",
}


class OutboxService:
    """
    Canonical service for generating and managing transactional OutboxEvent records.
    """

    @staticmethod
    def should_generate_outbox_event(status: PaymentStatus) -> bool:
        """
        Determine whether a payment status warrants a downstream notification event.
        """
        return status in MEANINGFUL_NOTIFICATION_STATUSES

    @staticmethod
    def get_outbox_event_type(status: PaymentStatus) -> Optional[str]:
        """
        Resolve the canonical event type string for a payment status.
        """
        return MEANINGFUL_NOTIFICATION_STATUSES.get(status)

    def create_payment_outbox_event(
        self,
        db: Session,
        payment: Payment,
        payment_event_id: Optional[uuid.UUID] = None,
        provider_event_id: Optional[str] = None,
        event_type: Optional[str] = None,
        auto_commit: bool = False,
    ) -> Optional[OutboxEvent]:
        """
        Construct and persist an OutboxEvent for a canonical Payment state change.

        Returns None if the payment's current status is not a notification-worthy state.
        """
        try:
            status_enum = PaymentStatus(payment.status)
        except ValueError:
            logger.warning("Payment %s has unmapped status '%s'; skipping outbox generation", payment.id, payment.status)
            return None

        resolved_event_type = event_type or self.get_outbox_event_type(status_enum)
        if not resolved_event_type:
            logger.debug(
                "Payment id=%s status='%s' does not warrant an outbox notification",
                payment.id,
                payment.status,
            )
            return None

        # Build clean, sanitized payload for downstream dispatch
        payload: Dict[str, Any] = {
            "event_id": str(payment_event_id) if payment_event_id else None,
            "provider_event_id": provider_event_id,
            "event_type": resolved_event_type,
            "merchant_id": str(payment.merchant_id),
            "payment_id": str(payment.id),
            "provider": payment.provider,
            "provider_payment_id": payment.provider_payment_id,
            "provider_order_id": payment.provider_order_id,
            "amount_minor": payment.amount_minor,
            "currency": payment.currency,
            "status": payment.status,
            "payment_method": payment.payment_method,
            "payer_reference": payment.payer_reference,
            "captured_at": payment.captured_at.isoformat() if payment.captured_at else None,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }

        outbox_event = OutboxEvent(
            id=uuid.uuid4(),
            event_type=resolved_event_type,
            aggregate_type="PAYMENT",
            aggregate_id=payment.id,
            payload=payload,
            status=OutboxStatus.PENDING.value,
            retry_count=0,
            max_retries=5,
            available_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )

        db.add(outbox_event)
        if auto_commit:
            db.commit()
            db.refresh(outbox_event)
        else:
            db.flush()

        logger.info(
            "Created OutboxEvent id=%s type='%s' aggregate=PAYMENT:%s status=PENDING",
            outbox_event.id,
            outbox_event.event_type,
            payment.id,
        )
        return outbox_event

    def get_outbox_events_for_aggregate(
        self,
        db: Session,
        aggregate_type: str,
        aggregate_id: uuid.UUID,
    ) -> List[OutboxEvent]:
        """
        Fetch all outbox events for a specific domain aggregate ordered by creation.
        """
        return (
            db.query(OutboxEvent)
            .filter(
                OutboxEvent.aggregate_type == aggregate_type,
                OutboxEvent.aggregate_id == aggregate_id,
            )
            .order_by(OutboxEvent.created_at.asc())
            .all()
        )


# Global singleton instance
outbox_service = OutboxService()
