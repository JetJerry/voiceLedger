# VoiceLedger — 2-Day Razorpay Buildathon Implementation Plan

## 1. Executive Summary

### Product name
**VoiceLedger**

### One-line pitch
> **An AI voice-first payment collection agent for small merchants that turns spoken sales into payment requests, uses Razorpay to collect real payments, verifies payment events, detects partial/missing payments, and helps recover outstanding money.**

### Core idea

The original idea was a voice-based sales/khata assistant. That alone is not differentiated enough because voice-ledger/khata products already exist.

The refined product keeps voice as the **interface**, but makes the real product the **payment lifecycle**:

```text
Merchant speaks about a sale
        ↓
AI extracts transaction details
        ↓
Sale / receivable is created
        ↓
Agent creates a REAL Razorpay Test Mode payment link
        ↓
Customer pays
        ↓
Razorpay webhook reaches backend
        ↓
Payment is matched to the sale
        ↓
FULL / PARTIAL / MISSING / UNMATCHED
        ↓
Agent tells merchant what happened
        ↓
If unpaid → recovery action can be triggered
```

This gives the project a stronger Razorpay connection and a measurable business outcome.

---

# 2. The Problem

Small merchants often need to manage a simple but messy workflow:

- Record what was sold.
- Calculate how much the customer owes.
- Ask the customer to pay.
- Know whether payment actually arrived.
- Identify partial payments.
- Track pending money.
- Follow up on overdue payments.

Traditional billing/khata software often requires manual data entry.

Voice solves the input problem, but **voice recording alone is not the interesting part**.

The harder problem is:

> **Closing the loop between a merchant's spoken sale and the actual payment received.**

Example:

Merchant says:

> "Rahul ko do burger diye, 100 rupaye each."

Expected:

```text
Customer: Rahul
Item: Burger
Quantity: 2
Expected amount: ₹200
```

The system creates a payment request.

If Razorpay later reports ₹200:

```text
Expected: ₹200
Received: ₹200
Status: PAID
```

If Razorpay reports ₹150:

```text
Expected: ₹200
Received: ₹150
Status: PARTIAL
Outstanding: ₹50
```

If no payment arrives:

```text
Expected: ₹200
Received: ₹0
Status: PENDING
```

---

# 3. Product USP

## Primary USP

> **Voice is not the product. Voice is the interface to an AI agent that manages the payment lifecycle.**

The agent can understand natural merchant speech and perform useful financial operations.

### Example

Merchant:

> "Rahul ko do burger diye, 200 rupaye lene hain."

Agent:

1. Understands the sale.
2. Looks up the burger price.
3. Calculates ₹200.
4. Creates a receivable.
5. Creates a Razorpay payment link.
6. Merchant/customer receives the link.
7. Razorpay processes the payment.
8. Webhook reaches the backend.
9. Agent reconciles the payment.
10. Merchant gets a voice/text confirmation.

---

# 4. What We Are NOT Building

Because this is a hackathon project, aggressively control scope.

## Do NOT build

- Full accounting software
- Full inventory management
- GST filing
- Payroll
- CRM
- Full POS system
- Complex mobile application
- Production-grade speaker biometric authentication
- Real-money payment processing
- Large autonomous financial system
- Complex multi-agent architecture

## We ARE building

A polished vertical slice:

> **Voice → Sale → Razorpay Payment Link → Real Test Payment → Webhook → Reconciliation → Outstanding/Recovery**

---

# 5. Razorpay Track

Primary target:

## AI Revenue Recovery

The product can detect money that is still at risk and initiate recovery.

Secondary fit:

## AI Finance Controller

The reconciliation portion matches expected merchant receivables against actual Razorpay payment events.

For the final pitch, position the project around:

> **Recovering and closing outstanding merchant payments through an AI voice agent.**

---

# 6. MVP Features

## P0 — Must Have

These are required for the demo.

### 6.1 Merchant voice input

Support natural English + Hinglish.

Examples:

```text
"Rahul ko 2 burger diye, 100 each."

"Rahul se 300 rupaye lene hain."

"Amit ne 500 UPI kar diya."

"Neha ko 2 pizzas diye, payment abhi pending hai."
```

