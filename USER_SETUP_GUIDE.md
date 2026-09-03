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

### Applied Migrations:
* `0001_initial_schema`: Generates the foundation 11 canonical tables with foreign keys, checks, indexes, and unique constraints.
* `0002_user_sessions`: Adds the `user_sessions` table for server-controlled refresh-token management, token rotation, and reuse detection.

---

## 6. Canonical Data Model & Schema Reference

VoiceLedger's canonical schema comprises **12 models** in `backend/app/models/`:

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
| 2 | `UserSession` | `user_sessions` | Server-controlled refresh token sessions; SHA-256 `token_hash`; token family tracking (`family_id`) for rotation and reuse detection; revocation timestamps. |
| 3 | `Merchant` | `merchants` | Isolated business tenant; UUID PK; status (`ACTIVE`, `SUSPENDED`, `DEACTIVATED`); default currency (`INR`). |
| 4 | `MerchantUser` | `merchant_users` | Tenant membership with composite unique constraint `(merchant_id, user_id)`; roles (`OWNER`, `ADMIN`, `STAFF`). |
| 5 | `ProviderConnection` | `provider_connections` | Payment gateway configurations (Razorpay); unique `(merchant_id, provider, provider_account_reference)`. |
| 6 | `Payment` | `payments` | Authoritative financial record; `amount_minor BIGINT`; check `amount_minor >= 0`; `length(currency) = 3`; `ON DELETE RESTRICT`; unique `(provider, provider_payment_id)`. |
| 7 | `PaymentEvent` | `payment_events` | Immutable provider audit trail; SHA-256 `payload_hash`; unique `(provider, event_id)`; `ON DELETE SET NULL`. |
| 8 | `Device` | `devices` | Output-only terminal (Soundbox); public-key auth; `device_token_hash`; zero financial authority. |
| 9 | `DeviceSession` | `device_sessions` | Active WebSocket connections; unique `session_token_hash`; expiration and revocation timestamps. |
| 10 | `VoiceNotification` | `voice_notifications` | Voice announcement dispatch tracking (`PENDING`, `QUEUED`, `DELIVERED`, `FAILED`, `CANCELLED`); attempt counters. |
| 11 | `AuditLog` | `audit_logs` | Append-only security audit log; native PostgreSQL `JSONB` metadata & `INET` IP; credential scrubbing. |
| 12 | `OutboxEvent` | `outbox_events` | Transactional outbox for event publication; `JSONB` payload; worker claim index `(status, available_at, created_at)` for `FOR UPDATE SKIP LOCKED`. |

---

## 7. Authentication & Token Architecture (API v1)

VoiceLedger implements an enterprise-grade authentication system under `/api/v1/auth/`:
- **Passwords**: Hashed with **Argon2id** ($m=64\text{ MiB}, t=3, p=4$) with unique salts.
- **Access Tokens**: Short-lived (15 min default) signed JWTs (`HS256`, configurable via `JWT_SECRET`). Minimum claims: `sub`, `type="access"`, `jti`, `iat`, `exp`.
- **Refresh Tokens**: Opaque 256-bit cryptographically secure random tokens. Only their SHA-256 hash is persisted server-side.
- **Token Rotation & Reuse Detection**: Every refresh request rotates the token and invalidates the old one. If an already-rotated token is presented (potential token theft), the entire session family (`family_id`) is immediately revoked.
- **Endpoints**:
  - `POST /api/v1/auth/register` — User registration.
  - `POST /api/v1/auth/login` — Verifies credentials; issues short-lived access token + rotating refresh token.
  - `POST /api/v1/auth/refresh` — Rotates refresh token; issues new access + refresh tokens.
  - `POST /api/v1/auth/logout` — Revokes refresh session.
  - `GET /api/v1/auth/me` — Protected endpoint returning current user profile (`Authorization: Bearer <access_token>`).

