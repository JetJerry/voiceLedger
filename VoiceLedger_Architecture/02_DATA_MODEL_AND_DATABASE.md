# VoiceLedger — Database HLD and LLD

## 1. Database

Use PostgreSQL as the authoritative financial ledger database.

Redis is not the source of truth.

## 2. Core entities

```text
users
merchants
merchant_users
provider_connections
payments
payment_events
devices
device_sessions
voice_notifications
audit_logs
```

## 3. Relationships

```text
User
 |
 +---- MerchantUser ---- Merchant
                            |
                            +---- ProviderConnection
                            |
                            +---- Payment
                            |       |
                            |       +---- PaymentEvent
                            |
                            +---- Device
                                    |
                                    +---- DeviceSession
                                    |
                                    +---- VoiceNotification
```

## 4. payments

Recommended fields:

```text
id UUID PK
merchant_id UUID FK
provider VARCHAR
provider_payment_id VARCHAR
provider_order_id VARCHAR NULL
amount_minor BIGINT
currency CHAR(3)
payment_method VARCHAR
status VARCHAR
payer_reference VARCHAR NULL
provider_created_at TIMESTAMP NULL
captured_at TIMESTAMP NULL
created_at TIMESTAMP
updated_at TIMESTAMP
```

Use `amount_minor` instead of floating point.

For INR:
₹500.00 -> 50000 paise.

### Critical constraint

```text
UNIQUE(provider, provider_payment_id)
```

This is a primary financial idempotency guard.

## 5. payment_events

Store normalized or safely retained event metadata:

```text
id UUID PK
merchant_id UUID FK NULL
provider VARCHAR
event_id VARCHAR NULL
provider_payment_id VARCHAR NULL
event_type VARCHAR
payload_hash VARCHAR
processing_status VARCHAR
received_at TIMESTAMP
processed_at TIMESTAMP NULL
error_code VARCHAR NULL
```

If provider event IDs are guaranteed unique, add a unique constraint.

If not, use a deterministic hash/fingerprint carefully.

Do not store unnecessary raw sensitive payload data indefinitely.

## 6. provider_connections

```text
id UUID PK
merchant_id UUID FK
provider VARCHAR
provider_account_reference VARCHAR
status VARCHAR
encrypted_credentials_reference VARCHAR NULL
created_at TIMESTAMP
updated_at TIMESTAMP
```

Prefer storing a reference to a secret manager rather than raw credentials.

## 7. devices

```text
id UUID PK
merchant_id UUID FK
device_name VARCHAR
device_type VARCHAR
status VARCHAR
public_key TEXT NULL
last_seen_at TIMESTAMP NULL
created_at TIMESTAMP
updated_at TIMESTAMP
```

For production, use device credentials/keys designed for device authentication.

## 8. voice_notifications

```text
id UUID PK
merchant_id UUID FK
device_id UUID FK
payment_id UUID FK
message TEXT
status VARCHAR
attempt_count INT
created_at TIMESTAMP
delivered_at TIMESTAMP NULL
```

## 9. audit_logs

```text
id UUID PK
merchant_id UUID FK NULL
actor_type VARCHAR
actor_id UUID NULL
action VARCHAR
resource_type VARCHAR
resource_id UUID NULL
metadata JSONB
created_at TIMESTAMP
ip_address INET NULL
```

Never put passwords, API secrets, webhook secrets, access tokens, or card data in audit metadata.

## 10. Financial state machine

Recommended statuses:

```text
CREATED
AUTHORIZED
CAPTURED
FAILED
REFUNDED
PARTIALLY_REFUNDED
```

For voice announcements, only a verified successful/captured state should trigger the normal "payment received" notification.

Never let an API request arbitrarily set a payment to CAPTURED.

## 11. Database transaction boundary

Payment processing should be atomic:

```text
BEGIN
  verify event
  insert payment_event
  create/update payment
  create notification job
COMMIT
```

Do not send an irreversible external notification before the database transaction is safely committed.

## 12. Indexes

At minimum:

```text
payments(merchant_id, created_at DESC)
payments(merchant_id, status, created_at DESC)
payments(provider, provider_payment_id)
payment_events(provider, event_type, received_at DESC)
voice_notifications(device_id, created_at DESC)
audit_logs(merchant_id, created_at DESC)
```

## 13. Data retention

Define retention periods before production.

Keep financial records according to applicable legal/accounting requirements.

Minimize retention of raw provider payloads and personally identifiable information.

## 14. Database security

- Private network only
- TLS connections in production
- Least-privilege DB user
- Separate migration credentials if possible
- Automated backups
- Point-in-time recovery for production
- Encryption at rest through managed infrastructure
- No production DB access from developer laptops without controlled access