The speech is converted to text and then structured by an LLM.

---

### 6.2 Product/menu catalog

Simple merchant catalog.

Example:

```json
{
  "burger": 100,
  "cheese burger": 150,
  "pizza": 300,
  "coke": 40
}
```

This can initially be seeded through JSON/database.

Optional voice onboarding:

> "Burger 100, cheese burger 150, pizza 300."

---

### 6.3 Transaction extraction

Convert speech into structured JSON.

Example input:

```text
"Rahul ko 2 burger diye, 100 each."
```

Expected output:

```json
{
  "customer_name": "Rahul",
  "items": [
    {
      "name": "burger",
      "quantity": 2,
      "unit_price": 100
    }
  ],
  "total_amount": 200,
  "payment_status": "pending"
}
```

Use an LLM with structured output/function calling.

---

### 6.4 Receivable creation

Store:

```text
Sale ID
Customer
Items
Expected amount
Created time
Payment status
Razorpay payment link ID
Razorpay payment ID
Outstanding amount
```

---

### 6.5 REAL Razorpay Test Mode integration

This is critical.

Do not simulate the payment system if avoidable.

Use Razorpay Test Mode.

Preferred flow:

```text
Backend
   ↓
Razorpay API
   ↓
Create Payment Link
   ↓
Return short URL
   ↓
Customer opens link
   ↓
Razorpay Test Checkout
   ↓
Test payment
   ↓
Razorpay webhook
   ↓
Backend
```

Use environment variables:

```env
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=
```

Never commit these values.

---

### 6.6 Razorpay webhook handling

The webhook is the source of truth for payment events in the demo.

Backend should receive relevant payment/payment-link events.

Core processing:

```text
Webhook
  ↓
Verify signature
  ↓
Extract payment/link ID
  ↓
Find local receivable
  ↓
Compare expected vs received
  ↓
Update status
```

Statuses:

```text
PENDING
PAID
PARTIAL
FAILED
UNMATCHED
```

---

### 6.7 Reconciliation engine

Simple deterministic logic is sufficient for MVP.

```python
if received == expected:
    status = "PAID"

elif received > 0 and received < expected:
    status = "PARTIAL"

elif received == 0:
    status = "PENDING"
```

Do not over-engineer this.

The AI should explain and act around the result; basic accounting calculations should remain deterministic.

---

### 6.8 Merchant dashboard

One simple web page.

Show:

```text
Today's Sales       ₹12,450

Collected           ₹9,850

Outstanding         ₹2,600

Transactions        27

Paid                19
Partial             3
Pending             5
```

Transaction table:

| Customer | Sale | Expected | Received | Status |
|---|---:|---:|---:|---|
| Rahul | 2 Burger | ₹200 | ₹200 | PAID |
| Amit | Pizza | ₹300 | ₹150 | PARTIAL |
| Neha | Burger | ₹100 | ₹0 | PENDING |

The UI should prioritize clarity over design complexity.

---

# 7. P1 — High-Value Features If Time Allows

## 7.1 Payment recovery

If a payment is pending:

```text
Pending
   ↓
Agent checks age / customer context
   ↓
Recommend recovery
   ↓
Resend payment link
```

Example:

> "Rahul's ₹200 payment is still pending. Should I resend the payment link?"

For a hackathon demo, a button such as:

**Recover Payment**

can trigger the action.

---

## 7.2 Partial payment detection

This is one of the strongest demo moments.

Expected:

```text
₹500
```

Received:

```text
₹300
```

Agent:

> "₹300 received. ₹200 is still outstanding."

---

## 7.3 Natural-language finance queries

Merchant can ask:

> "Aaj kitna paisa pending hai?"

Agent:

> "₹2,600 pending hai across 5 customers."

Other examples:

```text
"Rahul ka payment aaya?"
"Kitna collect hua?"
"Kaunse payments pending hain?"
"Aaj ka total sale kitna hai?"
"Kitna paisa recover karna hai?"
```

---

## 7.4 Recovery prioritization

Calculate a simple priority score.