### Merchant Context, RBAC & Tenant Isolation (Phase 2.4):
- **Server-Side Context Resolution**: `get_current_merchant` / `get_current_merchant_membership` resolves merchant organization via `X-Merchant-ID` header or sole membership. Validates membership in PostgreSQL; rejects arbitrary client merchant IDs (HTTP 403).
- **Role-Based Access Control (RBAC)**: Supports `OWNER`, `ADMIN`, `STAFF` via explicit allowed-role sets (`require_role("OWNER")`, `require_role("OWNER", "ADMIN")`, `require_role("OWNER", "ADMIN", "STAFF")`). Roles cannot be spoofed via client request headers or body.
- **Strict Query-Level Tenant Isolation**: All merchant-owned resource accesses (`Payment`, `PaymentEvent`, `Device`, `DeviceSession`, `VoiceNotification`, `ProviderConnection`) are filtered at query level `(id, merchant_id)`. Direct and indirect relationship navigation guarantees zero cross-tenant leakage and eliminates IDOR vulnerabilities.
- **Endpoints**:
  - `GET /api/v1/merchants/context` — Resolves active merchant details and caller's role.
  - `GET /api/v1/merchants/owner-only` — OWNER-only operation guard.
  - `GET /api/v1/merchants/admin-only` — ADMIN / OWNER operation guard.
  - `GET /api/v1/merchants/staff-accessible` — STAFF, ADMIN, or OWNER access.
  - `GET /api/v1/merchants/payments/{payment_id}` — Tenant-isolated payment retrieval.
  - `GET /api/v1/merchants/devices/{device_id}` — Tenant-isolated device retrieval.
  - `GET /api/v1/merchants/device-sessions/{session_id}` — Indirect tenant-isolated device session retrieval.

## 8. Running the Application

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

## 9. Health Checks & Observability

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

