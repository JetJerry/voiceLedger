
import { getApiBase } from '../config/api';

export const apiService = {
  async getDashboardSummary() {
    const base = getApiBase();
    const res = await fetch(`${base}/dashboard/summary`);
    if (!res.ok) {
      throw new Error(`Failed to fetch dashboard summary: ${res.status}`);
    }
    return await res.json();
  },

  async processVoiceCommand(text, context = 'terminal', history = []) {
    const base = getApiBase();
    const res = await fetch(`${base}/voice/process-text`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        text,
        speak_response: true,
        voice_lang: 'hi',
        context,
        history,
      }),
    });
    if (!res.ok) {
      throw new Error(`Voice processing error: ${res.status}`);
    }
    return await res.json();
  },

  async getPaymentAnnouncements(merchantId = null) {
    const base = getApiBase();
    let url = `${base}/voice/payment-announcements`;
    if (merchantId) {
      url += `?merchant_id=${merchantId}`;
    }
    const res = await fetch(url);
    if (!res.ok) {
      return [];
    }
    return await res.json();
  },

  async acknowledgePaymentAnnouncement(announcementId) {
    const base = getApiBase();
    try {
      await fetch(`${base}/voice/payment-announcements/${announcementId}/ack`, {
        method: 'POST',
      });
    } catch (e) {
      console.warn('Ack announcement notice:', e.message);
    }
  },

  async simulatePayment(saleId, amount) {
    const base = getApiBase();
    const res = await fetch(`${base}/payments/simulate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        sale_id: saleId,
        amount: parseFloat(amount),
        status: 'captured',
      }),
    });
    if (!res.ok) {
      throw new Error(`Payment simulation failed: ${res.status}`);
    }
    return await res.json();
  },

  async getHealth() {
    const base = getApiBase();
    const healthUrl = base.replace(/\/api$/, '/api/health');
    const res = await fetch(healthUrl);
    if (!res.ok) {
      throw new Error(`Health check failed: ${res.status}`);
    }
    return await res.json();
  },

  // ── Webhooks & Reconciliation Logs ─────────────────────────────────
  async getWebhookLogs(limit = 50, status = null) {
    const base = getApiBase();
    let url = `${base}/webhooks/logs?limit=${limit}`;
    if (status) {
      url += `&status=${encodeURIComponent(status)}`;
    }
    const res = await fetch(url);
    if (!res.ok) {
      throw new Error(`Failed to fetch webhook logs: ${res.status}`);
    }
    return await res.json();
  },

  async retryWebhookEvent(eventId) {
    const base = getApiBase();
    const res = await fetch(`${base}/webhooks/logs/${eventId}/retry`, {
      method: 'POST',
    });
    if (!res.ok) {
      throw new Error(`Retry failed: ${res.status}`);
    }
    return await res.json();
  },

  // ── Open-Ended Catalog & Menu APIs ────────────────────────────────
  async getCatalogProducts(category = null, search = '') {
    const base = getApiBase();
    let url = `${base}/sales/catalog/products?active_only=true`;
    if (category && category !== 'ALL') {
      url += `&category=${encodeURIComponent(category)}`;
    }
    if (search) {
      url += `&search=${encodeURIComponent(search)}`;
    }
    const res = await fetch(url);
    if (!res.ok) {
      throw new Error(`Failed to fetch catalog: ${res.status}`);
    }
    return await res.json();
  },

  async addCatalogProduct(data) {
    const base = getApiBase();
    const res = await fetch(`${base}/sales/catalog/products`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Failed to add product: ${res.status}`);
    }
    return await res.json();
  },

  async updateCatalogProduct(productId, data) {
    const base = getApiBase();
    const res = await fetch(`${base}/sales/catalog/products/${productId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      throw new Error(`Failed to update product: ${res.status}`);
    }
    return await res.json();
  },

  async deleteCatalogProduct(productId) {
    const base = getApiBase();
    const res = await fetch(`${base}/sales/catalog/products/${productId}`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      throw new Error(`Failed to delete product: ${res.status}`);
    }
    return await res.json();
  },

  async listSales(limit = 100) {
    const base = getApiBase();
    const res = await fetch(`${base}/sales?limit=${limit}`);
    if (!res.ok) {
      throw new Error(`Failed to fetch sales: ${res.status}`);
    }
    return await res.json();
  },

  // ── Sales Analytics & Excel Export APIs ───────────────────────────
  async getSalesAnalytics(merchantId = null) {
    const base = getApiBase();
    let url = `${base}/sales/analytics/summary`;
    if (merchantId) {
      url += `?merchant_id=${merchantId}`;
    }
    const res = await fetch(url);
    if (!res.ok) {
      throw new Error(`Failed to fetch sales analytics: ${res.status}`);
    }
    return await res.json();
  },

  getExportExcelUrl(merchantId = null) {
    const base = getApiBase();
    let url = `${base}/sales/analytics/export/excel`;
    if (merchantId) {
      url += `?merchant_id=${merchantId}`;
    }
    return url;
  },

  // ── Admin Multi-Merchant Hub APIs ─────────────────────────────────
  async getAdminMetrics() {
    const base = getApiBase();
    const res = await fetch(`${base}/admin/metrics`);
    if (!res.ok) {
      throw new Error(`Failed to fetch admin metrics: ${res.status}`);
    }
    return await res.json();
  },

  async getAdminMerchants(search = '') {
    const base = getApiBase();
    const url = search ? `${base}/admin/merchants?search=${encodeURIComponent(search)}` : `${base}/admin/merchants`;
    const res = await fetch(url);
    if (!res.ok) {
      throw new Error(`Failed to fetch merchants: ${res.status}`);
    }
    return await res.json();
  },

  async getAdminMerchantDetail(merchantId) {
    const base = getApiBase();
    const res = await fetch(`${base}/admin/merchants/${merchantId}`);
    if (!res.ok) {
      throw new Error(`Failed to fetch merchant details: ${res.status}`);
    }
    return await res.json();
  },

  async createMerchant(data) {
    const base = getApiBase();
    const res = await fetch(`${base}/admin/merchants`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Failed to create merchant: ${res.status}`);
    }
    return await res.json();
  },

  async updateMerchant(merchantId, data) {
    const base = getApiBase();
    const res = await fetch(`${base}/admin/merchants/${merchantId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      throw new Error(`Failed to update merchant: ${res.status}`);
    }
    return await res.json();
  },

  async setActiveMerchant(merchantId) {
    const base = getApiBase();
    const res = await fetch(`${base}/admin/merchants/${merchantId}/set-active`, {
      method: 'POST',
    });
    if (!res.ok) {
      throw new Error(`Failed to switch active merchant: ${res.status}`);
    }
    return await res.json();
  },

  // ── Authentication & Roles APIs ───────────────────────────────────
  async login(username, password, role = 'merchant') {
    const base = getApiBase();
    const res = await fetch(`${base}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password, role }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Login failed. Please check your credentials.');
    }
    return await res.json();
  },

  async registerShopkeeper(data) {
    const base = getApiBase();
    const res = await fetch(`${base}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Registration failed.');
    }
    return await res.json();
  },

  async getDemoAccounts() {
    const base = getApiBase();
    const res = await fetch(`${base}/auth/demo-accounts`);
    if (!res.ok) {
      throw new Error(`Failed to fetch demo accounts: ${res.status}`);
    }
    return await res.json();
  },

  // ── Business Type & Catalog Voice APIs ────────────────────────────
  async getBusinessTypes() {
    const base = getApiBase();
    const res = await fetch(`${base}/sales/catalog/business-types`);
    if (!res.ok) {
      throw new Error(`Failed to fetch business types: ${res.status}`);
    }
    return await res.json();
  },

  async setBusinessType(businessType, applySampleItems = false) {
    const base = getApiBase();
    const res = await fetch(`${base}/sales/catalog/merchant/business-type`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ business_type: businessType, apply_sample_items: applySampleItems }),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Failed to set business type: ${res.status}`);
    }
    return await res.json();
  },

  async getMerchant() {
    const base = getApiBase();
    const res = await fetch(`${base}/sales/catalog/merchant`);
    if (!res.ok) {
      throw new Error(`Failed to fetch merchant: ${res.status}`);
    }
    return await res.json();
  },
};

