import uuid
from datetime import datetime
import json
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class SaleItemBase(BaseModel):
    product_name: str
    quantity: int = 1
    unit_price: Optional[float] = None
    product_id: Optional[uuid.UUID] = None


class SaleItemCreate(SaleItemBase):
    pass


class SaleItemResponse(BaseModel):
    id: uuid.UUID
    product_id: Optional[uuid.UUID] = None
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
    merchant_id: uuid.UUID
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    total_amount: float
    received_amount: float
    outstanding_amount: float
    status: str
    payment_id: Optional[uuid.UUID] = None
    razorpay_order_id: Optional[str] = None
    razorpay_payment_link_id: Optional[str] = None
    razorpay_payment_link_url: Optional[str] = None
    raw_voice_transcript: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    items: List[SaleItemResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ProductBase(BaseModel):
    name: str = Field(..., description="Item name (e.g. chai, notebook, hammer, shirt, apple, paracetamol)")
    price: float = Field(default=0.0, description="Price per unit in INR")
    category: Optional[str] = Field(default="General", description="Product category")
    description: Optional[str] = Field(default=None, description="Item description")
    unit: Optional[str] = Field(default="piece", description="Unit of measure (e.g. kg, piece, packet, litre, box)")
    stock_quantity: int = Field(default=0, description="Current available inventory")
    track_inventory: bool = Field(default=False, description="Whether to track stock levels")
    attributes: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Dynamic key-value attributes")

    @field_validator("attributes", mode="before")
    @classmethod
    def parse_attributes_json(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return {}
        return v or {}


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    stock_quantity: Optional[int] = None
    track_inventory: Optional[bool] = None
    attributes: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

    @field_validator("attributes", mode="before")
    @classmethod
    def parse_attributes_json(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return {}
        return v


class ProductResponse(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID
    name: str
    price: float
    price_minor: int
    category: str
    description: Optional[str] = None
    unit: Optional[str] = "piece"
    stock_quantity: int = 0
    track_inventory: bool = False
    attributes: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class InventoryAdjustRequest(BaseModel):
    product_id: uuid.UUID
    delta: int = Field(..., description="Quantity to add (positive) or remove (negative)")
    reason: Optional[str] = Field(default="manual_adjustment", description="Reason for adjustment")


class InventoryAdjustResponse(BaseModel):
    product_id: uuid.UUID
    product_name: str
    previous_quantity: int
    new_quantity: int
    delta: int
    reason: str
