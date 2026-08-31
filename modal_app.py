"""
VoiceLedger — Modal Serverless Backend Deployment Definition

Deploy command:
    modal deploy modal_app.py

Test locally in ephemeral dev mode:
    modal serve modal_app.py
"""

import os
from pathlib import Path
import modal

# 1. Initialize Modal App
app = modal.App("voiceledger-backend")

# 2. Persistent Volume for SQLite Database & Storage
data_volume = modal.Volume.from_name("voiceledger-data", create_if_missing=True)

# 3. Custom Container Image Definition
voiceledger_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ffmpeg", "git")
    .pip_install(
        "fastapi>=0.115.0",
        "uvicorn[standard]>=0.30.0",
        "pydantic>=2.8.0",
        "pydantic-settings>=2.4.0",
        "sqlalchemy>=2.0.30",
        "aiosqlite>=0.20.0",
        "psycopg2-binary>=2.9.9",
        "httpx>=0.27.0",
        "google-genai>=2.20.0",
        "python-dotenv>=1.0.1",
        "python-multipart>=0.0.9",
        "jinja2>=3.1.4",
        "nest-asyncio>=1.6.0",
        "edge-tts>=7.2.8",
        "gtts>=2.5.4",
        "openpyxl>=3.1.5",
        "faster-whisper>=1.0.0",
        "torch>=2.1.0",
        "requests>=2.31.0",
    )
    .add_local_dir("backend", remote_path="/root/backend")
    .add_local_dir("data", remote_path="/root/data")
)


# 4. Serverless ASGI FastAPI App Endpoint
@app.function(
    image=voiceledger_image,
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

    from backend.app.db.init_db import init_db
    from backend.app.main import app as web_app

    # Ensure database is initialized in the persistent volume / remote DB
    try:
        init_db()
    except Exception as e:
        print(f"[Modal] Startup database init notice: {e}")

    return web_app
