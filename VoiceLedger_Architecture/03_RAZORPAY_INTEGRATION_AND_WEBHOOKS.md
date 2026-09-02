# VoiceLedger — Razorpay Integration HLD and LLD

## 1. Purpose

Razorpay is the initial payment provider.

The customer can use supported UPI applications to pay the merchant's Razorpay-powered payment/QR flow.

VoiceLedger receives payment events from Razorpay through its official integration mechanisms.

Reference documentation to verify during implementation:
- Razorpay payment documentation
- Razorpay QR documentation
- Razorpay webhook documentation
- Razorpay webhook signature validation documentation

Do not hard-code assumptions about event names or payload fields. Confirm them against the current Razorpay documentation and the account's enabled products.

## 2. Architecture

```text
Customer
   |
Any supported UPI App
   |
UPI
   |
Razorpay
   |
Payment state change
   |
Webhook
   |
POST /api/v1/webhooks/razorpay
   |
Signature verification
   |
Event validation
   |
Idempotency
   |
Payment Service
   |
PostgreSQL
   |
Notification Queue
```

## 3. Webhook endpoint

Example:

```text
POST /api/v1/webhooks/razorpay
```

Requirements:
- No normal user JWT required.
- Authenticate using Razorpay webhook signature.
- Read the raw request body for signature verification.
- Reject invalid signatures.
- Apply a request size limit.
- Parse JSON only after signature validation if the SDK/verification contract requires raw bytes.
- Return a fast success response after durable event acceptance.

## 4. Signature verification

Do not implement custom cryptography if Razorpay provides an official SDK/helper.

Conceptually:

```text
raw_body
timestamp/event metadata as required
webhook_secret
        |
        v
Razorpay signature verification
        |
        +---- invalid -> 401/4xx + security log
        |
        +---- valid -> continue
```

Never compare a secret or signature using normal insecure string logic when a timing-safe comparison is appropriate.

## 5. Event processing

```text
Webhook request
    |
    v
Verify signature
    |
    v
Validate event schema
    |
    v
Determine provider event ID / fingerprint
    |
    v
Check whether already processed
    |
    +---- yes -> return success/idempotent
    |
    v
Map merchant
    |
    v
Extract payment identifiers
    |
    v
Fetch/confirm payment through Razorpay API if required
    |
    v
Create normalized PaymentEvent
    |
    v
Persist transaction
    |
    v
Queue notification
```

## 6. Never trust webhook data blindly

The webhook is authenticated, but application logic must still validate:
- merchant mapping
- payment ID format
- currency
- amount
- expected status
- provider identifiers
- event type
- consistency with existing order/payment records

For high-risk state changes, use server-to-server Razorpay API retrieval where appropriate.

## 7. Provider adapter

Define:

```python
class PaymentProviderAdapter(Protocol):
    def verify_webhook(self, raw_body: bytes, signature: str) -> bool: ...
    def parse_webhook(self, raw_body: bytes) -> list[PaymentEvent]: ...
    def get_payment(self, provider_payment_id: str) -> ProviderPayment: ...
```

The Razorpay implementation lives only under:

```text
providers/razorpay/
```

## 8. Normalized event

Example internal model:

```json
{
  "provider": "razorpay",
  "provider_event_id": "event_x",
  "provider_payment_id": "pay_x",
  "provider_order_id": "order_x",
  "merchant_reference": "merchant_x",
  "amount_minor": 50000,
  "currency": "INR",
  "method": "upi",
  "status": "CAPTURED",
  "occurred_at": "..."
}
```

This is an internal representation, not a copy of Razorpay's exact payload.

## 9. Retry behavior

Webhook processing must be idempotent.

If Razorpay retries the same event:

```text
Attempt 1 -> processed
Attempt 2 -> duplicate -> no second transaction
Attempt 3 -> duplicate -> no second voice announcement
```

## 10. Webhook security

- Dedicated webhook secret
- Secret stored outside source control
- HTTPS in production
- Raw-body signature verification
- Request size limits
- Structured security logs
- Rate limiting / infrastructure protection where compatible with provider retry behavior
- Do not expose detailed validation errors to attackers
- Do not log raw webhook payloads by default

## 11. Testing

Must include:
- valid signature
- invalid signature
- modified payload
- duplicate webhook
- unknown payment
- payment already captured
- payment failed
- malformed JSON
- oversized request
- missing signature
- provider API temporarily unavailable
- DB temporarily unavailable
- webhook retry