Example:

```text
priority =
    outstanding_amount
    × overdue_factor
    × customer_payment_probability
```

Then show:

```text
HIGH PRIORITY
Rahul — ₹2,000 — 2 days overdue

MEDIUM
Amit — ₹700 — 1 day overdue

LOW
Neha — ₹100 — 2 hours overdue
```

This creates an actual AI decision layer.

---

# 8. P2 — Optional Features

Only implement if the core flow is already stable.

- Hindi/Hinglish TTS response
- Voice confirmation
- Payment summary
- Daily summary
- Simple analytics
- CSV export
- Merchant onboarding by voice
- Customer-level payment history

---

# 9. Recommended Architecture

Keep the architecture simple.

```text
                    ┌──────────────────────┐
                    │      MERCHANT        │
                    │ Voice / Web UI        │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │     FastAPI API      │
                    └──────────┬───────────┘
                               │
                 ┌─────────────┴─────────────┐
                 │                           │
                 ▼                           ▼
        ┌─────────────────┐        ┌─────────────────┐
        │ Voice/AI Layer  │        │ Payment Service │
        │                 │        │                 │
        │ STT             │        │ Razorpay API    │
        │ LLM             │        │ Webhooks        │
        │ Intent parsing  │        │ Payment Links   │
        └────────┬────────┘        └────────┬────────┘
                 │                          │
                 └────────────┬─────────────┘
                              ▼
                   ┌──────────────────────┐
                   │   Transaction Engine │
                   │                      │
                   │ Sales                │
                   │ Receivables          │
                   │ Reconciliation       │
                   │ Recovery             │
                   └──────────┬───────────┘
                              │
                              ▼
                   ┌──────────────────────┐
                   │      PostgreSQL      │
                   └──────────┬───────────┘
                              │
                              ▼
                   ┌──────────────────────┐
                   │    Merchant UI       │
                   │ Dashboard            │
                   └──────────────────────┘
```

---

# 10. Suggested Tech Stack

## Backend

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- PostgreSQL

## AI

Use an LLM that supports structured JSON/function calling.

Responsibilities:

- Intent detection
- Entity extraction
- Natural-language interpretation
- Merchant Q&A
- Recovery recommendation
- Explanation generation

Do NOT use the LLM for:

- Amount arithmetic
- Payment status truth
- Database updates without validation
- Authentication
- Signature verification

---

## Voice

For the 2-day MVP:

### STT

Use a reliable speech-to-text API/model that handles Hindi/Hinglish reasonably well.

Possible options:

- Whisper
- A hosted speech API
- Browser speech recognition if necessary for demo speed

### TTS

Optional.

If TTS becomes unreliable, use text responses instead.

---

# 11. Database Schema

Keep it small.

## merchants

```text
id
name
created_at
```

## products

```text
id
merchant_id
name
price
created_at
```

## customers

```text
id
merchant_id
name
phone
created_at
```

## sales

```text
id
merchant_id
customer_id
total_amount
status
created_at
```

## sale_items

```text
id
sale_id
product_id
quantity
unit_price
subtotal
```

## payments

```text
id
sale_id
razorpay_payment_id
razorpay_payment_link_id
amount
status
created_at
```

## recovery_actions

```text
id
sale_id
action_type
status
created_at
```

---

# 12. Agent Tools

Do not build a complicated multi-agent system.

Use one orchestrator with tools.

Possible tools:

```text
get_product_price(product_name)
create_sale(customer, items)
create_payment_link(sale_id)
get_sale_status(sale_id)
get_customer_balance(customer)
get_pending_payments()
get_daily_summary()
get_payment_history(customer)
recover_payment(sale_id)
```

The LLM decides which tool to call.

The backend validates every action.

---

# 13. Agent Guardrails

This is important because the product handles money.

## Rules

### Never let the LLM decide payment truth.

Payment truth comes from Razorpay.

### Never allow arbitrary payment amounts.

Amount must be calculated from the transaction/database.

### Require confirmation for important actions.

Example:

> "Send a ₹5,000 payment request to Rahul?"

Merchant:

> "Yes."

