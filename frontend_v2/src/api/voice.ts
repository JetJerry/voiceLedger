import { apiClient, getAccessToken } from './client';

export interface VoiceProcessResponse {
  action_taken: string;
  agent_reply: string;
  audio_base64?: string;
  intent?: string;
  product_name?: string;
  total_amount?: number;
  customer_name?: string;
  is_credit?: boolean;
  explanation?: string;
  items?: any[];
  sale?: any;
  sale_id?: string;
  product_id?: string;
}

export async function processVoiceTextApi(
  text: string,
  voiceLang: string = 'hi',
  speakResponse: boolean = true
): Promise<VoiceProcessResponse> {
  const payload = {
    text,
    voice_lang: voiceLang,
    speak_response: speakResponse,
  };

  try {
    return await apiClient.post<VoiceProcessResponse>(
      '/api/voice/process-text',
      payload,
      { requiresAuth: false }
    );
  } catch (err: any) {
    if (err?.status === 404 || err?.message?.includes('404') || err?.message?.includes('Not Found')) {
      return await apiClient.post<VoiceProcessResponse>(
        '/api/v1/voice/process-text',
        payload,
        { requiresAuth: false }
      );
    }
    throw err;
  }
}

export async function processVoiceAudioApi(audioBlob: Blob): Promise<VoiceProcessResponse> {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
  const token = getAccessToken();

  const formData = new FormData();
  formData.append('file', audioBlob, 'command.webm');

  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let response = await fetch(`${baseUrl}/api/voice/process-audio`, {
    method: 'POST',
    headers,
    body: formData,
  });

  if (response.status === 404) {
    const fallbackFormData = new FormData();
    fallbackFormData.append('file', audioBlob, 'command.webm');
    response = await fetch(`${baseUrl}/api/v1/voice/process-audio`, {
      method: 'POST',
      headers,
      body: fallbackFormData,
    });
  }

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Audio upload failed with status ${response.status}`);
  }

  return response.json();
}

export function getTtsAudioUrl(text: string, lang: string = 'hi'): string {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
  const q = new URLSearchParams({ text, lang });
  return `${baseUrl}/api/voice/speak?${q.toString()}`;
}

