"""
VoiceLedger Canonical Payment Core Service.

Authoritative domain service for financial payment creation, state transitions,
provider-payment identity management, and Level 2 idempotency guarantees.

Invariants:
- All payment amounts are non-negative integer minor units (paise for INR). Floats are strictly prohibited.
- Level 2 Idempotency: Identity is strictly (provider, provider_payment_id) backed by PostgreSQL uniqueness.
- Transactional Boundary: Default auto_commit=False so callers can compose atomic units (Payment + PaymentEvent + OutboxEvent).
- Strict State Machine: Validates legal transitions; rejects illegal jumps (e.g. REFUNDED -> CAPTURED).
- Restricted Creation Status: Prohibits initial creation directly into refund states (REFUNDED, PARTIALLY_REFUNDED).
- Financial Immutability: Prevents tampering with principal amount, currency, or merchant assignment.
- Provider Independence: Consumes NormalizedPayment without any direct coupling to gateway clients.
"""
from datetime import datetime, timezone
from typing import Optional, List, Tuple, Set, Dict, Any
import uuid

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend.app.models.payment import Payment, PaymentStatus
from backend.app.models.merchant import Merchant
from backend.app.providers.schemas import NormalizedPayment, PaymentMethodType
from backend.app.core.logging import logger


# =====================================================================
# Domain Exceptions
# =====================================================================

class PaymentCoreError(Exception):
    """Base exception for all Payment Core domain errors."""
    pass


class PaymentNotFoundError(PaymentCoreError):
    """Raised when a requested payment does not exist."""
    pass


class InactiveMerchantError(PaymentCoreError):
    """Raised when an operation is attempted for a non-existent or deactivated merchant."""
    pass


class CrossMerchantPaymentError(PaymentCoreError):
    """Raised when attempting to access or modify a payment belonging to another merchant."""
    pass


class InvalidPaymentStateTransitionError(PaymentCoreError):
    """Raised when an illegal payment status transition is attempted."""
    pass


class InvalidPaymentCreationStatusError(PaymentCoreError):
    """Raised when attempting to initialize a payment directly with a prohibited status."""
    pass


class PaymentFinancialMismatchError(PaymentCoreError):
    """Raised when an update attempts to tamper with immutable financial fields (amount, currency)."""
    pass


# =====================================================================
# State Machine Definitions
# =====================================================================

# Allowed initial statuses when a payment is first created
ALLOWED_CREATION_STATUSES: Set[PaymentStatus] = {
    PaymentStatus.CREATED,
    PaymentStatus.AUTHORIZED,
    PaymentStatus.CAPTURED,
    PaymentStatus.FAILED,
}

# Explicit directed graph of valid state transitions
ALLOWED_TRANSITIONS: Dict[PaymentStatus, Set[PaymentStatus]] = {
    PaymentStatus.CREATED: {
        PaymentStatus.AUTHORIZED,
        PaymentStatus.CAPTURED,
        PaymentStatus.FAILED,
    },
    PaymentStatus.AUTHORIZED: {
        PaymentStatus.CAPTURED,
        PaymentStatus.FAILED,
    },
    PaymentStatus.CAPTURED: {
        PaymentStatus.PARTIALLY_REFUNDED,
        PaymentStatus.REFUNDED,
    },
    PaymentStatus.PARTIALLY_REFUNDED: {
        PaymentStatus.REFUNDED,
    },
    PaymentStatus.FAILED: set(),    # Terminal state
    PaymentStatus.REFUNDED: set(),  # Terminal state
}


# =====================================================================
# Payment Core Service
# =====================================================================

