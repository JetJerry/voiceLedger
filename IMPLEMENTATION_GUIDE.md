# VoiceLedger — Technical Implementation Guide & Developer Context

> **Permanent context file for developers and future upgrades.**
> *Last Updated: August 2026*

---

## 1. Project Philosophy & Core Distinction

Traditional "khata" or ledger apps treat voice merely as a data entry shortcut: the merchant speaks, text is entered, and the app is finished.

**VoiceLedger** operates on a fundamentally different principle:
> **"Voice is not the product. Voice is the interface to an AI agent that manages the payment lifecycle and automates revenue recovery."**

```text
Merchant speaks sale ("Rahul ko 2 burger diye")
        ↓
AI extracts structured items & customer
        ↓
Authoritative catalog pricing (Deterministic)
        ↓
Real Razorpay Test Mode Payment Link generated
        ↓
Customer pays via UPI / Cards / NetBanking
        ↓
Verified Razorpay Webhook reaches Backend (HMAC SHA256)
        ↓
Deterministic Reconciliation Engine:
  - FULL PAYMENT    → Status: PAID ✅ (Outstanding: ₹0)
  - PARTIAL PAYMENT → Status: PARTIAL ⚠️ (Outstanding: ₹X)
  - NO PAYMENT      → Status: PENDING ⏳
  - INVALID RECORD  → Status: UNMATCHED ❓
        ↓
AI Revenue Recovery Queue ranks debtors by overdue risk
        ↓
1-Click WhatsApp / SMS Payment Link recovery triggered
```

---

## 2. Architecture & Directory Overview

```text
voiceledger/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI app, CORS, static routes, startup seeding
│   │   ├── config.py                   # Pydantic Settings & environment variables
│   │   ├── db/
│   │   │   ├── base.py                 # Declarative Base
│   │   │   ├── session.py              # Engine & SessionLocal factory
│   │   │   └── init_db.py              # Schema creation & default catalog seeding
│   │   ├── models/                     # SQLAlchemy Models
│   │   │   ├── merchant.py             # Merchant profile
│   │   │   ├── customer.py             # Customer directory
│   │   │   ├── product.py              # Product/Menu catalog
│   │   │   ├── sale.py                 # Sale & SaleItem entities
│   │   │   ├── payment.py              # Payment & WebhookEvent entities
│   │   │   └── recovery.py             # RecoveryAction log
│   │   ├── schemas/                    # Pydantic validation schemas
│   │   ├── services/
│   │   │   ├── llm_service.py          # Google Gemini structured extraction & Hinglish NLP
│   │   │   ├── voice_service.py        # Audio processing & STT integration
│   │   │   ├── sales_service.py        # Deterministic price lookup & sale creation
│   │   │   ├── razorpay_service.py     # Razorpay API client & HMAC SHA256 verification
│   │   │   ├── reconciliation_service.py # Deterministic matching engine
│   │   │   └── recovery_service.py     # Overdue scoring & reminder triggers
│   │   ├── agents/
│   │   │   └── merchant_agent.py       # Safe orchestrator with guarded tool dispatch
│   │   └── api/                        # FastAPI REST API endpoints
│   │       ├── voice.py                # POST /api/voice/process-text, process-audio
│   │       ├── sales.py                # POST /api/sales, GET catalog
│   │       ├── payments.py             # POST /api/payments/create-link, simulate
│   │       ├── webhooks.py             # POST /api/webhooks/razorpay, simulate
│   │       ├── recovery.py             # GET /api/recovery/queue, POST trigger
│   │       └── dashboard.py            # GET /api/dashboard/summary
│   └── tests/                          # 16 Comprehensive Unit & Integration Tests
│
├── frontend/                           # Merchant Web Application
│   ├── index.html                      # Glassmorphic Dark UI layout
│   ├── styles.css                      # Modern CSS variables, animations, and gradients
│   └── app.js                          # WebSpeech voice recognition & real-time polling
│
├── evaluation/                         # 100-Transaction Benchmark Suite
│   ├── dataset_generator.py            # Synthetic Hinglish dataset generator
│   ├── evaluate.py                     # Benchmark runner & metric reporter
│   └── dataset.json                    # 100 Golden test cases
│
├── data/
│   └── default_catalog.json            # Seed menu items & sample customers
├── docker-compose.yml                  # Containerized Postgres + Backend stack
├── IMPLEMENTATION_GUIDE.md             # This developer context file
└── USER_SETUP_GUIDE.md                 # User setup & configuration manual
```

---

## 3. Implemented Modules & Technical Summary

### Module 1 & 2: Database Schema & Seeding
- Models: `Merchant`, `Customer`, `Product`, `Sale`, `SaleItem`, `Payment`, `WebhookEvent`, `RecoveryAction`.
- Supported DBs: SQLite (default zero-config) and PostgreSQL via `DATABASE_URL`.
- Auto-seeding on startup from `data/default_catalog.json`.

