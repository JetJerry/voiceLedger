from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class RazorpayWebhookPayload(BaseModel):
    entity: Optional[str] = None
    account_id: Optional[str] = None
    event: str
    contains: Optional[list] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[int] = None
