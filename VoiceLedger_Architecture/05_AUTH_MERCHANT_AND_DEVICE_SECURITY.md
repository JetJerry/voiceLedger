# VoiceLedger — Authentication, Merchant Security and Device Security

## 1. Authentication

Recommended:
- email/password initially
- Argon2id password hashing
- short-lived access tokens
- rotating refresh tokens
- secure HttpOnly cookies for browser sessions where appropriate

Never store plaintext passwords.

## 2. Authorization model

At minimum:

```text
User
  |
  +-- Merchant membership
          |
          +-- role
```

Roles:

```text
OWNER
ADMIN
STAFF
```

Payment data must be tenant-isolated.

## 3. Tenant isolation

Every merchant-owned resource must include:

```text
merchant_id
```

Authorization must happen server-side.

Do not trust a `merchant_id` supplied by the client.

## 4. Session security

- Secure cookies
- HttpOnly
- SameSite appropriate to deployment
- CSRF protection for cookie-authenticated state-changing endpoints
- Refresh-token rotation
- Revoke sessions on logout/password reset
- Detect refresh-token reuse

## 5. API security

- HTTPS
- Strict request validation
- CORS allowlist
- Rate limiting
- Authentication endpoint throttling
- Generic authentication error messages
- Security headers
- Request body size limits
- Timeouts
- Dependency updates

## 6. Device authentication

A VoiceLedger device is a trusted endpoint associated with one merchant.

Recommended flow:

```text
Merchant Dashboard
      |
Generate one-time pairing code
      |
VoiceLedger Device
      |
Enter/scan pairing code
      |
Backend validates code
      |
Issue device credential
      |
Device opens authenticated WebSocket
```

Never use the merchant's normal password as the device credential.

## 7. Device credential

Prefer:
- device-specific key pair
- public-key registration
- private key stored in Android Keystore when available

Alternative MVP:
- high-entropy device token
- hashed token stored server-side
- rotation and revocation

## 8. Pairing code

Properties:
- short lifetime
- single use
- high entropy
- associated with merchant
- invalidated immediately after pairing
- rate limited

Do not use sequential codes.

## 9. Device authorization

Server verifies:

```text
device credential
+
device status
+
merchant association
```

A device must never subscribe to another merchant's events.

## 10. WebSocket security

Connection:

```text
wss://api.voiceledger...
```

Authentication must happen during connection establishment.

After authentication:

```text
device_id -> merchant_id
```

is stored server-side.

Do not allow the device to send:

```text
merchant_id = X
```

and trust it.

## 11. Device revocation

Merchant can:
- view devices
- rename device
- disable device
- revoke credential
- see last seen time

Revoked device:
```text
WebSocket -> disconnected/rejected
```

## 12. Sensitive data

Do not send unnecessary payer PII to the device.

Prefer:

```json
{
  "type": "payment.received",
  "payment_id": "...",
  "amount_minor": 50000,
  "currency": "INR"
}
```

rather than sending full payment payloads.

## 13. Security monitoring

Alert/log:
- repeated login failures
- invalid device pairing
- revoked device attempts
- invalid webhook signatures
- unusual API rates
- authorization failures
- suspicious admin activity
