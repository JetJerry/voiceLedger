#!/bin/sh
set -e

echo "==> VoiceLedger: Starting deployment initialization..."

# 1. Run database migrations to ensure PostgreSQL schema is current
echo "==> Running Alembic database migrations..."
alembic -c backend/alembic.ini upgrade head

# 2. Start the Uvicorn web server listening on Railway's dynamic PORT
PORT="${PORT:-8000}"
echo "==> Starting FastAPI Uvicorn server on port ${PORT}..."
exec uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT}"
