# VoiceLedger — User Setup, API Keys & Configuration Guide

Welcome to **VoiceLedger**! This guide walks you through setting up your API keys, database, webhook listener, and running the application.

---

## 1. Quick Start (Run in Under 1 Minute)

VoiceLedger comes with **zero-config defaults** and an **interactive simulator**, so you can start testing immediately without entering any keys upfront!

### Step 1: Install Dependencies
```bash
# Using uv (Recommended)
uv sync

# Or using standard pip
pip install -r backend/requirements.txt
```

### Step 2: Launch VoiceLedger
```bash
python main.py
```

### Step 3: Open in Browser
Visit **[http://localhost:8000](http://localhost:8000)** in Google Chrome or Microsoft Edge (for microphone voice support).

---

## 2. API Keys & Configuration

To connect real Razorpay Test Mode payments and live Google Gemini AI, copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Here are the environment variables configured in `.env`:

| Variable | Description | Where to Get It |
|---|---|---|
| `RAZORPAY_KEY_ID` | Your Razorpay Test Key ID | [Razorpay Dashboard > API Keys](https://dashboard.razorpay.com/app/keys) |
| `RAZORPAY_KEY_SECRET` | Your Razorpay Test Key Secret | [Razorpay Dashboard > API Keys](https://dashboard.razorpay.com/app/keys) |
| `RAZORPAY_WEBHOOK_SECRET` | Webhook Secret for signature verification | [Razorpay Dashboard > Settings > Webhooks](https://dashboard.razorpay.com/app/webhooks) |
| `GEMINI_API_KEY` | Google Gemini API Key | [Google AI Studio](https://aistudio.google.com/) |
| `DATABASE_URL` | Database Connection URL | SQLite default (`sqlite:///./voiceledger.db`) or PostgreSQL |

---

## 3. How to Get Your Razorpay Test Mode Keys

1. Sign up / Log in to **[Razorpay Dashboard](https://dashboard.razorpay.com/)**.
2. Switch the toggle in the top-right to **Test Mode** (ensure it says *Test Mode* in orange/blue).
3. Go to **Settings** → **API Keys** → Click **Generate Test Key**.
4. Copy:
   - **Key ID** (starts with `rzp_test_...`)
   - **Key Secret**
5. Paste them into your `.env` file:
   ```env
   RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxxxxxx
   RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
   ```

---

## 4. How to Configure Razorpay Webhooks

Webhooks allow Razorpay to notify VoiceLedger in real-time when a customer completes a payment.

### For Local Development (using ngrok)
1. Start an ngrok tunnel on port 8000:
   ```bash
   ngrok http 8000
   ```
2. Copy your forwarding URL (e.g. `https://abcd-1234.ngrok-free.app`).
3. In Razorpay Dashboard, go to **Settings** → **Webhooks** → Click **Add New Webhook**.
4. Set:
   - **Webhook URL**: `https://abcd-1234.ngrok-free.app/api/webhooks/razorpay`
   - **Secret**: Enter a secure password (e.g. `my_secret_webhook_123`)
   - **Active Events**:
     - `payment_link.paid`
     - `payment_link.partially_paid`
     - `payment.captured`
     - `payment.failed`
5. Save the webhook and add the secret to `.env`:
   ```env
   RAZORPAY_WEBHOOK_SECRET=my_secret_webhook_123
   ```

> [!TIP]
> **No ngrok? No problem!**
> You can test reconciliation instantly on the dashboard by clicking the **⚡ Simulate Pay** button on any transaction.

---

## 5. How to Get Your Google Gemini API Key

1. Visit **[Google AI Studio](https://aistudio.google.com/)**.
2. Click **Get API Key** → **Create API Key**.
3. Copy the key and paste it into `.env`:
   ```env
   GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxxx
   ```
*(If no Gemini key is provided, VoiceLedger automatically uses its built-in rule-based Hindi/Hinglish NLP parser).*

---

## 6. Database Setup Options

### Option A: SQLite (Default — Zero Config)
No database server installation required. VoiceLedger automatically creates and manages `voiceledger.db` in your project folder.

### Option B: PostgreSQL with Docker Compose
If you prefer PostgreSQL:
```bash
docker-compose up -d
```
This starts a PostgreSQL 16 container on port `5432` and connects the app.

---

## 7. How to Use the Merchant Dashboard

1. **Speak a Sale**: Click the **Microphone** button and say:
   - *"Rahul ko do burger aur ek coke diya"*
   - *"Amit se 300 rupaye lene hain"*
2. **View Payment Link**: VoiceLedger extracts the items, calculates the total from the authoritative catalog, and generates a **Razorpay Payment Link**.
3. **Simulate / Pay**:
   - Click **💳 Pay Link** to open Razorpay's checkout page.
   - Or click **⚡ Simulate Pay** to test Full (100%) or Partial (50%) payment reconciliation.
4. **Instant Reconciliation**:
   - Dashboard automatically updates the status tag: `PAID` ✅, `PARTIAL` ⚠️, or `PENDING` ⏳.
5. **Recover Pending Payments**:
   - If a payment is partial or pending, it automatically enters the **AI Revenue Recovery Queue**.
   - Click **💬 Resend WhatsApp Reminder** to open a pre-filled WhatsApp recovery chat with the customer!

---

## 8. Running Automated Tests & Benchmark

### Run the 16 Unit & Integration Tests:
```bash
uv run pytest -v
```

### Run the 100-Transaction Evaluation Benchmark:
```bash
uv run python -m evaluation.evaluate
```

This runs 100 diverse scenarios (Full payments, Partial payments, Pending bills, Failed payments, Unmatched records) and prints the comprehensive accuracy and recovery metrics.
