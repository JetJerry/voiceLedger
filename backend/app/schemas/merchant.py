from datetime import datetime
from typing import Optional, Any, Dict
from pydantic import BaseModel, ConfigDict


class MerchantCreate(BaseModel):
    name: str
    currency: Optional[str] = "INR"


class MerchantResponse(BaseModel):
    id: int
    name: str
    currency: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MerchantProfileCreate(BaseModel):
    config: Dict[str, Any]


class MerchantProfileResponse(BaseModel):
    id: int
    merchant_id: int
    config: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
