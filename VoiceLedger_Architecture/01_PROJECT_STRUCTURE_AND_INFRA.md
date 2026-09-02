# VoiceLedger — Project Structure and Infrastructure

## 1. Goal

Create a modular backend where payment-provider-specific code is isolated from the core ledger.

Recommended stack:

- Python 3.12+
- FastAPI
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- Redis
- Celery or an equivalent worker
- Pydantic
- WebSockets
- Docker
- Pytest

The frontend/device can be implemented separately.

## 2. Recommended repository

```text
voiceLedger/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── dependencies.py
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   ├── merchants.py
│   │   │   ├── payments.py
│   │   │   ├── devices.py
│   │   │   └── webhooks.py
│   │   ├── core/
│   │   │   ├── security.py
│   │   │   ├── exceptions.py
│   │   │   └── logging.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── repositories/
│   │   ├── services/
│   │   │   ├── payment_service.py
│   │   │   ├── merchant_service.py
│   │   │   ├── device_service.py
│   │   │   └── notification_service.py
│   │   ├── providers/
│   │   │   ├── base.py
│   │   │   └── razorpay/
│   │   │       ├── adapter.py
│   │   │       ├── client.py
│   │   │       ├── schemas.py
│   │   │       └── webhook.py
│   │   ├── realtime/
│   │   ├── workers/
│   │   └── db/
│   ├── tests/
│   ├── alembic/
│   ├── Dockerfile
│   └── requirements.txt
├── device/
├── frontend/
├── docs/
└── docker-compose.yml
```

## 3. Dependency direction

The core must not depend on Razorpay-specific implementation details.

```text
API
 |
 v
Application Services
 |
 +---- Provider Interface <---- Razorpay Adapter
 |
 +---- Repository Interface ---- PostgreSQL
 |
 +---- Event/Queue Interface ---- Redis
 |
 +---- Notification Interface ---- Device/Voice
```

The dependency direction prevents provider lock-in.

## 4. Environment variables

Example names:

```text
APP_ENV=
DATABASE_URL=
REDIS_URL=

JWT_SECRET=
JWT_ACCESS_TTL_MINUTES=
JWT_REFRESH_TTL_DAYS=

RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=

CORS_ALLOWED_ORIGINS=

LOG_LEVEL=
SENTRY_DSN=
```

Never commit actual values.

Provide `.env.example`, not `.env`.

## 5. Docker services

Development:

```text
api
worker
postgres
redis
```

Production should preferably use managed PostgreSQL/Redis where appropriate.

## 6. Infrastructure security

- Run containers as non-root where possible.
- Use minimal base images.
- Pin dependency versions.
- Scan dependencies regularly.
- Do not expose PostgreSQL/Redis publicly.
- Expose only required application ports.
- Use private networking for internal services.
- Apply resource limits.
- Keep backups enabled for production PostgreSQL.
- Test backup restoration.

## 7. Coding rules for Gemini

When implementing:
- Do not create provider-specific logic inside generic services.
- Do not place secrets in code.
- Use dependency injection.
- Use typed Pydantic schemas.
- Use database transactions around financial state changes.
- Add tests for every payment state transition.
- Never silently swallow webhook errors.
- Keep migrations version-controlled.
