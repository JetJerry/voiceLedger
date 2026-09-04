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
  status: 'CREATED' | 'AUTHORIZED' | 'CAPTURED' | 'FAILED' | 'REFUNDED' | 'PARTIALLY_REFUNDED' | 'PAID';
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
  let res: any;
  try {
    res = await apiClient.get<any>(`/api/payments${qs ? `?${qs}` : ''}`, { requiresAuth: false });
  } catch (err: any) {
    if (err?.status === 404 || err?.message?.includes('404')) {
      res = await apiClient.get<any>(`/api/v1/payments${qs ? `?${qs}` : ''}`, { requiresAuth: true });
    } else {
      throw err;
    }
  }

  if (Array.isArray(res)) {
    const items: PaymentRecord[] = res.map((p: any) => ({
      id: String(p.id),
      merchant_id: String(p.merchant_id || '1'),
      provider: p.provider || 'RAZORPAY',
      provider_payment_id: p.provider_payment_id || p.id || 'pay_demo',
      amount: Number(p.amount || 0),
      amount_minor: Math.round(Number(p.amount || 0) * 100),
      currency: p.currency || 'INR',
      status: p.status || 'CAPTURED',
      created_at: p.created_at || new Date().toISOString(),
      updated_at: p.updated_at || new Date().toISOString(),
    }));
    return {
      items,
      total_count: items.length,
      captured_count: items.filter((p) => p.status === 'CAPTURED' || p.status === 'PAID').length,
      total_captured_minor: 0,
      total_captured: items.reduce((sum, p) => sum + p.amount, 0),
    };
  }

  return res;
}

export async function getPaymentApi(id: string): Promise<PaymentRecord> {
  try {
    return await apiClient.get<PaymentRecord>(`/api/payments/${id}`, { requiresAuth: false });
  } catch (err: any) {
    if (err?.status === 404 || err?.message?.includes('404')) {
      return await apiClient.get<PaymentRecord>(`/api/v1/payments/${id}`, { requiresAuth: true });
    }
    throw err;
  }
}
