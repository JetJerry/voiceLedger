# VoiceLedger — Render Deployment Guide

Complete step-by-step instructions for deploying **VoiceLedger** to [Render](https://render.com) using your current development branch: **`feature/connection`**.

> [!IMPORTANT]
> **Branch Notice**: Do **NOT** merge or push to `main`. This deployment is configured specifically for your current branch: **`feature/connection`**. When configuring the service or Blueprint on Render, ensure the branch is set to `feature/connection`.

---

## Architecture on Render

```text
                               ┌──────────────────────────────────────────────────────────┐
                               │                    Render Web Service                    │
                               │                  (Docker Container)                      │
                               │                                                          │
Razorpay Webhook (HTTPS)  ───► │  /api/v1/webhooks/razorpay                               │
                               │         ↓                                                │
                               │  FastAPI (Uvicorn) ──── Transactional Outbox (Postgres)  │
                               │         │                                                │
Soundbox Device (WSS)     ───► │  /ws/device                                              │
                               │         ▲                                                │
                               │         │                                                │
                               │  Outbox Worker (Background PID)                          │
                               │         │                                                │
                               └─────────┼──────────────────────────┼─────────────────────┘
                                         ▼                          ▼
                          ┌───────────────────────────┐    ┌─────────────────┐
                          │     Render PostgreSQL     │    │ Render KeyValue │
                          │     (Managed Database)    │    │ (Redis Pub/Sub) │
                          └───────────────────────────┘    └─────────────────┘
```

The container uses `scripts/start.sh` to automatically:
1. Run database schema migrations (`alembic upgrade head`).
2. Start the transactional outbox worker in the background (`python -m backend.app.worker &`).
3. Start Uvicorn on Render's dynamic `$PORT`.

---

## Deployment Options

Choose either **Option A (Render Blueprint — Recommended)** or **Option B (Manual Dashboard Setup)**.

---

### Option A: 1-Click Deployment via Blueprint (`render.yaml`)

Render Blueprints allow you to provision PostgreSQL, Key-Value (Redis), and the Web Service together in a single click using the included [render.yaml](file:///d:/razorpay/render.yaml).

#### Step 1: Push Current Branch
Ensure your changes on `feature/connection` are pushed to GitHub:
```bash
git push origin feature/connection
```

#### Step 2: Create Blueprint in Render
1. Log in to [dashboard.render.com](https://dashboard.render.com).
2. Click **New +** in the top navigation bar and select **Blueprint**.
3. Connect your GitHub repository: `JetJerry/voiceLedger` (or your personal fork).
4. In the **Branch** dropdown, select **`feature/connection`** (do not select `main`).
5. Render will automatically detect `render.yaml` and display the resources to be created:
   - `voiceledger-db` (PostgreSQL)
   - `voiceledger-redis` (Key-Value / Redis)
   - `voiceledger-api` (Web Service)
6. Fill in the required environment variables prompted by Render:
   - `RAZORPAY_KEY_ID`: Your Razorpay Key ID (e.g. `rzp_test_...`)
   - `RAZORPAY_KEY_SECRET`: Your Razorpay Key Secret
   - `RAZORPAY_WEBHOOK_SECRET`: A high-entropy secret string for verifying incoming webhooks (e.g., generate a 32-char hex string)
7. Click **Apply**.
8. Render will provision the database, start Redis, build the Docker container, run migrations, and launch your API!

---

### Option B: Manual Dashboard Setup (Step-by-Step)

If you prefer creating the services manually in the Render dashboard (e.g. to use an external free Redis like Upstash), follow these steps:

#### Step 1: Provision PostgreSQL
1. On the Render Dashboard, click **New +** → **PostgreSQL**.
2. Configure:
   - **Name**: `voiceledger-db`
   - **Database**: `voiceledger`
   - **User**: `voiceledger_user`
   - **Region**: Select your preferred region (e.g. `Oregon` or `Singapore`)
   - **Plan**: `Free`
3. Click **Create Database**.
4. Once created, copy the **Internal Database URL** (e.g. `postgres://voiceledger_user:...@dpg-...:5432/voiceledger`).

#### Step 2: Provision Redis (Render Key-Value or Upstash)
- **Choice 1 (Render Key-Value)**:
  1. Click **New +** → **Key-Value (Redis)**.
  2. Name: `voiceledger-redis`.
  3. Plan: `Free`.
  4. Region: Same region as your database.
  5. Click **Create Key-Value** and copy the **Internal Connection String** (`redis://...`).
- **Choice 2 (Upstash Redis — 100% Free Tier with TLS)**:
  1. Go to [console.upstash.com](https://console.upstash.com), create a free Redis database in the same region.
  2. Copy the `rediss://default:...@...upstash.io:6379` connection string.

#### Step 3: Create the Web Service
1. Click **New +** → **Web Service**.
2. Connect your GitHub repository.
3. Configure the service settings:
   - **Name**: `voiceledger-api`
   - **Branch**: **`feature/connection`** ⚠️ *(Ensure this is not set to `main`)*
   - **Region**: Same region as your database and Redis.
   - **Language / Environment**: **Docker**
   - **Dockerfile Path**: `./Dockerfile`
   - **Plan**: `Free`
4. Under **Environment Variables**, add:

| Key | Value / Source | Description |
| :--- | :--- | :--- |
| `APP_ENV` | `production` | Enables production security checks |
| `DATABASE_URL` | *(Internal Postgres URL)* | Render internal connection string |
| `REDIS_URL` | *(Internal Redis URL)* | Render or Upstash connection string |
| `RUN_WORKER` | `true` | Runs outbox worker in background of the container |
| `JWT_SECRET` | *(Random 32+ char string)* | Signing secret for authentication |
| `SOUNDBOX_SIGNING_SECRET` | *(Random 32+ char string)* | HMAC secret for soundbox device authentication |
| `CORS_ALLOWED_ORIGINS` | `*` | Allowed origins (or specify your merchant frontend domain) |
| `RAZORPAY_KEY_ID` | `rzp_test_...` | Razorpay Test Key ID |
| `RAZORPAY_KEY_SECRET` | *(Your Secret)* | Razorpay Test Key Secret |
| `RAZORPAY_WEBHOOK_SECRET` | *(Your Webhook Secret)* | Razorpay Webhook Signing Secret |

5. Under **Health Check Path**, enter: `/health`
6. Click **Create Web Service**.

Render will pull `feature/connection`, build the Docker image, run migrations via `scripts/start.sh`, start the background outbox worker, and expose your service on `https://<service-name>.onrender.com`.

---

## Configuring Razorpay Test Mode Webhook

To receive live payment notifications from Razorpay:

1. Open the [Razorpay Dashboard](https://dashboard.razorpay.com) in **Test Mode**.
2. Navigate to **Settings** → **Webhooks** → **+ Add New Webhook**.
3. Configure:
   - **Webhook URL**:
     ```text
     https://<your-service-name>.onrender.com/api/v1/webhooks/razorpay
     ```
   - **Secret**: Enter the exact secret string you set for `RAZORPAY_WEBHOOK_SECRET` on Render.
   - **Alert Email**: Your email address.
   - **Active Events**:
     - `payment.captured`
     - `order.paid`
4. Click **Save Webhook**.

---

## Connecting the Soundbox Device

Once your Render service is live:

### 1. WebSocket Endpoint
Your Soundbox connects to the secure WebSocket URL:
```text
wss://<your-service-name>.onrender.com/ws/device
```

### 2. Device Headers & Authentication
The device authenticates using its device token or HMAC credentials:
- Header `X-Device-ID`: Device UUID or serial number
- Header `Authorization`: `Bearer <DEVICE_JWT_TOKEN>`

### 3. Replay Synchronization
If the Soundbox disconnects (offline state), payments are safely queued in PostgreSQL. As soon as the Soundbox reconnects to `wss://<your-service-name>.onrender.com/ws/device`, all pending notifications are automatically replayed and marked `DELIVERED` upon receiving playback `ACK`.

---

## Live Smoke Verification Checklist

After deployment finishes, run through these verification steps:

- [ ] **1. Public Health Check**:
  Visit `https://<your-service-name>.onrender.com/health` in your browser.
  Expected Response:
  ```json
  {"status":"healthy","database":"connected","redis":"connected"}
  ```
- [ ] **2. Database Schema**:
  Check Render logs for:
  ```text
  ==> Running Alembic database migrations...
  INFO  [alembic.runtime.migration] Running upgrade -> ...
  ```
- [ ] **3. Background Worker Started**:
  Check Render logs for:
  ```text
  ==> Starting VoiceLedger transactional outbox worker in background...
  ==> Outbox worker started (PID: ...)
  ```
- [ ] **4. Live Razorpay Payment Test**:
  - In Razorpay Dashboard, generate a Test Payment Link for ₹10.00.
  - Complete the payment using Razorpay Test UPI / Card.
  - Watch the Render Web Service logs:
    1. `POST /api/v1/webhooks/razorpay` returns `200 OK`.
    2. Outbox worker picks up event and synthesizes speech phrase: *"Received ten rupees on VoiceLedger"*.
    3. Event published to Redis channel.
    4. Connected Soundbox receives audio frame over WebSocket and sends `PLAYED` ACK.
    5. Database status updates from `QUEUED` to `DELIVERED`.

---

## Render Free Tier Notes

- **Spin-Down on Inactivity**: On the Render Free tier, web services spin down after 15 minutes of inactivity. The first incoming webhook or request may take ~30–45 seconds to wake the service.
- **Keep-Alive (Optional)**: If you need immediate zero-latency responses for a live demo, you can ping `https://<your-service-name>.onrender.com/health` every 10 minutes using a free uptime monitor (e.g. UptimeRobot or Cron-job.org).
- **Zero Extra Cost**: With `RUN_WORKER=true`, the outbox worker runs inside the Web Service container, eliminating the need to pay for a separate background worker service.
