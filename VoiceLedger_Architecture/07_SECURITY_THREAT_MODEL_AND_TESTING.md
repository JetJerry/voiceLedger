# VoiceLedger — Security Threat Model and Security Testing

## 1. Security objective

VoiceLedger handles financial transaction information. The system must prioritize:
- authenticity
- integrity
- confidentiality
- availability
- auditability
- tenant isolation
- idempotency

## 2. Threat model

### T1 — Fake payment request

Attacker calls an API:
```text
POST /payments
status=SUCCESS
amount=10000
```

Mitigation:
- client cannot create successful financial records
- only trusted provider events/API verification can create authoritative success
- server-side authorization

### T2 — Fake Razorpay webhook

Attacker sends forged webhook.

Mitigation:
- webhook signature verification
- secret stored securely
- reject invalid signatures

### T3 — Webhook replay

Attacker replays a valid event.

Mitigation:
- provider event id/fingerprint
- payment ID unique constraint
- notification idempotency

### T4 — Amount tampering

Attacker changes:
```text ₹500 -> ₹50,000
```

Mitigation:
- amount sourced from verified provider data
- integer minor units
- server-side validation
- frontend amount never authoritative

### T5 — Cross-merchant access

Merchant A requests Merchant B's transaction.

Mitigation:
- merchant_id scoping
- authorization middleware/service
- database query constraints
- integration tests for horizontal privilege escalation

### T6 — Device takeover

Attacker obtains device credential.

Mitigation:
- device-specific credentials
- revocation
- rotation
- short-lived pairing code
- no merchant password reuse
- Android Keystore

### T7 — WebSocket impersonation

Mitigation:
- authenticated WSS
- server-side device-to-merchant mapping
- reject unauthorized subscriptions

### T8 — Database compromise

Mitigation:
- encryption at rest
- least privilege
- private networking
- secret management
- backups
- minimize sensitive data

### T9 — Credential leakage

Mitigation:
- environment/secret manager
- secret scanning
- no secrets in Git
- no secrets in logs
- rotation procedure

### T10 — Denial of service

Mitigation:
- rate limiting
- request limits
- connection limits
- queue backpressure
- infrastructure WAF/CDN where appropriate

### T11 — Dependency vulnerability

Mitigation:
- lock dependencies
- automated vulnerability scanning
- regular updates
- remove unused packages

### T12 — Insider/admin misuse

Mitigation:
- RBAC
- audit logs
- least privilege
- no silent manual financial modification
- require explicit audited workflows

## 3. Security controls

### Network
- TLS 1.2+ / platform-recommended TLS
- HTTPS everywhere
- WSS for devices
- private DB/Redis

### Application
- strict Pydantic validation
- authorization on every resource
- rate limits
- CSRF protection where cookie auth is used
- security headers
- safe error messages

### Database
- least-privilege account
- parameterized queries/ORM
- constraints
- encrypted backups

### Secrets
- secret manager/environment
- rotation
- never commit secrets
- never log secrets

### Payment
- provider signature validation
- server-side provider verification
- idempotency
- immutable audit trail
- explicit state machine

## 4. Testing strategy

### Unit tests
- signature verification
- event parsing
- state transitions
- idempotency
- authorization
- amount conversion

### Integration tests
- Razorpay webhook -> database
- duplicate webhook -> one payment
- payment -> notification
- device authentication
- merchant isolation

### Security tests
- invalid JWT
- expired token
- revoked device
- invalid webhook signature
- replayed webhook
- IDOR/horizontal privilege escalation
- SQL injection
- XSS where applicable
- CSRF where applicable
- oversized request
- rate-limit bypass attempts

### Failure tests
- DB unavailable
- Redis unavailable
- provider API timeout
- duplicate event
- worker crash
- WebSocket disconnect
- device offline
- TTS failure

## 5. Production security checklist

Before production:
- [ ] HTTPS enabled
- [ ] Razorpay webhook secret configured securely
- [ ] No secrets in repository
- [ ] PostgreSQL private
- [ ] Redis private
- [ ] DB backups enabled
- [ ] Backup restore tested
- [ ] Rate limiting enabled
- [ ] Authentication hardened
- [ ] Device revocation tested
- [ ] Webhook replay tested
- [ ] Duplicate payment tested
- [ ] Merchant isolation tested
- [ ] Audit logging enabled
- [ ] Monitoring/alerting enabled
- [ ] Dependency scan clean/accepted
- [ ] Production error responses do not expose internals