Then execute.

### Verify Razorpay webhook signatures.

### Never expose API secrets to the frontend.

### Log every agent action.

---

# 14. Example End-to-End Demo

This should be the main 5-minute demo.

## Scene 1 — Merchant records sale

Merchant speaks:

> "Rahul ko do burger diye, 100 rupaye each."

System:

```text
Rahul
Burger × 2
Expected: ₹200
Payment: Pending
```

---

## Scene 2 — Create real payment request

Agent:

> "₹200 ka payment link ready hai."

Dashboard shows:

```text
Payment Link
₹200
PENDING
```

Open the Razorpay Test Mode checkout.

---

## Scene 3 — Customer pays

Perform a test payment.

Razorpay sends webhook.

Backend:

```text
Webhook received
Payment verified
Sale matched
```

Dashboard changes:

```text
Expected: ₹200
Received: ₹200
Status: PAID ✅
```

Agent:

> "Rahul ka ₹200 payment receive aur verify ho gaya."

---

## Scene 4 — Partial payment

Create another sale:

```text
Amit
Pizza
Expected ₹300
```

Make a ₹150 test payment.

System:

```text
Expected: ₹300
Received: ₹150
Outstanding: ₹150
Status: PARTIAL ⚠️
```

Agent:

> "Amit ne ₹150 pay kiye hain. ₹150 abhi pending hai."

---

## Scene 5 — Ask the agent

Merchant:

> "Aaj kitna paisa pending hai?"

Agent:

> "₹150 pending hai, Amit ka."

Then:

> "Payment link dobara bhej doon?"

Merchant:

> "Yes."

Recovery action executes.

---

# 15. Evaluation Dataset

Create at least 100 synthetic transactions.

Suggested distribution:

```text
40 FULL PAYMENT
20 PARTIAL PAYMENT
20 PENDING
10 FAILED
10 UNMATCHED
```

Include variations:

- Different customers
- Different products
- Different amounts
- Multiple payments
- Similar customer names
- Delayed payments
- Duplicate-looking payments
- Incorrect amounts

## Metrics

### Transaction extraction

```text
Extraction accuracy
```

### Reconciliation

```text
Match accuracy
Precision
Recall
```

### Payment state detection

```text
PAID accuracy
PARTIAL accuracy
PENDING accuracy
```

### Business metric

```text
Total outstanding detected
Total amount recovered
Recovery rate
```

Do not fabricate results. Run the actual test set and report what happens.

---

# 16. Failure Cases

Explicitly demonstrate that the system doesn't blindly trust AI.

### Case 1

Expected ₹500

Received ₹300

→ PARTIAL

### Case 2

Expected ₹500

Received ₹0

→ PENDING

### Case 3

Payment exists but no local sale matches

→ UNMATCHED

### Case 4

Webhook signature invalid

→ Reject webhook

### Case 5

Customer says "I paid"

but Razorpay has no successful payment

→ Do not mark as paid.

Agent:

> "I couldn't verify the payment yet."

This is an important trust feature.

---

# 17. What Makes This Different From Voice-Khata

Do NOT pitch:

> "We are a voice-based khata app."

Pitch:

> **"Existing voice tools help merchants record what happened. VoiceLedger closes the loop by connecting that spoken transaction to an actual payment lifecycle."**

Comparison:

| Existing voice ledger | VoiceLedger |
|---|---|
| Record sale | Record sale |
| Track dues | Track dues |
| Voice interface | Voice interface |
| Payment reminders | Payment recovery |
| Basic ledger | Payment reconciliation |
| May track claimed payment | Verifies actual Razorpay payment |
| Mostly data entry | Agentic payment workflow |

The differentiation is:

> **Expected money → Actual money → Explain the difference → Recover the difference**

---

# 18. Modular Implementation Workflow

This project must **not** be implemented as one giant task.

Claude Code should work module-by-module. Each module must be completed, tested, and recorded before moving to the next module.

## Module 1 — Project foundation

Build:

- Repository structure
- Backend setup
- Environment configuration
- Database connection
- Basic health endpoint

Then:

