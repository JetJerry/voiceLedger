# VoiceLedger — Implementation Plan for Gemini

## Purpose

Use this document as the implementation sequence. Do not ask Gemini to build the entire application in one prompt.

Implement one phase at a time and run tests after each phase.

## Phase 0 — Repository foundation

Create:
- FastAPI application
- configuration system
- Docker setup
- PostgreSQL connection
- Alembic
- Redis connection
- logging
- health endpoint

Acceptance:
```text
GET /health -> 200
Database health check works
Redis health check works
Migration runs successfully
```

## Phase 1 — Database

Implement:
- users
- merchants
- merchant_users
- provider_connections
- payments
- payment_events
- devices
- device_sessions
- voice_notifications
- audit_logs
- outbox_events

Add:
- UUID primary keys
- foreign keys
- unique constraints
- indexes
- timestamps
- amount_minor BIGINT

Run migrations and database tests.

## Phase 2 — Authentication

Implement:
- registration
- login
- refresh
- logout
- password hashing
- token/session revocation
- merchant membership
- RBAC

Acceptance:
- user cannot access another merchant's resources.

## Phase 3 — Razorpay provider adapter

Implement:
```text
PaymentProviderAdapter
RazorpayAdapter
```

Implement:
- Razorpay client wrapper
- configuration
- webhook verification
- event parser
- payment retrieval when required

Do not put Razorpay-specific logic in generic payment services.

## Phase 4 — Webhook ingestion

Implement:

```text
POST /api/v1/webhooks/razorpay
```

Requirements:
- raw body
- signature verification
- strict validation
- idempotency
- fast response
- background processing where appropriate
- security logging

Tests:
- valid webhook
- invalid signature
- duplicate webhook
- malformed payload
- unknown payment

## Phase 5 — Payment Core

Implement:
- merchant mapping
- payment state machine
- verification
- idempotency
- database transaction
- audit log
- outbox event

Acceptance:

```text
One successful provider payment
=
One VoiceLedger payment
=
One outbox event
```

Repeated provider events must not create duplicates.

## Phase 6 — Notification worker

Implement:
- outbox worker
- Redis queue
- notification creation
- retry policy
- bounded retries
- notification idempotency

Payment data must already be committed before notification processing.

## Phase 7 — Device management

Implement:
- device pairing
- one-time pairing code
- device registration
- device credential
- device listing
- device revoke/disable

Test:
- invalid pairing
- expired pairing
- reused pairing
- revoked device

## Phase 8 — WebSocket

Implement:
- authenticated WSS
- device session
- merchant/device mapping
- payment event delivery
- ACK
- reconnect
- heartbeat
- bounded retries

Acceptance:
```text
Payment captured
 -> notification created
 -> connected device receives event
```

## Phase 9 — Voice

Implement:
- message templates
- language selection
- TTS
- delivery status

Initial template:

```text
"{amount} rupaye prapt hue."
```

Do not use an LLM here.

## Phase 10 — Dashboard APIs

Implement:
- transaction history
- transaction details
- daily total
- payment count
- device status
- notification status

All queries must be merchant-scoped.

## Phase 11 — Security hardening

Perform:
- rate limiting
- secure headers
- CORS allowlist
- request size limits
- timeout configuration
- secret scan
- dependency scan
- audit logging
- authorization tests
- replay tests
- IDOR tests

## Phase 12 — Observability

Add:
- structured logs
- request IDs
- payment event IDs
- metrics
- error monitoring
- webhook processing metrics
- notification latency
- device online/offline metrics

Never log:
- secrets
- passwords
- access tokens
- webhook secrets
- unnecessary PII

## Phase 13 — End-to-end testing

Test the complete flow:

```text
Razorpay test payment
       |
Razorpay webhook
       |
VoiceLedger
       |
verification
       |
database
       |
outbox
       |
worker
       |
WebSocket
       |
device
       |
voice
```

Also test duplicate webhook delivery.

## Phase 14 — Deployment

Production:
- HTTPS
- managed PostgreSQL
- managed Redis
- backend deployment
- worker deployment
- secret management
- database backups
- monitoring
- domain
- webhook URL

## Rules for every Gemini coding prompt

Always tell Gemini:

1. Read the relevant architecture document first.
2. Do not modify unrelated modules.
3. Do not invent payment-provider behavior.
4. Verify current Razorpay API/webhook details against official documentation.
5. Never put secrets in source code.
6. Never trust frontend payment status.
7. Use database transactions for financial state changes.
8. Use idempotency for all provider events.
9. Add tests with every implementation.
10. Do not remove security checks to make tests pass.
11. Do not change database schema without an Alembic migration.
12. Do not introduce a new dependency unless necessary.
13. Explain changed files before making large architectural changes.
14. Keep provider-specific logic inside provider adapters.
15. Treat PostgreSQL as the financial source of truth.
