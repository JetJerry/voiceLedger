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

  async processVoiceCommand(text) {
    const base = getApiBase();
    const res = await fetch(`${base}/voice/process-text`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ text, speak_response: true, voice_lang: 'hi' }),
    });
    if (!res.ok) {
      throw new Error(`Voice processing error: ${res.status}`);
    }
    return await res.json();
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
  }
};
