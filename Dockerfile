# ============================================================
# VoiceLedger Dockerfile
# ============================================================

FROM python:3.12-slim AS builder

WORKDIR /app

# Build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Install Python dependencies
COPY pyproject.toml uv.lock* ./

RUN uv sync --frozen --no-dev --no-install-project \
    || uv sync --no-dev --no-install-project


# ============================================================
# Runtime image
# ============================================================

FROM python:3.12-slim AS runner

WORKDIR /app

# Create non-root user
RUN groupadd --system voiceledger \
    && useradd --system --gid voiceledger voiceledger

# Copy virtual environment
COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Application source
COPY backend ./backend
COPY data ./data
COPY scripts/start.sh ./start.sh

# Safe environment template only
COPY .env.example ./.env.example

# Permissions
RUN chmod +x ./start.sh \
    && chown -R voiceledger:voiceledger /app

USER voiceledger

EXPOSE 8000

# Health check
HEALTHCHECK \
    --interval=30s \
    --timeout=5s \
    --start-period=15s \
    --retries=3 \
    CMD python -c "import urllib.request, os; port=os.environ.get('PORT', '8000'); urllib.request.urlopen(f'http://127.0.0.1:{port}/health')" \
    || exit 1

CMD ["./start.sh"]