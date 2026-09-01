import json
import logging
from typing import Any, Dict, List, Optional
from langsmith import traceable

from backend.app.config import settings
from backend.app.schemas.voice import VoiceExtractionResult
from backend.app.services.llm.base import BaseLLMProvider
from backend.app.services.llm.prompts import (
    build_extraction_prompt,
    build_query_prompt,
    build_speech_refinement_prompt,
)

logger = logging.getLogger("voiceledger.llm.gemini")


class GeminiLLMProvider(BaseLLMProvider):
    name = "gemini"

    def __init__(self):
        self.client = None
        if settings.GEMINI_API_KEY:
            try:
                from google import genai
                self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
                logger.info("[Gemini] Initialized Gemini LLM client successfully.")
            except Exception as exc:
                logger.warning("Could not initialize Gemini client: %s", exc)

    @traceable(name="gemini_extract_transaction", run_type="llm")
    def extract_transaction(
        self,
        text: str,
        catalog_items: Optional[List[str]] = None,
        merchant_profile: Optional[dict] = None,
        business_type: Optional[str] = None,
        context: str = "terminal",
    ) -> VoiceExtractionResult:
        if not self.client:
            raise RuntimeError("Gemini client not configured (GEMINI_API_KEY missing)")

        prompt = build_extraction_prompt(text, catalog_items, merchant_profile, business_type, context)
        models_to_try = [
            settings.GEMINI_MODEL,
            "gemini-3.6-flash",
            "gemini-3.7-flash",
            "gemini-flash-latest",
        ]
        models_to_try = list(dict.fromkeys(m for m in models_to_try if m))

        last_err = None
        for model in models_to_try:
            try:
                response = self.client.models.generate_content(model=model, contents=prompt)
                response_text = self._strip_markdown_json(response.text)
                data = json.loads(response_text)
                return self._parse_extraction_response(text, data)
            except Exception as exc:
                last_err = exc
                logger.warning("Gemini model %s failed: %s, trying fallback...", model, exc)
                continue
        raise last_err or RuntimeError("All Gemini models failed")

    @traceable(name="gemini_answer_query", run_type="llm")
    def answer_query(self, query: str, context_data: Dict[str, Any]) -> str:
        if not self.client:
            raise RuntimeError("Gemini client not configured")

        prompt = build_query_prompt(query, context_data)
        models_to_try = [settings.GEMINI_MODEL, "gemini-3.6-flash", "gemini-3.7-flash", "gemini-flash-latest"]
        models_to_try = list(dict.fromkeys(m for m in models_to_try if m))
        for model in models_to_try:
            try:
                response = self.client.models.generate_content(model=model, contents=prompt)
                return response.text.strip()
            except Exception:
                continue
        raise RuntimeError("Gemini answer generation failed on all models")

    @traceable(name="gemini_refine_for_speech", run_type="llm")
    def refine_for_speech(self, text: str, lang: str = "hi") -> str:
        if not self.client or not settings.TTS_USE_LLM_REFINEMENT:
            return text
        prompt = build_speech_refinement_prompt(text, lang)
        models_to_try = [settings.GEMINI_MODEL, "gemini-3.6-flash", "gemini-3.7-flash", "gemini-flash-latest"]
        for model in models_to_try:
            try:
                response = self.client.models.generate_content(model=model, contents=prompt)
                refined = (response.text or "").strip()
                if refined:
                    return refined
            except Exception:
                continue
        return text

    @traceable(name="gemini_summarize_profile", run_type="llm")
    def summarize_profile(self, profile: Optional[dict]) -> Dict[str, Any]:
        if not self.client or not profile:
            return super().summarize_profile(profile)
        prompt = f"Summarize this merchant profile in JSON with modules array and summary string: {json.dumps(profile, default=str)}"
        try:
            response = self.client.models.generate_content(model=settings.GEMINI_MODEL, contents=prompt)
            txt = self._strip_markdown_json(response.text)
            return json.loads(txt)
        except Exception:
            return super().summarize_profile(profile)
