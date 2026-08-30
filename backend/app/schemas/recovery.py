from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RecoveryPriorityItem(BaseModel):
    sale_id: str
    customer_name: str
    customer_phone: Optional[str] = None
    expected_amount: float
    received_amount: float
    outstanding_amount: float
    days_overdue: int
    priority_score: float
    priority_level: str  # HIGH, MEDIUM, LOW
    recommended_action: str
    payment_link_url: Optional[str] = None
    created_at: datetime


class RecoveryTriggerRequest(BaseModel):
    sale_id: str
    action_type: str = Field(default="payment_link_resend", description="payment_link_resend, whatsapp_reminder")
    channel: str = Field(default="whatsapp", description="whatsapp, sms, in_app")
    custom_message: Optional[str] = None


class RecoveryActionResponse(BaseModel):
    id: int
    sale_id: str
    action_type: str
    status: str
    channel: str
    message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