### Module 3: AI Transaction Understanding (Hinglish & English)
- Supported LLM: Google Gemini (`gemini-2.5-flash` / `gemini-2.0-flash`).
- Fallback: Built-in regex / NLP heuristic parser that handles common Hindi numerals (*ek, do, teen, char, paanch*) and phrasing (*"Rahul ko 2 burger diye, 100 each"*).
- Structured Output: Schema validates `customer_name`, `customer_phone`, `items` (with `product_name`, `quantity`, `unit_price`), `intent`, and `explanation`.

### Module 4: Sales & Pricing Engine
- Authoritative pricing lookup against product database table.
- Subtotal computation: `quantity * unit_price`. Total: `sum(subtotals)`.
- Automatic Razorpay payment link generation on sale creation.

### Module 5 & 6: Razorpay Test Mode & Webhook Ingestion
- Real Razorpay API Client: `POST https://api.razorpay.com/v1/payment_links` using Basic Auth (`RAZORPAY_KEY_ID:RAZORPAY_KEY_SECRET`).
- Webhook Ingestion: `POST /api/webhooks/razorpay`.
- Security: Cryptographic HMAC SHA256 verification using `X-Razorpay-Signature`.
- Idempotency: Duplicate events with the same `event_id` are identified and skipped safely.

### Module 7: Deterministic Reconciliation Engine
Reconciliation state machine is 100% deterministic (no AI hallucinations for money):
$$\text{Cumulative Received} = \sum \text{Captured Payments for Sale}$$
$$\text{Outstanding Amount} = \max(0, \text{Total Amount} - \text{Cumulative Received})$$
- `PAID`: Cumulative Received $\ge$ Total Amount
- `PARTIAL`: $0 < \text{Cumulative Received} < \text{Total Amount}$
- `PENDING`: Cumulative Received $= 0$
- `FAILED`: Payment failure event received with 0 captured funds
- `UNMATCHED`: Payment event arrived with no corresponding local sale record

### Module 8 & 9: Merchant Agent & Revenue Recovery
- Agent Tools: `create_sale`, `query_pending`, `query_status`, `query_daily`, `trigger_recovery`.
- Recovery Priority Scoring:
  $$\text{Priority Score} = \text{Outstanding Amount} \times (1.0 + 0.5 \times \min(\text{Days Overdue}, 7))$$
- Categorizes debtors into **HIGH**, **MEDIUM**, and **LOW** priority.
- Generates click-to-chat WhatsApp reminders (`https://wa.me/...`) containing direct Razorpay short links.

### Module 10: Merchant Dashboard UI
- Dark glassmorphism styling (`backdrop-filter: blur(16px)`).
- Web Speech API speech-to-text integration with microphone recording animation.
- Instant KPI counters, live receivables table, and interactive **Payment Simulator** modal for live demo presentations.

### Module 11: 100-Transaction Evaluation Suite
- Benchmarks 100 synthetic transactions (40 Full, 20 Partial, 20 Pending, 10 Failed, 10 Unmatched).
- Verified Results:
  - **Reconciliation Accuracy**: **100.0%**
  - **Recovery Pipeline Rate**: **100.0%**
  - **Execution Benchmark Speed**: **0.37s (~3.7ms per transaction)**

---

## 4. Architectural Guardrails

To ensure financial integrity:
1. **Never let LLM calculate prices or totals**: The LLM extracts the word `"burger"` and quantity `2`. The backend looks up the database price (₹100) and computes ₹200.
2. **Never trust frontend for payment status**: Payment status updates only occur upon receiving a verified Razorpay Webhook or official Razorpay REST verification.
3. **Always verify HMAC SHA256 signatures** on webhooks in production.
4. **Log every recovery action**: All reminders and resends are stored with timestamp in `recovery_actions`.

---

## 5. Roadmap for Future Upgrades

When upgrading this codebase in the future, follow these architectural recommendations:

### 1. Automated WhatsApp Bot (Meta Cloud API / Twilio)
- **Current State**: Generates `https://wa.me/` direct chat links for merchant 1-click dispatch.
- **Future Upgrade**: Connect Meta WhatsApp Business Cloud API in `backend/app/services/recovery_service.py` to automatically dispatch WhatsApp template messages on a scheduled cron.

### 2. Automated Outbound IVR Voice Calls
- **Future Upgrade**: Integrate an Indian voice IVR provider (such as Sarvam AI or Exotel/Twilio) to make automated voice reminder calls in Hindi/English to customers with `HIGH` priority overdue balances.

### 3. Real-Time Push & Soundbox WebSockets
- **Current State**: Frontend polls `/api/dashboard/summary` every 5 seconds.
- **Future Upgrade**: Add FastAPI WebSocket endpoint `/ws/merchant/{merchant_id}` to broadcast payment events instantly to the web dashboard and hardware soundbox speakers (*"Razorpay par ₹200 prapt hue"*).

### 4. Multi-Tenant Merchant System
- **Current State**: Single merchant context (Merchant ID #1).
- **Future Upgrade**: Add JWT authentication with phone OTP login, allowing thousands of independent merchants to manage their own catalogs and Razorpay sub-accounts / Route split payments.

### 5. PDF Invoicing & GST Export
- **Future Upgrade**: Add a PDF generation service (e.g. `reportlab` or `weasyprint`) to generate GST-compliant e-invoices upon sale completion.
