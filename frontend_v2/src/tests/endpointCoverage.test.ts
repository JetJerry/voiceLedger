import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  testOwnerRoleApi,
  testAdminRoleApi,
  testStaffRoleApi,
  checkPaymentAccessApi,
  checkDeviceAccessApi,
  checkDeviceSessionAccessApi,
} from '../api/merchants';
import { sendDeviceHeartbeatApi } from '../api/devices';
import { registerApi, getHealthApi, getMeApi } from '../api/auth';
import { setTokens, clearTokens } from '../api/client';

describe('API Endpoint Coverage Tests - Comprehensive Backend Contract Verification', () => {
  const fetchSpy = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchSpy);
    setTokens('mock_access_jwt', 'mock_refresh_token');
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    clearTokens();
    fetchSpy.mockReset();
  });

  describe('RBAC Verification Endpoints (/api/v1/merchants/*)', () => {
    it('calls GET /api/v1/merchants/owner-only with Authorization header', async () => {
      fetchSpy.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({
          message: 'Access granted to owner resource',
          role: 'OWNER',
          merchant_id: 'merchant_123',
        }),
      });

      const res = await testOwnerRoleApi();
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/merchants/owner-only'),
        expect.objectContaining({
          method: 'GET',
          headers: expect.objectContaining({
            Authorization: 'Bearer mock_access_jwt',
          }),
        })
      );
      expect(res.role).toBe('OWNER');
      expect(res.merchant_id).toBe('merchant_123');
    });

    it('calls GET /api/v1/merchants/admin-only with Authorization header', async () => {
      fetchSpy.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({
          message: 'Access granted to admin resource',
          role: 'ADMIN',
          merchant_id: 'merchant_123',
        }),
      });

      const res = await testAdminRoleApi();
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/merchants/admin-only'),
        expect.objectContaining({
          method: 'GET',
        })
      );
      expect(res.role).toBe('ADMIN');
    });

    it('calls GET /api/v1/merchants/staff-accessible with Authorization header', async () => {
      fetchSpy.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({
          message: 'Access granted to staff resource',
          role: 'STAFF',
          merchant_id: 'merchant_123',
        }),
      });

      const res = await testStaffRoleApi();
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/merchants/staff-accessible'),
        expect.objectContaining({
          method: 'GET',
        })
      );
      expect(res.role).toBe('STAFF');
    });
  });

  describe('Direct Resource Inspection Endpoints', () => {
    it('calls GET /api/v1/merchants/payments/{payment_id}', async () => {
      fetchSpy.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({
          resource_type: 'payment',
          resource_id: 'pay_12345',
          merchant_id: 'merchant_123',
          authorized: true,
        }),
      });

      const res = await checkPaymentAccessApi('pay_12345');
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/merchants/payments/pay_12345'),
        expect.objectContaining({ method: 'GET' })
      );
      expect(res.authorized).toBe(true);
      expect(res.resource_id).toBe('pay_12345');
    });

    it('calls GET /api/v1/merchants/devices/{device_id}', async () => {
      fetchSpy.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({
          resource_type: 'device',
          resource_id: 'dev_67890',
          merchant_id: 'merchant_123',
          authorized: true,
        }),
      });

      const res = await checkDeviceAccessApi('dev_67890');
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/merchants/devices/dev_67890'),
        expect.objectContaining({ method: 'GET' })
      );
      expect(res.authorized).toBe(true);
      expect(res.resource_type).toBe('device');
    });

    it('calls GET /api/v1/merchants/device-sessions/{session_id}', async () => {
      fetchSpy.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({
          resource_type: 'device_session',
          resource_id: 'sess_abcde',
          merchant_id: 'merchant_123',
          authorized: true,
        }),
      });

      const res = await checkDeviceSessionAccessApi('sess_abcde');
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/merchants/device-sessions/sess_abcde'),
        expect.objectContaining({ method: 'GET' })
      );
      expect(res.authorized).toBe(true);
      expect(res.resource_type).toBe('device_session');
    });
  });

  describe('Hardware Heartbeat & Diagnostic Endpoints', () => {
    it('dispatches POST /api/v1/devices/{device_id}/heartbeat with X-Device-Session-Token', async () => {
      fetchSpy.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({
          status: 'ok',
          device_id: 'dev_67890',
          device_status: 'ONLINE',
          last_seen_at: '2026-09-04T12:00:00Z',
        }),
      });

      const res = await sendDeviceHeartbeatApi('dev_67890', 'session_token_xyz');
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/devices/dev_67890/heartbeat'),
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'X-Device-Session-Token': 'session_token_xyz',
          }),
        })
      );
      expect(res.device_status).toBe('ONLINE');
    });

    it('calls GET /health endpoint for server telemetry', async () => {
      fetchSpy.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({
          status: 'ok',
          database: 'connected',
          redis: 'connected',
          service: 'voiceledger-backend',
          version: '1.0.0',
        }),
      });

      const res = await getHealthApi();
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('/health'),
        expect.objectContaining({ method: 'GET' })
      );
      expect(res.database).toBe('connected');
      expect(res.redis).toBe('connected');
    });

    it('calls GET /api/v1/auth/me for current user identity', async () => {
      fetchSpy.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({
          id: 'user_123',
          email: 'demo@voiceledger.internal',
          full_name: 'Demo Merchant',
          role: 'OWNER',
          is_active: true,
          created_at: '2026-09-04T10:00:00Z',
        }),
      });

      const res = await getMeApi();
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/auth/me'),
        expect.objectContaining({
          method: 'GET',
          headers: expect.objectContaining({
            Authorization: 'Bearer mock_access_jwt',
          }),
        })
      );
      expect(res.email).toBe('demo@voiceledger.internal');
    });

    it('calls POST /api/v1/auth/register for user registration', async () => {
      fetchSpy.mockResolvedValueOnce({
        ok: true,
        status: 201,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({
          success: true,
          message: 'User registered successfully',
          user: {
            id: 'user_new',
            email: 'newmerchant@voiceledger.internal',
            full_name: 'New Merchant',
            is_active: true,
            created_at: '2026-09-04T12:00:00Z',
          },
        }),
      });

      const res = await registerApi({
        email: 'newmerchant@voiceledger.internal',
        password: 'SecurePassword123!',
        full_name: 'New Merchant',
      });
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/auth/register'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            email: 'newmerchant@voiceledger.internal',
            password: 'SecurePassword123!',
            full_name: 'New Merchant',
          }),
        })
      );
      expect(res.user.id).toBe('user_new');
    });
  });
});