class PaymentService:
    """
    Canonical Payment Core Service for VoiceLedger.
    """

    def validate_creation_status(self, status: PaymentStatus) -> None:
        """
        Verify that an incoming payment's status is permitted for initial creation.
        Prohibits starting a payment directly in refund statuses without a prior capture.
        """
        if status not in ALLOWED_CREATION_STATUSES:
            raise InvalidPaymentCreationStatusError(
                f"Initial payment creation cannot use status '{status.value}'. "
                f"Allowed initial statuses: {[s.value for s in ALLOWED_CREATION_STATUSES]}"
            )

    def validate_state_transition(
        self,
        current_status: PaymentStatus,
        target_status: PaymentStatus,
    ) -> bool:
        """
        Evaluate whether a proposed transition from current_status to target_status is valid.

        Returns:
            bool: True if this is a valid new transition.
                  False if this is an idempotent repeat (same status).

        Raises:
            InvalidPaymentStateTransitionError: If the proposed transition is illegal.
        """
        # Idempotent repeat: harmless no-op
        if current_status == target_status:
            return False

        allowed = ALLOWED_TRANSITIONS.get(current_status, set())
        if target_status in allowed:
            return True

        raise InvalidPaymentStateTransitionError(
            f"Illegal payment status transition: '{current_status.value}' -> '{target_status.value}'. "
            f"Allowed transitions from '{current_status.value}': {[s.value for s in allowed] or 'None (Terminal)'}"
        )

    def get_payment_by_id(
        self,
        db: Session,
        payment_id: uuid.UUID,
        merchant_id: Optional[uuid.UUID] = None,
    ) -> Optional[Payment]:
        """
        Fetch a payment by its primary UUID, optionally scoped to a merchant for tenant isolation.
        """
        query = db.query(Payment).filter(Payment.id == payment_id)
        if merchant_id is not None:
            query = query.filter(Payment.merchant_id == merchant_id)
        return query.first()

    def get_payment_by_provider_payment_id(
        self,
        db: Session,
        provider: str,
        provider_payment_id: str,
        merchant_id: Optional[uuid.UUID] = None,
    ) -> Optional[Payment]:
        """
        Fetch a payment by its authoritative provider payment reference.
        """
        query = db.query(Payment).filter(
            Payment.provider == provider,
            Payment.provider_payment_id == provider_payment_id,
        )
        if merchant_id is not None:
            query = query.filter(Payment.merchant_id == merchant_id)
        return query.first()

    def list_payments_for_merchant(
        self,
        db: Session,
        merchant_id: uuid.UUID,
        status: Optional[PaymentStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Payment]:
        """
        List payments for a specific merchant, ordered newest first.
        """
        query = db.query(Payment).filter(Payment.merchant_id == merchant_id)
        if status is not None:
            query = query.filter(Payment.status == status.value)
        return query.order_by(Payment.created_at.desc()).limit(limit).offset(offset).all()

    def record_or_update_payment(
        self,
        db: Session,
        merchant_id: uuid.UUID,
        payment_data: NormalizedPayment,
        auto_commit: bool = False,
    ) -> Tuple[Payment, bool]:
        """
        Idempotently create or transition a canonical Payment record from normalized provider data.

        Guarantees:
        1. Tenant Validation: Confirms merchant exists and is ACTIVE.
        2. Idempotency: Re-processing identical provider payment IDs returns the existing row.
        3. Anti-Tampering: Verifies merchant ownership, amount_minor, and currency match.
        4. State Machine: Transitions forward legally or treats identical status as idempotent repeat.
        5. Concurrency: Uses PostgreSQL unique constraint via SAVEPOINT to safely recover race conditions.
        6. Composable Transactions: Default auto_commit=False flushes to DB without committing caller's transaction.

        Returns:
            Tuple[Payment, bool]: (payment, is_created)
        """
        # 1. Verify merchant exists and is ACTIVE
        merchant = db.query(Merchant).filter(
            Merchant.id == merchant_id,
            Merchant.status == "ACTIVE",
        ).first()
        if not merchant:
            raise InactiveMerchantError(f"Merchant {merchant_id} does not exist or is not active")

        # 2. Check for existing payment under (provider, provider_payment_id)
        existing = self.get_payment_by_provider_payment_id(
            db=db,
            provider=payment_data.provider,
            provider_payment_id=payment_data.provider_payment_id,
        )

        if existing is not None:
            return self._apply_existing_payment_update(
                db=db,
                payment=existing,
                merchant_id=merchant_id,
                payment_data=payment_data,
                auto_commit=auto_commit,
            )

        # 3. New payment creation path
        self.validate_creation_status(payment_data.status)

        new_payment = Payment(
            merchant_id=merchant_id,
            provider=payment_data.provider,
            provider_payment_id=payment_data.provider_payment_id,
            provider_order_id=payment_data.provider_order_id,
            amount_minor=payment_data.amount_minor,
            currency=payment_data.currency,
            payment_method=(
                payment_data.payment_method.value
                if payment_data.payment_method and payment_data.payment_method != PaymentMethodType.UNKNOWN
                else None
            ),
            status=payment_data.status.value,
            payer_reference=payment_data.payer_reference,
            provider_created_at=payment_data.provider_created_at,
            captured_at=(
                payment_data.captured_at
                if payment_data.status == PaymentStatus.CAPTURED
                else None
            ),
        )

        # 4. Savepoint-protected insertion for safe concurrency handling
        try:
            with db.begin_nested():
                db.add(new_payment)
                db.flush()

            if auto_commit:
                db.commit()
                db.refresh(new_payment)

            logger.info(
                "Created canonical Payment id=%s merchant_id=%s provider=%s provider_payment_id=%s status=%s amount_minor=%d",
                new_payment.id,
                merchant_id,
                new_payment.provider,
                new_payment.provider_payment_id,
                new_payment.status,
                new_payment.amount_minor,
            )
            return new_payment, True

        except IntegrityError:
            # Race condition: another concurrent worker inserted this payment
            logger.info(
                "Concurrent race detected on (provider=%s, provider_payment_id=%s); resolving winning payment",
                payment_data.provider,
                payment_data.provider_payment_id,
            )
            winner = self.get_payment_by_provider_payment_id(
                db=db,
                provider=payment_data.provider,
                provider_payment_id=payment_data.provider_payment_id,
            )
            if winner:
                return self._apply_existing_payment_update(
                    db=db,
                    payment=winner,
                    merchant_id=merchant_id,
                    payment_data=payment_data,
                    auto_commit=auto_commit,
                )
            raise

    def _apply_existing_payment_update(
        self,
        db: Session,
        payment: Payment,
        merchant_id: uuid.UUID,
        payment_data: NormalizedPayment,
        auto_commit: bool,
    ) -> Tuple[Payment, bool]:
        """
        Handle updates to an existing payment with strict security, immutability, and state checks.
        """
        # 1. Anti-IDOR: Prevent cross-merchant payment hijacking
        if payment.merchant_id != merchant_id:
            raise CrossMerchantPaymentError(
                f"Payment {payment.provider_payment_id} belongs to merchant {payment.merchant_id}, "
                f"cannot be updated or associated with merchant {merchant_id}"
            )

        # 2. Immutability: Principal amount and currency must never change
        if payment.amount_minor != payment_data.amount_minor:
            raise PaymentFinancialMismatchError(
                f"Immutable amount_minor mismatch for payment {payment.id}: "
                f"existing={payment.amount_minor}, incoming={payment_data.amount_minor}"
            )
        if payment.currency != payment_data.currency:
            raise PaymentFinancialMismatchError(
                f"Immutable currency mismatch for payment {payment.id}: "
                f"existing='{payment.currency}', incoming='{payment_data.currency}'"
            )

        # 3. State Machine transition
        current_status = PaymentStatus(payment.status)
        target_status = payment_data.status

        is_new_transition = self.validate_state_transition(current_status, target_status)

        if is_new_transition:
            payment.status = target_status.value
            if target_status == PaymentStatus.CAPTURED and not payment.captured_at:
                payment.captured_at = payment_data.captured_at or datetime.now(timezone.utc)
            payment.updated_at = datetime.now(timezone.utc)
            logger.info(
                "Transitioned Payment id=%s status: %s -> %s",
                payment.id,
                current_status.value,
                target_status.value,
            )

        # 4. Update non-financial metadata if newly available
        if payment_data.provider_order_id and not payment.provider_order_id:
            payment.provider_order_id = payment_data.provider_order_id
        if (
            payment_data.payment_method
            and payment_data.payment_method != PaymentMethodType.UNKNOWN
            and not payment.payment_method
        ):
            payment.payment_method = payment_data.payment_method.value
        if payment_data.payer_reference and not payment.payer_reference:
            payment.payer_reference = payment_data.payer_reference
        if payment_data.captured_at and not payment.captured_at:
            payment.captured_at = payment_data.captured_at

        if auto_commit:
            db.commit()
            db.refresh(payment)
        else:
            db.flush()

        return payment, False

    def transition_payment_status(
        self,
        db: Session,
        payment: Payment,
        target_status: PaymentStatus,
        merchant_id: Optional[uuid.UUID] = None,
        captured_at: Optional[datetime] = None,
        auto_commit: bool = False,
    ) -> Payment:
        """
        Explicitly transition an existing payment to a target status with validation.
        """
        if merchant_id is not None and payment.merchant_id != merchant_id:
            raise CrossMerchantPaymentError(
                f"Payment {payment.id} does not belong to merchant {merchant_id}"
            )

        current_status = PaymentStatus(payment.status)
        is_new_transition = self.validate_state_transition(current_status, target_status)

        if is_new_transition:
            payment.status = target_status.value
            if target_status == PaymentStatus.CAPTURED and not payment.captured_at:
                payment.captured_at = captured_at or datetime.now(timezone.utc)
            payment.updated_at = datetime.now(timezone.utc)
            logger.info(
                "Explicitly transitioned Payment id=%s: %s -> %s",
                payment.id,
                current_status.value,
                target_status.value,
            )

        if auto_commit:
            db.commit()
            db.refresh(payment)
        else:
            db.flush()

        return payment


# Global singleton instance
payment_service = PaymentService()
