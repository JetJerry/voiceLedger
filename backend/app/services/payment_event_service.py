"""
VoiceLedger PaymentEvent Processing Service.

Processes persisted, verified PaymentEvent records and integrates them with the
canonical PaymentService within an atomic, composable transaction boundary.

Pipeline:
Verified Razorpay Webhook -> PaymentEvent -> PaymentEventService -> PaymentService -> Payment

Invariants:
- Atomic Transaction Boundary: Payment creation/update + PaymentEvent.payment_id + processing_status
  occur in a single transaction. On failure, all financial changes are rolled back.
- Provider Independent: Obtains normalized payment payloads via the PaymentProvider abstraction.
  Zero direct dependency or imports of gateway SDKs/clients.
- Level 2 Idempotency: Processing an already-processed event is a safe no-op.
- Tenant Isolation: Rejects event processing if the event's merchant does not match the payment.
- Composability: auto_commit=False by default to allow caller (e.g. worker pipeline) to own transaction commit.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import uuid

from sqlalchemy.orm import Session

from backend.app.models.payment import Payment
from backend.app.models.payment_event import PaymentEvent, EventProcessingStatus
from backend.app.models.outbox_event import OutboxEvent
from backend.app.providers.base import get_provider
from backend.app.providers.schemas import NormalizedPayment
from backend.app.services.payment_service import (
    payment_service,
    PaymentService,
    PaymentCoreError,
    CrossMerchantPaymentError,
    InvalidPaymentStateTransitionError,
    InvalidPaymentCreationStatusError,
    PaymentFinancialMismatchError,
    InactiveMerchantError,
)
from backend.app.services.outbox_service import outbox_service, OutboxService
from backend.app.core.logging import logger


# =====================================================================
# Domain Exceptions
# =====================================================================

class PaymentEventProcessingError(Exception):
    """Base exception for payment event processing errors."""
    pass


class PaymentEventNotFoundError(PaymentEventProcessingError):
    """Raised when the target PaymentEvent cannot be found in the database."""
    pass


class UnresolvedMerchantEventError(PaymentEventProcessingError):
    """Raised when an event lacks an associated active merchant and cannot be processed."""
    pass


class NonPaymentEventError(PaymentEventProcessingError):
    """Raised when an event contains no extractable payment entity."""
    pass


# =====================================================================
# Result DTO
# =====================================================================

@dataclass(frozen=True)
class PaymentEventProcessingResult:
    """
    Immutable result object representing the outcome of a PaymentEvent processing attempt.
    """
    event_id: uuid.UUID
    processing_status: EventProcessingStatus
    payment_id: Optional[uuid.UUID] = None
    payment: Optional[Payment] = None
    outbox_event_id: Optional[uuid.UUID] = None
    outbox_event: Optional[OutboxEvent] = None
    is_created: bool = False
    is_duplicate: bool = False
    error_code: Optional[str] = None
    error_message: Optional[str] = None


# =====================================================================
# Service Implementation
# =====================================================================

class PaymentEventService:
    """
    Service responsible for converting persisted PaymentEvents into canonical Payment records.
    """

    def __init__(
        self,
        payment_core: Optional[PaymentService] = None,
        outbox_core: Optional[OutboxService] = None,
    ):
        self._payment_service = payment_core or payment_service
        self._outbox_service = outbox_core or outbox_service

    def process_payment_event(
        self,
        db: Session,
        event_id: uuid.UUID,
        raw_event_payload: Optional[Dict[str, Any]] = None,
        normalized_payment: Optional[NormalizedPayment] = None,
        auto_commit: bool = False,
        raise_on_error: bool = True,
    ) -> PaymentEventProcessingResult:
        """
        Atomically process a persisted PaymentEvent into a canonical Payment.

        Steps:
        1. Load PaymentEvent from PostgreSQL.
        2. Check eligibility (idempotent no-op if already PROCESSED, DUPLICATE, or IGNORED).
        3. Verify merchant isolation (must have active merchant_id).
        4. Obtain NormalizedPayment via provider abstraction or passed data.
        5. Execute atomic transaction:
           - Call PaymentService.record_or_update_payment(auto_commit=False)
           - Set PaymentEvent.payment_id = Payment.id
           - Set PaymentEvent.processing_status = PROCESSED
           - Flush/Commit.
        6. On error: rollback financial mutation, mark PaymentEvent FAILED, and raise/return error.
        """
        # 1. Load the PaymentEvent
        event = db.query(PaymentEvent).filter(PaymentEvent.id == event_id).first()
        if not event:
            raise PaymentEventNotFoundError(f"PaymentEvent {event_id} does not exist")

        # 2. Idempotency Check: Already processed?
        if event.processing_status == EventProcessingStatus.PROCESSED.value:
            logger.info("PaymentEvent %s is already PROCESSED; returning existing linked payment", event.id)
            linked_payment = None
            if event.payment_id:
                linked_payment = self._payment_service.get_payment_by_id(
                    db=db, payment_id=event.payment_id, merchant_id=event.merchant_id
                )
            return PaymentEventProcessingResult(
                event_id=event.id,
                processing_status=EventProcessingStatus.PROCESSED,
                payment_id=event.payment_id,
                payment=linked_payment,
                is_duplicate=True,
            )

        if event.processing_status in (EventProcessingStatus.DUPLICATE.value, EventProcessingStatus.IGNORED.value):
            logger.info("PaymentEvent %s is in status '%s'; skipping processing", event.id, event.processing_status)
            return PaymentEventProcessingResult(
                event_id=event.id,
                processing_status=EventProcessingStatus(event.processing_status),
                payment_id=event.payment_id,
                is_duplicate=True,
            )

        # 3. Verify Merchant Association
        if event.merchant_id is None:
            logger.warning("PaymentEvent %s has no associated merchant_id; cannot process payment", event.id)
            with db.begin_nested():
                event.processing_status = EventProcessingStatus.FAILED.value
                event.error_code = "UNRESOLVED_MERCHANT"
                event.error_message = "PaymentEvent has no associated active merchant context"
                event.processed_at = datetime.now(timezone.utc)
                db.flush()

            if auto_commit:
                db.commit()
                db.refresh(event)

            if raise_on_error:
                raise UnresolvedMerchantEventError(f"PaymentEvent {event.id} has no associated active merchant context")

            return PaymentEventProcessingResult(
                event_id=event.id,
                processing_status=EventProcessingStatus.FAILED,
                error_code="UNRESOLVED_MERCHANT",
                error_message="PaymentEvent has no associated active merchant context",
            )

        # 4. Resolve NormalizedPayment using Provider Abstraction
        target_payment_data = normalized_payment
        if target_payment_data is None:
            provider_adapter = get_provider(event.provider)

            if raw_event_payload is not None:
                norm_event = provider_adapter.normalize_event_payload(raw_event_payload)
                target_payment_data = norm_event.payment

            if target_payment_data is None and event.provider_payment_id:
                target_payment_data = provider_adapter.fetch_payment(event.provider_payment_id)

        if target_payment_data is None:
            logger.warning("PaymentEvent %s contains no payment entity and could not be fetched", event.id)
            with db.begin_nested():
                event.processing_status = EventProcessingStatus.FAILED.value
                event.error_code = "NO_PAYMENT_DATA"
                event.error_message = "No payment entity found in event payload or provider lookup"
                event.processed_at = datetime.now(timezone.utc)
                db.flush()

            if auto_commit:
                db.commit()
                db.refresh(event)

            if raise_on_error:
                raise NonPaymentEventError(f"PaymentEvent {event.id} does not contain valid payment information")

            return PaymentEventProcessingResult(
                event_id=event.id,
                processing_status=EventProcessingStatus.FAILED,
                error_code="NO_PAYMENT_DATA",
                error_message="No payment entity found in event payload or provider lookup",
            )

        # Check if an existing payment is present to detect actual lifecycle transitions
        existing_payment = self._payment_service.get_payment_by_provider_payment_id(
            db=db,
            provider=event.provider,
            provider_payment_id=event.provider_payment_id or target_payment_data.provider_payment_id,
        )
        previous_status = existing_payment.status if existing_payment else None

        # 5. Atomic Transaction Boundary
        try:
            with db.begin_nested():
                # Record or transition the canonical Payment (auto_commit=False)
                payment, is_created = self._payment_service.record_or_update_payment(
                    db=db,
                    merchant_id=event.merchant_id,
                    payment_data=target_payment_data,
                    auto_commit=False,
                )

                # Generate OutboxEvent only on meaningful state changes (Phase 4.3)
                # Same-status repeats (e.g. CAPTURED -> CAPTURED) produce NO OutboxEvent
                outbox_event = None
                has_meaningful_state_change = is_created or (previous_status and previous_status != payment.status)
                if has_meaningful_state_change:
                    outbox_event = self._outbox_service.create_payment_outbox_event(
                        db=db,
                        payment=payment,
                        payment_event_id=event.id,
                        provider_event_id=event.event_id,
                        auto_commit=False,
                    )

                # Link Payment to PaymentEvent
                event.payment_id = payment.id
                event.processing_status = EventProcessingStatus.PROCESSED.value
                event.processed_at = datetime.now(timezone.utc)
                event.error_code = None
                event.error_message = None
                db.flush()

            if auto_commit:
                db.commit()
                db.refresh(event)
                db.refresh(payment)
                if outbox_event:
                    db.refresh(outbox_event)

            logger.info(
                "Successfully processed PaymentEvent id=%s -> linked to Payment id=%s (is_created=%s, outbox_event_id=%s)",
                event.id,
                payment.id,
                is_created,
                outbox_event.id if outbox_event else None,
            )

            return PaymentEventProcessingResult(
                event_id=event.id,
                processing_status=EventProcessingStatus.PROCESSED,
                payment_id=payment.id,
                payment=payment,
                outbox_event_id=outbox_event.id if outbox_event else None,
                outbox_event=outbox_event,
                is_created=is_created,
            )

        except Exception as exc:
            # Atomic rollback: savepoint cleanly unwound any payment mutations
            logger.error("Failed to process PaymentEvent %s: %s", event.id, exc)
            error_code = exc.__class__.__name__
            error_message = str(exc)[:500]

            with db.begin_nested():
                event.processing_status = EventProcessingStatus.FAILED.value
                event.error_code = error_code
                event.error_message = error_message
                event.processed_at = datetime.now(timezone.utc)
                event.payment_id = None
                db.flush()

            if auto_commit:
                db.commit()
                db.refresh(event)

            if raise_on_error:
                raise

            return PaymentEventProcessingResult(
                event_id=event.id,
                processing_status=EventProcessingStatus.FAILED,
                error_code=error_code,
                error_message=error_message,
            )


# Global singleton instance
payment_event_service = PaymentEventService()
