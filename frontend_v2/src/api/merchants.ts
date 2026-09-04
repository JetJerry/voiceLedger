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

export async function checkDeviceSessionAccessApi(sessionId: string): Promise<ResourceAccessResponse> {
  return apiClient.get<ResourceAccessResponse>(`/api/v1/merchants/device-sessions/${sessionId}`, {
    requiresAuth: true,
  });
}

export interface RbacTestResponse {
  message: string;
  role: string;
  merchant_id: string;
}

export async function testOwnerRoleApi(): Promise<RbacTestResponse> {
  return apiClient.get<RbacTestResponse>('/api/v1/merchants/owner-only', {
    requiresAuth: true,
  });
}

export async function testAdminRoleApi(): Promise<RbacTestResponse> {
  return apiClient.get<RbacTestResponse>('/api/v1/merchants/admin-only', {
    requiresAuth: true,
  });
}

export async function testStaffRoleApi(): Promise<RbacTestResponse> {
  return apiClient.get<RbacTestResponse>('/api/v1/merchants/staff-accessible', {
    requiresAuth: true,
  });
}
