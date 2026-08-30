# VoiceLedger — User Setup, API Keys & Configuration Guide

Welcome to **VoiceLedger**! This guide explains how to configure your API keys, run the application, and use voice to record product sales and check payment arrival.

---

## 1. Quick Start

### Step 1: Install Dependencies
```bash
# Using uv (Recommended)
uv sync

# Or using pip
pip install -r backend/requirements.txt
```

### Step 2: Run VoiceLedger
```bash
python main.py
```

### Step 3: Open in Browser
Visit **[http://localhost:8000](http://localhost:8000)** in Google Chrome or Microsoft Edge.

---

## 2. API Keys & Configuration

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

| Variable | Description | Where to Get It |
|---|---|---|
| `RAZORPAY_KEY_ID` | Your Razorpay Test Key ID | [Razorpay Dashboard > API Keys](https://dashboard.razorpay.com/app/keys) |
| `RAZORPAY_KEY_SECRET` | Your Razorpay Test Key Secret | [Razorpay Dashboard > API Keys](https://dashboard.razorpay.com/app/keys) |
| `RAZORPAY_WEBHOOK_SECRET` | Webhook Secret for signature verification | [Razorpay Dashboard > Settings > Webhooks](https://dashboard.razorpay.com/app/webhooks) |
| `GEMINI_API_KEY` | Google Gemini API Key | [Google AI Studio](https://aistudio.google.com/) |
| `DATABASE_URL` | Database Connection URL | SQLite default (`sqlite:///./voiceledger.db`) or PostgreSQL |

---

## 3. How to Use VoiceLedger

1. **Speak a Sold Product**:
   - Click the **Microphone** button or type:
     - *"2 coffee 60 rupaye"*
     - *"3 notebook 150 rs"*
     - *"1 pizza 300 rupaye"*
   - VoiceLedger creates the sale and generates a **Razorpay Payment Link**.

2. **Customer Pays / Simulate Payment**:
   - Customer pays via the Razorpay link.
   - Or click **⚡ Pay Simulate** on the dashboard to simulate receiving full or partial payment instantly.

3. **Check Payment Arrival via Voice**:
   - Click the **Microphone** button and ask:
     - *"Payment aaya kya?"*
     - *"Coffee ka payment aaya kya?"*
   - VoiceLedger Agent inspects real Razorpay payment state and replies immediately:
     - *"Haan! 2x coffee ka Rs. 60 payment receive ho chuka hai (PAID ✅)."*
     - *"Nahi, 2x coffee ka Rs. 60 payment abhi tak nahi aaya hai (PENDING ⏳)."*
     - *"Rs. 30 receive hua hai, Rs. 30 abhi pending hai (PARTIAL ⚠️)."*

---

## 4. Running Tests & Benchmarks

```bash
# Run 16 Unit & Integration Tests
uv run pytest -v

# Run 100-Transaction Evaluation Benchmark
uv run python -m evaluation.evaluate
```
