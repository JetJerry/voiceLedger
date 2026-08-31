from typing import List, Optional
from pydantic import BaseModel, Field


class VoiceItemExtracted(BaseModel):
    product_name: str = Field(..., description="Recognized item name from speech — any item, any category")
    quantity: int = Field(default=1, description="Quantity ordered")
    unit_price: Optional[float] = Field(default=None, description="Spoken unit price if explicitly stated")
    category: Optional[str] = Field(default=None, description="Item category if mentioned (e.g. Snacks, Beverages, Stationery)")


class VoiceExtractionResult(BaseModel):
    intent: str = Field(
        default="record_sale",
        description="record_sale, add_to_catalog, check_payment_status, query_pending, query_daily, general_qa"
    )
    product_name: Optional[str] = Field(default=None, description="Product filter for payment status queries")
    sale_id: Optional[str] = Field(default=None, description="Sale ID if mentioned")
    customer_name: Optional[str] = Field(default=None, description="Optional customer reference if mentioned")
    items: List[VoiceItemExtracted] = Field(default_factory=list, description="Extracted sale items")
    payment_status: Optional[str] = Field(default="pending", description="pending, paid, partial")
    raw_text: str = Field(..., description="Original raw transcript")
    explanation: Optional[str] = Field(default=None, description="Agent's natural language reply in Hinglish/English")


class VoiceProcessRequest(BaseModel):
    text: str = Field(..., description="Transcribed merchant speech or typed text query")
    speak_response: bool = Field(default=True, description="Whether to generate TTS neural voice audio")
    voice_lang: str = Field(default="hi", description="hi (Hindi) or en (English)")


class VoiceProcessResponse(BaseModel):
    extraction: VoiceExtractionResult
    agent_reply: str
    audio_base64: Optional[str] = Field(default=None, description="Base64 Data URL MP3 for neural audio playback")
    sale: Optional[dict] = None
    action_taken: Optional[str] = None
