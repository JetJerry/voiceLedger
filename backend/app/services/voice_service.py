"""
Voice Service — Orchestrates Speech-to-Text processing.

STT Provider Cascade:
1. PRIMARY:   HuggingFace faster-whisper (openai/whisper-small, local model)
2. FALLBACK:  Google Gemini multimodal audio (cloud API)
"""
import io
from typing import Optional, List
from backend.app.config import settings
from backend.app.services.llm_service import llm_service
from backend.app.schemas.voice import VoiceExtractionResult


class VoiceService:
    def __init__(self):
        self._hf_stt = None
        self._hf_available = None  # None = not checked yet

    def _get_hf_stt(self):
        """Lazy-load the HuggingFace STT service."""
        if self._hf_available is None:
            try:
                from backend.app.services.hf_stt_service import hf_stt_service
                self._hf_stt = hf_stt_service
                self._hf_available = True
                print("[Voice] HuggingFace Whisper STT available as primary STT.")
            except Exception as e:
                print(f"[Voice] HuggingFace STT not available, will use Gemini: {e}")
                self._hf_available = False
        return self._hf_stt if self._hf_available else None

    def process_text_input(self, text: str, catalog_items: Optional[List[str]] = None) -> VoiceExtractionResult:
        """
        Directly processes natural text query or browser WebSpeech transcribed text.
        """
        return llm_service.extract_transaction(text, catalog_items=catalog_items)

    def process_audio_bytes(self, audio_bytes: bytes, mime_type: str = "audio/webm", catalog_items: Optional[List[str]] = None) -> VoiceExtractionResult:
        """
        Processes raw audio bytes using HuggingFace Whisper STT (primary)
        or Gemini multimodal (fallback).
        
        STT cascade: faster-whisper → Gemini multimodal → default fallback
        """
        # 1. PRIMARY: HuggingFace faster-whisper (local Whisper model)
        hf_stt = self._get_hf_stt()
        if hf_stt:
            try:
                transcribed_text, lang_prob, detected_lang = hf_stt.transcribe_audio_bytes(
                    audio_bytes, mime_type=mime_type, language="hi"
                )
                
                if transcribed_text and transcribed_text.strip():
                    print(f"[Voice] Whisper STT transcription: '{transcribed_text}' "
                          f"(lang={detected_lang}, prob={lang_prob:.2f})")
                    
                    # Forward transcribed text to LLM for intent extraction
                    return llm_service.extract_transaction(
                        transcribed_text, catalog_items=catalog_items
                    )
                else:
                    print("[Voice] Whisper STT returned empty transcription, trying Gemini...")
            except Exception as e:
                print(f"[Voice] Whisper STT failed, falling back to Gemini: {e}")

        # 2. FALLBACK: Gemini multimodal audio processing
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
                    items=items,
                    payment_status=data.get("payment_status", "pending"),
                    raw_text=data.get("raw_text", "Audio processed"),
                    explanation=data.get("explanation")
                )
            except Exception as e:
                print(f"[Voice] Gemini audio processing also failed: {e}")

        # 3. Default fallback if nothing worked
        return VoiceExtractionResult(
            intent="record_sale",
            customer_name="Customer",
            items=[],
            payment_status="pending",
            raw_text="[Audio Recording]",
            explanation="Audio record ho gaya hai. Kripya browser WebSpeech use karein ya text likhein."
        )


voice_service = VoiceService()
