/**
 * Canonical WebSocket schemas matching VoiceLedger backend contracts.
 */

export type WsConnectionStatus = 'CONNECTED' | 'CONNECTING' | 'DISCONNECTED' | 'RECONNECTING';

export interface RawPaymentEventPayload {
  event_id: string;
  provider_event_id?: string | null;
  event_type: string;
  merchant_id: string;
  payment_id: string;
  provider: string;
  provider_payment_id: string;
  provider_order_id?: string | null;
  amount_minor: number;
  currency: string;
  status: string;
  payment_method?: string | null;
  payer_reference?: string | null;
  captured_at?: string | null;
  occurred_at?: string | null;
}

export interface MerchantPaymentEvent {
  id: string;
  eventId: string;
  eventType: string;
  merchantId: string;
  paymentId: string;
  provider: string;
  providerPaymentId: string;
  providerOrderId?: string | null;
  amountMinor: number;
  amountInr: number;
  currency: string;
  status: string;
  paymentMethod: string;
  payerReference: string;
  capturedAt: string | null;
  occurredAt: string;
  receivedAt: string;
}

export interface ActivityLogItem {
  id: string;
  type: 'payment' | 'connection' | 'system';
  title: string;
  detail: string;
  timestamp: string;
  level: 'success' | 'info' | 'warning' | 'error';
}
