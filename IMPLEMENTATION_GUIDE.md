# VoiceLedger — Technical Implementation Guide & Developer Context

> **Permanent context file for developers and future upgrades.**
> *Last Updated: August 2026*

---

## 1. Core Focus: Voice-First Product Sales & Payment Arrival Verification

**VoiceLedger** focuses on closing the loop between what product was sold and whether the money actually arrived via Razorpay:

```text
Merchant speaks sale ("2 coffee 60 rupaye" or "3 notebook 150 rs")
        ↓
Dynamic Product & Quantity Extraction (Any item, no hardcoding)
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
Merchant asks through voice: "Payment aaya kya?"
        ↓
VoiceLedger Agent checks live Razorpay status and replies in natural voice:
  "Haan! 2x coffee ka Rs. 60 payment receive ho chuka hai (PAID ✅)."
```

---

## 2. Architecture & File Structure

```text
voiceledger/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI app, static mounts, startup lifespan
│   │   ├── config.py                   # Pydantic Settings & environment variables
│   │   ├── db/
│   │   │   ├── base.py                 # Declarative Base
│   │   │   ├── session.py              # Engine & SessionLocal factory
│   │   │   └── init_db.py              # Schema creation & catalog seeding
│   │   ├── models/                     # SQLAlchemy Models (Sale, SaleItem, Payment, etc.)
│   │   ├── schemas/                    # Pydantic schemas (Product, Sale, Voice, Payment)
│   │   ├── services/
│   │   │   ├── llm_service.py          # Dynamic extraction & "Payment aaya kya?" query parser
│   │   │   ├── sales_service.py        # Dynamic product pricing & sale creation
│   │   │   ├── razorpay_service.py     # Razorpay API client & HMAC SHA256 verification
│   │   │   ├── reconciliation_service.py # Deterministic matching engine (PAID/PARTIAL/PENDING)
│   │   │   └── recovery_service.py     # Overdue scoring & reminder triggers
│   │   ├── agents/
│   │   │   └── merchant_agent.py       # Voice orchestrator & payment status checker
│   │   └── api/                        # REST API endpoints (voice, sales, payments, webhooks)
│   └── tests/                          # 16 Unit & Integration Tests (100% Pass)
│
├── frontend/                           # Merchant Web Application
│   ├── index.html                      # Glassmorphic Dark UI layout
│   ├── styles.css                      # Modern CSS variables, animations, and gradients
│   └── app.js                          # WebSpeech voice recognition & real-time polling
│
├── evaluation/                         # 100-Transaction Benchmark Suite
│   ├── dataset_generator.py            # Product-focused synthetic dataset generator
│   ├── evaluate.py                     # Benchmark runner & metric reporter
│   └── dataset.json                    # 100 Golden test cases
│
├── IMPLEMENTATION_GUIDE.md             # This developer context file
└── USER_SETUP_GUIDE.md                 # User setup & configuration manual
```

---

## 3. Key Design Decisions

1. **Zero Hardcoded Examples**: The system dynamically handles whatever product names, quantities, and prices the merchant speaks (e.g. coffee, notebook, shirt, pen, tea, meals).
2. **No Mandatory Customer Info**: Focus is on the sold products and their payment arrival status.
3. **Voice Payment Verification**: Merchant can simply ask *"Payment aaya kya?"* or *"Coffee ka payment aaya kya?"* at any time, and the agent inspects the verified Razorpay state and responds immediately.
4. **Deterministic Accounting**: Financial calculations, reconciliation, and signature verifications remain strictly in backend deterministic code.