## 10. Automated Testing & Verification

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
├── test_phase2_1_password_security.py       # Argon2id password hashing, validation, constant-time verification
├── test_phase2_2_registration_and_login.py  # User registration, email normalization, credential verification
├── test_phase2_3_tokens_and_sessions.py     # JWT access tokens, rotating refresh sessions, reuse detection, logout, get_current_user
├── test_phase2_4_merchant_rbac_and_tenancy.py # Merchant context, RBAC (OWNER/ADMIN/STAFF), tenant isolation & IDOR tests
├── test_phase2_5_security_hardening.py     # Security hardening: JWT algorithm confusion, production secrets, audit sanitization, security headers
├── test_phase3_1_provider_abstraction.py   # PaymentProvider interface, NormalizedPayment, NormalizedPaymentEvent, provider error hierarchy
├── test_phase3_2_razorpay_adapter.py       # RazorpayClient, RazorpayProvider adapter, status/method mapping, error translation, zero secret leakage
├── test_phase3_3_razorpay_webhook_verification.py # RazorpayWebhookVerifier, raw-body HMAC-SHA256, timing-safe compare_digest, size limit, zero financial mutation
├── test_phase3_4_webhook_ingestion_and_deduplication.py # WebhookIngestionService, Level 1 (provider, event_id) deduplication, safe concurrency, zero Payment mutations
├── test_phase3_5_integration_verification.py # Razorpay end-to-end boundary verification, tampering, adapter flows, and zero Phase 4 leakage
├── test_pre_phase4_cleanup.py               # Verification of unmounted conflicting legacy routes (/api/auth, /api/payments, /api/webhooks) and canonical v1 exclusivity
├── test_phase4_1_payment_core.py            # PaymentService, canonical state machine, Level 2 (provider, provider_payment_id) idempotency, anti-tampering
├── test_phase4_2_payment_event_processing.py # PaymentEventService, atomic event-to-payment transaction boundary, state updates, linking
├── test_phase4_3_transactional_outbox.py    # OutboxService, transactional outbox pattern, atomicity, sanitized payload, lifecycle transitions
├── test_phase4_4_outbox_worker.py           # OutboxWorker, FOR UPDATE SKIP LOCKED, RedisEventPublisher, bounded exponential backoff, DEAD_LETTER, stuck lease recovery
├── test_phase4_5_end_to_end.py              # Full E2E pipeline, Webhook -> PaymentEvent -> Payment -> OutboxEvent -> OutboxWorker -> Redis, multi-step lifecycle, reconciliation
├── test_phase5_1_websocket_gateway.py       # Minimal Real-Time WebSocket Gateway (/ws/merchant), JWT auth, tenant isolation, dynamic Redis subscription
├── test_phase6_1_device_management.py       # Soundbox device registration, one-time secret, SHA-256 token hashes, session auth, heartbeat telemetry
├── test_phase6_2_device_websocket.py        # Soundbox Device WebSocket Bridge (/ws/device), session token auth, tenant Redis channel, multi-device delivery
├── test_phase7_1_voice_notification.py       # Localized voice notifications, deterministic phrase & currency formatting, TTSProvider abstraction, failure isolation
├── test_phase7_2_audio_playback.py           # Soundbox audio streaming over WebSocket, base64 payload, device targeting, playback ACK lifecycle, idempotency
├── test_phase8_1_offline_replay.py           # Offline notification queuing, deterministic oldest-first replay upon device reconnect, duplicate in-flight protection
├── test_phase9_1_end_to_end_release.py       # Full system verification: Webhook -> Payment -> Outbox -> Worker -> Redis -> Voice -> WebSocket -> Soundbox -> ACK -> DELIVERED
└── (Legacy prototype compatibility tests)   # Isolated Kirana voice & sales tests
```

**Status**: 459 canonical VoiceLedger tests passed with 100% success (0 regressions, 0 failures).

---

## 11. Frontend Setup (Web & Universal Mobile)

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

---

## 12. Buildathon Demo Walkthrough (Step-by-Step)

Follow these exact steps to demonstrate VoiceLedger to judges or evaluators:

### 1. Start Infrastructure:
```bash
docker compose up -d postgres redis
```
Verify PostgreSQL is healthy on `localhost:5432` and Redis on `localhost:6379`.

### 2. Configure Environment:
Copy `.env.example` to `.env` (if not already present):
```ini
APP_ENV=development
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/voiceledger
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=voiceledger_jwt_signing_secret_dev_environment_key_2026_min_32
RAZORPAY_KEY_ID=rzp_test_TW8NzkX053cgZH
RAZORPAY_KEY_SECRET=u1aZqpcDoWbrNdYMVHDz3Z3M
RAZORPAY_WEBHOOK_SECRET=razorpay_webhook_secret_2026_test_8x7k2p
```

### 3. Verify Database Migrations:
```bash
uv run alembic -c backend/alembic.ini current
```
Output must show `0002_user_sessions (head)`.

### 4. Start Application & Worker:
Terminal 1 (API Server):
```bash
uv run uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```
Terminal 2 (Outbox Worker):
```bash
uv run python -m backend.app.worker
```

### 5. Automated Full-Pipeline Smoke Test:
To immediately verify the complete online payment flow, offline replay sync, and idempotency:
```bash
uv run python -m backend.scripts.live_demo_smoke
```

### 6. Live Razorpay Test Mode Webhook Integration (Optional Public Tunnel):
1. Start an HTTPS tunnel (using any of these zero-install options):
   - **Option A (LocalTunnel via npx — Pure JS, no .exe)**:
     ```bash
     npx localtunnel --port 8000
     ```
   - **Option B (Native Windows OpenSSH — No npm/download needed)**:
     ```bash
     ssh -R 80:localhost:8000 nokey@localhost.run
     ```
2. In Razorpay Dashboard (**Settings → Webhooks**):
   - **URL**: `https://<your-tunnel-domain>/api/v1/webhooks/razorpay`
   - **Secret**: Value of `RAZORPAY_WEBHOOK_SECRET`
   - **Active Events**: `payment.captured`
3. Make a test payment via UPI / Card in Razorpay Test Mode.
4. Observe the payment state machine commit to `CAPTURED`, the Outbox publish to Redis, the Voice Notification synthesis, and the real-time audio playback over the Soundbox WebSocket.