1. Run the application.
2. Verify the database connection.
3. Run tests.
4. Record what was implemented and any decisions made.
5. Only then move to Module 2.

---

## Module 2 — Merchant, customer and product data

Build:

- Merchant model
- Customer model
- Product/menu model
- Seed/demo data
- Basic CRUD APIs where necessary

Verify:

- Product prices can be retrieved.
- Customers can be created/retrieved.
- Database relationships work.

Record the module as complete before continuing.

---

## Module 3 — AI transaction understanding

This is the **main AI input layer**.

The merchant should be able to provide natural language such as:

> "Rahul ko do burger diye, 100 each."

The AI must convert this into structured information:

```json
{
  "intent": "record_sale",
  "customer_name": "Rahul",
  "items": [
    {
      "product_name": "burger",
      "quantity": 2
    }
  ],
  "payment_status": "pending"
}
```

The backend then looks up the authoritative product price and calculates:

```text
Burger = ₹100
Quantity = 2
Total = ₹200
```

### Important AI boundary

The LLM should **understand language**, not perform financial truth calculations.

LLM responsibilities:

- Intent detection
- Entity extraction
- Understanding Hindi/Hinglish
- Mapping natural language to structured commands
- Generating explanations
- Deciding which permitted tool to call

Backend responsibilities:

- Product price lookup
- Amount calculation
- Database writes
- Payment status
- Razorpay verification
- Reconciliation
- Security/authorization

Test multiple English/Hinglish inputs before moving on.

---

## Module 4 — Sale and receivable engine

Build deterministic business logic for:

- Creating a sale
- Creating sale items
- Calculating total
- Creating a receivable
- Tracking expected amount
- Tracking outstanding amount

Example:

```text
Sale
Expected = ₹500
Received = ₹0
Outstanding = ₹500
Status = PENDING
```

The AI should call this functionality through a controlled backend tool/API.

---

## Module 5 — Razorpay integration

Before implementing this module, read the current Razorpay documentation for the exact APIs available to the project.

The goal is to use **Razorpay Test Mode**, not real customer money.

Primary workflow:

```text
Local sale
    ↓
Backend
    ↓
Razorpay Test Mode API
    ↓
Payment Link / appropriate payment mechanism
    ↓
Razorpay Test Checkout
```

### Why webhooks?

A webhook is useful because the backend needs a reliable server-to-server signal when Razorpay reports that a payment event occurred.

Without a webhook, the demo could rely on:

```text
Frontend asks Razorpay:
"Did this payment succeed?"
```

or on manually refreshing/polling.

With a webhook:

```text
Razorpay
   ↓
Payment event
   ↓
Our backend
   ↓
Update transaction
```

This makes the payment lifecycle realistic.

### Cost question

Do **not assume that every Razorpay webhook or API capability is free**.

For the hackathon:

- Use Razorpay Test Mode wherever possible.
- Confirm the current Razorpay pricing and Test Mode/API/webhook documentation before implementation.
- Do not enable live payments merely for the demo.
- Do not design the project around a paid capability without first verifying its availability.
- If a webhook capability has a restriction, implement the best supported Test Mode alternative and document it honestly.

The objective is **real Razorpay integration in a safe test environment**, not processing real money.

---

## Module 6 — Razorpay event ingestion

Implement:

```text
Razorpay event
    ↓
Webhook endpoint
    ↓
Signature verification
    ↓
Parse event
    ↓
Find corresponding local payment/sale
    ↓
Store event
```

Important:

- Never trust an arbitrary frontend request saying "payment successful."
- Never let the LLM decide that a payment happened.
- Payment status should come from a verified Razorpay event or an officially supported Razorpay API response.

Add idempotency so the same event cannot incorrectly update the transaction multiple times.

---

## Module 7 — Reconciliation engine

Keep this deterministic.

Input:

```text
Expected amount
Actual received amount
Payment state
Sale/payment mapping
```

Output:

```text
PAID
PARTIAL
PENDING
FAILED
UNMATCHED
```

Example:

```text
Expected = ₹500
Received = ₹500
→ PAID
```

