import { apiClient } from './client';
import { MerchantContext, ResourceAccessResponse } from '../types/merchant';

export async function getMerchantContextApi(merchantId?: string): Promise<MerchantContext> {
  const headers: Record<string, string> = {};
  if (merchantId) {
    headers['X-Merchant-ID'] = merchantId;
  }
  return apiClient.get<MerchantContext>('/api/v1/merchants/context', {
    requiresAuth: true,
    headers,
  });
}

export async function checkPaymentAccessApi(paymentId: string): Promise<ResourceAccessResponse> {
  return apiClient.get<ResourceAccessResponse>(`/api/v1/merchants/payments/${paymentId}`, {
    requiresAuth: true,
  });
}

export async function checkDeviceAccessApi(deviceId: string): Promise<ResourceAccessResponse> {
  return apiClient.get<ResourceAccessResponse>(`/api/v1/merchants/devices/${deviceId}`, {
    requiresAuth: true,
  });
}
