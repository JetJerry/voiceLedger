import { RawPaymentEventPayload, MerchantPaymentEvent } from '../types/websocket';

/**
 * Validates and transforms a raw backend payment event payload into a frontend-safe MerchantPaymentEvent.
 *
 * Invariants:
 * 1. Requires event_id, event_type, merchant_id, and payment_id.
 * 2. Enforces tenant matching if expectedMerchantId is specified.
 * 3. Never throws exceptions on malformed payloads; returns null safely.
 * 4. Never exposes secrets or alters raw data.
 */
export function validateAndParsePaymentEvent(
  raw: unknown,
  expectedMerchantId?: string
): MerchantPaymentEvent | null {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return null;
  }

  const payload = raw as Partial<RawPaymentEventPayload>;

  // Check mandatory fields matching backend validate_event_payload
  if (
    !payload.event_id ||
    !payload.event_type ||
    !payload.merchant_id ||
    !payload.payment_id
  ) {
    return null;
  }

  // Tenant isolation check
  if (
    expectedMerchantId &&
    String(payload.merchant_id).toLowerCase() !== String(expectedMerchantId).toLowerCase()
  ) {
    return null;
  }

  const amountMinor = typeof payload.amount_minor === 'number' ? payload.amount_minor : 0;
  const amountInr = amountMinor / 100;

  return {
    id: String(payload.payment_id),
    eventId: String(payload.event_id),
    eventType: String(payload.event_type),
    merchantId: String(payload.merchant_id),
    paymentId: String(payload.payment_id),
    provider: String(payload.provider || 'RAZORPAY'),
    providerPaymentId: String(payload.provider_payment_id || payload.payment_id),
    providerOrderId: payload.provider_order_id ? String(payload.provider_order_id) : null,
    amountMinor,
    amountInr,
    currency: String(payload.currency || 'INR'),
    status: String(payload.status || 'CAPTURED'),
    paymentMethod: String(payload.payment_method || 'upi'),
    payerReference: String(payload.payer_reference || 'customer'),
    capturedAt: payload.captured_at ? String(payload.captured_at) : null,
    occurredAt: String(payload.occurred_at || new Date().toISOString()),
    receivedAt: new Date().toISOString(),
  };
}

/**
 * Formats integer paise into clean Indian Rupee format (e.g. 50000 -> "₹500.00").
 */
export function formatCurrency(amountMinor: number, currency: string = 'INR'): string {
  const amount = amountMinor / 100;
  const formatted = new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);

  return formatted;
}

/**
 * Formats an ISO date string into a user-friendly local time.
 */
export function formatTimestamp(isoString: string): string {
  try {
    const date = new Date(isoString);
    return new Intl.DateTimeFormat('en-IN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      day: 'numeric',
      month: 'short',
    }).format(date);
  } catch {
    return isoString;
  }
}
