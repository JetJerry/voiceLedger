"""
VoiceLedger Canonical Webhook Endpoint (API v1).

Authenticates inbound Razorpay webhooks, deduplicates provider events at Level 1,
and persists canonical PaymentEvent records transactionally.

Strict Financial Boundary:
- Strictly does NOT create, mutate, or transition Payment records in this batch.
- Strictly does NOT create VoiceNotification or OutboxEvent records.
- Event processing, state transitions, and outbox emission belong to Phase 4.
"""
import json
from fastapi import APIRouter, Request, Header, HTTPException, Depends, status
from sqlalchemy.orm import Session

from backend.app.core.logging import logger
from backend.app.db.session import get_db
from backend.app.services.webhook_ingestion_service import webhook_ingestion_service
from backend.app.services.payment_event_service import payment_event_service
from backend.app.providers.exceptions import (
    ProviderAuthenticationError,
    ProviderValidationError,
)

router = APIRouter(prefix="/webhooks", tags=["Webhooks v1"])

MAX_WEBHOOK_SIZE_BYTES = 1024 * 1024  # 1 MB maximum payload limit


@router.post("/razorpay", status_code=status.HTTP_200_OK)
async def handle_razorpay_webhook_v1(
    request: Request,
    x_razorpay_signature: str = Header(None, alias="X-Razorpay-Signature"),
    x_razorpay_event_id: str = Header(None, alias="X-Razorpay-Event-Id"),
    db: Session = Depends(get_db),
):
    """
    Razorpay Webhook Ingestion & Deduplication Endpoint.

    Invariants:
    - Verifies HMAC-SHA256 signature using raw request body bytes.
    - Enforces 1 MB payload size limit (returns HTTP 413).
    - Rejects missing, empty, or invalid signatures with HTTP 401.
    - Rejects malformed JSON or missing event identifiers with HTTP 400.
    - Deduplicates against existing PaymentEvent records; returns 200 with duplicate=True.
    - Financial Safety: Never creates or updates Payment records.
    """
    # 1. Enforce payload size limits
    content_length = request.headers.get("Content-Length")
    if content_length:
        try:
            if int(content_length) > MAX_WEBHOOK_SIZE_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail="Webhook payload exceeds size limit",
                )
        except ValueError:
            pass

    # 2. Read raw request body bytes
    raw_body = await request.body()
    if len(raw_body) > MAX_WEBHOOK_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Webhook payload exceeds size limit",
        )

    # 3. Cryptographic Signature Verification
    if not x_razorpay_signature:
        logger.warning("Rejecting Razorpay webhook: missing X-Razorpay-Signature header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing webhook signature",
        )

    # 4. Ingest, Deduplicate & Persist PaymentEvent
    try:
        event, is_duplicate = webhook_ingestion_service.ingest_razorpay_webhook(
            db=db,
            raw_body=raw_body,
            signature=x_razorpay_signature,
            header_event_id=x_razorpay_event_id,
        )
    except ProviderAuthenticationError as exc:
        logger.warning("Rejecting Razorpay webhook: signature authentication failure (%s)", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing webhook signature",
        ) from exc
    except ProviderValidationError as exc:
        logger.warning("Rejecting Razorpay webhook: payload validation failure (%s)", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error("Unhandled error during webhook ingestion: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error processing webhook",
        ) from exc

    # 5. Wire PaymentEventService into the successful webhook processing path
    if not is_duplicate and event.merchant_id is not None:
        payload_dict = None
        try:
            payload_dict = json.loads(raw_body.decode("utf-8"))
        except Exception:
            pass

        try:
            result = payment_event_service.process_payment_event(
                db=db,
                event_id=event.id,
                raw_event_payload=payload_dict,
                auto_commit=True,
                raise_on_error=False,
            )
            if result.payment:
                payment_notes = (
                    (payload_dict or {})
                    .get("payload", {})
                    .get("payment", {})
                    .get("entity", {})
                    .get("notes", {})
                )
                sale_id = payment_notes.get("sale_id") if isinstance(payment_notes, dict) else None
                from backend.app.services.store_service import store_service
                store_service.sync_payment_to_sale(db, result.payment, sale_id=sale_id)
        except Exception as proc_exc:
            logger.error("Unhandled error during payment event processing for %s: %s", event.id, proc_exc)

    return {
        "status": "accepted",
        "verified": True,
        "event": event.event_type,
        "event_id": event.event_id,
        "duplicate": is_duplicate,
    }
