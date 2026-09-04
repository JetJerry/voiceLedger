# 🎙️ Voice Box (VoiceLedger)

> **Real-Time Payment Voice Notification & AI Assistant Platform for Indian Retailers**

---

### 🌐 Live Production Deployments

| Resource | URL | Status |
| :--- | :--- | :--- |
| **Live Web App (Primary)** | [https://voiceledger-one.vercel.app](https://voiceledger-one.vercel.app) | 🟢 Active & Verified |
| **Live Web App (Mirror)** | [https://voice-box-pi.vercel.app](https://voice-box-pi.vercel.app) | 🟢 Active & Verified |
| **Modal Serverless Backend** | [https://rishil-cloud-mail--voiceledger-backend-fastapi-app.modal.run](https://rishil-cloud-mail--voiceledger-backend-fastapi-app.modal.run) | 🟢 Live API |
| **Interactive OpenAPI Docs** | [https://voiceledger-le5d.onrender.com/docs]([https://rishil-cloud-mail--voiceledger-backend-fastapi-app.modal.run/](https://voiceledger-le5d.onrender.com/)docs) | 📖 Swagger UI |

---

## 📌 Executive Summary

**Voice Box** (formerly *VoiceLedger*) is an AI-first merchant operations and payment infrastructure platform designed for Indian kirana stores and modern retail merchants. It bridges digital payment rails (**Razorpay & UPI**) directly to physical and virtual **Soundbox speaker terminals**, accompanied by an intelligent **Hindi / Hinglish Voice Talkback Assistant**.

Merchants can record sales and catalog updates simply by speaking (*"दो चाय और एक बिस्किट जोड़ो"*), generate instant dynamic UPI payment links, and hear instant, sub-second spoken payment announcements (*"Voice Box par ₹50 prapt hue"*) the exact millisecond a customer scans and pays.

---

## 🌟 Key Features

### 1. 🗣️ Multilingual Voice Talkback Assistant
- **Hands-Free Natural Voice Interaction**: Talk directly in Hindi, Hinglish, or English.
- **Agentic Intent Routing**: Powered by **Groq (Llama 3.3 70B)** / **Google Gemini** with a LangGraph state machine and a deterministic rule-based fallback engine.
- **Full Speech Pipeline**:
  - **Speech-to-Text (STT)**: OpenAI Whisper Base running on GPU/serverless.
  - **Text-to-Speech (TTS)**: Facebook MMS-TTS (`facebook/mms-tts-hin`) generating natural native Hindi audio.
  - **3-Tier Audio Playback Pipeline**:
    1. *Tier 1 (Blob ObjectURL)*: Base64 audio decoded into native `audio/mp3` Blobs to avoid URL buffer truncations.
    2. *Tier 2 (Streaming MP3)*: Server-side fallback via `GET /api/voice/speak?text=...&lang=hi`.
    3. *Tier 3 (Web SpeechSynthesis)*: Local browser speech engine with Indian English/Hindi voice fallback.
    4. *Autoplay Recovery*: Interactive **"Tap to Hear Voice 🔊"** unmute banner for browsers enforcing strict audio autoplay policies.

### 2. 🔊 Virtual & Physical Soundbox Gateway
- **Hardware Simulation Terminal**: Fully interactive digital soundbox reproducing physical IoT devices (status LEDs, volume step controls, firmware telemetry, battery simulation).
- **Cryptographic Device Authentication**: Provisioning tokens validated via SHA-256 digests (`device_token_hash`, `session_token_hash`).
- **Delivery Acknowledgment (ACK) Loop**: Hardware devices send cryptographic ACKs upon speaker completion to guarantee zero duplicate or dropped announcements.

### 3. 💳 Razorpay & Dynamic UPI Payment Rail
- **HMAC-SHA256 Signature Verification**: Validates every inbound webhook with cryptographic signature timing-safe comparison.
- **Instant Payment Links & QR Codes**: Dynamically creates Razorpay payment links and generates scannable UPI QR codes on the fly.
- **Transaction Simulator**: Built-in test sandbox to simulate payment arrivals (`CREATED` ➔ `AUTHORIZED` ➔ `CAPTURED`) in real time without incurring real bank charges.

### 4. ⚡ Hybrid Real-Time Event Engine
- **Dual-Mode Streaming**:
  - *WebSocket Feed*: Stateful low-latency persistent connection (`/ws/merchant`) for standard servers.
  - *Intelligent Cloud Polling Fallback*: Seamlessly activates high-frequency (5s) event polling on serverless microVM environments (such as Modal) where long-lived WebSockets are unavailable, avoiding RFC 6455 Code 1006 reconnect loops and activity log spam.
- **Pulsing Status Badges**: Live connection pills with automatic sync diagnostics.

### 5. 📦 Kirana Catalog & Billing Ledger
- **Live Inventory Management**: Complete CRUD for product items, barcodes, categories, and prices.
- **Fast Checkout & Order Management**: Real-time sales calculations, status tracking (`PENDING`, `PARTIAL`, `PAID`), and receipt breakdowns.

---

## 🛡️ Core Architectural Invariants

| Invariant | Guarantee | Technical Implementation |
| :--- | :--- | :--- |
| **Integer Minor Units** | Zero floating-point drift | All monetary amounts stored as `BIGINT amount_minor` in paise (e.g. ₹15.50 = `1550`). Prohibits SQL `FLOAT` / `DOUBLE`. |
| **Strict Multi-Tenancy** | Total merchant isolation | Every database record, query filter, Redis channel, and WebSocket feed is scoped strictly by `merchant_id`. |
| **Multi-Level Idempotency** | Protection against double payments | **Level 1**: `UNIQUE(provider, event_id)` on `payment_events`.<br>**Level 2**: `UNIQUE(provider, provider_payment_id)` on `payments`. |
| **Zero Financial Mutation** | Real-time streams cannot alter funds | WebSocket and polling streams are strictly read-only; payment mutations are only possible through verified cryptographic webhook callbacks. |
| **Zero Plaintext Secrets** | Enterprise credential security | User passwords hashed using **Argon2id**. Device keys and session tokens stored as SHA-256 digests. |
| **Transactional Outbox** | Reliable at-least-once notifications | Financial records and notification dispatch tasks are committed in a single atomic database transaction. |

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    subgraph Customer["Customer Facing"]
        C[Customer] -->|Scans UPI QR / Pays| RZP[Razorpay Payment Rails]
    end

    subgraph WebhookBoundary["Security & Ingestion Boundary"]
        RZP -->|HTTP POST Webhook with HMAC-SHA256| API[FastAPI Webhook Gateway]
        API -->|Timing-Safe Signature Check| IDEM[Level 1 & 2 Idempotency Guard]
    end

    subgraph Storage["PostgreSQL Authoritative Ledger"]
        IDEM -->|Atomic DB Transaction| PG[(PostgreSQL 16)]
        PG -->|Write Invariant| PE[payment_events: Immutable]
        PG -->|Write Invariant| P[payments: amount_minor]
        PG -->|Transactional Outbox| OB[outbox_events]
    end

    subgraph EventBus["Real-Time Dispatch Pipeline"]
        OB -->|Async Dispatch Worker| REDIS[(Redis 7 Pub/Sub)]
        REDIS -->|Tenant Channel Stream| WS[WebSocket / Polling Gateway]
    end

    subgraph Terminals["Merchant Frontends"]
        WS -->|Real-Time Frame| SB[Virtual / Physical Soundbox]
        WS -->|Live Updates| DASH[Voice Box React Dashboard]
        SB -->|MMS-TTS Playback| SPK[🔊 'Voice Box par ₹500 prapt hue']
        SB -->|Cryptographic ACK| API
    end
```

---

## 🛠️ Technology Stack

### Frontend (`frontend_v2`)
- **Framework**: React 18 with TypeScript & Vite
- **Styling**: Tailwind CSS with custom design system, glassmorphism, and responsive layout
- **Icons**: Lucide React
- **Testing**: Vitest & React Testing Library (24 automated unit and smoke tests)
- **Deployment**: Vercel (Edge CDN with SPA URL rewrites)

### Backend (`backend`)
- **Framework**: FastAPI (Python 3.10+ / 3.12 compatible) with Pydantic v2 schemas
- **Persistence**: SQLAlchemy 2.0 ORM with PostgreSQL 16 (Authoritative)
- **Caching & Streaming**: Redis 7 (Pub/Sub message broker)
- **Asynchronous Execution**: Worker tasks with exponential backoff retries
- **Security**: Argon2id, JWT (HS256) rotation, Timing-Safe HMAC verification

### AI / Voice Pipeline
- **LLM Intent Engine**: Groq (`llama-3.3-70b-versatile`) / Google Gemini Pro with LangGraph
- **Speech-to-Text**: OpenAI Whisper (`whisper-base`)
- **Text-to-Speech**: Facebook MMS-TTS Hindi (`facebook/mms-tts-hin`)
- **Serverless Runtime**: Modal microVM containers for high-performance GPU/CPU inferencing

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.10+ (`uv` recommended)
- Node.js 18+ & npm
- Docker & Docker Compose (for local database & Redis)

---

### 1. Clone the Repository
```bash
git clone https://github.com/JetJerry/voiceLedger.git
cd voiceLedger
```

---

### 2. Infrastructure Setup (Docker)
Start the PostgreSQL 16 and Redis 7 background containers:
```bash
docker-compose up -d
```
Verify containers are running:
```bash
docker-compose ps
```

---

### 3. Backend Setup
Using `uv` (or standard `venv` / `pip`):
```bash
# Install Python dependencies
uv sync

# Run database migrations
uv run alembic upgrade head

# Start the local development server
uv run uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```
- API Documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health Check: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

---

### 4. Frontend Setup
```bash
cd frontend_v2

# Install dependencies
npm install

# Start Vite dev server
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

---

### 5. Running Automated Tests

#### Backend Test Suite
```bash
# Run backend integration tests
uv run pytest backend/tests/test_store_integration.py backend/tests/test_soundbox.py -v
```

#### Frontend Test Suite
```bash
cd frontend_v2
npm test
```
All **24/24 unit, schema, parser, and lifecycle tests** will execute and pass.

---

## 📡 API Reference Highlights

### Authentication & Tenant Scoping
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/auth/register` | Register a new user and assign merchant role |
| `POST` | `/api/v1/auth/login` | Authenticate with Argon2id and receive JWT tokens |
| `POST` | `/api/v1/auth/refresh` | Rotate access tokens using secure refresh token |
| `GET` | `/api/v1/merchants/me` | Fetch active merchant organization and role |

### Payments & Ingestion
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/webhooks/razorpay` | Ingest Razorpay webhooks with HMAC-SHA256 signature |
| `GET` | `/api/payments` | List tenant payments with status and date filters |
| `POST` | `/api/payments/create-link` | Generate dynamic Razorpay payment links |
| `POST` | `/api/payments/simulate` | Test sandbox payment simulation without real charges |

### Voice & Soundbox
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/voice/process-text` | Natural Hindi/English text command processing |
| `POST` | `/api/voice/process-audio` | Audio file transcription (Whisper) & execution |
| `GET` | `/api/voice/speak` | Stream native Hindi MMS-TTS audio MP3 |
| `GET` | `/api/voice/payment-announcements` | Soundbox polling endpoint for pending audio arrival |
| `POST` | `/api/voice/payment-announcements/{id}/ack` | Submit device playback confirmation ACK |

### Store & Catalog
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/sales/catalog/merchant` | Retrieve full merchant product catalog |
| `POST` | `/api/sales/catalog/merchant` | Add product with minor-unit price and stock |
| `GET` | `/api/sales/orders` | List sales orders with balance breakdown |

---

## ⚙️ Key Environment Variables

### Backend Configuration (`.env`)
```env
# Database & Cache
DATABASE_URL=postgresql://voiceledger:voiceledger_secure_password_2026@localhost:5432/voiceledger
REDIS_URL=redis://localhost:6379/0

# Security
JWT_SECRET=voiceledger_jwt_signing_secret_dev_environment_key_2026_min_32
ARGON2_TIME_COST=2
ARGON2_MEMORY_COST=19456

# Razorpay Integration
RAZORPAY_KEY_ID=rzp_test_YourKeyIdHere
RAZORPAY_KEY_SECRET=YourRazorpayKeySecretHere
RAZORPAY_WEBHOOK_SECRET=YourWebhookSecretHere

# LLM & Voice
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_YourGroqKeyHere
GEMINI_API_KEY=AIzaSy_YourGeminiKeyHere
```

### Frontend Configuration (`frontend_v2/.env.production`)
```env
# Modal Serverless Production Backend
VITE_API_BASE_URL=https://rishil-cloud-mail--voiceledger-backend-fastapi-app.modal.run
VITE_WS_BASE_URL=wss://rishil-cloud-mail--voiceledger-backend-fastapi-app.modal.run
```

---

## 🔒 Security Compliance & Auditability

1. **Timing-Safe HMAC Verification**: Webhook signatures are validated using `hmac.compare_digest` to prevent timing attacks.
2. **Immutable Event Auditing**: Every incoming webhook payload is persisted in its raw, unmodified form into `payment_events` with an incremental sequence counter before business logic execution.
3. **Sensitive Key Redaction**: Credentials, webhook secrets, authorization headers, and raw tokens are scrubbed from server logs and diagnostics automatically.
4. **Argon2id Password Standards**: Adheres to OWASP password hashing guidelines with high memory and iteration costs.

---

## 👥 Authors & License

Developed with ❤️ for the **Razorpay Buildathon 2026**.  
Licensed under the **MIT License**.
