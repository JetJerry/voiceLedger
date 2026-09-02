# VoiceLedger — Comprehensive User & Developer Guide

Welcome to **VoiceLedger**! This guide covers everything implemented in the platform: infrastructure setup, database architecture, Alembic migrations, environment configuration, running the services, and testing.

---

## Table of Contents
1. [Platform Architecture & Principles](#1-platform-architecture--principles)
2. [Prerequisites & System Requirements](#2-prerequisites--system-requirements)
3. [Infrastructure Setup (Docker, PostgreSQL & Redis)](#3-infrastructure-setup-docker-postgresql--redis)
4. [Environment Configuration (.env)](#4-environment-configuration-env)
5. [Database Migrations (Alembic)](#5-database-migrations-alembic)
6. [Canonical Data Model & Schema Reference](#6-canonical-data-model--schema-reference)
7. [Running the Application](#7-running-the-application)
8. [Health Checks & Observability](#8-health-checks--observability)
9. [Automated Testing & Verification](#9-automated-testing--verification)
10. [Frontend Setup (Web & Universal Mobile)](#10-frontend-setup-web--universal-mobile)
11. [Merchant & Device Operations Guide](#11-merchant--device-operations-guide)

---

## 1. Platform Architecture & Principles

VoiceLedger is an enterprise-grade, merchant-focused payment event and voice notification platform designed for the Razorpay ecosystem. It bridges online payment events directly to physical merchant soundboxes and mobile terminals with guaranteed financial accuracy and low latency.

### Core Architectural Invariants:
* **PostgreSQL is Authoritative**: PostgreSQL 16 is the single authoritative source of truth for the financial ledger, device registry, and audit trail. SQLite is **never** used as an application or database fallback.
* **Minor Unit Financial Math**: All monetary amounts are strictly stored and computed as integers in minor currency units (`amount_minor BIGINT` — e.g. 100 paise = ₹1.00). Floating-point monetary columns are strictly prohibited.
* **Multi-Level Idempotency**:
  * **Level 1 (Event Idempotency)**: Enforced via `UNIQUE(provider, event_id)` on `payment_events`. Webhook retries are deduplicated before processing.
  * **Level 2 (Payment Idempotency)**: Enforced via `UNIQUE(provider, provider_payment_id)` on `payments`. The same provider transaction can never be recorded twice.
* **Output-Only Soundbox Terminals**: Physical soundbox devices are strictly announcement endpoints. Devices **never** act as the source of truth for payment status, amounts, or authorization.
* **Zero Plaintext Secrets**: Passwords use salted cryptographic hashes (Argon2 / bcrypt); device tokens and session tokens are stored as SHA-256 digests (`device_token_hash`, `session_token_hash`). Sensitive keys are automatically rejected from audit metadata.
* **Transactional Outbox Pattern**: Downstream events (voice dispatch, webhooks, soundbox announcements) are written atomically to `outbox_events` in the same database transaction as financial records to guarantee at-least-once delivery with zero phantom notifications.

---

## 2. Prerequisites & System Requirements

Before running VoiceLedger, ensure the following tools are installed on your host machine:

| Requirement | Recommended Version | Purpose |
|---|---|---|
| **Python** | 3.10, 3.11, or 3.12 | Backend runtime |
| **uv** (or pip) | Latest (`>=0.4.0`) | Blazing fast Python package and environment manager |
| **Docker & Docker Compose** | Docker Desktop 4+ / Engine 24+ | Hosts PostgreSQL 16 and Redis services |
| **Node.js & npm** | Node 18+ & npm 9+ | Frontend (React Native Web & Expo) |

---

## 3. Infrastructure Setup (Docker, PostgreSQL & Redis)

VoiceLedger uses Docker Compose to run its core infrastructure services:
- **PostgreSQL 16**: Port `5432` (`voiceledger-postgres`)
- **Redis 7**: Port `6379` (`voiceledger-redis`)

### Start the Infrastructure:
From the project root directory, run:
```bash
# Start PostgreSQL and Redis in the background
docker compose up -d

# Verify both containers are healthy
docker compose ps
```

You should see:
```text
NAME                  IMAGE                STATUS                    PORTS
voiceledger-postgres  postgres:16-alpine   Up (healthy)              0.0.0.0:5432->5432/tcp
voiceledger-redis     redis:7-alpine       Up (healthy)              0.0.0.0:6379->6379/tcp
```

---

## 4. Environment Configuration (.env)

Configure your `.env` file in the project root directory:

```bash
# If .env does not exist, copy from example
cp .env.example .env
```

### Essential Configuration Keys:

```ini
# Application
PROJECT_NAME=VoiceLedger
ENVIRONMENT=development
DEBUG=True
HOST=0.0.0.0
PORT=8000

# Authoritative Database (PostgreSQL 16)
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/voiceledger

# Event Queue & Caching (Redis)
REDIS_URL=redis://localhost:6379/0

# Razorpay Test Mode Credentials
# Get these from: https://dashboard.razorpay.com/app/keys
RAZORPAY_KEY_ID=rzp_test_TW8NzkX053cgZH
RAZORPAY_KEY_SECRET=u1aZqpcDoWbrNdYMVHDz3Z3M
RAZORPAY_WEBHOOK_SECRET=razorpay_webhook_secret_2026_test_8x7k2p

# AI & LLM (Intent Extraction & Querying)
GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
LLM_PROVIDER=groq
```

---

## 5. Database Migrations (Alembic)

Database schema migrations are managed via **Alembic** using SQLAlchemy 2.0 metadata bound to the PostgreSQL ledger.

### Migration Commands:

```bash
# 1. Apply all pending migrations to head
uv run alembic -c backend/alembic.ini upgrade head

# 2. Inspect the current revision in PostgreSQL
uv run alembic -c backend/alembic.ini current

# 3. Check available migration heads
uv run alembic -c backend/alembic.ini heads

# 4. Test rollback to base (clean removal)
uv run alembic -c backend/alembic.ini downgrade base

# 5. Re-apply migration to head
uv run alembic -c backend/alembic.ini upgrade head
```

### Baseline Migration (`0001_initial_schema`):
Located at `backend/alembic/versions/0001_initial_schema.py`. It generates all 11 canonical tables with foreign keys, checks, indexes, and unique constraints.

---

## 6. Canonical Data Model & Schema Reference

VoiceLedger's canonical schema comprises exactly **11 models** in `backend/app/models/`:

```text
       ┌───────────┐         ┌───────────────────────┐
       │   User    │◄────────┤     MerchantUser      │
       └─────┬─────┘         └───────────┬───────────┘
             │                           │ (Role: OWNER, ADMIN, STAFF)
             │                           ▼
             │                     ┌───────────┐
             │                     │ Merchant  │
             │                     └─────┬─────┘
             │                           │
    ┌────────┴───────────┬───────────────┼────────────────┬──────────────┐
    ▼                    ▼               ▼                ▼              ▼
┌────────┐      ┌────────────────┐ ┌───────────┐    ┌──────────┐   ┌──────────┐
│Device  │      │ProviderConnect.│ │  Payment  │    │AuditLog  │   │ Outbox   │
└───┬────┘      └────────────────┘ └─────┬─────┘    └──────────┘   │ Event    │
    │                                    │                         └──────────┘
    ▼                                    ▼
┌──────────────┐                 ┌───────────────┐
│DeviceSession │                 │ PaymentEvent  │
└──────────────┘                 └───────────────┘
                                         ▲
                                         │ (Delivery Target)
                                 ┌───────┴───────────┐
                                 │ VoiceNotification │
                                 └───────────────────┘
```

### Summary of Canonical Models:

| # | Model | Table Name | Purpose & Key Invariants |
|---|---|---|---|
| 1 | `User` | `users` | Platform accounts; unique email; Argon2/bcrypt password hash; active/superuser flags. |
| 2 | `Merchant` | `merchants` | Isolated business tenant; UUID PK; status (`ACTIVE`, `SUSPENDED`, `DEACTIVATED`); default currency (`INR`). |
| 3 | `MerchantUser` | `merchant_users` | Tenant membership with composite unique constraint `(merchant_id, user_id)`; roles (`OWNER`, `ADMIN`, `STAFF`). |
| 4 | `ProviderConnection` | `provider_connections` | Payment gateway configurations (Razorpay); unique `(merchant_id, provider, provider_account_reference)`. |
| 5 | `Payment` | `payments` | Authoritative financial record; `amount_minor BIGINT`; check `amount_minor >= 0`; `length(currency) = 3`; `ON DELETE RESTRICT`; unique `(provider, provider_payment_id)`. |
| 6 | `PaymentEvent` | `payment_events` | Immutable provider audit trail; SHA-256 `payload_hash`; unique `(provider, event_id)`; `ON DELETE SET NULL`. |
| 7 | `Device` | `devices` | Output-only terminal (Soundbox); public-key auth; `device_token_hash`; zero financial authority. |
| 8 | `DeviceSession` | `device_sessions` | Active WebSocket connections; unique `session_token_hash`; expiration and revocation timestamps. |
| 9 | `VoiceNotification` | `voice_notifications` | Voice announcement dispatch tracking (`PENDING`, `QUEUED`, `DELIVERED`, `FAILED`, `CANCELLED`); attempt counters. |
| 10 | `AuditLog` | `audit_logs` | Append-only security audit log; native PostgreSQL `JSONB` metadata & `INET` IP; credential scrubbing. |
| 11 | `OutboxEvent` | `outbox_events` | Transactional outbox for event publication; `JSONB` payload; worker claim index `(status, available_at, created_at)` for `FOR UPDATE SKIP LOCKED`. |

---

## 7. Running the Application

### Option A: Running with `uv` (Recommended)
```bash
# Sync dependencies
uv sync

# Run database migrations
uv run alembic -c backend/alembic.ini upgrade head

# Start FastAPI development server
uv run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

### Option B: Running with Standard Python
```bash
# Activate virtual environment
source .venv/bin/activate   # Linux / macOS
.venv\Scripts\activate      # Windows

# Run migrations
alembic -c backend/alembic.ini upgrade head

# Run server
python main.py
```

---

## 8. Health Checks & Observability

VoiceLedger provides deep liveness and readiness health monitoring endpoints.

### Health Endpoints:
* `GET /health` (or `GET /api/health`)
  * Checks PostgreSQL database connectivity via `SELECT 1`
  * Checks Redis connection via `PING`
  * Checks overall system responsiveness

#### Example Healthy Response (`200 OK`):
```json
{
  "status": "healthy",
  "environment": "development",
  "version": "1.0.0",
  "checks": {
    "database": {
      "status": "healthy",
      "latency_ms": 1.45
    },
    "redis": {
      "status": "healthy",
      "latency_ms": 0.82
    }
  }
}
```

If PostgreSQL or Redis is down, the endpoint returns `503 Service Unavailable` with detailed diagnosis for cloud orchestrators (Kubernetes / Docker Swarm / AWS ECS).

### Request Correlation & Tracing:
Every request processed by VoiceLedger is tagged with a unique `X-Request-ID` HTTP header. All log lines emitted during request processing automatically include `request_id` in their log record format:
```text
2026-09-03 02:11:36 [INFO] voiceledger (request_id=c148a032-1594-4d82-8bc6-981b2ae1b238): POST /api/webhooks/razorpay -> 200 in 12.3ms
```

---

## 9. Automated Testing & Verification

VoiceLedger features an extensive automated test suite covering unit, integration, migration, and backward-compatibility tests.

### Run All Tests:
```bash
uv run pytest -v
```

### Test Suite Structure:
```text
backend/tests/
├── test_phase0_foundation.py               # Health checks, DB/Redis probe failure, Request-ID middleware
├── test_phase1_1_models.py                  # User, Merchant, MerchantUser, ProviderConnection foundation
├── test_phase1_2_financial_models.py        # Payment, PaymentEvent, minor units, Level 1 & 2 idempotency
├── test_phase1_3_device_models.py           # Device, DeviceSession, public keys, token hashes
├── test_phase1_4_notification_audit_outbox.py # VoiceNotification, AuditLog (JSONB/INET), OutboxEvent
├── test_phase1_5_migration_integrity.py     # Consolidated Alembic migration, live PostgreSQL schema audit
└── (Legacy prototype compatibility tests)   # Isolated Kirana voice tests, webhook & LangGraph tests
```

**Status**: 120 tests passed across all suites (0 failures, 0 regressions).

---

## 10. Frontend Setup (Web & Universal Mobile)

The frontend is built with React Native (Expo) and runs universally on Web, Android, and iOS.

### Install Frontend Dependencies:
```bash
cd frontend
npm install
cd ..
```

### Option A: Run Universal Dev Server:
```bash
cd frontend
npx expo start
```
* **Web**: Press `w` in your terminal to open [http://localhost:8081](http://localhost:8081).
* **Smartphone (Expo Go)**: Scan the terminal QR code with your smartphone camera (iOS) or Expo Go (Android) on the same Wi-Fi network.

### Option B: Unified Production Build (FastAPI serves Static Web):
```bash
# 1. Build the web bundle
cd frontend && npm run build:web && cd ..

# 2. Run backend
uv run python main.py
```
Open [http://localhost:8000](http://localhost:8000) to view the unified web experience.

---

## 11. Merchant & Device Operations Guide

### 1. Recording a Sale via Voice:
Speak or type in Hindi, Hinglish, or English:
* *"2 chai 20 rupaye"*
* *"3 notebook 150 rs"*
* *"1 pizza 300 rupaye"*

VoiceLedger creates the payment request, assigns minor unit amounts (e.g. `15000` paise for ₹150.00), and creates an authorized Razorpay Payment Link.

### 2. Payment Arrival & Soundbox Voice Announcement:
When a customer scans and pays via UPI / Razorpay:
1. Razorpay sends a signed webhook (`payment.captured`) to `/api/webhooks/razorpay`.
2. Signature is verified using `RAZORPAY_WEBHOOK_SECRET` via HMAC-SHA256.
3. Level 1 idempotency registers the `PaymentEvent`.
4. Level 2 idempotency transitions the `Payment` to `CAPTURED`.
5. An `OutboxEvent` triggers the Soundbox service.
6. The physical device plays the real-time vernacular audio announcement:
   > *"Payment receive ho gaya! ₹150.00 successfully receive ho chuka hai."*

### 3. Voice Status Query:
Merchants can query payment arrival at any moment:
* *"Payment aaya kya?"*
* *"Coffee ka payment confirm hua?"*

The system checks authoritative ledger state and returns an immediate audible voice answer:
* *"Haan! Rs. 60 payment receive ho chuka hai (PAID ✅)."*
* *"Nahi, payment abhi tak nahi aaya hai (PENDING ⏳)."*
