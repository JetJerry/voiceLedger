from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.schemas.recovery import RecoveryPriorityItem, RecoveryTriggerRequest, RecoveryActionResponse
from backend.app.services.recovery_service import recovery_service

router = APIRouter(prefix="/recovery", tags=["Payment Recovery Engine"])


@router.get("/queue", response_model=List[RecoveryPriorityItem])
def get_recovery_queue(db: Session = Depends(get_db)):
    """
    Returns the prioritized queue of overdue and partially paid receivables.
    """
    return recovery_service.get_recovery_queue(db)


@router.post("/trigger", response_model=RecoveryActionResponse)
def trigger_recovery(request: RecoveryTriggerRequest, db: Session = Depends(get_db)):
    """
    Triggers payment link resend or WhatsApp reminder for an outstanding receivable.
    """
    try:
        result = recovery_service.trigger_recovery_action(
            db=db,
            sale_id=request.sale_id,
            action_type=request.action_type,
            channel=request.channel,
            custom_message=request.custom_message
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
