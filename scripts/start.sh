#!/bin/sh
set -e

echo "==> VoiceLedger: Starting deployment initialization..."

# ============================================================
# 1. Database migrations
# ============================================================

echo "==> Running Alembic database migrations..."

alembic -c backend/alembic.ini upgrade head


# ============================================================
# 2. Optional worker
# ============================================================

RUN_WORKER="${RUN_WORKER:-false}"

if [ "$RUN_WORKER" = "true" ] || [ "$RUN_WORKER" = "1" ]; then
    echo "==> Starting VoiceLedger transactional outbox worker..."

    python -m backend.app.worker &

    WORKER_PID=$!

    echo "==> Outbox worker started (PID: ${WORKER_PID})"
fi


# ============================================================
# 3. FastAPI
# ============================================================

PORT="${PORT:-8000}"

echo "==> Starting FastAPI Uvicorn server on port ${PORT}..."

exec uvicorn backend.app.main:app \
    --host 0.0.0.0 \
    --port "${PORT}"