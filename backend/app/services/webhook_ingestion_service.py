"""
VoiceLedger Webhook Ingestion Service.

Authoritative service for ingesting, authenticating, deduplicating, and persisting
inbound payment provider webhooks (Razorpay) as canonical PaymentEvent records.

Invariants:
- Signature is verified over raw bytes before any event handling.
- Level 1 Deduplication enforced via database uniqueness on (provider, event_id).
- Safe concurrent race handling via transactional rollbacks.
- Merchant association strictly server-verified (client claims never trusted blindly).
- STRICT FINANCIAL BOUNDARY: Never creates, updates, or transitions Payment models in this batch.
"""
from datetime import datetime, timezone
import hashlib
import uuid
from typing import Dict, Any, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend.app.core.logging import logger
from backend.app.core.security import sanitize_sensitive_data
from backend.app.models.merchant import Merchant
from backend.app.models.payment import Payment
from backend.app.models.payment_event import PaymentEvent, EventProcessingStatus
from backend.app.models.provider_connection import ProviderConnection
from backend.app.providers.razorpay.webhook import razorpay_webhook_verifier
from backend.app.providers.exceptions import (
    ProviderAuthenticationError,
    ProviderValidationError,
)


class WebhookIngestionService:
    """
    Ingests and deduplicates inbound payment provider webhooks.
    """

    PROVIDER_NAME: str = "RAZORPAY"

    def resolve_merchant_for_event(
        self,
        db: Session,
        raw_payload: Dict[str, Any],
        provider_payment_id: Optional[str] = None,
    ) -> Optional[uuid.UUID]:
        """
        Server-side merchant resolution for inbound Razorpay events.

        Precedence:
        1. Authoritative ProviderConnection matching Razorpay 'account_id'.
        2. Pre-existing Payment matching provider_payment_id.
        3. Validated merchant_id in notes ONLY if active in merchants table.

        Returns None if unresolvable. Never fabricates a merchant or guesses.
        """
        # 1. Resolve via ProviderConnection account reference
        account_id = raw_payload.get("account_id")
        if account_id and isinstance(account_id, str):
            clean_acc = account_id.strip()
            possible_refs = [clean_acc]
            if clean_acc.startswith("acc_"):
                possible_refs.append(clean_acc[4:])
            else:
                possible_refs.append(f"acc_{clean_acc}")

            conn = (
                db.query(ProviderConnection)
                .filter(
                    ProviderConnection.provider == self.PROVIDER_NAME,
                    ProviderConnection.provider_account_reference.in_(possible_refs),
                    ProviderConnection.status == "ACTIVE",
                )
                .first()
            )
            if conn:
                logger.info("Resolved merchant %s via ProviderConnection account %s", conn.merchant_id, account_id)
                return conn.merchant_id

        # 2. Resolve via pre-existing Payment record if one already exists
        if provider_payment_id:
            existing_payment = (
                db.query(Payment)
                .filter(
                    Payment.provider == self.PROVIDER_NAME,
                    Payment.provider_payment_id == provider_payment_id,
                )
                .first()
            )
            if existing_payment:
                logger.info(
                    "Resolved merchant %s via existing Payment %s",
                    existing_payment.merchant_id,
                    provider_payment_id,
                )
                return existing_payment.merchant_id

        # 3. If payload notes contain a merchant_id, verify against merchants table
        payment_entity = (
            raw_payload.get("payload", {})
            .get("payment", {})
            .get("entity")
        )
        if isinstance(payment_entity, dict):
            notes = payment_entity.get("notes")
            if isinstance(notes, dict) and "merchant_id" in notes:
                try:
                    candidate_id = uuid.UUID(str(notes["merchant_id"]))
                    merchant = (
                        db.query(Merchant)
                        .filter(
                            Merchant.id == candidate_id,
                            Merchant.status == "ACTIVE",
                        )
                        .first()
                    )
                    if merchant:
                        logger.info("Resolved active merchant %s from verified notes", merchant.id)
                        return merchant.id
                except (ValueError, TypeError):
                    logger.warning("Invalid merchant_id format in notes: %s", notes.get("merchant_id"))

        logger.info("Webhook event could not be associated with a known active merchant; leaving unassigned")
        return None

    def ingest_razorpay_webhook(
        self,
        db: Session,
        raw_body: bytes,
        signature: Optional[str],
        header_event_id: Optional[str] = None,
    ) -> Tuple[PaymentEvent, bool]:
        """
        Authenticate, deduplicate, and persist an inbound Razorpay webhook.

        Returns:
            Tuple[PaymentEvent, bool]: (payment_event, is_duplicate)

        Raises:
            ProviderAuthenticationError: On missing or invalid cryptographic signature.
            ProviderValidationError: On malformed JSON or missing required event fields.
        """
        # 1. Cryptographic Signature Verification & JSON parsing
        # (verify_and_parse raises ProviderAuthenticationError / ProviderValidationError)
        verified_payload = razorpay_webhook_verifier.verify_and_parse(
            raw_body=raw_body,
            signature=signature,
        )

        # 2. Extract Event Identifier
        raw_event_id = verified_payload.get("id") or verified_payload.get("event_id") or header_event_id
        if not raw_event_id or not isinstance(raw_event_id, str) or not raw_event_id.strip():
            logger.warning("Rejecting Razorpay webhook: missing or empty event ID")
            raise ProviderValidationError(
                "Missing or empty event ID in Razorpay webhook payload",
                provider=self.PROVIDER_NAME,
            )
        event_id = raw_event_id.strip()

        # 3. Extract Event Type
        raw_event_type = verified_payload.get("event")
        if not raw_event_type or not isinstance(raw_event_type, str) or not raw_event_type.strip():
            logger.warning("Rejecting Razorpay webhook: missing or empty event type")
            raise ProviderValidationError(
                "Missing or empty event type in Razorpay webhook payload",
                provider=self.PROVIDER_NAME,
            )
        event_type = raw_event_type.strip()

        # 4. Extract Provider Payment Identifier if present
        payment_entity = (
            verified_payload.get("payload", {})
            .get("payment", {})
            .get("entity")
        )
        provider_payment_id = None
        if isinstance(payment_entity, dict):
            p_id = payment_entity.get("id")
            if p_id and isinstance(p_id, str):
                provider_payment_id = p_id.strip()

        # 5. Payload SHA-256 fingerprint for tamper audit
        payload_hash = hashlib.sha256(raw_body).hexdigest()

        # 6. Level 1 Deduplication Check
        existing_event = (
            db.query(PaymentEvent)
            .filter(
                PaymentEvent.provider == self.PROVIDER_NAME,
                PaymentEvent.event_id == event_id,
            )
            .first()
        )
        if existing_event:
            logger.info(
                "Deduplicated Razorpay webhook event: provider=%s event_id=%s (already %s)",
                self.PROVIDER_NAME,
                event_id,
                existing_event.processing_status,
            )
            return existing_event, True

        # 7. Resolve Merchant Association
        merchant_id = self.resolve_merchant_for_event(
            db=db,
            raw_payload=verified_payload,
            provider_payment_id=provider_payment_id,
        )

        # 8. Transactional Event Persistence
        new_event = PaymentEvent(
            provider=self.PROVIDER_NAME,
            event_id=event_id,
            event_type=event_type,
            provider_payment_id=provider_payment_id,
            payload_hash=payload_hash,
            processing_status=EventProcessingStatus.RECEIVED.value,
            received_at=datetime.now(timezone.utc),
            merchant_id=merchant_id,
            payment_id=None,  # STRICT BOUNDARY: Never creates/attaches Payment in Phase 3.4
        )

        try:
            db.add(new_event)
            db.commit()
            db.refresh(new_event)
            logger.info(
                "Persisted new Razorpay PaymentEvent id=%s event_id=%s event_type=%s",
                new_event.id,
                event_id,
                event_type,
            )
            return new_event, False
        except IntegrityError:
            db.rollback()
            # Concurrent race condition: another worker inserted this event concurrently
            logger.info("Concurrent race detected on (provider, event_id); fetching existing winner")
            winner = (
                db.query(PaymentEvent)
                .filter(
                    PaymentEvent.provider == self.PROVIDER_NAME,
                    PaymentEvent.event_id == event_id,
                )
                .first()
            )
            if winner:
                return winner, True
            raise


webhook_ingestion_service = WebhookIngestionService()
