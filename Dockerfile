# VoiceLedger — Production Dockerfile for Render & Cloud Deployments
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project || uv sync --no-dev --no-install-project

# ── Final Production Runner ──
FROM python:3.12-slim AS runner

WORKDIR /app

# Create non-root system user
RUN groupadd -r voiceledger && useradd -r -g voiceledger voiceledger

# Copy prebuilt virtual environment
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy application source code and resources
COPY backend ./backend
COPY data ./data
COPY scripts/start.sh ./start.sh
COPY .env.example ./.env.example

# Set executable permissions and ownership
RUN chmod +x ./start.sh && chown -R voiceledger:voiceledger /app

USER voiceledger

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, os; port = os.environ.get('PORT', 8000); urllib.request.urlopen(f'http://localhost:{port}/health')" || exit 1

CMD ["./start.sh"]
