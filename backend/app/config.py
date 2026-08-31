import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    PROJECT_NAME: str = "VoiceLedger"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s %(levelname)s %(name)s %(message)s"

    # Database
    DATABASE_URL: str = "sqlite:///./voiceledger.db"

    # Razorpay API Credentials
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # AI / LLM Configuration (Groq primary, Gemini fallback)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    OPENAI_API_KEY: str = ""
    LLM_PROVIDER: str = "groq"  # groq, gemini, openai, or mock
    LLM_MODEL: str = "llama-3.3-70b-versatile"  # legacy alias; Groq uses GROQ_MODEL
    
    # HuggingFace Model Configuration (Optimized for 4GB GPU & High-Speed CPU)
    WHISPER_MODEL_SIZE: str = "base"        # base (~140MB, <100ms) or small (~460MB)
    WHISPER_DEVICE: str = "auto"            # auto, cuda, or cpu
    WHISPER_COMPUTE_TYPE: str = "float16"   # float16 (GPU), int8 (CPU)
    HF_TTS_MODEL: str = "facebook/mms-tts-hin"  # HuggingFace TTS model ID
    TTS_USE_LLM_REFINEMENT: bool = True     # Polish agent replies for natural speech via LLM
    TTS_PROVIDER: str = "edge"              # edge, hf, auto
    LLM_REQUEST_TIMEOUT_SECONDS: int = 30
    DEFAULT_MERCHANT_NAME: str = "VoiceLedger Merchant"

    # Server configuration (127.0.0.1 for local browser compatibility on Windows)
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    CORS_ORIGINS: List[str] = ["*"]


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
