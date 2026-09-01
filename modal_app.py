"""
VoiceLedger — Modal Serverless Backend Deployment Definition

Deploy command:
    modal deploy modal_app.py

Test locally in ephemeral dev mode:
    modal serve modal_app.py
"""

import os
import tempfile
from pathlib import Path
import modal

# 1. Initialize Modal App
app = modal.App("voiceledger-backend")

# 2. Persistent Volume for SQLite Database & Storage
data_volume = modal.Volume.from_name("voiceledger-data", create_if_missing=True)

# 3. CPU Image — Full FastAPI app (API routes, LLM calls via remote APIs, TTS, webhooks)
cpu_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ffmpeg", "git")
    .pip_install(
        # ── Web Framework ──
        "fastapi>=0.115.0",
        "uvicorn[standard]>=0.30.0",
        "pydantic>=2.8.0",
        "pydantic-settings>=2.4.0",
        "python-dotenv>=1.0.1",
        "python-multipart>=0.0.9",
        "jinja2>=3.1.4",
        "nest-asyncio>=1.6.0",
        # ── Database ──
        "sqlalchemy>=2.0.30",
        "aiosqlite>=0.20.0",
        "psycopg2-binary>=2.9.9",
        # ── LLM Providers (remote API calls — no GPU needed) ──
        "groq>=0.18.0",
        "google-genai>=2.20.0",
        "openai>=1.30.0",
        # ── LangGraph Agentic Framework ──
        "langgraph>=0.2.0",
        "langchain-core>=0.3.0",
        "langchain-groq>=0.2.0",
        "langchain-google-genai>=2.0.0",
        "langchain-openai>=0.2.0",
        "langsmith>=0.1.0",
        # ── Text-to-Speech (Edge-TTS is cloud API, gTTS is cloud API) ──
        "edge-tts>=7.2.8",
        "gtts>=2.5.4",
        # ── HTTP & Utilities ──
        "httpx>=0.27.0",
        "requests>=2.31.0",
        "openpyxl>=3.1.5",
        "scipy>=1.12.0",
        "soundfile>=0.12.0",
    )
    .add_local_python_source("backend")
    .add_local_dir("data", remote_path="/root/data")
)

# 4. GPU Image — Whisper STT (local model inference, benefits from GPU)
gpu_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ffmpeg")
    .pip_install(
        "faster-whisper>=1.0.0",
        "torch>=2.1.0",
    )
)


# ── GPU Function: Whisper STT Inference ───────────────────────────────
@app.function(
    image=gpu_image,
    gpu="T4",
    timeout=60,
    scaledown_window=60,
)
def transcribe_audio(audio_bytes: bytes, model_size: str = "base") -> dict:
    """
    GPU-accelerated Whisper STT inference.
    Called by the CPU FastAPI app when audio is uploaded.
    """
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device="cuda", compute_type="float16")

    # Write audio bytes to a temp file for faster-whisper
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name

    try:
        segments, info = model.transcribe(tmp_path, language="hi")
        text = " ".join(seg.text for seg in segments).strip()
    finally:
        os.unlink(tmp_path)

    return {
        "text": text,
        "language": info.language,
        "language_probability": info.language_probability,
    }


# ── CPU Function: Full FastAPI App ────────────────────────────────────
@app.function(
    image=cpu_image,
    volumes={"/data": data_volume},
    secrets=[
        modal.Secret.from_name("voice_ledger"),
    ],
    timeout=300,
    scaledown_window=120,
)
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def fastapi_app():
    import sys
    sys.path.insert(0, "/root")

    # Default to persistent volume SQLite if DATABASE_URL not supplied in secret
    if not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = "sqlite:////data/voiceledger.db"

    if not os.environ.get("ENVIRONMENT"):
        os.environ["ENVIRONMENT"] = "production"

    print(f"[Modal] Starting VoiceLedger with DB: {os.environ.get('DATABASE_URL')}")
    print(f"[Modal] LLM Provider: {os.environ.get('LLM_PROVIDER', 'groq')} (Groq primary, Gemini fallback)")
    print(f"[Modal] LangSmith Tracing: {'ENABLED' if os.environ.get('LANGCHAIN_API_KEY') else 'DISABLED'}")

    from backend.app.db.init_db import init_db
    from backend.app.main import app as web_app
    from fastapi import UploadFile, File

    # Ensure database is initialized in the persistent volume / remote DB
    try:
        init_db()
    except Exception as e:
        print(f"[Modal] Startup database init notice: {e}")

    # ── GPU-proxied STT endpoint ──
    @web_app.post("/api/stt/transcribe", tags=["Speech-to-Text (GPU)"])
    async def stt_transcribe(file: UploadFile = File(...)):
        """
        Transcribes uploaded audio using GPU-accelerated Whisper.
        Audio → GPU Function (faster-whisper) → Hindi/English text.
        """
        audio_bytes = await file.read()
        result = transcribe_audio.remote(audio_bytes)
        return result

    return web_app
