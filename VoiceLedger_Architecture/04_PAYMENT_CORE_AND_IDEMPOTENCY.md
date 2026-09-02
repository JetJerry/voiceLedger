# VoiceLedger — Payment Core, Verification and Idempotency

## 1. Purpose

This service converts provider-specific events into authoritative VoiceLedger transactions.

It is the most security-sensitive business component.

## 2. Processing pipeline

```text
Provider Event
     |
     v
Authenticate provider
     |
     v
Validate schema
     |
     v
Resolve merchant
     |
     v
Resolve payment
     |
     v
Verify current provider state if required
     |
     v
Idempotency check
     |
     v
Database transaction
     |
     +---- Payment
     +---- PaymentEvent
     +---- AuditLog
     |
     v
Commit
     |
     v
Publish internal event
     |
     v
Voice notification
```

## 3. Idempotency

Use multiple levels.

### Level 1: provider event

```text
provider + provider_event_id
```

### Level 2: payment

```text
provider + provider_payment_id
```

### Level 3: notification

```text
payment_id + notification_type + device_id
```

The database must enforce uniqueness wherever possible.

Application-level checks alone are not enough because two workers can race.

## 4. Race condition example

Bad:

```text
Worker A: SELECT -> no payment
Worker B: SELECT -> no payment
Worker A: INSERT
Worker B: INSERT
```

Correct:

```text
UNIQUE(provider, provider_payment_id)

Worker A -> INSERT succeeds
Worker B -> unique constraint -> treat as duplicate
```

## 5. Verification

Payment success should be based on:
- authenticated Razorpay event
- supported event/status
- merchant mapping
- payment identity
- server-side state consistency

Never use:

```text
frontend says success
```

as financial truth.

## 6. Payment state transitions

Allowed transitions must be explicit.

Example:

```text
CREATED -> AUTHORIZED
AUTHORIZED -> CAPTURED
AUTHORIZED -> FAILED
CAPTURED -> REFUNDED
CAPTURED -> PARTIALLY_REFUNDED
```

Reject impossible transitions.

Never allow:
```text
FAILED -> CAPTURED
```
without a provider-confirmed state change.

## 7. Amount handling

Always use integer minor units.

```text
₹10 = 1000 paise
₹500 = 50000 paise
```

Never use floating point for financial values.

## 8. Merchant isolation

Every payment query must be scoped to the authenticated merchant.

Example:

```python
payment = repo.get_by_id(
    payment_id=payment_id,
    merchant_id=current_merchant_id
)
```

Never:
```python
repo.get_by_id(payment_id)
```
for a user-facing endpoint unless authorization is separately guaranteed.

## 9. Event publishing

Only publish `payment.captured` after the database transaction commits.

Use an outbox pattern for stronger reliability in production:

```text
DB transaction
  |
  +-- payment
  +-- payment_event
  +-- outbox_event
  |
 COMMIT
  |
worker reads outbox
  |
Redis/WebSocket/notification
```

This prevents the dangerous case:

```text
DB commit succeeds
but event publishing fails
```

## 10. Refunds

Refund events must never delete the original payment.

Record the original transaction and its refund state.

Voice notifications for refunds should be a separate event type.

## 11. Auditability

Record:
- event received
- event accepted/rejected
- payment state transition
- manual administrative action
- device registration/revocation
- authentication/security events

Do not log:
- secrets
- tokens
- passwords
- card credentials
