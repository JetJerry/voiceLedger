# VoiceLedger — Backend Dockerfile
FROM python:3.12-slim AS builder

WORKDIR /app

# Install system dependencies needed for compiling packages if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast, reliable package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project || uv sync --no-dev --no-install-project

# ── Final Runtime Image ──
FROM python:3.12-slim AS runner

WORKDIR /app

# Create a non-root system user for security
RUN groupadd -r voiceledger && useradd -r -g voiceledger voiceledger

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy application source code
COPY backend ./backend
COPY .env.example ./.env.example

# Set proper ownership to the non-root user
RUN chown -R voiceledger:voiceledger /app

USER voiceledger

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
