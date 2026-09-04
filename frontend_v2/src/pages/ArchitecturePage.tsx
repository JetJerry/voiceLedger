import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Smartphone,
  CreditCard,
  ShieldCheck,
  Server,
  Database,
  Layers,
  Radio,
  Activity,
  Speaker,
  Volume2,
  CheckCheck,
  ArrowRight,
  Lock,
  Zap,
  CheckCircle2,
  Cpu,
  FileCode,
  Sparkles,
} from 'lucide-react';

interface PipelineStage {
  id: number;
  title: string;
  badge: string;
  badgeColor: string;
  icon: React.ComponentType<{ className?: string }>;
  summary: string;
  tech: string;
  sourceFile: string;
  guarantee: string;
  payloadTitle: string;
  payloadCode: string;
}

const PIPELINE_STAGES: PipelineStage[] = [
  {
    id: 1,
    title: 'Customer / UPI',
    badge: 'Initiation',
    badgeColor: 'bg-slate-100 text-slate-700 border-slate-200',
    icon: Smartphone,
    summary: 'Payer scans dynamic UPI QR code or initiates checkout using Google Pay, PhonePe, Paytm, or card.',
    tech: 'UPI 2.0 / BharatQR / Cards',
    sourceFile: 'Payer App / Mobile Client',
    guarantee: 'Standard UPI 2-factor authentication & banking rails',
    payloadTitle: 'Payer Transaction Intent',
    payloadCode: `{
  "intent": "PAYMENT_INITIATE",
  "vpa": "customer@okhdfcbank",
  "amount_inr": 500.00,
  "merchant_vpa": "ramesh.kirana@icici"
}`,
  },
  {
    id: 2,
    title: 'Razorpay Gateway',
    badge: 'Acquiring',
    badgeColor: 'bg-blue-50 text-blue-700 border-blue-200',
    icon: CreditCard,
    summary: 'Razorpay captures the funds, signs an HTTP POST webhook with HMAC-SHA256, and dispatches to VoiceLedger.',
    tech: 'Razorpay Payments API',
    sourceFile: 'Razorpay Webhook Engine',
    guarantee: 'Cardholder/UPI settlement with cryptographic signature header',
    payloadTitle: 'Razorpay Webhook Headers & Event',
    payloadCode: `{
  "headers": {
    "X-Razorpay-Signature": "3a7b9c1d4e...hmac_sha256_hex...",
    "Content-Type": "application/json"
  },
  "event": "payment.captured",
  "payload": {
    "payment": {
      "entity": {
        "id": "pay_OXYZ1234567890",
        "amount": 50000,
        "currency": "INR",
        "status": "captured",
        "method": "upi"
      }
    }
  }
}`,
  },
  {
    id: 3,
    title: 'Verified Webhook',
    badge: 'Security Perimeter',
    badgeColor: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    icon: ShieldCheck,
    summary: 'FastAPI computes HMAC-SHA256 over raw request bytes and uses constant-time comparison. Unsigned payloads are rejected with HTTP 400.',
    tech: 'HMAC-SHA256 (Constant-Time)',
    sourceFile: 'backend/app/api/v1/webhooks.py',
    guarantee: 'Zero forged or spoofed events enter the ledger system',
    payloadTitle: 'Webhook Verification Logic',
    payloadCode: `# backend/app/api/v1/webhooks.py
expected_signature = hmac.new(
    webhook_secret.encode('utf-8'),
    raw_body,
    hashlib.sha256
).hexdigest()

if not hmac.compare_digest(expected_signature, signature_header):
    raise HTTPException(status_code=400, detail="Invalid signature")`,
  },
  {
    id: 4,
    title: 'FastAPI Gateway',
    badge: 'Deduplication',
    badgeColor: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    icon: Server,
    summary: 'Two-tier idempotency check: inspects Redis memory lock, followed by PostgreSQL unique index. Duplicate webhooks return HTTP 200 without duplicate billing.',
    tech: 'FastAPI + Redis SETNX',
    sourceFile: 'backend/app/services/payment_service.py',
    guarantee: 'Duplicate event protection (at-most-once processing)',
    payloadTitle: 'Idempotency Check Payload',
    payloadCode: `{
  "event_id": "evt_capture_881865c7_102",
  "idempotency_key": "idemp:pay_OXYZ1234567890",
  "action": "PROCESS_NEW_PAYMENT",
  "is_duplicate": false
}`,
  },
  {
    id: 5,
    title: 'PostgreSQL Ledger',
    badge: 'Source of Truth',
    badgeColor: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    icon: Database,
    summary: 'Atomic transaction writes payment record and ledger entry. WebSockets are strictly read-only and cannot mutate financial balances.',
    tech: 'PostgreSQL 16 (ACID)',
    sourceFile: 'backend/app/models/payment.py & ledger.py',
    guarantee: 'ACID guarantees, tenant isolation by merchant_id, zero mutation by WebSockets',
    payloadTitle: 'Immutable Database Ledger Entry',
    payloadCode: `-- Committed in atomic ACID transaction
INSERT INTO payments (id, merchant_id, amount, currency, status, payment_method)
VALUES ('pay_OXYZ1234567890', '881865c7-d548-419f-8f37-4a451b3804a7', 500.00, 'INR', 'CAPTURED', 'upi');

INSERT INTO ledger_entries (merchant_id, payment_id, type, amount_cents)
VALUES ('881865c7-d548-419f-8f37-4a451b3804a7', 'pay_OXYZ1234567890', 'CREDIT', 50000);`,
  },
  {
    id: 6,
    title: 'Transactional Outbox',
    badge: 'Reliability',
    badgeColor: 'bg-amber-50 text-amber-700 border-amber-200',
    icon: Layers,
    summary: 'Outbox event row is saved in the exact same database commit as the financial payment. Eliminates dual-write data loss.',
    tech: 'Transactional Outbox Pattern',
    sourceFile: 'backend/app/models/outbox.py',
    guarantee: 'Guaranteed at-least-once event publication without distributed 2PC',
    payloadTitle: 'Transactional Outbox Row Schema',
    payloadCode: `{
  "id": "outbox_550e8400-e29b-41d4-a716-446655440000",
  "event_type": "payment.captured",
  "merchant_id": "881865c7-d548-419f-8f37-4a451b3804a7",
  "payload": { "payment_id": "pay_OXYZ1234567890", "amount": 500.00 },
  "status": "PENDING",
  "created_at": "2026-09-04T12:00:00Z"
}`,
  },
  {
    id: 7,
    title: 'Redis / Valkey Bus',
    badge: 'Fan-Out Engine',
    badgeColor: 'bg-red-50 text-red-700 border-red-200',
    icon: Radio,
    summary: 'Outbox worker drains pending rows and publishes to isolated Redis Pub/Sub channels partitioned by merchant UUID and device UUID.',
    tech: 'Redis Pub/Sub (Async Worker)',
    sourceFile: 'backend/app/worker.py',
    guarantee: 'Strict channel isolation: merchant:{id}:events & device:{id}:notifications',
    payloadTitle: 'Redis Pub/Sub Channel Broadcast',
    payloadCode: `# Channel: merchant:881865c7-d548-419f-8f37-4a451b3804a7:events
{
  "event_type": "payment.captured",
  "data": {
    "payment_id": "pay_OXYZ1234567890",
    "amount": 500.00,
    "currency": "INR",
    "payer_name": "Kavita Rao",
    "timestamp": "2026-09-04T12:00:01Z"
  }
}`,
  },
  {
    id: 8,
    title: 'Merchant WebSocket',
    badge: 'Live Dashboard',
    badgeColor: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    icon: Activity,
    summary: 'Dedicated stream for merchant operations dashboard. Delivers instant payment capture notifications with JWT authentication.',
    tech: 'WebSocket (/ws/merchant)',
    sourceFile: 'backend/app/api/v1/merchant_ws.py',
    guarantee: 'Real-time dashboard updates (<50ms delivery latency)',
    payloadTitle: 'Merchant WebSocket Event Frame',
    payloadCode: `{
  "type": "payment_event",
  "event": "payment.captured",
  "data": {
    "id": "pay_OXYZ1234567890",
    "amount": 500.00,
    "currency": "INR",
    "merchant_id": "881865c7-d548-419f-8f37-4a451b3804a7",
    "status": "captured",
    "method": "upi",
    "created_at": "2026-09-04T12:00:01Z"
  }
}`,
  },
  {
    id: 9,
    title: 'Device WebSocket',
    badge: 'Audio Dispatch',
    badgeColor: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    icon: Speaker,
    summary: 'Hardware audio dispatch stream. Devices authenticate via session token to receive synthesized base64 voice notifications.',
    tech: 'WebSocket (/ws/device)',
    sourceFile: 'backend/app/api/v1/device_ws.py',
    guarantee: 'Isolated hardware channel with session bearer token verification',
    payloadTitle: 'Voice Notification Frame',
    payloadCode: `{
  "type": "voice_notification",
  "notification_id": "29be1a53-87a4-4ea0-8b1b-944a9ba1df38",
  "device_id": "29be1a53-87a4-4ea0-8b1b-944a9ba1df38",
  "text": "Received ₹500 on VoiceLedger",
  "audio_data": "UklGRi4AAABXQVZFZm10IBAAAAABAAEA...",
  "priority": "HIGH"
}`,
  },
  {
    id: 10,
    title: 'Virtual Soundbox',
    badge: 'Speaker Terminal',
    badgeColor: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    icon: Volume2,
    summary: 'Hardware simulator receives the base64 audio payload, decodes it into audio buffer, and triggers browser speaker playback.',
    tech: 'HTML5 Web Audio Decoder',
    sourceFile: 'frontend_v2/src/context/SoundboxContext.tsx',
    guarantee: 'Real browser speaker output (with autoplay unlock fallback)',
    payloadTitle: 'Client Audio Playback State',
    payloadCode: `{
  "device_name": "Demo Soundbox Bridge",
  "status": "PLAYING",
  "volume": 0.85,
  "current_announcement": "Received ₹500 on VoiceLedger",
  "led_audio_status": "PULSING_AMBER"
}`,
  },
  {
    id: 11,
    title: 'Playback ACK',
    badge: 'Verification Loop',
    badgeColor: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    icon: CheckCheck,
    summary: 'Soundbox sends canonical playback acknowledgement upon audio completion. Backend marks notification as DELIVERED.',
    tech: 'Bi-directional WebSocket Handshake',
    sourceFile: 'backend/app/api/v1/device_ws.py',
    guarantee: 'Auditable delivery loop: server knows sound was actually heard',
    payloadTitle: 'Exact Playback ACK Protocol',
    payloadCode: `# 1. Soundbox Dispatches Outbound ACK:
{
  "type": "playback_ack",
  "notification_id": "29be1a53-87a4-4ea0-8b1b-944a9ba1df38",
  "status": "PLAYED"
}

# 2. Server Confirms & Updates Ledger:
{
  "type": "playback_ack_response",
  "notification_id": "29be1a53-87a4-4ea0-8b1b-944a9ba1df38",
  "status": "DELIVERED"
}`,
  },
];

