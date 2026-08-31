from datetime import datetime
from typing import Optional
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
