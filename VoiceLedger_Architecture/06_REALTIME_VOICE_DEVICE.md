# VoiceLedger — Realtime Notification and Voice Device

## 1. Goal

Deliver a verified payment event to the merchant's device with low latency.

The device is an output endpoint. It is not the financial source of truth.

## 2. Flow

```text
Razorpay
   |
Webhook
   |
Payment Core
   |
PostgreSQL COMMIT
   |
Outbox/Event Queue
   |
Notification Worker
   |
WebSocket Gateway
   |
Authenticated Device
   |
TTS
   |
Speaker
```

## 3. Event format

Example:

```json
{
  "event_id": "evt_internal_123",
  "event_type": "payment.received",
  "payment_id": "pay_internal_123",
  "amount_minor": 50000,
  "currency": "INR",
  "method": "UPI",
  "occurred_at": "2026-09-02T18:30:00Z"
}
```

No provider secrets or raw provider payloads.

## 4. Delivery semantics

Use at-least-once delivery.

The device must be able to safely receive the same event more than once.

Device stores the last processed event IDs or acknowledgements as appropriate.

```text
Server -> event
Device -> ACK(event_id)
```

If no ACK:
```text
server retries
```

The notification system must have its own idempotency key.

## 5. Device states

```text
PAIRING
ACTIVE
OFFLINE
DISABLED
REVOKED
```

## 6. Reconnection

Device should:
- reconnect with exponential backoff
- use jitter
- authenticate on reconnect
- report heartbeat/last-seen
- avoid creating multiple simultaneous sessions

## 7. Offline behavior

MVP recommendation:

If device is offline, store pending notification jobs server-side.

When device reconnects:
- send recent pending notifications
- avoid replaying stale notifications indefinitely
- enforce configurable TTL
- preserve payment ledger regardless of voice delivery

Financial transaction != voice delivery status.

## 8. Voice generation

Separate payment truth from voice rendering.

```text
PaymentEvent
     |
Notification Message
     |
Voice Template
     |
TTS
```

Example:

```text
₹500
+
Hindi
+
UPI
=
"500 rupaye prapt hue."
```

Do not use an LLM for normal payment announcements in the MVP.

## 9. TTS options

MVP options:
- Android native TTS
- cloud TTS

Prefer device-side TTS initially where acceptable to reduce latency and cloud cost.

## 10. Device security

- HTTPS/WSS only
- device-specific credentials
- Android Keystore for secrets
- no API secrets embedded in app
- certificate validation through standard platform TLS
- automatic credential rotation where feasible
- remote revocation
- minimal permissions

## 11. Notification priority

Payment notifications should be processed before analytics/background work.

```text
Payment received
     |
Immediate notification
     |
Then analytics/secondary jobs
```

## 12. Failure handling

If TTS fails:
- mark voice delivery failed
- retry bounded number of times
- do not alter payment status

If WebSocket fails:
- queue notification
- retry later

If payment processing succeeds but voice fails:
```text
payment = SUCCESS
voice_notification = FAILED/RETRYING
```

Never reverse a payment because voice failed.