const GUARANTEES = [
  {
    title: 'Verified Webhook Security',
    description:
      'Every inbound Razorpay webhook payload is validated against X-Razorpay-Signature using HMAC-SHA256 with constant-time comparison.',
    icon: ShieldCheck,
    tag: 'Cryptographic Integrity',
  },
  {
    title: 'Duplicate Event Protection',
    description:
      'Two-tier idempotency: Redis key lock prevents simultaneous processing, while PostgreSQL unique constraint prevents duplicate ledger entries.',
    icon: Zap,
    tag: 'At-Most-Once Processing',
  },
  {
    title: 'PostgreSQL as Immutable Source of Truth',
    description:
      'All merchant balances and payments exist in ACID-compliant PostgreSQL tables. WebSockets are strictly read-only and cannot mutate financial records.',
    icon: Database,
    tag: 'Zero Mutation Invariant',
  },
  {
    title: 'Transactional Outbox Reliability',
    description:
      'The outbox_events record is committed in the same database transaction as the payment, completely eliminating dual-write distributed transaction failures.',
    icon: Layers,
    tag: 'No Dual-Write Hazard',
  },
  {
    title: 'Strict Multi-Tenant Isolation',
    description:
      'Every database query, token check, Redis Pub/Sub channel, and WebSocket stream enforces the merchant UUID boundary.',
    icon: Lock,
    tag: 'Tenant Security',
  },
  {
    title: 'Dual-Channel WebSocket Delivery',
    description:
      'Separation of concerns: /ws/merchant delivers event payloads to business dashboards, while /ws/device dispatches audio data to soundboxes.',
    icon: Activity,
    tag: 'Sub-Second Latency',
  },
  {
    title: 'End-to-End Playback Acknowledgement',
    description:
      'Soundbox terminals dispatch a canonical playback_ack only after physical audio completion, transitioning the notification to DELIVERED.',
    icon: CheckCheck,
    tag: 'Closed-Loop Verification',
  },
];

