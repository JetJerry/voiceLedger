import { apiClient } from './client';
import {
  Device,
  DeviceCreateRequest,
  DeviceRegisterResponse,
  DeviceAuthResponse,
} from '../types/device';

export async function listDevicesApi(merchantId: string): Promise<Device[]> {
  return apiClient.get<Device[]>(`/api/v1/merchants/${merchantId}/devices`, {
    requiresAuth: true,
  });
}

export async function registerDeviceApi(
  merchantId: string,
  payload: DeviceCreateRequest
): Promise<DeviceRegisterResponse> {
  return apiClient.post<DeviceRegisterResponse>(
    `/api/v1/merchants/${merchantId}/devices`,
    payload,
    { requiresAuth: true }
  );
}

export async function authenticateDeviceApi(
  deviceId: string,
  deviceSecret: string
): Promise<DeviceAuthResponse> {
  return apiClient.post<DeviceAuthResponse>(
    `/api/v1/devices/${deviceId}/authenticate`,
    { device_secret: deviceSecret },
    { requiresAuth: false }
  );
}

export async function sendDeviceHeartbeatApi(
  deviceId: string,
  sessionToken: string
): Promise<{ status: string; device_id: string; device_status: string; last_seen_at: string }> {
  return apiClient.post(
    `/api/v1/devices/${deviceId}/heartbeat`,
    {},
    {
      requiresAuth: false,
      headers: {
        'X-Device-Session-Token': sessionToken,
      },
    }
  );
}
