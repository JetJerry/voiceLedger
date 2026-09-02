# VoiceLedger — System Architecture Overview

## 1. Purpose

VoiceLedger is a merchant-focused payment event and voice notification platform built around Razorpay for the initial implementation.

The customer can pay through any supported UPI application such as PhonePe, Paytm, Google Pay, BHIM, etc. The merchant-side payment processing is handled by Razorpay. Razorpay emits verified payment events to VoiceLedger. VoiceLedger validates, normalizes, deduplicates, stores the transaction, and sends a real-time voice notification to the merchant's VoiceLedger device/application.

### Core principle

VoiceLedger does NOT attempt to intercept, scrape, or impersonate customer UPI applications.

For the MVP:

Customer UPI App -> UPI -> Razorpay -> Razorpay Webhook/API -> VoiceLedger -> Voice Device

Future providers can be added through the Provider Adapter layer.

## 2. MVP Architecture

```text
                         CUSTOMER
                            |
                   Any UPI application
                            |
                            v
                     +-------------+
                     |   RAZORPAY  |
                     | UPI / QR /  |
                     | Payment     |
                     +------+------+
                            |
                     Webhook / API
                            |
                            v
                 +----------------------+
                 | Provider Adapter     |
                 | Razorpay Adapter    |
                 +----------+-----------+
                            |
                            v
                 +----------------------+
                 | VoiceLedger Core     |
                 |                      |
                 | Event validation     |
                 | Verification         |
                 | Deduplication        |
                 | Merchant mapping     |
                 | Transaction service  |
                 +----------+-----------+
                            |
              +-------------+-------------+
              |                           |
              v                           v
       +-------------+             +-------------+
       | PostgreSQL  |             | Redis/Queue |
       | Ledger      |             | Async jobs  |
       +-------------+             +------+------+
                                           |
                                           v
                                  +----------------+
                                  | Voice Service  |
                                  +-------+--------+
                                          |
                                   WebSocket
                                          |
                                          v
                                  +---------------+
                                  | Voice Device  |
                                  | / Android App |
                                  +-------+-------+
                                          |
                                          v
                                  "500 rupaye prapt hue"
```

## 3. Major components

1. API Gateway / FastAPI application
2. Authentication and authorization
3. Merchant service
4. Razorpay integration
5. Provider Adapter layer
6. Webhook ingestion service
7. Payment event processor
8. Verification service
9. Deduplication/idempotency service
10. Transaction/Ledger service
11. Device management service
12. Realtime notification service
13. Voice/TTS service
14. PostgreSQL
15. Redis
16. Background worker
17. Observability/audit system

AI is intentionally excluded from this phase.

## 4. Trust boundaries

### External / untrusted
- Customer
- UPI application
- Razorpay webhook request
- Browser/client
- Voice device network

### Trusted after authentication/verification
- VoiceLedger backend
- PostgreSQL
- Internal queues
- Authenticated device sessions

Never trust:
- client-provided payment status
- client-provided amount
- browser claims of successful payment
- unsigned webhook payloads
- device-provided transaction data

## 5. Security principles

- Verify Razorpay webhook signatures before processing.
- Use HTTPS/TLS everywhere outside localhost.
- Never store Razorpay secret keys in source code or database plaintext.
- Store secrets only in environment/secret management infrastructure.
- Use short-lived access tokens and refresh-token rotation where applicable.
- Hash passwords with Argon2id or another modern password hashing algorithm.
- Enforce server-side authorization for every merchant resource.
- Use database constraints for payment idempotency.
- Treat webhook processing as at-least-once delivery.
- Never trust payment information from the frontend.
- Never let AI/client-side code modify financial records.
- Maintain immutable audit records for sensitive payment actions.
- Apply rate limits to authentication and public endpoints.
- Validate all external payloads using strict schemas.
- Minimize personally identifiable information.
- Encrypt data in transit and encrypt sensitive data at rest where appropriate.
- Log security events without logging secrets or full sensitive payment credentials.

## 6. Recommended implementation order

1. Project structure
2. Configuration and secrets
3. PostgreSQL schema and migrations
4. Authentication
5. Merchant management
6. Razorpay integration
7. Webhook endpoint
8. Payment verification
9. Idempotency/deduplication
10. Ledger
11. Redis and background worker
12. Device authentication
13. WebSocket/realtime events
14. Voice notification
15. Security hardening
16. Observability
17. Integration testing
18. Production deployment

## 7. Non-goals for MVP

- Direct personal PhonePe/Paytm transaction scraping
- Intercepting UPI traffic
- Reading arbitrary bank SMS as a source of truth
- Storing card numbers/CVV
- Becoming a payment processor itself
- AI financial decision making
