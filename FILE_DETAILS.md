# VoiceLedger — Comprehensive Codebase & File Architecture Details

> **Complete inventory of every file in VoiceLedger, detailing its technical responsibility, system interconnections, and architectural necessity.**

---

## Table of Contents
1. [Architecture & System Flow Overview](#1-architecture--system-flow-overview)
2. [Project Root & Configuration](#2-project-root--configuration)
3. [Architecture Documentation (VoiceLedger_Architecture/)](#3-architecture-documentation)
4. [Database Models (backend/app/models/)](#4-database-models)
5. [Database Session & Infrastructure (backend/app/db/)](#5-database-session--infrastructure)
6. [Database Migrations (backend/alembic/)](#6-database-migrations)
7. [Core Security, Configuration & Runtime (backend/app/core/ & config)](#7-core-security-configuration--runtime)
8. [API Route Endpoints & WebSockets (backend/app/api/)](#8-api-route-endpoints--websockets)
9. [Core Business Logic & Services (backend/app/services/)](#9-core-business-logic--services)
10. [Payment & Voice Providers (backend/app/providers/)](#10-payment--voice-providers)
11. [Data Schemas & Validation (backend/app/schemas/)](#11-data-schemas--validation)
12. [Agentic & LLM System (backend/app/agentic/ & agents/)](#12-agentic--llm-system)
13. [Scripts, Tools & Standalone Utilities (backend/scripts/ & tools/)](#13-scripts-tools--standalone-utilities)
14. [Test Suite (backend/tests/)](#14-test-suite)
15. [Frontend Universal Application (frontend/)](#15-frontend-universal-application)
16. [Evaluation & Data (evaluation/ & data/)](#16-evaluation--data)

---

## 1. Architecture & System Flow Overview

VoiceLedger operates on a decoupled, multi-tier event-driven architecture designed to guarantee **absolute financial ledger integrity** while delivering **sub-second localized voice announcements** to merchant Soundbox hardware.

```text
Customer UPI Payment (PhonePe, GPay, Paytm)
                     ↓
         Razorpay Payment Gateway
                     ↓
  RFC HMAC-SHA256 Signature Verification
                     ↓
    HTTP Webhook Ingestion Boundary
                     ↓
   PaymentEvent Ingested (RECEIVED)
                     ↓
    Payment Core Transaction Boundary
  ┌─────────────────────────────────────┐
  │  Payment CAPTURED (Integer Paise)   │
  │                 +                   │
  │   OutboxEvent PENDING (Sanitized)   │
  └─────────────────────────────────────┘
                     ↓
        PostgreSQL Atomic COMMIT
                     ↓
  Transactional Outbox Worker (SKIP LOCKED)
                     ↓
       Redis Pub/Sub Event Transport
                     ↓
  VoiceNotificationService (TTS Synthesis)
                     ↓
       Soundbox WebSocket Gateway
                     ↓
   Physical Soundbox Audio Playback
                     ↓
         Hardware PLAYED ACK
                     ↓
     VoiceNotification DELIVERED
```

---

## 2. Project Root & Configuration

### [docker-compose.yml](file:///d:/razorpay/docker-compose.yml)
- **File Path**: `d:\razorpay\docker-compose.yml`
- **What it does**: Defines the multi-container orchestration for the complete VoiceLedger deployment: `api` (FastAPI backend), `worker` (outbox publisher), `postgres` (PostgreSQL 16 Alpine), and `redis` (Redis 7 Alpine). Sets up persistent volumes, healthchecks (`pg_isready`, `redis-cli ping`), and network bridge.
- **Connected Files**: [backend/Dockerfile](file:///d:/razorpay/backend/Dockerfile), [.env.example](file:///d:/razorpay/.env.example), [backend/app/worker.py](file:///d:/razorpay/backend/app/worker.py), [backend/app/main.py](file:///d:/razorpay/backend/app/main.py).
- **Why we need it**: Guarantees identical runtime environments for local development, automated testing, and Buildathon demo execution without dependency drift.

### [backend/Dockerfile](file:///d:/razorpay/backend/Dockerfile)
- **File Path**: `d:\razorpay\backend\Dockerfile`
- **What it does**: Multi-stage Docker build file. Uses Python 3.12 slim, installs dependencies using `uv`, creates an unprivileged `voiceledger` system user, copies code, and defines a lightweight Python `urllib` healthcheck probe.
- **Connected Files**: [pyproject.toml](file:///d:/razorpay/pyproject.toml), [uv.lock](file:///d:/razorpay/uv.lock), [docker-compose.yml](file:///d:/razorpay/docker-compose.yml).
- **Why we need it**: Containerizes the API and background worker processes securely with minimal image size and fast build caching.

### [pyproject.toml](file:///d:/razorpay/pyproject.toml)
- **File Path**: `d:\razorpay\pyproject.toml`
- **What it does**: Standard PEP 518/621 project configuration. Specifies Python dependencies (`fastapi`, `uvicorn`, `sqlalchemy`, `alembic`, `psycopg`, `redis`, `argon2-cffi`, `pyjwt`, `pydantic-settings`, `pytest`, `pytest-asyncio`), build system, and pytest test suite configuration.
- **Connected Files**: [uv.lock](file:///d:/razorpay/uv.lock), [requirements.txt](file:///d:/razorpay/requirements.txt).
- **Why we need it**: The central specification of all backend project dependencies, versions, and test tooling.

### [uv.lock](file:///d:/razorpay/uv.lock)
- **File Path**: `d:\razorpay\uv.lock`
- **What it does**: The deterministic lockfile generated by `uv`, pinning exact package versions and hashes.
- **Connected Files**: [pyproject.toml](file:///d:/razorpay/pyproject.toml).
- **Why we need it**: Prevents build failures and subtle bugs caused by dependency version drift across different machines.

### [requirements.txt](file:///d:/razorpay/requirements.txt)
- **File Path**: `d:\razorpay\requirements.txt`
- **What it does**: Legacy pip-compatible list of dependencies mirroring pyproject.toml.
- **Connected Files**: [pyproject.toml](file:///d:/razorpay/pyproject.toml).
- **Why we need it**: Backwards compatibility for environments or CI tools that do not use `uv`.

### [.env.example](file:///d:/razorpay/.env.example)
- **File Path**: `d:\razorpay\.env.example`
- **What it does**: Template providing placeholder values and documentation for all required environment variables (`DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, `APP_ENV`, `LOG_LEVEL`).
- **Connected Files**: [backend/app/config.py](file:///d:/razorpay/backend/app/config.py).
- **Why we need it**: Ensures new developers or evaluators can configure `.env` safely without accidentally committing secrets to Git.

### [.gitignore](file:///d:/razorpay/.gitignore)
- **File Path**: `d:\razorpay\.gitignore`
- **What it does**: Directs Git to ignore sensitive files (`.env`), Python caches (`__pycache__`, `.pytest_cache`, `.venv`), Node modules (`node_modules`), IDE artifacts, and database dumps.
- **Connected Files**: All tracked and untracked files in the repository.
- **Why we need it**: Protects secrets from being committed and keeps the repository clean.

### [.python-version](file:///d:/razorpay/.python-version)
- **File Path**: `d:\razorpay\.python-version`
- **What it does**: Pins the active Python version (`3.12`) for `uv` and pyenv.
- **Connected Files**: [pyproject.toml](file:///d:/razorpay/pyproject.toml).
- **Why we need it**: Ensures consistent runtime version selection across machines.

### [main.py](file:///d:/razorpay/main.py)
- **File Path**: `d:\razorpay\main.py`
- **What it does**: Root development server entrypoint. Imports `app` from `backend.app.main` and starts Uvicorn with reload options.
- **Connected Files**: [backend/app/main.py](file:///d:/razorpay/backend/app/main.py).
- **Why we need it**: Convenience runner for launching the API from the root directory during development.

### [README.md](file:///d:/razorpay/README.md)
- **File Path**: `d:\razorpay\README.md`
- **What it does**: Root documentation presenting VoiceLedger's mission, high-level features, system architecture diagram, and links to setup guides.
- **Connected Files**: [USER_SETUP_GUIDE.md](file:///d:/razorpay/USER_SETUP_GUIDE.md), [RENDER_DEPLOYMENT.md](file:///d:/razorpay/RENDER_DEPLOYMENT.md).
- **Why we need it**: The landing page for the repository and first document judges and developers see.

### [USER_SETUP_GUIDE.md](file:///d:/razorpay/USER_SETUP_GUIDE.md)
- **File Path**: `d:\razorpay\USER_SETUP_GUIDE.md`
- **What it does**: Comprehensive step-by-step installation, test execution, operations, and buildathon demo guide. Lists all 459 passing canonical tests and describes how to run the live demo.
- **Connected Files**: [backend/scripts/live_demo_smoke.py](file:///d:/razorpay/backend/scripts/live_demo_smoke.py), [backend/tests/](file:///d:/razorpay/backend/tests/).
- **Why we need it**: The primary operational playbook for onboarding and evaluating VoiceLedger.

### [RENDER_DEPLOYMENT.md](file:///d:/razorpay/RENDER_DEPLOYMENT.md)
- **File Path**: `d:\razorpay\RENDER_DEPLOYMENT.md`
- **What it does**: Production deployment runbook for Render.com covering Blueprint orchestration, PostgreSQL, Redis, Docker container environment, and Razorpay webhook integration.
- **Connected Files**: [render.yaml](file:///d:/razorpay/render.yaml), [Dockerfile](file:///d:/razorpay/Dockerfile), [scripts/start.sh](file:///d:/razorpay/scripts/start.sh).
- **Why we need it**: Explains cloud deployment topology and live smoke verification.

---

## 3. Architecture Documentation

Located in `VoiceLedger_Architecture/`. These files form the foundational blueprint that governed all design decisions from Phase 0 to Phase 10:

- **[00_SYSTEM_OVERVIEW.md](file:///d:/razorpay/VoiceLedger_Architecture/00_SYSTEM_OVERVIEW.md)**: Executive summary of VoiceLedger, core design philosophy, tier isolation, and high-level data flow.
- **[01_PROJECT_STRUCTURE_AND_INFRA.md](file:///d:/razorpay/VoiceLedger_Architecture/01_PROJECT_STRUCTURE_AND_INFRA.md)**: Directory layout, container boundaries, process model, and environment setup.
- **[02_DATA_MODEL_AND_DATABASE.md](file:///d:/razorpay/VoiceLedger_Architecture/02_DATA_MODEL_AND_DATABASE.md)**: PostgreSQL schema design, financial immutability rules, integer minor unit requirements, foreign keys, and indexes.
- **[03_RAZORPAY_INTEGRATION_AND_WEBHOOKS.md](file:///d:/razorpay/VoiceLedger_Architecture/03_RAZORPAY_INTEGRATION_AND_WEBHOOKS.md)**: Webhook security specification, raw HMAC-SHA256 signature verification, and deduplication logic.
- **[04_PAYMENT_CORE_AND_IDEMPOTENCY.md](file:///d:/razorpay/VoiceLedger_Architecture/04_PAYMENT_CORE_AND_IDEMPOTENCY.md)**: Transactional outbox pattern, state machine transitions, bounded retries, and reconciliation rules.
- **[05_AUTH_MERCHANT_AND_DEVICE_SECURITY.md](file:///d:/razorpay/VoiceLedger_Architecture/05_AUTH_MERCHANT_AND_DEVICE_SECURITY.md)**: Argon2id password hashing, JWT rotation, merchant tenant isolation, and Soundbox credential hashing.
- **[06_REALTIME_VOICE_DEVICE.md](file:///d:/razorpay/VoiceLedger_Architecture/06_REALTIME_VOICE_DEVICE.md)**: Soundbox WebSocket protocol, device sessions, heartbeats, audio serialization, and offline replay synchronization.
- **[07_SECURITY_THREAT_MODEL_AND_TESTING.md](file:///d:/razorpay/VoiceLedger_Architecture/07_SECURITY_THREAT_MODEL_AND_TESTING.md)**: STRIDE threat model, security boundaries, and automated test ladder specifications.
- **[08_IMPLEMENTATION_PLAN_FOR_GEMINI.md](file:///d:/razorpay/VoiceLedger_Architecture/08_IMPLEMENTATION_PLAN_FOR_GEMINI.md)**: Phased milestone roadmap followed sequentially during development.

---

## 4. Database Models

Located in `backend/app/models/`. All models inherit from SQLAlchemy `Base` and map strictly to PostgreSQL tables:

### [merchant.py](file:///d:/razorpay/backend/app/models/merchant.py)
- **Model**: `Merchant` (table: `merchants`)
- **What it does**: Stores the organization/store entity (ID, legal name, business type, status `ACTIVE`/`SUSPENDED`, currency `INR`, timestamps).
- **Connected Files**: Connected to [merchant_user.py](file:///d:/razorpay/backend/app/models/merchant_user.py), [device.py](file:///d:/razorpay/backend/app/models/device.py), [payment.py](file:///d:/razorpay/backend/app/models/payment.py), [provider_connection.py](file:///d:/razorpay/backend/app/models/provider_connection.py), [voice_notification.py](file:///d:/razorpay/backend/app/models/voice_notification.py).
- **Why we need it**: Fundamental tenant boundary. All transactions, devices, and notifications are scoped to a merchant ID.

### [user.py](file:///d:/razorpay/backend/app/models/user.py)
- **Model**: `User` (table: `users`)
- **What it does**: Stores human operator credentials (ID, email, Argon2id `password_hash`, full name, active status).
- **Connected Files**: Connected to [user_session.py](file:///d:/razorpay/backend/app/models/user_session.py), [merchant_user.py](file:///d:/razorpay/backend/app/models/merchant_user.py), [auth_service.py](file:///d:/razorpay/backend/app/services/auth_service.py).
- **Why we need it**: Enables merchant dashboard authentication and role-based staff management.

### [user_session.py](file:///d:/razorpay/backend/app/models/user_session.py)
- **Model**: `UserSession` (table: `user_sessions`)
- **What it does**: Tracks refresh token families and session validity. Stores SHA-256 `refresh_token_hash`, family ID, expiration, revoked status, and IP/User-Agent metadata.
- **Connected Files**: Connected to [user.py](file:///d:/razorpay/backend/app/models/user.py), [auth_service.py](file:///d:/razorpay/backend/app/services/auth_service.py).
- **Why we need it**: Protects against token theft via refresh token rotation and automatic family revocation upon replay detection.

### [merchant_user.py](file:///d:/razorpay/backend/app/models/merchant_user.py)
- **Model**: `MerchantUser` (table: `merchant_users`)
- **What it does**: Association table linking `User` and `Merchant` with RBAC roles (`OWNER`, `ADMIN`, `STAFF`).
- **Connected Files**: [merchant.py](file:///d:/razorpay/backend/app/models/merchant.py), [user.py](file:///d:/razorpay/backend/app/models/user.py), [tenant_service.py](file:///d:/razorpay/backend/app/services/tenant_service.py).
- **Why we need it**: Multi-tenant authorization. Ensures a user only accesses merchants they are authorized to manage with the correct role.

### [provider_connection.py](file:///d:/razorpay/backend/app/models/provider_connection.py)
- **Model**: `ProviderConnection` (table: `provider_connections`)
- **What it does**: Links a merchant to a payment gateway account (e.g. Razorpay `account_id` / `provider_account_reference`), storing status and configuration.
- **Connected Files**: [merchant.py](file:///d:/razorpay/backend/app/models/merchant.py), [webhook_ingestion_service.py](file:///d:/razorpay/backend/app/services/webhook_ingestion_service.py).
- **Why we need it**: Enables multi-merchant routing. Incoming webhooks use the `account_id` payload field to resolve the exact merchant tenant.

### [payment_event.py](file:///d:/razorpay/backend/app/models/payment_event.py)
- **Model**: `PaymentEvent` (table: `payment_events`)
- **What it does**: Level 1 webhook audit log. Stores raw webhook headers, raw JSON payload, `event_id`, `event_type`, `processing_status` (`RECEIVED`, `PROCESSED`, `DUPLICATE`, `FAILED`), and error details.
- **Connected Files**: [webhook_ingestion_service.py](file:///d:/razorpay/backend/app/services/webhook_ingestion_service.py), [payment_event_service.py](file:///d:/razorpay/backend/app/services/payment_event_service.py), [payment.py](file:///d:/razorpay/backend/app/models/payment.py).
- **Why we need it**: Complete non-repudiation and deduplication. Guaranteed audit trail of every provider webhook even if subsequent processing fails.

### [payment.py](file:///d:/razorpay/backend/app/models/payment.py)
- **Model**: `Payment` (table: `payments`)
- **What it does**: Authoritative canonical financial ledger record. Stores `merchant_id`, provider, `provider_payment_id`, `amount_minor` (BIGINT in paise), currency (`INR`), `status` (`CREATED`, `AUTHORIZED`, `CAPTURED`, `REFUNDED`, `FAILED`), payment method, and timestamps.
- **Connected Files**: [merchant.py](file:///d:/razorpay/backend/app/models/merchant.py), [payment_service.py](file:///d:/razorpay/backend/app/services/payment_service.py), [outbox_event.py](file:///d:/razorpay/backend/app/models/outbox_event.py), [voice_notification.py](file:///d:/razorpay/backend/app/models/voice_notification.py).
- **Why we need it**: The single financial source of truth. Float calculations are prohibited; all amounts are stored as exact minor integer units.

### [outbox_event.py](file:///d:/razorpay/backend/app/models/outbox_event.py)
- **Model**: `OutboxEvent` (table: `outbox_events`)
- **What it does**: Transactional outbox table. Stores `aggregate_type` (`PAYMENT`), `aggregate_id`, `event_type` (`payment.captured`), sanitized JSON `payload`, `status` (`PENDING`, `PROCESSING`, `PUBLISHED`, `FAILED`, `DEAD_LETTER`), retry count, worker lease expiration, and error details.
- **Connected Files**: [outbox_service.py](file:///d:/razorpay/backend/app/services/outbox_service.py), [outbox_worker.py](file:///d:/razorpay/backend/app/services/outbox_worker.py).
- **Why we need it**: Guarantees Dual-Write Consistency. PostgreSQL commits the payment and the outbox event in the same transaction; Redis failures never cause payment data loss.

### [device.py](file:///d:/razorpay/backend/app/models/device.py)
- **Model**: `Device` (table: `devices`)
- **What it does**: Represents physical Soundbox hardware. Stores `merchant_id`, `device_name`, `device_type` (`SOUNDBOX`), `secret_hash` (Argon2id/SHA-256), `status` (`ACTIVE`, `INACTIVE`, `REVOKED`), battery level, firmware version, and last heartbeat timestamp.
- **Connected Files**: [merchant.py](file:///d:/razorpay/backend/app/models/merchant.py), [device_session.py](file:///d:/razorpay/backend/app/models/device_session.py), [device_service.py](file:///d:/razorpay/backend/app/services/device_service.py), [voice_notification.py](file:///d:/razorpay/backend/app/models/voice_notification.py).
- **Why we need it**: Hardware management and ownership boundary. Prevents unauthorized devices from intercepting notifications.

### [device_session.py](file:///d:/razorpay/backend/app/models/device_session.py)
- **Model**: `DeviceSession` (table: `device_sessions`)
- **What it does**: Tracks active authenticated sessions for Soundboxes. Stores `device_id`, `token_hash` (SHA-256 of `devsess_...`), expiration, and revoked status.
- **Connected Files**: [device.py](file:///d:/razorpay/backend/app/models/device.py), [device_service.py](file:///d:/razorpay/backend/app/services/device_service.py), [websocket.py](file:///d:/razorpay/backend/app/api/v1/websocket.py).
- **Why we need it**: Stateless Soundbox authentication over persistent WebSocket connections without exposing long-lived device secrets.

### [voice_notification.py](file:///d:/razorpay/backend/app/models/voice_notification.py)
- **Model**: `VoiceNotification` (table: `voice_notifications`)
- **What it does**: Durable voice notification record. Stores `merchant_id`, `device_id`, `payment_id`, localized spoken `message`, `language` (`en-IN`, `hi-IN`), audio artifact metadata, `status` (`QUEUED`, `STREAMING`, `DELIVERED`, `FAILED`), attempts, delivered timestamp, and error details.
- **Connected Files**: [payment.py](file:///d:/razorpay/backend/app/models/payment.py), [device.py](file:///d:/razorpay/backend/app/models/device.py), [voice_notification_service.py](file:///d:/razorpay/backend/app/services/voice_notification_service.py), [websocket.py](file:///d:/razorpay/backend/app/api/v1/websocket.py).
- **Why we need it**: Durable offline queue and playback tracking. Allows offline devices to receive missed payments upon reconnecting and prevents duplicate audio playbacks.

### [audit_log.py](file:///d:/razorpay/backend/app/models/audit_log.py)
- **Model**: `AuditLog` (table: `audit_logs`)
- **What it does**: Immutable security audit trail tracking administrative actions, logins, device registrations, and critical configuration changes.
- **Connected Files**: [auth_service.py](file:///d:/razorpay/backend/app/services/auth_service.py), [device_service.py](file:///d:/razorpay/backend/app/services/device_service.py).
- **Why we need it**: Regulatory compliance and forensic auditing.

### [legacy.py](file:///d:/razorpay/backend/app/models/legacy.py)
- **Models**: `Sale`, `CatalogItem`, `KiranaProfile`
- **What it does**: Contains legacy prototype models from earlier hackathon explorations.
- **Connected Files**: Isolated from core financial tables.
- **Why we need it**: Preserved for backward compatibility with prototype voice-to-sale test cases.

---

## 5. Database Session & Infrastructure

Located in `backend/app/db/`:

### [session.py](file:///d:/razorpay/backend/app/db/session.py)
- **What it does**: Creates the SQLAlchemy engine with connection pooling (`pool_pre_ping=True`, `pool_size=10`), session maker (`SessionLocal`), and `get_db()` dependency generator for FastAPI endpoints.
- **Connected Files**: [backend/app/config.py](file:///d:/razorpay/backend/app/config.py), all API routes in [backend/app/api/](file:///d:/razorpay/backend/app/api/).
- **Why we need it**: Manages database connection lifecycles and transactions across requests.

### [base.py](file:///d:/razorpay/backend/app/db/base.py)
- **What it does**: Exports declarative `Base` and imports all models in one place so Alembic can discover metadata.
- **Connected Files**: [backend/alembic/env.py](file:///d:/razorpay/backend/alembic/env.py), all model files.
- **Why we need it**: Single import target for schema migrations.

### [init_db.py](file:///d:/razorpay/backend/app/db/init_db.py)
- **What it does**: Database seeding utility for initializing default test merchants and development data.
- **Connected Files**: [backend/app/db/session.py](file:///d:/razorpay/backend/app/db/session.py), [backend/app/models/](file:///d:/razorpay/backend/app/models/).
- **Why we need it**: Quickly bootstraps local databases with sample data.

---

## 6. Database Migrations

Located in `backend/alembic/`:

- **[alembic.ini](file:///d:/razorpay/backend/alembic.ini)**: Alembic CLI configuration specifying migration folder location and logging.
- **[env.py](file:///d:/razorpay/backend/alembic/env.py)**: Alembic environment script. Loads database URL dynamically from `settings.DATABASE_URL` and connects `target_metadata = Base.metadata`.
- **[script.py.mako](file:///d:/razorpay/backend/alembic/script.py.mako)**: Template for generating new revision scripts.
- **[0001_initial_schema.py](file:///d:/razorpay/backend/alembic/versions/0001_initial_schema.py)**: Initial migration creating core tables (`merchants`, `users`, `merchant_users`, `provider_connections`, `payment_events`, `payments`, `outbox_events`, `devices`, `device_sessions`, `voice_notifications`, `audit_logs`).
- **[0002_user_sessions.py](file:///d:/razorpay/backend/alembic/versions/0002_user_sessions.py)**: Adds `user_sessions` table with token hashing, expiration, and index constraints.

---

## 7. Core Security, Configuration & Runtime

Located in `backend/app/core/` and `backend/app/`:

### [config.py](file:///d:/razorpay/backend/app/config.py)
- **What it does**: Pydantic `Settings` class loading all environment variables with strong type validation, defaults, and a `validate_production_security()` hook that enforces strict key lengths in production.
- **Connected Files**: Used by virtually every file in the backend.
- **Why we need it**: Centralized, type-safe configuration management.

### [security.py](file:///d:/razorpay/backend/app/core/security.py)
- **What it does**: Core cryptography module. Provides Argon2id password hashing and verification (`hash_password`, `verify_password`), JWT issuance and validation (`create_access_token`, `decode_access_token`), and SHA-256 token hashing (`hash_token`).
- **Connected Files**: [auth_service.py](file:///d:/razorpay/backend/app/services/auth_service.py), [device_service.py](file:///d:/razorpay/backend/app/services/device_service.py), [deps.py](file:///d:/razorpay/backend/app/api/deps.py).
- **Why we need it**: Houses all cryptographic algorithms in one audited location, preventing weak algorithms (MD5/SHA1) or hardcoded keys.

### [redis.py](file:///d:/razorpay/backend/app/core/redis.py)
- **What it does**: Manages async Redis connection pool (`get_redis()`, `close_redis()`) with healthcheck pinging and graceful teardown.
- **Connected Files**: [main.py](file:///d:/razorpay/backend/app/main.py), [health.py](file:///d:/razorpay/backend/app/api/health.py), [websocket_manager.py](file:///d:/razorpay/backend/app/services/websocket_manager.py).
- **Why we need it**: Provides connection pooling for real-time pub/sub and distributed messaging.

### [logging.py](file:///d:/razorpay/backend/app/core/logging.py)
- **What it does**: Sets up structured logging with sensitive data filters (redacting passwords, tokens, and HMAC signatures) and attaches correlation request IDs.
- **Connected Files**: [main.py](file:///d:/razorpay/backend/app/main.py).
- **Why we need it**: Prevents credential leakage into log files.

### [main.py](file:///d:/razorpay/backend/app/main.py)
- **What it does**: FastAPI application factory. Registers routers (`/api/v1/auth`, `/api/v1/merchants`, `/api/v1/webhooks`, `/api/v1/devices`, `/ws`), attaches request ID and exception-handling middlewares, and sets up lifespan handlers (Redis connection and shutdown).
- **Connected Files**: Connects all API routers, middleware, and database engines.
- **Why we need it**: The central HTTP/WebSocket application entrypoint.

### [worker.py](file:///d:/razorpay/backend/app/worker.py)
- **What it does**: Standalone entrypoint for the background Outbox Worker process. Initializes database session, Redis publisher, and starts the asynchronous polling loop.
- **Connected Files**: [outbox_worker.py](file:///d:/razorpay/backend/app/services/outbox_worker.py), [docker-compose.yml](file:///d:/razorpay/docker-compose.yml).
- **Why we need it**: Runs the outbox worker as an isolated daemon process separate from the API server.

---

## 8. API Route Endpoints & WebSockets

Located in `backend/app/api/`:

### Canonical API v1:
- **[backend/app/api/v1/auth.py](file:///d:/razorpay/backend/app/api/v1/auth.py)**: Merchant operator authentication (`POST /register`, `POST /login`, `POST /refresh`, `POST /logout`, `GET /me`).
- **[backend/app/api/v1/merchants.py](file:///d:/razorpay/backend/app/api/v1/merchants.py)**: Merchant management and multi-tenant context resolution.
- **[backend/app/api/v1/webhooks.py](file:///d:/razorpay/backend/app/api/v1/webhooks.py)**: Razorpay webhook ingestion boundary (`POST /api/v1/webhooks/razorpay`). Enforces raw byte HMAC-SHA256 signature verification and passes valid events to `webhook_ingestion_service`.
- **[backend/app/api/v1/devices.py](file:///d:/razorpay/backend/app/api/v1/devices.py)**: Soundbox device management (`POST /devices` registration, `GET /devices` listing, `POST /devices/{id}/authenticate` session issuance, `POST /devices/{id}/heartbeat` telemetry).
- **[backend/app/api/v1/websocket.py](file:///d:/razorpay/backend/app/api/v1/websocket.py)**:
  - `/ws/merchant`: Authenticated merchant dashboard WebSocket gateway.
  - `/ws/device`: Authenticated Soundbox device WebSocket gateway. Enforces device session tokens, delivers base64 audio notifications, handles offline replay upon connect, and processes hardware `PLAYED` ACKs.

### Utility & Legacy Endpoints:
- **[backend/app/api/health.py](file:///d:/razorpay/backend/app/api/health.py)**: Health check endpoint (`GET /health` and `GET /api/health`). Validates PostgreSQL connectivity (`SELECT 1`) and Redis connectivity (`PING`).
- **[backend/app/api/deps.py](file:///d:/razorpay/backend/app/api/deps.py)**: FastAPI dependency injectors (`get_current_user`, `get_current_merchant`, `get_db`, `require_role`).
- **[backend/app/api/admin.py](file:///d:/razorpay/backend/app/api/admin.py)**, **[dashboard.py](file:///d:/razorpay/backend/app/api/dashboard.py)**, **[payments.py](file:///d:/razorpay/backend/app/api/payments.py)**, **[sales.py](file:///d:/razorpay/backend/app/api/sales.py)**, **[voice.py](file:///d:/razorpay/backend/app/api/voice.py)**, **[recovery.py](file:///d:/razorpay/backend/app/api/recovery.py)**: Supporting endpoints for merchant operations and catalog querying.

---

## 9. Core Business Logic & Services

Located in `backend/app/services/`:

### [payment_service.py](file:///d:/razorpay/backend/app/services/payment_service.py)
- **What it does**: Authoritative financial state machine. Enforces state transitions (`CREATED` $\rightarrow$ `AUTHORIZED` $\rightarrow$ `CAPTURED` $\rightarrow$ `REFUNDED`), prevents invalid transitions, and enforces integer paise amounts.
- **Connected Files**: [payment.py](file:///d:/razorpay/backend/app/models/payment.py), [outbox_service.py](file:///d:/razorpay/backend/app/services/outbox_service.py).
- **Why we need it**: Guarantees that only valid, legal financial state transitions can ever be committed to the database.

### [payment_event_service.py](file:///d:/razorpay/backend/app/services/payment_event_service.py)
- **What it does**: Bridges ingested webhook events to the payment core. Extracts provider IDs, handles duplicate event idempotency, invokes `payment_service`, and links `Payment` to `PaymentEvent`.
- **Connected Files**: [payment_event.py](file:///d:/razorpay/backend/app/models/payment_event.py), [payment_service.py](file:///d:/razorpay/backend/app/services/payment_service.py).
- **Why we need it**: Level 2 idempotency and safe transactional linking between raw provider events and canonical records.

### [webhook_ingestion_service.py](file:///d:/razorpay/backend/app/services/webhook_ingestion_service.py)
- **What it does**: Level 1 ingestion handler. Validates provider signatures, looks up merchant via `ProviderConnection.provider_account_reference`, deduplicates by `event_id`, and stores raw `PaymentEvent`.
- **Connected Files**: [webhooks.py](file:///d:/razorpay/backend/app/api/v1/webhooks.py), [payment_event.py](file:///d:/razorpay/backend/app/models/payment_event.py), [provider_connection.py](file:///d:/razorpay/backend/app/models/provider_connection.py).
- **Why we need it**: Ensures webhooks are safely persisted and verified before any complex business processing takes place.

### [outbox_service.py](file:///d:/razorpay/backend/app/services/outbox_service.py)
- **What it does**: Creates sanitized `OutboxEvent` records inside the active financial database transaction, stripping secrets, signatures, and internal tokens.
- **Connected Files**: [outbox_event.py](file:///d:/razorpay/backend/app/models/outbox_event.py), [payment_service.py](file:///d:/razorpay/backend/app/services/payment_service.py).
- **Why we need it**: Ensures events emitted to the outside world are clean and transactionally atomic with payment commits.

### [outbox_worker.py](file:///d:/razorpay/backend/app/services/outbox_worker.py)
- **What it does**: Background outbox polling worker. Uses PostgreSQL row locking (`FOR UPDATE SKIP LOCKED`) to claim pending outbox events across multiple worker instances, publishes them to Redis, handles bounded exponential backoff on network failure, and reclaims stuck leases.
- **Connected Files**: [outbox_event.py](file:///d:/razorpay/backend/app/models/outbox_event.py), [redis_publisher.py](file:///d:/razorpay/backend/app/services/redis_publisher.py), [worker.py](file:///d:/razorpay/backend/app/worker.py).
- **Why we need it**: Asynchronously bridges durable PostgreSQL events to Redis Pub/Sub without blocking the HTTP request thread.

### [redis_publisher.py](file:///d:/razorpay/backend/app/services/redis_publisher.py)
- **What it does**: Publishes canonical events to merchant-scoped Redis channels (`voiceledger:merchant:{merchant_id}:events`).
- **Connected Files**: [outbox_worker.py](file:///d:/razorpay/backend/app/services/outbox_worker.py), [websocket_manager.py](file:///d:/razorpay/backend/app/services/websocket_manager.py).
- **Why we need it**: Decouples event publishing from event consumption with strict tenant isolation.

### [websocket_manager.py](file:///d:/razorpay/backend/app/services/websocket_manager.py)
- **What it does**: In-memory connection manager for WebSocket clients. Maintains active client registries, subscribes to Redis channels on-demand when merchants have active connections, and fans out events.
- **Connected Files**: [websocket.py](file:///d:/razorpay/backend/app/api/v1/websocket.py), [redis_publisher.py](file:///d:/razorpay/backend/app/services/redis_publisher.py).
- **Why we need it**: Manages WebSocket lifecycles and real-time event forwarding.

### [device_service.py](file:///d:/razorpay/backend/app/services/device_service.py)
- **What it does**: Handles Soundbox registration (generating one-time secrets), device authentication (verifying secret and creating `devsess_...` session tokens), heartbeat telemetry updates, and session validation.
- **Connected Files**: [device.py](file:///d:/razorpay/backend/app/models/device.py), [device_session.py](file:///d:/razorpay/backend/app/models/device_session.py), [devices.py](file:///d:/razorpay/backend/app/api/v1/devices.py).
- **Why we need it**: Enforces device hardware security, secret hashing, and session issuance.

### [voice_formatter.py](file:///d:/razorpay/backend/app/services/voice_formatter.py)
- **What it does**: Deterministically converts financial minor units (paise) and event types into natural spoken phrases in English and Hindi (e.g. `15000` paise $\rightarrow$ `"One hundred fifty rupees received"`, `"एक सौ पचास रुपये प्राप्त हुए"`). Handles paise edge cases and refunds.
- **Connected Files**: [voice_notification_service.py](file:///d:/razorpay/backend/app/services/voice_notification_service.py).
- **Why we need it**: Eliminates floating-point inaccuracies and ensures natural, culturally accurate voice phrasing.

### [voice_notification_service.py](file:///d:/razorpay/backend/app/services/voice_notification_service.py)
- **What it does**: Coordinates the entire voice pipeline: filters notifiable events, generates phrases via `voice_formatter`, synthesizes audio via `TTSProvider`, caches WAV artifacts, persists `VoiceNotification` records, dispatches audio over `/ws/device`, and manages offline replay synchronization upon device reconnection.
- **Connected Files**: [voice_notification.py](file:///d:/razorpay/backend/app/models/voice_notification.py), [websocket.py](file:///d:/razorpay/backend/app/api/v1/websocket.py), [tts/base.py](file:///d:/razorpay/backend/app/providers/tts/base.py).
- **Why we need it**: Decouples audio synthesis and delivery from the financial ledger, ensuring TTS or playback errors never mutate financial transactions.

### [auth_service.py](file:///d:/razorpay/backend/app/services/auth_service.py)
- **What it does**: Implements user registration, password verification, access token generation, and refresh token family tracking.
- **Connected Files**: [user.py](file:///d:/razorpay/backend/app/models/user.py), [user_session.py](file:///d:/razorpay/backend/app/models/user_session.py), [security.py](file:///d:/razorpay/backend/app/core/security.py).
- **Why we need it**: Handles secure user authentication workflows.

### [tenant_service.py](file:///d:/razorpay/backend/app/services/tenant_service.py)
- **What it does**: Validates and resolves merchant organizational boundaries and user permissions.
- **Connected Files**: [merchant_user.py](file:///d:/razorpay/backend/app/models/merchant_user.py), [deps.py](file:///d:/razorpay/backend/app/api/deps.py).
- **Why we need it**: Prevents cross-tenant data leaks and unauthorized multi-merchant access.

### [reconciliation_service.py](file:///d:/razorpay/backend/app/services/reconciliation_service.py)
- **What it does**: Audits and cross-references `PaymentEvent`, `Payment`, and `OutboxEvent` records to detect missing outbox dispatches or stuck states.
- **Connected Files**: [payment.py](file:///d:/razorpay/backend/app/models/payment.py), [outbox_event.py](file:///d:/razorpay/backend/app/models/outbox_event.py).
- **Why we need it**: Financial auditability and automated ledger recovery.

### Supporting Services:
- **[analytics_service.py](file:///d:/razorpay/backend/app/services/analytics_service.py)**: Merchant sales analytics and metrics aggregation.
- **[sales_service.py](file:///d:/razorpay/backend/app/services/sales_service.py)**: Catalog order and cart checkout logic.
- **[voice_service.py](file:///d:/razorpay/backend/app/services/voice_service.py)** & **[hf_stt_service.py](file:///d:/razorpay/backend/app/services/hf_stt_service.py)**: Speech-to-text processing for merchant voice commands.
- **[tts_service.py](file:///d:/razorpay/backend/app/services/tts_service.py)**: Text-to-speech audio synthesis helper.
- **[recovery_service.py](file:///d:/razorpay/backend/app/services/recovery_service.py)**: Automatic state recovery procedures.
- **[business_presets.py](file:///d:/razorpay/backend/app/services/business_presets.py)**: Industry-specific catalogs (Kirana, Chai Stall, Bakery).

---

## 10. Payment & Voice Providers

Located in `backend/app/providers/`:

### Razorpay Integration:
- **[backend/app/providers/base.py](file:///d:/razorpay/backend/app/providers/base.py)**: Abstract base class `PaymentProvider` defining the contract for payment providers.
- **[backend/app/providers/razorpay/adapter.py](file:///d:/razorpay/backend/app/providers/razorpay/adapter.py)**: Concrete adapter translating Razorpay-specific webhook structures and payloads into normalized canonical objects (`NormalizedPayment`, `NormalizedEvent`).
- **[backend/app/providers/razorpay/webhook.py](file:///d:/razorpay/backend/app/providers/razorpay/webhook.py)**: Cryptographic signature verifier executing constant-time HMAC-SHA256 comparison against raw request bytes.
- **[backend/app/providers/razorpay/client.py](file:///d:/razorpay/backend/app/providers/razorpay/client.py)**: HTTP client for interacting with Razorpay REST APIs (Payment Links, Orders).
- **[backend/app/providers/schemas.py](file:///d:/razorpay/backend/app/providers/schemas.py)** & **[exceptions.py](file:///d:/razorpay/backend/app/providers/exceptions.py)**: Normalized provider data transfer objects and exception hierarchies.

### TTS (Text-to-Speech) Integration:
- **[backend/app/providers/tts/base.py](file:///d:/razorpay/backend/app/providers/tts/base.py)**: Abstract base class `TTSProvider` and `AudioResult` container (bytes, content-type, duration).
- **[backend/app/providers/tts/mock.py](file:///d:/razorpay/backend/app/providers/tts/mock.py)**: High-speed, deterministic mock TTS provider that produces real, valid 16-bit PCM WAV audio headers and sine-wave bytes without relying on external cloud APIs or API keys. Used for reliable unit testing and offline demo execution.

---

## 11. Data Schemas & Validation

Located in `backend/app/schemas/`. Pydantic models for request validation and response serialization:

- **[auth.py](file:///d:/razorpay/backend/app/schemas/auth.py)**: Login, registration, token refresh, and user profile schemas.
- **[merchant.py](file:///d:/razorpay/backend/app/schemas/merchant.py)**: Merchant creation, profile update, and membership schemas.
- **[device.py](file:///d:/razorpay/backend/app/schemas/device.py)**: Device registration request/response, session tokens, and heartbeat telemetry schemas.
- **[payment.py](file:///d:/razorpay/backend/app/schemas/payment.py)**: Canonical payment responses, status queries, and payment link requests.
- **[webhook.py](file:///d:/razorpay/backend/app/schemas/webhook.py)**: Webhook ingestion responses and normalized event representations.
- **[voice.py](file:///d:/razorpay/backend/app/schemas/voice.py)**: Voice notification status, audio metadata, and playback ACK payloads.
- **[admin.py](file:///d:/razorpay/backend/app/schemas/admin.py)**, **[dashboard.py](file:///d:/razorpay/backend/app/schemas/dashboard.py)**, **[sale.py](file:///d:/razorpay/backend/app/schemas/sale.py)**, **[recovery.py](file:///d:/razorpay/backend/app/schemas/recovery.py)**: Supporting schemas for admin operations and sales reporting.

---

## 12. Agentic & LLM System

Located in `backend/app/agentic/` and `backend/app/agents/`. Implements merchant voice-to-sale conversational processing:

- **[graph.py](file:///d:/razorpay/backend/app/agentic/graph.py)**: LangGraph state graph orchestrating conversational flow from merchant speech to payment link generation.
- **[state.py](file:///d:/razorpay/backend/app/agentic/state.py)**: TypedDict defining conversational state (cart items, detected quantities, merchant context).
- **[nodes.py](file:///d:/razorpay/backend/app/agentic/nodes.py)**: Graph nodes executing speech parsing, item matching, and price calculations.
- **[tools.py](file:///d:/razorpay/backend/app/agentic/tools.py)**: Catalog lookup tools and payment link generator bindings.
- **[llm_factory.py](file:///d:/razorpay/backend/app/agentic/llm_factory.py)**: Factory providing multi-provider LLM failover (Groq, Gemini, OpenAI).
- **[merchant_agent.py](file:///d:/razorpay/backend/app/agents/merchant_agent.py)**: Merchant assistant coordinating catalog actions and voice queries.
- **[llm/](file:///d:/razorpay/backend/app/services/llm/)**: Specific provider drivers (`gemini_provider.py`, `groq_provider.py`, `openai_provider.py`) and prompt templates (`prompts.py`).

---

## 13. Scripts, Tools & Standalone Utilities

Located in `backend/scripts/` and `backend/tools/`:

### [backend/scripts/live_demo_smoke.py](file:///d:/razorpay/backend/scripts/live_demo_smoke.py)
- **What it does**: Standalone automated live smoke test script. Performs the full end-to-end flow against live PostgreSQL and Redis instances:
  1. API health probe verification.
  2. Test merchant & Soundbox device onboarding and session authentication.
  3. Online payment announcement flow: Webhook $\rightarrow$ Payment CAPTURED $\rightarrow$ Outbox Worker $\rightarrow$ Redis $\rightarrow$ Voice synthesis $\rightarrow$ WebSocket delivery $\rightarrow$ PLAYED ACK $\rightarrow$ DELIVERED.
  4. Offline payment queuing & replay sync: Device disconnected $\rightarrow$ Webhook processed $\rightarrow$ Notification QUEUED in PostgreSQL $\rightarrow$ Device reconnects $\rightarrow$ Replayed audio received $\rightarrow$ PLAYED ACK $\rightarrow$ DELIVERED.
  5. Webhook deduplication idempotency.
  6. Automatic cleanup of test records.
- **Connected Files**: [main.py](file:///d:/razorpay/backend/app/main.py), [session.py](file:///d:/razorpay/backend/app/db/session.py), all services and models.
- **Why we need it**: Provides judges and developers an instant, one-command live verification of the entire system without manual dashboard clicking.

### [backend/tools/manage_profiles.py](file:///d:/razorpay/backend/tools/manage_profiles.py)
- **What it does**: CLI utility to inspect, create, or switch merchant business profiles and sample catalogs.
- **Connected Files**: [session.py](file:///d:/razorpay/backend/app/db/session.py), [merchant.py](file:///d:/razorpay/backend/app/models/merchant.py).
- **Why we need it**: Operational utility for configuring demo stores.

### [backend/mcp_server.py](file:///d:/razorpay/backend/mcp_server.py)
- **What it does**: Model Context Protocol (MCP) server exposing VoiceLedger operational tools to external AI coding agents.
- **Connected Files**: [backend/app/](file:///d:/razorpay/backend/app/).
- **Why we need it**: Enables seamless agentic pair-programming and automated auditing.

---

## 14. Test Suite

Located in `backend/tests/`. **459 canonical tests passing with 100% success (0 regressions, 0 failures)**:

| Test File | Covered Functionality |
| :--- | :--- |
| **[test_phase0_foundation.py](file:///d:/razorpay/backend/tests/test_phase0_foundation.py)** | Health endpoints (`/health`, `/api/health`), database & Redis failure handling, request ID middleware, log sanitization. |
| **[test_phase1_1_models.py](file:///d:/razorpay/backend/tests/test_phase1_1_models.py)** | Merchant and User entity constraints, UUID generation, timestamps. |
| **[test_phase1_2_financial_models.py](file:///d:/razorpay/backend/tests/test_phase1_2_financial_models.py)** | Financial models (`Payment`, `PaymentEvent`), BIGINT minor unit rules, status enums. |
| **[test_phase1_3_device_models.py](file:///d:/razorpay/backend/tests/test_phase1_3_device_models.py)** | Device and DeviceSession models, hashed credentials, heartbeat columns. |
| **[test_phase1_4_notification_audit_outbox.py](file:///d:/razorpay/backend/tests/test_phase1_4_notification_audit_outbox.py)** | `VoiceNotification`, `OutboxEvent`, and `AuditLog` schemas and relationships. |
| **[test_phase1_5_migration_integrity.py](file:///d:/razorpay/backend/tests/test_phase1_5_migration_integrity.py)** | Validates that live PostgreSQL schema matches canonical SQLAlchemy models with zero drift. |
| **[test_phase2_1_password_security.py](file:///d:/razorpay/backend/tests/test_phase2_1_password_security.py)** | Argon2id password hashing, entropy, and constant-time verification. |
| **[test_phase2_2_registration_and_login.py](file:///d:/razorpay/backend/tests/test_phase2_2_registration_and_login.py)** | Merchant registration, login flow, credential rejection, error sanitization. |
| **[test_phase2_3_tokens_and_sessions.py](file:///d:/razorpay/backend/tests/test_phase2_3_tokens_and_sessions.py)** | Access token expiration, refresh token rotation, session revocation. |
| **[test_phase2_4_merchant_rbac_and_tenancy.py](file:///d:/razorpay/backend/tests/test_phase2_4_merchant_rbac_and_tenancy.py)** | Multi-tenant RBAC (`OWNER`, `ADMIN`, `STAFF`), cross-merchant query blocking. |
| **[test_phase2_5_security_hardening.py](file:///d:/razorpay/backend/tests/test_phase2_5_security_hardening.py)** | Tampered JWTs, algorithm confusion attacks, timing attack protection, IDOR prevention. |
| **[test_phase3_1_provider_abstraction.py](file:///d:/razorpay/backend/tests/test_phase3_1_provider_abstraction.py)** | PaymentProvider base abstraction and interface isolation. |
| **[test_phase3_2_razorpay_adapter.py](file:///d:/razorpay/backend/tests/test_phase3_2_razorpay_adapter.py)** | Razorpay event normalization and status mapping. |
| **[test_phase3_3_razorpay_webhook_verification.py](file:///d:/razorpay/backend/tests/test_phase3_3_razorpay_webhook_verification.py)** | HMAC-SHA256 signature verification over raw request bytes. |
| **[test_phase3_4_webhook_ingestion_and_deduplication.py](file:///d:/razorpay/backend/tests/test_phase3_4_webhook_ingestion_and_deduplication.py)** | Duplicate webhook deduplication idempotency and tenant routing. |
| **[test_phase3_5_integration_verification.py](file:///d:/razorpay/backend/tests/test_phase3_5_integration_verification.py)** | Provider boundary integration checks. |
| **[test_phase4_1_payment_core.py](file:///d:/razorpay/backend/tests/test_phase4_1_payment_core.py)** | Canonical Payment state machine and ledger immutability. |
| **[test_phase4_2_payment_event_processing.py](file:///d:/razorpay/backend/tests/test_phase4_2_payment_event_processing.py)** | Sequential event processing and payment linking. |
| **[test_phase4_3_transactional_outbox.py](file:///d:/razorpay/backend/tests/test_phase4_3_transactional_outbox.py)** | Outbox event creation, transaction atomicity, payload sanitization. |
| **[test_phase4_4_outbox_worker.py](file:///d:/razorpay/backend/tests/test_phase4_4_outbox_worker.py)** | `FOR UPDATE SKIP LOCKED` worker batching, Redis dispatch, bounded backoff, lease recovery. |
| **[test_phase4_5_end_to_end.py](file:///d:/razorpay/backend/tests/test_phase4_5_end_to_end.py)** | Full E2E Webhook $\rightarrow$ Payment $\rightarrow$ Outbox $\rightarrow$ Redis pipeline. |
| **[test_phase5_1_websocket_gateway.py](file:///d:/razorpay/backend/tests/test_phase5_1_websocket_gateway.py)** | Merchant WebSocket gateway (`/ws/merchant`), JWT auth, tenant channel routing. |
| **[test_phase6_1_device_management.py](file:///d:/razorpay/backend/tests/test_phase6_1_device_management.py)** | Soundbox device registration, hashed secrets, session tokens, heartbeats. |
| **[test_phase6_2_device_websocket.py](file:///d:/razorpay/backend/tests/test_phase6_2_device_websocket.py)** | Soundbox WebSocket bridge (`/ws/device`), session token authentication, multi-device delivery. |
| **[test_phase7_1_voice_notification.py](file:///d:/razorpay/backend/tests/test_phase7_1_voice_notification.py)** | Deterministic phrase formatting (English & Hindi), minor unit parsing, TTS failure isolation. |
| **[test_phase7_2_audio_playback.py](file:///d:/razorpay/backend/tests/test_phase7_2_audio_playback.py)** | Soundbox audio streaming, base64 payload delivery, playback ACK lifecycle (`PLAYED` $\rightarrow$ `DELIVERED`). |
| **[test_phase8_1_offline_replay.py](file:///d:/razorpay/backend/tests/test_phase8_1_offline_replay.py)** | Offline queuing in PostgreSQL, deterministic oldest-first replay upon device reconnect. |
| **[test_phase9_1_end_to_end_release.py](file:///d:/razorpay/backend/tests/test_phase9_1_end_to_end_release.py)** | Full release verification: online flow, offline flow, disconnect resilience, cross-tenant/device isolation, zero secret leakage. |
| **[test_pre_phase4_cleanup.py](file:///d:/razorpay/backend/tests/test_pre_phase4_cleanup.py)** | Verifies unmounting of legacy prototype endpoints. |
| Supporting test files | Catalog, analytics, recovery, dynamic sales, and agent tests. |

---

## 15. Frontend Universal Application

Located in `frontend/`. Universal React Native (Expo) app targeting Web, Android, and iOS:

- **[package.json](file:///d:/razorpay/frontend/package.json)** & **[package-lock.json](file:///d:/razorpay/frontend/package-lock.json)**: Frontend dependency tree (`react-native`, `expo`, `axios`).
- **[app.json](file:///d:/razorpay/frontend/app.json)**: Expo project metadata, icons, splash screens, and bundle identifiers.
- **[app.js](file:///d:/razorpay/frontend/app.js)** & **[index.js](file:///d:/razorpay/frontend/index.js)**: Root application mounting component.
- **[babel.config.js](file:///d:/razorpay/frontend/babel.config.js)**: Babel compiler presets for React Native Web.
- **[src/config/api.js](file:///d:/razorpay/frontend/src/config/api.js)**: API baseUrl and WebSocket URL configuration.
- **[src/services/apiService.js](file:///d:/razorpay/frontend/src/services/apiService.js)**: Axios HTTP client wrapper with automatic bearer token attachment.
- **[src/services/voiceService.js](file:///d:/razorpay/frontend/src/services/voiceService.js)**: Client-side voice recording and WebSocket audio listener.
- **[src/theme/colors.js](file:///d:/razorpay/frontend/src/theme/colors.js)**: Curated UI color palette.
- **[src/components/Header.js](file:///d:/razorpay/frontend/src/components/Header.js)**: Navigation header bar.
- **[src/components/LoginScreen.js](file:///d:/razorpay/frontend/src/components/LoginScreen.js)**: Merchant login and session acquisition form.
- **[src/components/SalesLedger.js](file:///d:/razorpay/frontend/src/components/SalesLedger.js)**: Real-time sales transactions table.
- **[src/components/SaleItemRow.js](file:///d:/razorpay/frontend/src/components/SaleItemRow.js)**: Individual sale row component.
- **[src/components/MetricsGrid.js](file:///d:/razorpay/frontend/src/components/MetricsGrid.js)**: Dashboard revenue, sales volume, and payment metrics tiles.
- **[src/components/VoiceAssistantCard.js](file:///d:/razorpay/frontend/src/components/VoiceAssistantCard.js)**: Interactive microphone recording card for spoken voice sales.
- **[src/components/PaymentSimModal.js](file:///d:/razorpay/frontend/src/components/PaymentSimModal.js)**: In-app QR code customer payment simulator.
- **[src/components/CatalogManager.js](file:///d:/razorpay/frontend/src/components/CatalogManager.js)**: Inventory and catalog management UI.
- **[src/components/AdminDashboard.js](file:///d:/razorpay/frontend/src/components/AdminDashboard.js)**: Administrative metrics and controls.

---

## 16. Evaluation & Data

- **[data/default_catalog.json](file:///d:/razorpay/data/default_catalog.json)**: Seed dataset containing default Kirana store items (chai, samosa, milk, bread, rice, sugar) with prices in minor paise.
- **[evaluation/dataset.json](file:///d:/razorpay/evaluation/dataset.json)**: Benchmark dataset of multimodal merchant voice inputs in Hindi, Hinglish, and English.
- **[evaluation/dataset_generator.py](file:///d:/razorpay/evaluation/dataset_generator.py)**: Synthesizer for generating test audio samples with varying accents and background noise.
- **[evaluation/evaluate.py](file:///d:/razorpay/evaluation/evaluate.py)**: Benchmarking script measuring intent extraction accuracy and pricing precision.

---

## 17. Cloud Deployment & Container Orchestration

- **[render.yaml](file:///d:/razorpay/render.yaml)**: Infrastructure-as-Code Render Blueprint specification. Provisions PostgreSQL 16, Key-Value (Redis), and Docker Web Service with automatic branch binding (`feature/connection`), health checks (`/health`), and dynamic secret generation.
- **[RENDER_DEPLOYMENT.md](file:///d:/razorpay/RENDER_DEPLOYMENT.md)**: Exhaustive deployment runbook with step-by-step instructions for 1-click Blueprint or manual Render dashboard setup, environment variable configurations, live Razorpay webhook registration, and Soundbox hardware connectivity.
- **[Dockerfile](file:///d:/razorpay/Dockerfile)**: Multi-stage, production-grade root Docker container build using `astral-sh/uv` fast dependency synchronization, non-root user permissions, and container health checking.
- **[scripts/start.sh](file:///d:/razorpay/scripts/start.sh)**: Cloud container boot script executing automatic Alembic database schema migrations, launching the transactional outbox worker in the background (`RUN_WORKER=true`), and binding Uvicorn to Render's dynamic `$PORT`.

