import io
from typing import Optional, List
from backend.app.config import settings
from backend.app.services.llm_service import llm_service
from backend.app.schemas.voice import VoiceExtractionResult


class VoiceService:
    def __init__(self):
        pass

    def process_text_input(self, text: str, catalog_items: Optional[List[str]] = None) -> VoiceExtractionResult:
        """
        Directly processes natural text query or browser WebSpeech transcribed text.
        """
        return llm_service.extract_transaction(text, catalog_items=catalog_items)

    def process_audio_bytes(self, audio_bytes: bytes, mime_type: str = "audio/webm", catalog_items: Optional[List[str]] = None) -> VoiceExtractionResult:
        """
        Processes raw audio bytes using Gemini multimodal audio model if available.
        """
        if llm_service.client:
            try:
                from google.genai import types
                prompt = """
You are VoiceLedger AI. Listen carefully to this merchant voice recording (Hindi / Hinglish / English).
Extract the merchant's sale details or intent and output ONLY valid JSON matching this schema:
{
  "intent": "record_sale" | "query_pending" | "query_status" | "query_daily" | "trigger_recovery" | "general_qa",
  "customer_name": "string or null",
  "customer_phone": "string or null",
  "items": [
    {
      "product_name": "string (lowercase item name, e.g. burger, pizza, chai)",
      "quantity": int (default 1),
      "unit_price": float or null
    }
  ],
  "payment_status": "pending" | "paid" | "partial",
  "raw_text": "verbatim transcription of what was spoken",
  "explanation": "Short friendly reply in Hinglish to the merchant"
}
"""
                response = llm_service.client.models.generate_content(
                    model=settings.LLM_MODEL,
                    contents=[
                        types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                        prompt
                    ]
                )
                response_text = response.text.strip()
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.startswith("```"):
                    response_text = response_text[3:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                
                import json
                from backend.app.schemas.voice import VoiceItemExtracted
                data = json.loads(response_text.strip())
                items = [
                    VoiceItemExtracted(
                        product_name=it.get("product_name", "").lower(),
                        quantity=int(it.get("quantity", 1)),
                        unit_price=float(it.get("unit_price")) if it.get("unit_price") is not None else None
                    )
                    for it in data.get("items", [])
                ]
                return VoiceExtractionResult(
                    intent=data.get("intent", "record_sale"),
                    customer_name=data.get("customer_name"),
                    customer_phone=data.get("customer_phone"),
                    items=items,
                    payment_status=data.get("payment_status", "pending"),
                    raw_text=data.get("raw_text", "Audio processed"),
                    explanation=data.get("explanation")
                )
            except Exception as e:
                print(f"Audio processing fallback error: {e}")

        # Fallback default if audio model not configured
        return VoiceExtractionResult(
            intent="record_sale",
            customer_name="Customer",
            items=[],
            payment_status="pending",
            raw_text="[Audio Recording]",
            explanation="Audio record ho gaya hai. Kripya browser WebSpeech use karein ya text likhein."
        )


voice_service = VoiceService()
