from typing import List, Optional
from pydantic import BaseModel, Field


class VoiceItemExtracted(BaseModel):
    product_name: str = Field(..., description="Recognized item name from speech, e.g. burger, pizza")
    quantity: int = Field(default=1, description="Quantity ordered")
    unit_price: Optional[float] = Field(default=None, description="Spoken unit price if explicitly stated")


class VoiceExtractionResult(BaseModel):
    intent: str = Field(
        default="record_sale",
        description="record_sale, query_pending, query_status, query_daily, trigger_recovery, general_qa"
    )
    customer_name: Optional[str] = Field(default=None, description="Customer name mentioned in speech")
    customer_phone: Optional[str] = Field(default=None, description="Customer phone if mentioned")
    items: List[VoiceItemExtracted] = Field(default_factory=list, description="Extracted sale items")
    payment_status: Optional[str] = Field(default="pending", description="pending, paid, partial")
    raw_text: str = Field(..., description="Original raw transcript")
    explanation: Optional[str] = Field(default=None, description="Agent's natural language reply in Hinglish/English")


class VoiceProcessRequest(BaseModel):
    text: str = Field(..., description="Transcribed merchant speech or typed text query")


class VoiceProcessResponse(BaseModel):
    extraction: VoiceExtractionResult
    agent_reply: str
    sale: Optional[dict] = None
    action_taken: Optional[str] = None
