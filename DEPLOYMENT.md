# 🚀 VoiceLedger Cloud Deployment Guide
## Backend on **Modal** (`modal.com`) & Frontend on **Vercel** (`vercel.com`)

---

## 🏗️ Architecture Overview

```
 ┌───────────────────────────┐                ┌───────────────────────────────┐
 │   Vercel Cloud Edge       │  HTTPS REST    │    Modal Serverless Backend   │
 │   React Native Web (SPA)  │ ─────────────> │    FastAPI + Whisper STT      │
 │   (your-app.vercel.app)   │                │    + Neural TTS + SQLite Vol  │
 └───────────────────────────┘                └───────────────────────────────┘
                                                              │
                                                              ▼
                                                   ┌─────────────────────┐
                                                   │ Razorpay Webhooks & │
                                                   │ Google Gemini 2.5   │
                                                   └─────────────────────┘
```

---

## 1️⃣ Deploy Backend on Modal

[Modal](https://modal.com/) is a serverless cloud platform for Python with persistent volumes and optional GPU acceleration.

### Step 1: Install and Authenticate Modal CLI
```bash
# 1. Install Modal CLI
pip install modal

# 2. Authenticate with your Modal account (opens browser)
modal setup
```

### Step 2: Configure Modal Secrets
Create a secret named `voice_ledger` in Modal with your environment variables:
```bash
modal secret create voice_ledger \
  DATABASE_URL="sqlite:////data/voiceledger.db" \
  GEMINI_API_KEY="your_gemini_api_key_here" \
  RAZORPAY_KEY_ID="rzp_test_xxxxxx" \
  RAZORPAY_KEY_SECRET="your_razorpay_secret" \
  RAZORPAY_WEBHOOK_SECRET="your_webhook_secret"
```
*(Or create it in the Modal Web Dashboard under **Secrets > Create Secret** with name `voice_ledger`)*.

### Step 3: Deploy the Backend
From the project root directory (`d:\razorpay`), run:
```bash
modal deploy modal_app.py
```

### Step 4: Copy your Live Modal Backend URL
Modal will output your live URL, for example:
```
✓ Created web endpoint: https://<your-workspace>--voiceledger-backend-fastapi-app.modal.run
```
Test health check in browser:
`https://<your-workspace>--voiceledger-backend-fastapi-app.modal.run/api/health`

---

## 2️⃣ Deploy Frontend on Vercel

### Method A: Connect GitHub Repository (Recommended)
1. Push your repository to **GitHub / GitLab / Bitbucket**.
2. Go to [Vercel Dashboard](https://vercel.com/new) and click **"Add New Project"** -> **"Import Git Repository"**.
3. Configure Project Settings:
   - **Root Directory**: Select `frontend` (or click Edit and choose `frontend`).
   - **Framework Preset**: `Other`
   - **Build Command**: `npx expo export -p web` (or `npm run build`)
   - **Output Directory**: `dist`
4. Add **Environment Variable** in Vercel:
   | Key | Value |
   | :--- | :--- |
   | `EXPO_PUBLIC_API_URL` | `https://<your-workspace>--voiceledger-backend-fastapi-app.modal.run` |
5. Click **"Deploy"**.

---

### Method B: Deploy using Vercel CLI
```bash
# 1. Install Vercel CLI
npm install -g vercel

# 2. Navigate to frontend directory
cd frontend

# 3. Deploy
vercel --prod --env EXPO_PUBLIC_API_URL="https://<your-workspace>--voiceledger-backend-fastapi-app.modal.run"
```

---

## 3️⃣ Configure Razorpay Webhooks

To receive live payment updates from Razorpay customers:
1. Log in to [Razorpay Dashboard](https://dashboard.razorpay.com/app/webhooks).
2. Click **"Add New Webhook"**.
3. **Webhook URL**:
   ```
   https://<your-workspace>--voiceledger-backend-fastapi-app.modal.run/api/webhooks/razorpay
   ```
4. **Secret**: Enter the same value as `RAZORPAY_WEBHOOK_SECRET`.
5. **Active Events**:
   - `payment_link.paid`
   - `payment.captured`
   - `payment.failed`
6. Save the webhook.

---

## 🧪 Local Testing & Verification

### Test Modal locally in ephemeral dev mode:
```bash
modal serve modal_app.py
```

### Run local test suite:
```bash
uv run pytest backend/tests/ -v
```
