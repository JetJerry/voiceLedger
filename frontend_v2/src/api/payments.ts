import { apiClient } from './client';

export interface PaymentRecord {
  id: string;
  merchant_id: string;
  provider: string;
  provider_payment_id: string;
  provider_order_id?: string;
  amount_minor: number;
  amount: number;
  currency: string;
  payment_method?: string;
  status: 'CREATED' | 'AUTHORIZED' | 'CAPTURED' | 'FAILED' | 'REFUNDED' | 'PARTIALLY_REFUNDED';
  payer_reference?: string;
  captured_at?: string;
  created_at: string;
  updated_at: string;
}

export interface PaymentsListResponse {
  items: PaymentRecord[];
  total_count: number;
  captured_count: number;
  total_captured_minor: number;
  total_captured: number;
}

export async function listPaymentsApi(params?: {
  limit?: number;
  offset?: number;
  status?: string;
}): Promise<PaymentsListResponse> {
  const q = new URLSearchParams();
  if (params?.limit) q.append('limit', String(params.limit));
  if (params?.offset) q.append('offset', String(params.offset));
  if (params?.status && params.status !== 'ALL') q.append('status', params.status);

  const qs = q.toString();
  return apiClient.get<PaymentsListResponse>(`/api/v1/payments${qs ? `?${qs}` : ''}`, {
    requiresAuth: true,
  });
}

export async function getPaymentApi(id: string): Promise<PaymentRecord> {
  return apiClient.get<PaymentRecord>(`/api/v1/payments/${id}`, {
    requiresAuth: true,
  });
}
