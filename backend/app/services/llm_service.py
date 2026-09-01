"""
Backward compatibility re-export module.
The LLM service has been modularized into `backend.app.services.llm/`.
"""

from backend.app.services.llm import (
    BaseLLMProvider,
    GroqLLMProvider,
    GeminiLLMProvider,
    OpenAILLMProvider,
    LLMService,
    llm_service,
    build_extraction_prompt,
    build_query_prompt,
    build_speech_refinement_prompt,
)

# Alias for backward compatibility
_build_extraction_prompt = build_extraction_prompt

__all__ = [
    "BaseLLMProvider",
    "GroqLLMProvider",
    "GeminiLLMProvider",
    "OpenAILLMProvider",
    "LLMService",
    "llm_service",
    "build_extraction_prompt",
    "_build_extraction_prompt",
    "build_query_prompt",
    "build_speech_refinement_prompt",
]
