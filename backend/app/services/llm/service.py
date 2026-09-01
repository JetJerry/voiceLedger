import logging
from typing import Any, Dict, List, Optional
from langsmith import traceable

from backend.app.config import settings
from backend.app.schemas.voice import VoiceExtractionResult
from backend.app.services.llm.base import BaseLLMProvider
from backend.app.services.llm.groq_provider import GroqLLMProvider
from backend.app.services.llm.gemini_provider import GeminiLLMProvider
from backend.app.services.llm.openai_provider import OpenAILLMProvider

logger = logging.getLogger("voiceledger.llm.service")


class LLMService:
    """
    Pure AI Orchestrator with Multi-Provider Intelligent Fallback.
    Provider priority: Groq (primary ultra-fast LPU) -> Gemini (fallback) -> OpenAI.
    """

    def __init__(self):
        self.groq = GroqLLMProvider()
        self.gemini = GeminiLLMProvider()
        self.openai = OpenAILLMProvider()

    @property
    def client(self):
        """Active client handle for backward compatibility."""
        return self.groq.client or self.gemini.client or self.openai.client

    def _get_providers_in_priority(self) -> List[BaseLLMProvider]:
        configured = settings.LLM_PROVIDER.lower() if settings.LLM_PROVIDER else "groq"
        if configured == "gemini":
            return [self.gemini, self.groq, self.openai]
        elif configured == "openai":
            return [self.openai, self.groq, self.gemini]
        else:
            # Default: Groq primary, Gemini fallback
            return [self.groq, self.gemini, self.openai]

    @traceable(name="llm_service_extract_with_fallback", run_type="chain")
    def _extract_with_fallback(
        self,
        text: str,
        catalog_items: Optional[List[str]] = None,
        merchant_profile: Optional[dict] = None,
        business_type: Optional[str] = None,
        context: str = "terminal",
        history: Optional[List[Dict[str, str]]] = None,
    ) -> VoiceExtractionResult:
        errors = []
        for provider in self._get_providers_in_priority():
            if not getattr(provider, "client", None):
                continue
            try:
                result = provider.extract_transaction(
                    text, catalog_items, merchant_profile, business_type, context, history=history
                )
                logger.info("[AI Agent] Extraction succeeded via provider: %s", provider.name)
                return result
            except Exception as exc:
                errors.append(f"{provider.name}: {exc}")
                logger.warning("[AI Agent] Provider %s failed: %s", provider.name, exc)

        if not errors:
            return VoiceExtractionResult(
                intent="general_qa",
                raw_text=text,
                items=[],
                payment_status="pending",
                explanation="VoiceLedger AI Agent active. Kripya .env file me GROQ_API_KEY set karein.",
            )

        logger.error("[AI Agent] All LLM providers failed: %s", "; ".join(errors))
        return VoiceExtractionResult(
            intent="general_qa",
            raw_text=text,
            items=[],
            payment_status="pending",
            explanation="AI service temporarily unavailable. Kripya apna internet connection ya API key check karein.",
        )

    @traceable(name="llm_service_extract_transaction", run_type="chain")
    def extract_transaction(
        self,
        text: str,
        catalog_items: Optional[List[str]] = None,
        merchant_profile: Optional[dict] = None,
        business_type: Optional[str] = None,
        context: str = "terminal",
        history: Optional[List[Dict[str, str]]] = None,
    ) -> VoiceExtractionResult:
        text_clean = text.strip()
        if not text_clean:
            return VoiceExtractionResult(
                intent="unknown",
                raw_text=text,
                explanation="Koi aawaz ya text nahi mila. Kripya dobara bolein.",
            )

        result = self._extract_with_fallback(
            text_clean, catalog_items, merchant_profile, business_type, context, history=history
        )
        return self.validate_extraction(result, catalog_items or [])

    def validate_extraction(
        self, extraction: VoiceExtractionResult, catalog_items: List[str]
    ) -> VoiceExtractionResult:
        """
        Validates extraction result. In open catalog mode, permits dynamically recognized items.
        """
        return extraction

    @traceable(name="llm_service_answer_query", run_type="chain")
    def answer_query(self, query: str, context_data: Dict[str, Any]) -> str:
        for provider in self._get_providers_in_priority():
            if not getattr(provider, "client", None):
                continue
            try:
                return provider.answer_query(query, context_data)
            except Exception as exc:
                logger.warning("[AI Agent] Provider %s answer_query failed: %s", provider.name, exc)

        return "Abhi store ledger query ka jawab generate karne me samasya ho rahi hai."

    @traceable(name="llm_service_refine_for_speech", run_type="chain")
    def refine_for_speech(self, text: str, lang: str = "hi") -> str:
        for provider in self._get_providers_in_priority():
            if not getattr(provider, "client", None):
                continue
            try:
                return provider.refine_for_speech(text, lang)
            except Exception:
                continue
        return text

    @traceable(name="llm_service_summarize_profile", run_type="chain")
    def summarize_profile(self, profile: Optional[dict]) -> Dict[str, Any]:
        for provider in self._get_providers_in_priority():
            if not getattr(provider, "client", None):
                continue
            try:
                return provider.summarize_profile(profile)
            except Exception:
                continue

        if not profile:
            return {"modules": [], "summary": "Empty profile"}
        return {"modules": ["catalog", "pricing", "payments"], "summary": "Store profile active"}


llm_service = LLMService()
