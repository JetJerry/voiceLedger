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

logger = logging.getLogger("voiceledger.llm.openai")


class OpenAILLMProvider(BaseLLMProvider):
    name = "openai"

    def __init__(self):
        self.client = None
        if settings.OPENAI_API_KEY:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
                logger.info("[OpenAI] Initialized OpenAI LLM client successfully.")
            except Exception as exc:
                logger.warning("Could not initialize OpenAI client: %s", exc)

    @traceable(name="openai_extract_transaction", run_type="llm")
    def extract_transaction(
        self,
        text: str,
        catalog_items: Optional[List[str]] = None,
        merchant_profile: Optional[dict] = None,
        business_type: Optional[str] = None,
        context: str = "terminal",
    ) -> VoiceExtractionResult:
        if not self.client:
            raise RuntimeError("OpenAI client not configured (OPENAI_API_KEY missing)")

        prompt = build_extraction_prompt(text, catalog_items, merchant_profile, business_type, context)
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"},
                timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
            )
            response_text = self._strip_markdown_json(response.choices[0].message.content or "")
            data = json.loads(response_text)
            return self._parse_extraction_response(text, data)
        except Exception as exc:
            logger.warning("OpenAI extraction failed: %s", exc)
            raise

    @traceable(name="openai_answer_query", run_type="llm")
    def answer_query(self, query: str, context_data: Dict[str, Any]) -> str:
        if not self.client:
            raise RuntimeError("OpenAI client not configured")

        prompt = build_query_prompt(query, context_data)
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as exc:
            logger.warning("OpenAI answer generation failed: %s", exc)
            raise

    @traceable(name="openai_refine_for_speech", run_type="llm")
    def refine_for_speech(self, text: str, lang: str = "hi") -> str:
        if not self.client or not settings.TTS_USE_LLM_REFINEMENT:
            return text
        prompt = build_speech_refinement_prompt(text, lang)
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                timeout=10,
            )
            refined = (response.choices[0].message.content or "").strip()
            return refined if refined else text
        except Exception:
            return text
