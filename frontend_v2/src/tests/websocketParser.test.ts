import { describe, it, expect } from 'vitest';
import {
  validateAndParsePaymentEvent,
  formatCurrency,
  formatTimestamp,
} from '../services/websocketParser';

describe('websocketParser - Payment Event Parsing & Security', () => {
  const validMerchantId = '881865c7-d548-419f-8f37-4a451b3804a7';

  const validPayload = {
    event_id: 'evt_12345678-1234-1234-1234-123456789abc',
    provider_event_id: 'rzp_evt_001',
    event_type: 'payment.captured',
    merchant_id: validMerchantId,
    payment_id: 'pay_12345678-1234-1234-1234-123456789def',
    provider: 'RAZORPAY',
    provider_payment_id: 'pay_TXrAsDfHOH5LTU',
    provider_order_id: 'order_TXrAbcD1234',
    amount_minor: 50000,
    currency: 'INR',
    status: 'CAPTURED',
    payment_method: 'upi',
    payer_reference: 'customer@okhdfcbank',
    captured_at: '2026-09-04T07:15:00.000Z',
    occurred_at: '2026-09-04T07:15:00.000Z',
  };

  it('correctly parses a valid backend payment event', () => {
    const parsed = validateAndParsePaymentEvent(validPayload, validMerchantId);

    expect(parsed).not.toBeNull();
    expect(parsed?.id).toBe(validPayload.payment_id);
    expect(parsed?.eventId).toBe(validPayload.event_id);
    expect(parsed?.eventType).toBe('payment.captured');
    expect(parsed?.merchantId).toBe(validMerchantId);
    expect(parsed?.providerPaymentId).toBe('pay_TXrAsDfHOH5LTU');
    expect(parsed?.providerOrderId).toBe('order_TXrAbcD1234');
    expect(parsed?.amountMinor).toBe(50000);
    expect(parsed?.amountInr).toBe(500.0);
    expect(parsed?.currency).toBe('INR');
    expect(parsed?.status).toBe('CAPTURED');
    expect(parsed?.paymentMethod).toBe('upi');
    expect(parsed?.payerReference).toBe('customer@okhdfcbank');
    expect(parsed?.capturedAt).toBe('2026-09-04T07:15:00.000Z');
  });

  it('rejects null, undefined, or primitive payloads', () => {
    expect(validateAndParsePaymentEvent(null, validMerchantId)).toBeNull();
    expect(validateAndParsePaymentEvent(undefined, validMerchantId)).toBeNull();
    expect(validateAndParsePaymentEvent('invalid string', validMerchantId)).toBeNull();
    expect(validateAndParsePaymentEvent(42, validMerchantId)).toBeNull();
    expect(validateAndParsePaymentEvent([], validMerchantId)).toBeNull();
  });

  it('rejects payloads missing mandatory fields', () => {
    // Missing event_id
    expect(
      validateAndParsePaymentEvent({ ...validPayload, event_id: undefined }, validMerchantId)
    ).toBeNull();

    // Missing event_type
    expect(
      validateAndParsePaymentEvent({ ...validPayload, event_type: undefined }, validMerchantId)
    ).toBeNull();

    // Missing merchant_id
    expect(
      validateAndParsePaymentEvent({ ...validPayload, merchant_id: undefined }, validMerchantId)
    ).toBeNull();

    // Missing payment_id
    expect(
      validateAndParsePaymentEvent({ ...validPayload, payment_id: undefined }, validMerchantId)
    ).toBeNull();
  });

  it('enforces tenant isolation and rejects mismatched merchant IDs', () => {
    const intruderMerchantId = '00000000-0000-0000-0000-000000000000';
    const parsed = validateAndParsePaymentEvent(validPayload, intruderMerchantId);

    // Mismatched merchant_id MUST be discarded
    expect(parsed).toBeNull();
  });

  it('formats currency correctly in Indian Rupee format', () => {
    expect(formatCurrency(50000, 'INR')).toContain('500.00');
    expect(formatCurrency(100, 'INR')).toContain('1.00');
    expect(formatCurrency(1234567, 'INR')).toContain('12,345.67');
  });

  it('formats timestamps safely without throwing', () => {
    const formatted = formatTimestamp('2026-09-04T07:15:00.000Z');
    expect(typeof formatted).toBe('string');
    expect(formatted.length).toBeGreaterThan(0);

    // Malformed string returns fallback string safely
    const fallback = formatTimestamp('not-a-date');
    expect(typeof fallback).toBe('string');
  });
});