export const ArchitecturePage: React.FC = () => {
  const navigate = useNavigate();
  const [selectedStageId, setSelectedStageId] = useState<number>(1);

  const activeStage = PIPELINE_STAGES.find((s) => s.id === selectedStageId) || PIPELINE_STAGES[0];

  return (
    <div className="space-y-8">
      {/* Top Hero Banner */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 sm:p-8 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="max-w-2xl">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200 mb-3">
            <Cpu className="w-3.5 h-3.5" />
            <span>Architecture & Financial Invariants</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
            Real-Time Transactional Pipeline
          </h1>
          <p className="text-xs sm:text-sm text-slate-600 mt-2 leading-relaxed">
            From customer UPI QR scan to sub-second audio soundbox broadcast: a resilient event-driven architecture with cryptographic webhook verification, transactional outbox guarantees, and zero financial mutation.
          </p>
        </div>

        {/* Quick Demo Navigation Links */}
        <div className="flex flex-wrap md:flex-col gap-2 shrink-0">
          <button
            onClick={() => navigate('/')}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-xl transition-all shadow-xs"
          >
            <Activity className="w-4 h-4" />
            <span>Live Operations</span>
          </button>
          <button
            onClick={() => navigate('/devices')}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 text-xs font-semibold text-slate-700 bg-white hover:bg-slate-50 border border-slate-200 rounded-xl transition-all shadow-2xs"
          >
            <Speaker className="w-4 h-4 text-indigo-600" />
            <span>Soundbox Simulator</span>
          </button>
        </div>
      </div>

      {/* Interactive Pipeline Visualizer */}
      <div className="bg-white border border-slate-200 rounded-2xl shadow-xs overflow-hidden">
        <div className="px-6 py-5 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-500" />
              11-Stage End-to-End Delivery Flow
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Select any stage below to inspect its source code, payload schema, and architectural guarantee.
            </p>
          </div>
          <span className="text-xs font-medium text-slate-500">
            Selected: <strong className="text-blue-600">{activeStage.title}</strong>
          </span>
        </div>

        {/* Pipeline Horizontal Stepper Buttons */}
        <div className="p-6 bg-slate-50/50 border-b border-slate-200 overflow-x-auto">
          <div className="flex items-center gap-2 min-w-max">
            {PIPELINE_STAGES.map((stage, idx) => {
              const Icon = stage.icon;
              const isSelected = stage.id === selectedStageId;

              return (
                <React.Fragment key={stage.id}>
                  <button
                    onClick={() => setSelectedStageId(stage.id)}
                    className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold transition-all border ${
                      isSelected
                        ? 'bg-white border-blue-600 text-blue-700 shadow-sm ring-2 ring-blue-600/10'
                        : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                    }`}
                  >
                    <span
                      className={`w-5 h-5 rounded-full text-2xs flex items-center justify-center font-bold ${
                        isSelected ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-500'
                      }`}
                    >
                      {stage.id}
                    </span>
                    <Icon className="w-3.5 h-3.5 shrink-0" />
                    <span>{stage.title}</span>
                  </button>

                  {idx < PIPELINE_STAGES.length - 1 && (
                    <ArrowRight className="w-3.5 h-3.5 text-slate-300 shrink-0" />
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>

        {/* Selected Stage Detail Inspector */}
        <div className="p-6 sm:p-8 grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Stage Metadata (Left 5 Cols) */}
          <div className="lg:col-span-5 space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-blue-50 border border-blue-200 flex items-center justify-center text-blue-600 shadow-2xs">
                {React.createElement(activeStage.icon, { className: 'w-6 h-6' })}
              </div>
              <div>
                <span className="text-2xs font-mono font-bold text-slate-400 uppercase tracking-wider">
                  Stage {activeStage.id} of {PIPELINE_STAGES.length}
                </span>
                <h3 className="text-lg font-bold text-slate-900">{activeStage.title}</h3>
              </div>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed">{activeStage.summary}</p>

            <div className="space-y-2.5 pt-2 border-t border-slate-100">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-500 font-medium">Technology:</span>
                <span className="font-semibold text-slate-800">{activeStage.tech}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-500 font-medium">Repository Location:</span>
                <span className="font-mono text-2xs bg-slate-100 px-2 py-0.5 rounded text-slate-700 font-semibold truncate max-w-[220px]">
                  {activeStage.sourceFile}
                </span>
              </div>
              <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0 text-emerald-600" />
                <div>
                  <span className="font-bold block">Implemented Guarantee</span>
                  <span className="text-2xs leading-snug">{activeStage.guarantee}</span>
                </div>
              </div>
            </div>

            {/* Stepper controls */}
            <div className="pt-2 flex items-center gap-2">
              <button
                disabled={selectedStageId === 1}
                onClick={() => setSelectedStageId((prev) => Math.max(1, prev - 1))}
                className="flex-1 py-1.5 px-3 rounded-lg border border-slate-200 text-xs font-semibold text-slate-700 bg-white hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                ← Previous Stage
              </button>
              <button
                disabled={selectedStageId === PIPELINE_STAGES.length}
                onClick={() => setSelectedStageId((prev) => Math.min(PIPELINE_STAGES.length, prev + 1))}
                className="flex-1 py-1.5 px-3 rounded-lg border border-slate-200 text-xs font-semibold text-slate-700 bg-white hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Next Stage →
              </button>
            </div>
          </div>

          {/* Real Payload & Code Schema (Right 7 Cols) */}
          <div className="lg:col-span-7 bg-slate-900 rounded-xl p-4 sm:p-5 text-slate-100 font-mono text-xs flex flex-col justify-between shadow-inner">
            <div>
              <div className="flex items-center justify-between pb-3 border-b border-slate-800 text-slate-400 text-2xs">
                <span className="flex items-center gap-1.5 text-slate-300 font-semibold">
                  <FileCode className="w-3.5 h-3.5 text-blue-400" />
                  {activeStage.payloadTitle}
                </span>
                <span className="bg-slate-800 px-2 py-0.5 rounded text-3xs font-mono text-slate-400">
                  {activeStage.sourceFile}
                </span>
              </div>
              <pre className="mt-3 overflow-x-auto text-2xs leading-relaxed text-slate-300">
                <code>{activeStage.payloadCode}</code>
              </pre>
            </div>
            <div className="mt-4 pt-3 border-t border-slate-800 text-3xs text-slate-500 flex items-center justify-between">
              <span>VoiceLedger Invariant Engine</span>
              <span>ACID • At-Least-Once • Read-Only WebSockets</span>
            </div>
          </div>
        </div>
      </div>

      {/* Seven Core Architectural Guarantees Grid */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-slate-900">System Guarantees & Non-Negotiable Invariants</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Every design decision in VoiceLedger reinforces auditability, security, and sub-second performance.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {GUARANTEES.map((g, idx) => {
            const Icon = g.icon;
            return (
              <div
                key={idx}
                className="bg-white border border-slate-200 rounded-xl p-5 shadow-2xs hover:shadow-xs transition-shadow flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
                      <Icon className="w-4 h-4" />
                    </div>
                    <span className="text-2xs font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                      {g.tag}
                    </span>
                  </div>
                  <h3 className="text-xs font-bold text-slate-900 mt-3">{g.title}</h3>
                  <p className="text-2xs text-slate-600 mt-1.5 leading-relaxed">{g.description}</p>
                </div>
                <div className="mt-4 pt-3 border-t border-slate-100 flex items-center gap-1 text-3xs text-emerald-700 font-semibold">
                  <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                  <span>Enforced by Backend</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Judge Presentation Action Strip */}
      <div className="bg-gradient-to-r from-blue-600 to-indigo-700 rounded-2xl p-6 sm:p-8 text-white shadow-md flex flex-col sm:flex-row sm:items-center justify-between gap-6">
        <div>
          <span className="text-2xs font-semibold uppercase tracking-wider text-blue-200 block">
            Ready for Demo
          </span>
          <h3 className="text-lg font-bold mt-1">Experience the Live Payment Pipeline</h3>
          <p className="text-xs text-blue-100 mt-1 max-w-xl">
            Simulate or receive a real Razorpay payment to observe the transaction stream to Live Operations and trigger instantaneous voice playback on the Virtual Soundbox.
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={() => navigate('/')}
            className="px-4 py-2.5 rounded-xl bg-white text-blue-700 text-xs font-bold hover:bg-blue-50 transition-colors shadow-sm"
          >
            Go to Live Operations
          </button>
          <button
            onClick={() => navigate('/devices')}
            className="px-4 py-2.5 rounded-xl bg-blue-800 text-white text-xs font-bold hover:bg-blue-900 transition-colors border border-blue-500/30"
          >
            Launch Simulator
          </button>
        </div>
      </div>
    </div>
  );
};