```text
Expected = ₹500
Received = ₹300
→ PARTIAL
Outstanding = ₹200
```

```text
Expected = ₹500
Received = ₹0
→ PENDING
```

The AI can **explain** the result, but the reconciliation calculation itself should be ordinary backend code.

---

## Module 8 — Agent orchestration

Only after the deterministic backend workflow works should the AI agent be added around it.

The agent receives merchant requests and chooses from safe tools such as:

```text
get_product_price()
create_sale()
create_payment_request()
get_payment_status()
get_customer_balance()
get_pending_payments()
get_daily_summary()
recover_payment()
```

Example:

Merchant:

> "Rahul ko do burger diye."

Agent:

```text
Understand request
        ↓
get_product_price("burger")
        ↓
create_sale(...)
        ↓
create_payment_request(...)
```

The agent should not directly modify the database or call unrestricted payment APIs.

All actions go through validated backend tools.

---

## Module 9 — Recovery workflow

Add recovery only after payment creation and reconciliation work.

Example:

```text
PENDING / PARTIAL
       ↓
Agent identifies outstanding amount
       ↓
Checks permitted recovery rules
       ↓
Asks merchant for confirmation when required
       ↓
Resends/creates appropriate payment request
       ↓
Waits for verified payment event
       ↓
Updates outstanding amount
```

Example:

> "Amit still owes ₹200. Should I resend the payment request?"

Merchant:

> "Yes."

Then the backend performs the action.

---

## Module 10 — Merchant dashboard

Build the dashboard after the backend workflow is stable.

Show:

```text
Today's Sales
Collected
Outstanding
Pending
Partial
```

And a transaction table:

| Customer | Expected | Received | Outstanding | Status |
|---|---:|---:|---:|---|
| Rahul | ₹200 | ₹200 | ₹0 | PAID |
| Amit | ₹300 | ₹150 | ₹150 | PARTIAL |
| Neha | ₹100 | ₹0 | ₹100 | PENDING |
```

---

## Module 11 — Evaluation

Create a controlled synthetic dataset.

Include:

- Full payments
- Partial payments
- Pending payments
- Failed payments
- Unmatched payments
- Multiple customers
- Similar customer names
- Different products
- Different amounts
- English/Hinglish voice/text inputs

Measure separately:

### AI extraction

- Intent accuracy
- Entity extraction accuracy
- Product identification accuracy

### Payment/reconciliation

- Match precision
- Match recall
- Partial-payment detection
- Incorrect-match rate

### Business outcome

- Outstanding amount identified
- Payments recovered
- Recovery rate

Do not fabricate metrics.

---

## Module 12 — Final integration and demo

Only after every previous module is independently working:

```text
Voice/Text
   ↓
AI Understanding
   ↓
Validated Tool Call
   ↓
Sale
   ↓
Razorpay Test Mode
   ↓
Payment
   ↓
Verified Event
   ↓
Reconciliation
   ↓
Dashboard
   ↓
