import json
import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Header, HTTPException, Depends
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.models.legacy import WebhookEvent
from backend.app.services.razorpay_service import razorpay_service
from backend.app.services.reconciliation_service import reconciliation_service

logger = logging.getLogger("voiceledger.webhooks")
router = APIRouter(prefix="/webhooks", tags=["Razorpay Webhooks"])


@router.post("/razorpay")
async def handle_razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(None),
    x_razorpay_event_id: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Official Razorpay Webhook Ingestion Endpoint.
    - Verifies HMAC SHA256 Signature
    - Ensures Event Idempotency
    - Reconciles expected vs actual payment
    """
    raw_body = await request.body()

    if not raw_body:
        raise HTTPException(status_code=400, detail="Empty webhook payload")

    event_id = x_razorpay_event_id or f"wh_evt_{uuid.uuid4().hex[:12]}"
    payload_dict = {}
    try:
        payload_dict = json.loads(raw_body.decode("utf-8"))
        event_id = payload_dict.get("event_id") or event_id
        event_type = payload_dict.get("event", "unknown")
    except Exception as exc:
        event_type = "invalid_json"
        db.add(WebhookEvent(
            event_id=event_id,
            event_type="invalid_json",
            payload=raw_body.decode("utf-8", errors="replace"),
            processed=False,
            status="INVALID_JSON",
            error_message=str(exc),
        ))
        db.commit()
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {str(exc)}") from exc

    # 1. Verify Webhook Signature
    if not razorpay_service.verify_webhook_signature(raw_body, x_razorpay_signature):
        # Save audit record of signature failure for merchant visibility
        failed_evt = WebhookEvent(
            event_id=event_id,
            event_type=event_type,
            payload=json.dumps(payload_dict),
            processed=False,
            status="SIGNATURE_VERIFICATION_FAILED",
            error_message="Invalid HMAC signature. Please verify RAZORPAY_WEBHOOK_SECRET matches Razorpay dashboard.",
        )
        db.add(failed_evt)
        db.commit()
        logger.warning("[Webhook] Signature verification failed for event %s", event_id)
        raise HTTPException(status_code=400, detail="Invalid Razorpay webhook signature")

    # 2. Check Idempotency
    existing_event = db.query(WebhookEvent).filter(WebhookEvent.event_id == event_id).first()
    if existing_event and existing_event.processed:
        logger.info("Duplicate Razorpay webhook event ignored: %s", event_id)
        return {"status": "already_processed", "event_id": event_id}

    if not existing_event:
        existing_event = WebhookEvent(
            event_id=event_id,
            event_type=event_type,
            payload=json.dumps(payload_dict),
            processed=False,
            status="RECEIVED",
        )
        db.add(existing_event)
        db.commit()
        db.refresh(existing_event)

    try:
        # 3. Deterministic Reconciliation
        reconciliation_result = reconciliation_service.reconcile_from_webhook_payload(db, payload_dict)
    except Exception as exc:
        logger.exception("Webhook reconciliation failed for event %s: %s", event_id, exc)
        existing_event.status = "RECONCILIATION_FAILED"
        existing_event.error_message = str(exc)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Webhook reconciliation failed: {str(exc)}") from exc

    # 4. Mark Event Processed Successfully
    existing_event.processed = True
    existing_event.status = "PROCESSED"
    existing_event.processed_at = datetime.now(timezone.utc)
    db.commit()

    logger.info("Webhook processed successfully: %s (%s)", event_id, event_type)
    return {
        "status": "success",
        "event_id": event_id,
        "event_type": event_type,
        "reconciliation": reconciliation_result,
    }


@router.get("/logs", tags=["Razorpay Webhooks"])
def get_webhook_logs(
    limit: int = 50,
    status: str = None,
    db: Session = Depends(get_db)
):
    """
    Returns the most recent received Razorpay webhook events from the audit database.
    Shows processing status, errors (if any), timestamps, and full payloads.
    """
    query = db.query(WebhookEvent).order_by(WebhookEvent.created_at.desc())
    if status:
        query = query.filter(WebhookEvent.status == status.upper())
    events = query.limit(limit).all()

    return [
        {
            "id": evt.id,
            "event_id": evt.event_id,
            "event_type": evt.event_type,
            "status": evt.status or ("PROCESSED" if evt.processed else "PENDING"),
            "processed": evt.processed,
            "error_message": evt.error_message,
            "processed_at": evt.processed_at,
            "created_at": evt.created_at,
            "payload": json.loads(evt.payload) if evt.payload else {}
        }
        for evt in events
    ]


@router.post("/logs/{event_id}/retry", tags=["Razorpay Webhooks"])
def retry_webhook_event(
    event_id: str,
    db: Session = Depends(get_db)
):
    """
    Manually re-triggers reconciliation for a failed or un-processed webhook event.
    """
    event = db.query(WebhookEvent).filter(WebhookEvent.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail=f"Webhook event '{event_id}' not found")

    try:
        payload = json.loads(event.payload) if event.payload else {}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Cannot parse payload: {exc}")

    try:
        result = reconciliation_service.reconcile_from_webhook_payload(db, payload)
        event.processed = True
        event.status = "PROCESSED"
        event.error_message = None
        event.processed_at = datetime.now(timezone.utc)
        db.commit()
        return {
            "status": "retry_success",
            "event_id": event_id,
            "reconciliation": result,
        }
    except Exception as exc:
        event.status = "RETRY_FAILED"
        event.error_message = str(exc)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Retry reconciliation failed: {exc}")


@router.post("/simulate", tags=["Razorpay Webhooks"])
def simulate_webhook(
    sale_id: str,
    amount: float,
    status: str = "captured",
    db: Session = Depends(get_db)
):
    """
    Simulates sending a real Razorpay webhook payload for test/demo purposes.
    """
    payload = razorpay_service.simulate_test_webhook_payload(
        sale_id=sale_id,
        amount=amount,
        status=status
    )
    result = reconciliation_service.reconcile_from_webhook_payload(db, payload)
    return {
        "status": "simulated_success",
        "payload": payload,
        "reconciliation": result
    }
