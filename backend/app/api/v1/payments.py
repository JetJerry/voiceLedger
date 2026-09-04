"""
VoiceLedger Canonical Payments API (v1).

Authoritative merchant endpoints for querying financial payments,
transaction history, and payment status within strict tenant boundaries.
"""
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.db.session import get_db
from backend.app.api.deps import get_current_merchant
from backend.app.models.merchant import Merchant
from backend.app.models.payment import Payment, PaymentStatus

router = APIRouter(prefix="/payments", tags=["Payments v1"])


class PaymentRecordResponse(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID
    provider: str
    provider_payment_id: str
    provider_order_id: Optional[str] = None
    amount_minor: int
    amount: float
    currency: str
    payment_method: Optional[str] = None
    status: str
    payer_reference: Optional[str] = None
    captured_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentsListResponse(BaseModel):
    items: List[PaymentRecordResponse]
    total_count: int
    captured_count: int
    total_captured_minor: int
    total_captured: float


@router.get("", response_model=PaymentsListResponse)
def list_payments(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    """
    List historical canonical payments for the authenticated merchant organization.
    """
    base_query = db.query(Payment).filter(Payment.merchant_id == current_merchant.id)

    if status_filter and status_filter.upper() != "ALL":
        base_query = base_query.filter(Payment.status == status_filter.upper())

    total_count = base_query.count()
    records = (
        base_query.order_by(desc(Payment.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )

    all_payments = db.query(Payment).filter(Payment.merchant_id == current_merchant.id).all()
    captured = [p for p in all_payments if p.status == PaymentStatus.CAPTURED.value]
    total_captured_minor = sum(p.amount_minor for p in captured)

    items = [
        PaymentRecordResponse(
            id=p.id,
            merchant_id=p.merchant_id,
            provider=p.provider,
            provider_payment_id=p.provider_payment_id,
            provider_order_id=p.provider_order_id,
            amount_minor=p.amount_minor,
            amount=p.amount,
            currency=p.currency,
            payment_method=p.payment_method,
            status=p.status,
            payer_reference=p.payer_reference,
            captured_at=p.captured_at,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in records
    ]

    return PaymentsListResponse(
        items=items,
        total_count=total_count,
        captured_count=len(captured),
        total_captured_minor=total_captured_minor,
        total_captured=round(total_captured_minor / 100.0, 2),
    )


@router.get("/{payment_id}", response_model=PaymentRecordResponse)
def get_payment(
    payment_id: uuid.UUID,
    current_merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    """Retrieve single payment with strict tenant isolation."""
    payment = (
        db.query(Payment)
        .filter(Payment.id == payment_id, Payment.merchant_id == current_merchant.id)
        .first()
    )
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    return PaymentRecordResponse(
        id=payment.id,
        merchant_id=payment.merchant_id,
        provider=payment.provider,
        provider_payment_id=payment.provider_payment_id,
        provider_order_id=payment.provider_order_id,
        amount_minor=payment.amount_minor,
        amount=payment.amount,
        currency=payment.currency,
        payment_method=payment.payment_method,
        status=payment.status,
        payer_reference=payment.payer_reference,
        captured_at=payment.captured_at,
        created_at=payment.created_at,
        updated_at=payment.updated_at,
    )
