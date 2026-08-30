from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.models import Payment, Sale
from backend.app.schemas.payment import PaymentResponse, PaymentLinkCreate, PaymentLinkResponse
from backend.app.services.razorpay_service import razorpay_service
from backend.app.services.reconciliation_service import reconciliation_service

router = APIRouter(prefix="/payments", tags=["Payments & Reconciliation"])


class PaymentSimulateRequest(BaseModel):
    sale_id: str
    amount: float
    status: str = "captured"  # captured or failed
    method: str = "upi"
    vpa: Optional[str] = "customer@okhdfcbank"


@router.post("/create-link", response_model=PaymentLinkResponse)
def create_payment_link(request: PaymentLinkCreate, db: Session = Depends(get_db)):
    """
    Manually creates a Razorpay Payment Link for an existing sale.
    """
    sale = db.query(Sale).filter(Sale.id == request.sale_id).first()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
        
    amount = request.amount or sale.outstanding_amount or sale.total_amount
    link_info = razorpay_service.create_payment_link(
        amount=amount,
        sale_id=sale.id,
        customer_name=request.customer_name or sale.customer_name,
        customer_phone=request.customer_phone or (sale.customer.phone if sale.customer else None),
        description=request.description or f"Payment for #{sale.id}"
    )

    sale.razorpay_payment_link_id = link_info.get("id")
    sale.razorpay_payment_link_url = link_info.get("short_url")
    db.commit()

    return PaymentLinkResponse(
        id=link_info.get("id"),
        short_url=link_info.get("short_url"),
        amount=amount,
        currency="INR",
        status=link_info.get("status", "created"),
        sale_id=sale.id
    )


@router.get("", response_model=List[PaymentResponse])
def list_payments(limit: int = 50, db: Session = Depends(get_db)):
    """
    List all payment transactions received from Razorpay.
    """
    payments = db.query(Payment).order_by(Payment.created_at.desc()).limit(limit).all()
    return payments


@router.post("/simulate")
def simulate_payment(request: PaymentSimulateRequest, db: Session = Depends(get_db)):
    """
    Simulates a live Razorpay test payment (Full, Partial, or Failed) and triggers reconciliation.
    Ideal for fast demo and evaluation without waiting for external checkout.
    """
    sale = db.query(Sale).filter(Sale.id == request.sale_id).first()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")

    import uuid
    sim_pay_id = f"pay_sim_{uuid.uuid4().hex[:10]}"
    
    result = reconciliation_service.process_payment_event(
        db=db,
        razorpay_payment_id=sim_pay_id,
        amount_in_inr=request.amount,
        status=request.status,
        sale_id=sale.id,
        payment_link_id=sale.razorpay_payment_link_id,
        method=request.method,
        vpa=request.vpa
    )
    return result
