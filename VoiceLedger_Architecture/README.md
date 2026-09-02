# VoiceLedger Architecture Pack

This folder contains the HLD/LLD foundation for building VoiceLedger from scratch.

## Reading order

1. `00_SYSTEM_OVERVIEW.md`
2. `01_PROJECT_STRUCTURE_AND_INFRA.md`
3. `02_DATA_MODEL_AND_DATABASE.md`
4. `03_RAZORPAY_INTEGRATION_AND_WEBHOOKS.md`
5. `04_PAYMENT_CORE_AND_IDEMPOTENCY.md`
6. `05_AUTH_MERCHANT_AND_DEVICE_SECURITY.md`
7. `06_REALTIME_VOICE_DEVICE.md`
8. `07_SECURITY_THREAT_MODEL_AND_TESTING.md`
9. `08_IMPLEMENTATION_PLAN_FOR_GEMINI.md`

## Important architectural rule

Razorpay is the first and primary payment integration for the MVP. UPI customer apps are payment interfaces used by customers; VoiceLedger does not attempt to intercept them.

The provider adapter architecture allows future legitimate payment-provider integrations without coupling the core ledger to Razorpay.

## Security rule

Financial truth must come from authenticated provider events/server-side verification, not from the frontend, voice device, AI, or user-provided claims.
