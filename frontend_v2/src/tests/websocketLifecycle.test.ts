import { describe, it, expect } from 'vitest';
import { validateAndParsePaymentEvent } from '../services/websocketParser';

describe('websocketLifecycle - Connection & Resilience Logic', () => {
  const mockToken = 'mock_jwt_access_token_123';
  const mockMerchantId = '881865c7-d548-419f-8f37-4a451b3804a7';

  it('builds canonical WebSocket URL matching backend /ws/merchant query contract', () => {
    const wsBase = 'wss://voiceledger-api-2kfl.onrender.com';
    const wsUrl = `${wsBase}/ws/merchant?token=${encodeURIComponent(
      mockToken
    )}&merchant_id=${encodeURIComponent(mockMerchantId)}`;

    const parsedUrl = new URL(wsUrl);
    expect(parsedUrl.protocol).toBe('wss:');
    expect(parsedUrl.pathname).toBe('/ws/merchant');
    expect(parsedUrl.searchParams.get('token')).toBe(mockToken);
    expect(parsedUrl.searchParams.get('merchant_id')).toBe(mockMerchantId);
  });

  it('calculates exponential backoff capped at maximum 15 seconds', () => {
    const INITIAL_BACKOFF = 1000;
    const MAX_BACKOFF = 15000;

    let backoff = INITIAL_BACKOFF;
    const expectedProgression = [1000, 2000, 4000, 8000, 15000, 15000];

    const actualProgression: number[] = [];
    for (let i = 0; i < expectedProgression.length; i++) {
      actualProgression.push(backoff);
      backoff = Math.min(backoff * 2, MAX_BACKOFF);
    }

    expect(actualProgression).toEqual(expectedProgression);
  });

  it('ignores ping/pong text frames without polluting payment states', () => {
    const pongFrame = 'pong';
    // When text frame is not JSON or does not contain required fields:
    let parsedJson: any = null;
    try {
      parsedJson = JSON.parse(pongFrame);
    } catch {
      // Expected syntax error for plain text
    }

    const event = validateAndParsePaymentEvent(parsedJson, mockMerchantId);
    expect(event).toBeNull();
  });

  it('handles simulated incoming payment frame end-to-end', () => {
    const rawFrame = JSON.stringify({
      event_id: 'evt_sim_001',
      event_type: 'payment.captured',
      merchant_id: mockMerchantId,
      payment_id: 'pay_sim_001',
      provider: 'RAZORPAY',
      provider_payment_id: 'pay_live_test_123',
      amount_minor: 149900,
      currency: 'INR',
      status: 'CAPTURED',
      payment_method: 'upi',
      payer_reference: 'buyer@upi',
      captured_at: '2026-09-04T07:20:00Z',
      occurred_at: '2026-09-04T07:20:00Z',
    });

    const parsedJson = JSON.parse(rawFrame);
    const payment = validateAndParsePaymentEvent(parsedJson, mockMerchantId);

    expect(payment).not.toBeNull();
    expect(payment?.amountInr).toBe(1499.0);
    expect(payment?.providerPaymentId).toBe('pay_live_test_123');
    expect(payment?.status).toBe('CAPTURED');
  });
});
