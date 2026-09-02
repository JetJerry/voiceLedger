import os
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "VoiceLedger"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"

    # Application Environment
    APP_ENV: str = "development"
    ENVIRONMENT: str = "development"  # Alias for backward compatibility
    DEBUG: bool = True

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s [%(levelname)s] %(name)s (request_id=%(request_id)s): %(message)s"

    # Database (PostgreSQL is the authoritative ledger database)
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/voiceledger"

    # Redis (For event queue, workers, and caching)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Authentication & Security
    JWT_SECRET: str = "voiceledger_jwt_signing_secret_dev_environment_key_2026_min_32"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TTL_MINUTES: int = 15
    JWT_REFRESH_TTL_DAYS: int = 7
    ARGON2_TIME_COST: int = 3
    ARGON2_MEMORY_COST_KIB: int = 65536  # 64 MiB
    ARGON2_PARALLELISM: int = 4

    # Razorpay Provider Credentials
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # Network & Server configuration
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    CORS_ALLOWED_ORIGINS: Union[List[str], str] = ["http://localhost:3000", "http://localhost:8000"]
    CORS_ORIGINS: List[str] = ["*"]  # Alias for backward compatibility

    # Legacy prototype fields preserved for compatibility
    DEFAULT_MERCHANT_NAME: str = "VoiceLedger Merchant"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.6-flash"
    OPENAI_API_KEY: str = ""
    LLM_PROVIDER: str = "mock"
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "voiceledger-agent"
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    WHISPER_MODEL_SIZE: str = "base"
    WHISPER_DEVICE: str = "auto"
    WHISPER_COMPUTE_TYPE: str = "float16"
    HF_TTS_MODEL: str = "facebook/mms-tts-hin"
    TTS_USE_LLM_REFINEMENT: bool = False
    TTS_PROVIDER: str = "edge"
    LLM_REQUEST_TIMEOUT_SECONDS: int = 30

    @field_validator("CORS_ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