Recovery
```

Run the complete flow from a clean environment.

# 19. Suggested Repository Structure

```text
voiceledger/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   │
│   │   ├── api/
│   │   │   ├── voice.py
│   │   │   ├── sales.py
│   │   │   ├── payments.py
│   │   │   ├── webhooks.py
│   │   │   └── dashboard.py
│   │   │
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   │   ├── llm_service.py
│   │   │   ├── voice_service.py
│   │   │   ├── razorpay_service.py
│   │   │   ├── reconciliation_service.py
│   │   │   └── recovery_service.py
│   │   │
│   │   ├── agents/
│   │   │   └── merchant_agent.py
│   │   │
│   │   └── db/
│   │
│   ├── tests/
│   └── requirements.txt
│
├── frontend/
│   └── ...
│
├── data/
│   ├── products.json
│   └── evaluation_transactions.json
│
├── evaluation/
│   ├── generate_data.py
│   └── evaluate.py
│
├── docs/
│   ├── architecture.md
│   └── demo.md
│
├── .env.example
├── .gitignore
├── docker-compose.yml
└── README.md
```

---

# 20. Claude Code Instructions

Claude Code must treat `PROJECT_PLAN.md` as the source of truth.

### Critical development rule

**DO NOT implement the entire project in one task.**

Work through the numbered modules in order.

For every module:

1. Read the relevant section of `PROJECT_PLAN.md`.
2. State the exact scope of the current module.
3. Implement only that module.
4. Run the relevant tests.
5. Manually verify the important behavior.
6. Fix errors before proceeding.
7. Record the completed work in a project progress log, for example:
   `docs/IMPLEMENTATION_LOG.md`.
8. Record:
   - module completed
   - files changed
   - important technical decisions
   - tests run/results
   - known limitations
   - next module
9. Stop and wait for the next instruction before starting a new major module.

### Do not skip ahead

Do not implement advanced agent behavior, recovery, dashboard polish or extra features while an earlier core module is incomplete.

Do not rewrite working modules simply to introduce a new architecture.

### AI architecture rule

The LLM is NOT the source of financial truth.

Use AI for:

- Natural-language understanding
- Intent classification
- Entity extraction
- English/Hinglish understanding
- Tool selection
- Explanations
- Natural-language responses

Use deterministic backend code for:

- Prices
- Arithmetic
- Database writes
- Payment status
- Razorpay event verification
- Reconciliation
- Authorization
- Security rules

### Razorpay rule

Use Razorpay Test Mode where supported.

Before implementing Razorpay functionality, verify the current official documentation for the exact API/event/capability being used.

Never invent Razorpay endpoints or webhook event names.

Never commit secrets.

### Quality rule

A smaller working module is better than a large incomplete implementation.

At every stage, preserve a runnable application.

### Suggested first instruction

Start with **Module 1 only**.

Do not implement Module 2 or any later module until Module 1 is complete, tested and recorded in `docs/IMPLEMENTATION_LOG.md`.

---

# 21. Recommended Implementation Order

Claude Code should implement in exactly this order:

```text
1. Project setup
       ↓
2. Database models
       ↓
3. Product/customer seed data
       ↓
4. Sale API
       ↓
5. LLM transaction extraction
       ↓
6. Razorpay Test Mode integration
       ↓
7. Payment Link creation
       ↓
8. Razorpay webhook
       ↓
9. Reconciliation
       ↓
10. Dashboard
       ↓
11. Agent tools
       ↓
12. Payment recovery
       ↓
13. Evaluation dataset
       ↓
14. Metrics
       ↓
15. Demo polish
```

Do not start with the UI.

Do not start with advanced voice authentication.

Do not start with autonomous recovery.

First make this work:

```text
Create sale
    ↓
Create Razorpay payment link
    ↓
Make test payment
    ↓
Receive webhook
    ↓
Mark sale PAID
```

That is the project's critical path.

---

# 22. Final Pitch

## Problem

> Small merchants can easily record a sale, but tracking whether the expected money actually arrives, identifying partial payments and recovering outstanding money is still operationally difficult.

## Solution

> VoiceLedger is an AI voice-first payment collection agent that converts natural merchant speech into structured sales, creates Razorpay payment requests, verifies real payment events, automatically reconciles expected vs received amounts, and helps merchants recover outstanding payments.

## USP

> **Don't just record the sale. Close the payment loop.**

## Demo result

Show:

```text
100 Transactions
       ↓
Automatically reconciled
       ↓
Full payments
Partial payments
Pending payments
Unmatched payments
       ↓
₹X outstanding detected
₹Y successfully recovered
```

---

# 23. Success Criteria

The project is successful if the following works live:

- Merchant speaks a sale.
- AI correctly extracts the transaction.
- Backend calculates the correct amount.
- Razorpay Test Mode payment link is created.
- Test payment is completed.
- Real Razorpay webhook reaches backend.
- Backend verifies the webhook.
- Sale is automatically reconciled.
- Partial payment is correctly detected.
- Merchant can ask how much is pending.
- Agent can trigger a recovery action.
- Dashboard reflects the correct state.
- Evaluation results are measurable.

## The golden rule

> **A smaller system that works end-to-end with a real Razorpay integration is much stronger than a huge AI system full of mocked functionality.**
