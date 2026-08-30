# VoiceLedger — User Setup, API Keys & Configuration Guide

Welcome to **VoiceLedger**! This guide explains how to configure your API keys, run the application, and use voice to record product sales and check payment arrival.

---

## 1. Quick Start

### Step 1: Install Backend & Frontend Dependencies
```bash
# Backend (using uv or pip)
uv sync
# or: pip install -r backend/requirements.txt

# Frontend (React Native Universal Web & Mobile)
cd frontend
npm install
cd ..
```

### Step 2: Run the Backend & React Native Frontend

#### Option A: Run Unified Fullstack (FastAPI serves React Native Web build)
```bash
# 1. Build the React Native web bundle once:
cd frontend && npm run build:web && cd ..

# 2. Start the VoiceLedger server:
python main.py
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser.

---

#### Option B: Run Universal Live Dev Server (for Smartphone & Web)
```bash
# 1. Start Backend:
python main.py

# 2. In a new terminal, start Expo React Native:
cd frontend
npx expo start
```
- **Web**: Press `w` in terminal or open **[http://localhost:8081](http://localhost:8081)**.
- **Smartphone (iOS / Android)**:
  1. Install the free **Expo Go** app from App Store or Google Play on your phone.
  2. Make sure your phone and computer are on the same Wi-Fi.
  3. Scan the QR code shown in your terminal with your phone's camera (iOS) or Expo Go app (Android).
  4. In the app header, tap the ⚙️ settings icon and set your computer's local IP (e.g. `http://192.168.1.X:8000/api`) to connect to your backend.

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
