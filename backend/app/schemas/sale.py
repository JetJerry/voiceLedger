from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SaleItemBase(BaseModel):
    product_name: str
    quantity: int = 1
    unit_price: Optional[float] = None


class SaleItemCreate(SaleItemBase):
    pass


class SaleItemResponse(BaseModel):
    id: int
    product_id: Optional[int] = None
    product_name: str
    quantity: int
    unit_price: float
    subtotal: float

    model_config = ConfigDict(from_attributes=True)


class SaleCreate(BaseModel):
    customer_name: str
    customer_phone: Optional[str] = None
    items: List[SaleItemCreate]
    raw_voice_transcript: Optional[str] = None
    auto_create_payment_link: bool = True


class SaleResponse(BaseModel):
    id: str
    merchant_id: int
    customer_id: Optional[int] = None
    customer_name: str
    total_amount: float
    received_amount: float
    outstanding_amount: float
    status: str
    razorpay_payment_link_id: Optional[str] = None
    razorpay_payment_link_url: Optional[str] = None
    raw_voice_transcript: Optional[str] = None
    created_at: datetime
    items: List[SaleItemResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ProductBase(BaseModel):
    name: str
    price: float
    category: Optional[str] = "General"


class ProductCreate(ProductBase):
    pass


class ProductResponse(ProductBase):
    id: int
    merchant_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomerResponse(BaseModel):
    id: int
    name: str
    phone: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
