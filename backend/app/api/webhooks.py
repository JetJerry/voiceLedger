import json
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Header, HTTPException, Depends
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.models import WebhookEvent
from backend.app.services.razorpay_service import razorpay_service
from backend.app.services.reconciliation_service import reconciliation_service

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
    
    # 1. Verify Webhook Signature
    if not razorpay_service.verify_webhook_signature(raw_body, x_razorpay_signature):
        raise HTTPException(status_code=400, detail="Invalid Razorpay webhook signature")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {str(e)}")

    event_id = x_razorpay_event_id or payload.get("event_id") or f"wh_evt_{uuid.uuid4().hex[:12]}"
    event_type = payload.get("event", "unknown")

    # 2. Check Idempotency
    existing_event = db.query(WebhookEvent).filter(WebhookEvent.event_id == event_id).first()
    if existing_event and existing_event.processed:
        return {"status": "already_processed", "event_id": event_id}

    if not existing_event:
        existing_event = WebhookEvent(
            event_id=event_id,
            event_type=event_type,
            payload=json.dumps(payload),
            processed=False
        )
        db.add(existing_event)
        db.commit()
        db.refresh(existing_event)

    # 3. Deterministic Reconciliation
    reconciliation_result = reconciliation_service.reconcile_from_webhook_payload(db, payload)

    # 4. Mark Event Processed
    existing_event.processed = True
    existing_event.processed_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "status": "success",
        "event_id": event_id,
        "event_type": event_type,
        "reconciliation": reconciliation_result
    }


@router.post("/simulate")
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
