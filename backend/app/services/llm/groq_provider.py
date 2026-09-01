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

logger = logging.getLogger("voiceledger.llm.groq")


class GroqLLMProvider(BaseLLMProvider):
    name = "groq"

    def __init__(self):
        self.client = None
        if settings.GROQ_API_KEY:
            try:
                from groq import Groq
                self.client = Groq(api_key=settings.GROQ_API_KEY)
                logger.info("[Groq] Initialized Groq LLM client successfully.")
            except Exception as exc:
                logger.warning("Could not initialize Groq client: %s", exc)

    @traceable(name="groq_extract_transaction", run_type="llm")
    def extract_transaction(
        self,
        text: str,
        catalog_items: Optional[List[str]] = None,
        merchant_profile: Optional[dict] = None,
        business_type: Optional[str] = None,
        context: str = "terminal",
        history: Optional[List[Dict[str, str]]] = None,
    ) -> VoiceExtractionResult:
        if not self.client:
            raise RuntimeError("Groq client not configured (GROQ_API_KEY missing)")

        prompt = build_extraction_prompt(
            text, catalog_items, merchant_profile, business_type, context, history=history
        )
        models_to_try = [
            settings.GROQ_MODEL,
            "groq/compound-mini",
            "openai/gpt-oss-120b",
            "qwen/qwen3.8-27b",
            "llama-3.3-70b-versatile",
        ]
        models_to_try = list(dict.fromkeys(m for m in models_to_try if m))
        
        last_err = None
        for model in models_to_try:
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    response_format={"type": "json_object"},
                    timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
                )
                response_text = self._strip_markdown_json(response.choices[0].message.content or "")
                data = json.loads(response_text)
                return self._parse_extraction_response(text, data)
            except Exception as exc:
                last_err = exc
                logger.warning("Groq model %s failed: %s, trying fallback model...", model, exc)
                continue
        raise last_err or RuntimeError("All Groq models failed")

    @traceable(name="groq_answer_query", run_type="llm")
    def answer_query(self, query: str, context_data: Dict[str, Any]) -> str:
        if not self.client:
            raise RuntimeError("Groq client not configured")

        prompt = build_query_prompt(query, context_data)
        models_to_try = [settings.GROQ_MODEL, "groq/compound-mini", "openai/gpt-oss-120b", "qwen/qwen3.8-27b"]
        models_to_try = list(dict.fromkeys(m for m in models_to_try if m))
        for model in models_to_try:
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
                )
                return (response.choices[0].message.content or "").strip()
            except Exception:
                continue
        raise RuntimeError("Groq answer generation failed on all models")

    @traceable(name="groq_refine_for_speech", run_type="llm")
    def refine_for_speech(self, text: str, lang: str = "hi") -> str:
        if not self.client or not settings.TTS_USE_LLM_REFINEMENT:
            return text
        prompt = build_speech_refinement_prompt(text, lang)
        models_to_try = [settings.GROQ_MODEL, "groq/compound-mini", "openai/gpt-oss-120b"]
        for model in models_to_try:
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    timeout=10,
                )
                refined = (response.choices[0].message.content or "").strip()
                if refined:
                    return refined
            except Exception:
                continue
        return text

    @traceable(name="groq_summarize_profile", run_type="llm")
    def summarize_profile(self, profile: Optional[dict]) -> Dict[str, Any]:
        if not self.client or not profile:
            return super().summarize_profile(profile)
        prompt = f"Summarize this merchant profile in JSON with 'modules' array and 'summary' string: {json.dumps(profile, default=str)}"
        models_to_try = [settings.GROQ_MODEL, "groq/compound-mini", "openai/gpt-oss-120b"]
        for model in models_to_try:
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    response_format={"type": "json_object"},
                    timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
                )
                txt = self._strip_markdown_json(response.choices[0].message.content or "")
                return json.loads(txt)
            except Exception:
                continue
        return super().summarize_profile(profile)
