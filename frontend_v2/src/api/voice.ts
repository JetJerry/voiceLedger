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
  return apiClient.post<VoiceProcessResponse>(
    '/api/v1/voice/process-text',
    {
      text,
      voice_lang: voiceLang,
      speak_response: speakResponse,
    },
    { requiresAuth: true }
  );
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

  const response = await fetch(`${baseUrl}/api/v1/voice/process-audio`, {
    method: 'POST',
    headers,
    body: formData,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Audio upload failed with status ${response.status}`);
  }

  return response.json();
}

export function getTtsAudioUrl(text: string, lang: string = 'hi'): string {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
  const q = new URLSearchParams({ text, lang });
  return `${baseUrl}/api/v1/voice/speak?${q.toString()}`;
}
