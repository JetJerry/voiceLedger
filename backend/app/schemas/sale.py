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
    items: List[SaleItemCreate]
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    raw_voice_transcript: Optional[str] = None
    auto_create_payment_link: bool = True


class SaleResponse(BaseModel):
    id: str
    merchant_id: int
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
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
    name: str = Field(..., description="Item name — any product, any category (e.g. chai, notebook, hammer, shirt)")
    price: float = Field(default=0.0, description="Price per unit in INR")
    category: Optional[str] = Field(default="General", description="Free-form category (e.g. Snacks, Beverages, Stationery, Hardware)")
    description: Optional[str] = Field(default=None, description="Optional item description")
    unit: Optional[str] = Field(default=None, description="Unit of measure (e.g. kg, piece, plate, glass, packet)")


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    is_active: Optional[bool] = None


class ProductResponse(ProductBase):
    id: int
    merchant_id: int
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
