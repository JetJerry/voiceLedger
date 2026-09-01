import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.app.config import settings
from backend.app.db.init_db import init_db
from backend.app.api.voice import router as voice_router
from backend.app.api.sales import router as sales_router
from backend.app.api.payments import router as payments_router
from backend.app.api.webhooks import router as webhooks_router
from backend.app.api.recovery import router as recovery_router
from backend.app.api.dashboard import router as dashboard_router
from backend.app.api.admin import router as admin_router
from backend.app.api.auth import router as auth_router


logger = logging.getLogger("voiceledger")
logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(settings.LOG_FORMAT))
    logger.addHandler(handler)


from backend.app.agentic.llm_factory import setup_langsmith_tracing


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB & Seed Data on Startup
    try:
        init_db()
        logger.info("Database initialization completed")
    except Exception as e:
        logger.exception("Startup DB init error: %s", e)

    # Initialize LangSmith Observability
    setup_langsmith_tracing()
    logger.info(
        "[AI Agent] Started with Primary LLM: %s, LangSmith Tracing: %s (project: %s)",
        settings.LLM_PROVIDER,
        "ENABLED" if settings.LANGCHAIN_API_KEY else "DISABLED (set LANGCHAIN_API_KEY in .env)",
        settings.LANGCHAIN_PROJECT,
    )
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="VoiceLedger: AI Voice-First Payment Collection & Revenue Recovery Agent with Razorpay",
    lifespan=lifespan
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.perf_counter()
    try:
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            "%s %s -> %s in %.2fms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
    except Exception:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.exception("Unhandled request error for %s %s after %.2fms", request.method, request.url.path, duration_ms)
        raise


# CORS Middleware — configured to allow Vercel domains, localhost, and mobile apps
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=r"^https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(voice_router, prefix=settings.API_V1_STR)
app.include_router(sales_router, prefix=settings.API_V1_STR)
app.include_router(payments_router, prefix=settings.API_V1_STR)
app.include_router(webhooks_router, prefix=settings.API_V1_STR)
app.include_router(recovery_router, prefix=settings.API_V1_STR)
app.include_router(dashboard_router, prefix=settings.API_V1_STR)
app.include_router(admin_router, prefix=settings.API_V1_STR)
app.include_router(auth_router, prefix=settings.API_V1_STR)


@app.get("/api/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "llm_provider": settings.LLM_PROVIDER,
        "groq_configured": bool(settings.GROQ_API_KEY),
        "gemini_configured": bool(settings.GEMINI_API_KEY),
        "langsmith_tracing": bool(settings.LANGCHAIN_API_KEY),
        "langsmith_project": settings.LANGCHAIN_PROJECT,
        "razorpay_configured": bool(settings.RAZORPAY_KEY_ID),
        "huggingface_models": {
            "stt_model": f"openai/whisper-{settings.WHISPER_MODEL_SIZE}",
            "stt_device": settings.WHISPER_DEVICE,
            "stt_compute_type": settings.WHISPER_COMPUTE_TYPE,
            "tts_model": settings.HF_TTS_MODEL,
        }
    }


# Frontend Static Files Mount (for local monolithic runs)
frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
dist_dir = frontend_dir / "dist"

if dist_dir.exists() and (dist_dir / "index.html").exists():
    app.mount("/_expo", StaticFiles(directory=str(dist_dir / "_expo")), name="expo-static")
    if (dist_dir / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(dist_dir / "assets")), name="assets-static")
    
    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(dist_dir / "index.html")
else:
    @app.get("/", tags=["API Info"])
    def root():
        return {
            "service": "VoiceLedger AI Backend API",
            "version": settings.VERSION,
            "status": "online",
            "docs": "/docs",
            "health": "/api/health"
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=settings.PORT, reload=True)
