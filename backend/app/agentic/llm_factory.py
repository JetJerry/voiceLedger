import os
import logging
from typing import Optional
from backend.app.config import settings

logger = logging.getLogger("voiceledger.langgraph.llm")


def setup_langsmith_tracing():
    """
    Configures LangSmith tracing environment variables for deep observability.
    """
    if settings.LANGCHAIN_API_KEY:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
        os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT or "voiceledger-agent"
        os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT or "https://api.smith.langchain.com"
        logger.info("[LangSmith] Observability tracing enabled for project: %s", os.environ["LANGCHAIN_PROJECT"])
    else:
        # If no key is set, keep local tracking without failure
        os.environ["LANGCHAIN_TRACING_V2"] = "false"


setup_langsmith_tracing()


def get_langchain_llm(temperature: float = 0.1):
    """
    Returns a configured LangChain Chat Model based on settings with auto-fallback.
    """
    # 1. Try Groq (Ultra-fast inference)
    if settings.GROQ_API_KEY:
        try:
            from langchain_groq import ChatGroq
            return ChatGroq(
                groq_api_key=settings.GROQ_API_KEY,
                model_name=settings.GROQ_MODEL or "llama-3.3-70b-versatile",
                temperature=temperature,
                timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
            )
        except Exception as e:
            logger.warning("Could not initialize ChatGroq: %s", e)

    # 2. Try Google Gemini
    if settings.GEMINI_API_KEY:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                google_api_key=settings.GEMINI_API_KEY,
                model=settings.GEMINI_MODEL or "gemini-2.5-flash",
                temperature=temperature,
                timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
            )
        except Exception as e:
            logger.warning("Could not initialize ChatGoogleGenerativeAI: %s", e)

    # 3. Try OpenAI
    if settings.OPENAI_API_KEY:
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                api_key=settings.OPENAI_API_KEY,
                model="gpt-4o-mini",
                temperature=temperature,
                timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
            )
        except Exception as e:
            logger.warning("Could not initialize ChatOpenAI: %s", e)

    return None
