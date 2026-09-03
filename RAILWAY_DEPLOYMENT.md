# VoiceLedger — Complete Railway Deployment Guide

This guide walks you step-by-step through deploying VoiceLedger (FastAPI API, PostgreSQL, Redis, and Background Outbox Worker) on [Railway.app](https://railway.app) with live Razorpay Webhooks and real-time Soundbox WebSockets.

---

## Architecture on Railway

Your Railway Project will contain **4 interconnected services**:

```text
┌─────────────────────────────────────────────────────────────┐
│                       Railway Project                       │
│                                                             │
│   ┌───────────────────────────┐ ┌───────────────────────┐   │
│   │ Managed PostgreSQL (v16)  │ │   Managed Redis (v7)  │   │
│   │   (Authoritative Ledger)  │ │ (Real-Time Event Bus) │   │
│   └─────────────┬─────────────┘ └───────────┬───────────┘   │
│                 │                           │               │
│                 ├───────────────────────────┤               │
│                 │                           │               │
│   ┌─────────────▼─────────────┐ ┌───────────▼───────────┐   │
│   │    voiceledger-api        │ │   voiceledger-worker  │   │
│   │  (FastAPI + WebSockets)   │ │  (Outbox Event Poller)│   │
│   │    Public HTTPS Domain    │ │    Background Daemon  │   │
│   └─────────────▲─────────────┘ └───────────────────────┘   │
└─────────────────┼───────────────────────────────────────────┘
                  │
        Public Internet (HTTPS / WSS)
                  │
  ┌───────────────┴───────────────┐
  │                               │
  ▼                               ▼
Razorpay Webhook               Soundbox Hardware / Client
(payment.captured)             (wss://.../ws/device)
```

---

## Step 1: Create Railway Project & Add Databases

1. Log into your [Railway Dashboard](https://railway.app).
2. Click **"New Project"** $\rightarrow$ **"Provision PostgreSQL"**.
   - Railway will spin up a fully managed PostgreSQL 16 database.
3. In the same project canvas, click **"+ New"** $\rightarrow$ **"Database"** $\rightarrow$ **"Add Redis"**.
   - Railway will spin up a fully managed Redis 7 database.

---

## Step 2: Deploy the Web API Service (`voiceledger-api`)

1. In the project canvas, click **"+ New"** $\rightarrow$ **"GitHub Repo"**.
2. Select your repository (e.g. `JetJerry/voiceLedger` or `razorpay`).
3. Select the branch: `feature/connection` (or your main branch).
4. Click on the newly created service card and rename it to `voiceledger-api`.

### Configure Environment Variables
Go to the **"Variables"** tab of `voiceledger-api` and add:

| Variable | Value | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | Railway variable reference linking to your PostgreSQL instance. |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` | Railway variable reference linking to your Redis instance. |
| `APP_ENV` | `production` | Sets production mode. |
| `JWT_SECRET` | *(generate a 32+ char key)* | Secret key for JWT signing. (e.g., run `python -c "import secrets; print(secrets.token_hex(32))"`) |
| `RAZORPAY_KEY_ID` | `rzp_test_...` | Your Razorpay Test Mode Key ID. |
| `RAZORPAY_KEY_SECRET` | `...` | Your Razorpay Key Secret. |
| `RAZORPAY_WEBHOOK_SECRET` | `...` | Dedicated secret for HMAC-SHA256 signature verification. |
| `CORS_ALLOWED_ORIGINS` | `*` | Allowed CORS origins for merchant dashboard access. |

### Generate Public Domain
1. In the `voiceledger-api` service, navigate to **Settings** $\rightarrow$ **Networking**.
2. Click **"Generate Domain"**.
3. Railway will assign a public HTTPS domain: e.g. `https://voiceledger-api-production.up.railway.app`.

*(On first deploy, `scripts/start.sh` automatically runs Alembic database migrations and starts Uvicorn).*

---

## Step 3: Deploy the Outbox Worker Service (`voiceledger-worker`)

The outbox worker continuously queries PostgreSQL for `PENDING` outbox events and publishes them to Redis.

1. In the same Railway project canvas, click **"+ New"** $\rightarrow$ **"GitHub Repo"** again and select the same repository.
2. Click on this new service card and rename it to `voiceledger-worker`.
3. Go to **Settings** $\rightarrow$ **Deploy** $\rightarrow$ **Custom Start Command**:
   - Enter:
     ```bash
     python -m backend.app.worker
     ```
4. Go to the **Variables** tab of `voiceledger-worker` and add:
   - `DATABASE_URL`: `${{Postgres.DATABASE_URL}}`
   - `REDIS_URL`: `${{Redis.REDIS_URL}}`
   - `APP_ENV`: `production`
5. Click **Deploy**.

---

## Step 4: Configure Razorpay Webhook (Direct Cloud Webhooks)

Because Railway provides a publicly accessible HTTPS domain with valid SSL certificates, you do **NOT** need ngrok or local tunnels in production!

1. Log into your [Razorpay Dashboard](https://dashboard.razorpay.com).
2. Switch to **Test Mode** (toggle on the top-left/top-right).
3. Navigate to **Settings** $\rightarrow$ **Webhooks** $\rightarrow$ **Add New Webhook**.
4. Fill in the webhook form:
   - **Webhook URL**:
     ```text
     https://<your-railway-domain>.up.railway.app/api/v1/webhooks/razorpay
     ```
   - **Secret**: The exact value you set in `RAZORPAY_WEBHOOK_SECRET`.
   - **Active Events**: Check `payment.captured`.
5. Click **Save**.

---

## Step 5: Verify Live Cloud Deployment

### 1. Verify Health Check:
Open your browser or run:
```bash
curl -f https://<your-railway-domain>.up.railway.app/health
```
Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "service": "VoiceLedger",
  "version": "1.0.0",
  "environment": "production"
}
```

### 2. Verify WebSocket Connectivity:
Soundboxes and merchant dashboards connect natively via WebSockets using `wss://`:
- **Soundbox Endpoint**:
  ```text
  wss://<your-railway-domain>.up.railway.app/ws/device?token=devsess_<token>
  ```
- **Merchant Dashboard Endpoint**:
  ```text
  wss://<your-railway-domain>.up.railway.app/ws/merchant?token=<jwt_access_token>
  ```

---

## Step 6: Perform Live Test Payment

1. Create a Payment Link or trigger a test payment in the Razorpay Dashboard.
2. Complete the payment using Razorpay's test UPI / Card simulator.
3. Razorpay sends the signed `payment.captured` webhook to your Railway API.
4. Check your Railway service logs:
   - **`voiceledger-api`**: Logs signature verification `[INFO] POST /api/v1/webhooks/razorpay -> 200`, persists `Payment` as `CAPTURED`, and creates `OutboxEvent`.
   - **`voiceledger-worker`**: Logs claiming the outbox event and publishing to Redis channel `voiceledger:merchant:{id}:events`.
   - **WebSocket**: Streams the localized vernacular voice announcement to the connected Soundbox device in real time!
