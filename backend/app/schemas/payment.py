from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class PaymentLinkCreate(BaseModel):
    sale_id: str
    amount: Optional[float] = None
    description: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None


class PaymentLinkResponse(BaseModel):
    id: str
    short_url: str
    amount: float
    currency: str = "INR"
    status: str
    sale_id: str


class PaymentResponse(BaseModel):
    id: int
    sale_id: Optional[str] = None
    razorpay_payment_id: str
    razorpay_payment_link_id: Optional[str] = None
    amount: float
    currency: str
    status: str
    method: Optional[str] = None
    vpa: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
